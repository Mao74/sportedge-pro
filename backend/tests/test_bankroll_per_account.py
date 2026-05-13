"""Per-account bankroll filtering — current + series."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient


def _bare_strategy(client: TestClient) -> str:
    return client.post(
        "/api/v1/strategies",
        json={"name": "Bare", "field_schema": {"fields": []}},
    ).json()["id"]


def _seed_betfair(client: TestClient) -> str:
    return client.get("/api/v1/accounts").json()[0]["id"]


def _create_betflag(client: TestClient) -> str:
    return client.post(
        "/api/v1/accounts",
        json={
            "name": "Betflag",
            "venue": "betflag",
            "market_type": "classic",
            "commission_pct": "0.00",
            "opening_balance": "500.00",
        },
    ).json()["id"]


def _post_closed(
    client: TestClient,
    *,
    sid: str,
    account_id: str,
    pnl: str,
    when: str = "2026-04-25T20:00:00+00:00",
) -> dict:
    body = {
        "strategy_id": sid,
        "account_id": account_id,
        "home_team": "A", "away_team": "B", "league": "X",
        "kickoff_at": when,
        "stake_total": "100.00", "avg_odds": "2.50",
        "pnl_mode": "MANUAL", "manual_pnl_eur": pnl,
        "status": "CLOSED", "closed_at": when,
    }
    resp = client.post("/api/v1/trades", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestPerAccountCurrent:
    def test_current_scoped_to_account(self, client_with_auth: TestClient) -> None:
        sid = _bare_strategy(client_with_auth)
        bf = _seed_betfair(client_with_auth)
        bfl = _create_betflag(client_with_auth)

        _post_closed(client_with_auth, sid=sid, account_id=bf, pnl="50.00")
        _post_closed(client_with_auth, sid=sid, account_id=bfl, pnl="-30.00")

        # Scoped: Betfair sees +50 on top of its 1000 opening
        body = client_with_auth.get(
            "/api/v1/bankroll/current", params={"account_id": bf}
        ).json()
        assert Decimal(body["balance_eur"]) == Decimal("1050.00")
        assert body["account_id"] == bf

        # Scoped: Betflag sees -30 on top of its 500 opening
        body = client_with_auth.get(
            "/api/v1/bankroll/current", params={"account_id": bfl}
        ).json()
        assert Decimal(body["balance_eur"]) == Decimal("470.00")

    def test_current_aggregated_sums_both(
        self, client_with_auth: TestClient
    ) -> None:
        sid = _bare_strategy(client_with_auth)
        bf = _seed_betfair(client_with_auth)
        bfl = _create_betflag(client_with_auth)

        _post_closed(client_with_auth, sid=sid, account_id=bf, pnl="50.00")
        _post_closed(client_with_auth, sid=sid, account_id=bfl, pnl="-30.00")

        body = client_with_auth.get("/api/v1/bankroll/current").json()
        # 1000 + 500 (openings) + 50 - 30 (closed PnL) = 1520
        assert Decimal(body["balance_eur"]) == Decimal("1520.00")
        assert body["account_id"] is None


class TestPerAccountSeries:
    def test_series_excludes_other_account_trades(
        self, client_with_auth: TestClient
    ) -> None:
        sid = _bare_strategy(client_with_auth)
        bf = _seed_betfair(client_with_auth)
        bfl = _create_betflag(client_with_auth)

        _post_closed(
            client_with_auth,
            sid=sid,
            account_id=bf,
            pnl="50.00",
            when="2026-04-25T20:00:00+00:00",
        )
        _post_closed(
            client_with_auth,
            sid=sid,
            account_id=bfl,
            pnl="-30.00",
            when="2026-04-25T20:00:00+00:00",
        )

        bf_series = client_with_auth.get(
            "/api/v1/bankroll/series", params={"account_id": bf, "range": "all"}
        ).json()
        assert len(bf_series) == 1
        assert Decimal(bf_series[0]["day_pnl_eur"]) == Decimal("50.00")

        bfl_series = client_with_auth.get(
            "/api/v1/bankroll/series", params={"account_id": bfl, "range": "all"}
        ).json()
        assert len(bfl_series) == 1
        assert Decimal(bfl_series[0]["day_pnl_eur"]) == Decimal("-30.00")


class TestAdjustFallsBackToDefaultAccount:
    def test_adjust_without_account_id_uses_default(
        self, client_with_auth: TestClient
    ) -> None:
        bf = _seed_betfair(client_with_auth)
        resp = client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "100.00", "kind": "deposit"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["account_id"] == bf

    def test_adjust_explicit_account_id_routes_to_it(
        self, client_with_auth: TestClient
    ) -> None:
        bfl = _create_betflag(client_with_auth)
        resp = client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={
                "amount_eur": "100.00",
                "kind": "deposit",
                "account_id": bfl,
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["account_id"] == bfl


class TestTradeCreateUsesDefaultAccount:
    def test_trade_without_account_id_falls_back_to_default(
        self, client_with_auth: TestClient
    ) -> None:
        sid = _bare_strategy(client_with_auth)
        bf = _seed_betfair(client_with_auth)
        resp = client_with_auth.post(
            "/api/v1/trades",
            json={
                "strategy_id": sid,
                "home_team": "A", "away_team": "B", "league": "X",
                "kickoff_at": "2026-04-25T20:00:00+00:00",
                "stake_total": "100.00", "avg_odds": "2.50",
                "pnl_mode": "MANUAL", "manual_pnl_eur": "10.00",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["account_id"] == bf
