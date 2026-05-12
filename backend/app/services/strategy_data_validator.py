"""Validate a trade's ``strategy_data`` payload against the strategy's
``field_schema``. Forward-compatible: unknown keys are kept, declared keys
are type-checked.

Returned errors are a list of ``{key, msg}`` dicts so the API layer can
emit them as a structured 422 problem-details payload.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def validate_strategy_data(
    *,
    field_schema: dict[str, Any],
    strategy_data: dict[str, Any],
    trade_status: str = "OPEN",
) -> list[dict[str, str]]:
    """Returns a list of validation errors. Empty list = valid."""
    fields = (field_schema or {}).get("fields", []) or []
    errors: list[dict[str, str]] = []

    for f in fields:
        if not isinstance(f, dict):
            continue
        key = f.get("key")
        ftype = f.get("type")
        if not key or not ftype:
            continue
        present = key in strategy_data
        value = strategy_data.get(key)

        # Optional dependency: parent must be truthy for child to be considered.
        dep = f.get("depends_on")
        dep_satisfied = bool(strategy_data.get(dep)) if dep else True

        # Required (always)
        if f.get("required") and dep_satisfied and (not present or value in (None, "")):
            errors.append({"key": key, "msg": "field is required"})
            continue

        # Required when CLOSED
        if (
            f.get("required_for_status") == "CLOSED"
            and trade_status == "CLOSED"
            and (not present or value in (None, ""))
        ):
            errors.append({"key": key, "msg": "field is required for CLOSED trades"})
            continue

        if not present or value in (None, ""):
            continue
        if dep and not dep_satisfied:
            # parent toggled off — value present but ignored. No error.
            continue

        # Type-specific validation
        msg = _check_type(ftype, value, f)
        if msg:
            errors.append({"key": key, "msg": msg})

    return errors


def _check_type(ftype: str, value: Any, field_def: dict[str, Any]) -> str | None:
    if ftype == "text":
        if not isinstance(value, str):
            return "must be a string"
        return None

    if ftype == "number":
        if isinstance(value, bool):
            return "must be a number, not boolean"
        if not isinstance(value, (int, float, str, Decimal)):
            return "must be a number"
        try:
            num = Decimal(str(value))
        except InvalidOperation:
            return "must be a number"
        lo = field_def.get("min")
        hi = field_def.get("max")
        if lo is not None and num < Decimal(str(lo)):
            return f"must be >= {lo}"
        if hi is not None and num > Decimal(str(hi)):
            return f"must be <= {hi}"
        return None

    if ftype == "boolean":
        if not isinstance(value, bool):
            return "must be a boolean"
        return None

    if ftype == "select":
        opts = field_def.get("options") or []
        if value not in opts:
            return f"must be one of {opts}"
        return None

    if ftype in ("multiselect", "chip-picker"):
        if not isinstance(value, list):
            return "must be a list"
        opts = field_def.get("options") or []
        for v in value:
            if v not in opts:
                return f"contains invalid option {v!r}; must be one of {opts}"
        if ftype == "chip-picker":
            min_p = field_def.get("min_picks")
            max_p = field_def.get("max_picks")
            if min_p is not None and len(value) < min_p:
                return f"must have at least {min_p} picks"
            if max_p is not None and len(value) > max_p:
                return f"must have at most {max_p} picks"
        return None

    if ftype == "computed":
        # Read-only field — ignore any value the client sent.
        return None

    return f"unknown field type {ftype!r}"
