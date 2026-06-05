from ms_access_mcp.connectors.base import ConnectorCapabilities
from ms_access_mcp.services.transfer_strategy import TransferContext, TransferStrategySelector, PassthroughTransferStrategy


# ─────────────────────────────────────────────────────────────────────────────
# Passthrough with odbc_connection_string override (Phase 3.3, 4.1)
# ─────────────────────────────────────────────────────────────────────────────

def test_passthrough_strategy_can_run_with_odbc_override():
    """PassthroughTransferStrategy.can_run returns True when odbc_connection_string is provided."""

    class _FakeConnectorNoODBC:
        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )
        # No get_odbc_connection_string method

    connector = _FakeConnectorNoODBC()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="T",
        source_adapter=None,
        target_connector=connector,
        source_rows=[{"A": 1}],
        odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p",
    )

    # Override provided → can run even without connector method
    assert strategy.can_run(context) is True


def test_passthrough_strategy_execute_uses_odbc_override():
    """PassthroughTransferStrategy.execute uses the odbc_connection_string override when provided."""

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 10

    class _FakeConnectorNoODBC:
        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )
        # No get_odbc_connection_string method

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorNoODBC()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Orders",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"OrderID": 1}],
        odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=override-host;PORT=5433;DATABASE=override-db;UID=override-user;PWD=override-pass",
    )

    result = strategy.execute(context)

    assert result.strategy_used == "passthrough"
    assert result.rows_transferred == 10
    sql = adapter.executed_sql[0]
    # Override string is used when provided
    assert "SERVER=override-host" in sql
    assert "PORT=5433" in sql
    assert "DATABASE=override-db" in sql


def test_selector_passthrough_with_odbc_override_when_linked_unsupported():
    """Selector uses passthrough with odbc_override when linked is not supported."""

    class _FakeConnectorPassthroughOnly:
        def __init__(self):
            self.passthrough_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 4

    connector = _FakeConnectorPassthroughOnly()

    class _FakeAdapter:
        def __init__(self, rows: list[dict]):
            self.rows = rows

        def execute_query(self, sql: str, params=None):
            _ = params
            return {"success": True, "rows": list(self.rows), "count": len(self.rows), "columns": []}

    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}, {"ID": 3}, {"ID": 4}],
        odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p",
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "passthrough"


# ─────────────────────────────────────────────────────────────────────────────
# Fallback reason normalization (Phase 4.1)
# ─────────────────────────────────────────────────────────────────────────────

def test_fallback_reason_for_linked_runtime_then_passthrough_success():
    """When linked fails at runtime and passthrough succeeds, fallback_reason explains the chain."""

    class _FakeConnectorLinkedFailsPassthroughWorks:
        def __init__(self):
            self._odbc_str = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked runtime error")

        def get_odbc_connection_string(self) -> str:
            return self._odbc_str

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 3

    class _FakeAdapter:
        def __init__(self, rows: list[dict]):
            self.rows = rows

        def execute_query(self, sql: str, params=None):
            _ = params
            return {"success": True, "rows": list(self.rows), "count": len(self.rows), "columns": []}

    connector = _FakeConnectorLinkedFailsPassthroughWorks()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Passthrough succeeded after linked failed
    assert outcome.strategy_used == "passthrough"
    assert outcome.fallback_reason is not None
    assert "linked" in outcome.fallback_reason.lower()


def test_fallback_reason_when_passthrough_fails_then_batch():
    """When passthrough fails and batch succeeds, fallback_reason mentions passthrough."""

    class _FakeConnectorPassthroughFailsBatchWorks:
        def __init__(self):
            self.batch_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.batch_calls += 1
            return len(rows)

    class _FakeAdapterPassthroughFails:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            raise RuntimeError("passthrough SQL error")

    class _FakeAdapter:
        def __init__(self, rows: list[dict]):
            self.rows = rows

        def execute_query(self, sql: str, params=None):
            _ = params
            return {"success": True, "rows": list(self.rows), "count": len(self.rows), "columns": []}

    connector = _FakeConnectorPassthroughFailsBatchWorks()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterPassthroughFails(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert outcome.fallback_reason is not None
    assert "passthrough" in outcome.fallback_reason.lower()
    assert connector.batch_calls == 1


def test_fallback_reason_normalized_consistency():
    """Fallback reasons are consistent strings (not empty, not None when fallback occurred)."""

    class _FakeConnectorAllFail:
        def __init__(self):
            self.final_result = 10

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked failed")

        def get_odbc_connection_string(self) -> str:
            raise RuntimeError("ODBC failed")

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            return self.final_result

    class _FakeAdapter:
        def __init__(self, rows: list[dict]):
            self.rows = rows

        def execute_query(self, sql: str, params=None):
            _ = params
            return {"success": True, "rows": list(self.rows), "count": len(self.rows), "columns": []}

    connector = _FakeConnectorAllFail()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}]),
        target_connector=connector,
        source_rows=[{"A": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # batch was used as last resort
    assert outcome.strategy_used == "batch"
    # fallback_reason must be set when falling back
    assert outcome.fallback_reason is not None
    assert len(outcome.fallback_reason) > 0
    # Should mention at least one failed strategy
    reason_lower = outcome.fallback_reason.lower()
    assert "linked" in reason_lower or "passthrough" in reason_lower


# ─────────────────────────────────────────────────────────────────────────────
# TransferStrategy.can_run with odbc_override (no connector method needed)
# ─────────────────────────────────────────────────────────────────────────────

def test_passthrough_can_run_false_without_override_or_connector_method():
    """PassthroughTransferStrategy.can_run returns False when no override AND no connector method."""

    class _FakeConnectorNoMethod:
        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )
        # No get_odbc_connection_string method, no odbc_connection_string in context

    connector = _FakeConnectorNoMethod()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="T",
        source_adapter=None,
        target_connector=connector,
        source_rows=[{"A": 1}],
        odbc_connection_string=None,  # No override
    )

    # Neither override nor connector method → can't run
    assert strategy.can_run(context) is False


def test_passthrough_strategy_with_odbc_override_and_connector_both():
    """When both override and connector method exist, override is used (takes precedence)."""

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 5

    class _FakeConnectorWithODBC:
        def __init__(self):
            self.connector_odbc = "DRIVER={PostgreSQL Unicode};SERVER=connector-host;PORT=5432;DATABASE=connector-db;UID=connector-user;PWD=connector-pass"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.connector_odbc

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithODBC()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="T",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"A": 1}],
        odbc_connection_string="DRIVER={PostgreSQL Unicode};SERVER=override-host;PORT=5433;DATABASE=override-db;UID=u;PWD=p",
    )

    result = strategy.execute(context)

    sql = adapter.executed_sql[0]
    # Override takes precedence when provided
    assert "SERVER=override-host" in sql
    assert "SERVER=connector-host" not in sql