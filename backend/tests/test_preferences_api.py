"""Preferences + bankroll snapshots-list integration tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient


class TestPreferences:
    def test_get_defaults(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert Decimal(body["default_commission_pct"]) == Decimal("4.50")
        assert body["betting_exchange"] == "betfair"
        assert body["default_market_type"] == "exchange"

    def test_patch_market_type(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences",
            json={"default_market_type": "classic", "betting_exchange": "Snai"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["default_market_type"] == "classic"
        assert body["betting_exchange"] == "snai"

    def test_patch_invalid_market_type(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences", json={"default_market_type": "weird"}
        )
        assert resp.status_code == 422

    def test_patch_updates_both(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences",
            json={"default_commission_pct": "2.00", "betting_exchange": "Smarkets"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Exchange names normalised to lowercase.
        assert body["betting_exchange"] == "smarkets"
        assert Decimal(body["default_commission_pct"]) == Decimal("2.00")

    def test_patch_partial(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences", json={"default_commission_pct": "0.00"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert Decimal(body["default_commission_pct"]) == Decimal("0.00")
        # Untouched field keeps its default.
        assert body["betting_exchange"] == "betfair"

    def test_patch_out_of_range_rejected(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.patch(
            "/api/v1/preferences", json={"default_commission_pct": "150.0"}
        )
        assert resp.status_code == 422

    def test_get_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/preferences").status_code == 401


class TestBankrollSnapshots:
    def test_list_empty(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/bankroll/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_most_recent_first(self, client_with_auth: TestClient) -> None:
        client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "50.00", "kind": "deposit", "notes": "initial top-up"},
        )
        client_with_auth.post(
            "/api/v1/bankroll/adjust",
            json={"amount_eur": "20.00", "kind": "withdrawal", "notes": "cash out"},
        )
        body = client_with_auth.get(
            "/api/v1/bankroll/snapshots", params={"limit": 5}
        ).json()
        assert len(body) == 2
        # Newest first.
        assert Decimal(body[0]["withdrawal_eur"]) == Decimal("20.00")
        assert Decimal(body[1]["deposit_eur"]) == Decimal("50.00")

    def test_list_respects_limit(self, client_with_auth: TestClient) -> None:
        for i in range(15):
            client_with_auth.post(
                "/api/v1/bankroll/adjust",
                json={"amount_eur": "10.00", "kind": "deposit", "notes": f"snap {i}"},
            )
        ten = client_with_auth.get(
            "/api/v1/bankroll/snapshots", params={"limit": 10}
        ).json()
        assert len(ten) == 10
