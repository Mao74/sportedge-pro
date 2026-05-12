"""rename built-in strategies (Magic CS v3 → Magic CS, draw_hunter S4 → Draw Hunter)

Revision ID: 0004_rename_builtins
Revises: 0003_obsidian_tables
Create Date: 2026-04-29

Renames the two built-in strategies' display name and slug to the trader's
preferred labels, only when the existing row still holds the original
default (user-renamed strategies are left alone).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_rename_builtins"
down_revision: str | None = "0003_obsidian_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # Magic CS v3 → Magic CS
    bind.execute(
        sa.text(
            """
            UPDATE strategies
               SET name = 'Magic CS', slug = 'magic-cs'
             WHERE template_key = 'magic_cs_v3'
               AND name = 'Magic CS v3'
               AND slug = 'magic-cs-v3'
            """
        )
    )
    # If only the slug still matches but the user already renamed, still
    # tighten the slug to keep it consistent with the new template.
    bind.execute(
        sa.text(
            "UPDATE strategies SET slug = 'magic-cs' "
            "WHERE template_key = 'magic_cs_v3' AND slug = 'magic-cs-v3'"
        )
    )

    # draw_hunter S4 → Draw Hunter
    bind.execute(
        sa.text(
            """
            UPDATE strategies
               SET name = 'Draw Hunter', slug = 'draw-hunter'
             WHERE template_key = 'draw_hunter_s4'
               AND name = 'draw_hunter S4'
               AND slug = 'draw-hunter-s4'
            """
        )
    )
    bind.execute(
        sa.text(
            "UPDATE strategies SET slug = 'draw-hunter' "
            "WHERE template_key = 'draw_hunter_s4' AND slug = 'draw-hunter-s4'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE strategies SET slug = 'magic-cs-v3' "
            "WHERE template_key = 'magic_cs_v3' AND slug = 'magic-cs'"
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE strategies
               SET name = 'Magic CS v3'
             WHERE template_key = 'magic_cs_v3' AND name = 'Magic CS'
            """
        )
    )
    bind.execute(
        sa.text(
            "UPDATE strategies SET slug = 'draw-hunter-s4' "
            "WHERE template_key = 'draw_hunter_s4' AND slug = 'draw-hunter'"
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE strategies
               SET name = 'draw_hunter S4'
             WHERE template_key = 'draw_hunter_s4' AND name = 'Draw Hunter'
            """
        )
    )
