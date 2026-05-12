# ADR-0002 — SportEdge Pro is a journal, not a backtester

**Date**: 2026-04-28
**Status**: ACCEPTED
**Supersedes**: [ADR-0001](0001-magic-cs-v3-pnl-formulas.md)

## Context

`docs/strategies.md` originally instructed the PnL calculator to encode
scenario-specific logic for each built-in strategy (Magic CS v3 with seven
outcome scenarios; draw_hunter S4 with WIN/LOSS/SCRATCH formulas). ADR-0001
attempted an interpretive port. On review the trader rejected this direction:

> "ma non entrerei nel merito, voglio un journal"

The app is a record of what happened, not a reproducer of strategy decisions.

## Decision

The PnL calculator (`app/services/pnl_calculator.py`) is strategy-agnostic.
It supports three modes:

- **`MANUAL`** — user types in the final PnL. Stored verbatim. No commission
  applied.
- **`CASHOUT_ODDS`** — closed-form formula on `(stake_total, cashout_odds,
  position_side, commission_pct)`. Doubles as the engine of the WhatIf
  cash-out widget. Strategy is irrelevant.
- **`AUTO`** — closed-form back/lay formula on `(stake_total, avg_odds,
  commission_pct, position_side, outcome_label)` where `outcome_label ∈
  {WIN, LOSS, HALF_WIN, HALF_LOSS, VOID}`. Same formula for every strategy
  (built-in or custom). Commission applied to wins only.

Strategies own their `field_schema` to drive a fast, ergonomic logging form
(chips, pickers, computed read-only fields). Strategy-specific scenario
labels (`A1_HIT`, `A2_OVER25`, `B1_EARLY_CS`, `WIN`, `SCRATCH`, etc.) are
stored verbatim in `trades.strategy_data` and `trades.outcome_label` and
power filtering and aggregation in analytics — they do NOT drive PnL.

For trades the simple formulas can't capture (partial cash-outs across
multiple legs, dutched portfolios, weird edge cases), the trader uses
`MANUAL` mode.

## Consequences

- The PnL calculator collapses to ~80 lines and is trivially testable.
- The DB enum `pnl_mode` keeps the value `AUTO` (no migration needed).
- The DB column `outcome_label` is preserved as a free-form tag column for
  analytics filtering — its values are not constrained by the calculator
  except when `pnl_mode = AUTO` (in which case the universal outcomes apply).
- Strategy `field_schema` (Magic CS v3, draw_hunter S4) is unchanged: still
  used to render the trade form. The `scenario` / `exit_type` fields become
  free-form classification tags.
- Step 4 (analytics) can group/breakdown by `outcome_label` and arbitrary
  `strategy_data` keys without coupling to scenario-specific math.
- ADR-0001 is SUPERSEDED. Its scenario formulas are no longer authoritative.

## Validation

44 → 26 unit tests. 100% line coverage on the calculator preserved. All
tests run in <0.5s.
