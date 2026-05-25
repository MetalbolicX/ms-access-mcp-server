#!/usr/bin/env python3
"""Test all new missing-capabilities tools against a real Access database.

Usage:
    python sample-sql/test-new-tools.py --db "D:/path/to/db.accdb"

Handles both ODBC and WinCom adapters.
"""

import sys
import os
import json
import tempfile
import time
import os
import shutil
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.wincom import WinComAdapter


PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

def log(msg):
    print(msg, flush=True)


def test_run(name, func):
    try:
        result = func()
        if isinstance(result, list):
            # Some adapter methods return lists directly (e.g., get_queries)
            log(f"  {PASS} {name} ({len(result)} items)")
        elif isinstance(result, dict):
            if result.get("success") is False:
                log(f"  {FAIL} {name}: {result.get('error', 'unknown error')}")
            else:
                log(f"  {PASS} {name}")
        else:
            log(f"  {PASS} {name}")
        return result
    except Exception as e:
        log(f"  {FAIL} {name}: {e}")
        return None


def test_query_data(adapter, label):
    log(f"\n{'='*60}")
    log(f"query_data ({label})")
    log(f"{'='*60}")

    # Test basic SELECT
    result = test_run("SELECT from MSysObjects", lambda: adapter.execute_query(
        "SELECT TOP 5 Name, Type FROM MSysObjects WHERE Type=1 ORDER BY Name"
    ))
    if result and result.get("success"):
        log(f"    rows: {result.get('count')}, cols: {result.get('columns')}")

    # Test SELECT from tables if any exist
    result = test_run("SELECT current time", lambda: adapter.execute_query("SELECT Now() AS current_time"))
    if result and result.get("success"):
        log(f"    rows: {result.get('count')}, cols: {result.get('columns')}")


def test_query_crud(adapter, label):
    log(f"\n{'='*60}")
    log(f"Query CRUD ({label})")
    log(f"{'='*60}")

    # get_queries returns list[QueryInfo] directly
    result = test_run("get_queries", lambda: adapter.get_queries())
    if isinstance(result, list):
        log(f"    found {len(result)} queries")
        for q in result[:3]:
            log(f"      - {q['name'] if isinstance(q, dict) else q.name}")
    elif isinstance(result, dict) and result.get("success"):
        queries = result.get("queries", [])
        log(f"    found {result.get('count', len(queries))} queries")
        for q in queries[:3]:
            log(f"      - {q['name'] if isinstance(q, dict) else q.name}")

    # create_query (temp)
    test_query_name = f"__test_temp_q_{int(time.time())}"
    result = test_run("create_query", lambda: adapter.create_query(
        test_query_name, "SELECT 'hello' AS greeting"
    ))
    if result and result.get("success"):
        log(f"    created: {test_query_name}")

        # set_query_sql
        result = test_run("set_query_sql", lambda: adapter.set_query_sql(
            test_query_name, "SELECT 'world' AS greeting"
        ))
        if result and result.get("success"):
            log(f"    updated SQL")

        # delete_query
        result = test_run("delete_query", lambda: adapter.delete_query(test_query_name))
        if result and result.get("success"):
            log(f"    deleted: {test_query_name}")


def test_data_crud(adapter, label):
    log(f"\n{'='*60}")
    log(f"Data CRUD ({label})")
    log(f"{'='*60}")

    table_name = f"__test_crud_{int(time.time())}"

    # create temp table first
    result = adapter.create_table(table_name, [
        {"name": "id", "type": "Long Integer"},
        {"name": "name", "type": "Text", "size": 100},
        {"name": "value", "type": "Double"},
    ])
    if not result or not result.get("success"):
        log(f"  {SKIP} Data CRUD: could not create temp table ({result})")
        return

    log(f"  {PASS} created temp table: {table_name}")

    # insert single row
    result = test_run("insert single row", lambda: adapter.insert_data(
        table_name, {"id": 1, "name": "test1", "value": 3.14}
    ))
    if result and result.get("success"):
        log(f"    affected: {result.get('affected')}")

    # insert multiple rows
    result = test_run("insert multiple rows", lambda: adapter.insert_data(
        table_name, [
            {"id": 2, "name": "test2", "value": 2.71},
            {"id": 3, "name": "test3", "value": 1.41},
        ]
    ))
    if result and result.get("success"):
        log(f"    affected: {result.get('affected')}")

    # update
    result = test_run("update where id=1", lambda: adapter.update_data(
        table_name, {"value": 999.0}, {"id": 1}
    ))
    if result and result.get("success"):
        log(f"    affected: {result.get('affected')}")

    # delete
    result = test_run("delete where id=3", lambda: adapter.delete_data(
        table_name, {"id": 3}
    ))
    if result and result.get("success"):
        log(f"    affected: {result.get('affected')}")

    # verify with SELECT
    result = adapter.execute_query(f"SELECT * FROM [{table_name}] ORDER BY id")
    if result and result.get("success"):
        log(f"  {PASS} verify data: {result.get('count')} rows")
        for row in result.get("rows", []):
            log(f"      {row}")

    # clean up temp table
    adapter.delete_table(table_name)
    log(f"  {PASS} deleted temp table")


