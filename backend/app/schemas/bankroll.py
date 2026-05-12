"""Bankroll-related Pydantic schemas."""

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


class BankrollSeriesPoint(BaseModel):
    taken_at: datetime
    balance_eur: Decimal
    day_pnl_eur: Decimal


class BankrollAdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_eur: Annotated[Decimal, Field(gt=Decimal("0"), max_digits=10, decimal_places=2)]
    kind: Literal["deposit", "withdrawal"]
    notes: str | None = Field(default=None, max_length=2048)


class BankrollSnapshotOut(BaseModel):
    id: uuid.UUID
    taken_at: datetime
    balance_eur: Decimal
    deposit_eur: Decimal
    withdrawal_eur: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)
