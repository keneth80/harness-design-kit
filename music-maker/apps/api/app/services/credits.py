"""Credit Saga: hold -> charge | refund.

`credit_ledger` is the source of truth. `users.credits` is a cached scalar.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.core.exceptions import InsufficientCreditsError
from app.models.credit_ledger import CreditLedger, CreditLedgerType
from app.models.user import User

# ---------------- async (API path) ----------------


async def get_balance(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Compute balance = SUM(amount) of all ledger entries for user."""
    stmt = select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
        CreditLedger.user_id == user_id
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def hold(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    generation_id: uuid.UUID | None = None,
    reason: str = "song_generation_hold",
) -> CreditLedger:
    """Insert a `hold` entry (amount < 0). Raises InsufficientCreditsError."""
    if amount <= 0:
        raise ValueError("hold amount must be positive (will be stored as negative)")
    balance = await get_balance(session, user_id)
    if balance < amount:
        raise InsufficientCreditsError(
            detail=f"Need {amount} credit, have {balance}",
            required=amount,
            available=balance,
        )
    entry = CreditLedger(
        user_id=user_id,
        generation_id=generation_id,
        type=CreditLedgerType.hold.value,
        amount=-amount,
        reason=reason,
    )
    session.add(entry)
    await session.flush()
    # update cached users.credits
    user = await session.get(User, user_id)
    if user is not None:
        user.credits = balance - amount
    return entry


# ---------------- sync (Celery worker path) ----------------


def commit_sync(
    session: SyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    generation_id: uuid.UUID,
    reason: str = "song_generation_charge",
) -> CreditLedger:
    """Convert hold -> charge. Sum stays the same (hold is already -amount)."""
    # Insert a charge entry of 0 (book-keeping) OR replace hold->charge.
    # Architecture spec says: hold INSERT then charge INSERT — but they must
    # net out to the right balance. We keep the original hold entry as the
    # actual -amount, and add a `charge` marker with 0 amount so audit
    # trails show the transition explicitly.
    entry = CreditLedger(
        user_id=user_id,
        generation_id=generation_id,
        type=CreditLedgerType.charge.value,
        amount=0,
        reason=reason,
    )
    session.add(entry)
    session.flush()
    return entry


def refund_sync(
    session: SyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    generation_id: uuid.UUID,
    reason: str = "song_generation_refund",
) -> CreditLedger:
    """Reverse a prior hold by inserting +amount."""
    if amount <= 0:
        raise ValueError("refund amount must be positive")
    entry = CreditLedger(
        user_id=user_id,
        generation_id=generation_id,
        type=CreditLedgerType.refund.value,
        amount=amount,
        reason=reason,
    )
    session.add(entry)
    # Update cached users.credits
    balance = (
        session.execute(
            select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
                CreditLedger.user_id == user_id
            )
        ).scalar()
        or 0
    )
    user = session.get(User, user_id)
    if user is not None:
        user.credits = int(balance)
    session.flush()
    return entry
