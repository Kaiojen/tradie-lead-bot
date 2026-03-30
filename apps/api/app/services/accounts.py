from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from shared.python.tradie_shared.models import (
    Account,
    AccountMembership,
    LeadSource,
    Subscription,
    Template,
    User,
)
from shared.python.tradie_shared.operations import append_audit_log
from shared.python.tradie_shared.schemas import (
    AccountSettingsResponse,
    AccountSettingsUpdateRequest,
    ActionResponse,
    BillingPortalResponse,
    MembershipSummary,
    MeResponse,
    SetupBusinessBasicsRequest,
    SetupConnectResponse,
    SetupNumberRequest,
    SetupResponse,
    SubscriptionSummaryResponse,
    SupportRequest,
    TeamInviteRequest,
    TeamMemberSummary,
    TeamMembersResponse,
    TemplateSummaryResponse,
    TemplateUpdateRequest,
)
from shared.python.tradie_shared.settings import AppSettings

from ..core.errors import DomainError
from .webhooks import _extract_subscription_snapshot, _map_account_status

DEFAULT_ACKNOWLEDGE_TEMPLATE = (
    "Thanks for reaching out to [Business Name]. We're on a job right now and will get back to "
    "you shortly. What suburb are you in and what do you need help with?"
)
DEFAULT_QUALIFY_TEMPLATE = (
    "Thanks for your enquiry to [Business Name]. Please reply with your suburb and a short note "
    "about the job, and we'll get back to you shortly."
)
DEFAULT_URGENT_TEMPLATE = (
    "Thanks for contacting [Business Name]. If this is urgent, reply with your suburb and what "
    "happened. We'll review it as soon as possible."
)
DEFAULT_AFTER_HOURS_TEMPLATE = (
    "Thanks for your enquiry to [Business Name]. We're currently outside business hours, but "
    "we'll get back to you as soon as we're back on the tools."
)
PADDLE_API_BASE_URL = "https://api.paddle.com"
SUPABASE_ADMIN_INVITE_PATH = "/auth/v1/admin/invite"


def serialize_account(account: Account) -> AccountSettingsResponse:
    return AccountSettingsResponse(
        id=account.id,
        business_name=account.business_name,
        business_type=account.business_type,
        primary_phone=account.primary_phone,
        timezone=account.timezone,
        country=account.country,
        business_hours_start=account.business_hours_start,
        business_hours_end=account.business_hours_end,
        business_hours_tz=account.business_hours_tz,
        onboarding_step=account.onboarding_step,
        onboarding_completed_at=account.onboarding_completed_at,
    )


def _serialize_subscription_summary(
    *,
    account: Account,
    subscription: Subscription | None,
) -> SubscriptionSummaryResponse:
    if subscription is None:
        derived_status = {
            "trial": "trialing",
            "active": "active",
            "suspended": "past_due",
            "cancelled": "cancelled",
        }.get(account.status)
        return SubscriptionSummaryResponse(
            plan_code=account.plan_code,
            status=derived_status,
        )

    cancel_at_period_end = bool(subscription.cancel_at_period_end)
    is_cancelled = subscription.status in {"cancelled", "canceled"}
    return SubscriptionSummaryResponse(
        plan_code=subscription.plan_code,
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=cancel_at_period_end,
        can_manage_billing=bool(subscription.provider_customer_id),
        can_cancel=bool(
            subscription.provider_subscription_id
            and not cancel_at_period_end
            and not is_cancelled
        ),
    )


def _extract_portal_session_url(payload: dict) -> str | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    direct_url = data.get("url")
    if isinstance(direct_url, str) and direct_url.strip():
        return direct_url
    urls = data.get("urls")
    if not isinstance(urls, dict):
        return None
    general_urls = urls.get("general")
    if not isinstance(general_urls, dict):
        return None
    overview_url = general_urls.get("overview")
    if isinstance(overview_url, str) and overview_url.strip():
        return overview_url
    return None


