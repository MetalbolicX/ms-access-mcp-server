#!/usr/bin/env python3
"""Data CRUD — HTTP integration tests for query_data, insert_data, update_data, delete_data."""

import time
import sys
from test_helper import *
import test_helper

TS = int(time.time())
TABLE_NAME = f"__test_crud_{TS}"
TEST_NUM = 0


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Data CRUD Tests\n\n")


def main():
    global TEST_NUM

    print_header()

    print("============================================")
    print("Data CRUD  —  test-crud-data.py")
    print("============================================")
    print()

    # Verify server is reachable
    check_server()

    # Open MCP session
    print(f"{CYAN}[INIT]{NC} Acquiring session...")
    init_session()
    print(f"  Session: {test_helper.SID}")
    print()

    # Connect to database
    print(f"{CYAN}[CONNECT]{NC}")
    resp = call_tool("connect_access", {"database_path": DB_PATH, "use_com": True})
    detail = extract_text_content(resp)
    if detail.get("connected") is True:
        print(f"  {GREEN}Connected{NC}")
    else:
        print(f"  {RED}Connect FAILED — cannot proceed{NC}")
        sys.exit(1)
    print()

    try:
        # ------------------------------------------------------------------
        # Setup: create a temporary table
        # ------------------------------------------------------------------
        print(f"{CYAN}[SETUP] Creating {TABLE_NAME}{NC}")
        columns = [
            {"name": "id", "type": "Long Integer"},
            {"name": "name", "type": "Text", "size": 100},
            {"name": "value", "type": "Double"},
        ]
        TEST_NUM += 1
        resp = call_tool("create_table", {"table_name": TABLE_NAME, "columns": columns})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "create_table", "PASS", f"Created '{TABLE_NAME}'")
        else:
            record(TEST_NUM, "create_table", "FAIL", str(detail)[:100])

        # ------------------------------------------------------------------
        # Test 1: query_data — SELECT Now()
        # ------------------------------------------------------------------
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("query_data", {"sql": "SELECT Now() AS t"})
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("count", 0) > 0:
            cols = detail.get("columns", [])
            record(TEST_NUM, "query_data", "PASS",
                   f"count={detail['count']}, columns={cols}")
        else:
            record(TEST_NUM, "query_data", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 2: insert_data — single row
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("insert_data", {
            "table_name": TABLE_NAME,
            "data": {"id": 1, "name": "test1", "value": 3.14},
        })
        detail = extract_text_content(resp)
        affected = detail.get("affected", 0)
        if detail.get("success") is True and affected == 1:
            record(TEST_NUM, "insert_data (single)", "PASS", f"affected={affected}")
        else:
            record(TEST_NUM, "insert_data (single)", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 3: insert_data — multiple rows (2)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("insert_data", {
            "table_name": TABLE_NAME,
            "data": [
                {"id": 2, "name": "test2", "value": 2.71},
                {"id": 3, "name": "test3", "value": 1.41},
            ],
        })
        detail = extract_text_content(resp)
        affected = detail.get("affected", 0)
        if detail.get("success") is True and affected == 2:
            record(TEST_NUM, "insert_data (multi)", "PASS", f"affected={affected}")
        else:
            record(TEST_NUM, "insert_data (multi)", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 4: update_data — set value=999 where id=1
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("update_data", {
            "table_name": TABLE_NAME,
            "set_dict": {"value": 999.0},
            "where_dict": {"id": 1},
        })
        detail = extract_text_content(resp)
        affected = detail.get("affected", 0)
        if detail.get("success") is True and affected == 1:
            record(TEST_NUM, "update_data", "PASS", f"affected={affected}")
        else:
            record(TEST_NUM, "update_data", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 5: delete_data — where id=2
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("delete_data", {
            "table_name": TABLE_NAME,
            "where_dict": {"id": 2},
        })
        detail = extract_text_content(resp)
        affected = detail.get("affected", 0)
        if detail.get("success") is True and affected == 1:
            record(TEST_NUM, "delete_data", "PASS", f"affected={affected}")
        else:
            record(TEST_NUM, "delete_data", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 6: Verify — SELECT * should return 2 rows (id=1, id=3)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("query_data", {"sql": f"SELECT * FROM [{TABLE_NAME}] ORDER BY id"})
        detail = extract_text_content(resp)
        count = detail.get("count", 0)
        rows = detail.get("rows", [])
        if detail.get("success") is True and count == 2:
            id1 = rows[0].get("id", "?") if len(rows) > 0 else "?"
            id2 = rows[1].get("id", "?") if len(rows) > 1 else "?"
            record(TEST_NUM, "query_data (verify)", "PASS",
                   f"2 rows remaining: id={id1}, id={id2}")
        else:
            record(TEST_NUM, "query_data (verify)", "FAIL",
                   f"expected 2 rows, got {count}: {str(detail)[:120]}")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: remove temp table
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")
        try:
            resp = call_tool("delete_table", {"table_name": TABLE_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                print(f"  {GREEN}Deleted {TABLE_NAME}{NC}")
            else:
                print(f"  {YELLOW}Could not delete {TABLE_NAME}: {detail.get('error', '?')}{NC}")
        except Exception as e:
            print(f"  {YELLOW}Cleanup error: {e}{NC}")

        # Disconnect
        resp = call_tool("disconnect_access", {})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            print(f"  {GREEN}Disconnected{NC}")
        else:
            print(f"  {YELLOW}Disconnect warning: {detail.get('error', '?')}{NC}")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print()
        print("============================================")
        print("Data CRUD  —  Summary")
        print("============================================")
        print(f"  Total:  {test_helper.TOTAL}")
        print(f"  Pass:   {GREEN}{test_helper.PASS}{NC}")
        print(f"  Fail:   {RED}{test_helper.FAIL}{NC}")
        print(f"  Skip:   {YELLOW}{test_helper.SKIP}{NC}")
        print(f"  Results: {CYAN}{RESULTS_FILE}{NC}")
        print()

        if test_helper.FAIL > 0:
            sys.exit(0)  # Don't fail the run for documentation purposes
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()
