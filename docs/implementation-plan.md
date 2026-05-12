# Implementation plan

Sequential build plan. Confirm with the user before moving to each next step.
After every step, update the **Status** section in `CLAUDE.md` and run all
relevant tests.

## The 15 steps

### 1. Bootstrap

Set up the monorepo structure and Docker Compose. Get a hello-world FastAPI
backend talking to Postgres, and a Vite frontend with Tailwind v3.4 and the
dark theme tokens already wired into `global.css`. README with `docker compose
up` instructions.

**Done when**: `docker compose up` brings up all three services, `localhost`
shows the frontend with the dark theme applied, `/api/v1/health` returns 200.

### 2. DB schema and migrations

Implement all SQLAlchemy models from `docs/architecture.md`. Generate the
initial Alembic migration. Add the seed migration (default user from `.env`,
both built-in strategy templates with their full `field_schema`). Verify
migration `up` and `down` both run cleanly.

**Done when**: fresh DB → `alembic upgrade head` → all tables exist with
correct columns and indices, default user can authenticate, both built-in
strategies present and queryable.

### 3. PnL calculator service

Implement `services/pnl_calculator.py` with all three modes (AUTO with the
Magic CS scenarios + Draw Hunter outcomes + custom generic, MANUAL,
CASHOUT_ODDS). Comprehensive pytest suite with known fixtures — at least
one test per scenario in Magic CS, both back and lay paths in CASHOUT_ODDS.

Note: superseded by ADR-0002 — the PnL calculator is now strategy-agnostic
(journal, not backtester). Scenario labels live as free-form tags.

**Done when**: `pytest tests/test_pnl_calculator.py` passes with ≥95% line
coverage on the calculator.

### 4. Analytics service

Implement `services/analytics_service.py` (total_pnl, roi, win_rate, sharpe,
max_drawdown, rolling_roi, scenario_breakdown, league_breakdown,
calendar_grid) and `services/monte_carlo.py`. Unit tests using deterministic
fixtures of seeded trades.

**Done when**: `pytest tests/test_analytics_service.py tests/test_monte_carlo.py`
passes; results match hand-computed expectations on the fixture set.

### 5. Auth + strategies API

JWT login flow (`/auth/login`, `/auth/refresh`, `/auth/me`). Strategies CRUD
(`/strategies` GET/POST/PATCH/DELETE) with full `field_schema` validation
and the permission matrix from `docs/strategies.md`. OpenAPI docs auto-generated.

**Done when**: integration tests cover login, list strategies (built-ins
returned), create custom, attempted delete of built-in returns 409, attempted
field_schema modification of built-in returns 403, attempted breaking change
to a custom field_schema with existing trades returns 422.

### 6. Trades API

Full CRUD plus `/trades/{id}/close` shortcut, `/trades/{id}/tags` add/remove.
Validate `strategy_data` against the strategy's `field_schema` on every write.
PnL recompute on every PnL-affecting change. Filtering on all parameters
listed in `docs/architecture.md`. Pagination with aggregates in the response.

**Done when**: integration tests cover all three PnL modes round-tripped
(create → fetch → assert `computed_pnl_eur` matches expected), filtering
works on every parameter, pagination respects `page`/`page_size`.

### 7. Bankroll + analytics API

`/bankroll/*` endpoints, including the manual adjust and snapshot triggers.
Background task that creates a snapshot every day at 23:59 (apscheduler
or similar lightweight in-process scheduler). All `/analytics/*` endpoints
including `/analytics/whatif-cashout` and `/analytics/monte-carlo`.

**Done when**: snapshot scheduling verified, equity curve series endpoint
returns the expected shape, Monte Carlo endpoint completes 10k simulations
in <2s on the dev machine.

### 8. Frontend foundation

Design tokens (CSS vars + Tailwind extends), all primitives in
`components/primitives/`, layout components (Sidebar, TopBar), auth flow
(login page + protected route wrapper), theme toggle, command palette
skeleton with Cmd+K shortcut.

**Done when**: dark/light toggle works, sidebar collapses with Cmd+B,
command palette opens with Cmd+K and lists at least the navigation actions,
all primitives render correctly in both themes in a Storybook-style
demo route at `/_dev/primitives`.

### 9. Dashboard page

Metric cards with count-up animation, equity curve from `/bankroll/series`,
open trades list, by-strategy breakdown card. Responsive grid. Skeleton
loader matched to the layout.

**Done when**: page renders correctly with 50 seeded trades, metric numbers
animate on first load, equity curve has working brush zoom, all numbers
use tabular alignment.

### 10. Trade entry page

