#!/usr/bin/env python3
"""
parity_driver.py — Python child driver for the differential parity harness.

Reads a case JSON path from argv, runs the operation via the Python MCP
service container, and prints the envelope JSON to stdout.

Backend identity is explicit in the envelope via the "backend" field:
  "com"           — Win32 COM / Access.Application was available and used
  "odbc"          — ODBC fallback was used (COM unavailable or disabled)
  "unavailable"   — neither backend could be used

Exits:
  0  — envelope written to stdout
  1  — driver-level error (malformed case, import failure, etc.)
"""

import sys
import json
import os

# ---------------------------------------------------------------------------
# Backend detection with explicit identity
# ---------------------------------------------------------------------------

_BACKEND: str | None = None


def get_backend() -> str:
    """
    Detect which backend is available and return its identity string.
    Cached after first call.
    """
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    if sys.platform == "win32":
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            _BACKEND = "com"
            return "com"
        except Exception:
            pass

    try:
        import pyodbc
        _BACKEND = "odbc"
        return "odbc"
    except Exception:
        pass

    _BACKEND = "unavailable"
    return "unavailable"


# ---------------------------------------------------------------------------
# Set up container bootstrap env before importing server modules
# ---------------------------------------------------------------------------

def _bootstrap_env() -> None:
    """Configure env vars needed by the server container before tool imports."""
    # ACCESS_TEST_DB must be set before importing container-dependent modules
    if not os.environ.get("ACCESS_TEST_DB"):
        fixture = os.environ.get("PARITY_FIXTURE", "")
        if fixture:
            os.environ["ACCESS_TEST_DB"] = fixture


# ---------------------------------------------------------------------------
# Operation dispatch
# ---------------------------------------------------------------------------

def _dispatch(case_obj: dict) -> dict:
    """Run the operation described by case_obj and return an envelope dict."""

    backend = get_backend()
    args = case_obj.get("args", {})
    variant = case_obj.get("variant", "odbc")
    conn_name = f"parity-{variant}"

    # Import tools lazily to avoid container init before env is set
    from ms_access_mcp.mcp.connection import (
        connect_access,
        disconnect_access,
        list_connections,
        is_connected,
    )
    from ms_access_mcp.mcp.crud import (
        query_data,
        insert_data,
        update_data,
        delete_data,
        get_queries,
    )
    from ms_access_mcp.mcp.schema import (
        get_tables,
        get_table_schema,
        get_relationships,
        get_database_statistics,
    )
    from ms_access_mcp.mcp.raw_sql import execute_raw_sql
    from ms_access_mcp.mcp.export import export_data

    op = case_obj.get("operation", "")

    try:
        # Lifecycle operations
        if op == "connect_access":
            db_path = args.get("databasePath", "") or os.environ.get("ACCESS_TEST_DB", "")
            use_com = variant == "com"
            result = connect_access(
                database_path=db_path,
                use_com=use_com,
                name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "disconnect_access":
            result = disconnect_access(name=conn_name)
            result["backend"] = backend
            return result

        if op == "list_connections":
            result = list_connections()
            result["backend"] = backend
            return result

        if op == "is_connected":
            result = is_connected(connection_name=conn_name)
            result["backend"] = backend
            return result

        # Data operations
        if op == "query_data":
            result = query_data(
                sql=args.get("sql", ""),
                params=args.get("params"),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "insert_data":
            result = insert_data(
                table_name=args.get("tableName", "") or args.get("table_name", ""),
                data=args.get("data", {}),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "update_data":
            result = update_data(
                table_name=args.get("tableName", "") or args.get("table_name", ""),
                set_dict=args.get("setDict", {}),
                where_dict=args.get("whereDict"),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "delete_data":
            result = delete_data(
                table_name=args.get("tableName", "") or args.get("table_name", ""),
                where_dict=args.get("whereDict"),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "get_tables":
            result = get_tables(connection_name=conn_name)
            result["backend"] = backend
            return result

        if op == "get_table_schema":
            result = get_table_schema(
                table_name=args.get("tableName", "") or args.get("table_name", ""),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "get_queries":
            result = get_queries(connection_name=conn_name)
            result["backend"] = backend
            return result

        if op == "get_relationships":
            result = get_relationships(connection_name=conn_name)
            result["backend"] = backend
            return result

        if op == "get_database_statistics":
            result = get_database_statistics(connection_name=conn_name)
            result["backend"] = backend
            return result

        if op == "execute_raw_sql":
            result = execute_raw_sql(
                sql=args.get("sql", ""),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        if op == "export_data":
            import tempfile
            export_dir = os.environ.get("PARITY_EXPORT_DIR", tempfile.gettempdir())
            file_path = os.path.join(export_dir, f"parity_export_{os.getpid()}.csv")
            result = export_data(
                sql=args.get("sql", ""),
                file_path=file_path,
                format=args.get("format", "csv"),
                connection_name=conn_name,
            )
            result["backend"] = backend
            return result

        return {"success": False, "error": f"unknown operation: {op}", "backend": backend}

    except Exception as exc:
        return {"success": False, "error": str(exc), "backend": backend}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "usage: parity_driver.py <case.json>"}))
        return 1

    case_path = sys.argv[1]
    try:
        with open(case_path, "r", encoding="utf-8") as fh:
            case_obj = json.load(fh)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"failed to read case: {exc}"}))
        return 1

    _bootstrap_env()

    try:
        envelope = _dispatch(case_obj)
    except Exception as exc:
        envelope = {"success": False, "error": str(exc), "backend": get_backend()}

    print(json.dumps(envelope))
    return 0


if __name__ == "__main__":
    sys.exit(main())
