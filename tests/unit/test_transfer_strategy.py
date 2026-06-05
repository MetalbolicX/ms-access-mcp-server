from ms_access_mcp.connectors.base import ConnectorCapabilities
from ms_access_mcp.services.transfer_strategy import TransferContext, TransferStrategySelector


class _FakeAdapter:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def execute_query(self, sql: str, params=None):
        _ = params
        return {"success": True, "rows": list(self.rows), "count": len(self.rows), "columns": []}


class _FakeConnector:
    def __init__(self, *, supports_linked: bool, linked_error: Exception | None = None, supports_passthrough: bool = False):
        self._supports_linked = supports_linked
        self._linked_error = linked_error
        self._supports_passthrough = supports_passthrough
        self.linked_calls = 0
        self.batch_calls = 0

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_linked_insert_select=self._supports_linked,
            supports_passthrough_insert_select=self._supports_passthrough,
            supports_checksum=True,
            supports_sampling=True,
            preferred_batch_size=1000,
        )

    def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
        _ = source_adapter
        _ = target_table
        self.linked_calls += 1
        if self._linked_error is not None:
            raise self._linked_error
        return 3

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        _ = table
        self.batch_calls += 1
        return len(rows)


def test_selector_prefers_linked_when_supported():
    selector = TransferStrategySelector()
    connector = _FakeConnector(supports_linked=True)
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}, {"ID": 2}, {"ID": 3}]),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}, {"ID": 3}],
    )

    outcome = selector.transfer(context)

    assert outcome.strategy_used == "linked"
    assert outcome.rows_transferred == 3
    assert connector.linked_calls == 1
    assert connector.batch_calls == 0


def test_selector_falls_back_to_batch_when_linked_preflight_fails():
    selector = TransferStrategySelector()
    connector = _FakeConnector(supports_linked=False)
    context = TransferContext(
        table_name="Orders",
        source_adapter=_FakeAdapter([{"OrderID": 1}, {"OrderID": 2}]),
        target_connector=connector,
        source_rows=[{"OrderID": 1}, {"OrderID": 2}],
    )

    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert outcome.rows_transferred == 2
    assert outcome.fallback_reason == "linked preflight failed"
    assert connector.linked_calls == 0
    assert connector.batch_calls == 1


def test_passthrough_strategy_can_run_when_connector_supports_it():
    """PassthroughTransferStrategy.can_run returns True when connector has passthrough capability."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy
    from ms_access_mcp.connectors.base import ConnectorCapabilities

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self._caps = ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_capabilities(self) -> ConnectorCapabilities:
            return self._caps

        def get_odbc_connection_string(self) -> str:
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    connector = _FakeConnectorWithPassthrough()
    strategy = PassthroughTransferStrategy()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}]),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    assert strategy.can_run(context) is True


def test_passthrough_strategy_can_run_false_when_not_supported():
    """PassthroughTransferStrategy.can_run returns False when connector lacks passthrough."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    connector = _FakeConnector(supports_linked=False)
    connector._supports_passthrough = False

    strategy = PassthroughTransferStrategy()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}]),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    assert strategy.can_run(context) is False


def test_passthrough_strategy_execute_builds_correct_sql():
    """PassthroughTransferStrategy.execute builds INSERT INTO [ODBC;...] SELECT SQL."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [{"ID": 1}], "count": 1, "columns": ["ID"]}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 3

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self.odbc_connection_string = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=user;PWD=pass"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_connection_string

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithPassthrough()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Customers",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Bob"}, {"ID": 3, "Name": "Carol"}],
        columns=["ID", "Name"],
        where_clause=None,
        order_by_columns=None,
    )

    result = strategy.execute(context)

    assert result.strategy_used == "passthrough"
    assert result.rows_transferred == 3
    assert len(adapter.executed_sql) == 1
    sql = adapter.executed_sql[0]
    assert "INSERT INTO [ODBC;" in sql
    assert "DRIVER={PostgreSQL Unicode}" in sql
    assert "SELECT [ID], [Name] FROM [Customers]" in sql
    assert "[Customers]" in sql


def test_passthrough_strategy_execute_with_columns_filter():
    """Passthrough with column filter builds correct SELECT clause."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 0

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self.odbc_connection_string = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_connection_string

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithPassthrough()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Orders",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"OrderID": 1}],
        columns=["OrderID", "Total"],
        where_clause=None,
        order_by_columns=None,
    )

    result = strategy.execute(context)

    assert result.strategy_used == "passthrough"
    sql = adapter.executed_sql[0]
    assert "SELECT [OrderID], [Total] FROM [Orders]" in sql


