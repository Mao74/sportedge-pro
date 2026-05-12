# Frontend, design system, and visual language

Read this before any frontend work. It defines pages, layout, components,
and the **visual language** for the app. There are no visual mockups to
reference, so this document is the single source of truth for how the UI
should look and feel — read it carefully and follow the palette, typography,
spacing, and component specifications precisely.

## Pages and routes

| Path | Page | Purpose |
|---|---|---|
| `/login` | Login | JWT auth |
| `/` | Dashboard | Bankroll header, equity curve, open trades, by-strategy |
| `/trades` | Trade log | Filterable table + side drawer for detail |
| `/trades/new` | New trade | Strategy-aware form with cash-out toggle |
| `/strategies` | Strategies | List built-in + custom; create/edit custom |
| `/strategies/{id}` | Strategy detail | Edit metadata + field schema (custom only) |
| `/analytics` | Analytics | Tabs: Overview, Drawdown, Monte Carlo, Calendar, Per-strategy |
| `/whatif` | What-if | Standalone cash-out calculator |
| `/settings` | Settings | Bankroll adjustments, commission, theme, Obsidian config |

## Layout

### Sidebar (left, persistent)

- 240px expanded, 56px collapsed (Cmd/Ctrl+B to toggle)
- Top: workspace logo + name
- Nav items: Dashboard, Trades, Strategies, Analytics, What-if
- Mid: list of active strategies, each with a colored dot (`color_hex`).
  Click → navigate to `/trades?strategy_id=...` filtered view.
- Bottom: Settings, theme toggle, user menu

### Top bar

- Breadcrumb on the left
- Global search trigger (button) — opens command palette
- Cmd/Ctrl+K opens command palette directly
- "+ New trade" button (primary accent)
- Obsidian sync status badge (when enabled): green dot + "synced 2m ago",
  yellow when syncing, red with conflict count when there are unresolved
  conflicts (click → conflicts drawer)

### Command palette (Cmd/Ctrl+K)

Fuzzy-searchable action list. Categories:
- **Navigate**: jump to any page
- **Trade actions**: "Add trade", "Find trade by team", "Show open trades",
  "Recent losing trades"
- **Strategy actions**: "Switch to Magic CS view", "New custom strategy"
- **Analytics**: "Run Monte Carlo", "Show drawdown", "Calendar this month"
- **Settings**: "Toggle dark mode", "Adjust bankroll", "Configure Obsidian"

Implementation: `cmdk` library + custom result renderers.

## Component primitives

Build a small design system of reusable primitives in `components/primitives/`
before pages. Every page composes from these — never hand-roll a button or
card inline.

| Primitive | Purpose |
|---|---|
| `Button` | Primary / secondary / ghost variants × sm/md/lg sizes |
| `Card` | Elevated surface; optional header/footer slots |
| `Drawer` | Slide-in panel from right; controlled by `open` prop |
| `Modal` | Centered overlay with backdrop blur |
| `Toggle` | Single switch + segmented control variants |
| `Chip` | Pill with optional dismiss button; semantic colors |
| `MetricCard` | Label + big number + delta + sparkline |
| `Sparkline` | Tiny inline SVG line chart, no axes |
| `Skeleton` | Animated gradient placeholder |
| `Toast` | Bottom-right stacked notifications, semantic colors |
| `Input`, `NumberInput`, `Select`, `MultiSelect`, `DateRangePicker` | Form controls |
| `MarkdownEditor` | textarea + live preview tab; uses `react-markdown` |
| `TagPicker` | Async typeahead + create-on-the-fly |

All primitives must support dark mode, be keyboard-accessible (focus rings,
arrow nav where applicable), and handle loading states.

## Domain components

### `<CashOutToggle>`

The most important UX element. Three-state segmented control + dependent
field area:

- **No cash out** → trade plays out fully. Hides cash-out specific fields.
  Shows `outcome_label` selector (options depend on the strategy template).
  AUTO mode is used.
- **Manual P/L** → single number input "Final P/L (€)", positive or negative.
  `outcome_label` optional. Fast-path for mobile.
