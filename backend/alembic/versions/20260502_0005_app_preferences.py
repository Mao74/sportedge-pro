"""app preferences — default_commission_pct + betting_exchange on app_settings

Revision ID: 0005_app_preferences
Revises: 0004_rename_builtins
Create Date: 2026-05-02

Adds two trader-tunable preferences to the single-row ``app_settings`` table:

- ``default_commission_pct``  — default commission applied to new trades
  (e.g. 4.50 = 4.5%). Previously a read-only env var; now editable at runtime.
- ``betting_exchange``       — free-form label (betfair / smarkets / matchbook /
  betdaq / other) carried for analytics and shown next to the commission.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_app_preferences"
down_revision: str | None = "0004_rename_builtins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "default_commission_pct",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="4.50",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "betting_exchange",
            sa.String(length=32),
            nullable=False,
            server_default="betfair",
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "betting_exchange")
    op.drop_column("app_settings", "default_commission_pct")