def test_passthrough_strategy_execute_with_where_clause():
    """Passthrough with WHERE builds correct SQL."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 5

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self.odbc_connection_string = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_connection_string

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithPassthrough()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Orders",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"OrderID": 1}],
        columns=None,
        where_clause="Status='active'",
        order_by_columns=None,
    )

    result = strategy.execute(context)

    assert result.strategy_used == "passthrough"
    sql = adapter.executed_sql[0]
    assert "WHERE Status='active'" in sql


def test_passthrough_strategy_execute_with_order_by():
    """Passthrough with ORDER BY builds correct SQL."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 4

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self.odbc_connection_string = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_connection_string

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithPassthrough()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Orders",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"OrderID": 1}],
        columns=None,
        where_clause=None,
        order_by_columns=["OrderID", "Total"],
    )

    result = strategy.execute(context)

    assert result.strategy_used == "passthrough"
    sql = adapter.executed_sql[0]
    assert "ORDER BY [OrderID], [Total]" in sql


def test_selector_passthrough_fallback_to_batch():
    """TransferStrategySelector falls back to batch when passthrough fails."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector, PassthroughTransferStrategy

    class _FakeConnectorFailsPassthrough:
        def __init__(self):
            self._supports_passthrough = True
            self.batch_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            raise RuntimeError("DSN parse failed")

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.batch_calls += 1
            return len(rows)

    selector = TransferStrategySelector()
    connector = _FakeConnectorFailsPassthrough()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}, {"ID": 2}]),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}],
    )

    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert outcome.fallback_reason is not None
    assert "passthrough" in outcome.fallback_reason.lower()
    assert connector.batch_calls == 1


def test_selector_prefers_passthrough_over_batch():
    """TransferStrategySelector prefers passthrough over batch when both available."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self._supports_linked = False
            self._supports_passthrough = True
            self.passthrough_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 3

    connector = _FakeConnectorWithPassthrough()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}, {"ID": 3}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "passthrough"


def test_selector_passthrough_before_batch_order():
    """Selector prefers: linked > passthrough > batch."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorAllSupported:
        def __init__(self):
            self.calls = {"linked": 0, "passthrough": 0, "batch": 0}

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            self.calls["linked"] += 1
            return 5

        def get_odbc_connection_string(self) -> str:
            self.calls["passthrough"] += 1
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.calls["batch"] += 1
            return len(rows)

    connector = _FakeConnectorAllSupported()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}]),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # linked should be chosen first since it has highest priority
    assert outcome.strategy_used == "linked"


def test_selector_passthrough_when_linked_unsupported():
    """Selector uses passthrough when linked is not supported but passthrough is."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

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

        def get_odbc_connection_string(self) -> str:
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 2

    connector = _FakeConnectorPassthroughOnly()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "passthrough"


