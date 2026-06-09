"""Stateless orchestrator for linked table lifecycle management.

All methods accept an ISchemaAdapter and return standardized dicts.
Enforces password-never-persisted policy and provider allowlist validation.
"""
import re
from ..adapters.interfaces import ISchemaAdapter
from .connect_policy import ConnectPolicy


def _inject_password(connect_string: str, password: str | None) -> str:
    """Inject password into connect_string.

    If password is provided and not already in connect_string,
    append it. Otherwise return original.

    Args:
        connect_string: Base connection string (may already have PWD stripped)
        password: Password to inject (from session memory)

    Returns:
        connect_string with password injected if provided.
    """
    if not password:
        return connect_string

    # Check if password already present
    if f"PWD={password}" in connect_string or f"PWD={password};" in connect_string:
        return connect_string

    # Append password
    sep = ";" if not connect_string.endswith(";") else ""
    return f"{connect_string}{sep}PWD={password}"


def _find_existing_table(linked_tables: list[dict], local_name: str) -> dict | None:
    """Find a linked table by local name from get_linked_tables result.

    Args:
        linked_tables: List of linked table dicts from get_linked_tables()
        local_name: Name of the table to find

    Returns:
        The table dict if found, None otherwise.
    """
    for table in linked_tables:
        if table.get("name") == local_name:
            return table
    return None


def _build_result(
    success: bool,
    status: str | None = None,
    error: str | None = None,
    **extra,
) -> dict:
    """Build a standardized result dict.

    Args:
        success: Whether the operation succeeded
        status: Operation status (created, refreshed, recreated, etc.)
        error: Error message if failed
        **extra: Additional fields to include

    Returns:
        Standardized dict with success, status, error, and extra fields.
    """
    result = {"success": success}
    if status is not None:
        result["status"] = status
    if error is not None:
        result["error"] = error
    elif not success:
        result["error"] = "Unknown error"
    result.update(extra)
    return result


