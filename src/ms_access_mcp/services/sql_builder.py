"""SQL Builder — pure functions for SQL construction and row extraction."""

from __future__ import annotations

from ms_access_mcp.models.migration import TableTransferConfig


def build_select(
    table_name: str,
    columns: list[str] | None,
    where: str | None,
    order_by: list[str] | None,
) -> str:
    """Build SELECT statement with optional column list, WHERE, ORDER BY.

    columns=None → SELECT *
    columns=[] → invalid (should not reach here)
    columns=[...] → SELECT col, col, ...
    """
    cols = "*" if columns is None else ", ".join(columns)
    sql = f"SELECT {cols} FROM [{table_name}]"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {', '.join(order_by)}"
    return sql


def resolve_override(
    table_name: str,
    overrides: dict[str, TableTransferConfig] | None,
    schema_columns: list[str],
) -> tuple[list[str] | None, str | None, list[str] | None]:
    """Return (effective_columns, where, order_by) for a table.

    Returns (None, None, None) when table has no override entry or all override
    fields are None — signaling to build_select to use SELECT *.
    Returns (list, str, list) when at least one override field is set.
    """
    if overrides is None:
        return None, None, None
    cfg = overrides.get(table_name)
    if cfg is None:
        return None, None, None
    effective_cols = cfg.columns if cfg.columns else None
    return effective_cols, cfg.where, cfg.order_by


def validate_columns(requested: list[str], available: list[str]) -> None:
    """Raise ValueError if any requested column not in available."""
    available_set = set(available)
    for col in requested:
        if col not in available_set:
            raise ValueError(f"Invalid column '{col}' not found in table schema")


def extract_rows(query_result: dict | list) -> list[dict]:
    """Safely extract row dicts from varying query result formats."""
    if isinstance(query_result, dict):
        return query_result.get("rows", []) if query_result.get("success", False) else []
    return query_result


def normalize_value(value) -> str:
    """Normalize a value for comparison or storage, converting None to placeholder."""
    return "<NULL>" if value is None else str(value)