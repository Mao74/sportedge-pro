"""CSV import / export for trades.

Schema (header row, in this exact order — strict):

    kickoff_at,closed_at,strategy_slug,account_name,home_team,away_team,league,
    stake_total,avg_odds,commission_pct,market_type,
    pnl_mode,position_side,outcome_label,cashout_odds,manual_pnl_eur,
    status,ht_score_home,ht_score_away,ft_score_home,ft_score_away,
    tags,strategy_data,notes_md,computed_pnl_eur

Notes:

- ``computed_pnl_eur`` in the export is informative only; the importer
  RECOMPUTES it via the PnL calculator (never trusts the CSV).
- ``tags`` is a comma-free pipe-separated list (e.g. ``protocol-clean|high-xg``)
  to keep it embeddable inside a CSV cell without quoting headaches.
- ``strategy_data`` is a JSON string literal (e.g. ``{"cs_selected":["1-0"]}``).
- ``strategy_slug`` is matched against existing strategies; unknown slugs
  produce row-level errors. The importer never auto-creates strategies.
- ``account_name`` is matched against active accounts; blank cells fall
  back to ``app_settings.default_account_id``. Unknown names produce
  row-level errors. The importer never auto-creates accounts.
- Trades reference strategies and accounts by their human-readable
  identifiers (slug / name) so the same CSV is portable across DB resets.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Account,
    AppSettings,
    MarketType,
    PnLMode,
    Strategy,
    Tag,
    Trade,
    TradeStatus,
)
from app.services.pnl_calculator import PnLInputs, compute_pnl

CSV_COLUMNS: tuple[str, ...] = (
    "kickoff_at",
    "closed_at",
    "strategy_slug",
    "account_name",
    "home_team",
    "away_team",
    "league",
    "stake_total",
    "avg_odds",
    "commission_pct",
    "market_type",
    "pnl_mode",
    "position_side",
    "outcome_label",
    "cashout_odds",
    "manual_pnl_eur",
    "status",
    "ht_score_home",
    "ht_score_away",
    "ft_score_home",
    "ft_score_away",
    "tags",
    "strategy_data",
    "notes_md",
    "computed_pnl_eur",
)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def _dec(v: Decimal | None) -> str:
    return "" if v is None else str(v)


def _int(v: int | None) -> str:
    return "" if v is None else str(v)


def export_trades_csv(trades: Iterable[Trade]) -> str:
    """Serialise an iterable of fully-loaded Trade rows to a CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel", lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for t in trades:
        sd = t.strategy_data or {}
        position_side = sd.get("position_side") or ""
        writer.writerow([
            _iso(t.kickoff_at),
            _iso(t.closed_at),
            t.strategy.slug if t.strategy else "",
            t.account.name if t.account else "",
            t.home_team,
            t.away_team,
            t.league,
            _dec(t.stake_total),
            _dec(t.avg_odds),
            _dec(t.commission_pct),
            t.market_type.value,
            t.pnl_mode.value,
            position_side,
            t.outcome_label or "",
            _dec(t.cashout_odds),
            _dec(t.manual_pnl_eur),
            t.status.value,
            _int(t.ht_score_home),
            _int(t.ht_score_away),
            _int(t.ft_score_home),
            _int(t.ft_score_away),
            "|".join(tg.name for tg in t.tags) if t.tags else "",
            json.dumps(sd, separators=(",", ":"), ensure_ascii=False) if sd else "",
            t.notes_md or "",
            _dec(t.computed_pnl_eur),
        ])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@dataclass
class CsvRowError:
    row_index: int  # 1-based, excluding the header
    column: str | None
    detail: str


@dataclass
class ImportResult:
    parsed_rows: int
    valid_rows: int
    errors: list[CsvRowError]
    inserted: int  # 0 if dry-run
    dry_run: bool


def _parse_iso(value: str, *, allow_blank: bool = False) -> datetime | None:
    value = value.strip()
    if not value:
        if allow_blank:
            return None
        raise ValueError("required datetime")
    return datetime.fromisoformat(value)


def _parse_dec(value: str, *, allow_blank: bool = False) -> Decimal | None:
    value = value.strip()
    if not value:
        if allow_blank:
            return None
        raise ValueError("required decimal")
    try:
        return Decimal(value)
    except InvalidOperation as e:
        raise ValueError(f"invalid decimal {value!r}") from e


def _parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"invalid integer {value!r}") from e


def _parse_enum(value: str, enum_cls, *, default=None):
    value = value.strip()
    if not value and default is not None:
        return default
    try:
        return enum_cls(value)
    except ValueError as e:
        valid = ", ".join(e.value for e in enum_cls)
        raise ValueError(f"unknown {enum_cls.__name__} {value!r}; expected one of {valid}") from e


async def _resolve_strategies(
    db: AsyncSession, slugs: set[str]
) -> dict[str, Strategy]:
    if not slugs:
        return {}
    res = await db.execute(select(Strategy).where(Strategy.slug.in_(slugs)))
    return {s.slug: s for s in res.scalars()}


