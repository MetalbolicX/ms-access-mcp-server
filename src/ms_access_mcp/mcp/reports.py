"""Report manipulation tools for MS Access — PR1 Core/CRUD/Properties."""
from ._helpers import destructive_guard, require_connected
from .container import get_container
from .server import mcp


def _pool():
    return get_container().connection_pool


def _get_adapter(connection_name: str = "default"):
    """Get adapter for a named connection, or return None if not found."""
    try:
        return _pool().get_adapter(connection_name)
    except KeyError:
        return None


def _check_connected(connection_name: str = "default"):
    """Check if a named connection is connected."""
    return _pool().is_connected(connection_name)


def _ensure_connected(connection_name: str = "default"):
    """Check connection and return adapter, or None if not connected."""
    if not _check_connected(connection_name):
        return None
    return _get_adapter(connection_name)


# ============================================================================
# REPORT DISCOVERY TOOLS
# ============================================================================


@require_connected()
@mcp.tool()
def report_exists(report_name: str, connection_name: str = "default") -> dict:
    """
    Check if a report exists.

    Args:
        report_name: Name of the report to check
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    exists = adapter.report_exists(report_name)
    return {"success": True, "exists": exists, "report": report_name}


@require_connected()
@mcp.tool()
def get_reports(connection_name: str = "default") -> dict:
    """
    Get all reports in the database.

    Args:
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    reports = adapter.get_reports()
    return {"success": True, "reports": [r.model_dump() for r in reports], "count": len(reports)}


# ============================================================================
# REPORT MANIPULATION TOOLS
# ============================================================================


@require_connected()
@mcp.tool()
def create_report(report_name: str, record_source: str = "", template_name: str = "", properties: dict[str, str] | None = None, connection_name: str = "default") -> dict:
    """
    Create a new blank report, optionally with a RecordSource.

    Args:
        report_name: Name for the new report
        record_source: SQL table/query to bind as RecordSource (optional)
        template_name: Template to base the report on (optional, unused in MVP)
        properties: Additional properties to set after creation (optional)
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    result = adapter.create_report(report_name, record_source, template_name, properties)
    return {"success": result, "report_name": report_name}


@destructive_guard(action="rename_report")
@mcp.tool()
def rename_report(old_name: str, new_name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Rename an existing report.

    This is a destructive action. Set confirm=True to execute, or dry_run=True
    to preview without making changes.

    Args:
        old_name: Current name of the report
        new_name: New name for the report
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the rename
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.rename_report(old_name, new_name)
    return {"success": result, "old_name": old_name, "new_name": new_name}


@require_connected()
@mcp.tool()
def get_report_properties(report_name: str, connection_name: str = "default") -> dict:
    """
    Get all properties of a report.

    Opens the report in design view, reads Report.Properties, then closes.

    Args:
        report_name: Name of the report
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    props = adapter.get_report_properties(report_name)
    if not props:
        return {"success": False, "error": f"No properties found for report '{report_name}'", "report": report_name}
    return {"success": True, "report": report_name, "properties": props}


