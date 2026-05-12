# Strategies, PnL, and the What-if widget

How strategies are defined, how PnL is calculated under the three cash-out
modes, and how the standalone what-if cash-out widget works.

## Strategies — built-in vs custom

Two kinds of strategies coexist, sharing the same DB table and the same
field-schema mechanism for dynamic forms.

### Built-in templates

Hardcoded in `services/strategy_templates.py` via a registry pattern:

```python
@dataclass
class StrategyTemplate:
    template_key: str
    name: str
    description: str
    color_hex: str
    field_schema: dict
    auto_pnl_calculator: Callable[[Trade], Decimal]   # used when pnl_mode=AUTO

REGISTRY: dict[str, StrategyTemplate] = {
    "magic_cs_v3":    MAGIC_CS_V3_TEMPLATE,
    "draw_hunter_s4": DRAW_HUNTER_S4_TEMPLATE,
}
```

On app startup, `seed_strategies()` upserts the registry entries into the
`strategies` table, ensuring `kind='builtin'` and the correct `template_key`,
`field_schema`, and `color_hex`. The `name` field is preserved if the user has
renamed it (no overwrite if a row already exists with the same `template_key`).

#### Permission matrix for built-in strategies

| Action | Allowed |
|---|---|
| Rename display `name` | Yes |
| Change `color_hex`, `description`, `is_active` | Yes |
| Modify `field_schema` | No (server rejects) |
| Modify `template_key` or `kind` | No (server rejects) |
| Hard delete | No (HTTP 409). Deactivate instead. |

#### Magic CS template

Field schema (concise):

```json
{
  "fields": [
    {"key": "cs_selected", "label": "CS selected", "type": "chip-picker",
     "options": ["0-0","1-0","0-1","1-1","2-0","0-2","2-1","1-2","2-2","3-0","0-3","3-1","1-3"],
     "min_picks": 1, "max_picks": 6, "required": true},
    {"key": "tier", "label": "Tier", "type": "select",
     "options": ["1-CS","2-CS","3-CS","4-CS"], "required": true},
    {"key": "lay_00_placed", "label": "Lay 0-0 placed", "type": "boolean", "default": false},
    {"key": "lay_00_stake", "label": "Lay 0-0 stake (€)", "type": "number",
     "depends_on": "lay_00_placed", "min": 0, "step": 0.01},
    {"key": "o25_placed", "label": "O2.5 parachute placed", "type": "boolean", "default": false},
    {"key": "o25_stake", "label": "O2.5 stake (€)", "type": "number",
     "depends_on": "o25_placed", "min": 0, "step": 0.01},
    {"key": "o25_odds", "label": "O2.5 odds at entry", "type": "number",
     "depends_on": "o25_placed", "min": 1.01, "step": 0.01},
    {"key": "scenario", "label": "Outcome scenario", "type": "select",
     "options": ["A1_HIT","A2_OVER25","B1_EARLY_CS","B2_EARLY_OVER","B3_EARLY_MISS","C_MULTI_GOAL","OTHER"],
     "required_for_status": "CLOSED"}
  ]
}
```

`auto_pnl_calculator` — port the scenario-based logic from the legacy
SportEdge Journal backtester. Each scenario has its own formula combining
CS hit/miss, lay 0-0 outcome, O2.5 parachute outcome, and Betfair commission.
Implementation reference: see how the legacy `pnl_for_trade()` switches on
`scenario` and combines stakes/odds. Port it verbatim, with all branches:
`A1_HIT`, `A2_OVER25`, `B1_EARLY_CS`, `B2_EARLY_OVER`, `B3_EARLY_MISS`,
`C_MULTI_GOAL`. For `OTHER`, fall back to `MANUAL` mode (require user to
input `manual_pnl_eur`).

#### Draw Hunter template

Field schema:

```json
{
  "fields": [
    {"key": "lay_stake", "label": "Lay stake (€)", "type": "number",
     "min": 0.01, "step": 0.01, "required": true},
    {"key": "draw_odds", "label": "Draw odds at entry", "type": "number",
     "min": 1.01, "step": 0.01, "required": true},
    {"key": "entry_minute", "label": "Entry minute", "type": "number",
     "min": 0, "max": 90, "step": 1},
    {"key": "xg_diff", "label": "xG asymmetry", "type": "number",
     "step": 0.01, "min": -5, "max": 5},
    {"key": "exit_type", "label": "Exit", "type": "select",
     "options": ["WIN","LOSS","SCRATCH","MANUAL"],
     "required_for_status": "CLOSED"}
  ]
}
```

`auto_pnl_calculator`:
- `WIN`     → `+lay_stake * (1 - commission_pct/100)`
- `LOSS`    → `-lay_stake * (draw_odds - 1)`
- `SCRATCH` → `Decimal("0.00")`
- `MANUAL`  → fall back to MANUAL mode (`manual_pnl_eur` required)

### Custom strategies

User-creatable. The user writes the `field_schema` via a visual builder
(see `docs/frontend.md` → `FieldSchemaBuilder`). No `auto_pnl_calculator`
is registered for custom strategies; their AUTO mode uses a generic
back/lay calculator:

```
back: stake * (avg_odds - 1) * (1 - commission_pct/100)  (for WIN outcomes)
back: -stake                                              (for LOSS)
lay:  +stake * (1 - commission_pct/100)                   (for WIN — lay side)
lay:  -stake * (avg_odds - 1)                             (for LOSS — lay side)
```

The `position_side` (`back` or `lay`) is part of the universal trade fields
when AUTO mode is used on a custom strategy — surfaces as a toggle in the
trade form alongside an `outcome_label` selector with `WIN`, `LOSS`, `VOID`,
`HALF_WIN`, `HALF_LOSS`. For anything more nuanced, the user uses MANUAL or
CASHOUT_ODDS modes.

