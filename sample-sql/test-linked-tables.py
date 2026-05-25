#!/usr/bin/env python3
"""Linked Tables — HTTP integration tests for linked table tools.

Tests: get_linked_tables.
SKIP: create_linked_table, refresh_linked_table, unlink_table
(require external data source / existing linked table).

Strategy: query the database for any existing linked tables, report the count
and details. Tools that mutate linked tables are SKIP'd with explanation
since they require an external data source to link against.
"""

import sys
from test_helper import *
import test_helper

TEST_NUM = 0


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Linked Table Tests\n\n")


def main():
    global TEST_NUM

    print_header()

    print("============================================")
    print("Linked Tables  —  test-linked-tables.py")
    print("============================================")
    print()

    # Verify server is reachable
    check_server()

    # Open MCP session
    print(f"{CYAN}[INIT]{NC} Acquiring session...")
    init_session()
    print(f"  Session: {test_helper.SID}")
    print()

    # Connect to database with COM for linked table tools
    print(f"{CYAN}[CONNECT]{NC}")
    resp = call_tool("connect_access", {"database_path": DB_PATH, "use_com": True})
    detail = extract_text_content(resp)
    if detail.get("connected") is True:
        print(f"  {GREEN}Connected{NC}")
    else:
        print(f"  {RED}Connect FAILED — cannot proceed (linked table tools require COM){NC}")
        sys.exit(1)
    print()

    try:
        # ==================================================================
        # TEST 1: get_linked_tables — discover any existing links
        # ==================================================================
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("get_linked_tables", {})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            linked = detail.get("linked_tables", [])
            count = len(linked)
            record(TEST_NUM, "get_linked_tables", "PASS",
                   f"Found {count} linked tables")
            if count > 0:
                for lt in linked[:5]:
                    name = lt.get("name", "?")
                    source = lt.get("source_table", lt.get("source", "?"))
                    lt_type = lt.get("type", "?")
                    print(f"    - '{name}' -> {source} ({lt_type})")
        else:
            record(TEST_NUM, "get_linked_tables", "FAIL", str(detail)[:120])

        # ==================================================================
        # SKIP: create_linked_table — needs external data source
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "create_linked_table", "SKIP",
               "Requires external data source — cannot test in isolation")

        # ==================================================================
        # SKIP: refresh_linked_table — needs existing linked table
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "refresh_linked_table", "SKIP",
               "Requires external data source — cannot test in isolation")

        # ==================================================================
        # SKIP: unlink_table — needs existing linked table
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "unlink_table", "SKIP",
               "Requires external data source — cannot test in isolation")

    finally:
        # ------------------------------------------------------------------
        # Cleanup
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")

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
        print("Linked Tables  —  Summary")
        print("============================================")
        print(f"  Total:  {test_helper.TOTAL}")
        print(f"  Pass:   {GREEN}{test_helper.PASS}{NC}")
        print(f"  Fail:   {RED}{test_helper.FAIL}{NC}")
        print(f"  Skip:   {YELLOW}{test_helper.SKIP}{NC}")
        print(f"  Results: {CYAN}{RESULTS_FILE}{NC}")
        print()

        sys.exit(0)


if __name__ == "__main__":
    main()
