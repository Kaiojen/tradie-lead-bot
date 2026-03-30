from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sentry_sdk
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from shared.python.tradie_shared.db import build_session_factory
from shared.python.tradie_shared.logging import configure_logging, get_logger
from shared.python.tradie_shared.models import (
    Account,
    Lead,
    Message,
    MessageAttempt,
    ProcessingJob,
    Template,
)
from shared.python.tradie_shared.operations import (
    append_audit_log,
    append_lead_event,
    queue_processing_job,
)
from shared.python.tradie_shared.security import SensitiveDataCipher, mask_phone
from shared.python.tradie_shared.settings import AppSettings, get_settings

LOGGER = get_logger(__name__)
PHONE_LOG_PATTERN = re.compile(r"\+?\d[\d\s-]{6,}\d")


class AIQualificationResult(BaseModel):
    summary: str = Field(min_length=1)
    urgency_level: str
    extracted_fields: dict[str, str | None]


@dataclass
class ClaimedJob:
    id: str
    account_id: str
    lead_id: str
    job_type: str
    attempts: int
    max_attempts: int


class RetryableJobError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def build_tradie_alert_body(
    *,
    business_name: str,
    lead: Lead,
    customer_phone: str,
    ai_result: AIQualificationResult | None,
) -> str:
    if ai_result is None:
        fallback_parts = [
            f"New enquiry for {business_name}.",
            f"Name: {lead.customer_name}.",
            f"Phone: {customer_phone}.",
            f"Suburb: {lead.suburb}.",
            f"Service: {lead.service_requested}.",
        ]
        if lead.raw_text:
            fallback_parts.append(f"Notes: {lead.raw_text}.")
        return " ".join(fallback_parts)

    return (
        f"New Job Alert for {business_name}: {lead.customer_name} {customer_phone}. "
        f"{ai_result.summary} Urgency: {ai_result.urgency_level}."
    )


