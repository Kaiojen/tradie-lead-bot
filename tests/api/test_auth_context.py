from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.dependencies.auth import get_account_context, require_owner
from shared.python.tradie_shared.schemas import AuthIdentity


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeSession:
    def __init__(self, memberships):
        self._memberships = memberships

    async def scalars(self, _stmt):
        return FakeScalarResult(self._memberships)


@pytest.mark.asyncio
async def test_account_context_requires_explicit_account_for_multi_account_user() -> None:
    request = SimpleNamespace(state=SimpleNamespace(requested_account_id=None))
    session = FakeSession(
        [
            SimpleNamespace(account_id="acc-1", role="owner"),
            SimpleNamespace(account_id="acc-2", role="staff"),
        ]
    )

    with pytest.raises(DomainError) as exc_info:
        await get_account_context(request, AuthIdentity(user_id="user-1"), session)

    assert exc_info.value.status_code == 400
    assert exc_info.value.error == "account_required"


@pytest.mark.asyncio
async def test_account_context_returns_requested_membership() -> None:
    request = SimpleNamespace(state=SimpleNamespace(requested_account_id="acc-2"))
    session = FakeSession([SimpleNamespace(account_id="acc-2", role="staff")])

    account_context = await get_account_context(request, AuthIdentity(user_id="user-1"), session)

    assert account_context.account_id == "acc-2"
    assert account_context.role == "staff"


@pytest.mark.asyncio
async def test_require_owner_blocks_staff() -> None:
    with pytest.raises(DomainError) as exc_info:
        await require_owner(SimpleNamespace(account_id="acc-1", user_id="user-1", role="staff"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.error == "owner_required"