Strategy selector tabs at top, dynamic field renderer for `strategy_data`,
universal stake/odds row, the **CashOutToggle** wired to backend computation,
markdown notes editor, tag picker. Auto-save draft to localStorage every 5s
with restore on next visit.

**Done when**: each strategy tab renders the correct dynamic fields, the
three cash-out modes all submit to backend correctly and round-trip the
correct PnL, draft restore works after a page refresh.

### 11. Trade log page

TanStack Table with virtualization, filter chips above, full-text search,
footer aggregates of the filtered set. Row click opens `TradeDetailDrawer`.
Inline edit in drawer (double-click). Keyboard navigation (j/k/Enter/e/n).

**Done when**: 1000 seeded trades scroll smoothly, all filter combinations
work, drawer inline edit updates the row optimistically, keyboard shortcuts
documented in command palette.

### 12. Strategies page

List of built-in + custom strategies. For custom strategies, the
`FieldSchemaBuilder` visual editor with drag-reorder, type picker, validation
rules, and a live preview pane showing the resulting trade form.

**Done when**: a user can create a brand new strategy with 5+ fields of
mixed types and immediately use it in `/trades/new`.

### 13. Analytics page

Tabs: Overview, Drawdown, Monte Carlo, Calendar, Per-strategy. All charts
implemented with Recharts customization (thin axes, mono labels, gradient
fills). Monte Carlo widget with adjustable parameters and live recomputation.

**Done when**: each tab renders fully, Monte Carlo recomputes in <2s with
visible loading state, calendar heatmap cells are clickable to filter.

### 14a. Polish pass

Empty states for every list/table/chart with custom copy and CTAs.
Skeleton loaders matched to final layouts. Optimistic UI everywhere.
All keyboard shortcuts wired and visible in command palette.
Accessibility audit: focus rings, ARIA labels, semantic HTML, keyboard
trap on modals/drawers, screen reader announcements for toasts.
Lighthouse audit on the dashboard page → ≥90 in all four categories.

**Done when**: a11y check passes, Lighthouse target met, every async
interaction has either optimistic feedback or a skeleton.

### 14b. Obsidian integration

Vault exporter service, watcher for two-way mode, Settings panel, conflict
handling. End-to-end test with a real vault directory mounted as a Docker
volume. See `docs/obsidian.md` for full spec.

**Done when**: enabling Obsidian + clicking "Export now" produces a complete
vault that opens in Obsidian without errors, all frontmatter is parseable,
Dataview queries in `Strategies/*.md` and `Dashboards/Bankroll.md` resolve
correctly, two-way edit on a trade note's user-editable section syncs back
to the DB.

### 15. Deployment artifacts

Production Dockerfiles (multi-stage, non-root user, `.dockerignore`).
Caddyfile or equivalent for the production frontend. `docker-compose.prod.yml`
with proper restart policies, health checks, log rotation. Complete
`.env.example`. README with VPS deployment steps including the Nginx Proxy
Manager subdomain configuration to coexist with other Docker apps.

**Done when**: `docker compose -f docker-compose.prod.yml up -d` brings up
the full stack on a fresh VPS, the README walkthrough is verifiable
end-to-end including the NPM subdomain config.

## Quality requirements (apply to every step)

- All Python functions have type hints. No bare `Any` without justification.
- All Pydantic models use v2 syntax with field validators.
- All money values are `Decimal`, never `float`. JSON-serialized as strings.
- All SQL via SQLAlchemy ORM, parameterized.
- TypeScript strict, no `any`, no `// @ts-ignore` without inline reason.
- API types generated from OpenAPI via `openapi-typescript`.
- Backend test coverage ≥85% line. Frontend test coverage ≥70% on critical
  paths (forms, calculators, table).
- All API errors return RFC 9457 problem-details JSON.
- Idempotent migrations (Alembic), with both `up` and `down` implemented.
- No `print` / `console.log` left in production code.
- Lighthouse on dashboard ≥90 (perf, a11y, best-practices).
- Responsive: full at 1280px desktop, graceful at 1024px tablet,
  read-mostly at <768px mobile.

## Out of scope — do NOT build

- Tennis or any non-football sport (schema is ready, no UI)
- Multi-user auth, roles, sharing
- Live betting feed integration / Betfair API auto-sync
- Email or push notifications
- Mobile native app
- Audit log / change history (single-user, not needed)
- Custom Obsidian plugin (filesystem-based integration only)

## Checkpoint protocol

At the end of every step:
1. Run all tests for the touched area
2. Update the `## Status` section at the top of `CLAUDE.md` with:
   - New current phase / step
   - Date of completion
   - One-line summary of what was built
3. Stop and confirm with the user before starting the next step.
