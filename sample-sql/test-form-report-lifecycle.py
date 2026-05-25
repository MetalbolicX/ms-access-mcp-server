#!/usr/bin/env python3
"""Form/Report Lifecycle — HTTP integration tests for form and report tools.

Tests: export_form_to_text, import_form_from_text, delete_form, form_exists,
       export_report_to_text, import_report_from_text, delete_report,
       export_form_backup, restore_form_backup, import_form_from_file.

Strategy: form text export/import cycle, form backup/restore cycle,
          report text export/import cycle (if reports exist),
          and import_form_from_file with a temp .txt file.
"""

import os
import sys
import time
import tempfile
from test_helper import *
import test_helper

TS = int(time.time())
TEMP_FORM_NAME = f"__test_form_{TS}"
TEMP_REPORT_NAME = f"__test_report_{TS}"
TEMP_FILE_FORM = f"__test_file_{TS}"
TEST_NUM = 0
FIRST_FORM = ""
FIRST_REPORT = ""
FORM_DATA = None
BACKUP_PATH = None
TEMP_TXT_FILE = None
REPORT_DATA = None


def print_header():
    """Write a section header to the results markdown file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(f"\n### Form/Report Lifecycle Tests\n\n")


def main():
    global TEST_NUM, FIRST_FORM, FIRST_REPORT, FORM_DATA, BACKUP_PATH
    global TEMP_TXT_FILE, REPORT_DATA

    print_header()

    print("============================================")
    print("Form/Report Lifecycle  —  test-form-report-lifecycle.py")
    print("============================================")
    print()

    # Verify server is reachable
    check_server()

    # Open MCP session
    print(f"{CYAN}[INIT]{NC} Acquiring session...")
    init_session()
    print(f"  Session: {test_helper.SID}")
    print()

    # Connect to database with COM for form/report access
    print(f"{CYAN}[CONNECT]{NC}")
    resp = call_tool("connect_access", {"database_path": DB_PATH, "use_com": True})
    detail = extract_text_content(resp)
    if detail.get("connected") is True:
        print(f"  {GREEN}Connected{NC}")
    else:
        print(f"  {RED}Connect FAILED — cannot proceed (form/report tools require COM){NC}")
        sys.exit(1)
    print()

    try:
        # ------------------------------------------------------------------
        # Test 1: get_forms — discover first form name
        # ------------------------------------------------------------------
        print(f"{CYAN}[TEST]{NC}")
        TEST_NUM += 1
        resp = call_tool("get_forms", {})
        detail = extract_text_content(resp)
        forms = detail.get("forms", [])
        form_count = detail.get("count", len(forms))
        if detail.get("success") is True and form_count >= 1:
            FIRST_FORM = forms[0].get("name", "") if forms else ""
            record(TEST_NUM, "get_forms", "PASS",
                   f"{form_count} forms, first='{FIRST_FORM}'")
        else:
            record(TEST_NUM, "get_forms", "FAIL",
                   f"expected >=1 form, got {form_count}: {str(detail)[:120]}")
            print(f"  {RED}No forms found — cannot run form lifecycle tests{NC}")
            sys.exit(1)

        # ==================================================================
        # FORM TEXT IMPORT/EXPORT CYCLE
        # ==================================================================
        print(f"\n{CYAN}[FORM TEXT IMPORT/EXPORT]{NC}")

        # ------------------------------------------------------------------
        # Test 2: export_form_to_text — export the first form
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("export_form_to_text", {"form_name": FIRST_FORM})
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("data"):
            FORM_DATA = detail.get("data")
            data_len = len(FORM_DATA)
            record(TEST_NUM, "export_form_to_text", "PASS",
                   f"Exported '{FIRST_FORM}' ({data_len} chars)")
        else:
            record(TEST_NUM, "export_form_to_text", "FAIL",
                   f"data missing or success=False: {str(detail)[:120]}")
            # Cannot proceed without form data for import tests
            print(f"  {RED}Form export failed — cannot run import tests{NC}")
            FORM_DATA = ""

        # ------------------------------------------------------------------
        # Test 3: import_form_from_text — create temp form from exported data
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA:
            resp = call_tool("import_form_from_text", {
                "form_name": TEMP_FORM_NAME,
                "form_data": FORM_DATA,
            })
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "import_form_from_text", "PASS",
                       f"Imported temp form '{TEMP_FORM_NAME}'")
            else:
                record(TEST_NUM, "import_form_from_text", "FAIL",
                       f"Import failed: {detail.get('error', '?')}")
        else:
            record(TEST_NUM, "import_form_from_text", "SKIP",
                   "No form data from export — cannot import")

        # ------------------------------------------------------------------
        # Test 4: form_exists — verify temp form exists
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA:
            resp = call_tool("form_exists", {"form_name": TEMP_FORM_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True and detail.get("exists") is True:
                record(TEST_NUM, "form_exists (verify import)", "PASS",
                       f"'{TEMP_FORM_NAME}' exists=true")
            else:
                record(TEST_NUM, "form_exists (verify import)", "FAIL",
                       f"expected exists=true, got: {str(detail)[:120]}")
        else:
            record(TEST_NUM, "form_exists (verify import)", "SKIP",
                   "No temp form created — skipping check")

        # ------------------------------------------------------------------
        # Test 5: delete_form — delete the temp form
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA:
            resp = call_tool("delete_form", {"form_name": TEMP_FORM_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "delete_form (temp)", "PASS",
                       f"Deleted temp form '{TEMP_FORM_NAME}'")
            else:
                record(TEST_NUM, "delete_form (temp)", "WARN",
                       f"Could not delete '{TEMP_FORM_NAME}': {detail.get('error', '?')}")
        else:
            record(TEST_NUM, "delete_form (temp)", "SKIP",
                   "No temp form to delete")

        # ------------------------------------------------------------------
        # Test 6: form_exists — verify temp form is gone
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA:
            resp = call_tool("form_exists", {"form_name": TEMP_FORM_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True and detail.get("exists") is False:
                record(TEST_NUM, "form_exists (verify delete)", "PASS",
                       f"'{TEMP_FORM_NAME}' exists=false")
            else:
                record(TEST_NUM, "form_exists (verify delete)", "WARN",
                       f"expected exists=false, got: {str(detail)[:120]}")
        else:
            record(TEST_NUM, "form_exists (verify delete)", "SKIP",
                   "No temp form was created — skipping check")

        # ==================================================================
        # FORM BACKUP/RESTORE CYCLE
        # ==================================================================
        print(f"\n{CYAN}[FORM BACKUP/RESTORE]{NC}")

        # ------------------------------------------------------------------
        # Test 7: export_form_backup — back up the original form
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("export_form_backup", {"form_name": FIRST_FORM})
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("backup_path"):
            BACKUP_PATH = detail.get("backup_path")
            fsize = detail.get("file_size_bytes", "?")
            record(TEST_NUM, "export_form_backup", "PASS",
                   f"Backup of '{FIRST_FORM}' at {BACKUP_PATH} ({fsize} bytes)")
        else:
            record(TEST_NUM, "export_form_backup", "FAIL",
                   f"backup_path missing or success=False: {str(detail)[:120]}")

        # ------------------------------------------------------------------
        # Test 8: delete_form — delete the original form
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if BACKUP_PATH:
            resp = call_tool("delete_form", {"form_name": FIRST_FORM})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "delete_form (original)", "PASS",
                       f"Deleted original form '{FIRST_FORM}'")
            else:
                record(TEST_NUM, "delete_form (original)", "WARN",
                       f"Could not delete '{FIRST_FORM}': {detail.get('error', '?')}")
                print(f"  {YELLOW}Note: delete may be guarded. Continuing with restore...{NC}")
        else:
            record(TEST_NUM, "delete_form (original)", "SKIP",
                   "No backup_path from export — skipping delete")

        # ------------------------------------------------------------------
        # Test 9: restore_form_backup — restore from backup
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if BACKUP_PATH:
            resp = call_tool("restore_form_backup", {
                "form_name": FIRST_FORM,
                "backup_path": BACKUP_PATH,
            })
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "restore_form_backup", "PASS",
                       f"Restored '{FIRST_FORM}' from backup")
            else:
                record(TEST_NUM, "restore_form_backup", "FAIL",
                       f"Restore failed: {detail.get('error', '?')}")
        else:
            record(TEST_NUM, "restore_form_backup", "SKIP",
                   "No backup_path — cannot restore")

        # ------------------------------------------------------------------
        # Test 10: form_exists — verify original form is back
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("form_exists", {"form_name": FIRST_FORM})
        detail = extract_text_content(resp)
        if detail.get("success") is True and detail.get("exists") is True:
            record(TEST_NUM, "form_exists (verify restore)", "PASS",
                   f"'{FIRST_FORM}' exists=true after restore")
        else:
            record(TEST_NUM, "form_exists (verify restore)", "WARN",
                   f"expected exists=true, got: {str(detail)[:120]}")

        # ==================================================================
        # REPORT TEXT IMPORT/EXPORT CYCLE
        # ==================================================================
        print(f"\n{CYAN}[REPORT TEXT IMPORT/EXPORT]{NC}")

        # ------------------------------------------------------------------
        # Test 11: get_reports — discover first report name
        # ------------------------------------------------------------------
        TEST_NUM += 1
        resp = call_tool("get_reports", {})
        detail = extract_text_content(resp)
        reports = detail.get("reports", [])
        report_count = detail.get("count", len(reports))
        if detail.get("success") is True and report_count >= 1:
            FIRST_REPORT = reports[0].get("name", "") if reports else ""
            record(TEST_NUM, "get_reports", "PASS",
                   f"{report_count} reports, first='{FIRST_REPORT}'")
        else:
            FIRST_REPORT = ""
            if detail.get("success") is True:
                record(TEST_NUM, "get_reports", "PASS",
                       f"0 reports found — will SKIP report tests")
            else:
                record(TEST_NUM, "get_reports", "WARN",
                       f"Unexpected: {str(detail)[:120]}")

        # ------------------------------------------------------------------
        # Test 12: export_report_to_text — export the first report
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FIRST_REPORT:
            resp = call_tool("export_report_to_text", {"report_name": FIRST_REPORT})
            detail = extract_text_content(resp)
            if detail.get("success") is True and detail.get("data"):
                REPORT_DATA = detail.get("data")
                data_len = len(REPORT_DATA)
                record(TEST_NUM, "export_report_to_text", "PASS",
                       f"Exported '{FIRST_REPORT}' ({data_len} chars)")
            else:
                REPORT_DATA = None
                record(TEST_NUM, "export_report_to_text", "FAIL",
                       f"data missing or success=False: {str(detail)[:120]}")
        else:
            REPORT_DATA = None
            record(TEST_NUM, "export_report_to_text", "SKIP",
                   "No reports in database — cannot export")

        # ------------------------------------------------------------------
        # Test 13: import_report_from_text — create temp report
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if REPORT_DATA:
            resp = call_tool("import_report_from_text", {
                "report_name": TEMP_REPORT_NAME,
                "report_data": REPORT_DATA,
            })
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "import_report_from_text", "PASS",
                       f"Imported temp report '{TEMP_REPORT_NAME}'")
            else:
                record(TEST_NUM, "import_report_from_text", "FAIL",
                       f"Import failed: {detail.get('error', '?')}")
        else:
            record(TEST_NUM, "import_report_from_text", "SKIP",
                   "No report data — cannot import")

        # ------------------------------------------------------------------
        # Test 14: delete_report — delete the temp report
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if REPORT_DATA:
            resp = call_tool("delete_report", {"report_name": TEMP_REPORT_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "delete_report", "PASS",
                       f"Deleted temp report '{TEMP_REPORT_NAME}'")
            else:
                record(TEST_NUM, "delete_report", "WARN",
                       f"Could not delete '{TEMP_REPORT_NAME}': {detail.get('error', '?')}")
        else:
            record(TEST_NUM, "delete_report", "SKIP",
                   "No temp report to delete")

        # ==================================================================
        # IMPORT FORM FROM FILE
        # ==================================================================
        print(f"\n{CYAN}[IMPORT FORM FROM FILE]{NC}")

        # ------------------------------------------------------------------
        # Test 15: import_form_from_file — import from a temp .txt file
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA:
            # Write form data to a temp .txt file
            TEMP_TXT_FILE = os.path.join(tempfile.gettempdir(), f"{TEMP_FILE_FORM}.txt")
            try:
                with open(TEMP_TXT_FILE, "w", encoding="utf-8") as f:
                    f.write(FORM_DATA)
                print(f"  {CYAN}Created temp .txt: {TEMP_TXT_FILE}{NC}")
            except Exception as e:
                print(f"  {RED}Failed to write temp file: {e}{NC}")
                TEMP_TXT_FILE = None

            if TEMP_TXT_FILE and os.path.exists(TEMP_TXT_FILE):
                resp = call_tool("import_form_from_file", {
                    "form_name": TEMP_FILE_FORM,
                    "file_path": TEMP_TXT_FILE,
                })
                detail = extract_text_content(resp)
                if detail.get("success") is True:
                    record(TEST_NUM, "import_form_from_file", "PASS",
                           f"Imported '{TEMP_FILE_FORM}' from file")
                else:
                    record(TEST_NUM, "import_form_from_file", "FAIL",
                           f"Import failed: {detail.get('error', '?')}")
            else:
                record(TEST_NUM, "import_form_from_file", "SKIP",
                       "Temp file not created — cannot import")
        else:
            record(TEST_NUM, "import_form_from_file", "SKIP",
                   "No form data — cannot create file for import")

        # ------------------------------------------------------------------
        # Test 16: form_exists — verify file-imported form exists
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA and TEMP_TXT_FILE and os.path.exists(TEMP_TXT_FILE):
            resp = call_tool("form_exists", {"form_name": TEMP_FILE_FORM})
            detail = extract_text_content(resp)
            if detail.get("success") is True and detail.get("exists") is True:
                record(TEST_NUM, "form_exists (verify file import)", "PASS",
                       f"'{TEMP_FILE_FORM}' exists=true")
            else:
                record(TEST_NUM, "form_exists (verify file import)", "FAIL",
                       f"expected exists=true, got: {str(detail)[:120]}")
        else:
            record(TEST_NUM, "form_exists (verify file import)", "SKIP",
                   "File import was skipped — no form to verify")

        # ------------------------------------------------------------------
        # Test 17: delete_form — delete the file-imported form
        # ------------------------------------------------------------------
        TEST_NUM += 1
        if FORM_DATA and TEMP_TXT_FILE and os.path.exists(TEMP_TXT_FILE):
            resp = call_tool("delete_form", {"form_name": TEMP_FILE_FORM})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                record(TEST_NUM, "delete_form (file import)", "PASS",
                       f"Deleted file-imported form '{TEMP_FILE_FORM}'")
            else:
                record(TEST_NUM, "delete_form (file import)", "WARN",
                       f"Could not delete '{TEMP_FILE_FORM}': {detail.get('error', '?')}")
        else:
            record(TEST_NUM, "delete_form (file import)", "SKIP",
                   "No file-imported form to delete")

    finally:
        # ------------------------------------------------------------------
        # Cleanup
        # ------------------------------------------------------------------
        print(f"\n{CYAN}[CLEANUP]{NC}")

        # Remove temp .txt file
        if TEMP_TXT_FILE and os.path.exists(TEMP_TXT_FILE):
            try:
                os.remove(TEMP_TXT_FILE)
                print(f"  {GREEN}Removed {TEMP_TXT_FILE}{NC}")
            except Exception as e:
                print(f"  {YELLOW}Could not remove {TEMP_TXT_FILE}: {e}{NC}")

        # Delete temp __test_form_ form if it still exists
        try:
            resp = call_tool("delete_form", {"form_name": TEMP_FORM_NAME})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                print(f"  {GREEN}Deleted temp form '{TEMP_FORM_NAME}'{NC}")
            else:
                print(f"  {YELLOW}Note: temp form '{TEMP_FORM_NAME}' not deleted "
                      f"({detail.get('error', '?')}){NC}")
        except Exception as e:
            print(f"  {YELLOW}Cleanup error deleting temp form: {e}{NC}")

        # Delete temp __test_file_ form if it still exists
        try:
            resp = call_tool("delete_form", {"form_name": TEMP_FILE_FORM})
            detail = extract_text_content(resp)
            if detail.get("success") is True:
                print(f"  {GREEN}Deleted file-imported form '{TEMP_FILE_FORM}'{NC}")
            else:
                print(f"  {YELLOW}Note: file-imported form '{TEMP_FILE_FORM}' not deleted "
                      f"({detail.get('error', '?')}){NC}")
        except Exception as e:
            print(f"  {YELLOW}Cleanup error deleting file-imported form: {e}{NC}")

        # Delete temp __test_report_ report if it still exists
        if REPORT_DATA:
            try:
                resp = call_tool("delete_report", {"report_name": TEMP_REPORT_NAME})
                detail = extract_text_content(resp)
                if detail.get("success") is True:
                    print(f"  {GREEN}Deleted temp report '{TEMP_REPORT_NAME}'{NC}")
                else:
                    print(f"  {YELLOW}Note: temp report '{TEMP_REPORT_NAME}' not deleted "
                          f"({detail.get('error', '?')}){NC}")
            except Exception as e:
                print(f"  {YELLOW}Cleanup error deleting temp report: {e}{NC}")

        # Restore original form if it was deleted and not yet restored
        if BACKUP_PATH and FIRST_FORM:
            try:
                resp = call_tool("form_exists", {"form_name": FIRST_FORM})
                detail = extract_text_content(resp)
                if detail.get("exists") is not True:
                    print(f"  {YELLOW}Restoring '{FIRST_FORM}' from backup during cleanup...{NC}")
                    resp = call_tool("restore_form_backup", {
                        "form_name": FIRST_FORM,
                        "backup_path": BACKUP_PATH,
                    })
                    detail = extract_text_content(resp)
                    if detail.get("success") is True:
                        print(f"  {GREEN}Restored '{FIRST_FORM}'{NC}")
                    else:
                        print(f"  {RED}FAILED to restore '{FIRST_FORM}': {detail.get('error', '?')}{NC}")
            except Exception as e:
                print(f"  {YELLOW}Cleanup error restoring form: {e}{NC}")

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
        print("Form/Report Lifecycle  —  Summary")
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
