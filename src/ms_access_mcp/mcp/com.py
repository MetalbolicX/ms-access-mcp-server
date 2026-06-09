"""COM Automation and form/report discovery tools for MS Access — Phase 1 SDD."""
from .server import mcp
from .container import get_container
from ._helpers import guard_destructive


def _pool():
    return get_container().connection_pool


def _com():
    return get_container().com_automation


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return _pool().get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return _pool().is_connected(connection_name)


# ============================================================================
# COM AUTOMATION TOOLS
# ============================================================================


@mcp.tool()
def launch_access(visible: bool = False) -> dict:
    """
    Launch Microsoft Access application.

    Args:
        visible: Whether to show Access window (default False)
    """
    result = _com().launch_access(visible)
    return {"success": result, "access_running": _com().is_access_running()}


@mcp.tool()
def close_access() -> dict:
    """Close Microsoft Access application."""
    result = _com().close_access()
    return {"success": result, "access_running": _com().is_access_running()}


@mcp.tool()
def get_forms(connection_name: str = "default") -> dict:
    """
    Get all forms in the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    forms = adapter.get_forms()
    return {"success": True, "forms": [f.model_dump() for f in forms], "count": len(forms)}


@mcp.tool()
def get_reports(connection_name: str = "default") -> dict:
    """
    Get all reports in the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    reports = adapter.get_reports()
    return {"success": True, "reports": [r.model_dump() for r in reports], "count": len(reports)}


@mcp.tool()
def get_macros(connection_name: str = "default") -> dict:
    """
    Get all macros in the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    macros = adapter.get_macros()
    return {"success": True, "macros": [m.model_dump() for m in macros], "count": len(macros)}


@mcp.tool()
def get_modules(connection_name: str = "default") -> dict:
    """
    Get all VBA modules in the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    modules = adapter.get_modules()
    return {"success": True, "modules": [m.model_dump() for m in modules], "count": len(modules)}


@mcp.tool()
def open_form(form_name: str, connection_name: str = "default") -> dict:
    """
    Open a form in Access (appears on the server desktop).

    Args:
        form_name: Name of the form to open
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    result = _com().open_form(form_name)
    return {"success": result, "form": form_name, "message": "Form opened" if result else "Failed to open form"}


@mcp.tool()
def close_form(form_name: str, connection_name: str = "default") -> dict:
    """
    Close an open form.

    Args:
        form_name: Name of the form to close
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    result = _com().close_form(form_name)
    return {"success": result, "form": form_name, "message": "Form closed" if result else "Failed to close form"}


# ============================================================================
# FORM & CONTROL DISCOVERY TOOLS
# ============================================================================


@mcp.tool()
def form_exists(form_name: str, connection_name: str = "default") -> dict:
    """
    Check if a form exists.

    Args:
        form_name: Name of the form to check
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    exists = adapter.form_exists(form_name)
    return {"success": True, "exists": exists, "form": form_name}


@mcp.tool()
def get_form_controls(form_name: str, connection_name: str = "default") -> dict:
    """
    Get all controls in a form.

    Args:
        form_name: Name of the form
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    controls = adapter.get_form_controls(form_name)
    return {"success": True, "controls": [c.model_dump() for c in controls], "count": len(controls)}


@mcp.tool()
def get_control_properties(form_name: str, control_name: str, connection_name: str = "default") -> dict:
    """
    Get all properties of a specific control in a form.

    Opens the form in design view, reads the control's properties,
    then closes the form.

    Args:
        form_name: Name of the form
        control_name: Name of the control
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    props = _com().get_control_properties(form_name, control_name)
    if not props:
        return {"success": False, "error": f"Control '{control_name}' not found in form '{form_name}'"}
    return {"success": True, "form": form_name, "control": control_name, "properties": props}


@mcp.tool()
def set_control_property(form_name: str, control_name: str, property_name: str, value: str, connection_name: str = "default") -> dict:
    """
    Set a property of a control in a form.

    Opens the form in design view, sets the property, and saves.
    Some properties (ControlType, Name) are read-only and will fail.

    Args:
        form_name: Name of the form
        control_name: Name of the control
        property_name: Name of the property to set
        value: Value to set
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().set_control_property(form_name, control_name, property_name, value)
    return {"success": result, "form": form_name, "control": control_name, "property": property_name, "value": value}