def test_selector_retries_with_passthrough_when_linked_runtime_fails():
    """After linked runtime fails, selector tries passthrough before batch."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorLinkedFailsPassthroughWorks:
        def __init__(self):
            self.calls = {"passthrough": 0, "batch": 0}

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
            self.calls["passthrough"] += 1
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.calls["batch"] += 1
            return len(rows)

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 3

    connector = _FakeConnectorLinkedFailsPassthroughWorks()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}, {"ID": 3}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Should fall back to passthrough, not directly to batch
    assert outcome.strategy_used == "passthrough"
    assert "linked" in outcome.fallback_reason.lower()


def test_selector_retries_with_batch_when_passthrough_runtime_fails():
    """After passthrough runtime fails, selector falls back to batch."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorPassthroughFails:
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
            raise RuntimeError("passthrough SQL failed")

    connector = _FakeConnectorPassthroughFails()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterPassthroughFails(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert "passthrough" in outcome.fallback_reason.lower()
    assert connector.batch_calls == 1


def test_selector_passthrough_preflight_check():
    """Selector checks passthrough preflight before attempting execute."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorPassthroughNotConfigured:
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
            raise RuntimeError("no DSN configured")

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.batch_calls += 1
            return len(rows)

    connector = _FakeConnectorPassthroughNotConfigured()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}]),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Should fall back to batch because passthrough preflight failed
    assert outcome.strategy_used == "batch"
    assert outcome.fallback_reason is not None


def test_selector_passthrough_with_empty_rows_falls_to_batch():
    """Passthrough with no source rows falls back to batch (passthrough needs SELECT)."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorPassthrough:
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
            return 0

    connector = _FakeConnectorPassthrough()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([]),
        target_connector=connector,
        source_rows=[],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Empty rows: passthrough can't run (no rows to SELECT from), falls to batch
    assert outcome.strategy_used == "batch"


def test_selector_passthrough_when_pgpassword_env_var_used():
    """Passthrough uses PGPASSWORD env var when password not in DSN."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector
    import os

    class _FakeConnectorNoPassword:
        def __init__(self):
            self.executed_sql: list[str] = []

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            # Simulates DSN without password, PGPASSWORD should fill the gap
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=user"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 0

    connector = _FakeConnectorNoPassword()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Should use passthrough (it skips PGPASSWORD check, just passes the string as-is)
    assert outcome.strategy_used == "passthrough"


# ─────────────────────────────────────────────────────────────────────────────
# TransferStrategySelector — passthrough in fallback chain
# ─────────────────────────────────────────────────────────────────────────────

def test_selector_falls_linked_to_passthrough_to_batch():
    """Full fallback chain: linked preflight fail → passthrough → batch."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorFullChain:
        def __init__(self):
            self.calls = {"passthrough": 0, "batch": 0}

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,  # supported but...
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked preflight failed")

        def get_odbc_connection_string(self) -> str:
            self.calls["passthrough"] += 1
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.calls["batch"] += 1
            return len(rows)

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 3

    connector = _FakeConnectorFullChain()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}, {"ID": 2}, {"ID": 3}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # linked preflight failed → try passthrough → success
    assert outcome.strategy_used == "passthrough"
    assert outcome.fallback_reason is not None
    assert "linked" in outcome.fallback_reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# PassthroughTransferStrategy.execute returns TransferResult with correct metadata
# ─────────────────────────────────────────────────────────────────────────────

def test_passthrough_execute_returns_transfer_result_with_rows_and_duration():
    """PassthroughTransferStrategy.execute returns TransferResult with rows_transferred and duration_ms."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 7

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self.odbc_connection_string = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_connection_string

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithPassthrough()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Customers",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"ID": 1}],
        columns=None,
        where_clause=None,
        order_by_columns=None,
    )

    result = strategy.execute(context)

    assert result.rows_transferred == 7
    assert result.strategy_used == "passthrough"
    assert result.duration_ms >= 0


def test_selector_passthrough_selects_linked_first_when_both_supported():
    """When both linked and passthrough are supported, linked is chosen first."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorBothSupported:
        def __init__(self):
            self.linked_called = False

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            self.linked_called = True
            return 10

    connector = _FakeConnectorBothSupported()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapter([{"ID": 1}]),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # linked has highest priority
    assert outcome.strategy_used == "linked"
    assert connector.linked_called is True


