"""Bankroll API integration tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _bare_strategy(client: TestClient) -> dict:
    return client.post(
        "/api/v1/strategies", json={"name": "Bare", "field_schema": {"fields": []}}
    ).json()


def _post_closed_trade(
    client: TestClient, sid: str, pnl: str, kickoff: str, closed_at: str | None = None
) -> dict:
    body = {
        "strategy_id": sid,
        "home_team": "A", "away_team": "B", "league": "X",
        "kickoff_at": kickoff,
        "stake_total": "100.00", "avg_odds": "2.50",
        "pnl_mode": "MANUAL", "manual_pnl_eur": pnl,
        "status": "CLOSED",
        "closed_at": closed_at or kickoff,
    }
    resp = client.post("/api/v1/trades", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestBankrollCurrent:
    def test_current_with_no_activity_equals_starting(
        self, client_with_auth: TestClient
    ) -> None:
        resp = client_with_auth.get("/api/v1/bankroll/current")
        assert resp.status_code == 200
        body = resp.json()
        starting = Decimal(get_settings().default_starting_bankroll)
        assert Decimal(body["balance_eur"]) == starting
        assert body["last_snapshot_at"] is None
        assert Decimal(body["since_inception_pnl_eur"]) == Decimal("0")

    def test_current_includes_closed_pnl(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post_closed_trade(client_with_auth, sid, "50.00", "2026-04-25T20:00:00+00:00")
        _post_closed_trade(client_with_auth, sid, "-30.00", "2026-04-26T20:00:00+00:00")
        resp = client_with_auth.get("/api/v1/bankroll/current").json()
        starting = Decimal(get_settings().default_starting_bankroll)
        assert Decimal(resp["balance_eur"]) == starting + Decimal("20")  # +50 -30
        assert Decimal(resp["since_inception_pnl_eur"]) == Decimal("20.00")
        # ROI = 20/200 * 100 = 10%
        assert Decimal(resp["since_inception_roi_pct"]) == Decimal("10.0000")


class TestBankrollAdjust:
    def test_deposit_increases_balance(self, client_with_auth: TestClient) -> None:
        starting = Decimal(get_settings().default_starting_bankroll)
        before = client_with_auth.get("/api/v1/bankroll/current").json()
        assert Decimal(before["balance_eur"]) == starting
        resp = client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "250.00", "kind": "deposit", "notes": "test"},
        )
        assert resp.status_code == 201
        snap = resp.json()
        assert Decimal(snap["deposit_eur"]) == Decimal("250.00")
        assert Decimal(snap["balance_eur"]) == starting + Decimal("250")
        # current reflects the new balance
        after = client_with_auth.get("/api/v1/bankroll/current").json()
        assert Decimal(after["balance_eur"]) == starting + Decimal("250")

    def test_withdrawal_decreases_balance(self, client_with_auth: TestClient) -> None:
        starting = Decimal(get_settings().default_starting_bankroll)
        resp = client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "100.00", "kind": "withdrawal"},
        )
        assert resp.status_code == 201
        after = client_with_auth.get("/api/v1/bankroll/current").json()
        assert Decimal(after["balance_eur"]) == starting - Decimal("100")

    def test_negative_amount_rejected(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "-10.00", "kind": "deposit"},
        )
        assert resp.status_code == 422


class TestBankrollSnapshot:
    def test_snapshot_writes_balance(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post_closed_trade(client_with_auth, sid, "75.00", "2026-04-25T20:00:00+00:00")
        resp = client_with_auth.post("/api/v1/bankroll/snapshot")
        assert resp.status_code == 201
        snap = resp.json()
        starting = Decimal(get_settings().default_starting_bankroll)
        assert Decimal(snap["balance_eur"]) == starting + Decimal("75")
        # last_snapshot_at on /current now reflects the new snapshot
        cur = client_with_auth.get("/api/v1/bankroll/current").json()
        assert cur["last_snapshot_at"] is not None


class TestBankrollSeries:
    def test_series_returns_one_point_per_event_day(
        self, client_with_auth: TestClient
    ) -> None:
        sid = _bare_strategy(client_with_auth)["id"]
        _post_closed_trade(client_with_auth, sid, "20.00", "2026-04-20T20:00:00+00:00")
        _post_closed_trade(client_with_auth, sid, "-10.00", "2026-04-22T20:00:00+00:00")
        _post_closed_trade(client_with_auth, sid, "5.00", "2026-04-22T22:00:00+00:00")
        resp = client_with_auth.get("/api/v1/bankroll/series", params={"range": "all"})
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2  # two distinct days
        starting = Decimal(get_settings().default_starting_bankroll)
        assert Decimal(rows[0]["balance_eur"]) == starting + Decimal("20")
        # Day 2: -10 + 5 = -5
        assert Decimal(rows[1]["day_pnl_eur"]) == Decimal("-5.00")
        assert Decimal(rows[1]["balance_eur"]) == starting + Decimal("15")

    def test_series_empty_with_no_closed_trades(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/bankroll/series", params={"range": "all"}).json()
        assert resp == []


class TestAuth:
    def test_current_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/bankroll/current").status_code == 401