- **From cashout odds** → `cashout_odds` input + `position_side` toggle.
  System calls the backend live to compute P/L; shows the formula breakdown
  inline below the field.

Switching modes preserves data where possible — moving from "From cashout
odds" to "Manual P/L" pre-fills the manual field with the just-computed value.

### `<DynamicFieldRenderer>`

Walks a strategy's `field_schema.fields` array and renders one component per
field. Supports types: `text`, `number`, `select`, `multiselect`, `boolean`,
`chip-picker`, `computed`. Honors `depends_on` to conditionally show fields.
Validates against zod schemas derived from the field_schema at render time.

### `<FieldSchemaBuilder>` (custom strategy editor only)

Visual builder for the field_schema JSON. Drag-and-drop reorder, inline
add field with type picker, validation rules editor, live preview pane
showing what the trade form will look like.

### `<TradeForm>`

Composes `DynamicFieldRenderer` + universal fields (match, kickoff, stake,
odds) + `CashOutToggle` + `MarkdownEditor` for notes + `TagPicker`.
Strategy selector tabs at top. Auto-save draft to localStorage every 5s
(restorable on next visit).

### `<TradeTable>` (TanStack Table)

- Column virtualization (`useVirtualizer`)
- Sortable headers (multi-sort with shift+click)
- Sticky header
- Filter chips above the table — removable, each chip controls a query param
- Search input bound to `q` param
- Footer: live aggregates of the filtered set (count, sum P/L, ROI %)
- Row click → open `TradeDetailDrawer`
- Keyboard: `j`/`k` navigate, Enter open, `e` open in edit mode, `n` new trade

### `<TradeDetailDrawer>`

480px right-side drawer. Sections:
- Header: match + strategy badge + status pill + actions menu
- Body: tabs — `Overview`, `Notes`, `What-if`, `History`
  - Overview: all fields, inline-editable (double-click)
  - Notes: full markdown editor, what-if snapshots appended automatically
  - What-if: embedded `<WhatIfCashOut>` for OPEN trades
  - History: change log (created, edited, closed events)
- Footer: Close trade / Reopen / Delete (destructive, with confirm)

### Charts (Recharts + heavy customization)

- **EquityCurve**: area chart with FILL only (no stroke gradient — CSS rule).
  Brush for zoom, hover crosshair with tooltip showing date + balance + day P/L
- **RollingROI**: line chart, reference line at 0%, hover tooltip
- **DrawdownChart**: underwater chart (negative-area filled red, mirrored)
- **CalendarHeatmap**: 7×24 grid (day-of-week × hour-of-day), color intensity
  proportional to P/L volume. Click a cell to filter trades by that timeslot.
- **MonteCarloWidget**: parameter inputs at top, big risk-of-ruin number,
  histogram of ending bankrolls with a vertical marker for starting bankroll,
  three percentile callouts (P10, P50, P90)

All charts respect dark mode, use thin axes (1px, 10% opacity), and render
numeric labels in JetBrains Mono with `font-feature-settings: "tnum"`.

## Visual language — the actual design

Apply the dark, futuristic, financial-trading aesthetic below — inspired by
Linear, Vercel dashboards, Cron, and Bloomberg Terminal, reinterpreted for
2026.

### Color system

Dark mode is **default**. Light mode is fully supported but secondary. Define
both as CSS variables in `styles/global.css` and toggle via `data-theme="dark"`
on `<html>`.

