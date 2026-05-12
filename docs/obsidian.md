# Obsidian integration

Optional, off-by-default mirror of the app's data into a markdown vault that
opens cleanly in Obsidian. Gives the user the full power of Obsidian (graph
view, Dataview queries, backlinks, daily notes) on top of structured trading
data managed by the app's database.

## Configuration (Settings page)

Add a dedicated "Obsidian" panel to `/settings` with:

| Setting | Type | Notes |
|---|---|---|
| `obsidian_enabled` | boolean | master toggle |
| `obsidian_vault_path` | text | absolute path INSIDE the container, default `/vault` |
| `obsidian_sync_mode` | enum | `export_only` · `two_way` · `manual_only` |
| `obsidian_template_set` | enum | `complete` (default) · `minimal` · `tactical` |
| `obsidian_export_strategies` | multiselect | which strategies to export (default: all active) |

UI:
- "Export now" button → triggers a full bulk re-export
- "Open vault folder" link → shows the resolved host path as copyable text
- Last-sync indicator → timestamp + last error, if any
- Conflict count badge → click opens the conflict resolution drawer

Settings persist in a single-row `app_settings` table or as a JSONB column
on the user record.

## Sync modes

- **`export_only`** — app writes/updates the vault. Changes from outside the
  app are ignored. Safest, recommended for the first 1–2 weeks.
- **`two_way`** — app writes AND watches the vault for `.md` modifications.
  External edits to **notes and tags only** sync back to the database.
  Structural fields (stake, odds, P/L, scores) are read-only from Obsidian.
- **`manual_only`** — vault is updated only on explicit "Export now" clicks.
  No automatic sync, no watcher. For users who want full manual control.

## Vault directory structure

The exporter produces this layout. Files outside these paths are NEVER
touched, so the user can keep their own notes in the same vault without
fear of overwrite.

```
{vault_path}/
├── Trades/
│   ├── 2026-04-28 Inter vs Lazio.md
│   ├── 2026-04-28 Real vs Atletico.md
│   └── ...
├── Daily/
│   ├── 2026-04-28.md
│   └── 2026-04-29.md
├── Weekly/
│   └── 2026-W17.md
├── Strategies/
│   ├── Magic CS.md
│   ├── Draw Hunter.md
│   └── value 1X2.md
├── Dashboards/
│   ├── Bankroll.md
│   └── Performance.md
├── _meta/
│   ├── tags.md
│   └── _conflicts/
└── README.md
```

Filename rule for trades: `{YYYY-MM-DD} {home} vs {away}.md`. If two trades
match the same filename, append ` ({short_id})` (first 6 chars of UUID).

## Frontmatter conventions

Every generated file has YAML frontmatter so Obsidian's Dataview plugin can
query the vault as a database. The `app_managed: true` flag prevents
accidental hand-editing of structural data.

### Trade note (`Trades/{date} {home} vs {away}.md`)

```yaml
---
trade_id: a3f9e2c1-b9c2-4d6e-8f1a-2b3c4d5e6f7g
app_managed: true
strategy: Magic CS
strategy_color: "#8B7FFF"
match: "Inter vs Lazio"
league: Serie A
kickoff: 2026-04-28T20:45:00+02:00
stake_total: 62.00
avg_odds: 5.42
pnl_mode: AUTO
computed_pnl_eur: 41.20
outcome_label: A2_OVER25
status: CLOSED
tags: [protocol-clean, high-xg]
last_synced_at: 2026-04-28T22:15:33+02:00
---

# Inter vs Lazio
*Serie A · 28 Apr 2026 · 20:45*

> [!info] Result: **+€41.20** · A2_OVER25

## Setup
Strategy: [[Strategies/Magic CS]]
Tier: 4-CS · CS selected: 1-0, 1-1, 0-1, 0-0
Stake total: €62.00 · Avg odds: 5.42 · O2.5 parachute: €22.00

## Notes
<!-- USER_EDITABLE_START -->
xG asymmetry favorevole (1.8 vs 1.2). Inserimento al 55' come da protocollo.
Cash out parziale a 2-1...
<!-- USER_EDITABLE_END -->

## Tags
#protocol-clean #high-xg

---
*Auto-managed by SportEdge — last synced 2026-04-28 22:15. Edit notes between
the markers and tags freely. Do not edit frontmatter or structural sections.*
```

### Daily note (`Daily/{YYYY-MM-DD}.md`)

