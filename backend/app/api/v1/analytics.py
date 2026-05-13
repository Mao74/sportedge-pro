"""Analytics API — thin wrappers over the strategy-agnostic services."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api._filters import build_trade_where
from app.api.deps import CurrentUser, DbSession
from app.models import PnLMode, Trade, TradeStatus
from app.schemas import analytics as schemas
from app.services import analytics_service as svc
from app.services.monte_carlo import MonteCarloInputs, run_simulation
from app.services.pnl_calculator import PnLInputs, compute_pnl
from app.services.trade_projection import to_trade_rows
from app.services.bankroll_service import compute_current_bankroll
from app.models import PnLMode as _PnLMode  # alias to keep imports tidy

router = APIRouter(prefix="/analytics", tags=["analytics"])

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


# ---------------------------------------------------------------------------
# Filter dependency — surfaces the same query params as /trades.
# ---------------------------------------------------------------------------


async def _filtered_trade_rows(
    db,
    *,
    strategy_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    league: str | None = None,
    status: TradeStatus | None = None,
    outcome_label: str | None = None,
    pnl_mode: PnLMode | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    pnl_min: Decimal | None = None,
    pnl_max: Decimal | None = None,
    tag: list[str] | None = None,
    q: str | None = None,
) -> list[svc.TradeRow]:
    where = build_trade_where(
        strategy_id=strategy_id, account_id=account_id,
        league=league, status=status,
        outcome_label=outcome_label, pnl_mode=pnl_mode,
        date_from=date_from, date_to=date_to,
        pnl_min=pnl_min, pnl_max=pnl_max,
        tag=tag, q=q,
    )
    res = await db.execute(
        select(Trade)
        .options(selectinload(Trade.strategy))
        .where(where)
    )
    return to_trade_rows(res.scalars().all())


_FilterParams = dict


def _filter_query_params():
    """Reusable filter parameters as a dict — keeps endpoint signatures short."""
    return {
        "strategy_id": Annotated[uuid.UUID | None, Query()] ,
        "account_id": Annotated[uuid.UUID | None, Query()] ,
        "league": Annotated[str | None, Query()],
        "status": Annotated[TradeStatus | None, Query(alias="status")],
        "outcome_label": Annotated[str | None, Query()],
        "pnl_mode": Annotated[PnLMode | None, Query()],
        "date_from": Annotated[datetime | None, Query()],
        "date_to": Annotated[datetime | None, Query()],
        "pnl_min": Annotated[Decimal | None, Query()],
        "pnl_max": Annotated[Decimal | None, Query()],
        "tag": Annotated[list[str] | None, Query()],
        "q": Annotated[str | None, Query()],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=schemas.AnalyticsSummary)
async def summary(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    status_: Annotated[TradeStatus | None, Query(alias="status")] = None,
    outcome_label: Annotated[str | None, Query()] = None,
    pnl_mode: Annotated[PnLMode | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    pnl_min: Annotated[Decimal | None, Query()] = None,
    pnl_max: Annotated[Decimal | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> schemas.AnalyticsSummary:
    rows = await _filtered_trade_rows(
        db,
        strategy_id=strategy_id, account_id=account_id,
        league=league, status=status_,
        outcome_label=outcome_label, pnl_mode=pnl_mode,
        date_from=date_from, date_to=date_to,
        pnl_min=pnl_min, pnl_max=pnl_max, tag=tag, q=q,
    )
    s = svc.compute_summary(rows)
    return schemas.AnalyticsSummary(
        n_trades=s.n_trades,
        total_pnl_eur=s.total_pnl_eur,
        total_stake_eur=s.total_stake_eur,
        roi_pct=s.roi_pct,
        win_rate_pct=s.win_rate_pct,
        sharpe=s.sharpe,
        max_drawdown_pct=s.max_drawdown_pct,
        max_drawdown_eur=s.max_drawdown_eur,
    )


def _to_breakdown(rows: list[svc.BreakdownRow]) -> list[schemas.BreakdownRow]:
    return [
        schemas.BreakdownRow(
            key=r.key,
            n_trades=r.n_trades,
            total_pnl_eur=r.total_pnl_eur,
            total_stake_eur=r.total_stake_eur,
            roi_pct=r.roi_pct,
            win_rate_pct=r.win_rate_pct,
        )
        for r in rows
    ]


@router.get("/by-strategy", response_model=list[schemas.BreakdownRow])
async def by_strategy(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    status_: Annotated[TradeStatus | None, Query(alias="status")] = None,
    outcome_label: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> list[schemas.BreakdownRow]:
    rows = await _filtered_trade_rows(
        db, strategy_id=strategy_id, account_id=account_id, league=league, status=status_,
        outcome_label=outcome_label, date_from=date_from, date_to=date_to,
    )
    return _to_breakdown(svc.breakdown_by_strategy(rows))


@router.get("/by-league", response_model=list[schemas.BreakdownRow])
async def by_league(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    status_: Annotated[TradeStatus | None, Query(alias="status")] = None,
    outcome_label: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> list[schemas.BreakdownRow]:
    rows = await _filtered_trade_rows(
        db, strategy_id=strategy_id, account_id=account_id, league=league, status=status_,
        outcome_label=outcome_label, date_from=date_from, date_to=date_to,
    )
    return _to_breakdown(svc.breakdown_by_league(rows))


@router.get("/by-outcome", response_model=list[schemas.BreakdownRow])
async def by_outcome(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    status_: Annotated[TradeStatus | None, Query(alias="status")] = None,
    outcome_label: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> list[schemas.BreakdownRow]:
    rows = await _filtered_trade_rows(
        db, strategy_id=strategy_id, account_id=account_id, league=league, status=status_,
        outcome_label=outcome_label, date_from=date_from, date_to=date_to,
    )
    return _to_breakdown(svc.breakdown_by_outcome_label(rows))


@router.get("/rolling", response_model=list[schemas.RollingPoint])
async def rolling(
    _user: CurrentUser,
    db: DbSession,
    window: Annotated[int, Query(ge=2, le=500)] = 20,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> list[schemas.RollingPoint]:
    rows = await _filtered_trade_rows(
        db, strategy_id=strategy_id, account_id=account_id, league=league,
        date_from=date_from, date_to=date_to,
    )
    pts = svc.compute_rolling(rows, window=window)
    return [schemas.RollingPoint(idx=p.idx, roi_pct=p.roi_pct, win_rate_pct=p.win_rate_pct) for p in pts]


@router.get("/drawdown", response_model=schemas.DrawdownSeries)
async def drawdown(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> schemas.DrawdownSeries:
    rows = await _filtered_trade_rows(
        db, strategy_id=strategy_id, account_id=account_id, league=league,
        date_from=date_from, date_to=date_to,
    )
    starting = await compute_current_bankroll(db)  # anchor to current is fine here
    # Better: anchor to starting_bankroll from config to keep curve stable.
    from app.core.config import get_settings  # local to avoid circular at import time
    starting = Decimal(get_settings().default_starting_bankroll)
    ds = svc.compute_drawdown(rows, starting_bankroll=starting)
    return schemas.DrawdownSeries(
        points=[
            schemas.DrawdownPoint(
                closed_at=p.closed_at,
                cum_pnl_eur=p.cum_pnl_eur,
                underwater_eur=p.underwater_eur,
                underwater_pct=p.underwater_pct,
            )
            for p in ds.points
        ],
        max_drawdown_pct=ds.max_drawdown_pct,
        max_drawdown_eur=ds.max_drawdown_eur,
        max_dd_started_at=ds.max_dd_started_at,
        max_dd_ended_at=ds.max_dd_ended_at,
    )


@router.get("/calendar", response_model=schemas.CalendarGrid)
async def calendar(
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> schemas.CalendarGrid:
    rows = await _filtered_trade_rows(
        db, strategy_id=strategy_id, account_id=account_id, league=league,
        date_from=date_from, date_to=date_to,
    )
    grid = svc.compute_calendar_grid(rows)
    return schemas.CalendarGrid(
        cells=[
            schemas.CalendarCell(
                day_of_week=c.day_of_week, hour=c.hour,
                n_trades=c.n_trades, pnl_eur=c.pnl_eur,
            )
            for c in grid.cells
        ]
    )


# ---------------------------------------------------------------------------
# Monte Carlo (POST — body, not filter params)
# ---------------------------------------------------------------------------


@router.post("/monte-carlo", response_model=schemas.MonteCarloResponse)
async def monte_carlo(
    payload: schemas.MonteCarloRequest,
    _user: CurrentUser,
    db: DbSession,
    strategy_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    league: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> schemas.MonteCarloResponse:
    where = build_trade_where(
        strategy_id=strategy_id, account_id=account_id, league=league,
        status=TradeStatus.CLOSED,
        date_from=date_from, date_to=date_to,
    )
    pnl_res = await db.execute(select(Trade.computed_pnl_eur).where(where))
    historical = [Decimal(str(p)) for p in pnl_res.scalars().all()]

    inputs = MonteCarloInputs(
        historical_pnls=historical,
        starting_bankroll=payload.starting_bankroll,
        n_simulations=payload.n_simulations,
        horizon_trades=payload.horizon_trades,
        ruin_threshold_pct=payload.ruin_threshold_pct,
        n_buckets=payload.n_buckets,
        seed=payload.seed,
    )
    out = run_simulation(inputs)
    return schemas.MonteCarloResponse(
        risk_of_ruin_pct=out.risk_of_ruin_pct,
        p10_ending_bankroll=out.p10_ending_bankroll,
        p50_ending_bankroll=out.p50_ending_bankroll,
        p90_ending_bankroll=out.p90_ending_bankroll,
        mean_ending_bankroll=out.mean_ending_bankroll,
        min_ending_bankroll=out.min_ending_bankroll,
        max_ending_bankroll=out.max_ending_bankroll,
        distribution=[
            schemas.DistributionBucket(
                bucket_low=b.bucket_low, bucket_high=b.bucket_high, count=b.count
            )
            for b in out.distribution
        ],
        n_simulations=out.n_simulations,
        horizon_trades=out.horizon_trades,
        n_historical_pnls=len(historical),
    )


# ---------------------------------------------------------------------------
# WhatIf cash-out — stateless, single source of truth for the widget.
# ---------------------------------------------------------------------------


def _q(value: Decimal, places: Decimal = TWO_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_EVEN)


@router.post("/whatif-cashout", response_model=schemas.WhatIfCashoutResponse)
async def whatif_cashout(
    payload: schemas.WhatIfCashoutRequest, _user: CurrentUser
) -> schemas.WhatIfCashoutResponse:
    # Classic market: commission is irrelevant (quoted odds already net).
    from app.models import MarketType as _MarketType
    cf = (
        ONE
        if payload.market_type is _MarketType.classic
        else ONE - payload.commission_pct / HUNDRED
    )

    # Locked-in PnL via the same calculator the trades API uses.
    locked = compute_pnl(
        PnLInputs(
            pnl_mode=_PnLMode.CASHOUT_ODDS,
            stake_total=payload.stake_total,
            avg_odds=payload.avg_odds,
            commission_pct=payload.commission_pct,
            market_type=payload.market_type,
            cashout_odds=payload.cashout_odds,
            position_side=payload.position_side,
        )
    )

    # Breakeven: the cashout_odds at which gross PnL == 0.
    if payload.position_side == "back":
        # gross = stake * (co - 1) → 0 when co = 1
        breakeven: Decimal | None = ONE
    else:
        # lay: gross = stake - stake * (co - 1) = stake * (2 - co) → 0 when co = 2
        breakeven = Decimal("2")

    # Max win (full settlement) — for back, stake*(odds-1)*cf; for lay, stake*cf.
    if payload.position_side == "back":
        max_win = payload.stake_total * (payload.avg_odds - ONE) * cf
    else:
        max_win = payload.stake_total * cf
    pct_of_max = (locked / max_win * HUNDRED) if max_win > 0 else ZERO

    # Human-readable formula
    if payload.position_side == "back":
        gross_text = f"€{payload.stake_total} × ({payload.cashout_odds} − 1)"
    else:
        gross_text = f"€{payload.stake_total} − €{payload.stake_total} × ({payload.cashout_odds} − 1)"
    formula_text = (
        f"{gross_text} × (1 − {payload.commission_pct}/100) = €{locked}"
        if locked > 0
        else f"{gross_text} = €{locked}"
    )

    return schemas.WhatIfCashoutResponse(
        locked_in_pnl_eur=locked,
        breakeven_cashout_odds=breakeven,
        pct_of_max_win=_q(pct_of_max, FOUR_PLACES),
        formula_text=formula_text,
    )
