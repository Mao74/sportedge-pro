"""Trades API integration tests.

Covers all three PnL modes round-tripped (POST → GET → assert pnl), the
strategy_data validator, filtering, pagination, aggregates, the close
shortcut, and tag attach/detach.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

UTC = timezone.utc


def _strategy_id(client: TestClient, slug: str) -> str:
    items = client.get("/api/v1/strategies").json()
    return next(s["id"] for s in items if s["slug"] == slug)


def _custom_strategy(client: TestClient, name: str = "Custom A") -> dict:
    resp = client.post(
        "/api/v1/strategies",
        json={
            "name": name,
            "color_hex": "#4DA3FF",
            "field_schema": {"fields": [
                {"key": "scenario", "label": "Scenario", "type": "select",
                 "options": ["WIN", "LOSS", "VOID"]},
            ]},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _base_trade(strategy_id: str, **overrides) -> dict:
    base = {
        "strategy_id": strategy_id,
        "home_team": "Inter",
        "away_team": "Lazio",
        "league": "Serie A",
        "kickoff_at": "2026-04-28T20:45:00+02:00",
        "stake_total": "100.00",
        "avg_odds": "2.50",
        "commission_pct": "5.00",
        "pnl_mode": "AUTO",
        "position_side": "back",
        "outcome_label": "WIN",
        "strategy_data": {"scenario": "WIN"},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Create — three PnL modes round-trip
# ---------------------------------------------------------------------------


class TestCreatePnLModes:
    def test_auto_back_win_round_trip(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        body = _base_trade(sid)
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # 100 * (2.5 - 1) * 0.95 = 142.50
        assert data["computed_pnl_eur"] == "142.50"
        assert data["pnl_mode"] == "AUTO"
        assert data["status"] == "OPEN"
        # Default market_type is 'exchange' when omitted.
        assert data["market_type"] == "exchange"

        # Round-trip: GET returns the same value
        got = client_with_auth.get(f"/api/v1/trades/{data['id']}").json()
        assert got["computed_pnl_eur"] == "142.50"

    def test_classic_market_skips_commission(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        body = _base_trade(sid, market_type="classic")
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # Same stake/odds as the exchange case, but no commission applied
        # because market_type=classic → cf=1.0 → 100 * 1.5 * 1.0 = 150.00
        assert data["computed_pnl_eur"] == "150.00"
        assert data["market_type"] == "classic"

    def test_patch_market_type_recomputes_pnl(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        created = client_with_auth.post(
            "/api/v1/trades", json=_base_trade(sid)
        ).json()
        assert created["computed_pnl_eur"] == "142.50"
        patched = client_with_auth.patch(
            f"/api/v1/trades/{created['id']}", json={"market_type": "classic"}
        ).json()
        assert patched["market_type"] == "classic"
        assert patched["computed_pnl_eur"] == "150.00"

    def test_manual_round_trip(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        body = _base_trade(
            sid,
            pnl_mode="MANUAL",
            position_side=None,
            outcome_label=None,
            manual_pnl_eur="42.50",
            strategy_data={},
        )
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 201, resp.text
        assert resp.json()["computed_pnl_eur"] == "42.50"

    def test_cashout_odds_round_trip(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        body = _base_trade(
            sid,
            pnl_mode="CASHOUT_ODDS",
            cashout_odds="1.45",
            position_side="back",
            outcome_label=None,
            stake_total="62.00",
            avg_odds="5.42",
            strategy_data={},
        )
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 201, resp.text
        # 62 * (1.45 - 1) * 0.95 = 26.505 → 26.50 (HALF_EVEN)
        assert resp.json()["computed_pnl_eur"] == "26.50"


# ---------------------------------------------------------------------------
# strategy_data validation
# ---------------------------------------------------------------------------


class TestStrategyDataValidation:
    def test_required_field_missing_close_status(self, client_with_auth: TestClient) -> None:
        # Build a strategy with a field required only when CLOSED.
        sresp = client_with_auth.post(
            "/api/v1/strategies",
            json={
                "name": "Strict",
                "field_schema": {"fields": [
                    {"key": "exit_type", "label": "Exit", "type": "select",
                     "options": ["WIN", "LOSS"], "required_for_status": "CLOSED"}
                ]},
            },
        )
        sid = sresp.json()["id"]
        # POST with status=OPEN and no exit_type → OK (not required for OPEN)
        ok = client_with_auth.post("/api/v1/trades", json=_base_trade(
            sid, strategy_data={}, outcome_label="WIN"
        ))
        assert ok.status_code == 201, ok.text
        # POST with status=CLOSED and no exit_type → 422
        bad = client_with_auth.post("/api/v1/trades", json=_base_trade(
            sid, status="CLOSED", strategy_data={}, outcome_label="WIN"
        ))
        assert bad.status_code == 422, bad.text
        assert "exit_type" in bad.text

    def test_chip_picker_min_max_picks(self, client_with_auth: TestClient) -> None:
        sresp = client_with_auth.post(
            "/api/v1/strategies",
            json={
                "name": "Picker",
                "field_schema": {"fields": [
                    {"key": "picks", "label": "Picks", "type": "chip-picker",
                     "options": ["a", "b", "c", "d"], "min_picks": 2, "max_picks": 3}
                ]},
            },
        )
        sid = sresp.json()["id"]
        # too few
        too_few = client_with_auth.post("/api/v1/trades", json=_base_trade(
            sid, strategy_data={"picks": ["a"]}, outcome_label="WIN"
        ))
        assert too_few.status_code == 422
        # too many
        too_many = client_with_auth.post("/api/v1/trades", json=_base_trade(
            sid, strategy_data={"picks": ["a", "b", "c", "d"]}, outcome_label="WIN"
        ))
        assert too_many.status_code == 422
        # just right
        ok = client_with_auth.post("/api/v1/trades", json=_base_trade(
            sid, strategy_data={"picks": ["a", "b"]}, outcome_label="WIN"
        ))
        assert ok.status_code == 201

    def test_unknown_strategy_returns_404(self, client_with_auth: TestClient) -> None:
        body = _base_trade(str(uuid.uuid4()))
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH — PnL recompute on PnL-affecting change
# ---------------------------------------------------------------------------


class TestPatchRecompute:
    def test_changing_outcome_recomputes_pnl(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        created = client_with_auth.post("/api/v1/trades", json=_base_trade(sid)).json()
        # WIN → 142.50
        assert created["computed_pnl_eur"] == "142.50"
        # Flip to LOSS → -100.00
        patched = client_with_auth.patch(
            f"/api/v1/trades/{created['id']}",
            json={"outcome_label": "LOSS", "strategy_data": {"scenario": "LOSS"}},
        ).json()
        assert patched["computed_pnl_eur"] == "-100.00"

    def test_patching_only_notes_does_not_change_pnl(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        created = client_with_auth.post("/api/v1/trades", json=_base_trade(sid)).json()
        original_pnl = created["computed_pnl_eur"]
        patched = client_with_auth.patch(
            f"/api/v1/trades/{created['id']}", json={"notes_md": "good trade"}
        ).json()
        assert patched["computed_pnl_eur"] == original_pnl
        assert patched["notes_md"] == "good trade"


# ---------------------------------------------------------------------------
# Close shortcut
# ---------------------------------------------------------------------------


class TestCloseShortcut:
    def test_close_sets_status_and_recomputes(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        # Create OPEN with placeholder MANUAL pnl=0
        created = client_with_auth.post("/api/v1/trades", json=_base_trade(
            sid, pnl_mode="MANUAL", position_side=None, outcome_label=None,
            manual_pnl_eur="0.00", strategy_data={},
        )).json()
        assert created["status"] == "OPEN"
        # Close it via the shortcut, switching to CASHOUT_ODDS at 1.50
        closed = client_with_auth.post(
            f"/api/v1/trades/{created['id']}/close",
            json={
                "pnl_mode": "CASHOUT_ODDS",
                "cashout_odds": "1.50",
                "position_side": "back",
            },
        )
        assert closed.status_code == 200, closed.text
        body = closed.json()
        assert body["status"] == "CLOSED"
        assert body["closed_at"] is not None
        # 100 * (1.5 - 1) * 0.95 = 47.50
        assert body["computed_pnl_eur"] == "47.50"


# ---------------------------------------------------------------------------
# Tags inline + attach + detach
# ---------------------------------------------------------------------------


class TestTagging:
    def test_tags_created_inline_on_post(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        body = _base_trade(sid)
        body["tags"] = ["live", "high-xg"]
        resp = client_with_auth.post("/api/v1/trades", json=body)
        assert resp.status_code == 201
        names = sorted(t["name"] for t in resp.json()["tags"])
        assert names == ["high-xg", "live"]

        # Both tags now appear in /tags with usage counts
        tags = client_with_auth.get("/api/v1/tags").json()
        usage = {t["name"]: t["n_trades"] for t in tags}
        assert usage["live"] == 1
        assert usage["high-xg"] == 1

    def test_attach_tag_by_name_creates_if_missing(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        created = client_with_auth.post("/api/v1/trades", json=_base_trade(sid)).json()
        resp = client_with_auth.post(
            f"/api/v1/trades/{created['id']}/tags", json={"name": "fresh-tag"}
        )
        assert resp.status_code == 200
        assert any(t["name"] == "fresh-tag" for t in resp.json()["tags"])

    def test_detach_tag(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        body = _base_trade(sid)
        body["tags"] = ["x", "y"]
        created = client_with_auth.post("/api/v1/trades", json=body).json()
        tag_id = next(t["id"] for t in created["tags"] if t["name"] == "x")
        resp = client_with_auth.delete(f"/api/v1/trades/{created['id']}/tags/{tag_id}")
        assert resp.status_code == 204
        after = client_with_auth.get(f"/api/v1/trades/{created['id']}").json()
        assert [t["name"] for t in after["tags"]] == ["y"]


# ---------------------------------------------------------------------------
# List + filter + paginate + aggregates
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def _seed_three_trades(self, client: TestClient) -> tuple[str, list[dict]]:
        sid = _custom_strategy(client)["id"]
        # closed, win
        t1 = client.post("/api/v1/trades", json=_base_trade(
            sid, status="CLOSED", outcome_label="WIN", strategy_data={"scenario": "WIN"},
            kickoff_at="2026-04-25T20:00:00+00:00",
        )).json()
        # closed, loss
        t2 = client.post("/api/v1/trades", json=_base_trade(
            sid, status="CLOSED", outcome_label="LOSS", strategy_data={"scenario": "LOSS"},
            kickoff_at="2026-04-26T20:00:00+00:00",
        )).json()
        # open, no outcome yet
        t3 = client.post("/api/v1/trades", json=_base_trade(
            sid, status="OPEN", outcome_label="WIN", strategy_data={"scenario": "WIN"},
            kickoff_at="2026-04-27T20:00:00+00:00",
        )).json()
        return sid, [t1, t2, t3]

    def test_list_returns_all_with_aggregates_only_for_closed(
        self, client_with_auth: TestClient
    ) -> None:
        _, _ = self._seed_three_trades(client_with_auth)
        resp = client_with_auth.get("/api/v1/trades").json()
        assert resp["total"] == 3
        # Closed: 1 win (142.50) + 1 loss (-100.00) = 42.50; stake 200 → ROI 21.25
        assert resp["aggregates"]["n_trades"] == 2
        assert resp["aggregates"]["sum_pnl_eur"] == "42.50"
        assert resp["aggregates"]["sum_stake_eur"] == "200.00"
        assert resp["aggregates"]["roi_pct"] == "21.2500"
        assert resp["aggregates"]["win_rate_pct"] == "50.0000"

    def test_filter_by_status(self, client_with_auth: TestClient) -> None:
        self._seed_three_trades(client_with_auth)
        closed = client_with_auth.get("/api/v1/trades", params={"status": "CLOSED"}).json()
        assert closed["total"] == 2
        opened = client_with_auth.get("/api/v1/trades", params={"status": "OPEN"}).json()
        assert opened["total"] == 1

    def test_filter_by_outcome_label(self, client_with_auth: TestClient) -> None:
        self._seed_three_trades(client_with_auth)
        wins = client_with_auth.get("/api/v1/trades", params={"outcome_label": "WIN"}).json()
        assert wins["total"] == 2  # one closed, one open both with outcome_label=WIN

    def test_filter_by_pnl_range(self, client_with_auth: TestClient) -> None:
        self._seed_three_trades(client_with_auth)
        positives = client_with_auth.get("/api/v1/trades", params={"pnl_min": "0"}).json()
        # Win+open(=142.50) ≥ 0; loss(-100) < 0
        assert positives["total"] == 2

    def test_filter_by_date_range(self, client_with_auth: TestClient) -> None:
        self._seed_three_trades(client_with_auth)
        resp = client_with_auth.get(
            "/api/v1/trades",
            params={
                "date_from": "2026-04-26T00:00:00+00:00",
                "date_to": "2026-04-26T23:59:59+00:00",
            },
        ).json()
        assert resp["total"] == 1

    def test_filter_by_tag(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        a = _base_trade(sid)
        a["tags"] = ["live"]
        client_with_auth.post("/api/v1/trades", json=a)
        b = _base_trade(sid)
        b["tags"] = ["analytical"]
        client_with_auth.post("/api/v1/trades", json=b)
        resp = client_with_auth.get("/api/v1/trades", params={"tag": "live"}).json()
        assert resp["total"] == 1

    def test_pagination(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        for i in range(5):
            body = _base_trade(sid, kickoff_at=f"2026-04-{20 + i:02d}T20:00:00+00:00")
            client_with_auth.post("/api/v1/trades", json=body)
        first = client_with_auth.get(
            "/api/v1/trades", params={"page": 1, "page_size": 2, "sort": "kickoff_at"}
        ).json()
        assert first["total"] == 5
        assert len(first["items"]) == 2
        assert first["page"] == 1
        second = client_with_auth.get(
            "/api/v1/trades", params={"page": 3, "page_size": 2, "sort": "kickoff_at"}
        ).json()
        assert len(second["items"]) == 1  # last page has remainder

    def test_full_text_search(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        a = _base_trade(sid, home_team="Real Madrid", away_team="Atletico")
        client_with_auth.post("/api/v1/trades", json=a)
        b = _base_trade(sid, home_team="Bayern", away_team="Dortmund")
        client_with_auth.post("/api/v1/trades", json=b)
        resp = client_with_auth.get("/api/v1/trades", params={"q": "real"}).json()
        assert resp["total"] == 1
        assert resp["items"][0]["home_team"] == "Real Madrid"

    def test_filter_by_kickoff_dow_and_hour(self, client_with_auth: TestClient) -> None:
        # Create three trades on different days/times so we can isolate one cell.
        sid = _custom_strategy(client_with_auth)["id"]
        # 2026-04-28 = Tuesday (Python weekday=1) at 14:00 UTC
        client_with_auth.post(
            "/api/v1/trades",
            json=_base_trade(sid, home_team="A", kickoff_at="2026-04-28T14:00:00+00:00"),
        )
        # 2026-04-28 Tue at 20:00 UTC
        client_with_auth.post(
            "/api/v1/trades",
            json=_base_trade(sid, home_team="B", kickoff_at="2026-04-28T20:00:00+00:00"),
        )
        # 2026-05-02 = Saturday (weekday=5) at 20:00 UTC
        client_with_auth.post(
            "/api/v1/trades",
            json=_base_trade(sid, home_team="C", kickoff_at="2026-05-02T20:00:00+00:00"),
        )
        # Filter on Tuesday only → 2 results
        tue = client_with_auth.get(
            "/api/v1/trades", params={"kickoff_dow": 1}
        ).json()
        assert tue["total"] == 2
        # Filter on Tuesday + 14:00 → 1 result
        cell = client_with_auth.get(
            "/api/v1/trades", params={"kickoff_dow": 1, "kickoff_hour": 14}
        ).json()
        assert cell["total"] == 1
        assert cell["items"][0]["home_team"] == "A"
        # Out-of-range value rejected
        bad = client_with_auth.get("/api/v1/trades", params={"kickoff_dow": 9})
        assert bad.status_code == 422


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_removes_trade(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        created = client_with_auth.post("/api/v1/trades", json=_base_trade(sid)).json()
        resp = client_with_auth.delete(f"/api/v1/trades/{created['id']}")
        assert resp.status_code == 204
        assert client_with_auth.get(f"/api/v1/trades/{created['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    def test_list_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/trades").status_code == 401