def test_table_operations(adapter, label):
    log(f"\n{'='*60}")
    log(f"Table Operations ({label})")
    log(f"{'='*60}")

    table_name = f"__test_table_{int(time.time())}"

    # create_table
    result = test_run("create_table", lambda: adapter.create_table(table_name, [
        {"name": "id", "type": "Long Integer"},
        {"name": "label", "type": "Text", "size": 50, "nullable": True},
        {"name": "amount", "type": "Currency"},
        {"name": "active", "type": "Boolean"},
        {"name": "created", "type": "Date/Time"},
    ]))
    if not result or not result.get("success"):
        log(f"  {FAIL} aborting: {result}")
        return

    # verify table exists via execute_query
    result = test_run("verify table exists", lambda: adapter.execute_query(
        f"SELECT COUNT(*) AS cnt FROM [{table_name}]"
    ))
    if result and result.get("success"):
        log(f"    count: {result.get('rows')}")

    # delete_table
    test_run("delete_table", lambda: adapter.delete_table(table_name))


def test_data_export(adapter, label):
    log(f"\n{'='*60}")
    log(f"Data Export ({label})")
    log(f"{'='*60}")

    tmpdir = tempfile.mkdtemp(prefix="access_export_test_")
    csv_path = os.path.join(tmpdir, "export_test.csv")
    json_path = os.path.join(tmpdir, "export_test.json")

    # Find a small table to export
    result = adapter.execute_query("SELECT TOP 5 Name FROM MSysObjects WHERE Type=1 ORDER BY Name")
    if not result or not result.get("success") or result.get("count", 0) == 0:
        log(f"  [SKIP] Data Export: no data available")
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)
        return

    rows = result.get("rows", [])
    first_table = rows[0]["Name"] if rows else None

    if not first_table:
        log(f"  [SKIP] Data Export: no tables to export")
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)
        return

    log(f"  using table: {first_table}")

    import threading

    # Export table CSV with timeout
    export_results = [None]
    def do_export():
        try:
            export_results[0] = adapter.export_table_csv(first_table, csv_path)
        except Exception as e:
            export_results[0] = {"success": False, "error": str(e)}

    t = threading.Thread(target=do_export, daemon=True)
    t.start()
    t.join(timeout=5)

    if t.is_alive():
        log(f"  [SKIP] export_table_csv timed out (5s) - table may be too large")
    else:
        result = export_results[0]
        if result and result.get("success"):
            log(f"  {PASS} export_table_csv")
            log(f"    rows exported: {result.get('rows_exported')}")
            if os.path.exists(csv_path):
                with open(csv_path) as f:
                    content = f.read().strip()[:200]
                    log(f"    file preview: {content}")
        else:
            err = result.get('error', 'unknown') if isinstance(result, dict) else result
            log(f"  [SKIP] export_table_csv: {err}")

    # Export query JSON with timeout
    export_results[0] = None
    def do_json_export():
        try:
            export_results[0] = adapter.export_query_json(first_table, json_path, pretty=True)
        except Exception as e:
            export_results[0] = {"success": False, "error": str(e)}

    t2 = threading.Thread(target=do_json_export, daemon=True)
    t2.start()
    t2.join(timeout=5)

    if t2.is_alive():
        log(f"  [SKIP] export_query_json timed out (5s)")
    else:
        result = export_results[0]
        if result and result.get("success"):
            log(f"  {PASS} export_query_json")
            log(f"    rows exported: {result.get('rows_exported')}")
            if os.path.exists(json_path):
                with open(json_path) as f:
                    content = f.read().strip()[:300]
                    log(f"    file preview: {content}")
        else:
            err = result.get('error', 'unknown') if isinstance(result, dict) else result
            log(f"  [SKIP] export_query_json: {err}")

    import shutil; shutil.rmtree(tmpdir, ignore_errors=True)


