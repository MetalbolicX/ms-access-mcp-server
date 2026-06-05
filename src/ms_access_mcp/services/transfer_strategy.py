from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TransferContext:
    table_name: str
    source_adapter: Any
    target_connector: Any
    source_rows: list[dict]
    allow_linked: bool = True
    columns: list[str] | None = None
    where_clause: str | None = None
    order_by_columns: list[str] | None = None
    odbc_connection_string: str | None = None


@dataclass
class TransferOutcome:
    strategy_used: str
    rows_transferred: int
    fallback_reason: str | None = None
    duration_ms: float = 0.0


class TransferStrategy(Protocol):
    name: str

    def can_run(self, context: TransferContext) -> bool: ...

    def execute(self, context: TransferContext) -> TransferOutcome: ...


class LinkedTransferStrategy:
    name = "linked"

    def can_run(self, context: TransferContext) -> bool:
        if not context.allow_linked:
            return False
        capabilities = context.target_connector.get_capabilities()
        if not capabilities.supports_linked_insert_select:
            return False
        return hasattr(context.target_connector, "linked_transfer")

    def execute(self, context: TransferContext) -> TransferOutcome:
        import time
        start = time.perf_counter()
        inserted = context.target_connector.linked_transfer(
            source_adapter=context.source_adapter,
            source_table=context.table_name,
            target_table=context.table_name,
        )
        duration = (time.perf_counter() - start) * 1000
        return TransferOutcome(strategy_used="linked", rows_transferred=inserted, duration_ms=duration)


class PassthroughTransferStrategy:
    name = "passthrough"

    def can_run(self, context: TransferContext) -> bool:
        capabilities = context.target_connector.get_capabilities()
        if not capabilities.supports_passthrough_insert_select:
            return False
        # Need either the override string or the connector method
        if context.odbc_connection_string:
            return True
        if not hasattr(context.target_connector, "get_odbc_connection_string"):
            return False
        return True

    def execute(self, context: TransferContext) -> TransferOutcome:
        import time
        start = time.perf_counter()

        odbc_str = context.odbc_connection_string or context.target_connector.get_odbc_connection_string()
        select_clause = self._build_select(context)
        where_clause = f" WHERE {context.where_clause}" if context.where_clause else ""
        order_clause = self._build_order_by(context)

        sql = (
            f"INSERT INTO [ODBC;{odbc_str}].[{context.table_name}] "
            f"{select_clause} FROM [{context.table_name}]{where_clause}{order_clause}"
        )

        rows_affected = context.source_adapter.execute_raw_sql(sql)
        duration = (time.perf_counter() - start) * 1000
        return TransferOutcome(strategy_used="passthrough", rows_transferred=rows_affected, duration_ms=duration)

    def _build_select(self, context: TransferContext) -> str:
        if context.columns:
            cols = ", ".join(f"[{c}]" for c in context.columns)
            return f"SELECT {cols}"
        return "SELECT *"

    def _build_order_by(self, context: TransferContext) -> str:
        if context.order_by_columns:
            cols = ", ".join(f"[{c}]" for c in context.order_by_columns)
            return f" ORDER BY {cols}"
        return ""


class BatchTransferStrategy:
    name = "batch"

    def can_run(self, context: TransferContext) -> bool:
        _ = context
        return True

    def execute(self, context: TransferContext) -> TransferOutcome:
        import time
        start = time.perf_counter()
        inserted = context.target_connector.insert_rows(context.table_name, context.source_rows)
        duration = (time.perf_counter() - start) * 1000
        return TransferOutcome(strategy_used="batch", rows_transferred=inserted, duration_ms=duration)


class TransferStrategySelector:
    def __init__(self):
        self._linked = LinkedTransferStrategy()
        self._passthrough = PassthroughTransferStrategy()
        self._batch = BatchTransferStrategy()

    def transfer(self, context: TransferContext) -> TransferOutcome:
        # Phase 1: Try linked
        if self._linked.can_run(context):
            try:
                outcome = self._linked.execute(context)
                return outcome
            except Exception as exc:
                # Fall through to passthrough
                fallback_reason = f"linked runtime failed: {exc}"

                # Phase 2: Try passthrough
                if self._passthrough.can_run(context):
                    try:
                        outcome = self._passthrough.execute(context)
                        outcome.fallback_reason = fallback_reason
                        return outcome
                    except Exception:
                        # Fall through to batch
                        pass

                # Phase 3: Batch
                outcome = self._batch.execute(context)
                outcome.fallback_reason = fallback_reason
                return outcome

        # No linked support — try passthrough directly
        if self._passthrough.can_run(context):
            try:
                return self._passthrough.execute(context)
            except Exception as exc:
                outcome = self._batch.execute(context)
                outcome.fallback_reason = f"passthrough failed: {exc}"
                return outcome

        # Default to batch
        outcome = self._batch.execute(context)
        if context.allow_linked:
            outcome.fallback_reason = "linked preflight failed"
        return outcome
