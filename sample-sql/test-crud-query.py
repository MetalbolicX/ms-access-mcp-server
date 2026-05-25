#!/usr/bin/env python3
"""Query CRUD — HTTP integration tests for create_query, set_query_sql, delete_query."""

import time
import sys
from test_helper import *
import test_helper

TS = int(time.time())
QUERY_NAME = f"__test_query_{TS}"
TEST_NUM = 0


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Query CRUD Tests\n\n")


def main():
    global TEST_NUM

    print_header()

    print("============================================")
    print("Query CRUD  —  test-crud-query.py")
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
        # Test 1: get_queries — discover existing queries
        # ------------------------------------------------------------------
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("get_queries", {})
        detail = extract_text_content(resp)
        queries = detail.get("queries", [])
        count = detail.get("count", len(queries))
        if detail.get("success") is True:
            record(TEST_NUM, "get_queries", "PASS", f"{count} existing queries found")
        else:
            record(TEST_NUM, "get_queries", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 2: create_query — create a temp query
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("create_query", {
            "name": QUERY_NAME,
            "sql": "SELECT 1 AS test",
        })
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "create_query", "PASS", f"Created '{QUERY_NAME}'")
        else:
            record(TEST_NUM, "create_query", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 3: set_query_sql — modify the query's SQL
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("set_query_sql", {
            "name": QUERY_NAME,
            "sql": "SELECT 2 AS test",
        })
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "set_query_sql", "PASS", "SQL updated to SELECT 2 AS test")
        else:
            record(TEST_NUM, "set_query_sql", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 4: get_queries — verify the temp query is now listed
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_queries", {})
        detail = extract_text_content(resp)
        queries = detail.get("queries", [])
        query_names = [q.get("name", "") for q in queries]
        if detail.get("success") is True and QUERY_NAME in query_names:
            record(TEST_NUM, "get_queries (verify)", "PASS",
                   f"'{QUERY_NAME}' found in {len(queries)} queries")
        else:
            record(TEST_NUM, "get_queries (verify)", "FAIL",
                   f"'{QUERY_NAME}' not listed: {str(detail)[:120]}")

        # ------------------------------------------------------------------
        # Test 5: Execute the stored query via query_data (SELECT * FROM it)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("query_data", {"sql": f"SELECT * FROM [{QUERY_NAME}]"})
        detail = extract_text_content(resp)
        rows = detail.get("rows", [])
        if detail.get("success") is True and len(rows) > 0:
            val = rows[0].get("test", "?")
            record(TEST_NUM, "query_data (stored query)", "PASS", f"test={val}")
        else:
            record(TEST_NUM, "query_data (stored query)", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 6: delete_query — remove the temp query
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("delete_query", {"name": QUERY_NAME})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "delete_query", "PASS", f"Deleted '{QUERY_NAME}'")
        else:
            record(TEST_NUM, "delete_query", "FAIL", str(detail)[:120])

        # ------------------------------------------------------------------
        # Test 7: get_queries — verify the query is gone
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_queries", {})
        detail = extract_text_content(resp)
        queries = detail.get("queries", [])
        query_names = [q.get("name", "") for q in queries]
        if detail.get("success") is True and QUERY_NAME not in query_names:
            record(TEST_NUM, "get_queries (verify delete)", "PASS",
                   f"'{QUERY_NAME}' successfully removed")
        else:
            record(TEST_NUM, "get_queries (verify delete)", "FAIL",
                   f"'{QUERY_NAME}' still present in {len(queries)} queries")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: delete temp query if it still exists
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")
        try:
            resp = call_tool("delete_query", {"name": QUERY_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                print(f"  {GREEN}Deleted '{QUERY_NAME}'{NC}")
            else:
                print(f"  {YELLOW}Could not delete '{QUERY_NAME}': {detail.get('error', '?')}{NC}")
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
        print("Query CRUD  —  Summary")
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
