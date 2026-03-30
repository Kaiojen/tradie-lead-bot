from enum import StrEnum


class MembershipRole(StrEnum):
    OWNER = "owner"
    STAFF = "staff"


class EnquiryStatus(StrEnum):
    NEW = "new"
    FOLLOW_UP = "follow_up"
    DONE = "done"


class AIStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class UrgencyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class JobType(StrEnum):
    PROCESS_LEAD = "process_lead"
    SEND_SMS = "send_sms"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RecipientType(StrEnum):
    LEAD = "lead"
    TRADIE = "tradie"


class MessageStatus(StrEnum):
    QUEUED = "queued"
    SENT_TO_PROVIDER = "sent_to_provider"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


class TemplateType(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    QUALIFY = "qualify"
    URGENT = "urgent"
    AFTER_HOURS = "after_hours"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