#### Permission matrix for custom strategies

| Action | Allowed |
|---|---|
| Create new | Yes (unlimited) |
| Rename `name` | Yes |
| Modify `field_schema` | Yes — but flag a warning if existing trades reference removed fields |
| Hard delete | Yes if no trades reference it; otherwise soft-deactivate |
| Soft-deactivate (`is_active=false`) | Yes |

When a custom strategy's `field_schema` is modified after trades exist, the
server validates that no field removal would orphan data:
- If a field is being removed and at least one existing trade has data for
  that field key, return HTTP 422 with a list of affected trades and a
  suggestion to either keep the field or migrate the data.
- Field additions are always safe.
- Field renames (key change) are treated as remove + add and require explicit
  confirmation via a `?force=true` query param.

## PnL calculator — the three cash-out modes

Implemented in `services/pnl_calculator.py`. Every `trades` INSERT/UPDATE
runs through `compute_pnl(trade)` and writes `computed_pnl_eur` as the
single source of truth.

### Mode AUTO

Strategy-driven. Routes to:
- the `auto_pnl_calculator` of the built-in template if `strategy.kind='builtin'`
- the generic back/lay calculator for custom strategies

Inputs required: `stake_total`, `avg_odds`, `commission_pct`, `outcome_label`,
plus strategy-specific fields validated against `field_schema`.

Betfair commission is APPLIED automatically in AUTO mode.

### Mode MANUAL

User input is the post-everything reality. The system stores it untouched.

```python
computed_pnl_eur = manual_pnl_eur
```

Commission is NOT applied — the user is reporting a real-world outcome
that already accounts for commission, partial cash-outs, edge effects, etc.
Use this for any trade that doesn't fit a clean AUTO scenario.

### Mode CASHOUT_ODDS

System-computed from the cash-out price, mirroring Betfair's cash-out math.

For a back position closed at `cashout_odds`:
```
computed_pnl_eur = stake * (cashout_odds - 1) * (1 - commission_pct/100)
                   if cashout_odds > 1
                   else: stake * (cashout_odds - 1)   # already a loss, no commission earned
```

For a lay position closed at `cashout_odds`:
```
liability = stake * (avg_odds - 1)
payout    = stake * (cashout_odds - 1)   # what you'd pay to lay back at the new odds
computed_pnl_eur = (stake - payout) * (1 - commission_pct/100) if (stake - payout) > 0
                   else: stake - payout
```

The `position_side` is required when this mode is used. For built-in
strategies, the side is implied by the template (Magic CS = back, Draw Hunter
= lay). For custom strategies, the user picks.

## What-if cash-out widget

Interactive tool for evaluating "should I cash out now?" without commitment.

### Where it appears

1. **Inside the trade detail drawer** — a collapsible section below the main
   trade fields, only for trades where `status='OPEN'`. Inputs prefilled from
   the trade.
2. **Standalone `/whatif` page** — accessible from the topbar. Blank state,
   user inputs everything from scratch. Saved calculations land in
   `whatif_scratch` for later review.

### Inputs

- `stake_total` (€)
- `original_odds`
- `position_side` — segmented `back` / `lay`
- `cashout_odds` — slider (range 1.01–10.00, step 0.01) AND number input,
  bidirectionally synced
- `commission_pct` — defaults to 5%, editable

### Outputs (live, debounced 80ms)

- **Locked-in P/L** in EUR — large central number, color-coded by sign
- **Breakeven cashout odds** — the price at which P/L = 0
- **% of full-win realized** — fraction of max profit being locked in
- **Annotated formula display** inline, e.g.
  `€62 × (1.45 − 1) × (1 − 0.05) = +€26.51`

### Visual

A horizontal scale below the central number representing the spectrum from
worst-case loss (left, red zone) to full-win settlement (right, green zone),
with:
- a vertical marker for the user's current `cashout_odds`
- a second vertical marker for breakeven
- the slider sitting on the same scale, so dragging the slider visibly moves
  the marker through the gain/loss continuum

120ms ease transition on slider drag — the central number feels immediate
but smooth.

### Actions

- **Apply** (drawer mode only): closes the open trade with `pnl_mode='CASHOUT_ODDS'`,
  populates `cashout_odds` and `computed_pnl_eur`, sets `status='CLOSED'` and
  `closed_at=now()`. Toast confirmation. Drawer stays open showing the
  closed-trade view.
- **Save snapshot**: appends a markdown line to the trade's `notes_md`, formatted
  `> 28/04 14:32 — what-if @ 1.45 → +€26.51 (51% of max win)`. In standalone
  mode, saves to `whatif_scratch` with an optional `label`.
- **Reset**: returns inputs to their initial values.

### Backend

`POST /api/v1/analytics/whatif-cashout` — stateless. Math identical to
`pnl_calculator.py` CASHOUT_ODDS branch. **Single source of truth** — the
frontend MUST call this endpoint, NEVER duplicate the formula client-side.
This guarantees that what the user sees in the widget exactly matches what
they'd get if they applied it.

### Frontend

`<WhatIfCashOut>` component in `components/whatif/`. Reused in
`TradeDetailDrawer` (passes the open trade as initial values + shows Apply)
and on `/whatif` (blank state, no Apply, just Save snapshot). State managed
with react-hook-form + zod; API calls via TanStack Query mutation with
debouncing. The widget is fully keyboard-navigable: arrow keys nudge the
slider by step, Cmd+Enter applies (in drawer mode), Esc resets.
