"""Trade schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import MarketType, PnLMode, TradeStatus
from app.schemas.tag import TagOut

PositionSide = Literal["back", "lay"]


class _MoneyValidatorMixin:
    """Decimal precision normalisation for money fields. Pydantic v2 handles
    Decimal natively but we want JSON ↔ string ↔ Decimal round-trips that
    play well with the Numeric(10,2) DB columns."""


class TradeBase(BaseModel):
    """Fields shared between create / update / close payloads."""

    model_config = ConfigDict(extra="forbid")

    sport: str = "football"
    home_team: str = Field(min_length=1, max_length=128)
    away_team: str = Field(min_length=1, max_length=128)
    league: str = Field(min_length=1, max_length=128)
    kickoff_at: datetime

    ht_score_home: int | None = Field(default=None, ge=0, le=99)
    ht_score_away: int | None = Field(default=None, ge=0, le=99)
    ft_score_home: int | None = Field(default=None, ge=0, le=99)
    ft_score_away: int | None = Field(default=None, ge=0, le=99)

    stake_total: Annotated[Decimal, Field(ge=Decimal("0"), max_digits=10, decimal_places=2)]
    avg_odds: Annotated[Decimal, Field(ge=Decimal("1.01"), max_digits=6, decimal_places=2)]
    commission_pct: Annotated[
        Decimal, Field(ge=Decimal("0"), le=Decimal("100"), max_digits=4, decimal_places=2)
    ] = Decimal("5.00")
    market_type: MarketType = MarketType.exchange

    pnl_mode: PnLMode
    cashout_odds: Annotated[
        Decimal | None, Field(default=None, max_digits=6, decimal_places=2)
    ] = None
    manual_pnl_eur: Annotated[
        Decimal | None, Field(default=None, max_digits=10, decimal_places=2)
    ] = None
    position_side: PositionSide | None = None
    outcome_label: str | None = Field(default=None, max_length=64)

    strategy_data: dict[str, Any] = Field(default_factory=dict)
    notes_md: str | None = Field(default=None, max_length=20000)


class TradeCreate(TradeBase):
    strategy_id: uuid.UUID
    status: TradeStatus = TradeStatus.OPEN
    closed_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _mode_specific(self) -> TradeCreate:
        return _check_mode_specific(self)


class TradeUpdate(BaseModel):
    """All fields optional. Mode-specific consistency re-checked at the API layer."""

    model_config = ConfigDict(extra="forbid")

    strategy_id: uuid.UUID | None = None

    sport: str | None = None
    home_team: str | None = Field(default=None, min_length=1, max_length=128)
    away_team: str | None = Field(default=None, min_length=1, max_length=128)
    league: str | None = Field(default=None, min_length=1, max_length=128)
    kickoff_at: datetime | None = None

    ht_score_home: int | None = Field(default=None, ge=0, le=99)
    ht_score_away: int | None = Field(default=None, ge=0, le=99)
    ft_score_home: int | None = Field(default=None, ge=0, le=99)
    ft_score_away: int | None = Field(default=None, ge=0, le=99)

    stake_total: Annotated[Decimal | None, Field(default=None, ge=Decimal("0"))] = None
    avg_odds: Annotated[Decimal | None, Field(default=None, ge=Decimal("1.01"))] = None
    commission_pct: Annotated[
        Decimal | None, Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    ] = None
    market_type: MarketType | None = None

    pnl_mode: PnLMode | None = None
    cashout_odds: Decimal | None = None
    manual_pnl_eur: Decimal | None = None
    position_side: PositionSide | None = None
    outcome_label: str | None = None
    status: TradeStatus | None = None

    strategy_data: dict[str, Any] | None = None
    notes_md: str | None = None
    tags: list[str] | None = None


class TradeClose(BaseModel):
    """Body for ``POST /trades/{id}/close``."""

    model_config = ConfigDict(extra="forbid")

    pnl_mode: PnLMode
    cashout_odds: Decimal | None = None
    manual_pnl_eur: Decimal | None = None
    position_side: PositionSide | None = None
    outcome_label: str | None = None
    ft_score_home: int | None = Field(default=None, ge=0, le=99)
    ft_score_away: int | None = Field(default=None, ge=0, le=99)
    strategy_data: dict[str, Any] | None = None
    notes_md: str | None = None

    @model_validator(mode="after")
    def _mode_specific(self) -> TradeClose:
        return _check_mode_specific(self)


class _StrategyEmbed(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    template_key: str | None
    color_hex: str | None

    model_config = ConfigDict(from_attributes=True)


class TradeOut(BaseModel):
    id: uuid.UUID
    strategy: _StrategyEmbed
    sport: str
    home_team: str
    away_team: str
    league: str
    kickoff_at: datetime
    ht_score_home: int | None
    ht_score_away: int | None
    ft_score_home: int | None
    ft_score_away: int | None
    stake_total: Decimal
    avg_odds: Decimal
    commission_pct: Decimal
    market_type: MarketType
    pnl_mode: PnLMode
    cashout_odds: Decimal | None
    manual_pnl_eur: Decimal | None
    computed_pnl_eur: Decimal
    position_side: PositionSide | None
    outcome_label: str | None
    status: TradeStatus
    closed_at: datetime | None
    strategy_data: dict[str, Any]
    notes_md: str | None
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TradeAggregates(BaseModel):
    n_trades: int
    sum_pnl_eur: Decimal
    sum_stake_eur: Decimal
    roi_pct: Decimal
    win_rate_pct: Decimal


class TradeListResponse(BaseModel):
    items: list[TradeOut]
    total: int
    page: int
    page_size: int
    aggregates: TradeAggregates


class TagAttachRequest(BaseModel):
    """POST /trades/{id}/tags — pass either an existing tag id, or a name to find-or-create."""

    model_config = ConfigDict(extra="forbid")

    tag_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color_hex: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> TagAttachRequest:
        if (self.tag_id is None) == (self.name is None):
            raise ValueError("Provide exactly one of {tag_id, name}.")
        return self


# ---------------------------------------------------------------------------
# Helper: mode-specific consistency check used by Create / Close.
# ---------------------------------------------------------------------------


def _check_mode_specific(model) -> Any:
    mode = model.pnl_mode
    if mode is PnLMode.MANUAL and model.manual_pnl_eur is None:
        raise ValueError("MANUAL mode requires manual_pnl_eur.")
    if mode is PnLMode.CASHOUT_ODDS:
        if model.cashout_odds is None:
            raise ValueError("CASHOUT_ODDS mode requires cashout_odds.")
        if model.position_side is None:
            raise ValueError("CASHOUT_ODDS mode requires position_side.")
    if mode is PnLMode.AUTO:
        if model.position_side is None:
            raise ValueError("AUTO mode requires position_side.")
        if not model.outcome_label:
            raise ValueError("AUTO mode requires outcome_label.")
    return model
