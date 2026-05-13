"""Obsidian-flavoured markdown renderers.

Each public function returns a complete file body (frontmatter + body)
ready to write. ``existing_text`` is optional — when present, the renderer
extracts the user-editable block from it and re-injects it into the new
output so the user's notes survive re-exports.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

import yaml

from app.models import Strategy, Trade
from app.services.obsidian.markers import extract_user_editable, wrap_user_editable


def _yaml_dump(data: dict) -> str:
    """Stable YAML dump: sorted keys, no anchors, ISO timestamps."""
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    ).strip()


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _decimal_to_yaml(v: Decimal | None) -> str | float | None:
    if v is None:
        return None
    # YAML preserves the precision we want by emitting it as a quoted string
    # so the trader can parse it without locale surprises.
    return str(v)


def trade_filename(trade: Trade) -> str:
    """``YYYY-MM-DD home vs away.md`` — the docs' canonical naming rule."""
    date_part = trade.kickoff_at.date().isoformat()
    safe_home = trade.home_team.replace("/", "-")
    safe_away = trade.away_team.replace("/", "-")
    return f"{date_part} {safe_home} vs {safe_away}.md"


# ---------------------------------------------------------------------------
# Trade note
# ---------------------------------------------------------------------------


def render_trade(
    trade: Trade,
    *,
    now: datetime,
    existing_text: str | None = None,
) -> str:
    user_block = (
        extract_user_editable(existing_text) if existing_text else None
    ) or _initial_user_block(trade)

    fm = {
        "trade_id": str(trade.id),
        "app_managed": True,
        "strategy": trade.strategy.name,
        "strategy_slug": trade.strategy.slug,
        "strategy_color": trade.strategy.color_hex,
        "account": trade.account.name if trade.account else None,
        "account_venue": trade.account.venue if trade.account else None,
        "match": f"{trade.home_team} vs {trade.away_team}",
        "league": trade.league,
        "kickoff": _isoformat(trade.kickoff_at),
        "stake_total": _decimal_to_yaml(trade.stake_total),
        "avg_odds": _decimal_to_yaml(trade.avg_odds),
        "commission_pct": _decimal_to_yaml(trade.commission_pct),
        "market_type": trade.market_type.value,
        "pnl_mode": trade.pnl_mode.value,
        "computed_pnl_eur": _decimal_to_yaml(trade.computed_pnl_eur),
        "outcome_label": trade.outcome_label,
        "status": trade.status.value,
        "tags": [t.name for t in trade.tags],
        "last_synced_at": _isoformat(now),
    }

    pnl_signed = (
        f"+€{trade.computed_pnl_eur}"
        if trade.computed_pnl_eur >= 0
        else f"−€{abs(trade.computed_pnl_eur)}"
    )

    score_line = ""
    if trade.ft_score_home is not None and trade.ft_score_away is not None:
        score_line = f"FT {trade.ft_score_home}-{trade.ft_score_away}"
    elif trade.ht_score_home is not None and trade.ht_score_away is not None:
        score_line = f"HT {trade.ht_score_home}-{trade.ht_score_away}"

    body = f"""# {trade.home_team} vs {trade.away_team}
*{trade.league} · {trade.kickoff_at.strftime("%-d %b %Y · %H:%M") if hasattr(trade.kickoff_at, 'strftime') else trade.kickoff_at}*

> [!info] Result: **{pnl_signed}**{f" · {trade.outcome_label}" if trade.outcome_label else ""}{f" · {score_line}" if score_line else ""}

## Setup
Strategy: [[Strategies/{trade.strategy.name}]]
Account: {trade.account.name if trade.account else "—"}{f" ({trade.account.venue})" if trade.account else ""}
Stake total: €{trade.stake_total} · Avg odds: {trade.avg_odds} · Commission: {trade.commission_pct}%
PnL mode: `{trade.pnl_mode.value}`{_strategy_data_lines(trade.strategy_data)}

## Notes
{wrap_user_editable(user_block)}

## Tags
{_tags_line(t.name for t in trade.tags)}

---
*Auto-managed by SportEdge — last synced {now.strftime("%Y-%m-%d %H:%M")}. Edit notes between the markers freely. Do not edit frontmatter or structural sections.*
"""

    return _wrap_frontmatter(fm, body)


def _initial_user_block(trade: Trade) -> str:
    if trade.notes_md:
        return trade.notes_md
    return "*write your notes here*"


def _strategy_data_lines(strategy_data: dict | None) -> str:
    if not strategy_data:
        return ""
    parts: list[str] = []
    for k, v in strategy_data.items():
        if v is None or v == "":
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        parts.append(f"{k}: `{v}`")
    if not parts:
        return ""
    return "\n" + " · ".join(parts)


def _tags_line(tags: Iterable[str]) -> str:
    tag_list = list(tags)
    if not tag_list:
        return "_no tags_"
    return " ".join(f"#{t.replace(' ', '-')}" for t in tag_list)


# ---------------------------------------------------------------------------
# Daily note
# ---------------------------------------------------------------------------