def mask_message_body_for_logs(body: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        digits_only = re.sub(r"\D", "", match.group(0))
        return mask_phone(digits_only) or "***"

    return PHONE_LOG_PATTERN.sub(_replace, body)


class WorkerService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.session_factory = build_session_factory(settings)
        self.cipher = SensitiveDataCipher(settings.app_encryption_key)
        self.openai_client = (
            AsyncOpenAI(api_key=settings.openai_api_key)
            if settings.openai_api_key
            else None
        )
        self.twilio_client = (
            Client(settings.twilio_account_sid, settings.twilio_auth_token)
            if settings.twilio_account_sid and settings.twilio_auth_token
            else None
        )
        self.watchdog_started_at = datetime.now(UTC)

    async def run(self) -> None:
        LOGGER.info("worker_started")
        while True:
            try:
                await self._watchdog_if_needed()
                job = await self._claim_next_job()
                if job is None:
                    await asyncio.sleep(self.settings.job_poll_interval_seconds)
                    continue

                try:
                    await self._handle_job(job)
                except RetryableJobError as exc:
                    await self._schedule_retry(job, exc)
                except Exception as exc:  # pragma: no cover - defensive runtime guard
                    LOGGER.exception("worker_job_failed", extra={"extra_data": {"job_id": job.id}})
                    await self._schedule_retry(job, RetryableJobError("unhandled_error", str(exc)))
            except Exception:  # pragma: no cover - top-level resilience
                LOGGER.exception("worker_loop_failed")
                await asyncio.sleep(self.settings.job_poll_interval_seconds)

    async def _watchdog_if_needed(self) -> None:
        now = datetime.now(UTC)
        if now - self.watchdog_started_at < timedelta(
            seconds=self.settings.watchdog_interval_seconds
        ):
            return
        self.watchdog_started_at = now
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    update(ProcessingJob)
                    .where(
                        ProcessingJob.status == "processing",
                        ProcessingJob.locked_until.is_not(None),
                        ProcessingJob.locked_until < now,
                    )
                    .values(
                        status="pending",
                        locked_until=None,
                        scheduled_at=now,
                        error_code="lock_expired",
                        error_message="Lock expired and job was re-queued by watchdog",
                    )
                )
                result = await session.execute(stmt)
                if result.rowcount:
                    LOGGER.warning(
                        "watchdog_requeued_jobs",
                        extra={"extra_data": {"count": result.rowcount}},
                    )

    async def _claim_next_job(self) -> ClaimedJob | None:
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    select(ProcessingJob)
                    .where(
                        ProcessingJob.status == "pending",
                        ProcessingJob.scheduled_at <= datetime.now(UTC),
                    )
                    .order_by(ProcessingJob.scheduled_at.asc())
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                job = await session.scalar(stmt)
                if job is None:
                    return None

                job.status = "processing"
                job.attempts += 1
                job.locked_until = datetime.now(UTC) + timedelta(
                    seconds=self.settings.job_lock_ttl_seconds
                )
                return ClaimedJob(
                    id=job.id,
                    account_id=job.account_id,
                    lead_id=job.lead_id,
                    job_type=job.job_type,
                    attempts=job.attempts,
                    max_attempts=job.max_attempts,
                )

    async def _handle_job(self, job: ClaimedJob) -> None:
        if job.job_type == "process_lead":
            await self._process_lead_job(job)
        elif job.job_type == "send_sms":
            await self._send_sms_job(job)
        else:
            raise RetryableJobError("unsupported_job_type", job.job_type)

        async with self.session_factory() as session:
            async with session.begin():
                job_record = await session.get(ProcessingJob, job.id, with_for_update=True)
                if job_record is None:
                    return
                job_record.status = "completed"
                job_record.locked_until = None
                job_record.processed_at = datetime.now(UTC)
                job_record.error_code = None
                job_record.error_message = None

    async def _schedule_retry(self, job: ClaimedJob, exc: RetryableJobError) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                job_record = await session.get(ProcessingJob, job.id, with_for_update=True)
                if job_record is None:
                    return

                if job_record.attempts >= job_record.max_attempts:
                    job_record.status = "failed"
                    job_record.locked_until = None
                    job_record.processed_at = datetime.now(UTC)
                    job_record.error_code = exc.code
                    job_record.error_message = exc.detail
                    await append_audit_log(
                        session,
                        account_id=job_record.account_id,
                        action="processing_job_failed",
                        entity_type="processing_job",
                        entity_id=job_record.id,
                        metadata_json={"job_type": job_record.job_type, "error_code": exc.code},
                    )
                    return

                backoff_seconds = 2 ** job_record.attempts
                job_record.status = "pending"
                job_record.locked_until = None
                job_record.scheduled_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
                job_record.error_code = exc.code
                job_record.error_message = exc.detail

    async def _process_lead_job(self, job: ClaimedJob) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                lead = await session.scalar(
                    select(Lead).where(Lead.account_id == job.account_id, Lead.id == job.lead_id)
                )
                account = await session.scalar(select(Account).where(Account.id == job.account_id))
                if lead is None or account is None:
                    raise RetryableJobError("lead_not_found", "Lead or account not found")

                acknowledge_template = await session.scalar(
                    select(Template).where(
                        Template.account_id == job.account_id,
                        Template.template_type == "acknowledge",
                        Template.is_active.is_(True),
                    )
                )
                urgent_template = await session.scalar(
                    select(Template).where(
                        Template.account_id == job.account_id,
                        Template.template_type == "urgent",
                        Template.is_active.is_(True),
                    )
                )
                existing_messages = int(
                    await session.scalar(
                        select(func.count(Message.id)).where(
                            Message.account_id == job.account_id,
                            Message.lead_id == job.lead_id,
                        )
                    )
                    or 0
                )
                duplicate_candidate = await session.scalar(
                    select(Lead)
                    .where(
                        Lead.account_id == job.account_id,
                        Lead.id != job.lead_id,
                        Lead.customer_phone_hash == lead.customer_phone_hash,
                        Lead.received_at
                        >= datetime.now(UTC)
                        - timedelta(minutes=self.settings.default_duplicate_window_minutes),
                    )
                    .order_by(Lead.received_at.desc())
                    .limit(1)
                )
                customer_phone = self.cipher.decrypt(lead.customer_phone) or ""
                customer_email = (
                    self.cipher.decrypt(lead.customer_email) if lead.customer_email else None
                )
                raw_payload = {
                    "customer_name": lead.customer_name,
                    "customer_phone": customer_phone,
                    "customer_email": customer_email,
                    "suburb": lead.suburb,
                    "service_requested": lead.service_requested,
                    "raw_text": lead.raw_text,
                }

            ai_result: AIQualificationResult | None = None
            ai_failed = False
            if self.openai_client:
                try:
                    ai_result = await self._qualify_lead(raw_payload)
                except Exception as exc:
                    ai_failed = True
                    LOGGER.exception(
                        "ai_qualification_failed",
                        extra={
                            "extra_data": {
                                "lead_id": job.lead_id,
                                "customer_phone": mask_phone(customer_phone),
                            }
                        },
                    )
                    ai_error = str(exc)
            else:
                ai_failed = True
                ai_error = "OPENAI_API_KEY is not configured"

            async with session.begin():
                lead = await session.scalar(
                    select(Lead).where(Lead.account_id == job.account_id, Lead.id == job.lead_id)
                )
                if lead is None:
                    raise RetryableJobError("lead_not_found", "Lead disappeared during processing")

                lead.normalized_text = self._build_normalized_text(raw_payload)
                if duplicate_candidate is not None:
                    lead.is_possible_duplicate = True
                    lead.duplicate_of_lead_id = duplicate_candidate.id
                    await append_lead_event(
                        session,
                        account_id=job.account_id,
                        lead_id=job.lead_id,
                        event_type="possible_duplicate",
                        payload_json={"duplicate_of_lead_id": duplicate_candidate.id},
                    )

                if ai_result is not None:
                    lead.ai_status = "completed"
                    lead.urgency_level = ai_result.urgency_level
                    lead.qualification_summary = ai_result.summary
                    await append_lead_event(
                        session,
                        account_id=job.account_id,
                        lead_id=job.lead_id,
                        event_type="qualified",
                        payload_json={
                            "urgency_level": ai_result.urgency_level,
                            "extracted_fields": ai_result.extracted_fields,
                        },
                    )
                    await append_audit_log(
                        session,
                        account_id=job.account_id,
                        action="ai_executed",
                        entity_type="lead",
                        entity_id=job.lead_id,
                        metadata_json={"urgency_level": ai_result.urgency_level},
                    )
                else:
                    lead.ai_status = "failed"
                    await append_lead_event(
                        session,
                        account_id=job.account_id,
                        lead_id=job.lead_id,
                        event_type="ai_failed",
                        payload_json={"error": ai_error},
                    )
                    await append_audit_log(
                        session,
                        account_id=job.account_id,
                        action="ai_failed",
                        entity_type="lead",
                        entity_id=job.lead_id,
                        metadata_json={"error": ai_error},
                    )

                if duplicate_candidate is None and existing_messages == 0:
                    customer_template = (
                        urgent_template
                        if ai_result and ai_result.urgency_level in {"high", "emergency"}
                        else acknowledge_template
                    )
                    tradie_message: Message | None = None
                    if lead.consent_to_sms:
                        customer_message = Message(
                            account_id=job.account_id,
                            lead_id=job.lead_id,
                            recipient_type="lead",
                            recipient_value=customer_phone,
                            template_id=customer_template.id if customer_template else None,
                            body=self._build_customer_reply(
                                business_name=account.business_name,
                                customer_name=lead.customer_name,
                                template=customer_template.content if customer_template else None,
                            ),
                        )
                        session.add(customer_message)
                    if account.primary_phone:
                        tradie_message = Message(
                            account_id=job.account_id,
                            lead_id=job.lead_id,
                            recipient_type="tradie",
                            recipient_value=account.primary_phone,
                            template_id=None,
                            body=self._build_tradie_alert(
                                business_name=account.business_name,
                                lead=lead,
                                customer_phone=customer_phone,
                                ai_result=ai_result,
                            ),
                        )
                        session.add(tradie_message)
                    await session.flush()
                    send_job = await queue_processing_job(
                        session,
                        account_id=job.account_id,
                        lead_id=job.lead_id,
                        job_type="send_sms",
                    )
                    if ai_failed and tradie_message is not None:
                        await append_lead_event(
                            session,
                            account_id=job.account_id,
                            lead_id=job.lead_id,
                            event_type="fallback_tradie_alert_queued",
                            payload_json={
                                "job_id": send_job.id,
                                "message_id": tradie_message.id,
                            },
                        )
                    await append_audit_log(
                        session,
                        account_id=job.account_id,
                        action="send_sms_job_created",
                        entity_type="processing_job",
                        entity_id=send_job.id,
                        metadata_json={"lead_id": job.lead_id},
                    )

            if ai_failed:
                raise RetryableJobError("ai_failed", ai_error)

    async def _send_sms_job(self, job: ClaimedJob) -> None:
        if self.twilio_client is None or not self.settings.twilio_messaging_service_sid:
            raise RetryableJobError(
                "twilio_not_configured",
                "Twilio credentials or messaging service SID are missing",
            )

        async with self.session_factory() as session:
            async with session.begin():
                messages = list(
                    (
                        await session.scalars(
                            select(Message)
                            .where(
                                Message.account_id == job.account_id,
                                Message.lead_id == job.lead_id,
                                Message.status.in_(("queued", "failed", "undelivered")),
                            )
                            .order_by(Message.created_at.asc())
                        )
                    ).all()
                )

            if not messages:
                return

            had_failure = False
            for message in messages:
                try:
                    provider_response = await asyncio.to_thread(
                        self.twilio_client.messages.create,
                        body=message.body,
                        to=message.recipient_value,
                        messaging_service_sid=self.settings.twilio_messaging_service_sid,
                        status_callback=f"{self.settings.api_base_url}/webhooks/twilio",
                    )
                    async with session.begin():
                        message_record = await session.get(
                            Message,
                            message.id,
                            with_for_update=True,
                        )
                        if message_record is None:
                            continue
                        message_record.status = "sent_to_provider"
                        message_record.provider_message_id = provider_response.sid
                        session.add(
                            MessageAttempt(
                                message_id=message_record.id,
                                attempt_number=job.attempts,
                                request_payload_json={
                                    "to": mask_phone(message_record.recipient_value),
                                    "body": mask_message_body_for_logs(message_record.body),
                                },
                                provider_response_json={
                                    "sid": provider_response.sid,
                                    "status": provider_response.status,
                                },
                                provider_status=provider_response.status,
                            )
                        )
                        await append_lead_event(
                            session,
                            account_id=message_record.account_id,
                            lead_id=message_record.lead_id,
                            event_type="sms_sent",
                            payload_json={
                                "message_id": message_record.id,
                                "recipient_type": message_record.recipient_type,
                            },
                        )
                        await append_audit_log(
                            session,
                            account_id=message_record.account_id,
                            action="sms_sent_to_provider",
                            entity_type="message",
                            entity_id=message_record.id,
                            metadata_json={
                                "recipient_type": message_record.recipient_type,
                                "provider_message_id": provider_response.sid,
                            },
                        )
                except TwilioRestException as exc:
                    had_failure = True
                    async with session.begin():
                        message_record = await session.get(
                            Message,
                            message.id,
                            with_for_update=True,
                        )
                        if message_record is None:
                            continue
                        message_record.status = "failed"
                        session.add(
                            MessageAttempt(
                                message_id=message_record.id,
                                attempt_number=job.attempts,
                                request_payload_json={
                                    "to": mask_phone(message_record.recipient_value),
                                    "body": mask_message_body_for_logs(message_record.body),
                                },
                                provider_response_json=None,
                                provider_status="failed",
                                error_message=str(exc),
                            )
                        )
                        await append_lead_event(
                            session,
                            account_id=message_record.account_id,
                            lead_id=message_record.lead_id,
                            event_type="sms_failed",
                            payload_json={
                                "message_id": message_record.id,
                                "recipient_type": message_record.recipient_type,
                                "error": str(exc),
                            },
                        )
                        await append_audit_log(
                            session,
                            account_id=message_record.account_id,
                            action="sms_failed",
                            entity_type="message",
                            entity_id=message_record.id,
                            metadata_json={
                                "recipient_type": message_record.recipient_type,
                                "error": str(exc),
                            },
                        )

            if had_failure:
                raise RetryableJobError("sms_failed", "At least one SMS failed to send")

    async def _qualify_lead(self, raw_payload: dict[str, str | None]) -> AIQualificationResult:
        if self.openai_client is None:
            raise RuntimeError("OpenAI is not configured")

        prompt = (
            "You are qualifying an enquiry for an Australian trade business.\n"
            "Return strict JSON with keys: summary, urgency_level, extracted_fields.\n"
            "urgency_level must be one of: low, medium, high, emergency.\n"
            "summary must be 1-2 short lines in plain English.\n"
            "extracted_fields must include: name, service, suburb, availability.\n"
            "Do not add any other keys.\n"
            f"Input JSON:\n{json.dumps(raw_payload, ensure_ascii=True)}"
        )
        response = await self.openai_client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Extract only the required operational fields."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned empty content")
        payload = json.loads(content)
        return AIQualificationResult.model_validate(payload)

    def _build_normalized_text(self, raw_payload: dict[str, str | None]) -> str:
        return " | ".join(value for value in raw_payload.values() if value)

    def _build_customer_reply(
        self,
        *,
        business_name: str,
        customer_name: str,
        template: str | None,
    ) -> str:
        content = (
            template
            or (
                "Thanks for reaching out to [Business Name]. We're on a job right now and "
                "will get back to you shortly. What suburb are you in and what do you need "
                "help with?"
            )
        )
        return (
            content.replace("[Business Name]", business_name).replace(
                "[Customer Name]",
                customer_name,
            )
        )

    def _build_tradie_alert(
        self,
        *,
        business_name: str,
        lead: Lead,
        customer_phone: str,
        ai_result: AIQualificationResult | None,
    ) -> str:
        return build_tradie_alert_body(
            business_name=business_name,
            lead=lead,
            customer_phone=customer_phone,
            ai_result=ai_result,
        )


async def _async_main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)
    worker = WorkerService(settings)
    await worker.run()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
