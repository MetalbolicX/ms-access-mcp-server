from typing import Any
from .base import AccessAdapter


class WinComAdapter(AccessAdapter):
    """COM-based adapter using pywin32."""

    def connect(self, db_path: str) -> bool:
        raise NotImplementedError("Stub")

    def disconnect(self) -> None:
        raise NotImplementedError("Stub")

    def is_connected(self) -> bool:
        raise NotImplementedError("Stub")

    def get_tables(self) -> list[Any]:
        raise NotImplementedError("Stub")

    def execute_query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("Stub")

    def launch_access(self, visible: bool = False) -> None:
        raise NotImplementedError("Stub")

    def close_access(self) -> None:
        raise NotImplementedError("Stub")

    def set_vba_code(self, module_name: str, code: str) -> bool:
        raise NotImplementedError("Stub")