def _extract_supabase_user_id(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None
    candidates = (
        payload.get("id"),
        payload.get("user", {}).get("id") if isinstance(payload.get("user"), dict) else None,
        payload.get("data", {}).get("id") if isinstance(payload.get("data"), dict) else None,
        payload.get("data", {}).get("user", {}).get("id")
        if isinstance(payload.get("data"), dict)
        and isinstance(payload.get("data", {}).get("user"), dict)
        else None,
    )
    return next(
        (
            candidate
            for candidate in candidates
            if isinstance(candidate, str) and candidate.strip()
        ),
        None,
    )


def _serialize_team_member(
    *,
    membership: AccountMembership,
    user: User,
    current_user_id: str,
) -> TeamMemberSummary:
    joined_at = membership.accepted_at or membership.invited_at or user.created_at
    return TeamMemberSummary(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        role=membership.role,
        invited_at=membership.invited_at,
        accepted_at=membership.accepted_at,
        joined_at=joined_at,
        is_current_user=user.id == current_user_id,
    )


async def _post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict,
    upstream_name: str,
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise DomainError(502, f"{upstream_name}_unavailable", str(exc)) from exc

    if response.is_success:
        payload_json = response.json()
        if isinstance(payload_json, dict):
            return payload_json
        raise DomainError(502, f"{upstream_name}_invalid_response")

    detail = None
    try:
        error_payload = response.json()
    except ValueError:
        error_payload = None
    if isinstance(error_payload, dict):
        detail = (
            error_payload.get("detail")
            or error_payload.get("error_description")
            or error_payload.get("message")
            or error_payload.get("error")
        )
    raise DomainError(
        502,
        f"{upstream_name}_request_failed",
        detail or f"{upstream_name} returned {response.status_code}",
    )


async def _post_paddle_json(
    *,
    path: str,
    payload: dict,
    settings: AppSettings,
) -> dict:
    if not settings.paddle_api_key:
        raise DomainError(503, "billing_not_configured")
    return await _post_json(
        url=f"{PADDLE_API_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {settings.paddle_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        payload=payload,
        upstream_name="paddle",
    )


async def _invite_supabase_user(
    *,
    email: str,
    account_id: str,
    settings: AppSettings,
) -> str:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise DomainError(503, "auth_not_configured")

    payload = {
        "email": email,
        "data": {"account_id": account_id},
        "redirect_to": f"{settings.web_base_url}/inbox",
    }
    response = await _post_json(
        url=f"{settings.supabase_url.rstrip('/')}{SUPABASE_ADMIN_INVITE_PATH}",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": "application/json",
        },
        payload=payload,
        upstream_name="supabase",
    )
    user_id = _extract_supabase_user_id(response)
    if not user_id:
        raise DomainError(502, "supabase_invalid_response", "Invite response missing user id")
    return user_id


async def get_me(session: AsyncSession, *, user_id: str, email: str | None) -> MeResponse:
    memberships = list(
        (
            await session.scalars(
                select(AccountMembership).where(AccountMembership.user_id == user_id)
            )
        ).all()
    )
    return MeResponse(
        user_id=user_id,
        email=email,
        memberships=[
            MembershipSummary(account_id=membership.account_id, role=membership.role)
            for membership in memberships
        ],
    )


async def get_account(session: AsyncSession, *, account_id: str) -> AccountSettingsResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    return serialize_account(account)


