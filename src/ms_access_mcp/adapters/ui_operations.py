"""UI operations for COM automation — forms, reports, macros, controls, text export/import.

Extracted from WinComAdapter to respect SRP.
"""

import locale
import os
import tempfile
from typing import Any

from ..adapters.com_dispatcher import ComDispatcher
from ..models.database import (
    FormInfo,
    ReportInfo,
    MacroInfo,
    ControlInfo,
)


class UiOperations:
    """Form, report, macro, and control operations via COM automation.

    Args:
        dispatcher: ComDispatcher instance for STA-threaded COM calls.
        vba: VbaOperations instance for VBA procedure manipulation.
    """

    def __init__(self, dispatcher: ComDispatcher, vba: "VbaOperations | None" = None) -> None:
        self._dispatcher = dispatcher
        self._vba = vba  # set later by WinComAdapter if not provided

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _access_control_type_name(ctrl_type: int) -> str:
        """Map Access AcControlType integer to readable name."""
        type_map = {
            100: "TextBox",
            101: "Label",
            102: "CommandButton",
            103: "OptionButton",
            104: "ComboBox",
            105: "ListBox",
            106: "SubForm",
            107: "ToggleButton",
            108: "CheckBox",
            109: "OptionGroup",
            110: "TabControl",
            111: "Page",
            112: "Image",
            114: "BoundObjectFrame",
            115: "ObjectFrame",
            118: "Line",
            119: "Rectangle",
            120: "PageBreak",
            122: "Attachment",
            123: "NavigationButton",
            124: "NavigationControl",
            126: "WebBrowserControl",
            128: "EmptyCell",
        }
        return type_map.get(ctrl_type, f"Control({ctrl_type})")

    @staticmethod
    def _access_control_type_id(name: str) -> int:
        """Map readable control type name to Access AcControlType integer."""
        type_map = {
            "TextBox": 100,
            "Label": 101,
            "CommandButton": 102,
            "OptionButton": 103,
            "ComboBox": 104,
            "ListBox": 105,
            "SubForm": 106,
            "ToggleButton": 107,
            "CheckBox": 108,
            "OptionGroup": 109,
            "TabControl": 110,
            "Page": 111,
            "Image": 112,
            "BoundObjectFrame": 114,
            "ObjectFrame": 115,
            "Line": 118,
            "Rectangle": 119,
            "PageBreak": 120,
            "Attachment": 122,
            "NavigationButton": 123,
            "NavigationControl": 124,
            "WebBrowserControl": 126,
            "EmptyCell": 128,
        }
        return type_map.get(name, 0)

    @staticmethod
    def _ac_section_name(section_id: int) -> str:
        """Map Access AcSection integer to readable name."""
        section_map = {
            0: "detail",
            1: "header",
            2: "footer",
            3: "page_header",
            4: "page_footer",
        }
        return section_map.get(section_id, f"Section({section_id})")

    @staticmethod
    def _ac_section_id(name: str) -> int:
        """Map readable section name to Access AcSection integer."""
        section_map = {
            "detail": 0,
            "header": 1,
            "footer": 2,
            "page_header": 3,
            "page_footer": 4,
        }
        return section_map.get(name.lower(), 0)

    def _save_object_to_text(self, object_type: int, object_name: str) -> str:
        """Export an Access object to text using SaveAsText.

        Returns the text content or empty string on failure.
        object_type: acForm=2, acReport=4, acModule=5, acMacro=8
        """
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_exp_")
            os.close(fd)
            self._dispatcher.access_app.SaveAsText(object_type, object_name, temp_path)
            with open(temp_path, "rb") as f:
                raw = f.read()
            # SaveAsText outputs UTF-16-LE with BOM; decode accordingly
            content = raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
            return content
        except Exception:
            return ""
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def _load_object_from_text(self, object_type: int, object_name: str, text_data: str) -> bool:
        """Import an Access object from text data using LoadFromText.

        object_type: acForm=2, acReport=4, acModule=5, acMacro=8

        Encoding: VBA modules (acModule=5) expect the system ANSI codepage
        without BOM. Forms, reports, queries, and macros expect UTF-16-LE
        with BOM. Using the wrong encoding causes Access to store
        garbage (BOM chars as literal code) and corrupts the module.
        """
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_imp_")
            os.close(fd)
            # VBA modules (.bas) use system ANSI codepage — no BOM.
            # Everything else (forms, reports, macros, queries) uses
            # UTF-16-LE with BOM.
            if object_type == 5:  # acModule
                enc = locale.getpreferredencoding(False) or "cp1252"
                with open(temp_path, "w", encoding=enc, errors="replace") as f:
                    f.write(text_data)
            else:
                with open(temp_path, "wb") as f:
                    f.write(b"\xff\xfe")
                    f.write(text_data.encode("utf-16-le"))
            self._dispatcher.access_app.LoadFromText(object_type, object_name, temp_path)
            return True
        except Exception:
            return False
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def _get_vb_project(self):
        """Get the first VBA project via VBProjects enumeration.

        COM VBProjects collection uses 1-based indexing.
        More reliable than ActiveVBProject in COM automation.
        """
        try:
            vbe = self._dispatcher.access_app.VBE
            for i in range(1, vbe.VBProjects.Count + 1):
                return vbe.VBProjects(i)
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------ #
    # Form operations
    # ------------------------------------------------------------------ #

    def get_forms(self) -> list[FormInfo]:
        """Get all forms in the database."""
        if not self._dispatcher._started:
            return []

        def _do() -> list[FormInfo]:
            forms: list[FormInfo] = []
            try:
                all_forms = self._dispatcher.access_app.CurrentProject.AllForms
                for i in range(all_forms.Count):
                    form_obj = all_forms(i)
                    try:
                        record_source = ""
                        try:
                            record_source = str(form_obj.Properties("RecordSource")) if form_obj.Properties.Exists("RecordSource") else ""
                        except Exception:
                            pass
                        forms.append(FormInfo(name=form_obj.Name, record_source=record_source))
                    except Exception:
                        pass
            except Exception:
                pass
            return forms

        return self._dispatcher.call(_do)

    def form_exists(self, form_name: str) -> bool:
        """Check if a form exists."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                all_forms = self._dispatcher.access_app.CurrentProject.AllForms
                for i in range(all_forms.Count):
                    if all_forms(i).Name == form_name:
                        return True
            except Exception:
                pass
            return False

        return self._dispatcher.call(_do)

    def get_form_controls(self, form_name: str) -> list[ControlInfo]:
        """Get all controls in a form by opening it in design view."""
        if not self._dispatcher._started:
            return []

        def _do() -> list[ControlInfo]:
            controls: list[ControlInfo] = []
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            ctrl_name = ctrl.Name
                            ctrl_type_code = ctrl.ControlType
                            ctrl_type = self._access_control_type_name(ctrl_type_code)

                            props: dict[str, str] = {}
                            for prop_name in ("Visible", "Enabled", "Left", "Top",
                                              "Width", "Height", "Caption",
                                              "ControlSource", "TabIndex"):
                                try:
                                    val = ctrl.Properties(prop_name).Value
                                    if val is not None:
                                        props[prop_name] = str(val)
                                except Exception:
                                    pass

                            controls.append(ControlInfo(
                                name=ctrl_name, type=ctrl_type, properties=props,
                            ))
                        except Exception:
                            pass
            except Exception:
                pass
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)
                    except Exception:
                        pass
            return controls

        return self._dispatcher.call(_do)

    def open_form(self, form_name: str) -> bool:
        """Open a form in Access (appears on the server desktop)."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def close_form(self, form_name: str) -> bool:
        """Close an open form without saving."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acForm=2, acSaveNo=2
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def delete_form(self, form_name: str) -> bool:
        """Delete a form from the database."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                self._dispatcher.access_app.DoCmd.DeleteObject(2, form_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def export_form_to_text(self, form_name: str) -> str:
        """Export a form to text representation via SaveAsText."""
        if not self._dispatcher._started:
            return ""

        def _do() -> str:
            return self._save_object_to_text(2, form_name)

        return self._dispatcher.call(_do)

    def import_form_from_text(self, form_name: str, form_data: str) -> bool:
        """Import a form from text data via LoadFromText."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            return self._load_object_from_text(2, form_name, form_data)

        return self._dispatcher.call(_do)

    def create_form(self, form_name: str, record_source: str = "", template_name: str = "", properties: dict[str, Any] | None = None) -> bool:
        """Create a new form via DoCmd.CreateForm, optionally setting RecordSource and properties."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                form_obj = self._dispatcher.access_app.DoCmd.CreateForm()
                if record_source:
                    try:
                        form_obj.RecordSource = record_source
                    except Exception:
                        pass
                if properties:
                    for prop_name, value in properties.items():
                        try:
                            form_obj.Properties(prop_name).Value = value
                        except Exception:
                            pass
                # Close with acSaveYes (1) to persist the form
                self._dispatcher.access_app.DoCmd.Close(2, form_obj.Name, 1)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def rename_form(self, old_name: str, new_name: str) -> bool:
        """Rename a form via DoCmd.Rename with acForm=2."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                self._dispatcher.access_app.DoCmd.Rename(new_name, 2, old_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def get_form_properties(self, form_name: str) -> dict:
        """Get all properties of a form by opening it in design view."""
        if not self._dispatcher._started:
            return {}

        def _do() -> dict:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    props: dict[str, str] = {}
                    for prop in form.Properties:
                        try:
                            props[prop.Name] = str(prop.Value)
                        except Exception:
                            pass
                    return props
                return {}
            except Exception:
                return {}
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acSaveNo=2
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_form_property(self, form_name: str, property_name: str, value: str) -> bool:
        """Set a single property of a form by opening it in design view."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    form.Properties(property_name).Value = value
                    return True
                return False
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_form_properties(self, form_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties of a form. Returns dict of {property_name: success}."""
        if not self._dispatcher._started:
            return {}

        def _do() -> dict[str, bool]:
            results: dict[str, bool] = {}
            for prop_name, value in properties.items():
                opened = False
                try:
                    self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                    opened = True

                    try:
                        form = self._dispatcher.access_app.Screen.ActiveForm
                    except Exception:
                        form = self._dispatcher.access_app.Forms(form_name)

                    success = False
                    if form is not None:
                        try:
                            form.Properties(prop_name).Value = value
                            success = True
                        except Exception:
                            pass
                except Exception:
                    success = False
                finally:
                    if opened:
                        try:
                            self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                        except Exception:
                            pass
                results[prop_name] = success
            return results

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Control operations
    # ------------------------------------------------------------------ #

    def get_control_properties(self, form_name: str, control_name: str) -> dict:
        """Get all properties of a specific control by opening the form in design view."""
        if not self._dispatcher._started:
            return {}

        def _do() -> dict:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            if ctrl.Name == control_name:
                                props: dict[str, str] = {}
                                for prop in ctrl.Properties:
                                    try:
                                        props[prop.Name] = str(prop.Value)
                                    except Exception:
                                        pass
                                return props
                        except Exception:
                            pass
                return {}
            except Exception:
                return {}
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_control_property(self, form_name: str, control_name: str, property_name: str, value: str) -> bool:
        """Set a property of a control by opening the form in design view."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            if ctrl.Name == control_name:
                                ctrl.Properties(property_name).Value = value
                                return True
                        except Exception:
                            pass
                return False
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_control_properties(self, form_name: str, control_name: str, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties at once. Returns dict of {property_name: success}."""
        if not self._dispatcher._started:
            return {}

        def _do() -> dict[str, bool]:
            results: dict[str, bool] = {}
            for prop_name, value in properties.items():
                try:
                    opened = False
                    try:
                        self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)
                        opened = True

                        try:
                            form = self._dispatcher.access_app.Screen.ActiveForm
                        except Exception:
                            form = self._dispatcher.access_app.Forms(form_name)

                        success = False
                        if form is not None:
                            for i in range(form.Controls.Count):
                                try:
                                    ctrl = form.Controls(i)
                                    if ctrl.Name == control_name:
                                        ctrl.Properties(prop_name).Value = value
                                        success = True
                                        break
                                except Exception:
                                    pass
                    except Exception:
                        success = False
                    finally:
                        if opened:
                            try:
                                self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)
                            except Exception:
                                pass
                    results[prop_name] = success
                except Exception:
                    results[prop_name] = False
            return results

        return self._dispatcher.call(_do)

    def add_control(self, form_name: str, control_type: str, control_name: str, section: int = 0, properties: dict[str, Any] | None = None) -> bool:
        """Add a control to a form by opening it in design view, creating the control, and setting its name and properties."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                type_int = self._access_control_type_id(control_type)
                if type_int == 0:
                    return False

                ctrl = self._dispatcher.access_app.DoCmd.CreateControl(form_name, type_int, section)
                ctrl.Name = control_name

                if properties:
                    for prop_name, value in properties.items():
                        try:
                            ctrl.Properties(prop_name).Value = value
                        except Exception:
                            pass

                self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                return True
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acSaveNo=2
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def remove_control(self, form_name: str, control_name: str) -> bool:
        """Remove a control from a form by opening it in design view, selecting the control, and running the delete command."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    for i in range(form.Controls.Count):
                        try:
                            ctrl = form.Controls(i)
                            if ctrl.Name == control_name:
                                ctrl.SetFocus()
                                self._dispatcher.access_app.DoCmd.RunCommand(365)  # acCmdDelete
                                self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                                return True
                        except Exception:
                            pass

                self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acSaveNo=2
                return False
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def get_control_event_procedures(self, form_name: str, control_name: str) -> list[dict]:
        """List event procedures for a specific control in a form.

        Access stores event procedures with ControlName_EventName convention
        in the form's code module (e.g., cmdSave_Click, txtName_AfterUpdate).

        If control_name is empty, returns ALL event procedures in the form module.
        If control_name is specified, filters to procedures with that prefix.

        Returns list of {procedure_name, event_name, code, start_line}.
        """
        if not self._dispatcher._started:
            return []

        def _do() -> list[dict]:
            vb_project = self._get_vb_project()
            if vb_project is None:
                return []
            try:
                form_module_name = f"Form_{form_name}"
                target_module = None
                for comp in vb_project.VBComponents:
                    if comp.Name == form_module_name:
                        target_module = comp.CodeModule
                        break
                if target_module is None:
                    return []

                total_lines = target_module.CountOfLines
                if total_lines == 0:
                    return []

                all_procedures: list[dict] = []
                seen_procs: set[str] = set()

                for line in range(1, total_lines + 1):
                    try:
                        proc_name = target_module.ProcOfLine(line, 0)
                        if proc_name and proc_name not in seen_procs:
                            seen_procs.add(proc_name)
                            start_line = target_module.ProcStartLine(proc_name, 0)
                            line_count = target_module.ProcCountLines(proc_name, 0)
                            code = target_module.Lines(start_line, line_count)
                            all_procedures.append({
                                "procedure_name": proc_name,
                                "start_line": start_line,
                                "line_count": line_count,
                                "code": code,
                            })
                    except Exception:
                        pass

                if control_name:
                    prefix = f"{control_name}_"
                    filtered = []
                    for proc in all_procedures:
                        if proc["procedure_name"].startswith(prefix):
                            event_name = proc["procedure_name"][len(prefix):]
                            filtered.append({
                                "procedure_name": proc["procedure_name"],
                                "event_name": event_name,
                                "code": proc["code"],
                                "start_line": proc["start_line"],
                            })
                    return filtered
                else:
                    result = []
                    for proc in all_procedures:
                        proc_name = proc["procedure_name"]
                        if "_" in proc_name:
                            parts = proc_name.split("_", 1)
                            result.append({
                                "procedure_name": proc_name,
                                "event_name": parts[1] if len(parts) > 1 else "",
                                "code": proc["code"],
                                "start_line": proc["start_line"],
                            })
                        else:
                            result.append({
                                "procedure_name": proc_name,
                                "event_name": "",
                                "code": proc["code"],
                                "start_line": proc["start_line"],
                            })
                    return result
            except Exception:
                return []

        return self._dispatcher.call(_do)

    def set_control_event_procedure(self, form_name: str, control_name: str, event_name: str, code: str) -> bool:
        """Set a control's event procedure by opening the form in design view, setting the event property to [Event Procedure], and replacing the VBA procedure.

        Args:
            form_name: Name of the form containing the control.
            control_name: Name of the control.
            event_name: Name of the event (e.g., "Click", "Enter", "AfterUpdate").
            code: VBA code for the event procedure body.

        Returns:
            True on success, False on failure.
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is None:
                    return False

                # Find the control by name
                target_ctrl = None
                for i in range(form.Controls.Count):
                    try:
                        ctrl = form.Controls(i)
                        if ctrl.Name == control_name:
                            target_ctrl = ctrl
                            break
                    except Exception:
                        pass

                if target_ctrl is None:
                    return False

                # Set the event property to "[Event Procedure]"
                event_prop_name = f"On{event_name}"
                target_ctrl.Properties(event_prop_name).Value = "[Event Procedure]"

                # Replace the VBA procedure in the form's module
                module_name = f"Form_{form_name}"
                proc_name = f"{control_name}_{event_name}"
                if self._vba is not None:
                    self._vba.vba_replace_procedure(module_name, proc_name, code)
                else:
                    return False

                return True
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Form section operations
    # ------------------------------------------------------------------ #

    def get_form_sections(self, form_name: str) -> list[dict]:
        """Get all sections of a form by opening it in design view."""
        if not self._dispatcher._started:
            return []

        def _do() -> list[dict]:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is None:
                    return []

                sections: list[dict] = []
                for i in range(5):  # 0=acDetail, 1=acHeader, 2=acFooter, 3=acPageHeader, 4=acPageFooter
                    try:
                        section = form.Section(i)
                        sections.append({
                            "index": i,
                            "name": str(section.Name),
                            "section_type": self._ac_section_name(i),
                            "visible": bool(section.Visible),
                            "height": int(section.Height),
                        })
                    except Exception:
                        pass  # Section doesn't exist on this form
                return sections
            except Exception:
                return []
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acSaveNo=2
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def get_form_section_properties(self, form_name: str, section_id: int) -> dict:
        """Get all properties of a specific section by opening the form in design view."""
        if not self._dispatcher._started:
            return {}

        def _do() -> dict:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    section = form.Section(section_id)
                    props: dict[str, str] = {}
                    for prop in section.Properties:
                        try:
                            props[prop.Name] = str(prop.Value)
                        except Exception:
                            pass
                    return props
                return {}
            except Exception:
                return {}
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acSaveNo=2
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_form_section_property(self, form_name: str, section_id: int, property_name: str, value: str) -> bool:
        """Set a single property of a form section by opening the form in design view."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            opened = False
            try:
                self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                opened = True

                try:
                    form = self._dispatcher.access_app.Screen.ActiveForm
                except Exception:
                    form = self._dispatcher.access_app.Forms(form_name)

                if form is not None:
                    section = form.Section(section_id)
                    section.Properties(property_name).Value = value
                    self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                    return True
                return False
            except Exception:
                return False
            finally:
                if opened:
                    try:
                        self._dispatcher.access_app.DoCmd.Close(2, form_name, 2)  # acSaveNo=2
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def set_form_section_properties(self, form_name: str, section_id: int, properties: dict[str, Any]) -> dict[str, bool]:
        """Set multiple properties of a form section. Returns dict of {property_name: success}."""
        if not self._dispatcher._started:
            return {}

        def _do() -> dict[str, bool]:
            results: dict[str, bool] = {}
            for prop_name, value in properties.items():
                opened = False
                try:
                    self._dispatcher.access_app.DoCmd.OpenForm(form_name, 1)  # acDesign=1
                    opened = True

                    try:
                        form = self._dispatcher.access_app.Screen.ActiveForm
                    except Exception:
                        form = self._dispatcher.access_app.Forms(form_name)

                    success = False
                    if form is not None:
                        try:
                            section = form.Section(section_id)
                            section.Properties(prop_name).Value = value
                            success = True
                        except Exception:
                            pass
                except Exception:
                    success = False
                finally:
                    if opened:
                        try:
                            self._dispatcher.access_app.DoCmd.Close(2, form_name, 1)  # acSaveYes=1
                        except Exception:
                            pass
                results[prop_name] = success
            return results

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Report operations
    # ------------------------------------------------------------------ #

    def get_reports(self) -> list[ReportInfo]:
        """Get all reports in the database."""
        if not self._dispatcher._started:
            return []

        def _do() -> list[ReportInfo]:
            reports: list[ReportInfo] = []
            try:
                all_reports = self._dispatcher.access_app.CurrentProject.AllReports
                for i in range(all_reports.Count):
                    report_obj = all_reports(i)
                    try:
                        record_source = ""
                        try:
                            record_source = str(report_obj.Properties("RecordSource")) if report_obj.Properties.Exists("RecordSource") else ""
                        except Exception:
                            pass
                        reports.append(ReportInfo(name=report_obj.Name, record_source=record_source))
                    except Exception:
                        pass
            except Exception:
                pass
            return reports

        return self._dispatcher.call(_do)

    def report_exists(self, report_name: str) -> bool:
        """Check if a report exists."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                all_reports = self._dispatcher.access_app.CurrentProject.AllReports
                for i in range(all_reports.Count):
                    if all_reports(i).Name == report_name:
                        return True
            except Exception:
                pass
            return False

        return self._dispatcher.call(_do)

    def delete_report(self, report_name: str) -> bool:
        """Delete a report from the database."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                self._dispatcher.access_app.DoCmd.DeleteObject(4, report_name)
                return True
            except Exception:
                return False

        return self._dispatcher.call(_do)

    def export_report_to_text(self, report_name: str) -> str:
        """Export a report to text representation via SaveAsText."""
        if not self._dispatcher._started:
            return ""

        def _do() -> str:
            return self._save_object_to_text(4, report_name)

        return self._dispatcher.call(_do)

    def import_report_from_text(self, report_name: str, report_data: str) -> bool:
        """Import a report from text data via LoadFromText."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            return self._load_object_from_text(4, report_name, report_data)

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Macro operations
    # ------------------------------------------------------------------ #

    def get_macros(self) -> list[MacroInfo]:
        """Get all macros in the database."""
        if not self._dispatcher._started:
            return []

        def _do() -> list[MacroInfo]:
            macros: list[MacroInfo] = []
            try:
                all_macros = self._dispatcher.access_app.CurrentProject.AllMacros
                for i in range(all_macros.Count):
                    macro_obj = all_macros(i)
                    try:
                        macros.append(MacroInfo(name=macro_obj.Name, type="Macro"))
                    except Exception:
                        pass
            except Exception:
                pass
            return macros

        return self._dispatcher.call(_do)