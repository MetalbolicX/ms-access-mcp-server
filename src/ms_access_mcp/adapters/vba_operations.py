"""VBA operations for COM automation — extracted from WinComAdapter.

Handles VBA project introspection, module CRUD, compilation,
and procedure-level operations.
"""

import locale
import os
import sys
import tempfile
import threading
import time
from typing import Any, Callable

from ..config import ServerConfig
from ..adapters.com_dispatcher import ComDispatcher
from ..adapters.trusted_locations import capture_trusted_locations, restore_trusted_locations
from ..models.database import ModuleInfo
from ..logging import get_logger

_logger = get_logger(__name__)


# Compile command IDs by Access version (most likely first)
_COMPILE_CMD_IDS = [301, 206, 317, 232]


class VbaOperations:
    """VBA operations requiring COM automation.

    Args:
        dispatcher: ComDispatcher instance for STA-threaded COM calls.
    """

    def __init__(self, dispatcher: ComDispatcher, load_text: Callable | None = None) -> None:
        self._dispatcher = dispatcher
        self._load_text = load_text  # set later by WinComAdapter

    def set_load_text(self, load_text: Callable[[int, str, str], bool]) -> None:
        """Set the load_text callable (from UiOperations._load_object_from_text).

        Used by WinComAdapter to wire VbaOperations → UiOperations for
        the acModule=5 LoadFromText path.
        """
        self._load_text = load_text

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_vb_project(self):
        """Get the first VBA project via VBProjects enumeration.

        COM VBProjects collection uses 1-based indexing.
        More reliable than ActiveVBProject in COM automation, which depends
        on which project is active/focused and may return None.
        """
        try:
            vbe = self._dispatcher.access_app.VBE
            # VBProjects is 1-based COM collection
            for i in range(1, vbe.VBProjects.Count + 1):
                return vbe.VBProjects(i)
        except Exception:
            pass
        return None

    @staticmethod
    def _dialog_killer(stop_event: threading.Event) -> None:
        """Background thread that clicks the accept button on Access 'Save As' dialogs.

        The 'Save As' dialog appears when Access VBA compilation encounters an
        unnamed module.  It blocks the COM/STA thread, so we run this from a
        separate daemon thread to dismiss it by clicking the accept button.

        Args:
            stop_event: threading.Event — set when the dialog killer should stop.
        """
        try:
            import win32con
            import win32gui

            while not stop_event.is_set():
                def find_and_click(hwnd: int, _: object) -> bool:
                    if stop_event.is_set():
                        return False
                    cls = win32gui.GetClassName(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    if cls != "#32770" or "save" not in title.lower():
                        return True
                    # Found the dialog — find the accept button (OK, Save, etc.)
                    btn = win32gui.FindWindowEx(hwnd, None, "Button", None)
                    while btn:
                        btn_title = win32gui.GetWindowText(btn).strip()
                        if btn_title in ("OK", "Save", "&OK", "&Save"):
                            win32gui.PostMessage(hwnd, win32con.WM_COMMAND,
                                                 win32gui.GetWindowLong(btn, win32con.GWL_ID), 0)
                            return True
                        btn = win32gui.FindWindowEx(hwnd, btn, "Button", None)
                    # Fallback: press Enter on the dialog itself
                    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, 0x0D, 0)
                    return True

                win32gui.EnumWindows(find_and_click, None)
                if not stop_event.is_set():
                    time.sleep(0.1)

        except ImportError:
            pass  # Not on Windows
        except Exception:
            pass  # Best-effort

    # Module-level cache for preserve_trusted_locations (read once, cache for process lifetime)
try:
    _PRESERVE_TRUSTED_LOCATIONS = ServerConfig().preserve_trusted_locations
