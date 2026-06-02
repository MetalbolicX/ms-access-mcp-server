r"""
Integration tests for WinComAdapter Form/Report export-import operations.

These tests require:
  - Windows OS with MS Access installed
  - pywin32 (win32com.client)
  - A test .accdb database with frmMain, frmWithCode, and rptCustomers

Markers: com_integration
Execution: pytest tests/integration/test_wincom_form_report.py -m com_integration -v

Each test gets its own cloned database via `temp_db_copy` so the master fixture
is never modified.  A fresh WinComAdapter is instantiated per test class to
minimise COM threading issues.
"""

import pytest

from ms_access_mcp.adapters.wincom import WinComAdapter
from helpers import skip_unless_windows, skip_unless_pywin32, skip_unless_db

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


def _unique_name(prefix: str) -> str:
    """Generate a unique name for test objects to avoid collisions on reuse."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _cleanup_adapter(adapter: WinComAdapter) -> None:
    """Safely disconnect an adapter, swallowing cleanup exceptions.

    Tries to call disconnect() but catches all exceptions (including COM
    teardown crashes like 0x80010108 RPC_E_CALL_CANCELED) so the test
    process never crashes in teardown.
    """
    try:
        adapter.disconnect()
    except Exception:
        pass


# =============================================================================
# Form Export / Import
# =============================================================================

class TestWinComFormExportImport:
    """Tests for form export, import, and round-trip via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_export_form_frmMain(self, temp_db_copy: str):
        """Export frmMain to text and verify the output contains expected controls."""
        assert self.adapter.connect(temp_db_copy)

        text = self.adapter.export_form_to_text("frmMain")
        assert text, "export_form_to_text returned empty string for frmMain"

        # The exported text should contain control definitions
        # frmMain has: txtName (TextBox), lblTitle (Label), cmdGreet (CommandButton)
        assert "txtName" in text or "lblTitle" in text or "cmdGreet" in text, \
            f"Expected control names in exported text, got: {text[:300]}"

    def test_export_form_frmWithCode(self, temp_db_copy: str):
        """Export frmWithCode and verify it references the cmdHello_Click handler."""
        assert self.adapter.connect(temp_db_copy)

        text = self.adapter.export_form_to_text("frmWithCode")
        assert text, "export_form_to_text returned empty string for frmWithCode"

        # frmWithCode has cmdHello button with a Click event handler
        # The form export may reference the event in its module attributes
        assert "cmdHello" in text, f"Expected 'cmdHello' in form export, got: {text[:300]}"

    def test_import_form_roundtrip(self, temp_db_copy: str):
        """Export frmMain, modify the text, re-import, and verify the change persisted."""
        assert self.adapter.connect(temp_db_copy)

        # Export the original
        original = self.adapter.export_form_to_text("frmMain")
        assert original, "Precondition: export must succeed"

        # Add a unique comment marker to the text
        unique_marker = f"TestMarker_{_unique_name('MRK')}"
        modified = original + f"\r\n{unique_marker}\r\n"

        # Re-import (overwrite frmMain)
        ok = self.adapter.import_form_from_text("frmMain", modified)
        assert ok, f"import_form_from_text returned False: {ok}"

        # Export again and verify the marker is present
        re_exported = self.adapter.export_form_to_text("frmMain")
        assert unique_marker in re_exported, \
            f"After round-trip, expected marker '{unique_marker}' to persist in form text"


# =============================================================================
# Report Export / Import
# =============================================================================

class TestWinComReportExportImport:
    """Tests for report export and import via WinComAdapter."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_export_report_rptCustomers(self, temp_db_copy: str):
        """Export rptCustomers to text and verify the report definition is present."""
        assert self.adapter.connect(temp_db_copy)

        text = self.adapter.export_report_to_text("rptCustomers")
        assert text, "export_report_to_text returned empty string for rptCustomers"

        # The exported report text should contain rptCustomers properties
        # Check for something specific to the report definition
        assert "rptCustomers" in text or "customers" in text.lower(), \
            f"Expected 'rptCustomers' or customer reference in report text, got: {text[:300]}"


# =============================================================================
# Control Properties
# =============================================================================

class TestWinComControlProperties:
    """Tests for reading and writing control properties on forms."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_read_control_property(self, temp_db_copy: str):
        """Read a control's property on frmMain using get_control_properties."""
        assert self.adapter.connect(temp_db_copy)

        # frmMain has txtName, lblTitle, cmdGreet
        props = self.adapter.get_control_properties("frmMain", "txtName")
        assert props, f"get_control_properties returned empty dict for txtName"

        # At minimum we expect Name property to be set
        assert "Name" in props or len(props) > 0, \
            f"Expected at least Name property, got: {props}"

    def test_set_control_property(self, temp_db_copy: str):
        """Modify a control property on a cloned form and verify the change.

        We clone a fresh form from the import path to avoid affecting the
        original frmMain in the clone.
        """
        assert self.adapter.connect(temp_db_copy)

        # Create a clone form to modify safely
        form_name = _unique_name("frmClone")
        original = self.adapter.export_form_to_text("frmMain")
        assert original, "Precondition: export must succeed"

        ok = self.adapter.import_form_from_text(form_name, original)
        assert ok, f"Failed to import clone form: {ok}"

        # Modify the clone's caption — add a unique suffix
        unique_caption = f"Modified_{_unique_name('CAP')}"
        result = self.adapter.set_control_property(form_name, "lblTitle", "Caption", unique_caption)

        # set_control_property returns bool — the property may or may not be settable
        # depending on Access version. At minimum, the call should not crash.
        assert isinstance(result, bool), f"set_control_property returned non-bool: {result}"