def test_selector_passthrough_executes_when_linked_returns_zero_rows():
    """Passthrough is NOT retried after linked succeeds with 0 rows (0 is still success)."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorLinkedReturnsZero:
        def __init__(self):
            self.passthrough_called = False

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            return 0  # Success but 0 rows transferred

        def get_odbc_connection_string(self) -> str:
            self.passthrough_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 0

    connector = _FakeConnectorLinkedReturnsZero()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # linked returned 0 but that's still success — no retry with passthrough
    assert outcome.strategy_used == "linked"
    assert connector.passthrough_called is False


def test_selector_passthrough_retries_when_linked_raises_exception():
    """Passthrough is tried when linked raises an exception."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorLinkedRaisesPassthroughWorks:
        def __init__(self):
            self.passthrough_called = False

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
            self.passthrough_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 5

    connector = _FakeConnectorLinkedRaisesPassthroughWorks()
    context = TransferContext(
        table_name="Customers",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "passthrough"
    assert connector.passthrough_called is True


def test_selector_passthrough_when_linked_not_supported_but_passthrough_is():
    """Passthrough is chosen when linked is not supported but passthrough is."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorNoLinkedYesPassthrough:
        def __init__(self):
            self.passthrough_called = False

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,  # NOT supported
                supports_passthrough_insert_select=True,  # supported
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            self.passthrough_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 4

    connector = _FakeConnectorNoLinkedYesPassthrough()
    context = TransferContext(
        table_name="Orders",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"OrderID": 1}, {"ID": 2}, {"ID": 3}, {"ID": 4}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "passthrough"
    assert connector.passthrough_called is True


def test_selector_passthrough_when_linked_preflight_fails():
    """Passthrough is tried when linked preflight check fails."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorLinkedPreflightFails:
        def __init__(self):
            self.passthrough_called = False

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,  # supported
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked preflight failed")

        def get_odbc_connection_string(self) -> str:
            self.passthrough_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 6

    connector = _FakeConnectorLinkedPreflightFails()
    context = TransferContext(
        table_name="Orders",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "passthrough"
    assert "linked" in outcome.fallback_reason.lower()


def test_selector_passthrough_not_tried_when_not_in_capabilities():
    """Passthrough is skipped when connector does not advertise it in capabilities."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorNoPassthroughCapability:
        def __init__(self):
            self.passthrough_called = False
            self.batch_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=False,  # NOT supported
                supports_checksum=True,
                supports_sampling=True,
            )

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.batch_calls += 1
            return len(rows)

    connector = _FakeConnectorNoPassthroughCapability()
    context = TransferContext(
        table_name="Orders",
        source_adapter=_FakeAdapter([{"ID": 1}]),
        target_connector=connector,
        source_rows=[{"ID": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # No passthrough capability → falls to batch
    assert outcome.strategy_used == "batch"
    assert connector.batch_calls == 1


def test_passthrough_strategy_full_sql_building():
    """Full SQL shape: INSERT INTO [ODBC;DRIVER=...;SERVER=...;PORT=...;DATABASE=...;UID=...;PWD=...].[table] SELECT ... FROM [...] [WHERE ...] [ORDER BY ...]."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql: str, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 5

    class _FakeConnectorFull:
        def __init__(self):
            self.odbc_connection_string = "DRIVER={PostgreSQL Unicode};SERVER=db.example.com;PORT=5432;DATABASE=production;UID=admin;PWD=secret123"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_connection_string

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorFull()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Orders",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"OrderID": 1, "Total": 100.0, "Status": "active"}],
        columns=["OrderID", "Total", "Status"],
        where_clause="Status='active'",
        order_by_columns=["OrderID"],
    )

    result = strategy.execute(context)

    assert result.strategy_used == "passthrough"
    sql = adapter.executed_sql[0]
    # INSERT INTO [ODBC;DRIVER={PostgreSQL Unicode};SERVER=db.example.com;PORT=5432;DATABASE=production;UID=admin;PWD=secret123].[Orders]
    assert sql.startswith("INSERT INTO [ODBC;")
    assert "DRIVER={PostgreSQL Unicode}" in sql
    assert "SERVER=db.example.com" in sql
    assert "PORT=5432" in sql
    assert "DATABASE=production" in sql
    assert "UID=admin" in sql
    assert "PWD=secret123" in sql
    assert "].[Orders]" in sql
    # SELECT clause
    assert "SELECT [OrderID], [Total], [Status] FROM [Orders]" in sql
    # WHERE clause
    assert "WHERE Status='active'" in sql
    # ORDER BY clause
    assert "ORDER BY [OrderID]" in sql


def test_selector_passthrough_uses_connector_get_odbc_connection_string():
    """The connector's get_odbc_connection_string() is called to build passthrough SQL."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorReturnsDSN:
        def __init__(self):
            self.get_odbc_connection_string_called = False
            self.dsn_returned = "DRIVER={PostgreSQL Unicode};SERVER=myhost;PORT=5432;DATABASE=mydb;UID=myuser;PWD=mypassword"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            self.get_odbc_connection_string_called = True
            return self.dsn_returned

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.executed_sql: list[str] = []

        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.executed_sql.append(sql)
            return 1

    connector = _FakeConnectorReturnsDSN()
    adapter = _FakeAdapterWithExecuteRaw()
    context = TransferContext(
        table_name="T",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"A": 1}],
        columns=None,
        where_clause=None,
        order_by_columns=None,
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert connector.get_odbc_connection_string_called is True
    assert "SERVER=myhost" in adapter.executed_sql[0]


# ─────────────────────────────────────────────────────────────────────────────
# TransferStrategySelector — passthrough ordering (linked → passthrough → batch)
# ─────────────────────────────────────────────────────────────────────────────

def test_selector_falls_from_linked_to_passthrough_not_batch():
    """linked preflight fail → try passthrough before batch."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorLinkedFailsPassthroughWorks:
        def __init__(self):
            self.passthrough_called = False

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked preflight failed")

        def get_odbc_connection_string(self) -> str:
            self.passthrough_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 2

    connector = _FakeConnectorLinkedFailsPassthroughWorks()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"A": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Should be passthrough, not batch
    assert outcome.strategy_used == "passthrough"
    assert connector.passthrough_called is True


def test_selector_falls_from_passthrough_to_batch():
    """passthrough runtime error → fall back to batch."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorPassthroughError:
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

    class _FakeAdapterRaises:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            raise RuntimeError("SQL execution error")

    connector = _FakeConnectorPassthroughError()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapterRaises(),
        target_connector=connector,
        source_rows=[{"A": 1}, {"A": 2}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # passthrough error → batch fallback
    assert outcome.strategy_used == "batch"
    assert "passthrough" in outcome.fallback_reason.lower()
    assert connector.batch_calls == 1


def test_selector_retries_passthrough_on_linked_runtime_failure():
    """linked runtime error → retry with passthrough."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorLinkedRuntimeFailsPassthroughWorks:
        def __init__(self):
            self.passthrough_called = False

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked runtime failed")

        def get_odbc_connection_string(self) -> str:
            self.passthrough_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

    class _FakeAdapterWithExecuteRaw:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 3

    connector = _FakeConnectorLinkedRuntimeFailsPassthroughWorks()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapterWithExecuteRaw(),
        target_connector=connector,
        source_rows=[{"A": 1}, {"A": 2}, {"A": 3}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # linked runtime error → passthrough
    assert outcome.strategy_used == "passthrough"
    assert "linked" in outcome.fallback_reason.lower()


def test_selector_skips_passthrough_when_not_in_capabilities():
    """Passthrough is skipped when connector does not advertise it."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorNoPassthrough:
        def __init__(self):
            self.batch_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=False,
                supports_checksum=True,
                supports_sampling=True,
            )

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.batch_calls += 1
            return len(rows)

    connector = _FakeConnectorNoPassthrough()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}]),
        target_connector=connector,
        source_rows=[{"A": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # passthrough not in capabilities → goes directly to batch
    assert outcome.strategy_used == "batch"
    assert connector.batch_calls == 1


def test_selector_passthrough_only_when_connector_has_it():
    """Passthrough is only attempted when connector advertises supports_passthrough_insert_select=True."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorNotAdvertised:
        def __init__(self):
            self.get_odbc_called = False
            self.batch_calls = 0

        def get_capabilities(self) -> ConnectorCapabilities:
            # Note: supports_passthrough_insert_select is NOT set to True
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            self.get_odbc_called = True
            return "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            self.batch_calls += 1
            return len(rows)

    connector = _FakeConnectorNotAdvertised()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}]),
        target_connector=connector,
        source_rows=[{"A": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # Even though get_odbc_connection_string exists, selector should not call it
    # because capabilities don't advertise supports_passthrough_insert_select=True
    assert outcome.strategy_used == "batch"
    assert connector.get_odbc_called is False


def test_selector_passthrough_when_connector_does_not_have_get_odbc_method():
    """Selector skips passthrough gracefully when connector has no get_odbc_connection_string."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorNoGetODBC:
        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            return len(rows)

    connector = _FakeConnectorNoGetODBC()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}]),
        target_connector=connector,
        source_rows=[{"A": 1}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # No get_odbc_connection_string → skip passthrough, use batch
    assert outcome.strategy_used == "batch"


def test_passthrough_strategy_with_all_options():
    """Passthrough with columns, WHERE, and ORDER BY builds complete SQL."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterCaptureSQL:
        def __init__(self):
            self.sql_executed: list[str] = []

        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            self.sql_executed.append(sql)
            return 4

    class _FakeConnectorFull:
        def __init__(self):
            self.odbc_str = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_str

    adapter = _FakeAdapterCaptureSQL()
    connector = _FakeConnectorFull()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="Orders",
        source_adapter=adapter,
        target_connector=connector,
        source_rows=[{"OrderID": 1}],
        columns=["OrderID", "CustomerID", "Total"],
        where_clause="CustomerID > 100",
        order_by_columns=["CustomerID", "OrderID"],
    )

    result = strategy.execute(context)

    sql = adapter.sql_executed[0]
    assert "SELECT [OrderID], [CustomerID], [Total] FROM [Orders]" in sql
    assert "WHERE CustomerID > 100" in sql
    assert "ORDER BY [CustomerID], [OrderID]" in sql


def test_passthrough_strategy_execute_returns_correct_rows_transferred():
    """PassthroughTransferStrategy.execute returns rows_transferred from execute_raw_sql."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeAdapterReturnsRows:
        def __init__(self, rows_affected: int):
            self._rows_affected = rows_affected

        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return self._rows_affected

    class _FakeConnectorValid:
        def __init__(self):
            self.odbc_str = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_str

    for expected_rows in [0, 1, 50, 100]:
        adapter = _FakeAdapterReturnsRows(expected_rows)
        connector = _FakeConnectorValid()
        strategy = PassthroughTransferStrategy()

        context = TransferContext(
            table_name="T",
            source_adapter=adapter,
            target_connector=connector,
            source_rows=[{"A": 1}],
            columns=None,
            where_clause=None,
            order_by_columns=None,
        )

        result = strategy.execute(context)
        assert result.rows_transferred == expected_rows, f"Expected {expected_rows}, got {result.rows_transferred}"


def test_selector_passthrough_fallback_all_conditions():
    """Full chain: linked fails → passthrough fails → batch succeeds."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorAllFallbacks:
        def __init__(self):
            self.final_result = 99

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=True,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def linked_transfer(self, source_adapter, source_table: str, target_table: str) -> int:
            raise RuntimeError("linked preflight failed")

        def get_odbc_connection_string(self) -> str:
            raise RuntimeError("DSN parse error")

        def insert_rows(self, table: str, rows: list[dict]) -> int:
            return self.final_result

    connector = _FakeConnectorAllFallbacks()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}, {"A": 2}]),
        target_connector=connector,
        source_rows=[{"A": 1}, {"A": 2}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert "linked" in outcome.fallback_reason.lower()
    assert outcome.rows_transferred == 99


def test_passthrough_strategy_can_run_false_for_empty_rows():
    """PassthroughTransferStrategy.can_run returns False when source_rows is empty."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeConnectorValid:
        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

    connector = _FakeConnectorValid()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([]),
        target_connector=connector,
        source_rows=[],  # empty
        columns=None,
        where_clause=None,
        order_by_columns=None,
    )

    # Empty source rows → passthrough can't run (no data to transfer)
    assert strategy.can_run(context) is False


def test_passthrough_strategy_can_run_false_without_connector_get_odbc():
    """PassthroughTransferStrategy.can_run returns False when connector lacks get_odbc_connection_string."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeConnectorNoODBC:
        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

    connector = _FakeConnectorNoODBC()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}]),
        target_connector=connector,
        source_rows=[{"A": 1}],
        columns=None,
        where_clause=None,
        order_by_columns=None,
    )

    assert strategy.can_run(context) is False


