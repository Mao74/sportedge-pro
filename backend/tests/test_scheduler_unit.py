"""Direct unit tests for the scheduler helpers."""

from __future__ import annotations

from datetime import UTC, datetime, time

from app.services.scheduler import _seconds_until


def test_seconds_until_target_today() -> None:
    # Now is 22:59 UTC, target is 23:59 → 60 minutes = 3600s
    now = datetime(2026, 4, 28, 22, 59, 0, tzinfo=UTC)
    assert _seconds_until(time(23, 59, tzinfo=UTC), now=now) == 3600.0


def test_seconds_until_wraps_next_day() -> None:
    # Now is 23:59:30 UTC, target is 23:59:00 → must wrap to tomorrow.
    now = datetime(2026, 4, 28, 23, 59, 30, tzinfo=UTC)
    delay = _seconds_until(time(23, 59, tzinfo=UTC), now=now)
    # 23:59:30 → 23:59:00 next day = 24h - 30s = 86370s
    assert delay == 86370.0


def test_seconds_until_at_target_wraps() -> None:
    # If now == target exactly, treat as already passed: wrap to next day.
    now = datetime(2026, 4, 28, 23, 59, 0, tzinfo=UTC)
    delay = _seconds_until(time(23, 59, tzinfo=UTC), now=now)
    assert delay == 86400.0
