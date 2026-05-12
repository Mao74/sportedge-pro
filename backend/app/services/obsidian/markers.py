"""USER_EDITABLE block helpers. Templates wrap user-writable areas with HTML
comment markers; the exporter preserves whatever the user typed between
markers across re-exports."""

from __future__ import annotations

import re

USER_EDITABLE_START = "<!-- USER_EDITABLE_START -->"
USER_EDITABLE_END = "<!-- USER_EDITABLE_END -->"

_RE = re.compile(
    re.escape(USER_EDITABLE_START) + r"\n?(.*?)\n?" + re.escape(USER_EDITABLE_END),
    re.DOTALL,
)


def extract_user_editable(text: str) -> str | None:
    """Return the content between the first USER_EDITABLE markers, or None."""
    match = _RE.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def wrap_user_editable(content: str) -> str:
    """Render the content surrounded by markers (used by template renderers)."""
    body = content.strip()
    return f"{USER_EDITABLE_START}\n{body}\n{USER_EDITABLE_END}"
