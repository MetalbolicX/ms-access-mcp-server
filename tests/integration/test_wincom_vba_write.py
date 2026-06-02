r"""
Integration tests for WinComAdapter VBA write operations.

These tests require:
  - Windows OS with MS Access installed
  - pywin32 (win32com.client)
  - A test .accdb database with modUtilities module

Markers: com_integration
Execution: pytest tests/integration/test_wincom_vba_write.py -m com_integration -v

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


def _compile_retry(adapter: WinComAdapter, module_name: str, code: str, max_attempts: int = 3) -> dict:
    """Set VBA code with compile-retry loop.

    Writes code first, then attempts compile. If compile fails, retries up to
    max_attempts times. This handles the case where fresh modules need a moment
    before Access will compile them successfully.

    Returns dict with success=True/False and compile result.
    """
    if not adapter.is_connected():
        return {"success": False, "error": "Not connected"}

    for attempt in range(1, max_attempts + 1):
        # Write the code
        ok = adapter.set_vba_code(module_name, code)
        if not ok:
            return {"success": False, "error": "Failed to write code to module"}

        # Attempt compile
        compile_result = adapter.compile_vba()
        if compile_result.get("success"):
            return {"success": True, "compile": compile_result, "attempts": attempt}

        if attempt < max_attempts:
            import time
            time.sleep(0.3)

    return {"success": False, "compile": compile_result, "attempts": max_attempts}


# =============================================================================
# VBA Set Code
# =============================================================================

class TestWinComVbaSetCode:
    """Tests for WinComAdapter.set_vba_code()."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_set_vba_code_modifies_module(self, temp_db_copy: str):
        """Set code on modUtilities and verify the code is readable back."""
        assert self.adapter.connect(temp_db_copy), f"Failed to connect to {temp_db_copy}"

        new_code = (
            "Public Function TestSum(ByVal a As Long, ByVal b As Long) As Long\n"
            "    TestSum = a + b\n"
            "End Function\n"
        )

        ok = self.adapter.set_vba_code("modUtilities", new_code)
        assert ok, "set_vba_code returned False"

        # Read back and verify
        read_code = self.adapter.get_vba_code("modUtilities")
        assert "TestSum" in read_code, f"Expected 'TestSum' in module code, got: {read_code[:200]}"
        assert "Public Function TestSum" in read_code

    def test_set_vba_code_with_compile_retry(self, temp_db_copy: str):
        """Set code with compile-retry flow — verify no compile errors remain."""
        assert self.adapter.connect(temp_db_copy)

        code = (
            "Public Function AddThree(ByVal a As Long, ByVal b As Long, ByVal c As Long) As Long\n"
            "    AddThree = a + b + c\n"
            "End Function\n"
        )

        result = _compile_retry(self.adapter, "modUtilities", code)
        assert result.get("success") is True, f"Compile failed: {result}"

        # Verify the function is present and presumably compiles
        read_back = self.adapter.get_vba_code("modUtilities")
        assert "AddThree" in read_back

    def test_set_vba_code_nonexistent_module(self, temp_db_copy: str):
        """Setting code on a non-existent module must return False."""
        assert self.adapter.connect(temp_db_copy)

        ok = self.adapter.set_vba_code("modDoesNotExist_xyz", "Public Sub Dummy()\nEnd Sub")
        assert ok is False, "set_vba_code should return False for non-existent module"


# =============================================================================
# VBA Add Procedure
# =============================================================================

class TestWinComVbaAddProcedure:
    """Tests for WinComAdapter.add_vba_procedure()."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_add_vba_procedure(self, temp_db_copy: str):
        """Add a function to modUtilities and verify it exists in the module."""
        assert self.adapter.connect(temp_db_copy)

        proc_code = (
            "Public Function MultiplyIt(ByVal x As Long, ByVal y As Long) As Long\n"
            "    MultiplyIt = x * y\n"
            "End Function\n"
        )

        ok = self.adapter.add_vba_procedure("modUtilities", "MultiplyIt", proc_code)
        assert ok, "add_vba_procedure returned False"

        # Verify via get_vba_code
        module_code = self.adapter.get_vba_code("modUtilities")
        assert "MultiplyIt" in module_code, f"Expected 'MultiplyIt' in module code, got: {module_code[:200]}"

    def test_add_vba_procedure_duplicate(self, temp_db_copy: str):
        """Adding a procedure with a name that already exists should not crash.

        The adapter may return False or overwrite — either is acceptable as long
        as the test process remains stable.
        """
        assert self.adapter.connect(temp_db_copy)

        proc_code = (
            "Public Sub DoSomething()\n"
            "    Debug.Print \"first\"\n"
            "End Sub\n"
        )

        # Add once
        ok1 = self.adapter.add_vba_procedure("modUtilities", "DoSomething", proc_code)
        assert ok1, "First add_vba_procedure should succeed"

        # Add again — should not crash; may return False or may succeed
        ok2 = self.adapter.add_vba_procedure("modUtilities", "DoSomething", proc_code)
        # Accept either True (overwritten) or False (rejected) — both are valid
        assert isinstance(ok2, bool)


# =============================================================================
# VBA Delete Module
# =============================================================================

class TestWinComVbaDeleteModule:
    """Tests for WinComAdapter.delete_module()."""

    def setup_method(self):
        self.adapter: WinComAdapter = WinComAdapter()

    def teardown_method(self):
        _cleanup_adapter(self.adapter)

    def test_delete_module(self, temp_db_copy: str):
        """Delete a module and verify it is gone from get_modules()."""
        assert self.adapter.connect(temp_db_copy)

        # Create a unique module to delete
        module_name = _unique_name("modToDelete")
        create_ok = self.adapter.add_vba_procedure(module_name, "TempFunc", "Public Function TempFunc() As Long\n    TempFunc = 1\nEnd Function")
        assert create_ok, "Precondition: could not create test module"

        # Verify it exists
        modules_before = [m.name for m in self.adapter.get_modules()]
        assert module_name in modules_before, f"Precondition: {module_name} should exist in {modules_before}"

        # Delete
        ok = self.adapter.delete_module(module_name)
        assert ok, "delete_module returned False"

        # Verify it's gone
        modules_after = [m.name for m in self.adapter.get_modules()]
        assert module_name not in modules_after, f"{module_name} should not be in {modules_after}"

    def test_delete_module_nonexistent(self, temp_db_copy: str):
        """Deleting a non-existent module must return False without crashing."""
        assert self.adapter.connect(temp_db_copy)

        ok = self.adapter.delete_module("modIDontExist_xyz")
        assert ok is False, "delete_module should return False for non-existent module"
