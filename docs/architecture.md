# Architecture

Detailed structural reference for SportEdge Pro: full folder layout, complete
data model with column definitions and indices, and the full API surface.
Read this before touching DB schema, models, migrations, or endpoints.

## Repository structure (full)

```
sportedge-pro/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, middleware, router mounting
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings, .env-driven
│   │   │   ├── security.py          # JWT, bcrypt
│   │   │   ├── database.py          # async engine + session factory
│   │   │   └── logging.py           # structlog setup
│   │   ├── models/
│   │   │   ├── base.py              # DeclarativeBase, TimestampMixin
│   │   │   ├── user.py
│   │   │   ├── strategy.py
│   │   │   ├── trade.py
│   │   │   ├── tag.py
│   │   │   ├── bankroll_snapshot.py
│   │   │   └── daily_reflection.py
│   │   ├── schemas/                 # Pydantic v2 input/output models
│   │   │   ├── auth.py
│   │   │   ├── strategy.py
│   │   │   ├── trade.py
│   │   │   ├── tag.py
│   │   │   ├── bankroll.py
│   │   │   ├── analytics.py
│   │   │   └── obsidian.py
│   │   ├── api/
│   │   │   ├── deps.py              # get_current_user, get_db
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py
│   │   │       ├── strategies.py
│   │   │       ├── trades.py
│   │   │       ├── tags.py
│   │   │       ├── bankroll.py
│   │   │       ├── analytics.py
│   │   │       └── obsidian.py
│   │   └── services/
│   │       ├── pnl_calculator.py    # AUTO / MANUAL / CASHOUT_ODDS
│   │       ├── strategy_templates.py # builtin Magic CS + Draw Hunter
│   │       ├── analytics_service.py # Sharpe, drawdown, ROI, scenarios
│   │       ├── monte_carlo.py
│   │       ├── kelly_service.py
│   │       └── obsidian_sync.py     # vault export/import + watcher
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_pnl_calculator.py
│   │   ├── test_analytics_service.py
│   │   ├── test_monte_carlo.py
│   │   ├── test_strategies_api.py
│   │   ├── test_trades_api.py
│   │   ├── test_obsidian_sync.py
│   │   └── fixtures/                # JSON fixtures for known-result tests
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── lib/
│   │   │   ├── api.ts               # fetch client, generated types
│   │   │   ├── auth.ts
│   │   │   ├── format.ts            # currency, percent, odds formatters
│   │   │   └── theme.ts             # dark/light mode toggle
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── TopBar.tsx
│   │   │   │   └── CommandPalette.tsx
│   │   │   ├── primitives/          # design-system level
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── Drawer.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Toggle.tsx
│   │   │   │   ├── Chip.tsx
│   │   │   │   ├── MetricCard.tsx
│   │   │   │   ├── Sparkline.tsx
│   │   │   │   ├── Skeleton.tsx
│   │   │   │   └── Toast.tsx
│   │   │   ├── dashboard/
│   │   │   ├── trades/
│   │   │   │   ├── TradeForm.tsx
│   │   │   │   ├── TradeTable.tsx
│   │   │   │   ├── TradeDetailDrawer.tsx
│   │   │   │   └── CashOutToggle.tsx
│   │   │   ├── strategies/
│   │   │   │   ├── StrategyList.tsx
│   │   │   │   ├── StrategyEditor.tsx
│   │   │   │   ├── DynamicFieldRenderer.tsx
│   │   │   │   └── FieldSchemaBuilder.tsx
│   │   │   ├── analytics/
│   │   │   │   ├── EquityCurve.tsx
│   │   │   │   ├── DrawdownChart.tsx
│   │   │   │   ├── RollingROI.tsx
│   │   │   │   ├── CalendarHeatmap.tsx
│   │   │   │   └── MonteCarloWidget.tsx
│   │   │   ├── notes/
│   │   │   │   ├── MarkdownEditor.tsx
│   │   │   │   └── TagPicker.tsx
│   │   │   └── whatif/
│   │   │       └── WhatIfCashOut.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── TradeLog.tsx
│   │   │   ├── NewTrade.tsx
│   │   │   ├── Strategies.tsx
│   │   │   ├── Analytics.tsx
│   │   │   ├── WhatIf.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/
│   │   ├── stores/
│   │   └── styles/global.css
│   ├── public/
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
└── Caddyfile                        # production reverse proxy
```

