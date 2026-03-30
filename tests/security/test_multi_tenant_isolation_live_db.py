from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.app.services.enquiries import list_enquiries
from shared.python.tradie_shared.models import Account, Lead, LeadSource

LIVE_DATABASE_URL = os.getenv("LIVE_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not LIVE_DATABASE_URL,
    reason="LIVE_DATABASE_URL is required for the real multi-tenant isolation test",
)


@pytest.mark.asyncio
async def test_list_enquiries_isolates_accounts_on_real_db() -> None:
    engine = create_async_engine(LIVE_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        transaction = await session.begin()
        try:
            account_a = Account(id=str(uuid4()), business_name="Tenant A", status="trial")
            account_b = Account(id=str(uuid4()), business_name="Tenant B", status="trial")
            source_a = LeadSource(
                id=str(uuid4()),
                account_id=account_a.id,
                type="web_form",
                external_key=f"token-{uuid4()}",
                is_active=True,
            )
            source_b = LeadSource(
                id=str(uuid4()),
                account_id=account_b.id,
                type="web_form",
                external_key=f"token-{uuid4()}",
                is_active=True,
            )
            lead_a = Lead(
                id=str(uuid4()),
                account_id=account_a.id,
                lead_source_id=source_a.id,
                customer_name="Alice",
                customer_phone="enc:a",
                suburb="Brisbane",
                service_requested="Blocked drain",
            )
            lead_b = Lead(
                id=str(uuid4()),
                account_id=account_b.id,
                lead_source_id=source_b.id,
                customer_name="Bob",
                customer_phone="enc:b",
                suburb="Gold Coast",
                service_requested="Power outage",
            )

            session.add_all([account_a, account_b, source_a, source_b, lead_a, lead_b])
            await session.flush()

            response = await list_enquiries(
                session,
                account_id=account_a.id,
                status=None,
                page=1,
                limit=20,
            )

            assert [item.id for item in response.data] == [lead_a.id]
            assert all(item.id != lead_b.id for item in response.data)
        finally:
            await transaction.rollback()
            await engine.dispose()
