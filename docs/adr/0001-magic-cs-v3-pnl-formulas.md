# ADR-0001 — Magic CS v3 AUTO PnL formulas (interpretive)

**Date**: 2026-04-28
**Status**: SUPERSEDED by [ADR-0002](0002-journal-not-backtester.md). The
calculator no longer encodes per-strategy scenario logic. This ADR is kept
for historical context; do not implement against it.

## Context

`docs/strategies.md` instructs us to "port the scenario-based logic from the
legacy SportEdge Journal backtester verbatim". The legacy source code was not
provided alongside the spec. This ADR pins down the formulas implemented in
`app/services/pnl_calculator.py::_compute_magic_cs_v3` so they can be reviewed
and corrected in one place.

## Trade model

A Magic CS v3 trade has three independent components:

| Component | Inputs |
|---|---|
| CS basket | `stake_total` distributed across selected correct-scores at weighted `avg_odds` |
| Lay 0-0 hedge (optional) | `lay_00_placed: bool`, `lay_00_stake: €` |
| Over 2.5 parachute (optional) | `o25_placed: bool`, `o25_stake: €`, `o25_odds` |

Commission is the universal `commission_pct` (default 5%, Betfair).

## Per-component formulas (gross, before commission)

| Component | Win | Loss |
|---|---|---|
| CS basket | `stake_total * (avg_odds - 1)` | `-stake_total` |
| Lay 0-0 | `+lay_00_stake` | not computable (lay-0-0 odds not in schema) |
| O2.5 parachute | `o25_stake * (o25_odds - 1)` | `-o25_stake` |

Commission factor `cf = 1 - commission_pct / 100` is applied to **winning
components only**.

## Scenarios (interpretive)

| Scenario | CS basket | Lay 0-0 | O2.5 parachute | Notes |
|---|---|---|---|---|
| `A1_HIT` | win | win | scratched | A selected CS landed at FT. Lay 0-0 wins because CS hit ≠ 0-0; O2.5 is treated as cashed-at-break-even when the CS landed. |
| `A2_OVER25` | loss | win | win | No CS hit, match went Over 2.5. Identical to `C_MULTI_GOAL` mathematically. |
| `B1_EARLY_CS` | win | win | scratched | Treated as `A1_HIT`. Real partial cash-outs should use CASHOUT_ODDS. |
| `B2_EARLY_OVER` | scratched | scratched | win | Only the O2.5 component locks in. CS basket and lay-0-0 left in play (no PnL). |
| `B3_EARLY_MISS` | loss | scratched | scratched | Early cut-loss. CS basket loses in full; lay-0-0 and O2.5 not yet resolved. |
| `C_MULTI_GOAL` | loss | win | win | High-scoring miss-of-CS — same math as `A2_OVER25`. |
| `OTHER` | n/a | n/a | n/a | Not handled — caller must use MANUAL mode. |

"Scratched" means the component contributes 0 to PnL.

## Known limitations

1. **Lay 0-0 loss** (final 0-0 score) is not computable: the schema does not
   carry a `lay_00_odds` field. Trades that end 0-0 must use MANUAL mode. If
   we need AUTO support for that case, add `lay_00_odds` to the field schema
   in a follow-up migration.
2. **B-scenarios** (`B1_EARLY_CS`, `B2_EARLY_OVER`, `B3_EARLY_MISS`) describe
   *early exits*. A clean Betfair cash-out would carry an explicit cash-out
   price; AUTO mode here approximates with a "treat-as-final" model. Traders
   wanting exact early-exit math should use the CASHOUT_ODDS mode instead.
3. **CS basket odds**: we treat `avg_odds` as the *effective single-bet odds*
   for the basket. This is exact when all picks share equal stake and the
   gain is `stake_total * (avg_odds - 1)`; it is an approximation otherwise.

## Decision

Implement the formulas in the table above as the canonical AUTO calculation
for Magic CS v3. Expose the OTHER scenario as a MANUAL fallback. Document the
limitations above in user-facing copy on the trade-entry form once it lands
(step 10).

## Consequences

- Tests in `backend/tests/test_pnl_calculator.py` pin down each formula with
  hand-computed expected values. Any change in this ADR must update both the
  calculator and the test fixtures atomically.
- If the legacy backtester surfaces and uses different formulas, this ADR
  must be revised to a `Status: SUPERSEDED` and a follow-up ADR documents the
  corrected math.

## Owner

Backend (the trader). Review point: before the first Magic CS v3 trade is
logged in production.
