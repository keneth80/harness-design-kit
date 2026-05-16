"""Credit saga unit tests."""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import InsufficientCreditsError
from app.models.credit_ledger import CreditLedger, CreditLedgerType
from app.models.user import User
from app.services import credits as credits_svc


@pytest.mark.asyncio
async def test_hold_succeeds_and_updates_cache(session_factory):
    async with session_factory() as s:
        user = User(id=uuid.uuid4(), email="a@b.c", credits=0, plan="free")
        s.add(user)
        s.add(
            CreditLedger(
                user_id=user.id, type=CreditLedgerType.grant.value, amount=5
            )
        )
        await s.commit()

        await credits_svc.hold(s, user_id=user.id, amount=2)
        await s.commit()

        balance = await credits_svc.get_balance(s, user.id)
        assert balance == 3
        await s.refresh(user)
        assert user.credits == 3


@pytest.mark.asyncio
async def test_hold_raises_when_balance_insufficient(session_factory):
    async with session_factory() as s:
        user = User(id=uuid.uuid4(), email="c@d.e", credits=0, plan="free")
        s.add(user)
        await s.commit()
        with pytest.raises(InsufficientCreditsError):
            await credits_svc.hold(s, user_id=user.id, amount=1)
