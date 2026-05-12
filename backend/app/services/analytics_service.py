"""Analytics service.

Strategy-agnostic, ORM-decoupled. Consumes a list of ``TradeRow`` rows
(populated by the API layer from the DB) and returns plain data structures.
All money arithmetic uses ``Decimal`` end-to-end; only the Sharpe ratio uses
``float`` internally because variance has no exact decimal form.

Conventions:
- Only ``status == 'CLOSED'`` rows contribute to PnL stats. ``OPEN`` and
  ``VOID`` rows are filtered out of every aggregation that consumes PnL.
- Time-ordered series are sorted by ``closed_at`` (falling back to
  ``kickoff_at`` if ``closed_at`` is missing).
- Percentages are returned as ``Decimal`` in the 0..100 range, full
  precision. Display formatting (1 dp etc.) is the frontend's job.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Iterable, Literal

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")

TradeStatusLiteral = Literal["OPEN", "CLOSED", "VOID"]


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeRow:
    """One trade, projected to the fields analytics needs."""

    id: str
    kickoff_at: datetime
    closed_at: datetime | None
    strategy_slug: str
    strategy_name: str
    league: str
    outcome_label: str | None
    status: TradeStatusLiteral
    stake_total: Decimal
    pnl_eur: Decimal


def _closed(rows: Iterable[TradeRow]) -> list[TradeRow]:
    """Filter to closed trades, ordered chronologically by closure."""
    closed = [r for r in rows if r.status == "CLOSED"]
    closed.sort(key=lambda r: r.closed_at or r.kickoff_at)
    return closed


def _quantise(value: Decimal, places: Decimal = TWO_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_EVEN)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SummaryMetrics:
    n_trades: int
    total_pnl_eur: Decimal
    total_stake_eur: Decimal
    roi_pct: Decimal       # 0..100
    win_rate_pct: Decimal  # 0..100
    sharpe: Decimal        # per-trade Sharpe (no annualization scaling)
    max_drawdown_pct: Decimal  # 0..100, against running peak bankroll
    max_drawdown_eur: Decimal


def compute_summary(rows: Iterable[TradeRow]) -> SummaryMetrics:
    closed = _closed(rows)
    n = len(closed)
    if n == 0:
        return SummaryMetrics(0, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)

    total_pnl = sum((r.pnl_eur for r in closed), start=ZERO)
    total_stake = sum((r.stake_total for r in closed), start=ZERO)
    roi = (total_pnl / total_stake * HUNDRED) if total_stake > ZERO else ZERO

    wins = sum(1 for r in closed if r.pnl_eur > ZERO)
    win_rate = Decimal(wins) / Decimal(n) * HUNDRED

    sharpe = _per_trade_sharpe(closed)
    max_dd_pct, max_dd_eur, _, _ = _max_drawdown(closed)

    return SummaryMetrics(
        n_trades=n,
        total_pnl_eur=_quantise(total_pnl),
        total_stake_eur=_quantise(total_stake),
        roi_pct=_quantise(roi, FOUR_PLACES),
        win_rate_pct=_quantise(win_rate, FOUR_PLACES),
        sharpe=_quantise(sharpe, FOUR_PLACES),
        max_drawdown_pct=_quantise(max_dd_pct, FOUR_PLACES),
        max_drawdown_eur=_quantise(max_dd_eur),
    )


def _per_trade_sharpe(closed: list[TradeRow]) -> Decimal:
    """Per-trade Sharpe = mean(roi_per_trade) / stdev(roi_per_trade).

    No sqrt(N) scaling — the API does not know the trader's per-trade
    horizon, so any annualization would be a guess. Returns 0 if stdev is 0
    (single trade, or all trades produced identical ROI).
    """
    rois: list[float] = []
    for r in closed:
        if r.stake_total > ZERO:
            rois.append(float(r.pnl_eur / r.stake_total))
    if len(rois) < 2:
        return ZERO
    mean = statistics.fmean(rois)
    stdev = statistics.stdev(rois)
    if stdev == 0.0:
        return ZERO
    return Decimal(str(mean / stdev))


# ---------------------------------------------------------------------------
# Drawdown series
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DrawdownPoint:
    closed_at: datetime
    cum_pnl_eur: Decimal
    underwater_eur: Decimal     # negative-or-zero distance from running peak
    underwater_pct: Decimal     # 0..100


@dataclass(frozen=True)
class DrawdownSeries:
    points: list[DrawdownPoint]
    max_drawdown_pct: Decimal
    max_drawdown_eur: Decimal
    max_dd_started_at: datetime | None
    max_dd_ended_at: datetime | None


def compute_drawdown(rows: Iterable[TradeRow], starting_bankroll: Decimal) -> DrawdownSeries:
    """Equity-curve drawdown relative to the running peak bankroll.

    ``starting_bankroll`` anchors the curve so the percentage drawdown is
    well-defined even when cumulative PnL is negative (curve dips below
    starting capital).
    """
    closed = _closed(rows)
    if not closed:
        return DrawdownSeries([], ZERO, ZERO, None, None)

    points: list[DrawdownPoint] = []
    cum = ZERO
    peak = starting_bankroll  # equity peak (bankroll + cum)
    for r in closed:
        cum += r.pnl_eur
        equity = starting_bankroll + cum
        if equity > peak:
            peak = equity
        underwater = equity - peak  # ≤ 0
        if peak > ZERO:
            underwater_pct = (-underwater / peak) * HUNDRED
        else:
            underwater_pct = ZERO
        ts = r.closed_at or r.kickoff_at
        points.append(
            DrawdownPoint(
                closed_at=ts,
                cum_pnl_eur=_quantise(cum),
                underwater_eur=_quantise(underwater),
                underwater_pct=_quantise(underwater_pct, FOUR_PLACES),
            )
        )

    max_dd_pct, max_dd_eur, dd_start, dd_end = _max_drawdown(closed, starting_bankroll)
    return DrawdownSeries(
        points=points,
        max_drawdown_pct=_quantise(max_dd_pct, FOUR_PLACES),
        max_drawdown_eur=_quantise(max_dd_eur),
        max_dd_started_at=dd_start,
        max_dd_ended_at=dd_end,
    )


def _max_drawdown(
    closed: list[TradeRow], starting_bankroll: Decimal = ZERO
) -> tuple[Decimal, Decimal, datetime | None, datetime | None]:
    """Compute (max_dd_pct, max_dd_eur, started_at, ended_at).

    Drawdown is measured against the running peak bankroll.
    """
    if not closed:
        return ZERO, ZERO, None, None

    cum = ZERO
    peak = starting_bankroll
    peak_at: datetime | None = None
    max_dd_pct = ZERO
    max_dd_eur = ZERO
    dd_start: datetime | None = None
    dd_end: datetime | None = None

    for r in closed:
        cum += r.pnl_eur
        equity = starting_bankroll + cum
        ts = r.closed_at or r.kickoff_at
        if equity > peak:
            peak = equity
            peak_at = ts
        underwater = peak - equity
        if underwater > max_dd_eur:
            max_dd_eur = underwater
            max_dd_pct = (underwater / peak * HUNDRED) if peak > ZERO else ZERO
            dd_start = peak_at
            dd_end = ts

    return max_dd_pct, max_dd_eur, dd_start, dd_end


# ---------------------------------------------------------------------------
# Rolling ROI
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RollingPoint:
    idx: int               # trade index (0-based, in chronological order)
    roi_pct: Decimal
    win_rate_pct: Decimal


def compute_rolling(rows: Iterable[TradeRow], window: int = 20) -> list[RollingPoint]:
    """Rolling ROI and win-rate over a sliding window of ``window`` closed trades.

    Returns one point per trade once index ≥ ``window - 1``. Earlier indices
    are skipped — too few samples to be meaningful.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    closed = _closed(rows)
    if len(closed) < window:
        return []

    out: list[RollingPoint] = []
    for i in range(window - 1, len(closed)):
        slice_ = closed[i - window + 1 : i + 1]
        stake = sum((r.stake_total for r in slice_), start=ZERO)
        pnl = sum((r.pnl_eur for r in slice_), start=ZERO)
        wins = sum(1 for r in slice_ if r.pnl_eur > ZERO)
        roi = (pnl / stake * HUNDRED) if stake > ZERO else ZERO
        wr = Decimal(wins) / Decimal(window) * HUNDRED
        out.append(
            RollingPoint(
                idx=i,
                roi_pct=_quantise(roi, FOUR_PLACES),
                win_rate_pct=_quantise(wr, FOUR_PLACES),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Breakdowns
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BreakdownRow:
    key: str
    n_trades: int
    total_pnl_eur: Decimal
    total_stake_eur: Decimal
    roi_pct: Decimal
    win_rate_pct: Decimal


def _group_summary(
    rows: Iterable[TradeRow], key_fn
) -> list[BreakdownRow]:
    closed = _closed(rows)
    groups: dict[str, list[TradeRow]] = defaultdict(list)
    for r in closed:
        groups[key_fn(r)].append(r)

    out: list[BreakdownRow] = []
    for key, items in groups.items():
        n = len(items)
        pnl = sum((r.pnl_eur for r in items), start=ZERO)
        stake = sum((r.stake_total for r in items), start=ZERO)
        wins = sum(1 for r in items if r.pnl_eur > ZERO)
        roi = (pnl / stake * HUNDRED) if stake > ZERO else ZERO
        wr = Decimal(wins) / Decimal(n) * HUNDRED
        out.append(
            BreakdownRow(
                key=key,
                n_trades=n,
                total_pnl_eur=_quantise(pnl),
                total_stake_eur=_quantise(stake),
                roi_pct=_quantise(roi, FOUR_PLACES),
                win_rate_pct=_quantise(wr, FOUR_PLACES),
            )
        )
    out.sort(key=lambda b: b.total_pnl_eur, reverse=True)
    return out


def breakdown_by_strategy(rows: Iterable[TradeRow]) -> list[BreakdownRow]:
    return _group_summary(rows, lambda r: r.strategy_slug)


def breakdown_by_league(rows: Iterable[TradeRow]) -> list[BreakdownRow]:
    return _group_summary(rows, lambda r: r.league)


def breakdown_by_outcome_label(rows: Iterable[TradeRow]) -> list[BreakdownRow]:
    return _group_summary(rows, lambda r: r.outcome_label or "(unset)")


# ---------------------------------------------------------------------------
# Calendar heatmap (7 × 24)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalendarCell:
    day_of_week: int   # 0=Mon .. 6=Sun (Python convention)
    hour: int          # 0..23
    n_trades: int
    pnl_eur: Decimal


@dataclass(frozen=True)
class CalendarGrid:
    """7×24 heatmap. ``cells`` is a flat list, sorted by (dow, hour).

    Empty cells (no trades at that slot) are NOT included — the frontend
    fills them with the "empty" colour.
    """

    cells: list[CalendarCell] = field(default_factory=list)


def compute_calendar_grid(rows: Iterable[TradeRow]) -> CalendarGrid:
    closed = _closed(rows)
    bucket: dict[tuple[int, int], list[TradeRow]] = defaultdict(list)
    for r in closed:
        ts = r.kickoff_at  # bucket by kickoff (when the trade actually happened)
        bucket[(ts.weekday(), ts.hour)].append(r)

    cells: list[CalendarCell] = []
    for (dow, hour), items in sorted(bucket.items()):
        pnl = sum((r.pnl_eur for r in items), start=ZERO)
        cells.append(
            CalendarCell(
                day_of_week=dow,
                hour=hour,
                n_trades=len(items),
                pnl_eur=_quantise(pnl),
            )
        )
    return CalendarGrid(cells=cells)


# ---------------------------------------------------------------------------
# Helpers reusable in tests / the API layer
# ---------------------------------------------------------------------------


def count_outcomes(rows: Iterable[TradeRow]) -> dict[str, int]:
    """Quick counter of `outcome_label` values among CLOSED trades."""
    closed = _closed(rows)
    return dict(Counter((r.outcome_label or "(unset)") for r in closed))


def cumulative_pnl(rows: Iterable[TradeRow]) -> list[tuple[datetime, Decimal]]:
    """Cumulative PnL points, one per closed trade in chronological order.
    Useful for plotting and exposed as a building block for tests."""
    closed = _closed(rows)
    out: list[tuple[datetime, Decimal]] = []
    cum = ZERO
    for r in closed:
        cum += r.pnl_eur
        ts = r.closed_at or r.kickoff_at
        out.append((ts, _quantise(cum)))
    return out


# Marker so star-imports stay tidy.
__all__ = [
    "TradeRow",
    "SummaryMetrics",
    "DrawdownPoint",
    "DrawdownSeries",
    "RollingPoint",
    "BreakdownRow",
    "CalendarCell",
    "CalendarGrid",
    "compute_summary",
    "compute_drawdown",
    "compute_rolling",
    "breakdown_by_strategy",
    "breakdown_by_league",
    "breakdown_by_outcome_label",
    "compute_calendar_grid",
    "count_outcomes",
    "cumulative_pnl",
]


# ``math`` is imported but only used in tests — silence the lint hint.
_ = math