except Exception:
    _PRESERVE_TRUSTED_LOCATIONS = False

    # ------------------------------------------------------------------ #
    # Trusted Locations wrapper
    # ------------------------------------------------------------------ #

    def _trusted_locations_wrap(self, func, *args, **kwargs):
        """Execute func(*args, **kwargs) with Trusted Locations preservation if enabled.

        Captures Trusted Locations before the call and restores them after,
        controlled by config.preserve_trusted_locations (cached at module level).
        """
        if not _PRESERVE_TRUSTED_LOCATIONS:
            return func(*args, **kwargs)

        captured = capture_trusted_locations()
        try:
            return func(*args, **kwargs)
        finally:
            if captured:
                restore_trusted_locations(captured)

    # ------------------------------------------------------------------ #
    # _load_object_from_text for acModule=5
    # Inlined here; full version with all object types lives in UiOperations (PR 3).
    # ------------------------------------------------------------------ #

    def _load_object_from_text_module(self, module_name: str, text_data: str) -> bool:
        """Import a VBA module from text data using LoadFromText.

        Uses system ANSI codepage (cp1252) as Access expects for .bas files,
        with no BOM. This is the acModule=5 path only.

        If a _load_text callable was injected by WinComAdapter (from UiOperations),
        use it; otherwise fall back to inline logic.
        """
        if self._load_text:
            return self._load_text(5, module_name, text_data)

        # Fallback: inline acModule=5 logic
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_imp_")
            os.close(fd)
            enc = locale.getpreferredencoding(False) or "cp1252"
            with open(temp_path, "w", encoding=enc, errors="replace") as f:
                f.write(text_data)
            self._dispatcher.access_app.LoadFromText(5, module_name, temp_path)
            return True
        except Exception:
            return False
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # Public VBA API
    # ------------------------------------------------------------------ #

    def get_vba_project_name(self) -> str:
        """Get the VBA project name from COM."""
        if not self._dispatcher._started:
            return ""
        def _do() -> str:
            vb_project = self._get_vb_project()
            return vb_project.Name if vb_project else ""
        try:
            return self._dispatcher.call(_do)
        except Exception:
            return ""

    def get_modules(self) -> list[ModuleInfo]:
        """Get all VBA modules in the database."""
        if not self._dispatcher._started:
            return []

        def _do() -> list[ModuleInfo]:
            modules: list[ModuleInfo] = []
            vb_project = self._get_vb_project()
            if vb_project is None:
                return []
            try:
                for comp in vb_project.VBComponents:
                    try:
                        code = ""
                        if comp.Type == 1:
                            code = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
                        modules.append(ModuleInfo(
                            name=comp.Name,
                            type="Standard Module" if comp.Type == 1 else "Class Module",
                            code=code,
                        ))
                    except Exception:
                        pass
            except Exception:
                pass
            return modules

        return self._dispatcher.call(_do)

    def get_vba_code(self, module_name: str) -> str:
        """Get VBA code from a module."""
        if not self._dispatcher._started:
            return ""

        def _do() -> str:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return ""
            try:
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        lines = comp.CodeModule.CountOfLines
                        if lines > 0:
                            return comp.CodeModule.Lines(1, lines)
                        return ""
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    def set_vba_code(self, module_name: str, code: str) -> bool:
        """Set VBA code in a module.

        For non-existent modules: uses LoadFromText which auto-creates,
        names, and saves the module without triggering 'Save As' dialogs.
        For existing modules: uses DeleteLines + AddFromString (safe
        in-memory update on already-named components).
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
                # Check if module already exists
                target_module = None
                for mod in vb_project.VBComponents:
                    if mod.Name == module_name:
                        target_module = mod
                        break

                if target_module is None:
                    # New module: use LoadFromText (bypasses Access UI layer)
                    text_data = f"Attribute VB_Name = \"{module_name}\"\r\n{code}"
                    return self._load_object_from_text_module(module_name, text_data)
                else:
                    # Existing module: clear and repopulate in-memory
                    try:
                        target_module.CodeModule.DeleteLines(
                            1, target_module.CodeModule.CountOfLines
                        )
                        target_module.CodeModule.AddFromString(code)
                        return True
                    except Exception:
                        return False
            except Exception as set_vba_exc:
                import traceback
                traceback.print_exc()
                _logger.exception(f"[set_vba_code] Exception: {set_vba_exc}")
                return False

        return self._dispatcher.call(self._trusted_locations_wrap, _do)

    def add_vba_procedure(self, module_name: str, procedure_name: str, code: str) -> bool:
        """Add a VBA procedure to a module.

        For non-existent modules: uses LoadFromText to create and name
        the module. For existing modules: safely appends via AddFromString
        on the already-named component.
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
                target_module = None
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        target_module = comp
                        break
                if target_module is None:
                    # New module: use LoadFromText (bypasses Access UI layer)
                    text_data = f"Attribute VB_Name = \"{module_name}\"\r\n{code}"
                    return self._load_object_from_text_module(module_name, text_data)
                else:
                    # Existing module: append via AddFromString (safe on named)
                    target_module.CodeModule.AddFromString(code)
                    return True
            except Exception:
                return False

        return self._dispatcher.call(self._trusted_locations_wrap, _do)

    def delete_module(self, module_name: str) -> bool:
        """Delete a VBA module from the database.

        Args:
            module_name: Name of the module to delete

        Returns:
            True if deleted, False if not found or error
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        vb_project.VBComponents.Remove(comp)
                        return True
                return False
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def save_database(self) -> dict:
        """Save all VBA modules and database changes.

        Uses DoCmd.Save to persist each standard module.
        Returns structured result with success/error.

        Returns:
            dict with success=True on success, error message on failure
        """
        if not self._dispatcher._started:
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return {"success": False, "error": "No VBA project"}
            app = self._dispatcher.access_app
            saved = 0
            errors = []
            try:
                for comp in vb_project.VBComponents:
                    if comp.Type == 1:  # vbext_ct_StdModule
                        try:
                            app.DoCmd.Save(5, comp.Name)  # 5 = acModule
                            saved += 1
                        except Exception as e:
                            errors.append(f"{comp.Name}: {e}")
            except Exception as e:
                return {"success": False, "error": str(e)}
            return {
                "success": True,
                "saved_modules": saved,
                "errors": errors,
            }

        return self._dispatcher.call(_do)

    def compile_vba(self) -> dict:
        """Compile VBA code.

        Tries known DoCmd.RunCommand constants for VBA compilation.
        The correct command ID varies by Access version:
        - 301: Access 16.0 (Office 365 / 2021) — confirmed working
        - 206: acCmdCompileAllModules (older versions)
        - 317: acCmdCompileAndSaveAllModules (older versions)
        - 232: 0xE8 — commonly documented online

        Returns:
            dict with success=True on success
            dict with success=False and error message on failure
        """
        if not self._dispatcher._started:
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return {"success": False, "error": "No VBA project"}
            app = self._dispatcher.access_app

            # Save all modules first so compilation doesn't trigger "Save As" dialog
            for comp in vb_project.VBComponents:
                if comp.Type == 1:  # vbext_ct_StdModule
                    try:
                        app.DoCmd.Save(5, comp.Name)
                    except Exception:
                        pass

            # Start dialog killer as safety net for any remaining dialogs
            dismissed = threading.Event()
            killer_thread = threading.Thread(
                target=self._dialog_killer,
                args=(dismissed,),
                daemon=True,
            )
            killer_thread.start()

            try:
                for cmd_id in _COMPILE_CMD_IDS:
                    try:
                        app.DoCmd.RunCommand(cmd_id)
                        return {"success": True}
                    except Exception:
                        continue
                return {
                    "success": False,
                    "error": "Could not find working compile command for this Access version",
                }
            finally:
                dismissed.set()
                killer_thread.join(timeout=2.0)

        try:
            return self._dispatcher.call(self._trusted_locations_wrap, _do)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vba_list_procedures(self, module_name: str) -> list[dict]:
        """List all procedures in a module with name, type, line info.

        Uses CodeModule.ProcOfLine to detect procedure boundaries.

        Returns:
            List of dicts with keys: name, type ("Sub"|"Function"|"Property"),
            start_line, line_count
        """
        if not self._dispatcher._started:
            return []

        def _do() -> list[dict]:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return []
            try:
                target_module = None
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        target_module = comp.CodeModule
                        break
                if target_module is None:
                    return []

                total_lines = target_module.CountOfLines
                if total_lines == 0:
                    return []

                procedures: list[dict] = []
                seen_procs: set[str] = set()

                for line in range(1, total_lines + 1):
                    try:
                        proc_name = target_module.ProcOfLine(line, 0)
                        if proc_name and proc_name not in seen_procs:
                            seen_procs.add(proc_name)
                            proc_kind = target_module.ProcKind(line, 0)
                            proc_type = {0: "Sub", 1: "Function", 2: "Property"}.get(proc_kind, "Sub")
                            start_line = target_module.ProcStartLine(proc_name, 0)
                            line_count = target_module.ProcCountLines(proc_name, 0)
                            procedures.append({
                                "name": proc_name,
                                "type": proc_type,
                                "start_line": start_line,
                                "line_count": line_count,
                            })
                    except Exception:
                        pass
                return procedures
            except Exception:
                return []

        return self._dispatcher.call(_do)

    def vba_get_procedure(self, module_name: str, procedure_name: str) -> dict:
        """Get full source code of a specific procedure.

        Returns:
            dict with keys: name, type, code, signature
        """
        if not self._dispatcher._started:
            return {}

        def _do() -> dict:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return {}
            try:
                target_module = None
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        target_module = comp.CodeModule
                        break
                if target_module is None:
                    return {}

                start_line = target_module.ProcStartLine(procedure_name, 0)
                line_count = target_module.ProcCountLines(procedure_name, 0)
                code = target_module.Lines(start_line, line_count)

                # Extract signature (first line of the procedure)
                lines = code.split("\n")
                signature = lines[0] if lines else ""

                proc_kind = target_module.ProcKind(start_line, 0)
                proc_type = {0: "Sub", 1: "Function", 2: "Property"}.get(proc_kind, "Sub")

                return {
                    "name": procedure_name,
                    "type": proc_type,
                    "code": code,
                    "signature": signature,
                }
            except Exception:
                return {}

        return self._dispatcher.call(_do)

    def vba_replace_procedure(self, module_name: str, procedure_name: str, new_code: str) -> bool:
        """Replace a procedure's body with new code (preserves signature).

        Deletes the old procedure lines and inserts new code at the same position.

        Returns:
            True on success, False on failure
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return False
            try:
                target_module = None
                for comp in vb_project.VBComponents:
                    if comp.Name == module_name:
                        target_module = comp.CodeModule
                        break
                if target_module is None:
                    return False

                start_line = target_module.ProcStartLine(procedure_name, 0)
                line_count = target_module.ProcCountLines(procedure_name, 0)

                # Delete old procedure lines
                target_module.DeleteLines(start_line, line_count)
                # Insert new code at the same position
                target_module.InsertLines(start_line, new_code)
                return True
            except Exception:
                return False

        return self._dispatcher.call(self._trusted_locations_wrap, _do)