## Data model

All models inherit `TimestampMixin` (provides `created_at`, `updated_at` as
`timestamptz` with `now()` defaults).

### `users`

Single user for now, but proper schema. Seed one default from `.env` on
first migration.

| column | type | notes |
|---|---|---|
| id | uuid PK | gen_random_uuid() |
| email | text UNIQUE NOT NULL | |
| password_hash | text NOT NULL | bcrypt |
| created_at | timestamptz | |

### `strategies`

Both built-in templates and user-defined custom strategies live here.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| name | text NOT NULL | display name, editable for both kinds |
| slug | text UNIQUE NOT NULL | derived from name on create |
| kind | enum('builtin', 'custom') | |
| template_key | text NULL | `'magic_cs_v3'` or `'draw_hunter_s4'` for builtins; NULL for custom |
| sport | text DEFAULT 'football' | |
| description | text | |
| color_hex | text | accent color (chips, badges, mini-chart) |
| is_active | boolean DEFAULT true | inactive strategies hidden from trade entry |
| field_schema | jsonb NOT NULL | declares strategy-specific form fields |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Indices**: `UNIQUE (slug)`, `INDEX (kind, is_active)`.

**Constraints**:
- For `kind='builtin'`, `template_key` MUST be non-null and must match a key
  in `services/strategy_templates.py` REGISTRY.