class LinkedTableService:
    """Stateless orchestrator for linked table operations.

    Provides upsert logic (create/refresh/recreate) with:
    - Connection policy validation (via injected ConnectPolicy)
    - Password re-injection for refresh/recreate
    - Hidden state preservation on recreate
    - Standardized dict returns
    """

    def __init__(self, policy: ConnectPolicy | None = None) -> None:
        """Initialize LinkedTableService with an optional ConnectPolicy.

        Args:
            policy: ConnectPolicy instance for connection string validation.
                   Defaults to ConnectPolicy() if None.
        """
        self._policy = policy or ConnectPolicy()

    def upsert_linked_table(
        self,
        adapter: ISchemaAdapter,
        local_name: str,
        remote_name: str,
        connect_string: str,
        preserve_hidden: bool = True,
        password: str | None = None,
    ) -> dict:
        """Upsert a linked table — create, refresh, or recreate based on state.

        Args:
            adapter: ISchemaAdapter instance
            local_name: Local table name in the .accdb
            remote_name: Remote table name (e.g., 'dbo.Orders')
            connect_string: Full connection string (may include PWD=)
            preserve_hidden: If True, preserve dbHiddenObject flag on recreate
            password: Optional password for re-injection during refresh/recreate

        Returns:
            dict with keys:
                - success (bool): Whether operation succeeded
                - status (str): 'created', 'refreshed', 'recreated', or None on error
                - error (str|None): Error message if failed
        """
        # Check connection
        if not adapter.is_connected():
            return _build_result(False, error="Not connected to database")

        # Validate connection string against ConnectPolicy
        policy_result = self._policy.validate(connect_string)
        if not policy_result.allowed:
            reasons_str = "; ".join(policy_result.reasons)
            return _build_result(
                False,
                error=f"Connection string rejected: {reasons_str}",
            )

        # Get current linked tables
        tables_result = adapter.get_linked_tables()
        if not tables_result.get("success"):
            return _build_result(False, error=tables_result.get("error", "Failed to get linked tables"))

        linked_tables = tables_result.get("linked_tables", [])
        existing = _find_existing_table(linked_tables, local_name)

        # Extract password for re-injection (password will be stripped after COM operation)
        # If password provided separately, inject it into connect_string first
        if password:
            connect_string = _inject_password(connect_string, password)
        extracted_password = self._extract_password(connect_string)

        if existing is None:
            # Table doesn't exist — create it
            return self._create_table(
                adapter, local_name, remote_name, connect_string, extracted_password
            )
        elif existing.get("source_table") == remote_name:
            # Table exists with same remote name — refresh it
            return self._refresh_table(
                adapter, local_name, connect_string, extracted_password, existing
            )
        else:
            # Table exists but remote name differs — recreate it
            return self._recreate_table(
                adapter, local_name, remote_name, connect_string, extracted_password, existing, preserve_hidden
            )

    def _extract_password(self, connect_string: str) -> str | None:
        """Extract password from connect_string for later re-injection.

        Args:
            connect_string: Connection string that may contain PWD=

        Returns:
            The password if found, None otherwise.
        """
        match = re.search(r"PWD=([^;]*)", connect_string, re.IGNORECASE)
        return match.group(1) if match else None

    def _create_table(
        self,
        adapter: ISchemaAdapter,
        local_name: str,
        remote_name: str,
        connect_string: str,
        password: str | None,
    ) -> dict:
        """Create a new linked table.

        Args:
            adapter: ISchemaAdapter instance
            local_name: Local table name
            remote_name: Remote table name
            connect_string: Connection string (with password)
            password: Extracted password for re-injection

        Returns:
            Standardized result dict.
        """
        try:
            # Inject password for creation
            cs_with_pwd = _inject_password(connect_string, password)

            result = adapter.create_linked_table(local_name, remote_name, cs_with_pwd)
            if not result.get("success"):
                return _build_result(False, error=result.get("error", "Create failed"))

            return _build_result(True, status="created", name=local_name)

        except Exception as e:
            return _build_result(False, error=str(e))

    def _refresh_table(
        self,
        adapter: ISchemaAdapter,
        local_name: str,
        connect_string: str,
        password: str | None,
        existing: dict,
    ) -> dict:
        """Refresh an existing linked table.

        Args:
            adapter: ISchemaAdapter instance
            local_name: Local table name
            connect_string: Connection string (may have PWD stripped)
            password: Extracted password for re-injection
            existing: Existing table info from get_linked_tables

        Returns:
            Standardized result dict.
        """
        try:
            # Re-inject password for refresh
            # Use stored connect_string (password stripped) + password from session
            stored_cs = existing.get("connect_string", "")
            cs_with_pwd = _inject_password(stored_cs, password)

            # Call refresh with optional connect_string (if adapter supports it)
            result = adapter.refresh_linked_table(local_name, cs_with_pwd)
            if not result.get("success"):
                return _build_result(False, error=result.get("error", "Refresh failed"))

            return _build_result(True, status="refreshed", name=local_name)

        except Exception as e:
            return _build_result(False, error=str(e))

    def _recreate_table(
        self,
        adapter: ISchemaAdapter,
        local_name: str,
        remote_name: str,
        connect_string: str,
        password: str | None,
        existing: dict,
        preserve_hidden: bool,
    ) -> dict:
        """Recreate a linked table (delete + create with updated remote name).

        Args:
            adapter: ISchemaAdapter instance
            local_name: Local table name
            remote_name: New remote table name
            connect_string: Connection string (with password)
            password: Extracted password for re-injection
            existing: Existing table info from get_linked_tables
            preserve_hidden: Whether to preserve hidden attribute

        Returns:
            Standardized result dict.
        """
        try:
            # Capture existing attributes for restoration
            old_attributes = existing.get("attributes", 0) if preserve_hidden else None

            # Inject password for recreate
            cs_with_pwd = _inject_password(connect_string, password)

            result = adapter.recreate_linked_table(
                local_name, remote_name, cs_with_pwd, attributes=old_attributes
            )
            if not result.get("success"):
                return _build_result(False, error=result.get("error", "Recreate failed"))

            return _build_result(True, status="recreated", name=local_name)

        except Exception as e:
            return _build_result(False, error=str(e))