```css
:root[data-theme="dark"] {
  --bg-base:        #07090C;
  --bg-elevated:    #0F1218;
  --bg-overlay:     #161B24;
  --bg-hover:       #1A2030;

  --border-subtle:  rgba(255, 255, 255, 0.06);
  --border-strong:  rgba(255, 255, 255, 0.12);
  --border-focus:   #8B7FFF;

  --text-primary:   #E8ECF1;
  --text-secondary: #8B92A3;
  --text-tertiary:  #5A6273;

  --accent-gain:    #1DCC8C;
  --accent-gain-bg: rgba(29, 204, 140, 0.10);
  --accent-loss:    #FF4757;
  --accent-loss-bg: rgba(255, 71, 87, 0.10);
  --accent-warn:    #FFB547;
  --accent-warn-bg: rgba(255, 181, 71, 0.10);
  --accent-info:    #4DA3FF;
  --accent-info-bg: rgba(77, 163, 255, 0.10);
  --accent-brand:   #8B7FFF;
  --accent-brand-bg:rgba(139, 127, 255, 0.10);
}

:root[data-theme="light"] {
  --bg-base:        #FAFAFA;
  --bg-elevated:    #FFFFFF;
  --bg-overlay:     #FFFFFF;
  --bg-hover:       #F4F5F7;

  --border-subtle:  rgba(0, 0, 0, 0.06);
  --border-strong:  rgba(0, 0, 0, 0.12);
  --border-focus:   #6B5FFF;

  --text-primary:   #0E1116;
  --text-secondary: #5A6273;
  --text-tertiary:  #9097A3;

  --accent-gain:    #0F9D6E;   /* slightly darker for AA contrast on white */
  --accent-loss:    #DD3344;
  --accent-warn:    #C77B0F;
  --accent-info:    #2A7CD9;
  --accent-brand:   #6B5FFF;
}
```

### Strategy color palette

Each strategy gets a distinct hue used for chips, badges, dots, and mini-chart
strokes. Built-ins are fixed; custom strategies get the next free color
from the rotation.

```
--strat-magic-cs:    #8B7FFF   (violet)        builtin
--strat-draw-hunter: #1DCC8C   (green)         builtin
--strat-custom-1:    #FFB547   (amber)
--strat-custom-2:    #4DA3FF   (blue)
--strat-custom-3:    #FF6FCF   (pink)
--strat-custom-4:    #00D4D4   (teal)
--strat-custom-5:    #FF8A4D   (orange)
--strat-custom-6:    #C792EA   (lilac)
```

### Typography

- **Display / UI sans**: Geist (load via `@fontsource/geist-sans`). Inter
  as system fallback.
- **Mono for numbers, odds, P/L**: JetBrains Mono (`@fontsource/jetbrains-mono`).
  Always with `font-feature-settings: "tnum"` for tabular numerals.
- **Type scale (px)**: 11 / 12 / 13 / 15 / 18 / 24 / 32 / 48
  - 11–13 for labels and metadata
  - 15 for body text
  - 18–24 for section headings
  - 32–48 for hero metrics on the dashboard
- **Two weights only**: 400 regular and 500 medium. Never 600 or 700 —
  they look heavy and dated.
- **Tracking**: `-0.01em` on display sizes (24px+), default elsewhere
- **Line height**: 1.5 on body, 1.2 on display

### Spacing and grid

Base unit 4px. Use multiples: 4 · 8 · 12 · 16 · 24 · 32 · 48. Cards have
20px internal padding minimum. Generous whitespace — never cram.

### Components

- **Cards**: `bg: var(--bg-elevated)` · `border: 1px solid var(--border-subtle)` ·
  `rounded-xl` (12px) · no shadow. Hover: `border-color: var(--border-strong)`,
  200ms transition.
- **Buttons**:
  - **Primary**: solid `--accent-brand` background, white text, `rounded-lg` (8px),
    medium weight. Hover: 90% opacity. Active: scale(0.98).
  - **Secondary**: transparent background, `1px solid --border-subtle`, hover bg
    `--bg-hover`.
  - **Ghost**: no border, hover bg only.
  - **Destructive**: `--accent-loss` background.
  - Sizes: 28px (sm), 32px (md), 36px (lg), 40px (xl) heights.
- **Inputs**: `bg: var(--bg-overlay)` · `border: 1px solid var(--border-subtle)` ·
  focus: `border-color: var(--border-focus)` + 2px outer ring of
  `var(--accent-brand-bg)`.
- **Chips**: pill (radius 999px), 24px height, semantic background using the
  10% accent variants, text in 100% accent color. Use for tags, statuses,
  strategies.
- **Drawers**: slide from right, 480px width, `bg: var(--bg-overlay)`,
  backdrop blur 8px on the overlay. Animation 240ms cubic-bezier(0.16, 1, 0.3, 1).