- `field_schema` for builtins is locked (server validates that incoming PATCH
  requests don't modify it for `kind='builtin'`).
- Built-in strategies CANNOT be deleted (HTTP 409). They CAN be deactivated
  (`is_active=false`) and renamed.
- Custom strategies CAN be deleted only if no `trades` reference them;
  otherwise soft-deactivate with a 200 + warning toast.

#### `field_schema` format

JSON document describing dynamic form fields for the trade entry form.

```json
{
  "fields": [
    {
      "key": "selection",
      "label": "Selection",
      "type": "select",
      "options": ["1", "X", "2"],
      "required": true
    },
    {
      "key": "model_prob",
      "label": "Model probability",
      "type": "number",
      "min": 0, "max": 1, "step": 0.001,
      "required": true
    },
    {
      "key": "edge_pct",
      "label": "Edge %",
      "type": "computed",
      "formula": "(model_prob * odds - 1) * 100"
    }
  ]
}
```

Supported `type` values: `text` · `number` · `select` · `multiselect` ·
`boolean` · `chip-picker` · `computed` (read-only, derived via `formula`
expression that can reference any other field key plus the universal
`stake_total` and `avg_odds`).

### `trades`

The core table. Universal columns + JSONB for strategy-specific data.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| strategy_id | uuid FK → strategies.id | ON DELETE RESTRICT |
| sport | text DEFAULT 'football' | future-proofing |
| home_team | text NOT NULL | |
| away_team | text NOT NULL | |
| league | text NOT NULL | |
| kickoff_at | timestamptz NOT NULL | |
| ht_score_home | int NULL | |
| ht_score_away | int NULL | |
| ft_score_home | int NULL | |
| ft_score_away | int NULL | |
| stake_total | numeric(10,2) NOT NULL | |
| avg_odds | numeric(6,2) NOT NULL | |
| commission_pct | numeric(4,2) DEFAULT 5.00 | |
| pnl_mode | enum('AUTO','MANUAL','CASHOUT_ODDS') NOT NULL | |
| cashout_odds | numeric(6,2) NULL | only when mode=CASHOUT_ODDS |
| manual_pnl_eur | numeric(10,2) NULL | only when mode=MANUAL |
| computed_pnl_eur | numeric(10,2) NOT NULL | always: source of truth |
| outcome_label | text NULL | e.g. `A2_OVER25`, `WIN`, `void`, `cashout` |
| status | enum('OPEN','CLOSED','VOID') DEFAULT 'OPEN' | |
| strategy_data | jsonb NOT NULL DEFAULT '{}' | validated against field_schema |
| notes_md | text NULL | markdown-formatted |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| closed_at | timestamptz NULL | set when status transitions to CLOSED |

**Indices**:
- `INDEX (kickoff_at DESC)` — main timeline scan
- `INDEX (strategy_id, kickoff_at DESC)` — per-strategy listing
- `INDEX (status) WHERE status = 'OPEN'` — partial index for live trades
- `GIN (strategy_data)` — for filtering/aggregating on strategy-specific keys
- `GIN (to_tsvector('simple', home_team || ' ' || away_team || ' ' || coalesce(notes_md, '')))` — full-text search

**Critical invariant**: `computed_pnl_eur` is ALWAYS the source of truth for
analytics, regardless of `pnl_mode`. The PnL calculator service derives it
from the relevant inputs on every INSERT/UPDATE — see `docs/strategies.md`
for the three modes.

### `tags` and `trade_tags`

Many-to-many.

```sql
tags (
  id uuid PK,
  name text UNIQUE NOT NULL,
  color_hex text,
  created_at timestamptz
)

trade_tags (
  trade_id uuid REFERENCES trades(id) ON DELETE CASCADE,
  tag_id   uuid REFERENCES tags(id)   ON DELETE CASCADE,
  PRIMARY KEY (trade_id, tag_id)
)
```

### `bankroll_snapshots`

Periodic snapshots powering the equity curve. Auto-created daily at 23:59
local time via an apscheduler-style background task.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| taken_at | timestamptz NOT NULL | |
| balance_eur | numeric(12,2) NOT NULL | |
| deposit_eur | numeric(10,2) DEFAULT 0 | manual top-ups |
| withdrawal_eur | numeric(10,2) DEFAULT 0 | |
| notes | text NULL | |

**Indices**: `INDEX (taken_at DESC)`.

### `daily_reflections`

User-written daily reflections, surfaced in the daily Obsidian note.

| column | type |
|---|---|
| id | uuid PK |
| date | date UNIQUE NOT NULL |
| reflection_md | text |
| updated_at | timestamptz |

### `whatif_scratch`

Stand-alone what-if cash-out calculations not tied to a trade.

| column | type |
|---|---|
| id | uuid PK |
| inputs_json | jsonb NOT NULL |
| outputs_json | jsonb NOT NULL |
| label | text NULL |
| created_at | timestamptz |

## API surface

All endpoints under `/api/v1`. JSON in/out. JWT bearer auth except `/auth/login`.
Errors as RFC 9457 problem-details.

### Auth

```
POST   /auth/login                  body: {email, password}
                                     -> {access_token, token_type: "bearer", expires_in}
POST   /auth/refresh                 -> new access_token
GET    /auth/me                      -> current user info
```

### Strategies

```
GET    /strategies                   ?include_inactive=false
                                     -> [{id, name, slug, kind, color_hex, is_active, field_schema, ...}]
POST   /strategies                   body: {name, color_hex, description, field_schema}
                                     -> created strategy (kind='custom' enforced)
GET    /strategies/{id}
PATCH  /strategies/{id}              body: partial update; field_schema only mutable for kind='custom'
DELETE /strategies/{id}              hard delete only if kind='custom' AND no trades reference;
                                     otherwise 200 + soft-deactivate + warning in payload
```

### Trades

```
GET    /trades                       query params:
                                       strategy_id, league, status, outcome_label,
                                       date_from, date_to, tags[], pnl_min, pnl_max,
                                       q (full-text), sort, page, page_size
                                     -> {items, total, page, page_size, aggregates: {sum_pnl, count, roi}}
POST   /trades                       full trade body, validates strategy_data against
                                     strategies.field_schema, computes pnl
GET    /trades/{id}                  -> trade with embedded strategy + tags
PATCH  /trades/{id}                  any field; recomputes pnl on pnl-affecting change
DELETE /trades/{id}                  hard delete
POST   /trades/{id}/close            body: {pnl_mode, ...mode-specific fields, outcome_label}
                                     shortcut to set status=CLOSED with PnL payload
POST   /trades/{id}/tags             body: {tag_id} or {name} (creates tag if missing)
DELETE /trades/{id}/tags/{tag_id}
```

### Tags

```
GET    /tags                         -> list with usage counts
POST   /tags                         body: {name, color_hex}
PATCH  /tags/{id}
DELETE /tags/{id}
```

### Bankroll

```
GET    /bankroll/current             -> {balance, last_snapshot_at, since_inception_pnl, since_inception_roi}
GET    /bankroll/series              ?range=7d|30d|90d|all
                                     -> [{taken_at, balance, day_pnl}, ...]
POST   /bankroll/adjust              body: {amount_eur, kind: 'deposit'|'withdrawal', notes}
POST   /bankroll/snapshot            forces a snapshot now
```

### Analytics

All endpoints respect the same filter params as `/trades` so a "filtered view"
in the UI shares one query shape.

```
GET    /analytics/summary            -> {bankroll, pnl_total, roi_pct, win_rate, sharpe, max_dd, n_trades}
GET    /analytics/by-strategy        -> per-strategy breakdown
GET    /analytics/by-league
GET    /analytics/by-outcome         -> for Magic CS scenarios etc.
GET    /analytics/rolling            ?window=20 -> [{idx, roi, win_rate}]
GET    /analytics/drawdown           -> {series, max_dd, max_dd_started_at, max_dd_ended_at}
GET    /analytics/calendar           -> 7×24 grid of P/L sums + trade counts
POST   /analytics/monte-carlo        body: {starting_bankroll, n_simulations, horizon_trades, ruin_threshold_pct}
                                     -> {risk_of_ruin, p10, p50, p90, distribution: [{bucket_low, bucket_high, count}]}
POST   /analytics/whatif-cashout     body: {stake_total, original_odds, position_side, cashout_odds, commission_pct}
                                     -> {locked_in_pnl, breakeven_odds, pct_of_max_win, formula_text}
```

### Obsidian

```
GET    /obsidian/status              -> {enabled, mode, vault_path, last_sync_at, errors: [...]}
PATCH  /obsidian/config              body: partial settings
POST   /obsidian/export-all          -> {trades_exported, daily_exported, strategies_exported, took_ms}
POST   /obsidian/sync-now            triggers a one-shot import-changes pass
GET    /obsidian/conflicts           -> [{path, trade_id, detected_at, preview}]
POST   /obsidian/conflicts/{id}/resolve
                                     body: {resolution: 'keep_db'|'keep_file'|'manual_merged_text'}
```

## Configuration via `.env`

All settings flow through `pydantic-settings` (`core/config.py`). The
`.env.example` enumerates every required variable with safe defaults.

```
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=sportedge
POSTGRES_USER=sportedge
POSTGRES_PASSWORD=<generate-strong-secret>

# Auth
JWT_SECRET_KEY=<openssl rand -hex 48>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_TTL_MINUTES=120
JWT_REFRESH_TOKEN_TTL_DAYS=14

# Default user (seeded on first migration)
DEFAULT_USER_EMAIL=you@domain.tld
DEFAULT_USER_PASSWORD=<change-on-first-login>
DEFAULT_STARTING_BANKROLL=1000.00

# Betfair
BETFAIR_DEFAULT_COMMISSION_PCT=5.00

# Obsidian
OBSIDIAN_DEFAULT_VAULT=/vault
OBSIDIAN_VAULT_PATH=./obsidian-vault    # host path mounted to /vault

# Frontend
VITE_API_BASE_URL=/api/v1
```

## Migrations

Single Alembic environment under `backend/alembic/`. Each migration must
implement both `upgrade()` and `downgrade()`. Seed data (default user,
built-in strategies) lives in a dedicated post-init migration that's
idempotent.
