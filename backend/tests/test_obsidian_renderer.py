"""Renderer unit tests. Build a Trade-like object and assert the rendered
markdown contains the structural pieces, frontmatter parses, and the
USER_EDITABLE block round-trips."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import frontmatter

from app.models import MarketType, PnLMode, TradeStatus
from app.services.obsidian.markers import extract_user_editable
from app.services.obsidian.templates import (
    render_bankroll_dashboard,
    render_daily,
    render_readme,
    render_strategy,
    render_trade,
    trade_filename,
)


def _stub_strategy(name="Magic CS", slug="magic-cs", color="#8B7FFF"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        color_hex=color,
        kind=SimpleNamespace(value="builtin"),
        description="multi-CS portfolio",
    )


def _stub_account(name="Betfair", venue="betfair"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        venue=venue,
        market_type=MarketType.exchange,
        commission_pct=Decimal("5.00"),
    )


def _stub_trade(**overrides):
    base = SimpleNamespace(
        id=uuid.uuid4(),
        strategy=_stub_strategy(),
        account=_stub_account(),
        sport="football",
        home_team="Inter",
        away_team="Lazio",
        league="Serie A",
        kickoff_at=datetime(2026, 4, 28, 20, 45, tzinfo=UTC),
        ht_score_home=None,
        ht_score_away=None,
        ft_score_home=None,
        ft_score_away=None,
        stake_total=Decimal("62.00"),
        avg_odds=Decimal("5.42"),
        commission_pct=Decimal("5.00"),
        market_type=MarketType.exchange,
        pnl_mode=PnLMode.AUTO,
        cashout_odds=None,
        manual_pnl_eur=None,
        computed_pnl_eur=Decimal("41.20"),
        outcome_label="A2_OVER25",
        status=TradeStatus.CLOSED,
        closed_at=datetime(2026, 4, 28, 22, 30, tzinfo=UTC),
        strategy_data={"scenario": "A2_OVER25", "lay_00_stake": 10},
        notes_md="xG asymmetry favorevole.",
        tags=[SimpleNamespace(name="protocol-clean"), SimpleNamespace(name="high-xg")],
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_trade_filename_format() -> None:
    t = _stub_trade()
    assert trade_filename(t) == "2026-04-28 Inter vs Lazio.md"


class TestRenderTrade:
    def test_frontmatter_parseable(self) -> None:
        t = _stub_trade()
        out = render_trade(t, now=datetime(2026, 4, 28, 22, 31, tzinfo=UTC))
        doc = frontmatter.loads(out)
        assert doc["app_managed"] is True
        assert doc["trade_id"] == str(t.id)
        assert doc["computed_pnl_eur"] == "41.20"
        assert doc["outcome_label"] == "A2_OVER25"
        assert doc["status"] == "CLOSED"
        assert doc["account"] == "Betfair"
        assert doc["account_venue"] == "betfair"

    def test_user_editable_block_present_with_initial_notes(self) -> None:
        t = _stub_trade()
        out = render_trade(t, now=datetime(2026, 4, 28, 22, 31, tzinfo=UTC))
        ub = extract_user_editable(out)
        assert ub == "xG asymmetry favorevole."

    def test_user_editable_block_preserved_across_re_export(self) -> None:
        t = _stub_trade()
        first = render_trade(t, now=datetime(2026, 4, 28, 22, 31, tzinfo=UTC))
        # User has hand-edited the notes section; pretend the file looks
        # different from the DB notes_md now.
        existing = first.replace(
            "xG asymmetry favorevole.",
            "xG favorevole.\nCash-out parziale a 2-1.\nNuova nota.",
        )
        # Re-export: pass existing_text. The new render must keep the user text.
        second = render_trade(
            t, now=datetime(2026, 4, 29, 9, 0, tzinfo=UTC), existing_text=existing
        )
        ub = extract_user_editable(second)
        assert ub is not None
        assert "Nuova nota." in ub
        # And the frontmatter has bumped last_synced_at.
        assert "2026-04-29" in frontmatter.loads(second)["last_synced_at"]

    def test_tags_render_as_hashtags(self) -> None:
        t = _stub_trade()
        out = render_trade(t, now=datetime(2026, 4, 28, 22, 31, tzinfo=UTC))
        assert "#protocol-clean" in out
        assert "#high-xg" in out

    def test_no_tags_renders_no_tags_marker(self) -> None:
        t = _stub_trade(tags=[])
        out = render_trade(t, now=datetime(2026, 4, 28, 22, 31, tzinfo=UTC))
        assert "_no tags_" in out


class TestRenderDaily:
    def test_renders_with_no_trades(self) -> None:
        out = render_daily(
            day=date(2026, 4, 28),
            trades=[],
            bankroll_eod=Decimal("1000.00"),
            bankroll_sod=Decimal("1000.00"),
        )
        doc = frontmatter.loads(out)
        assert doc["trades_count"] == 0
        assert "_no closed trades on this day_" in out

    def test_renders_with_trades(self) -> None:
        t = _stub_trade()
        out = render_daily(
            day=date(2026, 4, 28),
            trades=[t],
            bankroll_eod=Decimal("1041.20"),
            bankroll_sod=Decimal("1000.00"),
        )
        assert "Inter vs Lazio" in out
        assert "+€41.20" in out
        assert "Magic CS" in out

    def test_user_editable_reflection_preserved(self) -> None:
        first = render_daily(
            day=date(2026, 4, 28),
            trades=[],
            bankroll_eod=Decimal("1000.00"),
            bankroll_sod=Decimal("1000.00"),
        )
        existing = first.replace(
            "*write your post-session reflection here*",
            "Today felt patient. Stuck to protocol on the late-window setup.",
        )
        second = render_daily(
            day=date(2026, 4, 28),
            trades=[],
            bankroll_eod=Decimal("1000.00"),
            bankroll_sod=Decimal("1000.00"),
            existing_text=existing,
        )
        ub = extract_user_editable(second)
        assert ub is not None
        assert "patient" in ub


class TestRenderStrategyAndDashboards:
    def test_strategy_includes_dataview_query(self) -> None:
        s = _stub_strategy()
        out = render_strategy(s)
        assert "```dataview" in out
        assert 'WHERE strategy_slug = "magic-cs"' in out

    def test_bankroll_dashboard_dataview(self) -> None:
        out = render_bankroll_dashboard()
        assert "```dataview" in out
        assert "FROM \"Trades\"" in out

    def test_readme_self_describing(self) -> None:
        out = render_readme()
        assert "USER_EDITABLE_START" in out
        assert "_meta/_conflicts/" in out
