"""Obsidian API integration tests — config, export-all into a tmp vault,
then round-trip a notes edit back into the DB via sync-now."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _enable_obsidian(client: TestClient, vault: Path) -> None:
    resp = client.patch(
        "/api/v1/obsidian/config",
        json={
            "enabled": True,
            "vault_path": str(vault),
            "sync_mode": "two_way",
        },
    )
    assert resp.status_code == 200, resp.text


def _make_trade(client: TestClient) -> dict:
    sresp = client.post(
        "/api/v1/strategies",
        json={"name": "Bare", "field_schema": {"fields": []}},
    )
    sid = sresp.json()["id"]
    body = {
        "strategy_id": sid,
        "home_team": "Inter",
        "away_team": "Lazio",
        "league": "Serie A",
        "kickoff_at": "2026-04-28T20:45:00+00:00",
        "closed_at": "2026-04-28T22:30:00+00:00",
        "stake_total": "62.00",
        "avg_odds": "5.42",
        "pnl_mode": "MANUAL",
        "manual_pnl_eur": "41.20",
        "status": "CLOSED",
        "outcome_label": "A2_OVER25",
        "notes_md": "xG asymmetry favorevole.",
    }
    resp = client.post("/api/v1/trades", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestStatusAndConfig:
    def test_status_default(self, client_with_auth: TestClient) -> None:
        body = client_with_auth.get("/api/v1/obsidian/status").json()
        assert body["enabled"] is False
        assert body["sync_mode"] == "export_only"
        assert body["conflict_count"] == 0

    def test_config_patch(self, client_with_auth: TestClient, tmp_path: Path) -> None:
        _enable_obsidian(client_with_auth, tmp_path / "vault")
        body = client_with_auth.get("/api/v1/obsidian/status").json()
        assert body["enabled"] is True
        assert body["vault_path"].endswith("vault")
        assert body["sync_mode"] == "two_way"


class TestExportAll:
    def test_export_writes_trade_daily_dashboards(
        self, client_with_auth: TestClient, tmp_path: Path
    ) -> None:
        vault = tmp_path / "vault"
        _enable_obsidian(client_with_auth, vault)
        _make_trade(client_with_auth)
        resp = client_with_auth.post("/api/v1/obsidian/export-all")
        assert resp.status_code == 200, resp.text
        s = resp.json()
        assert s["trades_exported"] == 1
        assert s["daily_exported"] == 1
        assert s["dashboards_exported"] >= 1

        assert (vault / "Trades" / "2026-04-28 Inter vs Lazio.md").exists()
        assert (vault / "Daily" / "2026-04-28.md").exists()
        assert (vault / "Dashboards" / "Bankroll.md").exists()
        assert (vault / "README.md").exists()
        assert (vault / "Strategies" / "Bare.md").exists()

    def test_export_disabled_returns_400(self, client_with_auth: TestClient) -> None:
        resp = client_with_auth.post("/api/v1/obsidian/export-all")
        assert resp.status_code == 400


class TestSyncNow:
    def test_round_trip_user_notes(
        self, client_with_auth: TestClient, tmp_path: Path
    ) -> None:
        vault = tmp_path / "vault"
        _enable_obsidian(client_with_auth, vault)
        trade = _make_trade(client_with_auth)
        client_with_auth.post("/api/v1/obsidian/export-all")

        path = vault / "Trades" / "2026-04-28 Inter vs Lazio.md"
        before = path.read_text(encoding="utf-8")
        after = re.sub(
            r"<!-- USER_EDITABLE_START -->\n(.+?)\n<!-- USER_EDITABLE_END -->",
            "<!-- USER_EDITABLE_START -->\nbrand new notes\n<!-- USER_EDITABLE_END -->",
            before,
            count=1,
            flags=re.DOTALL,
        )
        assert after != before
        path.write_text(after, encoding="utf-8")

        resp = client_with_auth.post("/api/v1/obsidian/sync-now")
        assert resp.status_code == 200, resp.text
        events = resp.json()
        assert any(e["action"] == "updated" for e in events)

        # The trade now reflects the file's notes.
        got = client_with_auth.get(f"/api/v1/trades/{trade['id']}").json()
        assert got["notes_md"] == "brand new notes"


class TestSyncNowExportOnlyRejected:
    def test_export_only_mode_rejects_sync_now(
        self, client_with_auth: TestClient, tmp_path: Path
    ) -> None:
        vault = tmp_path / "vault"
        client_with_auth.patch(
            "/api/v1/obsidian/config",
            json={"enabled": True, "vault_path": str(vault), "sync_mode": "export_only"},
        )
        resp = client_with_auth.post("/api/v1/obsidian/sync-now")
        assert resp.status_code == 400


class TestAuth:
    def test_status_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/v1/obsidian/status").status_code == 401