@mcp.tool()
def set_control_properties(form_name: str, control_name: str, properties: dict[str, str], connection_name: str = "default") -> dict:
    """
    Set multiple properties of a control in a form at once.

    Opens the form in design view, sets each property, and saves.
    Some properties (ControlType, Name) are read-only and will fail.
    Continues setting remaining properties if some fail.

    Args:
        form_name: Name of the form
        control_name: Name of the control
        properties: Dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().set_control_properties(form_name, control_name, properties)
    if not result:
        return {"success": False, "error": f"Control '{control_name}' not found in form '{form_name}'"}
    return {"success": True, "form": form_name, "control": control_name, "properties": result}


@mcp.tool()
def get_control_event_procedures(form_name: str, control_name: str = "", connection_name: str = "default") -> dict:
    """
    Get event procedures for a form or specific control.

    Access stores event procedures in form code modules using the naming
    convention ControlName_EventName (e.g., cmdSave_Click, txtName_AfterUpdate).

    If control_name is empty, returns ALL event procedures in the form's module.
    If control_name is specified, returns only procedures for that control.

    Args:
        form_name: Name of the form
        control_name: Name of the control (optional, leave empty for all)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    procedures = _com().get_control_event_procedures(form_name, control_name)
    return {
        "success": True,
        "form": form_name,
        "control": control_name if control_name else "(all)",
        "event_procedures": procedures,
        "count": len(procedures),
    }


@mcp.tool()
def set_control_event_procedure(
    form_name: str,
    control_name: str,
    event_name: str,
    code: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Set a control's event procedure in a form.

    Opens the form in design view, sets the control's event property to
    "[Event Procedure]", and replaces the VBA procedure with the provided code.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form containing the control.
        control_name: Name of the control.
        event_name: Name of the event (e.g., "Click", "Enter", "AfterUpdate").
        code: VBA code for the event procedure body.
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "set_control_event_procedure", form_name=form_name, control_name=control_name, event_name=event_name)
    if guard is not None:
        return guard
    result = _com().set_control_event_procedure(form_name, control_name, event_name, code)
    return {"success": result, "form_name": form_name, "control_name": control_name, "event_name": event_name}


# ============================================================================
# FORM MANIPULATION TOOLS
# ============================================================================


@mcp.tool()
def create_form(form_name: str, record_source: str = "", template_name: str = "", properties: dict[str, str] | None = None, connection_name: str = "default") -> dict:
    """
    Create a new blank form, optionally with a RecordSource.

    Args:
        form_name: Name for the new form
        record_source: SQL table/query to bind as RecordSource (optional)
        template_name: Template to base the form on (optional, unused in MVP)
        properties: Additional properties to set after creation (optional)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.create_form(form_name, record_source, template_name, properties)
    return {"success": result, "form_name": form_name}


@mcp.tool()
def rename_form(old_name: str, new_name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Rename an existing form.

    This is a destructive action. Set confirm=True to execute, or dry_run=True
    to preview without making changes.

    Args:
        old_name: Current name of the form
        new_name: New name for the form
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the rename
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "rename_form", old_name=old_name, new_name=new_name)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.rename_form(old_name, new_name)
    return {"success": result, "old_name": old_name, "new_name": new_name}


@mcp.tool()
def get_form_properties(form_name: str, connection_name: str = "default") -> dict:
    """
    Get all properties of a form.

    Opens the form in design view, reads Form.Properties, then closes.

    Args:
        form_name: Name of the form
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    props = _com().get_form_properties(form_name)
    if not props:
        return {"success": False, "error": f"No properties found for form '{form_name}'", "form": form_name}
    return {"success": True, "form": form_name, "properties": props}


@mcp.tool()
def set_form_property(form_name: str, property_name: str, value: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set a single property of a form.

    Opens the form in design view, sets the property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form
        property_name: Name of the property to set
        value: Value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "set_form_property", form_name=form_name, property_name=property_name)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().set_form_property(form_name, property_name, value)
    return {"success": result, "form": form_name, "property": property_name, "value": value}


