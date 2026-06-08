"""Regression tests for IDataAdapter protocol — ensure execute_raw_sql is required."""

from typing import Any
from ms_access_mcp.adapters.interfaces import IDataAdapter


class TestIDataAdapterProtocol:
    """Verify IDataAdapter requires execute_raw_sql method."""

    def test_fake_adapter_without_execute_raw_sql_is_not_idata_adapter(self):
        """Regression: A fake adapter missing execute_raw_sql must NOT be considered an IDataAdapter.

        This test will FAIL until execute_raw_sql is added to IDataAdapter.
        Once added, adapters that lack this method will fail the runtime_checkable check.
        """
        class FakeAdapterWithoutExecuteRawSql:
            """Minimal adapter that implements IDataAdapter methods except execute_raw_sql."""
            def connect(self, db_path: str) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def execute_query(self, sql: str, params: list | None = None) -> dict:
                return {"rows": [], "count": 0}

            def insert_data(self, table_name: str, data: dict | list[dict]) -> dict:
                return {"success": True}

            def update_data(self, table_name: str, set_dict: dict, where_dict: dict | str | None = None) -> dict:
                return {"success": True}

            def delete_data(self, table_name: str, where_dict: dict | str | None = None) -> dict:
                return {"success": True}

            def export_data(self, sql: str, file_path: str, format: str = "csv", **options: Any) -> dict:
                return {"success": True}

        fake = FakeAdapterWithoutExecuteRawSql()

        # Before the change: fake IS considered IDataAdapter (test FAILS)
        # After the change: fake is NOT considered IDataAdapter (test PASSES)
        assert not isinstance(fake, IDataAdapter), (
            "FakeAdapterWithoutExecuteRawSql should NOT be considered an IDataAdapter "
            "because it lacks execute_raw_sql"
        )

    def test_adapter_with_execute_raw_sql_is_valid_idata_adapter(self):
        """Verify that an adapter with execute_raw_sql IS considered an IDataAdapter."""
        class FakeAdapterWithExecuteRawSql:
            """Full IDataAdapter implementation including execute_raw_sql."""
            def connect(self, db_path: str) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def execute_query(self, sql: str, params: list | None = None) -> dict:
                return {"rows": [], "count": 0}

            def insert_data(self, table_name: str, data: dict | list[dict]) -> dict:
                return {"success": True}

            def update_data(self, table_name: str, set_dict: dict, where_dict: dict | str | None = None) -> dict:
                return {"success": True}

            def delete_data(self, table_name: str, where_dict: dict | str | None = None) -> dict:
                return {"success": True}

            def export_data(self, sql: str, file_path: str, format: str = "csv", **options: Any) -> dict:
                return {"success": True}

            def execute_raw_sql(self, sql: str) -> int:
                return 0

        fake = FakeAdapterWithExecuteRawSql()
        assert isinstance(fake, IDataAdapter), "Adapter with execute_raw_sql should be IDataAdapter"
