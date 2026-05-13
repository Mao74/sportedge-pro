"""Trading account schemas (CRUD)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models import MarketType


class AccountBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    venue: Annotated[str, Field(min_length=1, max_length=32)]
    market_type: MarketType = MarketType.exchange
    commission_pct: Annotated[
        Decimal,
        Field(ge=Decimal("0"), le=Decimal("100"), max_digits=4, decimal_places=2),
    ] = Decimal("5.00")
    opening_balance: Annotated[
        Decimal,
        Field(ge=Decimal("0"), max_digits=12, decimal_places=2),
    ] = Decimal("0.00")
    opened_at: date | None = None  # optional on create; defaults to today


class AccountCreate(AccountBase):
    model_config = ConfigDict(extra="forbid")


class AccountUpdate(BaseModel):
    """Patch — every field optional.

    `opening_balance` is editable: this is a single-user app so retroactively
    correcting the seeded balance is a legitimate first-time-setup action.
    For ongoing money movements after trades are booked, prefer
    POST /bankroll/adjust so the audit trail stays coherent.
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=64)] = None
    venue: Annotated[str | None, Field(default=None, min_length=1, max_length=32)] = None
    market_type: MarketType | None = None
    commission_pct: Annotated[
        Decimal | None,
        Field(default=None, ge=Decimal("0"), le=Decimal("100"), max_digits=4, decimal_places=2),
    ] = None
    opening_balance: Annotated[
        Decimal | None,
        Field(default=None, ge=Decimal("0"), max_digits=12, decimal_places=2),
    ] = None
    opened_at: date | None = None
    is_active: bool | None = None


class Account(AccountBase):
    """API response shape."""

    id: uuid.UUID
    is_active: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
