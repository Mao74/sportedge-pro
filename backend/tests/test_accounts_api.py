"""Accounts CRUD API integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _list_accounts(client: TestClient) -> list[dict]:
    resp = client.get("/api/v1/accounts")
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAccountsList:
    def test_seed_account_visible(self, client_with_auth: TestClient) -> None:
        rows = _list_accounts(client_with_auth)
        assert len(rows) == 1
        assert rows[0]["name"] == "Betfair"
        assert rows[0]["venue"] == "betfair"
        assert rows[0]["market_type"] == "exchange"

    def test_include_archived_filter(self, client_with_auth: TestClient) -> None:
        # Create + archive a second account.
        created = client_with_auth.post(
            "/api/v1/accounts",
            json={
                "name": "TempBook",
                "venue": "snai",
                "market_type": "classic",
                "commission_pct": "0.00",
                "opening_balance": "500.00",
            },
        ).json()
        client_with_auth.post(f"/api/v1/accounts/{created['id']}/archive")

        active_only = _list_accounts(client_with_auth)
        assert {a["name"] for a in active_only} == {"Betfair"}

        with_archived = client_with_auth.get(
            "/api/v1/accounts", params={"include_archived": "true"}
        ).json()
        assert {a["name"] for a in with_archived} == {"Betfair", "TempBook"}


class TestAccountsCreate:
    def test_create_classic_account(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/accounts",
            json={
                "name": "Betflag",
                "venue": "betflag",
                "market_type": "classic",
                "commission_pct": "0.00",
                "opening_balance": "1000.00",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "Betflag"
        assert body["market_type"] == "classic"
        assert body["commission_pct"] == "0.00"

    def test_duplicate_name_rejected(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post(
            "/api/v1/accounts",
            json={
                "name": "Betfair",  # same as seed
                "venue": "betfair",
                "market_type": "exchange",
                "commission_pct": "5.00",
                "opening_balance": "0.00",
            },
        )
        assert resp.status_code == 409


class TestAccountsPatch:
    def test_rename_commission(self, client_with_auth: TestClient) -> None:
        rows = _list_accounts(client_with_auth)
        bf = rows[0]
        resp = client_with_auth.patch(
            f"/api/v1/accounts/{bf['id']}",
            json={"commission_pct": "2.50"},
        )
        assert resp.status_code == 200
        assert resp.json()["commission_pct"] == "2.50"


class TestAccountsDelete:
    def test_delete_unused_account_succeeds(
        self, client_with_auth: TestClient
    ) -> None:
        created = client_with_auth.post(
            "/api/v1/accounts",
            json={
                "name": "Throwaway",
                "venue": "snai",
                "market_type": "classic",
                "commission_pct": "0.00",
                "opening_balance": "0.00",
            },
        ).json()
        resp = client_with_auth.delete(f"/api/v1/accounts/{created['id']}")
        assert resp.status_code == 204

    def test_delete_account_with_trades_returns_409(
        self, client_with_auth: TestClient
    ) -> None:
        # Booking a trade against the seed account.
        sid = client_with_auth.post(
            "/api/v1/strategies",
            json={"name": "Bare", "field_schema": {"fields": []}},
        ).json()["id"]
        rows = _list_accounts(client_with_auth)
        bf_id = rows[0]["id"]
        trade_resp = client_with_auth.post(
            "/api/v1/trades",
            json={
                "strategy_id": sid,
                "account_id": bf_id,
                "home_team": "A", "away_team": "B", "league": "X",
                "kickoff_at": "2026-04-25T20:00:00+00:00",
                "stake_total": "100.00", "avg_odds": "2.50",
                "pnl_mode": "MANUAL", "manual_pnl_eur": "10.00",
                "status": "CLOSED",
                "closed_at": "2026-04-25T22:00:00+00:00",
            },
        )
        assert trade_resp.status_code == 201, trade_resp.text

        resp = client_with_auth.delete(f"/api/v1/accounts/{bf_id}")
        assert resp.status_code == 409
        assert "in use" in resp.json()["detail"]


class TestAccountsArchive:
    def test_archive_round_trip(self, client_with_auth: TestClient) -> None:
        rows = _list_accounts(client_with_auth)
        bf_id = rows[0]["id"]
        archived = client_with_auth.post(
            f"/api/v1/accounts/{bf_id}/archive"
        ).json()
        assert archived["archived_at"] is not None
        assert archived["is_active"] is False

        unarchived = client_with_auth.post(
            f"/api/v1/accounts/{bf_id}/unarchive"
        ).json()
        assert unarchived["archived_at"] is None
        assert unarchived["is_active"] is True
