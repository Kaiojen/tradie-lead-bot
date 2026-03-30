from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shared.python.tradie_shared.schemas import (
    AccountContext,
    AccountSettingsResponse,
    AccountSettingsUpdateRequest,
    ActionResponse,
    AuthIdentity,
    BillingPortalResponse,
    MeResponse,
    SendTestSMSRequest,
    SetupBusinessBasicsRequest,
    SetupNumberRequest,
    SetupResponse,
    SubscriptionSummaryResponse,
    SupportRequest,
    TeamInviteRequest,
    TeamMembersResponse,
    TemplateSummaryResponse,
    TemplateUpdateRequest,
)

from ..core.errors import DomainError
from ..core.rate_limit import enforce_rate_limit
from ..dependencies.auth import get_account_context, get_auth_identity, require_owner
from ..dependencies.db import get_db_session
from ..services.accounts import (
    cancel_subscription_at_period_end,
    complete_setup,
    create_billing_portal_session,
    get_account,
    get_me,
    get_setup_state,
    get_subscription_summary,
    get_team_members,
    get_templates,
    invite_team_member,
    remove_team_member,
    send_test_sms,
    setup_auto_reply,
    setup_business_basics,
    setup_number,
    submit_support_request,
    update_account,
    update_template,
)

router = APIRouter(tags=["account"])
AccountContextDependency = Annotated[AccountContext, Depends(get_account_context)]
OwnerContextDependency = Annotated[AccountContext, Depends(require_owner)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
AuthIdentityDependency = Annotated[AuthIdentity, Depends(get_auth_identity)]


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/api/me", response_model=MeResponse)
async def me_route(
    request: Request,
    identity: AuthIdentityDependency,
    session: SessionDependency,
) -> MeResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{identity.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_me(
        session,
        user_id=identity.user_id,
        email=identity.email,
    )
    await session.commit()
    return response


@router.get("/api/account", response_model=AccountSettingsResponse)
async def get_account_route(
    request: Request,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> AccountSettingsResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_account(session, account_id=account_context.account_id)
    await session.commit()
    return response


@router.patch("/api/account", response_model=AccountSettingsResponse)
async def update_account_route(
    request: Request,
    payload: AccountSettingsUpdateRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> AccountSettingsResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await update_account(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.get("/api/setup", response_model=SetupResponse)
async def get_setup_route(
    request: Request,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> SetupResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_setup_state(
        session,
        account_id=account_context.account_id,
        settings=request.app.state.settings,
    )
    await session.commit()
    return response


@router.post("/api/setup/business-basics", response_model=AccountSettingsResponse)
async def setup_business_basics_route(
    request: Request,
    payload: SetupBusinessBasicsRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> AccountSettingsResponse:
    response = await setup_business_basics(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/setup/your-number", response_model=AccountSettingsResponse)
async def setup_number_route(
    request: Request,
    payload: SetupNumberRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> AccountSettingsResponse:
    response = await setup_number(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/setup/auto-reply", response_model=TemplateSummaryResponse)
async def setup_auto_reply_route(
    request: Request,
    payload: TemplateUpdateRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> TemplateSummaryResponse:
    response = await setup_auto_reply(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/setup/test-drive", response_model=ActionResponse)
async def setup_test_drive_route(
    request: Request,
    payload: SendTestSMSRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await send_test_sms(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        phone_number=payload.phone_number,
        body="Tradie Lead Bot test drive: your urgent job alerts are connected.",
        settings=request.app.state.settings,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/setup/complete", response_model=ActionResponse)
async def complete_setup_route(
    request: Request,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    response = await complete_setup(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.get("/api/templates", response_model=list[TemplateSummaryResponse])
async def get_templates_route(
    request: Request,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> list[TemplateSummaryResponse]:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_templates(session, account_id=account_context.account_id)
    await session.commit()
    return response


@router.patch("/api/templates/{template_id}", response_model=TemplateSummaryResponse)
async def update_template_route(
    request: Request,
    template_id: str,
    payload: TemplateUpdateRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> TemplateSummaryResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await update_template(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        template_id=template_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/templates/{template_id}/send-test", response_model=ActionResponse)
async def send_template_test_route(
    request: Request,
    template_id: str,
    payload: SendTestSMSRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    template = next(
        (
            template
            for template in await get_templates(session, account_id=account_context.account_id)
            if template.id == template_id
        ),
        None,
    )
    if template is None:
        raise DomainError(404, "not_found")
    response = await send_test_sms(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        phone_number=payload.phone_number,
        body=template.content.replace("[Business Name]", "Your Business").replace(
            "[Customer Name]",
            "Customer",
        ),
        settings=request.app.state.settings,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.get("/api/subscription", response_model=SubscriptionSummaryResponse)
async def get_subscription_route(
    request: Request,
    account_context: OwnerContextDependency,
    session: SessionDependency,
) -> SubscriptionSummaryResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_subscription_summary(session, account_id=account_context.account_id)
    await session.commit()
    return response


@router.post("/api/subscription/portal", response_model=BillingPortalResponse)
async def create_billing_portal_route(
    request: Request,
    account_context: OwnerContextDependency,
    session: SessionDependency,
) -> BillingPortalResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await create_billing_portal_session(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        settings=request.app.state.settings,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/subscription/cancel", response_model=SubscriptionSummaryResponse)
async def cancel_subscription_route(
    request: Request,
    account_context: OwnerContextDependency,
    session: SessionDependency,
) -> SubscriptionSummaryResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await cancel_subscription_at_period_end(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        settings=request.app.state.settings,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.get("/api/team", response_model=TeamMembersResponse)
async def get_team_route(
    request: Request,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> TeamMembersResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"api:{account_context.user_id}",
        limit=request.app.state.settings.api_rate_limit_per_minute,
    )
    response = await get_team_members(
        session,
        account_id=account_context.account_id,
        current_user_id=account_context.user_id,
    )
    await session.commit()
    return response


@router.post("/api/team/invite", response_model=ActionResponse)
async def invite_team_route(
    request: Request,
    payload: TeamInviteRequest,
    account_context: OwnerContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await invite_team_member(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        payload=payload,
        settings=request.app.state.settings,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.delete("/api/team/{membership_id}", response_model=ActionResponse)
async def remove_team_member_route(
    request: Request,
    membership_id: str,
    account_context: OwnerContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await remove_team_member(
        session,
        account_id=account_context.account_id,
        membership_id=membership_id,
        user_id=account_context.user_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response


@router.post("/api/support", response_model=ActionResponse)
async def support_route(
    request: Request,
    payload: SupportRequest,
    account_context: AccountContextDependency,
    session: SessionDependency,
) -> ActionResponse:
    await enforce_rate_limit(
        session,
        bucket_key=f"manual:{account_context.user_id}",
        limit=request.app.state.settings.manual_action_rate_limit_per_minute,
    )
    response = await submit_support_request(
        session,
        account_id=account_context.account_id,
        user_id=account_context.user_id,
        payload=payload,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return response
