"""PnL calculator unit tests.

Each expected value was computed by hand and double-checked. When you change
a formula, update both the implementation in
``app/services/pnl_calculator.py`` AND the corresponding expected value here
in the same commit — there is no "regenerate fixtures" shortcut.

The calculator is strategy-agnostic (journal, not backtester): there are no
Magic CS / Draw Hunter scenarios encoded here. AUTO mode is a universal
back/lay formula keyed on ``position_side`` + ``outcome_label``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models import MarketType, PnLMode
from app.services.pnl_calculator import (
    PnLComputationError,
    PnLInputs,
    compute_pnl,
)

D = Decimal


def _base(**overrides: object) -> PnLInputs:
    """Build a PnLInputs with sensible defaults that callers override per case."""
    defaults: dict[str, object] = {
        "pnl_mode": PnLMode.AUTO,
        "stake_total": D("100.00"),
        "avg_odds": D("3.00"),
        "commission_pct": D("5.00"),
        "strategy_data": {},
    }
    defaults.update(overrides)
    return PnLInputs(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MANUAL
# ---------------------------------------------------------------------------


class TestManual:
    def test_returns_manual_value_verbatim(self) -> None:
        inputs = _base(pnl_mode=PnLMode.MANUAL, manual_pnl_eur=D("42.50"))
        assert compute_pnl(inputs) == D("42.50")

    def test_negative_manual_value(self) -> None:
        inputs = _base(pnl_mode=PnLMode.MANUAL, manual_pnl_eur=D("-17.20"))
        assert compute_pnl(inputs) == D("-17.20")

    def test_quantises_to_two_places(self) -> None:
        # 12.345 → ROUND_HALF_EVEN → 12.34 (banker's rounding)
        inputs = _base(pnl_mode=PnLMode.MANUAL, manual_pnl_eur=D("12.345"))
        assert compute_pnl(inputs) == D("12.34")

    def test_missing_manual_pnl_raises(self) -> None:
        inputs = _base(pnl_mode=PnLMode.MANUAL)
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)


# ---------------------------------------------------------------------------
# CASHOUT_ODDS — back
# ---------------------------------------------------------------------------


class TestCashoutOddsBack:
    def test_winning_back_applies_commission(self) -> None:
        # WhatIf widget canonical example: 62 * (1.45 - 1) * 0.95 = 26.505 → 26.50 (HALF_EVEN)
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("62.00"),
            avg_odds=D("5.42"),
            commission_pct=D("5.00"),
            cashout_odds=D("1.45"),
            position_side="back",
        )
        assert compute_pnl(inputs) == D("26.50")

    def test_winning_back_no_commission(self) -> None:
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("100.00"),
            avg_odds=D("3.00"),
            commission_pct=D("0.00"),
            cashout_odds=D("2.00"),
            position_side="back",
        )
        # 100 * (2 - 1) * 1 = 100.00
        assert compute_pnl(inputs) == D("100.00")

    def test_losing_back_no_commission_applied(self) -> None:
        # cashout_odds < 1 is unusual but the formula must handle it without
        # silently applying commission to a negative gross.
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("50.00"),
            cashout_odds=D("0.80"),
            position_side="back",
        )
        # 50 * (0.80 - 1) = -10.00, no commission.
        assert compute_pnl(inputs) == D("-10.00")


# ---------------------------------------------------------------------------
# CASHOUT_ODDS — lay
# ---------------------------------------------------------------------------


class TestCashoutOddsLay:
    def test_winning_lay_applies_commission(self) -> None:
        # 62 - 62*(1.45 - 1) = 62 - 27.90 = 34.10; * 0.95 = 32.395 → 32.40 (HALF_EVEN)
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("62.00"),
            commission_pct=D("5.00"),
            cashout_odds=D("1.45"),
            position_side="lay",
        )
        assert compute_pnl(inputs) == D("32.40")

    def test_losing_lay_no_commission(self) -> None:
        # cashout_odds=2.50, stake=20: 20 - 20*(2.5-1) = 20 - 30 = -10. No commission.
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("20.00"),
            cashout_odds=D("2.50"),
            position_side="lay",
        )
        assert compute_pnl(inputs) == D("-10.00")

    def test_breakeven_lay(self) -> None:
        # cashout_odds = 2 → stake - stake*(2-1) = 0
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("50.00"),
            cashout_odds=D("2.00"),
            position_side="lay",
        )
        assert compute_pnl(inputs) == D("0.00")


class TestCashoutOddsValidation:
    def test_missing_cashout_odds_raises(self) -> None:
        inputs = _base(pnl_mode=PnLMode.CASHOUT_ODDS, position_side="back")
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)

    def test_missing_position_side_raises(self) -> None:
        inputs = _base(pnl_mode=PnLMode.CASHOUT_ODDS, cashout_odds=D("1.50"))
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)


# ---------------------------------------------------------------------------
# AUTO — universal back/lay calculator
# ---------------------------------------------------------------------------


class TestAutoBack:
    def _back(self, outcome: str) -> PnLInputs:
        return _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),
            position_side="back",
            outcome_label=outcome,
        )

    def test_back_win(self) -> None:
        # 100 * (2.5 - 1) * 0.95 = 142.50
        assert compute_pnl(self._back("WIN")) == D("142.50")

    def test_back_loss(self) -> None:
        assert compute_pnl(self._back("LOSS")) == D("-100.00")

    def test_back_half_win(self) -> None:
        # 100 * 1.5 / 2 * 0.95 = 71.25
        assert compute_pnl(self._back("HALF_WIN")) == D("71.25")

    def test_back_half_loss(self) -> None:
        assert compute_pnl(self._back("HALF_LOSS")) == D("-50.00")

    def test_back_void(self) -> None:
        assert compute_pnl(self._back("VOID")) == D("0.00")


class TestAutoLay:
    def _lay(self, outcome: str) -> PnLInputs:
        return _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),
            position_side="lay",
            outcome_label=outcome,
        )

    def test_lay_win(self) -> None:
        # 100 * 0.95 = 95.00
        assert compute_pnl(self._lay("WIN")) == D("95.00")

    def test_lay_loss(self) -> None:
        # -100 * (2.5 - 1) = -150.00
        assert compute_pnl(self._lay("LOSS")) == D("-150.00")

    def test_lay_half_win(self) -> None:
        # 100 / 2 * 0.95 = 47.50
        assert compute_pnl(self._lay("HALF_WIN")) == D("47.50")

    def test_lay_half_loss(self) -> None:
        # -100 * (2.5 - 1) / 2 = -75.00
        assert compute_pnl(self._lay("HALF_LOSS")) == D("-75.00")

    def test_lay_void(self) -> None:
        assert compute_pnl(self._lay("VOID")) == D("0.00")


class TestAutoSourcing:
    """position_side and outcome_label may also be supplied via strategy_data."""

    def test_side_and_outcome_from_strategy_data(self) -> None:
        inputs = _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),
            strategy_data={"position_side": "back", "outcome_label": "WIN"},
        )
        assert compute_pnl(inputs) == D("142.50")

    def test_explicit_field_overrides_strategy_data(self) -> None:
        # Explicit position_side='lay' must win over strategy_data['position_side']='back'.
        inputs = _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),
            position_side="lay",
            outcome_label="WIN",
            strategy_data={"position_side": "back", "outcome_label": "LOSS"},
        )
        assert compute_pnl(inputs) == D("95.00")  # lay WIN, not back LOSS

    def test_strategy_label_does_not_drive_pnl(self) -> None:
        # User can record a strategy-specific scenario tag like "A2_OVER25" in
        # strategy_data — it must NOT affect the PnL computation. Only
        # outcome_label ∈ {WIN,LOSS,...} is used.
        inputs = _base(
            stake_total=D("60.00"),
            avg_odds=D("4.00"),
            position_side="back",
            outcome_label="LOSS",
            strategy_data={"scenario": "A2_OVER25", "lay_00_stake": 10, "o25_stake": 20},
        )
        # AUTO/back/LOSS = -stake regardless of strategy_data noise.
        assert compute_pnl(inputs) == D("-60.00")


class TestAutoValidation:
    def test_missing_side_raises(self) -> None:
        inputs = _base(outcome_label="WIN")
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)

    def test_missing_outcome_raises(self) -> None:
        inputs = _base(position_side="back")
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)

    def test_unknown_outcome_raises(self) -> None:
        inputs = _base(position_side="back", outcome_label="WEIRD")
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)

    def test_strategy_specific_label_rejected_in_auto(self) -> None:
        # Magic CS / Draw Hunter scenario labels are NOT valid AUTO outcomes.
        inputs = _base(position_side="back", outcome_label="A2_OVER25")
        with pytest.raises(PnLComputationError):
            compute_pnl(inputs)


# ---------------------------------------------------------------------------
# Market type — classic vs exchange
# ---------------------------------------------------------------------------


class TestMarketType:
    """Classic bookmaker (Snai/Bet365): quoted odds are already net, so the
    PnL calculator forces commission_factor to 1.0 — commission_pct is
    irrelevant. Exchange (Betfair/Smarkets): current behaviour."""

    def test_auto_back_win_classic_ignores_commission(self) -> None:
        # 100 * (2.5 - 1) * 1.0 = 150.00 (no commission on classic)
        inputs = _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),  # ignored when classic
            position_side="back",
            outcome_label="WIN",
            market_type=MarketType.classic,
        )
        assert compute_pnl(inputs) == D("150.00")

    def test_auto_back_win_exchange_applies_commission(self) -> None:
        # Same trade on an exchange: 100 * 1.5 * 0.95 = 142.50
        inputs = _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),
            position_side="back",
            outcome_label="WIN",
            market_type=MarketType.exchange,
        )
        assert compute_pnl(inputs) == D("142.50")

    def test_cashout_odds_classic_no_commission(self) -> None:
        # 62 * (1.45 - 1) * 1.0 = 27.90 vs the exchange 26.50 baseline.
        inputs = _base(
            pnl_mode=PnLMode.CASHOUT_ODDS,
            stake_total=D("62.00"),
            avg_odds=D("5.42"),
            commission_pct=D("5.00"),
            cashout_odds=D("1.45"),
            position_side="back",
            market_type=MarketType.classic,
        )
        assert compute_pnl(inputs) == D("27.90")

    def test_lay_win_classic_full_stake(self) -> None:
        # Lay WIN on classic: full stake kept (cf=1.0).
        inputs = _base(
            stake_total=D("100.00"),
            avg_odds=D("2.50"),
            commission_pct=D("5.00"),
            position_side="lay",
            outcome_label="WIN",
            market_type=MarketType.classic,
        )
        assert compute_pnl(inputs) == D("100.00")

    def test_manual_mode_unaffected_by_market_type(self) -> None:
        # MANUAL is verbatim, market_type is irrelevant.
        for mt in (MarketType.exchange, MarketType.classic):
            inputs = _base(
                pnl_mode=PnLMode.MANUAL,
                manual_pnl_eur=D("42.50"),
                market_type=mt,
            )
            assert compute_pnl(inputs) == D("42.50")

    def test_loss_outcomes_unaffected(self) -> None:
        # Losses don't accrue commission either way → market_type is moot.
        ex = _base(
            position_side="back",
            outcome_label="LOSS",
            market_type=MarketType.exchange,
        )
        cl = _base(
            position_side="back",
            outcome_label="LOSS",
            market_type=MarketType.classic,
        )
        assert compute_pnl(ex) == compute_pnl(cl) == D("-100.00")
