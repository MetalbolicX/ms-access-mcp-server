#!/usr/bin/env python3
"""Dev Copy — HTTP integration tests for copy_database, get_dev_copy_status.

Tests: copy_database, get_dev_copy_status.
SKIP: create_dev_copy, deploy_dev_copy, discard_dev_copy
(require full dev copy lifecycle — file system mutation + connection switch).

Strategy: exercise the non-destructive subset of dev copy tools against a
real Access database. copy_database is tested with a file path within
EXPORT_DIR (must be in ACCESS_MCP_ALLOWED_DIRS) and verified via
os.path.exists. get_dev_copy_status is called with the production DB path
and validated for graceful return. The destructive create/deploy/discard
tools are recorded as SKIP with explanation since they modify the active
connection and write to production paths.
"""

import os
import sys
import time
from test_helper import *
import test_helper

TS = int(time.time())
COPY_PATH = os.path.join(EXPORT_DIR, f"test_dev_copy_{TS}.accdb")
TEST_NUM = 0

# Populated by copy_database response — server may normalize the path
COPY_DEST = None

CLEANUP_FILES = [COPY_PATH]


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Dev Copy Tests\n\n")


def main():
    global TEST_NUM, COPY_DEST

    print_header()

    print("=" * 60)
    print("Dev Copy      —  test-dev-copy.py")
    print("=" * 60)
    print()

    # Verify server is reachable
    check_server()

    # Open MCP session
    print(f"{CYAN}[INIT]{NC} Acquiring session...")
    init_session()
    print(f"  Session: {test_helper.SID}")
    print()

    # Connect to database with COM for dev copy tools
    print(f"{CYAN}[CONNECT]{NC}")
    resp = call_tool("connect_access", {"database_path": DB_PATH, "use_com": True})
    detail = extract_text_content(resp)
    if detail.get("connected") is True:
        print(f"  {GREEN}Connected{NC}")
    else:
        print(f"  {RED}Connect FAILED — cannot proceed (dev copy tools require COM){NC}")
        sys.exit(1)
    print()

    try:
        # ==================================================================
        # TEST 1: copy_database — copy the production DB to EXPORT_DIR
        # ==================================================================
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("copy_database", {"source": DB_PATH, "dest": COPY_PATH})
        detail = extract_text_content(resp)
        global COPY_DEST
        if detail.get("source") and detail.get("dest"):
            COPY_DEST = detail.get("dest")
            record(TEST_NUM, "copy_database", "PASS",
                   f"Copied DB from '{detail['source']}' to '{COPY_DEST}'")
        elif detail.get("success") is True:
            COPY_DEST = COPY_PATH
            record(TEST_NUM, "copy_database", "PASS",
                   f"Copied DB to '{COPY_PATH}'")
        else:
            COPY_DEST = None
            record(TEST_NUM, "copy_database", "FAIL",
                   f"success={detail.get('success')} error={detail.get('error', '?')}")

        # ------------------------------------------------------------------
        # Verify the copied file exists on disk (use response path)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        check_path = COPY_DEST or COPY_PATH
        if os.path.exists(check_path):
            size = os.path.getsize(check_path)
            record(TEST_NUM, "copy_database (file exists)", "PASS",
                   f"Copy file exists ({size} bytes) at '{check_path}'")
        else:
            record(TEST_NUM, "copy_database (file exists)", "FAIL",
                   f"Copy file not found at '{check_path}'")

        # ==================================================================
        # TEST 2: get_dev_copy_status — query current dev copy state
        # ==================================================================
        TEST_NUM += 1
        resp = call_tool("get_dev_copy_status", {"db_path": DB_PATH})
        detail = extract_text_content(resp)
        # Expect a graceful return with at least an "active" field
        if "active" in detail:
            is_active = detail.get("active")
            record(TEST_NUM, "get_dev_copy_status", "PASS",
                   f"active={is_active}")
        else:
            record(TEST_NUM, "get_dev_copy_status", "WARN",
                   f"No 'active' field in response: {str(detail)[:100]}")

        # ==================================================================
        # SKIP: create_dev_copy — destructive; modifies file system + connection
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "create_dev_copy", "SKIP",
               "Destructive: modifies file system and connection")

        # ==================================================================
        # SKIP: deploy_dev_copy — destructive; writes to production path
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "deploy_dev_copy", "SKIP",
               "Destructive: writes to production path")

        # ==================================================================
        # SKIP: discard_dev_copy — destructive; deletes files
        # ==================================================================
        TEST_NUM += 1
        record(TEST_NUM, "discard_dev_copy", "SKIP",
               "Destructive: deletes files")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: remove generated files
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")

        # Clean up both the original path and server-normalized path (if different)
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
        print("=" * 60)
        print("Dev Copy      —  Summary")
        print("=" * 60)
        print(f"  Total:  {test_helper.TOTAL}")
        print(f"  Pass:   {GREEN}{test_helper.PASS}{NC}")
        print(f"  Fail:   {RED}{test_helper.FAIL}{NC}")
        print(f"  Skip:   {YELLOW}{test_helper.SKIP}{NC}")
        print(f"  Results: {CYAN}{RESULTS_FILE}{NC}")
        print()

        sys.exit(0)


if __name__ == "__main__":
    main()