@mcp.tool()
def set_form_properties(form_name: str, properties: dict[str, str], connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set multiple properties of a form at once.

    Opens the form in design view, sets each property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form
        properties: Dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the changes
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "set_form_properties", form_name=form_name)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().set_form_properties(form_name, properties)
    if not result:
        return {"success": False, "error": f"No properties found for form '{form_name}'"}
    return {"success": True, "form": form_name, "properties": result}


# ============================================================================
# CONTROL MANIPULATION TOOLS
# ============================================================================


@mcp.tool()
def add_control(
    form_name: str,
    control_type: str,
    control_name: str,
    section: int = 0,
    properties: dict[str, str] | None = None,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Add a control to a form.

    Opens the form in design view, creates the control via DoCmd.CreateControl,
    and sets the control name and optional properties.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form
        control_type: Type of control (e.g., "TextBox", "Label", "CommandButton")
        control_name: Name for the new control
        section: Form section (0=Detail, 1=Header, 2=Footer, default 0)
        properties: Optional dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "add_control", form_name=form_name, control_type=control_type, control_name=control_name)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().add_control(form_name, control_type, control_name, section, properties)
    return {"success": result, "form_name": form_name, "control_name": control_name, "control_type": control_type}


@mcp.tool()
def remove_control(
    form_name: str,
    control_name: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Delete a control from a form.

    Opens the form in design view, selects the control, and deletes it.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form
        control_name: Name of the control to delete
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the deletion
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "remove_control", form_name=form_name, control_name=control_name)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().remove_control(form_name, control_name)
    return {"success": result, "form_name": form_name, "control_name": control_name}


# ============================================================================
# FORM SECTION TOOLS
# ============================================================================


@mcp.tool()
def get_form_sections(form_name: str, connection_name: str = "default") -> dict:
    """
    Get all sections of a form.

    Returns a list of sections with their index, name, type, visibility, and height.
    Forms always have a detail section (index 0). Header, footer, page header,
    and page footer sections may or may not exist.

    Args:
        form_name: Name of the form
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    sections = _com().get_form_sections(form_name)
    if not sections:
        return {"success": False, "error": f"No sections found for form '{form_name}'", "form": form_name}
    return {"success": True, "form": form_name, "sections": sections}


@mcp.tool()
def get_form_section_properties(form_name: str, section_id: int, connection_name: str = "default") -> dict:
    """
    Get all properties of a specific form section.

    Opens the form in design view, reads the section's Properties collection, then closes.

    Args:
        form_name: Name of the form
        section_id: Section index (0=Detail, 1=Header, 2=Footer, 3=PageHeader, 4=PageFooter)
        connection_name: Connection identifier (defaults to "default")
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    props = _com().get_form_section_properties(form_name, section_id)
    if not props:
        return {"success": False, "error": f"No properties found for section {section_id} of form '{form_name}'", "form": form_name, "section_id": section_id}
    return {"success": True, "form": form_name, "section_id": section_id, "properties": props}


@mcp.tool()
def set_form_section_property(
    form_name: str,
    section_id: int,
    property_name: str,
    value: str,
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Set a single property of a form section.

    Opens the form in design view, sets the property on the section, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form
        section_id: Section index (0=Detail, 1=Header, 2=Footer, 3=PageHeader, 4=PageFooter)
        property_name: Name of the property to set
        value: Value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "set_form_section_property", form_name=form_name, section_id=section_id, property_name=property_name)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().set_form_section_property(form_name, section_id, property_name, value)
    return {"success": result, "form_name": form_name, "section_id": section_id, "property_name": property_name, "value": value}


@mcp.tool()
def set_form_section_properties(
    form_name: str,
    section_id: int,
    properties: dict[str, str],
    connection_name: str = "default",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Set multiple properties of a form section at once.

    Opens the form in design view, sets each property on the section, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        form_name: Name of the form
        section_id: Section index (0=Detail, 1=Header, 2=Footer, 3=PageHeader, 4=PageFooter)
        properties: Dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the changes
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    guard = guard_destructive(confirm, dry_run, "set_form_section_properties", form_name=form_name, section_id=section_id)
    if guard is not None:
        return guard
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = _com().set_form_section_properties(form_name, section_id, properties)
    if not result:
        return {"success": False, "error": f"No properties set for section {section_id} of form '{form_name}'"}
    return {"success": True, "form_name": form_name, "section_id": section_id, "properties": result}
