"""Strategy schemas + ``field_schema`` validation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import StrategyKind

# --- field_schema ----------------------------------------------------------

FieldType = Literal[
    "text", "number", "select", "multiselect", "boolean", "chip-picker", "computed",
]

VALID_FIELD_TYPES: frozenset[str] = frozenset(
    ("text", "number", "select", "multiselect", "boolean", "chip-picker", "computed")
)

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class FieldDef(BaseModel):
    """One dynamic form field declared by a strategy's ``field_schema``."""

    model_config = ConfigDict(extra="allow")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    type: FieldType
    required: bool = False
    default: Any = None
    depends_on: str | None = None

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError(
                "field key must be snake_case (start with a lowercase letter, "
                "then lowercase letters/digits/underscores)."
            )
        return v

    @model_validator(mode="after")
    def _type_specific(self) -> FieldDef:
        # `select` / `multiselect` / `chip-picker` need an `options` list.
        if self.type in {"select", "multiselect", "chip-picker"}:
            options = getattr(self, "options", None) or self.model_extra.get("options")  # type: ignore[union-attr]
            if not isinstance(options, list) or not options:
                raise ValueError(
                    f"field type {self.type!r} requires a non-empty 'options' list."
                )
        # `computed` needs a `formula`.
        if self.type == "computed":
            formula = self.model_extra.get("formula") if self.model_extra else None  # type: ignore[union-attr]
            if not isinstance(formula, str) or not formula.strip():
                raise ValueError("field type 'computed' requires a non-empty 'formula' string.")
        return self


class FieldSchema(BaseModel):
    """Top-level wrapper for a strategy's dynamic-form declaration."""

    model_config = ConfigDict(extra="forbid")

    fields: list[FieldDef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> FieldSchema:
        seen: set[str] = set()
        for f in self.fields:
            if f.key in seen:
                raise ValueError(f"duplicate field key: {f.key!r}")
            seen.add(f.key)
        return self


# --- Strategy I/O ----------------------------------------------------------


class StrategyOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: StrategyKind
    template_key: str | None
    sport: str
    description: str | None
    color_hex: str | None
    is_active: bool
    field_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def _validate_color_hex(v: str | None) -> str | None:
    if v is None:
        return v
    if not _HEX_RE.match(v):
        raise ValueError("color_hex must be #RRGGBB or #RRGGBBAA")
    return v


class StrategyCreate(BaseModel):
    """Custom strategies only — built-ins are seeded by Alembic, not user-created."""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2048)
    color_hex: str | None = None
    field_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("color_hex")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_color_hex(v)

    @field_validator("field_schema")
    @classmethod
    def _schema_shape(cls, v: dict[str, Any]) -> dict[str, Any]:
        # Validate against FieldSchema, then return as plain dict for JSONB.
        FieldSchema.model_validate(v)
        return v


class StrategyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2048)
    color_hex: str | None = None
    is_active: bool | None = None
    field_schema: dict[str, Any] | None = None

    @field_validator("color_hex")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_color_hex(v)

    @field_validator("field_schema")
    @classmethod
    def _schema_shape(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return v
        FieldSchema.model_validate(v)
        return v
