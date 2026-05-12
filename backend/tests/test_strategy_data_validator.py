"""Direct unit tests for strategy_data_validator."""

from __future__ import annotations

import pytest

from app.services.strategy_data_validator import validate_strategy_data


def _v(field_schema, strategy_data, status="OPEN"):
    return validate_strategy_data(
        field_schema=field_schema, strategy_data=strategy_data, trade_status=status
    )


# --- text -------------------------------------------------------------------


class TestText:
    def test_valid(self) -> None:
        errs = _v({"fields": [{"key": "n", "label": "N", "type": "text"}]}, {"n": "hello"})
        assert errs == []

    def test_non_string_rejected(self) -> None:
        errs = _v({"fields": [{"key": "n", "label": "N", "type": "text"}]}, {"n": 42})
        assert errs and errs[0]["key"] == "n"


# --- number -----------------------------------------------------------------


class TestNumber:
    SCHEMA = {"fields": [
        {"key": "x", "label": "X", "type": "number", "min": 0, "max": 10}
    ]}

    def test_valid_int(self) -> None:
        assert _v(self.SCHEMA, {"x": 5}) == []

    def test_valid_float(self) -> None:
        assert _v(self.SCHEMA, {"x": 5.5}) == []

    def test_valid_string_decimal(self) -> None:
        assert _v(self.SCHEMA, {"x": "3.14"}) == []

    def test_below_min(self) -> None:
        assert _v(self.SCHEMA, {"x": -1})[0]["msg"].startswith("must be >=")

    def test_above_max(self) -> None:
        assert _v(self.SCHEMA, {"x": 11})[0]["msg"].startswith("must be <=")

    def test_boolean_rejected(self) -> None:
        assert _v(self.SCHEMA, {"x": True})[0]["key"] == "x"

    def test_garbage_string_rejected(self) -> None:
        assert _v(self.SCHEMA, {"x": "hello"})[0]["key"] == "x"


# --- boolean ----------------------------------------------------------------


class TestBoolean:
    SCHEMA = {"fields": [{"key": "b", "label": "B", "type": "boolean"}]}

    def test_valid(self) -> None:
        assert _v(self.SCHEMA, {"b": True}) == []
        assert _v(self.SCHEMA, {"b": False}) == []

    def test_non_bool_rejected(self) -> None:
        assert _v(self.SCHEMA, {"b": "yes"})[0]["key"] == "b"


# --- select / multiselect ---------------------------------------------------


class TestSelect:
    SCHEMA = {"fields": [
        {"key": "s", "label": "S", "type": "select", "options": ["a", "b", "c"]}
    ]}

    def test_valid_pick(self) -> None:
        assert _v(self.SCHEMA, {"s": "b"}) == []

    def test_invalid_pick(self) -> None:
        assert _v(self.SCHEMA, {"s": "x"})[0]["key"] == "s"


class TestMultiselect:
    SCHEMA = {"fields": [
        {"key": "m", "label": "M", "type": "multiselect", "options": ["a", "b", "c"]}
    ]}

    def test_valid_subset(self) -> None:
        assert _v(self.SCHEMA, {"m": ["a", "c"]}) == []

    def test_non_list_rejected(self) -> None:
        assert _v(self.SCHEMA, {"m": "a"})[0]["key"] == "m"

    def test_invalid_value_in_list(self) -> None:
        errs = _v(self.SCHEMA, {"m": ["a", "x"]})
        assert errs and "invalid option" in errs[0]["msg"]


# --- chip-picker -----------------------------------------------------------


class TestChipPicker:
    SCHEMA = {"fields": [
        {"key": "p", "label": "P", "type": "chip-picker",
         "options": ["a", "b", "c", "d"], "min_picks": 2, "max_picks": 3}
    ]}

    def test_valid_count(self) -> None:
        assert _v(self.SCHEMA, {"p": ["a", "b"]}) == []
        assert _v(self.SCHEMA, {"p": ["a", "b", "c"]}) == []

    def test_too_few(self) -> None:
        assert _v(self.SCHEMA, {"p": ["a"]})[0]["msg"].startswith("must have at least")

    def test_too_many(self) -> None:
        assert _v(self.SCHEMA, {"p": ["a", "b", "c", "d"]})[0]["msg"].startswith("must have at most")


# --- depends_on -------------------------------------------------------------


class TestDependsOn:
    SCHEMA = {"fields": [
        {"key": "parent", "label": "Parent", "type": "boolean"},
        {"key": "child", "label": "Child", "type": "number",
         "depends_on": "parent", "min": 0, "max": 100},
    ]}

    def test_child_ignored_when_parent_falsy(self) -> None:
        # Parent=false → child value ignored, no validation
        errs = _v(self.SCHEMA, {"parent": False, "child": "garbage"})
        assert errs == []

    def test_child_validated_when_parent_truthy(self) -> None:
        errs = _v(self.SCHEMA, {"parent": True, "child": -5})
        assert errs and errs[0]["msg"].startswith("must be >=")


# --- required + required_for_status ----------------------------------------


class TestRequired:
    def test_required_field_missing(self) -> None:
        schema = {"fields": [
            {"key": "k", "label": "K", "type": "text", "required": True}
        ]}
        assert _v(schema, {})[0]["msg"] == "field is required"

    def test_required_for_status_only_when_closed(self) -> None:
        schema = {"fields": [
            {"key": "k", "label": "K", "type": "text", "required_for_status": "CLOSED"}
        ]}
        assert _v(schema, {}, status="OPEN") == []
        assert _v(schema, {}, status="CLOSED")[0]["msg"].startswith("field is required for")


# --- computed + unknown / forward-compat -----------------------------------


class TestEdgeCases:
    def test_computed_field_value_ignored(self) -> None:
        schema = {"fields": [
            {"key": "c", "label": "C", "type": "computed", "formula": "1+1"}
        ]}
        # Even if the client sent a bogus value, computed fields are skipped.
        assert _v(schema, {"c": "anything"}) == []

    def test_unknown_field_type_reported(self) -> None:
        schema = {"fields": [{"key": "x", "label": "X", "type": "wat"}]}
        assert _v(schema, {"x": 1})[0]["msg"].startswith("unknown field type")

    def test_unknown_strategy_data_keys_kept(self) -> None:
        # Forward-compat: unknown keys in strategy_data don't trigger errors
        schema = {"fields": [{"key": "k", "label": "K", "type": "text"}]}
        assert _v(schema, {"k": "ok", "future_field": 42}) == []

    def test_empty_field_schema_accepts_anything(self) -> None:
        assert _v({}, {"anything": "goes"}) == []
        assert _v({"fields": []}, {}) == []

    def test_malformed_field_skipped(self) -> None:
        # A field without 'key' or 'type' is silently skipped.
        schema = {"fields": [{"label": "broken"}, {"key": "k", "label": "K", "type": "text"}]}
        assert _v(schema, {"k": "v"}) == []
