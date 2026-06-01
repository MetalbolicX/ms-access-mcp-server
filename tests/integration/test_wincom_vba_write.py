"""COM integration tests for WinComAdapter VBA write operations.

Tests set_vba_code, add_vba_procedure, delete_module, vba_list_procedures,
vba_get_procedure, vba_replace_procedure, compile_vba, save_database on a
temporary copy of the fixture DB.
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


class TestWinComVbaSetCode:
    """set_vba_code via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_code_existing_module(self):
        """Set code on existing modUtilities module and verify persistence."""
        code = "Sub TestSetCode()\n    Debug.Print \"Hello from set_vba_code test\"\nEnd Sub"
        result = self.adapter.set_vba_code("modUtilities", code)
        assert result is True

        # Verify via get_vba_code
        retrieved = self.adapter.get_vba_code("modUtilities")
        assert "TestSetCode" in retrieved

    def test_set_code_nonexistent_module(self):
        """Set code on a module that does not exist returns False."""
        result = self.adapter.set_vba_code("NonExistentModule_VBA_Test", "Sub X()\nEnd Sub")
        assert result is False

    def test_set_code_not_connected(self):
        """set_vba_code when not connected returns False."""
        self.adapter.disconnect()
        result = self.adapter.set_vba_code("modUtilities", "Sub X()\nEnd Sub")
        assert result is False


class TestWinComVbaAddProcedure:
    """add_vba_procedure via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_sub_to_existing_module(self):
        """Add a Sub procedure to modUtilities."""
        code = "Sub AddedSub()\n    Debug.Print \"Added via add_vba_procedure\"\nEnd Sub"
        result = self.adapter.add_vba_procedure("modUtilities", "AddedSub", code)
        assert result is True

    def test_add_function_to_existing_module(self):
        """Add a Function procedure to modUtilities."""
        code = "Function AddedFunction() As Integer\n    AddedFunction = 42\nEnd Function"
        result = self.adapter.add_vba_procedure("modUtilities", "AddedFunction", code)
        assert result is True

    def test_add_to_new_module(self):
        """Add procedure to a module name that does not exist — adapter creates it."""
        new_module = "TestModule_VBA_Add"
        code = "Sub NewModuleSub()\n    Debug.Print \"In new module\"\nEnd Sub"
        result = self.adapter.add_vba_procedure(new_module, "NewModuleSub", code)
        assert result is True

        # Verify the module was created and has the procedure
        procedures = self.adapter.vba_list_procedures(new_module)
        proc_names = [p["name"] for p in procedures]
        assert "NewModuleSub" in proc_names

        # Clean up
        self.adapter.delete_module(new_module)


class TestWinComVbaDeleteModule:
    """delete_module via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_and_delete_module(self):
        """Create a temp module, verify it exists, then delete it."""
        module_name = "TempDeleteModule_VBA_Test"
        code = "Sub TempForDeletion()\nEnd Sub"

        # Create it via add_vba_procedure
        created = self.adapter.add_vba_procedure(module_name, "TempForDeletion", code)
        assert created is True

        # Verify it exists (list_procedures returns non-empty)
        procedures = self.adapter.vba_list_procedures(module_name)
        assert len(procedures) > 0

        # Delete it
        deleted = self.adapter.delete_module(module_name)
        assert deleted is True

        # Verify it's gone
        procedures_after = self.adapter.vba_list_procedures(module_name)
        assert len(procedures_after) == 0

    def test_delete_nonexistent_returns_false(self):
        """Deleting a module that does not exist returns False."""
        result = self.adapter.delete_module("NonExistentModule_VBA_Delete")
        assert result is False

    def test_delete_not_connected(self):
        """delete_module when not connected returns False."""
        self.adapter.disconnect()
        result = self.adapter.delete_module("modUtilities")
        assert result is False


class TestWinComVbaListGetReplace:
    """vba_list_procedures, vba_get_procedure, vba_replace_procedure via WinComAdapter."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_procedures_on_modUtilities(self):
        """List procedures on modUtilities — should return at least AddTwo."""
        procedures = self.adapter.vba_list_procedures("modUtilities")
        assert isinstance(procedures, list)
        proc_names = [p["name"] for p in procedures]
        # AddTwo is defined in the fixture
        assert "AddTwo" in proc_names

    def test_get_specific_procedure(self):
        """Get a specific procedure by name (e.g., AddTwo) from modUtilities."""
        result = self.adapter.vba_get_procedure("modUtilities", "AddTwo")
        assert isinstance(result, dict)
        assert result.get("name") == "AddTwo"
        assert "code" in result

    def test_get_nonexistent_procedure(self):
        """Getting a procedure that does not exist returns empty dict."""
        result = self.adapter.vba_get_procedure("modUtilities", "NonExistentProc_VBA_Test")
        assert result == {}

    def test_replace_procedure_body(self):
        """Replace a procedure body and verify the replacement via get_procedure."""
        new_code = (
            "Function AddTwo(a As Integer, b As Integer) As Integer\n"
            "    AddTwo = a + b + 1\n"
            "End Function"
        )
        replaced = self.adapter.vba_replace_procedure("modUtilities", "AddTwo", new_code)
        assert replaced is True

        # Verify via get_procedure
        result = self.adapter.vba_get_procedure("modUtilities", "AddTwo")
        assert "a + b + 1" in result.get("code", "")

    def test_replace_nonexistent_procedure(self):
        """Replacing a nonexistent procedure returns False."""
        result = self.adapter.vba_replace_procedure(
            "modUtilities", "NonExistentProc_VBA_Test", "Sub X()\nEnd Sub"
        )
        assert result is False


class TestWinComVbaCompileSave:
    """compile_vba and save_database via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_compile_vba_success(self):
        """Compile valid VBA returns success."""
        result = self.adapter.compile_vba()
        assert isinstance(result, dict)
        assert result.get("success") is True

    def test_save_database_success(self):
        """Save database returns success."""
        result = self.adapter.save_database()
        assert isinstance(result, dict)
        assert result.get("success") is True

    def test_compile_not_connected(self):
        """compile_vba when not connected returns error dict."""
        self.adapter.disconnect()
        result = self.adapter.compile_vba()
        assert result.get("success") is False
        assert "Not connected" in result.get("error", "")

    def test_save_not_connected(self):
        """save_database when not connected returns error dict."""
        self.adapter.disconnect()
        result = self.adapter.save_database()
        assert result.get("success") is False
        assert "Not connected" in result.get("error", "")