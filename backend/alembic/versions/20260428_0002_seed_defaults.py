"""seed default user + built-in strategies

Revision ID: 0002_seed_defaults
Revises: 0001_initial_schema
Create Date: 2026-04-28

Idempotent: re-running upgrade is a no-op when the rows already exist
(thanks to ON CONFLICT DO NOTHING and email/slug uniqueness). If the user
has renamed a built-in strategy, the seed preserves their custom name.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import get_settings
from app.core.security import hash_password
from app.services.strategy_templates import all_templates

# Alembic identifiers
revision: str = "0002_seed_defaults"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    settings = get_settings()

    # --- Default user ---------------------------------------------------------
    bind.execute(
        sa.text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:email, :pw) "
            "ON CONFLICT (email) DO NOTHING"
        ),
        {
            "email": settings.default_user_email,
            "pw": hash_password(settings.default_user_password),
        },
    )

    # --- Built-in strategies --------------------------------------------------
    # On conflict on slug we update only the *non-user-editable* fields:
    # template_key, kind, color_hex defaults, and field_schema.
    # The display name is preserved if the user has renamed it.
    for tpl in all_templates():
        bind.execute(
            sa.text(
                """
                INSERT INTO strategies (
                    name, slug, kind, template_key, sport,
                    description, color_hex, is_active, field_schema
                )
                VALUES (
                    :name, :slug, 'builtin', :template_key, 'football',
                    :description, :color_hex, true, CAST(:field_schema AS jsonb)
                )
                ON CONFLICT (slug) DO UPDATE SET
                    template_key = EXCLUDED.template_key,
                    field_schema = EXCLUDED.field_schema,
                    description  = EXCLUDED.description,
                    kind         = 'builtin'
                WHERE strategies.kind = 'builtin'
                """
            ),
            {
                "name": tpl.name,
                "slug": tpl.slug,
                "template_key": tpl.template_key,
                "description": tpl.description,
                "color_hex": tpl.color_hex,
                "field_schema": json.dumps(tpl.field_schema),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    settings = get_settings()

    # Remove built-in seeds (only those with a known template_key — leaves
    # user-renamed but template_key-bound builtins resettable).
    bind.execute(
        sa.text(
            "DELETE FROM strategies "
            "WHERE kind = 'builtin' AND template_key IN :keys"
        ).bindparams(sa.bindparam("keys", expanding=True)),
        {"keys": [t.template_key for t in all_templates()]},
    )

    bind.execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": settings.default_user_email},
    )
