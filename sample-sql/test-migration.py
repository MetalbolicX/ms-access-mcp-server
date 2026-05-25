#!/usr/bin/env python3
"""Migration — HTTP integration tests for migration tools.

Tests: extract_schema, generate_sql, compact_repair, get_migration_status.
SKIP: upload_schema, transfer_data (require external target DB).

Strategy: extract the schema from the live database, generate a SQL DDL file
to disk, compact a copy of the database, and verify graceful error handling
for nonexistent migration jobs. Tools that require an external target
database are recorded as SKIP with explanation.
"""

import os
import sys
import time
from test_helper import *
import test_helper

TS = int(time.time())
DDL_PATH = os.path.join(EXPORT_DIR, f"test_ddl_{TS}.sql")
COPY_PATH = os.path.join(EXPORT_DIR, f"test_copy_{TS}.accdb")
COMPACTED_PATH = os.path.join(EXPORT_DIR, f"test_compacted_{TS}.accdb")
TEST_NUM = 0

CLEANUP_FILES = [DDL_PATH, COPY_PATH, COMPACTED_PATH]

# Populated by copy_database response — server may normalize the path
COPY_DEST = None


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Migration Tests\n\n")


def main():
    global TEST_NUM, COPY_DEST

    print_header()

    print("============================================")
    print("Migration     —  test-migration.py")
    print("============================================")
    print()

    # Verify server is reachable
    check_server()

    # Open MCP session
    print(f"{CYAN}[INIT]{NC} Acquiring session...")
    init_session()
    print(f"  Session: {test_helper.SID}")
    print()

    # Connect to database with COM for migration tools
    print(f"{CYAN}[CONNECT]{NC}")
    resp = call_tool("connect_access", {"database_path": DB_PATH, "use_com": True})
    detail = extract_text_content(resp)
    if detail.get("connected") is True:
        print(f"  {GREEN}Connected{NC}")
    else:
        print(f"  {RED}Connect FAILED — cannot proceed (migration tools require COM){NC}")
        sys.exit(1)
    print()

    try:
        # ==================================================================
        # TEST 1: extract_schema — retrieve DB schema
        # ==================================================================
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("extract_schema", {"database_path": DB_PATH})
        detail = extract_text_content(resp)
        # Debug: show keys when response is unexpected
        if not detail.get("success"):
            print(f"  {YELLOW}DEBUG response keys: {list(detail.keys())}{NC}")
            print(f"  {YELLOW}DEBUG response: {str(detail)[:200]}{NC}")
            # Try unwrapping from alternate response shapes
            if "schema" in detail:
                detail = detail["schema"]
        if detail.get("success") is True and "tables" in detail:
            num_tables = len(detail.get("tables", []))
            num_queries = len(detail.get("queries", []))
            record(TEST_NUM, "extract_schema", "PASS",
                   f"Schema extracted: {num_tables} tables, {num_queries} queries")
        else:
            record(TEST_NUM, "extract_schema", "FAIL",
                   f"success={detail.get('success')} keys={list(detail.keys())[:6]} error={detail.get('error', '?')}")

        # ==================================================================
        # TEST 2: generate_sql — create DDL file on disk
        # ==================================================================
        TEST_NUM += 1
        resp = call_tool("generate_sql", {"output_path": DDL_PATH})
        detail = extract_text_content(resp)
        # Debug: show keys when response is unexpected
        if not detail.get("success"):
            print(f"  {YELLOW}DEBUG response keys: {list(detail.keys())}{NC}")
            print(f"  {YELLOW}DEBUG response: {str(detail)[:200]}{NC}")
        if detail.get("success") is True:
            record(TEST_NUM, "generate_sql", "PASS",
                   f"DDL generated at '{DDL_PATH}'")
        else:
            record(TEST_NUM, "generate_sql", "FAIL",
                   f"success={detail.get('success')} keys={list(detail.keys())[:6]} error={detail.get('error', '?')}")

        # ------------------------------------------------------------------
        # Verify DDL file exists on disk
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if os.path.exists(DDL_PATH):
            size = os.path.getsize(DDL_PATH)
            record(TEST_NUM, "ddl_file_exists", "PASS",
                   f"DDL file exists ({size} bytes)")
        else:
            record(TEST_NUM, "ddl_file_exists", "FAIL",
                   f"DDL file not found at '{DDL_PATH}'")

        # ==================================================================
        # TEST 3: compact_repair — via copy
        # ==================================================================
        # First create a copy of the database to avoid touching the original
        TEST_NUM += 1
        resp = call_tool("copy_database", {"source": DB_PATH, "dest": COPY_PATH})
        detail = extract_text_content(resp)
        global COPY_DEST
        if detail.get("source") and detail.get("dest"):
            COPY_DEST = detail.get("dest")
            record(TEST_NUM, "copy_database (for compact)", "PASS",
                   f"Copied DB from '{detail['source']}' to '{COPY_DEST}'")
        elif detail.get("success") is True:
            COPY_DEST = COPY_PATH
            record(TEST_NUM, "copy_database (for compact)", "PASS",
                   f"Copied DB to '{COPY_PATH}'")
        else:
            COPY_DEST = None
            record(TEST_NUM, "copy_database (for compact)", "FAIL",
                   f"success={detail.get('success')} error={detail.get('error', '?')}")

        # Compact the copy using compact_repair
        TEST_NUM += 1
        compact_source = COPY_DEST or COPY_PATH
        resp = call_tool("compact_repair", {
            "action": "compact",
            "source_path": compact_source,
            "dest_path": COMPACTED_PATH,
            "keep_original": True,
        })
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "compact_repair", "PASS",
                   f"Compacted to '{COMPACTED_PATH}'")
        else:
            record(TEST_NUM, "compact_repair", "FAIL",
                   f"success={detail.get('success')} error={detail.get('error', '?')} "
                   f"source={compact_source}")

        # Verify compacted file exists on disk
        TEST_NUM += 1
        if os.path.exists(COMPACTED_PATH):
            size = os.path.getsize(COMPACTED_PATH)
            record(TEST_NUM, "compacted_file_exists", "PASS",
                   f"Compacted file exists ({size} bytes)")
        else:
            record(TEST_NUM, "compacted_file_exists", "FAIL",
                   f"Compacted file not found at '{COMPACTED_PATH}'")

        # ==================================================================
        # TEST 4: get_migration_status — nonexistent job (graceful error)
        # ==================================================================
        TEST_NUM += 1
        resp = call_tool("get_migration_status", {"job_id": "nonexistent_job_id"})
        detail = extract_text_content(resp)
        # Expect a graceful error (success=false with error message), not a crash
        if detail.get("success") is False:
            err = detail.get("error", "Job not found")
            record(TEST_NUM, "get_migration_status (invalid)", "PASS",
                   f"Graceful error: {err[:100]}")
        elif "error" in detail:
            err = detail["error"]
            record(TEST_NUM, "get_migration_status (invalid)", "PASS",
                   f"Graceful error via 'error' key: {err[:100]}")
        elif isinstance(detail, dict) and detail.get("success") is True:
            record(TEST_NUM, "get_migration_status (invalid)", "WARN",
                   f"Unexpected success for nonexistent job: {str(detail)[:100]}")
        else:
            record(TEST_NUM, "get_migration_status (invalid)", "WARN",
                   f"Unexpected response: {str(detail)[:120]}")

        # ==================================================================
        # SKIP: upload_schema — requires external target DB
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "upload_schema", "SKIP",
               "Requires external target DB — cannot test in isolation")

        # ==================================================================
        # SKIP: transfer_data — requires external target DB
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "transfer_data", "SKIP",
               "Requires external target DB — cannot test in isolation")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: remove generated files
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")

        # Clean up both the original paths and server-normalized path (if different)
        cleanup_paths = set(CLEANUP_FILES)
        if COPY_DEST and COPY_DEST != COPY_PATH:
            cleanup_paths.add(COPY_DEST)
        for fpath in cleanup_paths:
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
        print("Migration     —  Summary")
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
