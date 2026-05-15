"""multiple_bets — support parlay / accumulator trades

Revision ID: 0008_multiple_bets
Revises: 0007_multi_account
Create Date: 2026-05-15

Lets the journal record multiple-leg trades (parlay / accumulator) as a
single row instead of forcing one row per leg. The trader books the
combined trade with the total stake and the combined odds; only the
number of legs is tracked separately so analytics can split single vs
multiple performance.

Schema changes:

- ``trades.n_selections``  INT NOT NULL DEFAULT 1
  How many legs are in this bet slip. 1 = single, ≥2 = multiple.
- ``trades.away_team``     made nullable.
  A multiple has no canonical "away" team; we still keep ``home_team``
  as a free-text label (e.g. "Multipla 3 eventi") so existing analytics
  that key on home_team keep working.

Idempotent: both ``upgrade`` and ``downgrade`` implemented. Downgrade
backfills any null away_team with "—" before re-applying NOT NULL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_multiple_bets"
down_revision: str | None = "0007_multi_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trades",
        sa.Column(
            "n_selections",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column("trades", "away_team", nullable=True)


def downgrade() -> None:
    op.execute(
        "UPDATE trades SET away_team = '—' WHERE away_team IS NULL"
    )
    op.alter_column("trades", "away_team", nullable=False)
    op.drop_column("trades", "n_selections")