def test_passthrough_strategy_can_run_true_full_conditions():
    """PassthroughTransferStrategy.can_run returns True when all conditions are met."""
    from ms_access_mcp.services.transfer_strategy import PassthroughTransferStrategy

    class _FakeConnectorFull:
        def __init__(self):
            self.odbc_str = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def get_capabilities(self) -> ConnectorCapabilities:
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_str

    connector = _FakeConnectorFull()
    strategy = PassthroughTransferStrategy()

    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapter([{"A": 1}]),
        target_connector=connector,
        source_rows=[{"A": 1}],
        columns=None,
        where_clause=None,
        order_by_columns=None,
    )

    assert strategy.can_run(context) is True


# ─────────────────────────────────────────────────────────────────────────────
# TransferStrategySelector.execute_raw_sql passthrough path (Migrates from batch)
# ─────────────────────────────────────────────────────────────────────────────

def test_migration_service_execute_raw_sql_passthrough_path():
    """MigrationService.execute_raw_sql delegates to adapter's execute_raw_sql for passthrough."""
    from ms_access_mcp.services.migration import MigrationService
    from ms_access_mcp.models.migration import ExtractedSchema, TableSchema, ColumnSchema
    from ms_access_mcp.models.database import TableInfo, FieldInfo

    class _FakeAdapterWithExecuteRaw:
        def __init__(self):
            self.execute_raw_sql_calls: list[str] = []

        def get_table_schema_plan(self):
            tables = [
                TableSchema(name="Customers", columns=[
                    ColumnSchema(name="ID", source_type="Long Integer", allow_null=False),
                ])
            ]
            return (tables, None)

        def get_tables(self):
            fields = [FieldInfo(name="ID", type="Long Integer", size=4, required=True, allow_zero_length=False)]
            return [TableInfo(name="Customers", fields=fields, record_count=0)]

        def get_queries(self):
            return []

        def execute_raw_sql(self, sql: str) -> int:
            self.execute_raw_sql_calls.append(sql)
            return 5

    class _FakeConnectorWithPassthrough:
        def __init__(self):
            self.odbc_str = "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p"

        def connect(self, conn_str):
            return True

        def is_connected(self):
            return True

        def disconnect(self):
            pass

        def get_capabilities(self):
            from ms_access_mcp.connectors.base import ConnectorCapabilities
            return ConnectorCapabilities(
                supports_linked_insert_select=False,
                supports_passthrough_insert_select=True,
                supports_checksum=True,
                supports_sampling=True,
            )

        def get_odbc_connection_string(self) -> str:
            return self.odbc_str

    adapter = _FakeAdapterWithExecuteRaw()
    connector = _FakeConnectorWithPassthrough()
    svc = MigrationService()

    # Call execute_raw_sql on the service (passthrough path)
    sql = "INSERT INTO [ODBC;DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=test;UID=u;PWD=p].[Customers] SELECT [ID] FROM [Customers]"
    result = svc.execute_raw_sql(sql, adapter)

    assert result["success"] is True
    assert result["rows_affected"] == 5
    assert len(adapter.execute_raw_sql_calls) == 1
    assert adapter.execute_raw_sql_calls[0] == sql


