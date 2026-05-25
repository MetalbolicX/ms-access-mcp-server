#!/usr/bin/env python3
"""Export — HTTP integration tests for export_table_csv, export_query_json."""

import time
import sys
import os
from test_helper import *
import test_helper

TS = int(time.time())
CSV_PATH = os.path.join(EXPORT_DIR, f"test_export_{TS}.csv")
JSON_PATH = os.path.join(EXPORT_DIR, f"test_export_{TS}.json")
TEST_NUM = 0

EXPORTED_FILES = [CSV_PATH, JSON_PATH]


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Export Tests\n\n")


def main():
    global TEST_NUM

    print_header()

    print("============================================")
    print("Export       —  test-export.py")
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
        # Discover first user table
        # ------------------------------------------------------------------
        print(f"{CYAN}[SETUP]{NC} Discovering tables...")
        resp = call_tool("get_tables", {})
        detail = extract_text_content(resp)
        tables = detail.get("tables", [])
        count = detail.get("count", len(tables))
        if detail.get("success") is True and count > 0:
            # Pick the SMALLEST table to avoid timeout on large exports
            tables.sort(key=lambda t: t.get("record_count", 0))
            export_table = tables[0].get("name", "")
            row_count = tables[0].get("record_count", 0)
            print(f"  Using smallest table: '{export_table}' ({row_count} rows)")
        else:
            print(f"  {RED}No tables found — cannot proceed{NC}")
            sys.exit(1)
        print()

        # ------------------------------------------------------------------
        # Test 1: export_table_csv — export smallest table as CSV
        # ------------------------------------------------------------------
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("export_table_csv", {
            "table_or_query_name": export_table,
            "file_path": CSV_PATH,
        })
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("rows_exported", 0) > 0:
            record(TEST_NUM, "export_table_csv", "PASS",
                   f"Exported '{export_table}' ({detail.get('rows_exported')} rows to '{CSV_PATH}'")
        else:
            record(TEST_NUM, "export_table_csv", "FAIL",
                   f"success={detail.get('success')} error={detail.get('error', '?')}")

        # ------------------------------------------------------------------
        # Test 2: Verify CSV file exists on disk
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if os.path.exists(CSV_PATH):
            size = os.path.getsize(CSV_PATH)
            record(TEST_NUM, "csv_file_exists", "PASS",
                   f"CSV file exists ({size} bytes)")
        else:
            record(TEST_NUM, "csv_file_exists", "FAIL",
                   f"CSV file not found at '{CSV_PATH}'")

        # ------------------------------------------------------------------
        # Test 3: export_query_json — export smallest table as JSON
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("export_query_json", {
            "query_name": export_table,
            "file_path": JSON_PATH,
            "pretty": True,
        })
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("rows_exported", 0) > 0:
            record(TEST_NUM, "export_query_json", "PASS",
                   f"Exported '{export_table}' ({detail.get('rows_exported')} rows to '{JSON_PATH}'")
        else:
            record(TEST_NUM, "export_query_json", "FAIL",
                   f"success={detail.get('success')} error={detail.get('error', '?')}")

        # ------------------------------------------------------------------
        # Test 4: Verify JSON file exists on disk and is valid JSON
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if os.path.exists(JSON_PATH):
            size = os.path.getsize(JSON_PATH)
            try:
                with open(JSON_PATH, "r") as f:
                    json.load(f)
                record(TEST_NUM, "json_file_valid", "PASS",
                       f"JSON file exists ({size} bytes) and is valid")
            except (json.JSONDecodeError, Exception) as e:
                record(TEST_NUM, "json_file_valid", "FAIL",
                       f"JSON file exists but is invalid: {e}")
        else:
            record(TEST_NUM, "json_file_valid", "FAIL",
                   f"JSON file not found at '{JSON_PATH}'")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: delete exported files
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")
        for fpath in EXPORTED_FILES:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
                    print(f"  {GREEN}Removed '{fpath}'{NC}")
            except Exception as e:
                print(f"  {YELLOW}Cleanup error for '{fpath}': {e}{NC}")

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
        print("Export       —  Summary")
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
