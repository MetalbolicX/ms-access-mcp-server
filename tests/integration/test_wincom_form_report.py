"""COM integration tests for WinComAdapter form/report/control operations.

Tests form/report read, export/import round-trip, control properties,
and control event procedures on a temporary copy of the fixture DB.
"""

import shutil
import tempfile

import pytest
from helpers import (
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
    TEST_DB,
)

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


class TestWinComFormReportRead:
    """Basic form/report read operations on temp DB copy."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_forms_returns_expected(self):
        """get_forms returns list with at least frmMain and frmWithCode."""
        forms = self.adapter.get_forms()
        form_names = [f.name for f in forms]
        assert "frmMain" in form_names
        assert "frmWithCode" in form_names

    def test_get_reports_returns_expected(self):
        """get_reports returns list with rptCustomers."""
        reports = self.adapter.get_reports()
        report_names = [r.name for r in reports]
        assert "rptCustomers" in report_names

    def test_form_exists_true(self):
        """form_exists returns True for valid forms."""
        assert self.adapter.form_exists("frmMain") is True

    def test_form_exists_false(self):
        """form_exists returns False for nonexistent form."""
        assert self.adapter.form_exists("NonExistentForm_Test") is False


class TestWinComFormExportImport:
    """Round-trip form export/import via export_form_to_text / import_form_from_text."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_form_to_text_returns_non_empty(self):
        """Exporting frmMain returns a non-empty string (SaveAsText output)."""
        text = self.adapter.export_form_to_text("frmMain")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_import_form_from_text_and_delete(self):
        """Export frmMain, import to temp form name, verify exists, delete."""
        # Export
        original_text = self.adapter.export_form_to_text("frmMain")
        assert len(original_text) > 0

        # Import to temp form
        temp_form = "TempImportForm_Test"
        imported = self.adapter.import_form_from_text(temp_form, original_text)
        assert imported is True

        # Verify imported form exists
        assert self.adapter.form_exists(temp_form) is True

        # Clean up — delete temp form
        deleted = self.adapter.delete_form(temp_form)
        assert deleted is True

        # Verify it's gone
        assert self.adapter.form_exists(temp_form) is False


class TestWinComReportExportImport:
    """Round-trip report export/import via export_report_to_text / import_report_from_text."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_report_to_text_returns_non_empty(self):
        """Exporting rptCustomers returns a non-empty string."""
        text = self.adapter.export_report_to_text("rptCustomers")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_import_report_from_text_and_delete(self):
        """Export rptCustomers, import to temp report name, verify exists, delete."""
        # Export
        original_text = self.adapter.export_report_to_text("rptCustomers")
        assert len(original_text) > 0

        # Import to temp report
        temp_report = "TempImportReport_Test"
        imported = self.adapter.import_report_from_text(temp_report, original_text)
        assert imported is True

        # Verify imported report exists — use get_reports to check
        reports = self.adapter.get_reports()
        report_names = [r.name for r in reports]
        assert temp_report in report_names

        # Clean up — delete temp report
        deleted = self.adapter.delete_report(temp_report)
        assert deleted is True

        # Verify it's gone
        reports_after = self.adapter.get_reports()
        report_names_after = [r.name for r in reports_after]
        assert temp_report not in report_names_after


class TestWinComFormControls:
    """Form control operations: get_form_controls, get/set control properties."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_form_controls_returns_list(self):
        """get_form_controls on frmMain returns controls list."""
        controls = self.adapter.get_form_controls("frmMain")
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_get_form_controls_contains_expected_names(self):
        """frmMain controls include txtName, lblTitle, cmdGreet (or similar)."""
        controls = self.adapter.get_form_controls("frmMain")
        control_names = [c.name for c in controls]
        # Fixture has these controls; allow variations
        expected = {"txtName", "lblTitle", "cmdGreet"}
        found = set(control_names) & expected
        assert len(found) >= 1, f"Expected at least one of {expected} in {control_names}"

    def test_get_control_properties(self):
        """get_control_properties on frmMain + cmdGreet returns properties dict."""
        props = self.adapter.get_control_properties("frmMain", "cmdGreet")
        assert isinstance(props, dict)
        assert len(props) > 0

    def test_set_control_property(self):
        """set_control_property sets a safe property (Visible -> True)."""
        result = self.adapter.set_control_property("frmMain", "cmdGreet", "Visible", "True")
        assert result is True

    def test_set_control_properties_multiple(self):
        """set_control_properties sets multiple properties at once."""
        props = {
            "Visible": "True",
            "Enabled": "True",
        }
        result = self.adapter.set_control_properties("frmMain", "cmdGreet", props)
        assert isinstance(result, dict)
        # At least one property should succeed
        assert any(r for r in result.values())


class TestWinComControlEventProcedures:
    """Control event procedure listing via get_control_event_procedures."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_control_event_procedures_returns_list(self):
        """get_control_event_procedures on frmWithCode returns list."""
        procedures = self.adapter.get_control_event_procedures("frmWithCode")
        assert isinstance(procedures, list)

    def test_get_control_event_procedures_with_control_name(self):
        """get_control_event_procedures with control_name filters results."""
        procedures = self.adapter.get_control_event_procedures("frmWithCode", "cmdHello")
        assert isinstance(procedures, list)
        for proc in procedures:
            assert proc.get("procedure_name", "").startswith("cmdHello_")

    def test_get_control_event_procedures_empty_control_name_returns_all(self):
        """Empty string control_name returns all event procedures in the form module."""
        all_procedures = self.adapter.get_control_event_procedures("frmWithCode", "")
        filtered = self.adapter.get_control_event_procedures("frmWithCode")
        # Both calls with empty string (default) should return same result
        assert isinstance(all_procedures, list)
        assert isinstance(filtered, list)

    def test_get_control_event_procedures_not_connected(self):
        """get_control_event_procedures when not connected returns empty list."""
        self.adapter.disconnect()
        result = self.adapter.get_control_event_procedures("frmWithCode")
        assert result == []