def test_migration_service_execute_raw_sql_not_implemented():
    """MigrationService.execute_raw_sql returns error when adapter lacks the method."""
    from ms_access_mcp.services.migration import MigrationService

    class _FakeAdapterNoExecuteRaw:
        def get_table_schema_plan(self):
            return ([], None)

    adapter = _FakeAdapterNoExecuteRaw()
    svc = MigrationService()

    result = svc.execute_raw_sql("SELECT 1", adapter)

    assert result["success"] is False
    assert "execute_raw_sql" in result["error"]


def test_migration_service_execute_raw_sql_empty_sql():
    """MigrationService.execute_raw_sql returns error for empty SQL."""
    from ms_access_mcp.services.migration import MigrationService

    class _FakeAdapterWithExecuteRaw:
        def execute_raw_sql(self, sql: str) -> int:
            return 0

    adapter = _FakeAdapterWithExecuteRaw()
    svc = MigrationService()

    result = svc.execute_raw_sql("", adapter)

    assert result["success"] is False
    assert "empty" in result["error"].lower()


def test_migration_service_execute_raw_sql_via_passthrough():
    """MigrationService.execute_raw_sql calls adapter.execute_raw_sql for passthrough."""
    from ms_access_mcp.services.migration import MigrationService

    class _FakeAdapterCaptureSql:
        def __init__(self):
            self.sql_calls: list[str] = []

        def get_table_schema_plan(self):
            return ([], None)

        def execute_raw_sql(self, sql: str) -> int:
            self.sql_calls.append(sql)
            return 5

    adapter = _FakeAdapterCaptureSql()
    svc = MigrationService()

    passthrough_sql = (
        "INSERT INTO [ODBC;DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;"
        "DATABASE=test;UID=u;PWD=p].[T] SELECT [A] FROM [T]"
    )
    result = svc.execute_raw_sql(passthrough_sql, adapter)

    assert result["success"] is True
    assert result["rows_affected"] == 5
    assert adapter.sql_calls[0] == passthrough_sql


