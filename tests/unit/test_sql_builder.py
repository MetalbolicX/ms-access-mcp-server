"""Tests for sql_builder module — RED phase."""

from __future__ import annotations

import pytest
from ms_access_mcp.services.sql_builder import (
    build_select,
    resolve_override,
    validate_columns,
    extract_rows,
    normalize_value,
)
from ms_access_mcp.models.migration import TableTransferConfig


class TestBuildSelect:
    def test_none_columns_returns_select_star(self):
        result = build_select("Customers", None, None, None)
        assert result == "SELECT * FROM [Customers]"

    def test_column_list_returns_proper_select(self):
        result = build_select("Customers", ["Name", "Email"], None, None)
        assert result == "SELECT Name, Email FROM [Customers]"

    def test_with_where_clause(self):
        result = build_select("Orders", ["ID", "Status"], "Amount > 100", None)
        assert result == "SELECT ID, Status FROM [Orders] WHERE Amount > 100"

    def test_with_order_by(self):
        result = build_select("Customers", ["Name"], None, ["Name"])
        assert result == "SELECT Name FROM [Customers] ORDER BY Name"

    def test_with_where_and_order_by(self):
        result = build_select("Orders", ["ID", "Date"], "Status = 'Active'", ["Date"])
        assert result == "SELECT ID, Date FROM [Orders] WHERE Status = 'Active' ORDER BY Date"


class TestResolveOverride:
    def test_none_overrides_returns_none_tuple(self):
        result = resolve_override("Orders", None, ["ID", "Status"])
        assert result == (None, None, None)

    def test_missing_table_returns_none_tuple(self):
        overrides = {"OtherTable": TableTransferConfig(columns=["X"])}
        result = resolve_override("Orders", overrides, ["ID", "Status"])
        assert result == (None, None, None)

    def test_config_with_columns_returns_columns_and_where(self):
        cfg = TableTransferConfig(columns=["ID", "Name"], where="Active = true", order_by=["Name"])
        overrides = {"Customers": cfg}
        result = resolve_override("Customers", overrides, ["ID", "Name", "Email"])
        assert result == (["ID", "Name"], "Active = true", ["Name"])


class TestValidateColumns:
    def test_valid_columns_does_not_raise(self):
        validate_columns(["Name", "Email"], ["Name", "Email", "Phone"])

    def test_invalid_column_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            validate_columns(["Name", "InvalidCol"], ["Name", "Email"])
        assert "InvalidCol" in str(exc_info.value)


class TestExtractRows:
    def test_dict_result_with_success(self):
        query_result = {"success": True, "rows": [{"id": 1}, {"id": 2}]}
        result = extract_rows(query_result)
        assert result == [{"id": 1}, {"id": 2}]

    def test_dict_result_without_success_flag_returns_empty(self):
        """Missing success key defaults to False → returns empty list (matches original)."""
        query_result = {"rows": [{"id": 1}]}
        result = extract_rows(query_result)
        assert result == []

    def test_dict_result_with_failed_success(self):
        query_result = {"success": False, "rows": [{"id": 1}]}
        result = extract_rows(query_result)
        assert result == []

    def test_list_result_passthrough(self):
        query_result = [{"id": 1}, {"id": 2}]
        result = extract_rows(query_result)
        assert result == [{"id": 1}, {"id": 2}]


class TestNormalizeValue:
    def test_none_returns_null_placeholder(self):
        assert normalize_value(None) == "<NULL>"

    def test_string_value_returns_string(self):
        assert normalize_value("hello") == "hello"

    def test_int_value_returns_string(self):
        assert normalize_value(42) == "42"