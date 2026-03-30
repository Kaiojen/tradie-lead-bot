from __future__ import annotations

from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .enums import EnquiryStatus, MembershipRole, MessageStatus, UrgencyLevel
from .normalization import normalize_au_mobile, normalize_email, sanitize_text


class LeadIngestRequest(BaseModel):
    form_token: str = Field(min_length=8, max_length=255)
    customer_name: str = Field(min_length=1, max_length=255)
    customer_phone: str = Field(min_length=8, max_length=32)
    customer_email: EmailStr | None = None
    suburb: str = Field(min_length=1, max_length=255)
    service_requested: str = Field(min_length=1, max_length=255)
    raw_message: str | None = Field(default=None, max_length=2_000)
    consent_to_sms: bool = True

    @field_validator("customer_name", "suburb", "service_requested", "raw_message")
    @classmethod
    def sanitize_text_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value)

    @field_validator("customer_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_au_mobile(value)

    @field_validator("customer_email")
    @classmethod
    def validate_email(cls, value: EmailStr | None) -> str | None:
        return normalize_email(str(value)) if value else None


class LeadIngestResponse(BaseModel):
    lead_id: str
    status: str


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int


class MessageSummary(BaseModel):
    id: str
    recipient_type: str
    status: MessageStatus
    body: str
    created_at: datetime


class TimelineEvent(BaseModel):
    id: str
    event_type: str
    payload_json: dict[str, Any] | None = None
    created_at: datetime


class LeadNoteSummary(BaseModel):
    id: str
    user_id: str
    content: str
    created_at: datetime


class EnquiryListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_name: str
    suburb: str
    service_requested: str
    status: EnquiryStatus
    ai_status: str
    urgency_level: UrgencyLevel | None = None
    qualification_summary: str | None = None
    needs_review: bool = False
    has_failed_sms: bool = False
    has_failed_customer_sms: bool = False
    has_failed_tradie_sms: bool = False
    received_at: datetime


class EnquiryDetail(BaseModel):
    id: str
    status: EnquiryStatus
    ai_status: str
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    suburb: str
    service_requested: str
    urgency_level: UrgencyLevel | None = None
    qualification_summary: str | None = None
    needs_review: bool = False
    has_failed_sms: bool = False
    has_failed_customer_sms: bool = False
    has_failed_tradie_sms: bool = False
    messages: list[MessageSummary]
    timeline: list[TimelineEvent]
    notes: list[LeadNoteSummary]
    is_possible_duplicate: bool
    duplicate_of_lead_id: str | None = None
    received_at: datetime
    updated_at: datetime


class EnquiryListResponse(BaseModel):
    data: list[EnquiryListItem]
    pagination: PaginationMeta


class EnquiryStatusUpdateRequest(BaseModel):
    status: EnquiryStatus


class ActionResponse(BaseModel):
    status: str
    lead_id: str | None = None
    job_id: str | None = None


class AuthIdentity(BaseModel):
    user_id: str
    email: str | None = None


class AccountContext(BaseModel):
    account_id: str
    user_id: str
    role: MembershipRole
    email: str | None = None


class MembershipSummary(BaseModel):
    account_id: str
    role: MembershipRole


class MeResponse(BaseModel):
    user_id: str
    email: str | None = None
    memberships: list[MembershipSummary]


class AccountSettingsResponse(BaseModel):
    id: str
    business_name: str
    business_type: str | None = None
    primary_phone: str | None = None
    timezone: str
    country: str
    business_hours_start: time
    business_hours_end: time
    business_hours_tz: str
    onboarding_step: int
    onboarding_completed_at: datetime | None = None


class AccountSettingsUpdateRequest(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    business_type: str | None = Field(default=None, max_length=50)
    primary_phone: str | None = Field(default=None, min_length=8, max_length=32)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    business_hours_start: time | None = None
    business_hours_end: time | None = None
    business_hours_tz: str | None = Field(default=None, min_length=3, max_length=64)

    @field_validator("primary_phone")
    @classmethod
    def validate_primary_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_au_mobile(value)


class SetupBusinessBasicsRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    business_type: str = Field(min_length=1, max_length=50)

    @field_validator("business_name", "business_type")
    @classmethod
    def sanitize_basics_fields(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if sanitized is None:
            raise ValueError("field cannot be empty")
        return sanitized


class SetupNumberRequest(BaseModel):
    primary_phone: str = Field(min_length=8, max_length=32)
    business_hours_start: time | None = None
    business_hours_end: time | None = None
    business_hours_tz: str | None = Field(default=None, min_length=3, max_length=64)

    @field_validator("primary_phone")
    @classmethod
    def validate_setup_phone(cls, value: str) -> str:
        return normalize_au_mobile(value)


class TemplateSummaryResponse(BaseModel):
    id: str
    template_type: str
    content: str
    is_active: bool
    locale: str


class SetupConnectResponse(BaseModel):
    form_token: str
    embed_code: str
    google_business_link: str


class SetupResponse(BaseModel):
    account: AccountSettingsResponse
    connect: SetupConnectResponse


class BillingPortalResponse(BaseModel):
    url: str


class TemplateUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=800)
    is_active: bool = True

    @field_validator("content")
    @classmethod
    def sanitize_template_content(cls, value: str) -> str:
        sanitized = sanitize_text(value, max_length=800)
        if sanitized is None:
            raise ValueError("content cannot be empty")
        return sanitized


class SendTestSMSRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=32)

    @field_validator("phone_number")
    @classmethod
    def validate_test_phone(cls, value: str) -> str:
        return normalize_au_mobile(value)


class LeadNoteCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2_000)

    @field_validator("content")
    @classmethod
    def sanitize_note_content(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if sanitized is None:
            raise ValueError("content cannot be empty")
        return sanitized


class LeadNotesResponse(BaseModel):
    data: list[LeadNoteSummary]


class SubscriptionSummaryResponse(BaseModel):
    plan_code: str | None = None
    status: str | None = None
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    can_manage_billing: bool = False
    can_cancel: bool = False


class TeamMemberSummary(BaseModel):
    id: str
    user_id: str
    email: str
    role: MembershipRole
    invited_at: datetime | None = None
    accepted_at: datetime | None = None
    joined_at: datetime | None = None
    is_current_user: bool = False


class TeamMembersResponse(BaseModel):
    data: list[TeamMemberSummary]


class TeamInviteRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_invite_email(cls, value: EmailStr) -> str:
        normalized = normalize_email(str(value))
        if normalized is None:
            raise ValueError("email cannot be empty")
        return normalized


class SupportRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)

    @field_validator("message")
    @classmethod
    def sanitize_support_message(cls, value: str) -> str:
        sanitized = sanitize_text(value)
        if sanitized is None:
            raise ValueError("message cannot be empty")
        return sanitized


class APIError(BaseModel):
    error: str
    detail: str | None = None
