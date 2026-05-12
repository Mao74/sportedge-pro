"""Tag schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def _validate_color(v: str | None) -> str | None:
    if v is None:
        return v
    if not _HEX_RE.match(v):
        raise ValueError("color_hex must be #RRGGBB or #RRGGBBAA")
    return v


class TagOut(BaseModel):
    id: uuid.UUID
    name: str
    color_hex: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagWithUsage(TagOut):
    n_trades: int


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color_hex: str | None = None

    @field_validator("color_hex")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_color(v)


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color_hex: str | None = None

    @field_validator("color_hex")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        return _validate_color(v)
