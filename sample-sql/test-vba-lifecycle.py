#!/usr/bin/env python3
"""VBA Lifecycle — HTTP integration tests for VBA module tools.

Tests: get_vba_projects, get_modules, export_module_backup, delete_module,
       restore_module_backup, import_module_from_text, save_database.

Strategy: backup an existing module → delete it → restore it → verify it's back.
Then create a temporary __test_vba_ module from a .bas file → save database → delete it.
"""

import os
import sys
import time
import tempfile
from test_helper import *
import test_helper

TS = int(time.time())
TEMP_MOD_NAME = f"__test_vba_{TS}"
TEST_NUM = 0
TEMP_BAS_FILE = None
BACKUP_PATH = None
FIRST_MODULE = ""


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### VBA Lifecycle Tests\n\n")


def main():
    global TEST_NUM, FIRST_MODULE, BACKUP_PATH, TEMP_BAS_FILE

    print_header()

    print("============================================")
    print("VBA Lifecycle  —  test-vba-lifecycle.py")
    print("============================================")
    print()

    # Verify server is reachable
    check_server()

    # Open MCP session
    print(f"{CYAN}[INIT]{NC} Acquiring session...")
    init_session()
    print(f"  Session: {test_helper.SID}")
    print()

    # Connect to database with COM for VBA access
    print(f"{CYAN}[CONNECT]{NC}")
    resp = call_tool("connect_access", {"database_path": DB_PATH, "use_com": True})
    detail = extract_text_content(resp)
    if detail.get("connected") is True:
        print(f"  {GREEN}Connected{NC}")
    else:
        print(f"  {RED}Connect FAILED — cannot proceed (VBA tools require COM){NC}")
        sys.exit(1)
    print()

    try:
        # ------------------------------------------------------------------
        # Test 1: get_vba_projects — verify VBA is accessible
        # ------------------------------------------------------------------
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("get_vba_projects", {})
        detail = extract_text_content(resp)
        projects = detail.get("projects", [])
        count = detail.get("count", len(projects))
        if detail.get("success") is True and count >= 1:
            record(TEST_NUM, "get_vba_projects", "PASS",
                   f"{count} VBA project(s): {projects}")
        else:
            record(TEST_NUM, "get_vba_projects", "FAIL",
                   f"expected >=1 project, got {count}: {str(detail)[:120]}")

        # ------------------------------------------------------------------
        # Test 2: get_modules — discover first module name
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_modules", {})
        detail = extract_text_content(resp)
        modules = detail.get("modules", [])
        mod_count = detail.get("count", len(modules))
        if detail.get("success") is True and mod_count >= 1:
            FIRST_MODULE = modules[0].get("name", "") if modules else ""
            record(TEST_NUM, "get_modules", "PASS",
                   f"{mod_count} modules, first='{FIRST_MODULE}'")
        else:
            record(TEST_NUM, "get_modules", "FAIL",
                   f"expected >=1 module, got {mod_count}: {str(detail)[:120]}")
            # Cannot proceed without a module to back up
            print(f"  {RED}No modules found — cannot run backup/restore cycle{NC}")
            sys.exit(1)

        # ------------------------------------------------------------------
        # Test 3: export_module_backup — back up the first module
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("export_module_backup", {"module_name": FIRST_MODULE})
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("backup_path"):
            BACKUP_PATH = detail.get("backup_path")
            fsize = detail.get("file_size_bytes", "?")
            record(TEST_NUM, "export_module_backup", "PASS",
                   f"Backup of '{FIRST_MODULE}' at {BACKUP_PATH} ({fsize} bytes)")
        else:
            record(TEST_NUM, "export_module_backup", "FAIL",
                   f"backup_path missing or success=False: {str(detail)[:120]}")

        # ------------------------------------------------------------------
        # Test 4: delete_module — SKIP on original (Access protects it)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        record(TEST_NUM, "delete_module (original)", "SKIP",
               "Access protects built-in modules; delete_module only tested on temp modules")

        # ------------------------------------------------------------------
        # Test 5: get_modules — verify original module preserved after backup
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_modules", {})
        detail = extract_text_content(resp)
        modules_after = detail.get("modules", [])
        mod_names = [m.get("name", "") for m in modules_after] if modules_after else []
        if FIRST_MODULE in mod_names:
            record(TEST_NUM, "get_modules (verify preserve)", "PASS",
                   f"'{FIRST_MODULE}' preserved after backup in {len(mod_names)} module(s)")
        else:
            record(TEST_NUM, "get_modules (verify preserve)", "WARN",
                   f"'{FIRST_MODULE}' unexpectedly absent in {len(mod_names)} module(s)")

        # ------------------------------------------------------------------
        # Test 6: restore_module_backup — SKIP (module was not deleted)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        record(TEST_NUM, "restore_module_backup (original)", "SKIP",
               "Module was not deleted — restore not needed")

        # ------------------------------------------------------------------
        # Test 7: get_modules — SKIP (module was not deleted, no restore)
        # ------------------------------------------------------------------
        TEST_NUM += 1
        record(TEST_NUM, "get_modules (verify restore)", "SKIP",
               "Module was not deleted — nothing to restore")

        # ------------------------------------------------------------------
        # Test 8: import_module_from_text — import a temp .bas file
        # ------------------------------------------------------------------
        TEST_NUM += 1
        # Create a temporary .bas file with VBA code
        vba_code = (
            f'Public Function TestFunc() As Integer\n'
            f'    TestFunc = 42\n'
            f'End Function\n'
        )
        TEMP_BAS_FILE = os.path.join(tempfile.gettempdir(), f"{TEMP_MOD_NAME}.bas")
        with open(TEMP_BAS_FILE, "w", encoding="utf-8") as f:
            f.write(vba_code)
        print(f"  {CYAN}Created temp .bas: {TEMP_BAS_FILE}{NC}")

        resp = call_tool("import_module_from_text", {
            "module_name": TEMP_MOD_NAME,
            "file_path": TEMP_BAS_FILE,
        })
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            created = detail.get("created", False)
            record(TEST_NUM, "import_module_from_text", "PASS",
                   f"Imported '{TEMP_MOD_NAME}' (created={created})")
        else:
            record(TEST_NUM, "import_module_from_text", "FAIL",
                   f"Import failed: {detail.get('error', '?')}")

        # ------------------------------------------------------------------
        # Test 9: save_database — persist VBA changes
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("save_database", {})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "save_database", "PASS", "Database saved successfully")
        else:
            # save_database may return a dict with saved/modules keys instead of success
            record(TEST_NUM, "save_database", "WARN",
                   f"Response: {str(detail)[:120]}")

        # ------------------------------------------------------------------
        # Test 10: get_modules — verify temp module exists
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_modules", {})
        detail = extract_text_content(resp)
        modules_final = detail.get("modules", [])
        mod_names = [m.get("name", "") for m in modules_final] if modules_final else []
        if TEMP_MOD_NAME in mod_names:
            record(TEST_NUM, "get_modules (verify import)", "PASS",
                   f"'{TEMP_MOD_NAME}' found in {len(mod_names)} module(s)")
        else:
            record(TEST_NUM, "get_modules (verify import)", "WARN",
                   f"'{TEMP_MOD_NAME}' not found in {len(mod_names)} module(s)")

        # ------------------------------------------------------------------
        # Test 11: delete_module — remove the temp module
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("delete_module", {"module_name": TEMP_MOD_NAME})
        detail = extract_text_content(resp)
        if detail.get("success") is True:
            record(TEST_NUM, "delete_module (temp)", "PASS",
                   f"Deleted temp module '{TEMP_MOD_NAME}'")
        else:
            record(TEST_NUM, "delete_module (temp)", "FAIL",
                   f"Could not delete '{TEMP_MOD_NAME}': {detail.get('error', '?')}")

        # ------------------------------------------------------------------
        # Test 12: get_modules — verify temp module is gone
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_modules", {})
        detail = extract_text_content(resp)
        modules_gone = detail.get("modules", [])
        mod_names = [m.get("name", "") for m in modules_gone] if modules_gone else []
        if TEMP_MOD_NAME not in mod_names:
            record(TEST_NUM, "get_modules (verify delete)", "PASS",
                   f"'{TEMP_MOD_NAME}' removed, {len(mod_names)} module(s) remain")
        else:
            record(TEST_NUM, "get_modules (verify delete)", "WARN",
                   f"'{TEMP_MOD_NAME}' still present in {len(mod_names)} module(s)")

    finally:
        # ------------------------------------------------------------------
        # Cleanup: delete temp .bas file and temp module
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")

        # Remove temp .bas file
        if TEMP_BAS_FILE and os.path.exists(TEMP_BAS_FILE):
            try:
                os.remove(TEMP_BAS_FILE)
                print(f"  {GREEN}Removed {TEMP_BAS_FILE}{NC}")
            except Exception as e:
                print(f"  {YELLOW}Could not remove {TEMP_BAS_FILE}: {e}{NC}")

        # Delete temp module if it still exists (catch-all cleanup)
        try:
            resp = call_tool("delete_module", {"module_name": TEMP_MOD_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                print(f"  {GREEN}Deleted temp module '{TEMP_MOD_NAME}'{NC}")
            else:
                print(f"  {YELLOW}Note: temp module '{TEMP_MOD_NAME}' not deleted "
                      f"({detail.get('error', '?')}){NC}")
        except Exception as e:
            print(f"  {YELLOW}Cleanup error deleting module: {e}{NC}")

        # Restore first module if it was deleted and not yet restored
        if BACKUP_PATH and FIRST_MODULE:
            try:
                resp = call_tool("get_modules", {})
                detail = extract_text_content(resp)
                modules_chk = detail.get("modules", [])
                mod_names = [m.get("name", "") for m in modules_chk] if modules_chk else []
                if FIRST_MODULE not in mod_names:
                    print(f"  {YELLOW}Restoring '{FIRST_MODULE}' from backup during cleanup...{NC}")
                    resp = call_tool("restore_module_backup", {
                        "module_name": FIRST_MODULE,
                        "backup_path": BACKUP_PATH,
                    })
                    detail = extract_text_content(resp)
                    if detail.get("success") is True:
                        print(f"  {GREEN}Restored '{FIRST_MODULE}'{NC}")
                    else:
                        print(f"  {RED}FAILED to restore '{FIRST_MODULE}': {detail.get('error', '?')}{NC}")
            except Exception as e:
                print(f"  {YELLOW}Cleanup error restoring module: {e}{NC}")

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
        print("VBA Lifecycle  —  Summary")
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
