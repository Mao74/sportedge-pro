"""Analytics service tests — deterministic fixtures, hand-checked expected values."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.analytics_service import (
    TradeRow,
    breakdown_by_league,
    breakdown_by_outcome_label,
    breakdown_by_strategy,
    compute_calendar_grid,
    compute_drawdown,
    compute_rolling,
    compute_summary,
    count_outcomes,
    cumulative_pnl,
)

D = Decimal
UTC = timezone.utc


def _row(
    *,
    idx: int,
    pnl: str,
    stake: str = "100.00",
    strategy: str = "magic-cs",
    strategy_name: str = "Magic CS",
    league: str = "Serie A",
    outcome: str | None = "WIN",
    status: str = "CLOSED",
    kickoff: datetime | None = None,
    closed: datetime | None = None,
) -> TradeRow:
    """Helper to build a TradeRow tersely."""
    base = datetime(2026, 4, 1, 20, 45, tzinfo=UTC)
    ko = kickoff or base + timedelta(days=idx)
    cl = closed or (ko + timedelta(hours=2) if status == "CLOSED" else None)
    return TradeRow(
        id=f"trade-{idx:03d}",
        kickoff_at=ko,
        closed_at=cl,
        strategy_slug=strategy,
        strategy_name=strategy_name,
        league=league,
        outcome_label=outcome,
        status=status,  # type: ignore[arg-type]
        stake_total=D(stake),
        pnl_eur=D(pnl),
    )


@pytest.fixture
def empty_rows() -> list[TradeRow]:
    return []


@pytest.fixture
def winning_streak() -> list[TradeRow]:
    """Five wins of varying size, same stake, alphabetical leagues."""
    return [
        _row(idx=1, pnl="50.00", league="Bundesliga"),
        _row(idx=2, pnl="20.00", league="La Liga"),
        _row(idx=3, pnl="80.00", league="Premier League"),
        _row(idx=4, pnl="10.00", league="Serie A"),
        _row(idx=5, pnl="40.00", league="Ligue 1"),
    ]


@pytest.fixture
def mixed_pnls() -> list[TradeRow]:
    """Ten trades, alternating outcomes, plus a void and an open one."""
    pnls = ["50", "-30", "20", "-10", "60", "-40", "15", "-5", "100", "-25"]
    rows = [_row(idx=i + 1, pnl=p, outcome="WIN" if D(p) > 0 else "LOSS") for i, p in enumerate(pnls)]
    # one VOID, one OPEN — must be filtered out of stats
    rows.append(_row(idx=11, pnl="0.00", outcome="VOID", status="VOID"))
    rows.append(_row(idx=12, pnl="0.00", outcome=None, status="OPEN", closed=None))
    return rows


# ---------------------------------------------------------------------------
# compute_summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_empty_yields_zeros(self, empty_rows) -> None:
        s = compute_summary(empty_rows)
        assert s.n_trades == 0
        assert s.total_pnl_eur == D("0")
        assert s.roi_pct == D("0")
        assert s.win_rate_pct == D("0")
        assert s.sharpe == D("0")
        assert s.max_drawdown_eur == D("0")

    def test_winning_streak(self, winning_streak) -> None:
        # total pnl = 50+20+80+10+40 = 200; total stake = 5*100 = 500; roi = 40%
        s = compute_summary(winning_streak)
        assert s.n_trades == 5
        assert s.total_pnl_eur == D("200.00")
        assert s.total_stake_eur == D("500.00")
        assert s.roi_pct == D("40.0000")
        assert s.win_rate_pct == D("100.0000")
        # Drawdown is 0 — never below previous peak.
        assert s.max_drawdown_eur == D("0.00")
        assert s.max_drawdown_pct == D("0.0000")

    def test_mixed_only_counts_closed(self, mixed_pnls) -> None:
        # 10 closed trades: pnl sum = 50-30+20-10+60-40+15-5+100-25 = 135
        # stake sum = 1000, roi = 13.5%
        # wins = 5 (50,20,60,15,100), win_rate = 50%
        s = compute_summary(mixed_pnls)
        assert s.n_trades == 10  # void/open excluded
        assert s.total_pnl_eur == D("135.00")
        assert s.total_stake_eur == D("1000.00")
        assert s.roi_pct == D("13.5000")
        assert s.win_rate_pct == D("50.0000")
        # Sharpe is non-zero (mixed positive and negative pnls).
        assert s.sharpe != D("0")

    def test_zero_stake_does_not_explode(self) -> None:
        # Hypothetical degenerate case — stake 0 should not divide-by-zero.
        rows = [_row(idx=1, pnl="10.00", stake="0.00")]
        s = compute_summary(rows)
        assert s.roi_pct == D("0")  # safe fallback
        assert s.sharpe == D("0")   # only 1 trade — stdev undefined

    def test_single_trade_sharpe_zero(self) -> None:
        # stdev of a one-element sample is undefined → Sharpe falls back to 0.
        rows = [_row(idx=1, pnl="50.00")]
        assert compute_summary(rows).sharpe == D("0")

    def test_identical_rois_yield_zero_sharpe(self) -> None:
        # Multiple trades with the SAME ROI → stdev == 0 → Sharpe = 0.
        rows = [_row(idx=i, pnl="20.00", stake="100.00") for i in range(1, 6)]
        assert compute_summary(rows).sharpe == D("0")


# ---------------------------------------------------------------------------
# compute_drawdown
# ---------------------------------------------------------------------------


class TestDrawdown:
    def test_drawdown_after_a_loss_streak(self) -> None:
        # +100 → +50 → -80 → +30  (cumulative: 100, 150, 70, 100)
        # Starting bankroll 1000 → equity 1100, 1150, 1070, 1100.
        # Peak = 1150 at trade 2; trough = 1070 at trade 3 → max_dd = 80 (≈6.96%)
        rows = [
            _row(idx=1, pnl="100.00"),
            _row(idx=2, pnl="50.00"),
            _row(idx=3, pnl="-80.00"),
            _row(idx=4, pnl="30.00"),
        ]
        ds = compute_drawdown(rows, starting_bankroll=D("1000"))
        assert len(ds.points) == 4
        assert ds.max_drawdown_eur == D("80.00")
        # 80/1150 ≈ 0.06956 → 6.9565
        assert ds.max_drawdown_pct == D("6.9565")
        # Series increments cumulatively
        assert [p.cum_pnl_eur for p in ds.points] == [
            D("100.00"), D("150.00"), D("70.00"), D("100.00"),
        ]

    def test_drawdown_empty_returns_empty_series(self) -> None:
        ds = compute_drawdown([], starting_bankroll=D("1000"))
        assert ds.points == []
        assert ds.max_drawdown_eur == D("0")

    def test_drawdown_with_zero_starting_bankroll_is_safe(self) -> None:
        # Edge: starting_bankroll = 0 → absolute drawdown still measurable
        # (peak=0, equity=-50, so dd_eur=50), but pct is undefined → 0.
        rows = [_row(idx=1, pnl="-50.00")]
        ds = compute_drawdown(rows, starting_bankroll=D("0"))
        assert ds.max_drawdown_pct == D("0")
        assert ds.max_drawdown_eur == D("50.00")


# ---------------------------------------------------------------------------
# compute_rolling
# ---------------------------------------------------------------------------


class TestRolling:
    def test_rolling_window_3(self) -> None:
        # Five trades with pnls [50, 20, 80, 10, 40], all stake=100. window=3.
        # idx=2: trades 0..2  (pnl=150, stake=300, ROI=50%)
        # idx=3: trades 1..3  (pnl=110, stake=300, ROI=36.6667%)
        # idx=4: trades 2..4  (pnl=130, stake=300, ROI=43.3333%)
        rows = [
            _row(idx=1, pnl="50.00"),
            _row(idx=2, pnl="20.00"),
            _row(idx=3, pnl="80.00"),
            _row(idx=4, pnl="10.00"),
            _row(idx=5, pnl="40.00"),
        ]
        out = compute_rolling(rows, window=3)
        assert [p.idx for p in out] == [2, 3, 4]
        assert out[0].roi_pct == D("50.0000")
        assert out[1].roi_pct == D("36.6667")
        assert out[2].roi_pct == D("43.3333")
        # All wins → win_rate 100%
        assert all(p.win_rate_pct == D("100.0000") for p in out)

    def test_rolling_returns_empty_when_too_few_trades(self) -> None:
        rows = [_row(idx=1, pnl="50.00"), _row(idx=2, pnl="20.00")]
        assert compute_rolling(rows, window=5) == []

    def test_rolling_invalid_window_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_rolling([_row(idx=1, pnl="0")], window=0)


# ---------------------------------------------------------------------------
# Breakdowns
# ---------------------------------------------------------------------------


class TestBreakdowns:
    @pytest.fixture
    def two_strategies(self) -> list[TradeRow]:
        return [
            _row(idx=1, pnl="50.00", strategy="magic-cs", strategy_name="Magic CS", outcome="A1_HIT"),
            _row(idx=2, pnl="-100.00", strategy="magic-cs", strategy_name="Magic CS", outcome="A2_OVER25"),
            _row(idx=3, pnl="80.00", strategy="draw-hunter", strategy_name="Draw Hunter", outcome="WIN"),
            _row(idx=4, pnl="-110.00", strategy="draw-hunter", strategy_name="Draw Hunter", outcome="LOSS"),
            _row(idx=5, pnl="40.00", strategy="draw-hunter", strategy_name="Draw Hunter", outcome="WIN"),
        ]

    def test_breakdown_by_strategy_sorted_by_pnl_desc(self, two_strategies) -> None:
        out = breakdown_by_strategy(two_strategies)
        assert len(out) == 2
        # draw_hunter: 80 - 110 + 40 = 10; magic-cs: 50 - 100 = -50
        assert out[0].key == "draw-hunter"
        assert out[0].total_pnl_eur == D("10.00")
        assert out[1].key == "magic-cs"
        assert out[1].total_pnl_eur == D("-50.00")

    def test_breakdown_by_outcome_label(self, two_strategies) -> None:
        out = breakdown_by_outcome_label(two_strategies)
        keys = [b.key for b in out]
        assert set(keys) == {"A1_HIT", "A2_OVER25", "WIN", "LOSS"}
        # WIN total = 80 + 40 = 120
        win_row = next(b for b in out if b.key == "WIN")
        assert win_row.n_trades == 2
        assert win_row.total_pnl_eur == D("120.00")

    def test_breakdown_by_league_with_default_unset_label(self) -> None:
        rows = [
            _row(idx=1, pnl="10.00", league="Serie A", outcome=None),
            _row(idx=2, pnl="-5.00", league="Serie A", outcome=None),
        ]
        out = breakdown_by_outcome_label(rows)
        assert len(out) == 1
        assert out[0].key == "(unset)"
        assert out[0].n_trades == 2

    def test_breakdown_by_league(self, two_strategies) -> None:
        # All from default Serie A — single bucket
        out = breakdown_by_league(two_strategies)
        assert len(out) == 1
        assert out[0].key == "Serie A"
        assert out[0].n_trades == 5


# ---------------------------------------------------------------------------
# Calendar grid
# ---------------------------------------------------------------------------


class TestCalendarGrid:
    def test_buckets_by_dow_and_hour(self) -> None:
        # Tue 14:00 (dow=1, hour=14) and Sat 20:00 (dow=5, hour=20)
        tue = datetime(2026, 4, 28, 14, 0, tzinfo=UTC)  # Tuesday
        sat = datetime(2026, 5, 2, 20, 0, tzinfo=UTC)   # Saturday
        rows = [
            _row(idx=1, pnl="10.00", kickoff=tue),
            _row(idx=2, pnl="20.00", kickoff=tue),
            _row(idx=3, pnl="-5.00", kickoff=sat),
        ]
        grid = compute_calendar_grid(rows)
        assert len(grid.cells) == 2
        # Sorted by (dow, hour) → Tuesday cell first
        assert grid.cells[0].day_of_week == 1
        assert grid.cells[0].hour == 14
        assert grid.cells[0].n_trades == 2
        assert grid.cells[0].pnl_eur == D("30.00")
        assert grid.cells[1].day_of_week == 5
        assert grid.cells[1].hour == 20

    def test_empty_grid(self) -> None:
        assert compute_calendar_grid([]).cells == []


# ---------------------------------------------------------------------------
# Helpers used in the API layer
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_count_outcomes_excludes_open_and_void(self, mixed_pnls) -> None:
        out = count_outcomes(mixed_pnls)
        # 5 wins + 5 losses among the closed ones; void/open excluded.
        assert out == {"WIN": 5, "LOSS": 5}

    def test_cumulative_pnl(self) -> None:
        rows = [
            _row(idx=1, pnl="10.00"),
            _row(idx=2, pnl="-3.00"),
            _row(idx=3, pnl="5.00"),
        ]
        cum = cumulative_pnl(rows)
        assert [v for _, v in cum] == [D("10.00"), D("7.00"), D("12.00")]