- **Modals**: centered, max-width 560px, same backdrop blur.
- **Dividers**: 1px solid `--border-subtle`, never decorative pseudo-elements.

### Motion (Framer Motion)

- **Page transitions**: 180ms, opacity + 8px y slide on mount
- **Card mount**: stagger 30ms per child, fade + 4px y
- **Numbers**: count-up animation on first render via custom hook.
  Duration clamped 600ms, easing easeOutQuart. Skip for values that change
  via re-render (only animate on mount).
- **Chart draws**: stroke-dashoffset animation 800ms ease-out on first paint
- **Live dots** (open trades): subtle pulse, 1.5s loop, 0.6 → 1.0 opacity
- **Drawer**: 240ms cubic-bezier(0.16, 1, 0.3, 1)
- **Avoid**: bounces, exaggerated easings, anything that delays interaction.

### Polish details (these are what make the app feel "5 years ahead")

- **Empty states**: every list, table, and chart has a custom empty state
  with a one-line hint and a primary CTA. No generic "no data" text. Examples:
  - Trade log empty: "No trades yet — start by logging your first one"
    + button "Add trade"
  - Open trades empty: "Nothing live right now"
- **Skeleton loaders**: animated gradient skeletons matched to the final
  layout (same dimensions, same number of rows). No spinners anywhere.
- **Optimistic UI**: trade create / edit applies instantly with a subtle
  "saving…" indicator in the corner. Roll back with a toast on error.
- **Inline editing**: double-click any field in the trade detail drawer to
  edit. Esc cancels, Enter saves.
- **Keyboard everywhere**:
  - Cmd/Ctrl+K → command palette
  - Cmd/Ctrl+B → toggle sidebar
  - Cmd/Ctrl+N → new trade (from any page)
  - `j` / `k` → navigate trade rows
  - Enter → open selected row
  - `e` → edit
  - Esc → close drawer / modal
  - Cmd/Ctrl+Enter → submit form
- **Toasts**: bottom-right, max 3 stacked, 4s auto-dismiss, semantic colors,
  swipe-to-dismiss on touch.
- **Numeric tabular alignment**: every number in a table cell uses `tnum`
  so columns line up perfectly. Right-align numeric columns.
- **Color-coded P/L**: positive in `--accent-gain`, negative in `--accent-loss`,
  zero in `--text-secondary`. Always include the sign explicitly: `+€41.20`,
  not `41.20`. For `−`, use the proper minus character (U+2212), not hyphen.

### Iconography

Lucide Icons exclusively, 1.5px stroke. Sizes: 14px in chips and buttons,
16px in nav, 20px in drawer headers. Never emoji. For strategy markers,
use a simple filled colored dot (8px), never an icon.

### Loading and error patterns

- **Initial app load**: skeleton sidebar + skeleton dashboard, no spinner
- **Page-level error**: full-page error component with the failing endpoint,
  a retry button, and a "report this" link that pre-fills a clipboard with
  the request ID
- **Inline errors** (forms): red text below the field, never red borders alone
- **Network offline**: persistent yellow banner at top, queues optimistic
  writes for replay when online

### Responsive behavior

- **≥1280px**: full desktop layout, sidebar expanded
- **1024–1279px**: sidebar auto-collapses, content reflows to wider columns
- **768–1023px**: sidebar overlay only (hamburger trigger), tables fall back
  to card layout (one card per trade), charts stack vertically
- **<768px**: read-mostly. Dashboard works (single-column), trade log works
  (cards), but trade entry redirects to a friendly "use desktop" screen for
  complex strategies, allows MANUAL P/L entry only on mobile.

## Reference inspirations (for "feel", not for copying)

- Linear (linear.app) — typography, density, command palette
- Vercel dashboard — dark surfaces, mono numbers
- Cron / Notion Calendar — calendar heatmap interactions
- Bloomberg Terminal — information density, color-coded P/L
- Raycast — keyboard-first interactions, inline previews

The app should feel like it belongs in this lineage: serious, fast, precise.
Not playful, not corporate, not friendly-cute. **Trader-grade.**