@destructive_guard(action="set_report_property")
@mcp.tool()
def set_report_property(report_name: str, property_name: str, value: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set a single property of a report.

    Opens the report in design view, sets the property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        property_name: Name of the property to set
        value: Value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.set_report_property(report_name, property_name, value)
    return {"success": result, "report": report_name, "property": property_name, "value": value}


@destructive_guard(action="set_report_properties")
@mcp.tool()
def set_report_properties(report_name: str, properties: dict[str, str], connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set multiple properties of a report at once.

    Opens the report in design view, sets each property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        properties: Dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the changes
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.set_report_properties(report_name, properties)
    if not result:
        return {"success": False, "error": f"No properties found for report '{report_name}'"}
    return {"success": True, "report": report_name, "properties": result}


# =============================================================================
# REPORT CONTROL TOOLS
# =============================================================================


@require_connected()
@mcp.tool()
def get_report_controls(report_name: str, connection_name: str = "default") -> dict:
    """
    Get all controls in a report.

    Opens the report in design view, reads Report.Controls, then closes.

    Args:
        report_name: Name of the report
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    controls = adapter.get_report_controls(report_name)
    return {"success": True, "controls": [c.model_dump() for c in controls], "count": len(controls)}


@require_connected()
@mcp.tool()
def get_report_control_properties(report_name: str, control_name: str, connection_name: str = "default") -> dict:
    """
    Get all properties of a specific control in a report.

    Opens the report in design view, finds the control, reads its properties, then closes.

    Args:
        report_name: Name of the report
        control_name: Name of the control
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    props = adapter.get_report_control_properties(report_name, control_name)
    if not props:
        return {"success": False, "error": f"No properties found for control '{control_name}' in report '{report_name}'", "report": report_name, "control": control_name}
    return {"success": True, "report": report_name, "control": control_name, "properties": props}


@destructive_guard(action="set_report_control_property")
@mcp.tool()
def set_report_control_property(report_name: str, control_name: str, property_name: str, value: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set a single property of a control in a report.

    Opens the report in design view, finds the control, sets the property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        control_name: Name of the control
        property_name: Name of the property to set
        value: Value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.set_report_control_property(report_name, control_name, property_name, value)
    return {"success": result, "report": report_name, "control": control_name, "property": property_name, "value": value}


@destructive_guard(action="set_report_control_properties")
@mcp.tool()
def set_report_control_properties(report_name: str, control_name: str, properties: dict[str, str], connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set multiple properties of a control in a report at once.

    Opens the report in design view, finds the control, sets each property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        control_name: Name of the control
        properties: Dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the changes
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.set_report_control_properties(report_name, control_name, properties)
    if not result:
        return {"success": False, "error": f"No properties found for control '{control_name}' in report '{report_name}'"}
    return {"success": True, "report": report_name, "control": control_name, "properties": result}


@destructive_guard(action="add_report_control")
@mcp.tool()
def add_report_control(report_name: str, control_type: str, control_name: str, section: int = 0, properties: dict[str, str] | None = None, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Add a control to a report.

    Opens the report in design view, creates the control with the given type and name,
    optionally sets properties, and saves. This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        control_type: Type of control (e.g., "TextBox", "Label", "CommandButton")
        control_name: Name for the new control
        section: Section index (0=detail, 1=header, 2=footer, 3=page_header, 4=page_footer)
        properties: Additional properties to set after creation (optional)
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.add_report_control(report_name, control_type, control_name, section, properties)
    return {"success": result, "report": report_name, "control_name": control_name, "control_type": control_type}


@destructive_guard(action="remove_report_control")
@mcp.tool()
def remove_report_control(report_name: str, control_name: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Remove a control from a report.

    Opens the report in design view, selects and deletes the control, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        control_name: Name of the control to remove
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.remove_report_control(report_name, control_name)
    return {"success": result, "report": report_name, "control": control_name}


# =============================================================================
# REPORT SECTION TOOLS
# =============================================================================


@require_connected()
@mcp.tool()
def get_report_sections(report_name: str, connection_name: str = "default") -> dict:
    """
    Get all sections of a report.

    Opens the report in design view, reads Report.Sections, then closes.

    Args:
        report_name: Name of the report
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    sections = adapter.get_report_sections(report_name)
    return {"success": True, "report": report_name, "sections": sections, "count": len(sections)}


@require_connected()
@mcp.tool()
def get_report_section_properties(report_name: str, section_id: int, connection_name: str = "default") -> dict:
    """
    Get all properties of a specific section in a report.

    Opens the report in design view, finds the section, reads its properties, then closes.

    Args:
        report_name: Name of the report
        section_id: Section index (0=detail, 1=header, 2=footer, 3=page_header, 4=page_footer)
        connection_name: Connection identifier (defaults to "default")
    """
    adapter = _ensure_connected(connection_name)
    if adapter is None:
        return {"success": False, "error": "Not connected to database"}
    props = adapter.get_report_section_properties(report_name, section_id)
    if not props:
        return {"success": False, "error": f"No properties found for section {section_id} in report '{report_name}'", "report": report_name, "section_id": section_id}
    return {"success": True, "report": report_name, "section_id": section_id, "properties": props}


@destructive_guard(action="set_report_section_property")
@mcp.tool()
def set_report_section_property(report_name: str, section_id: int, property_name: str, value: str, connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set a single property of a section in a report.

    Opens the report in design view, finds the section, sets the property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        section_id: Section index (0=detail, 1=header, 2=footer, 3=page_header, 4=page_footer)
        property_name: Name of the property to set
        value: Value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the change
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.set_report_section_property(report_name, section_id, property_name, value)
    return {"success": result, "report": report_name, "section_id": section_id, "property": property_name, "value": value}


@destructive_guard(action="set_report_section_properties")
@mcp.tool()
def set_report_section_properties(report_name: str, section_id: int, properties: dict[str, str], connection_name: str = "default", confirm: bool = False, dry_run: bool = False) -> dict:
    """
    Set multiple properties of a section in a report at once.

    Opens the report in design view, finds the section, sets each property, and saves.
    This is a destructive action — set confirm=True to execute.

    Args:
        report_name: Name of the report
        section_id: Section index (0=detail, 1=header, 2=footer, 3=page_header, 4=page_footer)
        properties: Dict of property_name -> value to set
        connection_name: Connection identifier (defaults to "default")
        confirm: Must be True to execute the changes
        dry_run: If True, returns a preview without executing
    """
    if not _check_connected(connection_name):
        return {"success": False, "error": "Not connected to database"}
    adapter = _get_adapter(connection_name)
    if adapter is None:
        return {"success": False, "error": "No adapter available"}
    result = adapter.set_report_section_properties(report_name, section_id, properties)
    if not result:
        return {"success": False, "error": f"No properties found for section {section_id} in report '{report_name}'", "report": report_name, "section_id": section_id}
    return {"success": True, "report": report_name, "section_id": section_id, "properties": result}
