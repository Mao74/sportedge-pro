"""CSV import / export integration tests."""

from __future__ import annotations

import io
from decimal import Decimal

from fastapi.testclient import TestClient


def _custom_strategy(client: TestClient, name: str = "Bare") -> dict:
    resp = client.post(
        "/api/v1/strategies",
        json={"name": name, "color_hex": "#FFB547", "field_schema": {"fields": []}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _post_trade(client: TestClient, sid: str, **overrides) -> dict:
    body = {
        "strategy_id": sid,
        "home_team": "Inter",
        "away_team": "Lazio",
        "league": "Serie A",
        "kickoff_at": "2026-04-28T20:45:00+00:00",
        "closed_at": "2026-04-28T22:30:00+00:00",
        "stake_total": "100.00",
        "avg_odds": "2.50",
        "commission_pct": "5.00",
        "pnl_mode": "MANUAL",
        "manual_pnl_eur": "42.50",
        "status": "CLOSED",
        "tags": ["live", "high-xg"],
    }
    body.update(overrides)
    resp = client.post("/api/v1/trades", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestExportCsv:
    def test_export_empty_returns_header_only(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.get("/api/v1/trades/export.csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        lines = resp.text.strip().splitlines()
        assert len(lines) == 1
        header = lines[0].split(",")
        for col in (
            "kickoff_at", "strategy_slug", "account_name",
            "market_type", "pnl_mode", "tags",
        ):
            assert col in header

    def test_export_one_trade(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        _post_trade(client_with_auth, sid)
        resp = client_with_auth.get("/api/v1/trades/export.csv")
        assert resp.status_code == 200
        lines = resp.text.strip().splitlines()
        assert len(lines) == 2
        # data row contains the strategy slug + tags pipe-separated
        data = lines[1]
        assert "bare" in data
        assert "live|high-xg" in data or "high-xg|live" in data


class TestImportCsv:
    HEADER = (
        "kickoff_at,closed_at,strategy_slug,account_name,home_team,away_team,league,"
        "stake_total,avg_odds,commission_pct,market_type,pnl_mode,position_side,"
        "outcome_label,cashout_odds,manual_pnl_eur,status,ht_score_home,"
        "ht_score_away,ft_score_home,ft_score_away,tags,strategy_data,notes_md,"
        "computed_pnl_eur"
    )

    def _post_csv(self, client: TestClient, csv_text: str, dry_run: bool) -> dict:
        return client.post(
            "/api/v1/trades/import",
            files={"file": ("trades.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
            data={"dry_run": "true" if dry_run else "false"},
        ).json()

    def test_dry_run_two_valid_rows(self, client_with_auth: TestClient) -> None:
        _custom_strategy(client_with_auth)  # slug "bare"
        csv_text = self.HEADER + "\n" + "\n".join([
            "2026-04-28T20:45:00+00:00,2026-04-28T22:30:00+00:00,bare,Betfair,Inter,Lazio,Serie A,100.00,2.50,5.00,exchange,MANUAL,,WIN,,42.50,CLOSED,,,,,live,{},,,0.00",
            "2026-04-29T18:00:00+00:00,,bare,Betfair,Roma,Milan,Serie A,50.00,3.00,0.00,classic,AUTO,back,WIN,,,OPEN,,,,,,{},,,0.00",
        ])
        body = self._post_csv(client_with_auth, csv_text, dry_run=True)
        assert body["parsed_rows"] == 2
        assert body["valid_rows"] == 2
        assert body["errors"] == []
        assert body["inserted"] == 0
        assert body["dry_run"] is True

    def test_commit_inserts_trades(self, client_with_auth: TestClient) -> None:
        _custom_strategy(client_with_auth)
        csv_text = self.HEADER + "\n" + (
            "2026-04-28T20:45:00+00:00,2026-04-28T22:30:00+00:00,bare,Betfair,Inter,Lazio,Serie A,"
            "100.00,2.50,5.00,exchange,MANUAL,,WIN,,42.50,CLOSED,,,,,live,{},,,0.00"
        )
        body = self._post_csv(client_with_auth, csv_text, dry_run=False)
        assert body["inserted"] == 1
        # Confirm the trade lands with the correct fields.
        rows = client_with_auth.get("/api/v1/trades").json()["items"]
        assert len(rows) == 1
        assert rows[0]["home_team"] == "Inter"
        assert Decimal(rows[0]["computed_pnl_eur"]) == Decimal("42.50")
        # market_type defaults to exchange when CSV says exchange.
        detail = client_with_auth.get(f"/api/v1/trades/{rows[0]['id']}").json()
        assert detail["market_type"] == "exchange"

    def test_classic_row_recomputes_pnl_without_commission(
        self, client_with_auth: TestClient
    ) -> None:
        _custom_strategy(client_with_auth)
        csv_text = self.HEADER + "\n" + (
            "2026-04-28T20:45:00+00:00,2026-04-28T22:30:00+00:00,bare,Betfair,A,B,X,"
            "100.00,2.50,5.00,classic,AUTO,back,WIN,,,CLOSED,,,,,,{},,,9999.99"
        )
        body = self._post_csv(client_with_auth, csv_text, dry_run=False)
        assert body["inserted"] == 1
        rows = client_with_auth.get("/api/v1/trades").json()["items"]
        # Classic mode: 100 * 1.5 * 1.0 = 150.00 (the 9999.99 from the CSV is ignored).
        assert Decimal(rows[0]["computed_pnl_eur"]) == Decimal("150.00")

    def test_unknown_strategy_slug_is_row_error(
        self, client_with_auth: TestClient
    ) -> None:
        # No strategy created with slug "ghost"
        csv_text = self.HEADER + "\n" + (
            "2026-04-28T20:45:00+00:00,,ghost,Betfair,A,B,X,100.00,2.50,5.00,exchange,"
            "MANUAL,,WIN,,42.50,OPEN,,,,,,{},,,0.00"
        )
        body = self._post_csv(client_with_auth, csv_text, dry_run=True)
        assert body["valid_rows"] == 0
        assert any("ghost" in e["detail"] for e in body["errors"])

    def test_missing_required_column_aborts(self, client_with_auth: TestClient) -> None:
        # 'avg_odds' missing entirely
        bad_header = self.HEADER.replace("avg_odds,", "")
        body = self._post_csv(client_with_auth, bad_header + "\n", dry_run=True)
        assert body["valid_rows"] == 0
        assert any("missing columns" in e["detail"] for e in body["errors"])

    def test_round_trip_export_then_import(self, client_with_auth: TestClient) -> None:
        sid = _custom_strategy(client_with_auth)["id"]
        _post_trade(client_with_auth, sid)
        exported = client_with_auth.get("/api/v1/trades/export.csv").text
        # Delete original then re-import.
        rows = client_with_auth.get("/api/v1/trades").json()["items"]
        for r in rows:
            client_with_auth.delete(f"/api/v1/trades/{r['id']}")
        body = self._post_csv(client_with_auth, exported, dry_run=False)
        assert body["inserted"] == 1
        round_trip = client_with_auth.get("/api/v1/trades").json()["items"]
        assert len(round_trip) == 1
        assert round_trip[0]["home_team"] == "Inter"