async def _resolve_accounts(
    db: AsyncSession, names: set[str]
) -> dict[str, Account]:
    """Match account names against the active accounts (case-sensitive)."""
    if not names:
        return {}
    res = await db.execute(
        select(Account).where(
            Account.name.in_(names), Account.archived_at.is_(None)
        )
    )
    return {a.name: a for a in res.scalars()}


async def _default_account_id(db: AsyncSession) -> uuid.UUID | None:
    res = await db.execute(select(AppSettings.default_account_id))
    return res.scalar_one_or_none()


async def _resolve_or_create_tags(db: AsyncSession, names: set[str]) -> dict[str, Tag]:
    if not names:
        return {}
    res = await db.execute(select(Tag).where(Tag.name.in_(names)))
    by_name = {t.name: t for t in res.scalars()}
    missing = names - by_name.keys()
    for n in missing:
        t = Tag(name=n)
        db.add(t)
        by_name[n] = t
    if missing:
        await db.flush()
    return by_name


def _parse_row(row: dict[str, str]) -> dict:
    """Parse a single CSV row into a dict ready for Trade(**parsed). Raises ValueError on bad input."""
    sd_raw = (row.get("strategy_data") or "").strip()
    sd = json.loads(sd_raw) if sd_raw else {}
    if not isinstance(sd, dict):
        raise ValueError("strategy_data must be a JSON object")

    position_side = (row.get("position_side") or "").strip().lower()
    if position_side:
        if position_side not in ("back", "lay"):
            raise ValueError("position_side must be 'back' or 'lay'")
        sd["position_side"] = position_side
    elif "position_side" in sd:
        # Already inside strategy_data — leave as-is.
        pass

    parsed = {
        "kickoff_at":       _parse_iso(row.get("kickoff_at", "")),
        "closed_at":        _parse_iso(row.get("closed_at", ""), allow_blank=True),
        "strategy_slug":    (row.get("strategy_slug") or "").strip(),
        "account_name":     (row.get("account_name") or "").strip(),
        "home_team":        (row.get("home_team") or "").strip(),
        "away_team":        (row.get("away_team") or "").strip(),
        "league":           (row.get("league") or "").strip(),
        "stake_total":      _parse_dec(row.get("stake_total", "")),
        "avg_odds":         _parse_dec(row.get("avg_odds", "")),
        "commission_pct":   _parse_dec(row.get("commission_pct", ""), allow_blank=True) or Decimal("5.00"),
        "market_type":      _parse_enum(row.get("market_type") or "exchange", MarketType, default=MarketType.exchange),
        "pnl_mode":         _parse_enum(row.get("pnl_mode") or "MANUAL", PnLMode, default=PnLMode.MANUAL),
        "outcome_label":    (row.get("outcome_label") or "").strip() or None,
        "cashout_odds":     _parse_dec(row.get("cashout_odds", ""), allow_blank=True),
        "manual_pnl_eur":   _parse_dec(row.get("manual_pnl_eur", ""), allow_blank=True),
        "status":           _parse_enum(row.get("status") or "OPEN", TradeStatus, default=TradeStatus.OPEN),
        "ht_score_home":    _parse_int(row.get("ht_score_home", "")),
        "ht_score_away":    _parse_int(row.get("ht_score_away", "")),
        "ft_score_home":    _parse_int(row.get("ft_score_home", "")),
        "ft_score_away":    _parse_int(row.get("ft_score_away", "")),
        "notes_md":         (row.get("notes_md") or "") or None,
        "strategy_data":    sd,
        "tags":             [t.strip() for t in (row.get("tags") or "").split("|") if t.strip()],
    }

    # Cross-field sanity
    if not parsed["home_team"] or not parsed["away_team"]:
        raise ValueError("home_team and away_team are required")
    if not parsed["league"]:
        raise ValueError("league is required")
    if not parsed["strategy_slug"]:
        raise ValueError("strategy_slug is required")
    if parsed["pnl_mode"] is PnLMode.MANUAL and parsed["manual_pnl_eur"] is None:
        raise ValueError("manual_pnl_eur is required when pnl_mode=MANUAL")
    if parsed["pnl_mode"] is PnLMode.CASHOUT_ODDS and parsed["cashout_odds"] is None:
        raise ValueError("cashout_odds is required when pnl_mode=CASHOUT_ODDS")

    return parsed


