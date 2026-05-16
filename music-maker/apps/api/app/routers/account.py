"""/api/v1/account — credit balance & usage."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import db_session, get_current_user
from app.models.credit_ledger import CreditLedger
from app.models.user import User
from app.schemas.billing import CreditBalance, LedgerEntry
from app.services import credits as credits_svc

router = APIRouter(prefix="/api/v1/account", tags=["account"])


PLAN_QUOTAS = {"free": 3, "pro": 100, "studio": 500}


@router.get("/credits", response_model=CreditBalance)
async def get_credits(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> CreditBalance:
    balance = await credits_svc.get_balance(session, user.id)
    stmt = (
        select(CreditLedger)
        .where(CreditLedger.user_id == user.id)
        .order_by(CreditLedger.created_at.desc())
        .limit(10)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return CreditBalance(
        credits=balance,
        plan=user.plan,
        plan_quota_per_month=PLAN_QUOTAS.get(user.plan, 0),
        used_this_month=0,
        renews_at=None,
        ledger_preview=[
            LedgerEntry(
                type=r.type,
                amount=r.amount,
                reason=r.reason,
                at=r.created_at,
            )
            for r in rows
        ],
    )
