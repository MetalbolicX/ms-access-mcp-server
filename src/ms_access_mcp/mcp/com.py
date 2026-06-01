"""COM Automation and form/report discovery tools for MS Access — Phase 1 SDD."""
from .server import mcp, connection_service, schema_service, com_automation_service


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return connection_service.get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return connection_service.is_connected(connection_name)


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
    result = com_automation_service.launch_access(visible)
    return {"success": result, "access_running": com_automation_service.is_access_running()}


@mcp.tool()
def close_access() -> dict:
    """Close Microsoft Access application."""
    result = com_automation_service.close_access()
    return {"success": result, "access_running": com_automation_service.is_access_running()}


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
    schema_service.set_adapter(adapter)
    forms = schema_service.get_forms()
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
    schema_service.set_adapter(adapter)
    reports = schema_service.get_reports()
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
    schema_service.set_adapter(adapter)
    macros = schema_service.get_macros()
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
    schema_service.set_adapter(adapter)
    modules = schema_service.get_modules()
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
    result = com_automation_service.open_form(form_name)
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
    result = com_automation_service.close_form(form_name)
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
    schema_service.set_adapter(adapter)
    exists = schema_service.form_exists(form_name)
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
    schema_service.set_adapter(adapter)
    controls = schema_service.get_form_controls(form_name)
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
    com_automation_service.set_adapter(adapter)
    props = com_automation_service.get_control_properties(form_name, control_name)
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
    com_automation_service.set_adapter(adapter)
    result = com_automation_service.set_control_property(form_name, control_name, property_name, value)
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
    com_automation_service.set_adapter(adapter)
    result = com_automation_service.set_control_properties(form_name, control_name, properties)
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
    com_automation_service.set_adapter(adapter)
    procedures = com_automation_service.get_control_event_procedures(form_name, control_name)
    if procedures is None:
        return {"success": False, "error": f"Form module 'Form_{form_name}' not found"}
    return {
        "success": True,
        "form": form_name,
        "control": control_name if control_name else "(all)",
        "event_procedures": procedures,
        "count": len(procedures),
    }
