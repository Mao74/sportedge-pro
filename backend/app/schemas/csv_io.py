"""CSV import response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CsvRowError(BaseModel):
    row_index: int
    column: str | None = None
    detail: str


class CsvImportResult(BaseModel):
    parsed_rows: int
    valid_rows: int
    errors: list[CsvRowError]
    inserted: int
    dry_run: bool
