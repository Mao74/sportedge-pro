"""User-tunable trading preferences (single-row, lives on app_settings)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models import MarketType


# Common labels we suggest in the UI dropdown. Free-form is allowed.
# The field is named ``betting_exchange`` historically but it now generalises
# to any venue — exchange OR classic bookmaker.
KNOWN_VENUES = (
    "betfair", "smarkets", "matchbook", "betdaq",
    "snai", "bet365", "sisal", "lottomatica", "eurobet", "goldbet",
    "other",
)


class Preferences(BaseModel):
    default_commission_pct: Decimal
    betting_exchange: str  # legacy name — actually "venue" (exchange OR bookmaker)
    default_market_type: MarketType

    model_config = ConfigDict(from_attributes=True)


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_commission_pct: Annotated[
        Decimal | None,
        Field(default=None, ge=Decimal("0"), le=Decimal("100"), max_digits=4, decimal_places=2),
    ] = None
    betting_exchange: Annotated[
        str | None, Field(default=None, min_length=1, max_length=32)
    ] = None
    default_market_type: MarketType | None = None