async def import_trades_csv(
    db: AsyncSession, csv_text: str, *, dry_run: bool = True
) -> ImportResult:
    """Parse a CSV string and either preview or commit the trades.

    Each row is validated independently — a bad row is collected as an
    error but does not abort sibling rows. With ``dry_run=True`` nothing
    is written; with ``dry_run=False`` valid rows are inserted in a single
    transaction (commit) and errored rows are simply skipped.
    """
    reader = csv.DictReader(io.StringIO(csv_text))

    # Validate header.
    missing = set(CSV_COLUMNS) - set(reader.fieldnames or [])
    extra = set(reader.fieldnames or []) - set(CSV_COLUMNS)
    if missing:
        return ImportResult(
            parsed_rows=0,
            valid_rows=0,
            errors=[
                CsvRowError(
                    row_index=0, column=None,
                    detail=f"missing columns: {', '.join(sorted(missing))}",
                )
            ],
            inserted=0,
            dry_run=dry_run,
        )
    # Extra columns are non-fatal but reported as a warning row.
    warnings: list[CsvRowError] = []
    if extra:
        warnings.append(
            CsvRowError(
                row_index=0, column=None,
                detail=f"ignoring unknown columns: {', '.join(sorted(extra))}",
            )
        )

    parsed_rows: list[tuple[int, dict]] = []
    errors: list[CsvRowError] = list(warnings)
    for i, row in enumerate(reader, start=1):
        try:
            parsed = _parse_row(row)
            parsed_rows.append((i, parsed))
        except ValueError as e:
            errors.append(CsvRowError(row_index=i, column=None, detail=str(e)))
        except json.JSONDecodeError as e:
            errors.append(
                CsvRowError(row_index=i, column="strategy_data", detail=f"invalid JSON: {e}")
            )

    # Resolve strategies by slug (one query).
    slugs = {p["strategy_slug"] for _, p in parsed_rows}
    strat_by_slug = await _resolve_strategies(db, slugs)

    # Resolve accounts by name (one query). Blank cells fall back to the
    # `app_settings.default_account_id` — fetched lazily on first need.
    account_names = {p["account_name"] for _, p in parsed_rows if p["account_name"]}
    acct_by_name = await _resolve_accounts(db, account_names)
    default_acct_id: uuid.UUID | None = None
    default_loaded = False

    valid: list[tuple[int, dict]] = []
    for i, p in parsed_rows:
        if p["strategy_slug"] not in strat_by_slug:
            errors.append(
                CsvRowError(
                    row_index=i, column="strategy_slug",
                    detail=f"unknown strategy slug {p['strategy_slug']!r}",
                )
            )
            continue

        if p["account_name"]:
            account = acct_by_name.get(p["account_name"])
            if account is None:
                errors.append(
                    CsvRowError(
                        row_index=i, column="account_name",
                        detail=f"unknown account name {p['account_name']!r}",
                    )
                )
                continue
            p["account_id"] = account.id
        else:
            if not default_loaded:
                default_acct_id = await _default_account_id(db)
                default_loaded = True
            if default_acct_id is None:
                errors.append(
                    CsvRowError(
                        row_index=i, column="account_name",
                        detail="account_name is blank and no default account is configured",
                    )
                )
                continue
            p["account_id"] = default_acct_id

        valid.append((i, p))

    inserted = 0
    if not dry_run and valid:
        # Resolve tags up front (one query) and create the missing ones.
        all_tags = {n for _, p in valid for n in p["tags"]}
        tag_by_name = await _resolve_or_create_tags(db, all_tags)

        for _, p in valid:
            strategy = strat_by_slug[p["strategy_slug"]]
            inputs = PnLInputs(
                pnl_mode=p["pnl_mode"],
                stake_total=p["stake_total"],
                avg_odds=p["avg_odds"],
                commission_pct=p["commission_pct"],
                market_type=p["market_type"],
                cashout_odds=p["cashout_odds"],
                position_side=p["strategy_data"].get("position_side"),
                manual_pnl_eur=p["manual_pnl_eur"],
                outcome_label=p["outcome_label"],
                strategy_data=p["strategy_data"],
            )
            pnl = compute_pnl(inputs)

            trade = Trade(
                strategy_id=strategy.id,
                account_id=p["account_id"],
                home_team=p["home_team"],
                away_team=p["away_team"],
                league=p["league"],
                kickoff_at=p["kickoff_at"],
                closed_at=p["closed_at"],
                ht_score_home=p["ht_score_home"],
                ht_score_away=p["ht_score_away"],
                ft_score_home=p["ft_score_home"],
                ft_score_away=p["ft_score_away"],
                stake_total=p["stake_total"],
                avg_odds=p["avg_odds"],
                commission_pct=p["commission_pct"],
                market_type=p["market_type"],
                pnl_mode=p["pnl_mode"],
                cashout_odds=p["cashout_odds"],
                manual_pnl_eur=p["manual_pnl_eur"],
                computed_pnl_eur=pnl,
                outcome_label=p["outcome_label"],
                status=p["status"],
                strategy_data=p["strategy_data"],
                notes_md=p["notes_md"],
                tags=[tag_by_name[n] for n in p["tags"]],
            )
            db.add(trade)
            inserted += 1
        await db.commit()

    return ImportResult(
        parsed_rows=len(parsed_rows) + len(
            [e for e in errors if e.row_index > 0 and e.detail not in (w.detail for w in warnings)]
        ),
        valid_rows=len(valid),
        errors=errors,
        inserted=inserted,
        dry_run=dry_run,
    )


# Eagerly load Trade with strategy + tags for export.
async def all_trades_for_export(db: AsyncSession) -> list[Trade]:
    res = await db.execute(
        select(Trade)
        .options(
            selectinload(Trade.strategy),
            selectinload(Trade.account),
            selectinload(Trade.tags),
        )
        .order_by(Trade.kickoff_at)
    )
    return list(res.scalars().all())
