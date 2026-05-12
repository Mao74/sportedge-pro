"""Analytics response + request schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import MarketType


# --- Summary ---------------------------------------------------------------


class AnalyticsSummary(BaseModel):
    n_trades: int
    total_pnl_eur: Decimal
    total_stake_eur: Decimal
    roi_pct: Decimal
    win_rate_pct: Decimal
    sharpe: Decimal
    max_drawdown_pct: Decimal
    max_drawdown_eur: Decimal


# --- Breakdowns ------------------------------------------------------------


class BreakdownRow(BaseModel):
    key: str
    n_trades: int
    total_pnl_eur: Decimal
    total_stake_eur: Decimal
    roi_pct: Decimal
    win_rate_pct: Decimal


# --- Rolling ---------------------------------------------------------------


class RollingPoint(BaseModel):
    idx: int
    roi_pct: Decimal
    win_rate_pct: Decimal


# --- Drawdown --------------------------------------------------------------


class DrawdownPoint(BaseModel):
    closed_at: datetime
    cum_pnl_eur: Decimal
    underwater_eur: Decimal
    underwater_pct: Decimal


class DrawdownSeries(BaseModel):
    points: list[DrawdownPoint]
    max_drawdown_pct: Decimal
    max_drawdown_eur: Decimal
    max_dd_started_at: datetime | None
    max_dd_ended_at: datetime | None


# --- Calendar --------------------------------------------------------------


class CalendarCell(BaseModel):
    day_of_week: int
    hour: int
    n_trades: int
    pnl_eur: Decimal


class CalendarGrid(BaseModel):
    cells: list[CalendarCell]


# --- Monte Carlo -----------------------------------------------------------


class MonteCarloRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starting_bankroll: Annotated[Decimal, Field(gt=Decimal("0"))]
    n_simulations: Annotated[int, Field(ge=1, le=100_000)] = 10_000
    horizon_trades: Annotated[int, Field(ge=1, le=1_000)] = 100
    ruin_threshold_pct: Annotated[Decimal, Field(ge=Decimal("0"), le=Decimal("100"))] = (
        Decimal("50.0")
    )
    n_buckets: Annotated[int, Field(ge=2, le=200)] = 20
    seed: int | None = None


class DistributionBucket(BaseModel):
    bucket_low: Decimal
    bucket_high: Decimal
    count: int


class MonteCarloResponse(BaseModel):
    risk_of_ruin_pct: Decimal
    p10_ending_bankroll: Decimal
    p50_ending_bankroll: Decimal
    p90_ending_bankroll: Decimal
    mean_ending_bankroll: Decimal
    min_ending_bankroll: Decimal
    max_ending_bankroll: Decimal
    distribution: list[DistributionBucket]
    n_simulations: int
    horizon_trades: int
    n_historical_pnls: int


# --- WhatIf cash-out -------------------------------------------------------


class WhatIfCashoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stake_total: Annotated[Decimal, Field(ge=Decimal("0"))]
    avg_odds: Annotated[Decimal, Field(ge=Decimal("1.01"))]
    cashout_odds: Annotated[Decimal, Field(ge=Decimal("0"))]
    position_side: Literal["back", "lay"]
    commission_pct: Annotated[
        Decimal, Field(ge=Decimal("0"), le=Decimal("100"))
    ] = Decimal("5.0")
    market_type: MarketType = MarketType.exchange


class WhatIfCashoutResponse(BaseModel):
    locked_in_pnl_eur: Decimal
    breakeven_cashout_odds: Decimal | None
    pct_of_max_win: Decimal
    formula_text: str
