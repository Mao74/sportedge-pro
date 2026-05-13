"""Bankroll-related Pydantic schemas.

After migration 0007 every bankroll figure (current balance, daily series,
adjust, snapshot) is scoped to an account_id. The API exposes both:
- aggregated views (no account_id query param → sum across active accounts)
- per-account views (account_id query param → just that account)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class BankrollCurrent(BaseModel):
    balance_eur: Decimal
    last_snapshot_at: datetime | None
    since_inception_pnl_eur: Decimal
    since_inception_roi_pct: Decimal
    account_id: uuid.UUID | None = None  # None when aggregated across all accounts


class BankrollSeriesPoint(BaseModel):
    taken_at: datetime
    balance_eur: Decimal
    day_pnl_eur: Decimal


class BankrollAdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional with default-account fallback for backward-compat with
    # pre-multi-account clients (see TradeCreate.account_id).
    account_id: uuid.UUID | None = None
    amount_eur: Annotated[Decimal, Field(gt=Decimal("0"), max_digits=10, decimal_places=2)]
    kind: Literal["deposit", "withdrawal"]
    notes: str | None = Field(default=None, max_length=2048)


class BankrollSnapshotOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    taken_at: datetime
    balance_eur: Decimal
    deposit_eur: Decimal
    withdrawal_eur: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)