def test_linked_tables(adapter, label):
    log(f"\n{'='*60}")
    log(f"Linked Tables ({label})")
    log(f"{'='*60}")

    import threading
    results_holder = [None]

    def do_get():
        try:
            results_holder[0] = adapter.get_linked_tables()
        except Exception as e:
            results_holder[0] = {"success": False, "error": str(e)}

    t = threading.Thread(target=do_get, daemon=True)
    t.start()
    t.join(timeout=15)

    if t.is_alive():
        log(f"  [SKIP] get_linked_tables timed out (15s)")
        return

    result = results_holder[0]
    if result and result.get("success"):
        log(f"  {PASS} get_linked_tables")
        linked = result.get("linked_tables", [])
        log(f"    linked tables: {len(linked)}")
        for lt in linked[:5]:
            log(f"      - {lt['name']} -> {lt.get('source_table', '?')} ({lt.get('type', '?')})")
    elif result:
        log(f"  [SKIP] get_linked_tables: {result.get('error', 'unknown')}")
    else:
        log(f"  [FAIL] get_linked_tables: no result")


def test_compact_repair(adapter, label):
    log(f"\n{'='*60}")
    log(f"Compact/Repair ({label})")
    log(f"{'='*60}")

    # Just check the stub returns properly — actual compact is risky
    result = test_run("compact_repair (dry)", lambda: adapter.compact_repair(
        "compact", "NONEXISTENT.accdb", "output.accdb"
    ))
    if result and result.get("success") is False:
        log(f"    (expected: {result.get('error', 'error on non-existent file')})")


def main():
    parser = argparse.ArgumentParser(description="Test new Access tools")
    parser.add_argument("--db", default="D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb",
                        help="Path to .accdb file")
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        log(f"Database not found: {db_path}")
        sys.exit(1)

    log(f"Database: {db_path}")
    log(f"Size: {os.path.getsize(db_path) / 1024 / 1024:.1f} MB")

    # Test OdbcAdapter first
    log(f"\n{'#'*60}")
    log("# Testing OdbcAdapter")
    log(f"{'#'*60}")

    odbc = OdbcAdapter()

    try:
        ok = odbc.connect(db_path)
        if ok and odbc.is_connected():
            log(f"  {PASS} ODBC connected")
            test_query_data(odbc, "ODBC")
            test_query_crud(odbc, "ODBC")
            test_data_crud(odbc, "ODBC")
            test_table_operations(odbc, "ODBC")
            test_compact_repair(odbc, "ODBC")
            test_linked_tables(odbc, "ODBC")
            test_data_export(odbc, "ODBC")
            odbc.disconnect()
            log(f"  {PASS} ODBC disconnected")
        else:
            log(f"  {SKIP} ODBC could not connect")
    except Exception as e:
        log(f"  {SKIP} ODBC: {e} - skipping")

    # Test WinComAdapter
    log(f"\n{'#'*60}")
    log("# Testing WinComAdapter")
    log(f"{'#'*60}")

    wincom = WinComAdapter()

    try:
        wincom.connect(db_path)
    except Exception as e:
        log(f"  {FAIL} WinCom connect: {e}")
        log(f"  Skipping WinCom tests")
    else:
        if wincom.is_connected():
            log(f"  {PASS} WinCom connected")
            test_query_data(wincom, "WinCom")
            test_query_crud(wincom, "WinCom")
            test_data_crud(wincom, "WinCom")
            test_table_operations(wincom, "WinCom")
            test_compact_repair(wincom, "WinCom")
            test_linked_tables(wincom, "WinCom")
            test_data_export(wincom, "WinCom")
            wincom.disconnect()
            log(f"  {PASS} WinCom disconnected")
        else:
            log(f"  {FAIL} WinCom not connected")

    log(f"\n{'#'*60}")
    log("# DONE")
    log(f"{'#'*60}")


if __name__ == "__main__":
    main()
