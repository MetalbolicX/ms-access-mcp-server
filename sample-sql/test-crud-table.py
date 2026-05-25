#!/usr/bin/env python3
"""Table CRUD — HTTP integration tests for create_table, delete_table."""

import time
import sys
from test_helper import *
import test_helper

TS = int(time.time())
TABLE_NAME = f"__test_table_{TS}"
TEST_NUM = 0


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Table CRUD Tests\n\n")


def main():
    global TEST_NUM

    print_header()

    print("============================================")
    print("Table CRUD  —  test-crud-table.py")
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
        # Test 1: create_table — create a temp table with 5 columns
        # ------------------------------------------------------------------
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        columns = [
            {"name": "id", "type": "Long Integer"},
            {"name": "label", "type": "Text", "size": 50},
            {"name": "amount", "type": "Currency"},
            {"name": "active", "type": "Boolean"},
            {"name": "created", "type": "Date/Time"},
        ]
        resp = call_tool("create_table", {"table_name": TABLE_NAME, "columns": columns})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "create_table", "PASS",
                   f"Created '{TABLE_NAME}' with 5 columns")
        else:
            record(TEST_NUM, "create_table", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 2: get_tables — verify table appears in list
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_tables", {})
        detail = extract_text_content(resp)
        tables = detail.get("tables", [])
        count = detail.get("count", len(tables))
        table_names = [t.get("name", "") for t in tables] if tables else []
        if detail.get("success") is True and TABLE_NAME in table_names:
            record(TEST_NUM, "get_tables (verify)", "PASS",
                   f"'{TABLE_NAME}' found in {count} tables")
        else:
            record(TEST_NUM, "get_tables (verify)", "FAIL",
                   f"'{TABLE_NAME}' not in {count} tables")

        # ------------------------------------------------------------------
        # Test 3: delete_table — remove the temp table
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("delete_table", {"table_name": TABLE_NAME})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "delete_table", "PASS", f"Deleted '{TABLE_NAME}'")
        else:
            record(TEST_NUM, "delete_table", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 4: get_tables — verify table is gone
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_tables", {})
        detail = extract_text_content(resp)
        tables = detail.get("tables", [])
        count = detail.get("count", len(tables))
        table_names = [t.get("name", "") for t in tables] if tables else []
        if detail.get("success") is True and TABLE_NAME not in table_names:
            record(TEST_NUM, "get_tables (verify delete)", "PASS",
                   f"'{TABLE_NAME}' removed, {count} tables remain")
        else:
            record(TEST_NUM, "get_tables (verify delete)", "FAIL",
                   f"'{TABLE_NAME}' still present in {count} tables")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: delete temp table if it still exists
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")
        try:
            resp = call_tool("delete_table", {"table_name": TABLE_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                print(f"  {GREEN}Deleted '{TABLE_NAME}'{NC}")
            else:
                print(f"  {YELLOW}Could not delete '{TABLE_NAME}': {detail.get('error', '?')}{NC}")
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
        print("Table CRUD  —  Summary")
        print("============================================")
        print(f"  Total:  {test_helper.TOTAL}")
        print(f"  Pass:   {GREEN}{test_helper.PASS}{NC}")
        print(f"  Fail:   {RED}{test_helper.FAIL}{NC}")
        print(f"  Skip:   {YELLOW}{test_helper.SKIP}{NC}")
        print(f"  Results: {CYAN}{RESULTS_FILE}{NC}")
        print()

        if test_helper.FAIL > 0:
            sys.exit(0)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()
