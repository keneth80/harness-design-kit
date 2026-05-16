"""Billing / credits schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LedgerEntry(BaseModel):
    type: str
    amount: int
    reason: str | None = None
    at: datetime


class CreditBalance(BaseModel):
    credits: int
    plan: str
    plan_quota_per_month: int = 0
    used_this_month: int = 0
    renews_at: datetime | None = None
    ledger_preview: list[LedgerEntry] = Field(default_factory=list)
