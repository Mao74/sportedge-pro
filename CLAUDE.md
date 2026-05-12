# SportEdge Pro — project memory

Production-grade, full-stack sports trading journal for a single professional
Betfair Exchange trader. Replaces an earlier prototype called "SportEdge Journal".
Football only; tennis is out of scope but the schema is sport-agnostic so it
can be added later without breaking changes.

This file is read at the start of every Claude Code session. Keep it concise.
Detailed specs live in `docs/`. Update the **Status** section after every
completed step.

## Status

- Phase: ✅ all 15 steps complete (2026-04-29). Project shipped + post-ship
  polish sprint (Settings + market_type + CSV + CI + watcher + conflicts).
- Post-ship sprint 2 (started ~2026-05-02): Settings page completa
  (Bankroll panel: balance + deposit/withdrawal + ultimi 10 snapshot;
  Preferences panel: theme picker dark/light esplicito, default
  market_type picker exchange/classic, venue dropdown generalizzato
  (Betfair/Smarkets/Matchbook/BetDAQ/Snai/Bet365/Sisal/Lottomatica/
  Eurobet/Goldbet/Other) con autosuggest commission per venue, default
  commission editable). Backend: migration 0005 (`default_commission_pct`
  + `betting_exchange`) + migration 0006 (`trade.market_type` enum
  exchange|classic + `app_settings.default_market_type`). PnL calculator
  rispetta market_type → `commission_factor=1.0` per classic in AUTO e
  CASHOUT_ODDS (MANUAL irrilevante). PnLInputs + TradeBase + TradeUpdate
  + WhatIfCashoutRequest + Obsidian frontmatter aggiornati. NewTrade
  form + CashOutToggle + WhatIf standalone tutti con segmented
  Exchange/Classic e commission disabled quando classic. Sweep dei
  riferimenti residui "Magic CS v3" / "draw_hunter S4" nel codice
  corrente + docs (mantenuti solo in ADR, migration 0004, log CLAUDE.md).
  Salvate 2 memory: feedback naming + project Settings TODOs.

  **CSV import/export**: `app/services/csv_io.py` round-trip simmetrico
  (24 colonne, header strict, tags pipe-separated, strategy_data JSON);
  `GET /api/v1/trades/export.csv` streama l'intera history; `POST /api/v1/
  trades/import` multipart con flag `dry_run` (default true → preview
  con counts + errors per riga, no DB write; false → commit).
  Strategy resolution per slug, tags find-or-create, PnL ricomputato dal
  calcolatore (ignora `computed_pnl_eur` del CSV — non si fida). Errori
  per riga indipendenti: bad row → skip, good rows → insert. Frontend
  `DataIoPanel` su /settings con drag&drop + auto-preview + Commit button.
  9 test (export empty/with-trade + import dry-run/commit/classic
  recompute/unknown-slug/missing-column/round-trip).

  **CI GitHub Actions** `.github/workflows/ci.yml`: backend job
  (Postgres 16 sidecar, alembic upgrade, pytest + ruff), frontend job
  (typecheck + Vite build), concurrency cancel-superseded. Repo target
  `Mao74/sportedge-pro` (da creare). `.github/workflows/README.md` con
  istruzioni first-push.

  **Conflicts drawer**: `components/obsidian/ConflictsDrawer.tsx` con
  lista conflitti (path + detected_at + side-by-side DB/file diff
  preview), 3 risoluzioni (Keep DB / Keep file / Merge…), Merge apre
  modal con MarkdownEditor pre-popolato dal file_text. UI state via
  `useUiStore.conflictsOpen`. `ObsidianStatusBadge` apre il drawer
  invece di linkare a /settings quando conflict_count > 0; il panel
  Obsidian su /settings ha link "resolve" sul conteggio.

  **Live watcher**: `app/services/obsidian/watcher.py` con `watchfiles.
  awatch` + helper `is_drvfs_path` per detect WSL2/DrvFs → polling
  fallback (`force_polling=True`, `poll_delay_ms` configurabile via
  `OBSIDIAN_WATCH_POLL_INTERVAL` env). Debounce 500ms per coalescare
  burst di salvataggi. Gated on `obsidian_enabled` + `sync_mode=
  'two_way'`. Spawned dalla lifespan come terzo bg task. 3 unit test
  per `is_drvfs_path`. **Limite noto**: cambi runtime di sync_mode non
  riciclano il watcher (richiede restart del backend).

  **Lighthouse helper**: `scripts/lighthouse.md` con setup + comandi
  + target ≥90; `index.html` ha ora `lang=it`, `<meta name=description>`,
  `<meta name=theme-color>` per dark/light, `<noscript>` fallback.

  **Prod dry-run**: `scripts/prod-dryrun.md` con walkthrough completo
  (`docker compose -f docker-compose.prod.yml` + .env.prod + smoke
  curl) per validare le immagini production prima del deploy VPS reale
  (deferito — niente dominio Hostinger pubblico assegnato ancora).

  Tests previsti totali ~243 (era 214 prima della sprint, +29):
  +6 PnL classic, +3 preferences, +3 trade market_type, +9 CSV, +3
  drvfs helper, +5 test misc già esistenti aggiornati con MarketType
  fixtures. Type-check frontend pulito (verifica Docker pendente).

- Post-ship change: 2026-04-29 — built-in strategies renamed and made
  deletable. New defaults: `Magic CS v3` → **Magic CS** (slug `magic-cs`),
  `draw_hunter S4` → **Draw Hunter** (slug `draw-hunter`). `template_key`
  preserved (`magic_cs_v3` / `draw_hunter_s4`) so the seed registry still
  identifies the rows. Migration `0004_rename_builtins` updates existing
  seeded rows in place — only when name+slug still match the previous
  defaults so user-renamed instances are left alone. `delete_strategy`
  no longer returns 409 for `kind=builtin`; both kinds use the same
  delete-or-soft-deactivate logic. Once a built-in is deleted, the seed
  migration's `ON CONFLICT (slug)` won't recreate it on re-deploy
  (deletion sticks). Test `test_cannot_delete_builtin` replaced by
  `test_can_delete_builtin_when_no_trades` and
  `test_delete_builtin_with_trades_soft_deactivates`. **214/214 backend
  tests green.**
- Last meaningful change: 2026-04-29 — step 15 (Deployment artifacts)
  complete. Production multi-stage Dockerfiles for backend and frontend.
  Backend `Dockerfile.prod`: stage-1 builds wheels for runtime-only
  dependencies (no dev/test extras), stage-2 runs as non-root user
  `sportedge` (uid 10001), `tini` as PID 1, `entrypoint.sh` runs
  `alembic upgrade head` before exec'ing uvicorn (`--workers 2
  --proxy-headers`). HEALTHCHECK against /api/v1/health.
  Frontend `Dockerfile.prod`: stage-1 Vite build with
  `VITE_API_BASE_URL` build arg, stage-2 Caddy 2-alpine serves the
  static bundle with SPA `try_files` fallback, gzip+zstd compression,
  immutable `Cache-Control` on hashed `/assets/*`, no-cache on
  index.html, security headers (X-Content-Type-Options, X-Frame-Options
  DENY, Referrer-Policy, Permissions-Policy), `auto_https off` since
  TLS terminates upstream at NPM, `/api/*` reverse-proxied to backend
  inside the docker network. `docker-compose.prod.yml`: postgres has
  no published port (network-internal), backend has no published port,
  frontend binds to `127.0.0.1:${FRONTEND_PROXY_PORT:-8080}` so NPM
  forwards to it without colliding with other VPS apps. Restart
  policy `unless-stopped` on every service, healthchecks, log
  rotation 10MB×5 files. `.env.prod.example` with required-or-error
  semantics (`?POSTGRES_PASSWORD is required`). README walkthrough
  covers VPS setup, NPM proxy host config (subdomain + LE cert), and
  pg_dump nightly backup recipe. `compose config` validates clean.

  Previous: step 14b (Obsidian integration)
- Last meaningful change: 2026-04-28 — step 14b (Obsidian integration)
  complete in **export_only + manual sync-now** form (live watcher
  deferred per docs' "soft start" guidance). Migration `0003` adds
  `app_settings` (single-row), `obsidian_conflicts`, and
  `trades.last_obsidian_sync_at`. Templates in
  `app/services/obsidian/templates.py` render trade.md, daily.md,
  strategy.md, Dashboards/Bankroll.md, README — every file with a
  YAML frontmatter (`app_managed: true`) and a `USER_EDITABLE_START/
  END` marker block whose content is preserved across re-exports via
  `extract_user_editable`. `ObsidianSyncService` (export_trade,
  export_daily, export_strategy, export_dashboards, export_all,
  import_changes) atomically writes via tmp+replace and surfaces
  conflicts to `_meta/_conflicts/{trade_id}-{ts}.md` plus an
  `obsidian_conflicts` row when the DB updated_at is newer than the
  file's frontmatter `last_synced_at`. Trade POST/PATCH/close/delete
  enqueue an async re-export via `services/obsidian/queue.py`; a
  single background worker drains the queue (started by lifespan
  alongside the daily-snapshot scheduler). Endpoints:
  GET /obsidian/status, PATCH /obsidian/config, POST /obsidian/export-all,
  POST /obsidian/sync-now, GET /obsidian/conflicts,
  POST /obsidian/conflicts/{id}/resolve. Frontend: `/settings` page
  rewritten with full Obsidian panel (toggle, vault path, sync mode
  picker, Export now / Sync now buttons, last sync + conflict count
  + last error display), `ObsidianStatusBadge` in TopBar (green/yellow/
  red dot, refetch every 30s, links to /settings).
  docker-compose mounts `${OBSIDIAN_VAULT_PATH:-./obsidian-vault}:/vault`.
  **213/213 backend tests green** (added 19): renderer goldens for
  trade/daily/strategy/dashboard/README, frontmatter parses, USER_EDITABLE
  preservation across re-export, full export-all writes the expected
  files, sync-now round-trips a hand-edit back into trades.notes_md,
  export_only mode rejects sync-now with 400.
  **Known limitation**: live watcher (auto-import on file change) is
  deferred — manual "Sync now" button is the trigger. Adding
  `watchfiles`-based polling fallback for DrvFs is a follow-up.

  Previous: step 14a (Polish pass)
- Last meaningful change: 2026-04-28 — step 14a (Polish pass) complete.
  Added `EmptyState` primitive (icon + title + body + action) and
  threaded it into the trade-log empty path (replaces the inline copy).
  Added `ErrorBoundary` class wrapping the page outlet with a friendly
  retry/reload card; route `*` now hits a real `NotFound` page (was a
  silent redirect). `OfflineBanner` (yellow, sticky, top of main) +
  `useOnlineStatus` hook listening to window online/offline events.
  Skip-link "Skip to content" appears on focus and jumps to a focusable
  `<main id="main-content">`. Toast region gets `role=region`, an
  `aria-label`, and `aria-live=polite`. `usePatchTrade` is now optimistic:
  it cancels in-flight queries, snapshots the cached trade, applies the
  patch immediately, rolls back on error and writes the server response
  on success (so backend-recomputed `computed_pnl_eur` always wins).
  Calendar drill-through is wired end-to-end: backend `_filters` and
  the `/trades` endpoint accept `kickoff_dow` (0=Mon..6=Sun, mapped from
  PG `isodow - 1`) and `kickoff_hour` (0..23); frontend
  `useTradeFilters` parses & writes them; `FilterBar` renders Day/Hour
  chips; `CalendarHeatmap` cells navigate to `/trades?kickoff_dow=N&
  kickoff_hour=M` and the table shrinks to that exact slot. Backend
  test `test_filter_by_kickoff_dow_and_hour` proves Tuesday 14:00 cell
  isolates exactly one trade from a 3-trade fixture; out-of-range
  values rejected 422. **194/194 backend tests green** (added 1 from 193).

  Previous: step 13 (Analytics page)
- Last meaningful change: 2026-04-28 — step 13 (Analytics page) complete.
  `/analytics` renders 5 tabs: Overview (4 metric cards + Rolling line +
  By-strategy card), Drawdown (3 callout cards + underwater area chart
  with red gradient), Monte Carlo (param inputs left + risk-of-ruin
  callout + P10/P50/P90/Mean + ending-bankroll histogram with reference
  line at starting bankroll; runs the simulation with manual button +
  shows took_ms), Calendar (7×24 dow×hour heatmap with intensity-scaled
  green/red cells, hover tooltip, click cells), Per-strategy (table
  with color dot + ROI/win-rate, plus by-league and by-outcome tables;
  rows link to /trades?strategy_id= or ?league= for drill-down).
  Standalone `/whatif` page added: stake / original odds / cashout
  odds (with slider) / position side / commission, live preview of
  locked-in P/L via /analytics/whatif-cashout (debounced 80ms);
  formula text + breakeven + % of max win shown. Recharts tooltips
  typed via `payload?: readonly { payload?: ... }[]` to satisfy
  Recharts' ContentType signature with TS strict.

  Previous: step 12 (Strategies page)
- Last meaningful change: 2026-04-28 — step 12 (Strategies page) complete.
  `/strategies` lists builtins and customs in two sections, each card
  showing color dot, name, kind chip, slug, field count, and quick
  actions: toggle is_active (Eye/EyeOff), open editor, delete (custom
  only). "Show inactive" switch + "New strategy" modal (asks name +
  accent color, redirects to the editor). `/strategies/:id` is the
  editor: metadata card (name/color/description) + FieldSchemaBuilder
  (drag-reorder via dnd-kit, type picker for text/number/select/
  multiselect/boolean/chip-picker/computed, type-specific options
  inline — options list, min/max/step, min_picks/max_picks, formula,
  depends_on key, required, required_for_status), all driven by the
  same shape `DynamicFieldRenderer` reads — preview pane on the right
  shows the live trade-form rendering. Built-in strategies show the
  schema as locked (Lock chip, all controls disabled, no add/remove/
  drag). Save handler shows a soft warning on field-removal 422 with
  affected_trade_ids count. Verified end-to-end: create custom →
  patch field_schema → delete (no trades) all return 2xx. New deps:
  @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities.

  Previous: step 11 (Trade log page)
- Last meaningful change: 2026-04-28 — step 11 (Trade log page)
  complete. `/trades` renders the full filterable, virtualized log:
  FilterBar with debounced search (200ms), expandable filter row
  (strategy/status/pnl_mode/league/outcome/date range/pnl range),
  removable filter chips, URL-synced state via useTradeFilters
  (filtered views are sharable links). TradeTable on TanStack Table
  + react-virtual: sticky header with sort toggles, 56px row height,
  keyboard-focused-row indicator (ring), 70vh max scroll, virtualizes
  >1000 rows. TradeDetailDrawer: 480px right-side, tabs Overview /
  Notes / History; inline-edit on Overview (Edit toggles fields to
  inputs; blur saves) for stake, odds, HT/FT scores; Notes tab embeds
  MarkdownEditor; History lists created/updated/closed timestamps;
  footer has close-trade / reopen / delete with confirm. Keyboard
  nav: j/k navigate rows, Enter/e open focused, n creates new trade.
  Footer aggregates (n_closed, sum P/L, stake, ROI%, win-rate%) on
  the filtered set; pagination prev/next with page-of-N. New deps:
  @tanstack/react-table, @tanstack/react-virtual.

  Previous: step 10 (Trade entry page)
  complete. `/trades/new` renders the full form: strategy selector tabs
  (chip-style, kind label), Match card (home/away/league/kickoff),
  Stake & odds card, dynamic strategy-specific fields card via
  `DynamicFieldRenderer` (supports text/number/select/multiselect/
  boolean/chip-picker/computed; honours depends_on), CashOutToggle
  (3-state: No cashout / Manual P/L / From cashout odds; live preview
  from /analytics/whatif-cashout debounced 80ms; switching cashout→manual
  lifts the locked-in P/L into the manual input), MarkdownEditor
  (Edit/Preview tabs via react-markdown + remark-gfm), TagPicker
  (typeahead with usage counts + create-on-the-fly via Enter, X-remove
  + Backspace). Auto-save draft to localStorage every 5s, restored on
  next visit; "Clear draft" wipes. Submission via TanStack mutation
  invalidates queries and toasts. Pre-submit validates stake>0,
  odds≥1.01, mode-specific required fields. All three PnL modes
  verified round-trip with hand-computed values (AUTO/back/WIN €142.50,
  MANUAL €42.50, CASHOUT_ODDS €26.50). New deps: react-markdown,
  remark-gfm.

  Previous: step 9 (Dashboard page) complete.
  `/` now renders the live dashboard: 4 hero metric cards (Bankroll,
  Total P/L, ROI, Win rate) with first-mount count-up animation
  (easeOutQuart 600ms) + tiny sparklines from the daily series. Big
  equity-curve card with Recharts AreaChart (gradient fill, no stroke
  gradient per CSS rule), thin axes 1px 10% opacity, JetBrains Mono
  axis labels, brush zoom (only when ≥12 points), hover crosshair
  tooltip showing date + balance + day P/L; range selector
  (7d/30d/90d/All) via Segmented. Two-column row: open trades card
  (live pulse-dot animation, click→ /trades?focus=...) and by-strategy
  breakdown card with diverging RoiBar centered at 0. All data via
  TanStack Query hooks in `src/queries/dashboard.ts`. Skeleton
  loaders matched to final layout. Recharts dep added.

  Previous: step 8 (Frontend foundation)
  complete. React 18 + TS strict + Vite + Tailwind v3.4 + TanStack Query +
  Zustand + react-router + framer-motion + cmdk + lucide. Auth flow: Login
  page (POST /auth/login → token pair → /auth/me → Zustand persist),
  ProtectedRoute redirects to /login on missing token. Layout: Sidebar
  (collapsible Cmd/Ctrl+B, persisted), TopBar (breadcrumb + Cmd+K
  trigger + New trade), AppShell composes both. Command palette
  (Cmd/Ctrl+K) with navigation, theme toggle, sidebar toggle, sign-out.
  Primitives library: Button (4 variants × 4 sizes), Card, Input, Segmented,
  Switch, Chip (6 tones, dismissible), MetricCard (label + big number +
  delta + sparkline), Sparkline, Skeleton, Toast (provider + useToast,
  bottom-right stacked, swipe-equivalent dismiss), Drawer (480px,
  framer-motion 240ms spring-out, Esc to close), Modal (centered, backdrop
  blur). Demo route at `/_dev/primitives` showcases all primitives in
  the active theme. Theme toggle (sidebar bottom + palette) persists.
  Routes wired: /login, /, /trades, /trades/new, /strategies, /analytics,
  /whatif, /settings — all placeholder pages except dashboard which
  shows live bankroll + health from backend. Default user (.env
  DEFAULT_USER_EMAIL/PASSWORD) authenticates end-to-end.

  Previous: step 7 (Bankroll + Analytics API)
  complete. `app/services/bankroll_service.py` derives current bankroll
  from `default_starting_bankroll + sum(deposits) - sum(withdrawals) +
  sum(closed_pnl)`; daily series buckets closed trades by day and exposes
  `7d/30d/90d/all` ranges. Bankroll API: `/current`, `/series?range=`,
  `/adjust` (deposit/withdrawal as a snapshot row), `/snapshot` (manual
  trigger). `app/services/scheduler.py` runs an asyncio task spawned by
  the FastAPI lifespan that takes a daily auto-snapshot at 23:59 UTC;
  scheduler is gated by `enable_scheduler` and `app_env != "test"`.
  Analytics API: `/summary`, `/by-{strategy,league,outcome}`, `/rolling`,
  `/drawdown`, `/calendar`, `/monte-carlo` (POST, 200-trade horizon
  budget), and stateless `/whatif-cashout` that delegates to the same
  pnl_calculator the trades API uses. Shared `app/api/_filters.py` builds
  the same WHERE clauses for `/trades` and `/analytics/*`. Added
  `closed_at` as an optional explicit field on `TradeCreate` so users
  can journal historical trades with the right closure date.
  **193/193 backend tests green · coverage 85%** (services 94-100%,
  schemas 94-100%, models 96-100%; API router % artificially low due
  to async/greenlet coverage tracker quirk but covered functionally).

## Tech stack

- **Backend**: Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Alembic ·
  Pydantic v2 · python-jose · asyncpg · structlog · watchfiles
- **Database**: PostgreSQL 16
- **Frontend**: React 18 · TypeScript strict · Vite · Tailwind v3.4 ·
  Framer Motion · TanStack Query v5 · TanStack Table v8 · Zustand ·
  react-hook-form + zod · Recharts · Lucide icons
- **Testing**: pytest + pytest-asyncio + httpx (backend) · Vitest +
  Testing Library (frontend)
- **Deployment**: Docker Compose (backend, postgres, frontend served by
  Caddy). Target: self-hosted Hostinger VPS, exposed via Nginx Proxy Manager
  on the host alongside other Docker apps.

## Top-level folder layout

```
sportedge-pro/
├── CLAUDE.md                 # this file
├── docs/                     # detailed specs, read on demand
│   ├── architecture.md
│   ├── strategies.md
│   ├── frontend.md
│   ├── obsidian.md
│   └── implementation-plan.md
├── wireframes/               # 4 reference PNGs (structural only)
├── backend/
├── frontend/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
└── README.md                 # human setup guide, generated last
```

## Documentation index — read on demand

| File | When to read |
|---|---|
| `docs/architecture.md` | Before touching DB, models, migrations, or API endpoints |
| `docs/strategies.md` | Before working on strategies, PnL calculator, or what-if widget |
| `docs/frontend.md` | Before any frontend work — contains the **visual language** |
| `docs/obsidian.md` | Before working on Obsidian integration (step 14b) |
| `docs/implementation-plan.md` | At the start of every session — confirms current step |
| `docs/adr/0002-journal-not-backtester.md` | Defines the PnL philosophy — the calculator is strategy-agnostic; ADR-0001 is SUPERSEDED |

## Wireframes

Not provided. The visual language is fully specified in `docs/frontend.md` —
follow it precisely. Pay extra attention to the palette, typography scale,
spacing system, and per-component specifications since there is no visual
reference to lean on.

## Universal code conventions

### Python

- Type hints on every function signature. No bare `Any` without justification.
- Pydantic v2 syntax everywhere (`model_config`, not `class Config`).
- All money values are `Decimal`, never `float`. Serialized to JSON as strings
  to preserve precision.
- All SQL via SQLAlchemy ORM, parameterized. Never string-interpolate user data.
- Async everywhere — `async def`, `AsyncSession`, `asyncpg`. No sync DB calls
  in request paths.
- Logging via structlog. No `print` statements in committed code.
- Errors: return RFC 9457 problem-details JSON for all 4xx/5xx responses.
- Tests: pytest, fixtures over factory mocks, golden-file snapshots for
  template renderers.

### TypeScript

- `strict: true` in tsconfig. No `any`. No `// @ts-ignore` without an
  inline comment explaining why.
- API types generated from the backend OpenAPI schema via `openapi-typescript`
  — never hand-write request/response shapes.
- Forms via react-hook-form + zod. Schemas live next to the component.
- Server state via TanStack Query. Client state via Zustand. Don't mix.
- No `console.log` in committed code.

### Money and rounding

- Stakes: 2 decimal places
- Odds: 2 decimal places
- Percentages: 1 decimal place in display, full precision internally
- EUR values: 2 decimal places, formatted via `Intl.NumberFormat('it-IT')`
- Betfair commission default: 5%, overridable per trade

### Naming

- Python: `snake_case` for functions/variables/modules · `PascalCase` for
  classes · `UPPER_SNAKE` for constants
- TypeScript: `camelCase` for functions/variables · `PascalCase` for
  components and types · hooks `useFoo` · stores `useFooStore`
- Files: kebab-case for assets, PascalCase for React components,
  snake_case for Python modules
- DB tables: plural snake_case (`trades`, `bankroll_snapshots`)

## Quality bar (non-negotiable)

- Backend test coverage ≥85% line
- Frontend test coverage ≥70% on critical paths (forms, calculators, table)
- Lighthouse on dashboard page ≥90 for performance, a11y, best-practices
- All API endpoints documented in OpenAPI (auto from FastAPI)
- All migrations idempotent with both `up` and `down` implemented
- Responsive: full at 1280px desktop · graceful at 1024px tablet ·
  read-mostly at <768px mobile

## Out of scope (do NOT build)

- Tennis or any non-football sport (schema is ready, but no UI)
- Multi-user auth, roles, sharing
- Live betting feed integration / Betfair API auto-sync
- Email or push notifications
- Mobile native app
- Audit log / change history (single-user, not needed)
- Custom Obsidian plugin (filesystem-based integration only)

## Working agreement with Claude Code

- Implementation is sequential — see `docs/implementation-plan.md`. Confirm
  with the user before moving to the next step.
- After each step: run the relevant tests, then update the **Status** section
  at the top of this file with the new current step and date.
- When making a non-trivial architectural choice not covered in the docs,
  add an ADR (Architecture Decision Record) under `docs/adr/` with a
  zero-padded number, and link it from the documentation index above.
- If the user asks for something that contradicts these conventions, flag
  it explicitly and ask before proceeding.
- Do not silently install dependencies the user hasn't approved. Propose
  the addition with a one-line rationale and wait for the OK.
