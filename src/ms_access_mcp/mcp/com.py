"""COM Automation and form/report discovery tools for MS Access."""
from .server import mcp, connection_service, schema_service, com_automation_service


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
def get_forms() -> dict:
    """Get all forms in the database."""
    forms = schema_service.get_forms()
    return {"success": True, "forms": [f.model_dump() for f in forms], "count": len(forms)}


@mcp.tool()
def get_reports() -> dict:
    """Get all reports in the database."""
    reports = schema_service.get_reports()
    return {"success": True, "reports": [r.model_dump() for r in reports], "count": len(reports)}


@mcp.tool()
def get_macros() -> dict:
    """Get all macros in the database."""
    macros = schema_service.get_macros()
    return {"success": True, "macros": [m.model_dump() for m in macros], "count": len(macros)}


@mcp.tool()
def get_modules() -> dict:
    """Get all VBA modules in the database."""
    modules = schema_service.get_modules()
    return {"success": True, "modules": [m.model_dump() for m in modules], "count": len(modules)}


@mcp.tool()
def open_form(form_name: str) -> dict:
    """Open a form in Access (appears on the server desktop)."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    result = com_automation_service.open_form(form_name)
    return {"success": result, "form": form_name, "message": "Form opened" if result else "Failed to open form"}


@mcp.tool()
def close_form(form_name: str) -> dict:
    """Close an open form."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    result = com_automation_service.close_form(form_name)
    return {"success": result, "form": form_name, "message": "Form closed" if result else "Failed to close form"}


# ============================================================================
# FORM & CONTROL DISCOVERY TOOLS
# ============================================================================


@mcp.tool()
def form_exists(form_name: str) -> dict:
    """Check if a form exists."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    exists = schema_service.form_exists(form_name)
    return {"success": True, "exists": exists, "form": form_name}


@mcp.tool()
def get_form_controls(form_name: str) -> dict:
    """Get all controls in a form."""
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}

    controls = schema_service.get_form_controls(form_name)
    return {"success": True, "controls": [c.model_dump() for c in controls], "count": len(controls)}


@mcp.tool()
def get_control_properties(form_name: str, control_name: str) -> dict:
    """Get all properties of a specific control in a form.

    Opens the form in design view, reads the control's properties,
    then closes the form.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    props = com_automation_service.get_control_properties(form_name, control_name)
    if not props:
        return {"success": False, "error": f"Control '{control_name}' not found in form '{form_name}'"}
    return {"success": True, "form": form_name, "control": control_name, "properties": props}


@mcp.tool()
def set_control_property(form_name: str, control_name: str, property_name: str, value: str) -> dict:
    """Set a property of a control in a form.

    Opens the form in design view, sets the property, and saves.
    Some properties (ControlType, Name) are read-only and will fail.
    """
    if not connection_service.is_connected():
        return {"success": False, "error": "Not connected to database"}
    result = com_automation_service.set_control_property(form_name, control_name, property_name, value)
    return {"success": result, "form": form_name, "control": control_name, "property": property_name, "value": value}
