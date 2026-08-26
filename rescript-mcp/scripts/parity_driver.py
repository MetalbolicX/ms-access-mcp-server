"""parity_driver.py — Python-side runner for the differential parity harness.

Reads a case JSON file (parity/cases/<op>.json) and prints the JSON envelope
the equivalent Python implementation would return. The runner (run.mjs)
spawns this driver with ACCESS_TEST_DB pointing at a per-side fixture
copy for `mutating: true` cases, and at the pristine fixture otherwise.

The driver calls the same Python adapter (`OdbcAdapter`) that the MCP
tool modules ultimately wrap, then wraps the result in the same shape
the ReScript Facade returns (modulo ReScript's normalization layer —
those are handled by the harness's normalize.mjs).

Usage:
    .venv/Scripts/python.exe rescript-mcp/scripts/parity_driver.py <case.json>

Outputs a single JSON object on stdout. Exits 0 on success, 1 on driver
error (so the runner can distinguish "case failed" from "driver crashed").
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from typing import Any, Callable

# Repo root: parents[0] = rescript-mcp/scripts, parents[1] = rescript-mcp,
# parents[2] = repo root.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ms_access_mcp.adapters.odbc import OdbcAdapter  # noqa: E402


def _connect(name: str = "default") -> OdbcAdapter:
    """Open an OdbcAdapter against ACCESS_TEST_DB.

    Mirrors the ReScript facade's connectAccess: the adapter opens a
    pyodbc connection on the same .accdb file the ReScript side uses.
    """
    db_path = os.environ["ACCESS_TEST_DB"]
    adapter = OdbcAdapter(db_path)
    if not adapter.connect(db_path):
        raise RuntimeError(f"connect failed for {name} at {db_path}")
    return adapter


def _shape_query(adapter: OdbcAdapter, sql: str) -> dict:
    """Wrap adapter.execute_query in the ReScript facade envelope shape.

    ReScript: { success, rows, count, columns, error: JSON.Null | String }
    Python (OdbcAdapter.execute_query): { success, rows, count, columns, error? }
    """
    result = adapter.execute_query(sql, None)
    return {
        "success": bool(result.get("success")),
        "rows": result.get("rows", []),
        "count": result.get("count", 0),
        "columns": result.get("columns", []),
        "error": result.get("error", None),
    }


def _shape_insert(adapter: OdbcAdapter, table: str, data: dict) -> dict:
    """Wrap adapter.insert_data — ReScript: { success, affected }."""
    result = adapter.insert_data(table, data)
    return {
        "success": bool(result.get("success")),
        "affected": result.get("affected", 0),
    }


def _shape_update(
    adapter: OdbcAdapter, table: str, set_dict: dict, where_dict: dict
) -> dict:
    """Wrap adapter.update_data — ReScript: { success, affected }."""
    result = adapter.update_data(table, set_dict, where_dict)
    return {
        "success": bool(result.get("success")),
        "affected": result.get("affected", 0),
    }


def _shape_delete(adapter: OdbcAdapter, table: str, where_dict: dict) -> dict:
    """Wrap adapter.delete_data — ReScript: { success, affected }."""
    result = adapter.delete_data(table, where_dict)
    return {
        "success": bool(result.get("success")),
        "affected": result.get("affected", 0),
    }


def _shape_get_tables(adapter: OdbcAdapter) -> dict:
    """Wrap adapter.get_tables — ReScript: { success, tables, count }.

    ReScript fields per table: name, fields[], recordCount, primaryKey.
    """
    tables = adapter.get_tables()
    table_dicts = []
    for t in tables:
        table_dicts.append({
            "name": t.name,
            "fields": [
                {
                    "name": f.name,
                    "type": f.type,
                    "size": f.size,
                    "required": f.required,
                    "allowZeroLength": f.allow_zero_length,
                    "defaultValue": None,
                    "isAutoincrement": False,
                }
                for f in t.fields
            ],
            "recordCount": t.record_count,
            "primaryKey": None,
        })
    return {
        "success": True,
        "tables": table_dicts,
        "count": len(table_dicts),
    }


def _shape_get_table_schema(adapter: OdbcAdapter, table: str) -> dict:
    """Wrap adapter.get_tables() filtered to one — ReScript: { success, table }."""
    tables = adapter.get_tables()
    target = next((t for t in tables if t.name == table), None)
    if target is None:
        return {"success": False, "error": f"Table '{table}' not found"}
    return {
        "success": True,
        "table": {
            "name": target.name,
            "fields": [
                {
                    "name": f.name,
                    "type": f.type,
                    "size": f.size,
                    "required": f.required,
                    "allowZeroLength": f.allow_zero_length,
                    "defaultValue": None,
                    "isAutoincrement": False,
                }
                for f in target.fields
            ],
            "recordCount": target.record_count,
            "primaryKey": None,
        },
    }


def _shape_get_relationships(adapter: OdbcAdapter) -> dict:
    """Wrap adapter.get_relationships — ReScript: { success, relationships, count }."""
    rels = adapter.get_relationships()
    rel_dicts = []
    for r in rels:
        rel_dicts.append({
            "name": r.name,
            "table": r.table,
            "foreignTable": r.foreign_table,
            "attributes": "",
            "columns": list(r.columns),
            "foreignColumns": list(r.foreign_columns),
        })
    return {
        "success": True,
        "relationships": rel_dicts,
        "count": len(rel_dicts),
    }


def _shape_get_queries(adapter: OdbcAdapter) -> dict:
    """Wrap adapter.get_queries — ReScript: { success, queries, count }."""
    queries = adapter.get_queries()
    q_dicts = [
        {"name": q.name, "sql": q.sql, "type": q.type}
        for q in queries
    ]
    return {
        "success": True,
        "queries": q_dicts,
        "count": len(q_dicts),
    }


def _shape_get_database_statistics(adapter: OdbcAdapter) -> dict:
    """Wrap adapter.get_database_statistics — ReScript merges the result."""
    return adapter.get_database_statistics()


def _shape_execute_raw_sql(adapter: OdbcAdapter, sql: str) -> dict:
    """Wrap adapter.execute_raw_sql — ReScript: { success, rows_affected }.

    ReScript clamps -1 to 0 per spec; mirror that here.
    """
    try:
        affected = adapter.execute_raw_sql(sql)
    except Exception as exc:  # pragma: no cover — defensive
        return {"success": False, "error": str(exc)}
    clamped = affected if affected >= 0 else 0
    return {"success": True, "rows_affected": clamped}


def _shape_export_data(
    adapter: OdbcAdapter,
    sql: str,
    file_path: str,
    format: str,
) -> dict:
    """Wrap adapter.export_data — ReScript: { success, rows_exported, file_path, format }.

    The strategy layer for Python always returns rows_exported + file_path
    on success (and format is implicit in the file_path extension).
    ReScript returns the format explicitly — mirror it.
    """
    if format == "csv":
        result = adapter.export_data(sql, file_path, "csv")
    elif format == "json":
        result = adapter.export_data(sql, file_path, "json")
    else:
        return {"success": False, "error": f"Unknown format '{format}'"}
    if not result.get("success"):
        return result
    result["format"] = format
    return result


# ---------------------------------------------------------------------------
# Operation dispatch
# ---------------------------------------------------------------------------

def run_case(case: dict) -> dict:
    """Execute the case and return the envelope dict.

    Each branch connects if the operation isn't a connection-lifecycle op,
    runs the operation, and disconnects. The runner (run.mjs) handles
    fixture copying for mutating cases; the driver treats the file in
    ACCESS_TEST_DB as the canonical input.
    """
    operation = case["operation"]
    args = case.get("args", {})

    # Connection-lifecycle ops do not require a prior connect.
    if operation == "connect_access":
        return _connect_op(args)
    if operation == "disconnect_access":
        return _disconnect_op(args)
    if operation == "list_connections":
        return _list_connections_op()
    if operation == "is_connected":
        return _is_connected_op(args)
    if operation == "get_active_connection":
        return _get_active_op()
    if operation == "set_active_connection":
        return _set_active_op(args)

    # Everything else needs a live adapter.
    adapter = _connect()
    try:
        if operation == "query_data":
            return _query_data_op(adapter, args)
        if operation == "insert_data":
            return _insert_data_op(adapter, args)
        if operation == "update_data":
            return _update_data_op(adapter, args)
        if operation == "delete_data":
            return _delete_data_op(adapter, args)
        if operation == "get_tables":
            return _shape_get_tables(adapter)
        if operation == "get_table_schema":
            return _shape_get_table_schema(adapter, args["table"])
        if operation == "get_relationships":
            return _shape_get_relationships(adapter)
        if operation == "get_queries":
            return _shape_get_queries(adapter)
        if operation == "get_database_statistics":
            return _shape_get_database_statistics(adapter)
        if operation == "execute_raw_sql":
            return _shape_execute_raw_sql(adapter, args["sql"])
        if operation == "export_data":
            file_path = args["filePath"]
            if file_path == "REPLACE_AT_RUNTIME":
                file_path = _export_path()
            return _shape_export_data(adapter, args["sql"], file_path, args["format"])
        raise ValueError(f"unknown operation: {operation}")
    finally:
        try:
            adapter.disconnect()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Connection-lifecycle ops — drive _pool() directly so we exercise the same
# pool the MCP tools use. The ReScript facade wraps ConnectionPool, not a
# raw adapter, so the parity envelope is at the pool layer.
# ---------------------------------------------------------------------------

def _connect_op(args: dict) -> dict:
    """Mirror ReScript's connectAccess envelope.

    ReScript returns { success, connected, database, name } on success,
    { success:false, error } on failure (no `database` or `name`).
    Python's connect_access returns the same shape on success; on failure
    it returns { success:false, error } (and may omit database/name).
    """
    from ms_access_mcp.mcp.container import get_container

    db_path = os.environ["ACCESS_TEST_DB"]
    name = args.get("name", "default")
    try:
        state = get_container().connection_pool.connect(
            name, db_path, "odbc", password=""
        )
        return {
            "success": True,
            "connected": True,
            "database": db_path,
            "name": name,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _disconnect_op(args: dict) -> dict:
    """Mirror ReScript's disconnectAccess envelope."""
    from ms_access_mcp.mcp.container import get_container

    name = args.get("name", "default")
    try:
        get_container().connection_pool.disconnect(name)
        return {"success": True, "message": f"Disconnected '{name}'"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _is_connected_op(args: dict) -> dict:
    """Mirror ReScript's isConnected envelope.

    ReScript returns { connected, database, name } — NO success key (parity
    exception). Python's is_connected returns the same shape.
    """
    from ms_access_mcp.mcp.container import get_container

    pool = get_container().connection_pool
    name = args.get("name", "default")
    return {
        "connected": pool.is_connected(name),
        "database": pool.current_database,
        "name": name,
    }


def _set_active_op(args: dict) -> dict:
    """Mirror ReScript's setActiveConnection envelope."""
    from ms_access_mcp.mcp.container import get_container

    name = args["name"]
    try:
        get_container().connection_pool.set_active(name)
        return {"success": True, "active": name}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _list_connections_op() -> dict:
    """Mirror ReScript's listConnections envelope.

    ReScript returns the per-connection info as { database, adapter_type,
    connected }. Python adds created_at; the harness's volatileFields drop
    it before the differ.
    """
    from ms_access_mcp.mcp.container import get_container

    pool = get_container().connection_pool
    connections = pool.list()
    result: dict[str, dict] = {}
    for conn_name, state in connections.items():
        result[conn_name] = {
            "database": state.db_path,
            "adapter_type": state.adapter_type,
            "connected": state.adapter.is_connected(),
            "created_at": state.created_at.isoformat(),
        }
    return {
        "success": True,
        "connections": result,
        "count": len(connections),
        "active": pool.get_active(),
    }


def _get_active_op() -> dict:
    """Mirror ReScript's getActiveConnection envelope."""
    from ms_access_mcp.mcp.container import get_container

    return {
        "success": True,
        "active": get_container().connection_pool.get_active(),
    }


# ---------------------------------------------------------------------------
# Data ops
# ---------------------------------------------------------------------------

def _query_data_op(adapter: OdbcAdapter, args: dict) -> dict:
    sql = args["sql"]
    return _shape_query(adapter, sql)


def _insert_data_op(adapter: OdbcAdapter, args: dict) -> dict:
    table = args["table"]
    data = args["data"]
    return _shape_insert(adapter, table, data)


def _update_data_op(adapter: OdbcAdapter, args: dict) -> dict:
    table = args["table"]
    set_dict = args["setDict"]
    where_dict = args.get("whereDict") or {}
    return _shape_update(adapter, table, set_dict, where_dict)


def _delete_data_op(adapter: OdbcAdapter, args: dict) -> dict:
    table = args["table"]
    where_dict = args.get("whereDict")
    if not where_dict:
        return {
            "success": False,
            "error": "DELETE requires non-empty WHERE clause",
        }
    return _shape_delete(adapter, table, where_dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _export_path() -> str:
    """Pick an export file path inside the runner-managed export dir.

    The runner sets ACCESS_MCP_ALLOWED_DIRS to include both the fixture
    dir and a temp export dir; for the Python child this resolves to
    a fresh .csv in the system temp (or the harness's export dir if set).
    """
    export_dir = os.environ.get("PARITY_EXPORT_DIR") or tempfile.gettempdir()
    os.makedirs(export_dir, exist_ok=True)
    return os.path.join(export_dir, f"parity_export_{os.getpid()}.csv")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(json.dumps({"error": "usage: parity_driver.py <case.json>"}), file=sys.stderr)
        return 1
    case_path = argv[1]
    with open(case_path, "r", encoding="utf-8") as fh:
        case = json.load(fh)
    try:
        envelope = run_case(case)
    except Exception as exc:  # pragma: no cover — defensive
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(envelope, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))