def render_daily(
    *,
    day: date,
    trades: list[Trade],
    bankroll_eod: Decimal,
    bankroll_sod: Decimal,
    existing_text: str | None = None,
) -> str:
    closed = [t for t in trades if t.status.value == "CLOSED"]
    day_pnl = sum((t.computed_pnl_eur for t in closed), start=Decimal("0"))
    day_stake = sum((t.stake_total for t in closed), start=Decimal("0"))
    roi = (day_pnl / day_stake * Decimal("100")) if day_stake > 0 else Decimal("0")

    user_block = (
        extract_user_editable(existing_text) if existing_text else None
    ) or "*write your post-session reflection here*"

    fm = {
        "app_managed": True,
        "date": day.isoformat(),
        "trades_count": len(closed),
        "day_pnl_eur": _decimal_to_yaml(day_pnl),
        "roi_day_pct": _decimal_to_yaml(roi.quantize(Decimal("0.01"))),
        "bankroll_eod": _decimal_to_yaml(bankroll_eod),
    }

    pnl_signed = f"+€{day_pnl}" if day_pnl >= 0 else f"−€{abs(day_pnl)}"

    trade_bullets = "\n".join(
        f"- [[Trades/{trade_filename(t).rstrip('.md')}]] — {t.strategy.name}"
        f" — {t.outcome_label or '—'}"
        f" — **{('+€' + str(t.computed_pnl_eur)) if t.computed_pnl_eur >= 0 else ('−€' + str(abs(t.computed_pnl_eur)))}**"
        for t in closed
    ) or "_no closed trades on this day_"

    body = f"""# {day.isoformat()} — Daily recap

> {len(closed)} trades · **{pnl_signed}** · ROI {roi.quantize(Decimal("0.01"))}% · Bankroll €{bankroll_sod} → €{bankroll_eod}

## Trades
{trade_bullets}

## Reflection
{wrap_user_editable(user_block)}
"""

    return _wrap_frontmatter(fm, body)


# ---------------------------------------------------------------------------
# Strategy note
# ---------------------------------------------------------------------------


def render_strategy(strategy: Strategy, existing_text: str | None = None) -> str:
    user_block = (
        extract_user_editable(existing_text) if existing_text else None
    ) or "*write your playbook notes for this strategy here*"

    fm = {
        "app_managed": True,
        "strategy_id": str(strategy.id),
        "strategy_slug": strategy.slug,
        "kind": strategy.kind.value,
        "color_hex": strategy.color_hex,
    }

    body = f"""# {strategy.name}

{strategy.description or ""}

## Notes
{wrap_user_editable(user_block)}

## Recent trades

```dataview
TABLE kickoff, stake_total, avg_odds, computed_pnl_eur, outcome_label
FROM "Trades"
WHERE strategy_slug = "{strategy.slug}"
SORT kickoff DESC
LIMIT 50
```
"""

    return _wrap_frontmatter(fm, body)


# ---------------------------------------------------------------------------
# Bankroll dashboard
# ---------------------------------------------------------------------------


def render_bankroll_dashboard() -> str:
    fm = {"app_managed": True}
    body = """# Bankroll

```dataview
TABLE WITHOUT ID kickoff AS "Date", strategy AS "Strategy", computed_pnl_eur AS "P/L", outcome_label AS "Outcome"
FROM "Trades"
WHERE status = "CLOSED"
SORT kickoff DESC
LIMIT 100
```

## By strategy

```dataview
TABLE rows.length AS "Trades", sum(rows.computed_pnl_eur) AS "Total P/L"
FROM "Trades"
WHERE status = "CLOSED"
GROUP BY strategy
SORT sum(rows.computed_pnl_eur) DESC
```
"""
    return _wrap_frontmatter(fm, body)


def render_readme() -> str:
    fm = {"app_managed": True, "purpose": "vault root readme"}
    body = """# SportEdge vault

This vault is auto-managed by SportEdge Pro. Files outside the
`Trades/`, `Daily/`, `Strategies/`, `Dashboards/`, and `_meta/` folders
are never touched, so you can keep your own notes alongside.

- `Trades/` — one markdown file per trade. Edit anything between the
  `<!-- USER_EDITABLE_START -->` and `<!-- USER_EDITABLE_END -->` markers
  freely; everything outside is regenerated on every export.
- `Daily/` — one file per day with a recap and a reflection block.
- `Strategies/` — one file per strategy, with Dataview queries listing
  the strategy's trades.
- `Dashboards/Bankroll.md` — global Dataview-driven view.
- `_meta/_conflicts/` — files with concurrent edits land here for
  manual resolution. SportEdge never silently overwrites your content.

The `app_managed: true` frontmatter flag identifies files SportEdge owns.
Do not edit the frontmatter or the structural sections; the next export
will overwrite them.
"""
    return _wrap_frontmatter(fm, body)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap_frontmatter(fm: dict, body: str) -> str:
    return f"---\n{_yaml_dump(fm)}\n---\n\n{body.lstrip()}"