# ─────────────────────────────────────────────────────────────────────────────
# TransferStrategySelector — passthrough fallback verification
# ─────────────────────────────────────────────────────────────────────────────

def test_selector_passthrough_runtime_error_falls_to_batch():
    """Passthrough runtime error triggers batch fallback."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorPassthroughRuntimeError:
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

    class _FakeAdapterPassthroughError:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            raise RuntimeError("DAO execution error")

    connector = _FakeConnectorPassthroughRuntimeError()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapterPassthroughError(),
        target_connector=connector,
        source_rows=[{"A": 1}, {"A": 2}],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert "passthrough" in outcome.fallback_reason.lower()
    assert connector.batch_calls == 1


def test_selector_passthrough_zero_rows_still_success():
    """Passthrough returning 0 rows is still success (no retry to batch)."""
    from ms_access_mcp.services.transfer_strategy import TransferStrategySelector

    class _FakeConnectorPassthroughZero:
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

    class _FakeAdapterReturnsZero:
        def execute_query(self, sql, params=None):
            return {"success": True, "rows": [], "count": 0, "columns": []}

        def execute_raw_sql(self, sql: str) -> int:
            return 0

    connector = _FakeConnectorPassthroughZero()
    context = TransferContext(
        table_name="T",
        source_adapter=_FakeAdapterReturnsZero(),
        target_connector=connector,
        source_rows=[],
    )

    selector = TransferStrategySelector()
    outcome = selector.transfer(context)

    # 0 rows is still success — no need to fall to batch
    assert outcome.strategy_used == "passthrough"
    assert outcome.rows_transferred == 0
    assert connector.batch_calls == 0
