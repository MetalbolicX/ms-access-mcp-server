from ms_access_mcp.connectors.base import ConnectorCapabilities
from ms_access_mcp.services.transfer_strategy import TransferContext, TransferStrategySelector


class _FakeAdapter:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def execute_query(self, sql: str, params=None):
        _ = params
        return {"success": True, "rows": list(self.rows), "count": len(self.rows), "columns": []}


class _FakeConnector:
    def __init__(self, *, supports_linked: bool, linked_error: Exception | None = None):
        self._supports_linked = supports_linked
        self._linked_error = linked_error
        self.linked_calls = 0
        self.batch_calls = 0

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_linked_insert_select=self._supports_linked,
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


def test_selector_retries_once_with_batch_when_linked_runtime_fails():
    selector = TransferStrategySelector()
    connector = _FakeConnector(supports_linked=True, linked_error=RuntimeError("linked path failed"))
    context = TransferContext(
        table_name="Invoices",
        source_adapter=_FakeAdapter([{"InvoiceID": 11}]),
        target_connector=connector,
        source_rows=[{"InvoiceID": 11}],
    )

    outcome = selector.transfer(context)

    assert outcome.strategy_used == "batch"
    assert outcome.rows_transferred == 1
    assert outcome.fallback_reason == "linked runtime failed: linked path failed"
    assert connector.linked_calls == 1
    assert connector.batch_calls == 1