```yaml
---
app_managed: true
date: 2026-04-28
trades_count: 3
day_pnl: 84.20
roi_day: 4.2
bankroll_eod: 2847.00
---

# 2026-04-28 — Daily recap

> 3 trades · **+€84.20** · ROI 4.2% · Bankroll €2,762.80 → €2,847.00

## Trades
- [[Trades/2026-04-28 Inter vs Lazio]] — Magic CS — A2_OVER25 — **+€41.20**
- [[Trades/2026-04-28 Real vs Atletico]] — Draw Hunter — WIN — **+€88.00**
- [[Trades/2026-04-28 Bayern vs Dortmund]] — value 1X2 — LOSS — **−€45.00**

## Reflection
<!-- USER_EDITABLE_START -->
*(write your post-session reflection here — preserved across syncs)*
<!-- USER_EDITABLE_END -->
```

### Weekly note (`Weekly/{YYYY}-W{week}.md`)

Aggregates the week's stats: total trades, P/L, ROI, drawdown, best/worst day,
plus a Dataview block listing the week's trades sorted by P/L. Single
user-editable reflection block.

### Strategy note (`Strategies/{name}.md`)

Lists strategy metadata, current performance, and a Dataview query block:

````markdown
```dataview
TABLE kickoff, stake_total, avg_odds, computed_pnl_eur, outcome_label
FROM "Trades"
WHERE strategy = "Magic CS"
SORT kickoff DESC
LIMIT 50
```
````

### Bankroll dashboard (`Dashboards/Bankroll.md`)

Pure Dataview-driven view. The exporter generates this once on first export;
queries inside compute live aggregates from the trade frontmatters whenever
Obsidian opens the file.

## User-editable section markers

Critical pattern. The exporter wraps user-writable content with comment
markers:

```markdown
<!-- USER_EDITABLE_START -->
... content the user can edit freely ...
<!-- USER_EDITABLE_END -->
```

On re-export, the exporter:
1. Reads the existing file (if present)
2. Extracts the content between markers
3. Generates the new file with all auto-content updated
4. Restores the user-edited content between the new markers

In `two_way` mode, edits inside these blocks are synced back to the database:
- Trade note: `notes_md` column
- Daily note: `daily_reflections.reflection_md`
- Weekly note: a `weekly_reflections` table (add to schema)

## Two-way sync behavior

When `obsidian_sync_mode == 'two_way'`:

1. A filesystem watcher (using `watchfiles` in async mode) monitors the vault
   directory for `.md` file modifications.
2. On change, the parser:
   a. Reads frontmatter to identify the entity (trade_id, daily date, etc.)
   b. Validates `app_managed: true` — files without this flag are ignored
   c. Compares `last_synced_at` with the DB record's `updated_at` to detect
      concurrent edits
   d. Extracts content between `USER_EDITABLE_START` / `USER_EDITABLE_END`
      markers and updates corresponding DB columns
3. **Tag handling**: tags appearing as `#tag-name` in user-editable blocks
   are added to the trade. Tags NOT present in the file are NOT removed
   unless the frontmatter contains `tags-authoritative: true` (advanced
   user opt-in).
4. **Conflict resolution**: if a DB record was modified after `last_synced_at`,
   write the incoming version to `_meta/_conflicts/{trade_id}-{timestamp}.md`
   and emit a toast in the app on next page load with a link to the conflict
   resolution drawer. Never silently overwrite.
5. Watcher coalesces rapid changes (debounce 500ms per file) to avoid sync
   storms during bulk edits.

### Watcher on Windows + Docker (WSL2 caveat)

When the host is Windows and the container runs under Docker Desktop's
WSL2 backend, `inotify` events from a Windows-mounted volume (path under
`/c/Users/...`) DO NOT propagate reliably to the Linux container. The
filesystem watcher will appear to do nothing.

The service must detect this scenario and fall back to **polling mode**
automatically:

```python
# In ObsidianSyncService.start_watcher():
# - Try watchfiles in default mode first
# - If running on Linux but the vault path is under /c/, /d/, etc.
#   (DrvFs mount detection), switch to force_polling=True with poll_interval=2.0
# - Log a one-time WARNING explaining the fallback so the user understands
#   why CPU usage is slightly higher
from watchfiles import awatch

async for changes in awatch(vault_path, force_polling=is_drvfs_mount(vault_path),
                            poll_interval=2.0 if is_drvfs_mount(vault_path) else None):
    ...
```

Polling at 2s gives near-real-time feel for trade journaling without
hammering the CPU. The user can override `poll_interval` via the
`OBSIDIAN_WATCH_POLL_INTERVAL` env var if needed.

Alternative for power users: move the vault into the WSL2 filesystem
(e.g. `/home/<user>/vaults/sportedge-pro`) and use Obsidian's iCloud/
Syncthing/git plugin to bridge it back to Windows. This restores native
inotify at the cost of an extra sync layer.

## Implementation

### Backend service

`backend/app/services/obsidian_sync.py`:

```python
class ObsidianSyncService:
    def __init__(self, vault_path: Path, db: AsyncSession,
                 template_set: str = "complete"): ...

    # Export side
    async def export_trade(self, trade: Trade) -> Path: ...
    async def export_daily(self, date: date) -> Path: ...
    async def export_weekly(self, year: int, week: int) -> Path: ...
    async def export_strategy(self, strategy: Strategy) -> Path: ...
    async def export_dashboards(self) -> list[Path]: ...
    async def export_all(self, progress_cb=None) -> ExportSummary: ...

    # Import side
    async def import_changes(self) -> list[ChangeEvent]: ...
    async def start_watcher(self) -> None: ...    # background task
    async def stop_watcher(self) -> None: ...

    # Conflict resolution
    async def list_conflicts(self) -> list[Conflict]: ...
    async def resolve_conflict(self, conflict_id: UUID,
                                resolution: Literal["keep_db","keep_file","merged"],
                                merged_text: str | None = None) -> None: ...
```

### Trade lifecycle hooks

After every successful trade INSERT/UPDATE/DELETE, if Obsidian is enabled,
schedule an async export task via an asyncio queue (`obsidian_queue`)
processed by a single background worker. This prevents:
- Blocking API responses on filesystem I/O
- Concurrent writes to the same file
- Cascading exports if the user creates many trades quickly

The queue collapses redundant tasks: if the queue contains an existing
`export_trade(trade_id=X)` task, a new one for the same trade replaces it.

Daily snapshots and weekly aggregates trigger their corresponding exports
on a schedule (daily at 23:59, weekly on Sunday at 23:59).

### API endpoints

```
GET    /api/v1/obsidian/status
       -> {enabled, mode, vault_path, last_sync_at, errors[], conflict_count}

PATCH  /api/v1/obsidian/config
       body: partial settings (any of the config fields above)

POST   /api/v1/obsidian/export-all
       -> {trades_exported, daily_exported, weekly_exported, strategies_exported,
           dashboards_exported, took_ms}

POST   /api/v1/obsidian/sync-now
       triggers a one-shot import-changes pass (only useful in two_way mode)

GET    /api/v1/obsidian/conflicts
       -> [{id, path, trade_id, detected_at, db_updated_at, file_updated_at, preview}]

POST   /api/v1/obsidian/conflicts/{id}/resolve
       body: {resolution: 'keep_db'|'keep_file'|'merged', merged_text?}
```

### Frontend

- **Settings panel**: as described above. All fields wire to `PATCH /obsidian/config`.
- **Topbar status badge**: subscribes to `/obsidian/status` via TanStack Query
  with 30s refetch. Shows green/yellow/red dot + relative time. Click → opens
  conflicts drawer if any, otherwise opens settings panel.
- **Conflicts drawer**: list of unresolved conflicts. Each shows file path,
  detection time, side-by-side diff (DB version vs file version), and three
  buttons (Keep DB, Keep file, Manual merge). Manual merge opens a modal
  with a markdown editor pre-filled with the file version.
- **Toast notifications**: on successful syncs (preference: silent / summary /
  verbose). On errors: persistent until dismissed.

## Dependencies

Add to `backend/pyproject.toml`:

```
watchfiles >= 0.21    # async filesystem watcher
python-frontmatter >= 1.1    # YAML frontmatter parser
aiofiles >= 23.2      # async file I/O
```

## Docker compose addition

```yaml
backend:
  volumes:
    - ./data/postgres:/var/lib/postgresql/data
    - ${OBSIDIAN_VAULT_PATH:-./obsidian-vault}:/vault    # NEW
  environment:
    - OBSIDIAN_DEFAULT_VAULT=/vault
```

Document in `README.md` that the user sets `OBSIDIAN_VAULT_PATH` in `.env`
to point at:
- A Syncthing folder shared between VPS and laptop (recommended for self-hosted)
- An iCloud / Dropbox / OneDrive synced folder
- A server-only folder, with Obsidian Sync handling distribution to devices

## Testing

- **Unit tests** for each template renderer with golden-file snapshots in
  `tests/fixtures/obsidian/`
- **Integration test**: create trade via API → assert the markdown file exists
  with correct frontmatter → modify the file's notes section between markers
  → trigger import → assert DB `notes_md` updated
- **Conflict test**: simulate concurrent DB and file edits → assert conflict
  file created in `_meta/_conflicts/` and original not overwritten
- **User-editable preservation test**: write content between markers, modify
  the trade, re-export, assert the user content survives
- **Bulk export test**: 500 trades, full re-export completes in <30s on the
  CI runner (rough perf budget)

## Out of scope (v1)

- Custom Obsidian plugin (filesystem integration is simpler and more robust)
- Automatic Templater snippets installation
- Embedding Obsidian graph view in the app
- Image/attachment handling beyond markdown
