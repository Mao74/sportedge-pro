"""PnL calculator — single source of truth for ``trades.computed_pnl_eur``.

This is a *journal* helper, not a strategy backtester. The calculator does
NOT encode any scenario-based logic from individual strategies (Magic CS,
Draw Hunter, etc.). Strategies own their own form fields via
``strategy.field_schema`` for fast logging, but the actual PnL is one of:

- ``MANUAL``       — user-supplied PnL stored verbatim. Commission NOT applied.
- ``CASHOUT_ODDS`` — system-computed using the simplified cashout model
                     spelled out in docs/strategies.md (and the WhatIf widget).
                     NOT Betfair's literal lay-back formula.
- ``AUTO``         — universal back/lay PnL from ``stake_total``, ``avg_odds``,
                     ``commission_pct``, ``position_side`` and ``outcome_label``
                     ∈ {WIN, LOSS, HALF_WIN, HALF_LOSS, VOID}. Commission is
                     applied to *winning* components only.

``market_type`` modulates commission application:

- ``exchange`` (Betfair, Smarkets, …): commission_pct is applied on wins.
- ``classic``  (Snai, Bet365, …): quoted odds are already net of margin →
                  commission_factor is forced to 1.0 regardless of
                  commission_pct (MANUAL mode is unaffected — it's verbatim).

All money values flow through this module as ``Decimal``. The final
``computed_pnl_eur`` is quantised to 2 decimal places (banker's rounding —
ROUND_HALF_EVEN), matching the Numeric(10, 2) DB column.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Literal

from app.models import MarketType, PnLMode

PositionSide = Literal["back", "lay"]

ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class PnLInputs:
    """Plain-data inputs for the PnL calculator. Decoupled from the ORM so
    the module is unit-testable without a DB."""

    pnl_mode: PnLMode

    # Universal trade fields
    stake_total: Decimal
    avg_odds: Decimal
    commission_pct: Decimal = Decimal("5.00")
    # exchange = apply commission on wins (current default).
    # classic  = quoted odds are already net of the bookmaker margin →
    #            commission_factor is forced to 1.0 regardless of
    #            commission_pct.
    market_type: MarketType = MarketType.exchange

    # Mode-specific
    cashout_odds: Decimal | None = None
    position_side: PositionSide | None = None
    manual_pnl_eur: Decimal | None = None
    outcome_label: str | None = None

    # Free-form context (not used by the calculator; carried for traceability).
    strategy_data: dict[str, Any] = field(default_factory=dict)


class PnLComputationError(ValueError):
    """Raised when inputs are insufficient or invalid for the chosen mode."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_pnl(inputs: PnLInputs) -> Decimal:
    """Compute the canonical ``computed_pnl_eur`` for a trade.

    The returned ``Decimal`` is quantised to 2 dp. Callers must persist it as
    the source of truth — analytics never recompute on the fly.
    """
    if inputs.pnl_mode is PnLMode.MANUAL:
        result = _compute_manual(inputs)
    elif inputs.pnl_mode is PnLMode.CASHOUT_ODDS:
        result = _compute_cashout_odds(inputs)
    elif inputs.pnl_mode is PnLMode.AUTO:
        result = _compute_auto(inputs)
    else:  # pragma: no cover — exhaustive enum match
        raise PnLComputationError(f"Unknown pnl_mode: {inputs.pnl_mode}")

    return _quantise(result)


# ---------------------------------------------------------------------------
# MANUAL
# ---------------------------------------------------------------------------


def _compute_manual(i: PnLInputs) -> Decimal:
    if i.manual_pnl_eur is None:
        raise PnLComputationError("MANUAL mode requires manual_pnl_eur.")
    return i.manual_pnl_eur


# ---------------------------------------------------------------------------
# CASHOUT_ODDS
# ---------------------------------------------------------------------------


