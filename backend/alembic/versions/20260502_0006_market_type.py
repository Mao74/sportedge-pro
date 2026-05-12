"""market_type — exchange (with commission) vs classic (commission-free)

Revision ID: 0006_market_type
Revises: 0005_app_preferences
Create Date: 2026-05-02

Adds a per-trade market_type flag (exchange | classic) plus a matching
default in app_settings. When market_type='classic' the PnL calculator
treats commission_factor as 1.0 — the quoted odds are already net of any
bookmaker margin so no commission is applied.

The existing `betting_exchange` column on app_settings generalises in
meaning: it now stores any venue name (Betfair, Smarkets, Snai, Bet365,
etc.). The DB schema and column name stay the same to avoid renaming;
the UI presents it as 'Venue' regardless of market_type.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_market_type"
down_revision: str | None = "0005_app_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MARKET_TYPE = postgresql.ENUM("exchange", "classic", name="market_type")
MARKET_TYPE_COL = postgresql.ENUM(
    "exchange", "classic", name="market_type", create_type=False
)


def upgrade() -> None:
    MARKET_TYPE.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "trades",
        sa.Column(
            "market_type",
            MARKET_TYPE_COL,
            nullable=False,
            server_default="exchange",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "default_market_type",
            MARKET_TYPE_COL,
            nullable=False,
            server_default="exchange",
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "default_market_type")
    op.drop_column("trades", "market_type")
    MARKET_TYPE.drop(op.get_bind(), checkfirst=True)
