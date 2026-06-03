"""Recovery and diagnostics tools for MS Access."""

import platform
import sys
from .server import mcp, connection_service


@mcp.tool()
def recover_access() -> dict:
    """
    Kill hung Microsoft Access processes and reconnect all managed connections.

    Executes taskkill /F /IM MSACCESS.EXE on Windows and attempts to
    reconnect all previously managed connections.

    Returns:
        dict with success status, reconnected connection names, and any errors
    """
    return connection_service.recover_access()


@mcp.tool()
def diagnose_environment() -> dict:
    """
    Provide structured health check of the runtime environment.

    Checks:
    - ACE OLEDB driver availability
    - pywin32 import status
    - COM server launch capability
    - OS platform and Python version
    - Configured allowed directories

    Returns:
        dict with environment diagnostics
    """
    diagnostics: dict = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": sys.version,
        "python_executable": sys.executable,
    }

    # Check ACE OLEDB driver
    try:
        import win32com.client
        diagnostics["pywin32_available"] = True
        diagnostics["pywin32_import"] = "ok"
    except ImportError:
        diagnostics["pywin32_available"] = False
        diagnostics["pywin32_import"] = "not installed"

    # Check ACE OLEDB provider
    if sys.platform == "win32":
        try:
            import winreg
            hklm = winreg.HKEY_LOCAL_MACHINE
            key = winreg.OpenKey(hklm, r"SOFTWARE\Microsoft\Office\16.0\Access Connectivity Engine")
            winreg.CloseKey(key)
            diagnostics["ace_provider"] = "installed"
        except FileNotFoundError:
            diagnostics["ace_provider"] = "not found"
        except PermissionError:
            diagnostics["ace_provider"] = "access denied"
        except Exception as e:
            diagnostics["ace_provider"] = f"error: {e}"
    else:
        diagnostics["ace_provider"] = "windows_only"

    # Check COM server launch (mocked - would require actual COM call)
    if sys.platform == "win32":
        diagnostics["com_server_test"] = "not_tested_in_diagnostics"
    else:
        diagnostics["com_server_test"] = "windows_only"

    # Check allowed directories from config
    try:
        from ..config import ServerConfig
        config = ServerConfig()
        diagnostics["allowed_dirs"] = config.allowed_dirs
        diagnostics["api_key_configured"] = bool(config.api_key)
    except Exception as e:
        diagnostics["config_error"] = str(e)
        diagnostics["allowed_dirs"] = []
        diagnostics["api_key_configured"] = False

    # Overall status
    all_ok = (
        diagnostics.get("pywin32_available", False) and
        diagnostics.get("ace_provider") == "installed" and
        diagnostics.get("allowed_dirs") is not None
    )
    diagnostics["overall_status"] = "ok" if all_ok else "issues_found"

    return {"success": True, "diagnostics": diagnostics}