def _compute_cashout_odds(i: PnLInputs) -> Decimal:
    """Implements the simplified cashout model from docs/strategies.md.

    NOTE — this is *not* Betfair's literal lay-back math. The docs treat
    ``cashout_odds`` as an "effective settlement odds" rather than the
    counter-bet price. For a back, locked-in PnL = stake * (cashout_odds - 1)
    with commission applied to wins only. For a lay, locked-in PnL =
    stake - stake * (cashout_odds - 1) = stake * (2 - cashout_odds), again
    with commission on wins.
    """
    if i.cashout_odds is None:
        raise PnLComputationError("CASHOUT_ODDS mode requires cashout_odds.")
    if i.position_side is None:
        raise PnLComputationError("CASHOUT_ODDS mode requires position_side.")

    cf = _commission_factor(i.commission_pct, i.market_type)

    if i.position_side == "back":
        gross = i.stake_total * (i.cashout_odds - ONE)
    elif i.position_side == "lay":
        payout = i.stake_total * (i.cashout_odds - ONE)
        gross = i.stake_total - payout
    else:  # pragma: no cover — Literal narrows to the two values above
        raise PnLComputationError(f"Invalid position_side: {i.position_side}")

    return gross * cf if gross > ZERO else gross


# ---------------------------------------------------------------------------
# AUTO — universal back/lay journal calculator
# ---------------------------------------------------------------------------


_AUTO_OUTCOMES = frozenset({"WIN", "LOSS", "VOID", "HALF_WIN", "HALF_LOSS"})


def _compute_auto(i: PnLInputs) -> Decimal:
    """Universal back/lay PnL from stake/odds/commission and outcome_label.

    The calculator is strategy-agnostic. Strategy-specific scenarios (e.g.
    Magic CS ``A1_HIT``, Draw Hunter ``SCRATCH``) live as user-chosen
    labels in ``strategy_data`` for filtering and aggregation; they do NOT
    drive PnL computation here.

    ``position_side`` and ``outcome_label`` may be supplied either as
    explicit ``PnLInputs`` fields or through ``strategy_data`` (the trade
    form may surface them via the dynamic field renderer).

    ============  ==================================  =================================
    outcome       back PnL (gross)                    lay PnL (gross)
    ============  ==================================  =================================
    WIN           stake * (avg_odds - 1)              +stake
    LOSS          -stake                              -stake * (avg_odds - 1)
    HALF_WIN      stake * (avg_odds - 1) / 2          +stake / 2
    HALF_LOSS     -stake / 2                          -stake * (avg_odds - 1) / 2
    VOID          0                                   0
    ============  ==================================  =================================

    Commission is applied to gross profits only.
    """
    side = i.position_side or i.strategy_data.get("position_side")
    outcome = i.outcome_label or i.strategy_data.get("outcome_label")

    if side not in ("back", "lay"):
        raise PnLComputationError(
            "AUTO mode requires position_side ('back' or 'lay'), either as a "
            "field on PnLInputs or in strategy_data."
        )
    if outcome not in _AUTO_OUTCOMES:
        raise PnLComputationError(
            f"AUTO mode requires outcome_label in {sorted(_AUTO_OUTCOMES)}; got {outcome!r}."
        )

    cf = _commission_factor(i.commission_pct, i.market_type)
    stake = i.stake_total
    odds = i.avg_odds

    if outcome == "VOID":
        return ZERO

    if side == "back":
        if outcome == "WIN":
            return stake * (odds - ONE) * cf
        if outcome == "LOSS":
            return -stake
        if outcome == "HALF_WIN":
            return stake * (odds - ONE) / TWO * cf
        if outcome == "HALF_LOSS":
            return -stake / TWO

    # side == "lay"
    if outcome == "WIN":
        return stake * cf
    if outcome == "LOSS":
        return -stake * (odds - ONE)
    if outcome == "HALF_WIN":
        return stake / TWO * cf
    if outcome == "HALF_LOSS":
        return -stake * (odds - ONE) / TWO

    raise PnLComputationError(  # pragma: no cover — guarded by validation above
        f"Unhandled AUTO case: side={side} outcome={outcome}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _commission_factor(commission_pct: Decimal, market_type: MarketType) -> Decimal:
    # Classic bookmaker odds are already net of the venue margin → no
    # commission is applied. Only betting exchanges charge on wins.
    if market_type is MarketType.classic:
        return ONE
    return ONE - commission_pct / HUNDRED


def _quantise(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_EVEN)