async def update_account(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    payload: AccountSettingsUpdateRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> AccountSettingsResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")

    for field_name, value in payload.model_dump(exclude_none=True).items():
        setattr(account, field_name, value)

    account.updated_at = datetime.now(UTC)
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="account_updated",
        entity_type="account",
        entity_id=account.id,
        metadata_json=payload.model_dump(exclude_none=True),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return serialize_account(account)


async def ensure_default_templates(session: AsyncSession, *, account_id: str) -> None:
    existing_types = set(
        (
            await session.scalars(
                select(Template.template_type).where(Template.account_id == account_id)
            )
        ).all()
    )
    defaults = {
        "acknowledge": DEFAULT_ACKNOWLEDGE_TEMPLATE,
        "qualify": DEFAULT_QUALIFY_TEMPLATE,
        "urgent": DEFAULT_URGENT_TEMPLATE,
        "after_hours": DEFAULT_AFTER_HOURS_TEMPLATE,
    }
    for template_type, content in defaults.items():
        if template_type in existing_types:
            continue
        session.add(
            Template(
                account_id=account_id,
                template_type=template_type,
                content=content,
                is_default=True,
                is_active=True,
                variables_schema=["customer_name", "business_name"],
            )
        )
    await session.flush()


async def get_templates(session: AsyncSession, *, account_id: str) -> list[TemplateSummaryResponse]:
    await ensure_default_templates(session, account_id=account_id)
    templates = list(
        (
            await session.scalars(
                select(Template)
                .where(Template.account_id == account_id)
                .order_by(Template.template_type.asc(), Template.version.desc())
            )
        ).all()
    )
    return [
        TemplateSummaryResponse(
            id=template.id,
            template_type=template.template_type,
            content=template.content,
            is_active=template.is_active,
            locale=template.locale,
        )
        for template in templates
    ]


async def update_template(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    template_id: str,
    payload: TemplateUpdateRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> TemplateSummaryResponse:
    template = await session.scalar(
        select(Template).where(Template.account_id == account_id, Template.id == template_id)
    )
    if template is None:
        raise DomainError(404, "not_found")

    template.content = payload.content
    template.is_active = payload.is_active
    template.version += 1
    template.active_version = template.version
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="auto_reply_updated",
        entity_type="template",
        entity_id=template.id,
        metadata_json={"template_type": template.template_type},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return TemplateSummaryResponse(
        id=template.id,
        template_type=template.template_type,
        content=template.content,
        is_active=template.is_active,
        locale=template.locale,
    )


async def send_test_sms(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    phone_number: str,
    body: str,
    settings: AppSettings,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    if (
        settings.twilio_account_sid is None
        or settings.twilio_auth_token is None
        or settings.twilio_messaging_service_sid is None
    ):
        raise DomainError(503, "sms_not_configured")

    twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    try:
        response = await asyncio.to_thread(
            twilio_client.messages.create,
                body=body,
                to=phone_number,
                messaging_service_sid=settings.twilio_messaging_service_sid,
                status_callback=f"{settings.api_base_url}/webhooks/twilio",
        )
    except TwilioRestException as exc:
        raise DomainError(502, "sms_failed", str(exc)) from exc

    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="test_sms_sent",
        entity_type="account",
        entity_id=account_id,
        metadata_json={"provider_message_id": response.sid, "phone_number": phone_number},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="queued")


async def get_or_create_primary_lead_source(
    session: AsyncSession,
    *,
    account_id: str,
) -> LeadSource:
    lead_source = await session.scalar(
        select(LeadSource)
        .where(LeadSource.account_id == account_id, LeadSource.type == "web_form")
        .order_by(LeadSource.id.asc())
    )
    if lead_source is not None:
        return lead_source

    lead_source = LeadSource(
        account_id=account_id,
        type="web_form",
        external_key=secrets.token_urlsafe(24),
        is_active=True,
    )
    session.add(lead_source)
    await session.flush()
    return lead_source


async def get_setup_state(
    session: AsyncSession,
    *,
    account_id: str,
    settings: AppSettings,
) -> SetupResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    lead_source = await get_or_create_primary_lead_source(session, account_id=account_id)
    embed_code = (
        f'<script src="{settings.web_base_url}/embed.js" '
        f'data-form-token="{lead_source.external_key}"></script>'
    )
    google_business_link = f"{settings.web_base_url}/f/{lead_source.external_key}"
    return SetupResponse(
        account=serialize_account(account),
        connect=SetupConnectResponse(
            form_token=lead_source.external_key,
            embed_code=embed_code,
            google_business_link=google_business_link,
        ),
    )


async def setup_business_basics(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    payload: SetupBusinessBasicsRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> AccountSettingsResponse:
    await update_account(
        session,
        account_id=account_id,
        user_id=user_id,
        payload=AccountSettingsUpdateRequest(
            business_name=payload.business_name,
            business_type=payload.business_type,
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    account.onboarding_step = max(account.onboarding_step, 2)
    return serialize_account(account)


async def setup_number(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    payload: SetupNumberRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> AccountSettingsResponse:
    await update_account(
        session,
        account_id=account_id,
        user_id=user_id,
        payload=AccountSettingsUpdateRequest(
            primary_phone=payload.primary_phone,
            business_hours_start=payload.business_hours_start,
            business_hours_end=payload.business_hours_end,
            business_hours_tz=payload.business_hours_tz,
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    account.onboarding_step = max(account.onboarding_step, 3)
    return serialize_account(account)


async def setup_auto_reply(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    payload: TemplateUpdateRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> TemplateSummaryResponse:
    await ensure_default_templates(session, account_id=account_id)
    template = await session.scalar(
        select(Template).where(
            Template.account_id == account_id,
            Template.template_type == "acknowledge",
        )
    )
    if template is None:
        raise DomainError(404, "not_found")
    response = await update_template(
        session,
        account_id=account_id,
        user_id=user_id,
        template_id=template.id,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    account.onboarding_step = max(account.onboarding_step, 4)
    return response


async def complete_setup(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    await get_or_create_primary_lead_source(session, account_id=account_id)
    account.onboarding_step = 5
    account.onboarding_completed_at = datetime.now(UTC)
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="setup_completed",
        entity_type="account",
        entity_id=account_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="completed")


async def get_subscription_summary(
    session: AsyncSession,
    *,
    account_id: str,
) -> SubscriptionSummaryResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    subscription = await session.scalar(
        select(Subscription).where(Subscription.account_id == account_id)
    )
    return _serialize_subscription_summary(account=account, subscription=subscription)


async def create_billing_portal_session(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    settings: AppSettings,
    ip_address: str | None,
    user_agent: str | None,
) -> BillingPortalResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    subscription = await session.scalar(
        select(Subscription).where(Subscription.account_id == account_id)
    )
    if subscription is None or not subscription.provider_customer_id:
        raise DomainError(409, "billing_portal_unavailable")

    response = await _post_paddle_json(
        path=f"/customers/{subscription.provider_customer_id}/portal-sessions",
        payload={"return_url": f"{settings.web_base_url}/subscription"},
        settings=settings,
    )
    portal_url = _extract_portal_session_url(response)
    if not portal_url:
        raise DomainError(502, "paddle_invalid_response", "Portal session URL missing")

    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="billing_portal_opened",
        entity_type="subscription",
        entity_id=subscription.id,
        metadata_json={"provider_customer_id": subscription.provider_customer_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return BillingPortalResponse(url=portal_url)


async def cancel_subscription_at_period_end(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    settings: AppSettings,
    ip_address: str | None,
    user_agent: str | None,
) -> SubscriptionSummaryResponse:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise DomainError(404, "not_found")
    subscription = await session.scalar(
        select(Subscription).where(Subscription.account_id == account_id)
    )
    if subscription is None or not subscription.provider_subscription_id:
        raise DomainError(409, "subscription_unavailable")
    if subscription.cancel_at_period_end:
        return _serialize_subscription_summary(account=account, subscription=subscription)

    response = await _post_paddle_json(
        path=f"/subscriptions/{subscription.provider_subscription_id}/cancel",
        payload={"effective_from": "next_billing_period"},
        settings=settings,
    )
    snapshot = _extract_subscription_snapshot(response, event_type="subscription.updated")
    for field_name in (
        "status",
        "plan_code",
        "trial_ends_at",
        "current_period_end",
        "cancel_at_period_end",
    ):
        field_value = snapshot[field_name]
        if field_value is None and field_name != "cancel_at_period_end":
            continue
        setattr(subscription, field_name, field_value)

    if subscription.status:
        mapped_status = _map_account_status(subscription.status)
        if mapped_status:
            account.status = mapped_status
    if subscription.plan_code:
        account.plan_code = subscription.plan_code

    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="subscription_cancel_scheduled",
        entity_type="subscription",
        entity_id=subscription.id,
        metadata_json={
            "provider_subscription_id": subscription.provider_subscription_id,
            "current_period_end": subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return _serialize_subscription_summary(account=account, subscription=subscription)


async def get_team_members(
    session: AsyncSession,
    *,
    account_id: str,
    current_user_id: str,
) -> TeamMembersResponse:
    rows = list(
        (
            await session.execute(
                select(AccountMembership, User)
                .join(User, User.id == AccountMembership.user_id)
                .where(AccountMembership.account_id == account_id)
            )
        ).all()
    )
    members = [
        _serialize_team_member(
            membership=membership,
            user=user,
            current_user_id=current_user_id,
        )
        for membership, user in rows
    ]
    members.sort(key=lambda member: (0 if member.role == "owner" else 1, member.email.lower()))
    return TeamMembersResponse(data=members)


async def invite_team_member(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    payload: TeamInviteRequest,
    settings: AppSettings,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    existing_user = await session.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        existing_membership = await session.scalar(
            select(AccountMembership).where(
                AccountMembership.account_id == account_id,
                AccountMembership.user_id == existing_user.id,
            )
        )
        if existing_membership is not None:
            raise DomainError(409, "member_already_exists")

    invited_user_id = await _invite_supabase_user(
        email=payload.email,
        account_id=account_id,
        settings=settings,
    )
    invited_user = existing_user or await session.scalar(
        select(User).where(User.id == invited_user_id)
    )
    if invited_user is None:
        invited_user = User(
            id=invited_user_id,
            email=payload.email,
            auth_provider="supabase",
            is_active=True,
        )
        session.add(invited_user)
        await session.flush()

    membership = AccountMembership(
        account_id=account_id,
        user_id=invited_user.id,
        role="staff",
        invited_at=datetime.now(UTC),
    )
    session.add(membership)
    await session.flush()

    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="team_member_invited",
        entity_type="account_membership",
        entity_id=membership.id,
        metadata_json={"email": payload.email, "role": membership.role},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="invited")


async def remove_team_member(
    session: AsyncSession,
    *,
    account_id: str,
    membership_id: str,
    user_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    membership = await session.scalar(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.id == membership_id,
        )
    )
    if membership is None:
        raise DomainError(404, "not_found")
    if membership.user_id == user_id:
        raise DomainError(400, "cannot_remove_self")

    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="team_member_removed",
        entity_type="account_membership",
        entity_id=membership.id,
        metadata_json={"removed_user_id": membership.user_id, "role": membership.role},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await session.delete(membership)
    return ActionResponse(status="removed")


async def submit_support_request(
    session: AsyncSession,
    *,
    account_id: str,
    user_id: str,
    payload: SupportRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> ActionResponse:
    await append_audit_log(
        session,
        account_id=account_id,
        user_id=user_id,
        action="support_requested",
        entity_type="account",
        entity_id=account_id,
        metadata_json={"message": payload.message},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ActionResponse(status="received")
