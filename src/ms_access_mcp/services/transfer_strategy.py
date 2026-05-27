from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class TransferContext:
    table_name: str
    source_adapter: Any
    target_connector: Any
    source_rows: list[dict]
    allow_linked: bool = True


@dataclass
class TransferOutcome:
    strategy_used: str
    rows_transferred: int
    fallback_reason: str | None = None


class TransferStrategy(Protocol):
    name: str

    def can_run(self, context: TransferContext) -> bool: ...

    def execute(self, context: TransferContext) -> int: ...


class LinkedTransferStrategy:
    name = "linked"

    def can_run(self, context: TransferContext) -> bool:
        if not context.allow_linked:
            return False
        capabilities = context.target_connector.get_capabilities()
        if not capabilities.supports_linked_insert_select:
            return False
        return hasattr(context.target_connector, "linked_transfer")

    def execute(self, context: TransferContext) -> int:
        return int(
            context.target_connector.linked_transfer(
                source_adapter=context.source_adapter,
                source_table=context.table_name,
                target_table=context.table_name,
            )
        )


class BatchTransferStrategy:
    name = "batch"

    def can_run(self, context: TransferContext) -> bool:
        _ = context
        return True

    def execute(self, context: TransferContext) -> int:
        return int(context.target_connector.insert_rows(context.table_name, context.source_rows))


class TransferStrategySelector:
    def __init__(self):
        self._linked = LinkedTransferStrategy()
        self._batch = BatchTransferStrategy()

    def transfer(self, context: TransferContext) -> TransferOutcome:
        if self._linked.can_run(context):
            try:
                inserted = self._linked.execute(context)
                return TransferOutcome(strategy_used="linked", rows_transferred=inserted)
            except Exception as exc:
                inserted = self._batch.execute(context)
                return TransferOutcome(
                    strategy_used="batch",
                    rows_transferred=inserted,
                    fallback_reason=f"linked runtime failed: {exc}",
                )

        inserted = self._batch.execute(context)
        fallback_reason = "linked preflight failed" if context.allow_linked else None
        return TransferOutcome(
            strategy_used="batch",
            rows_transferred=inserted,
            fallback_reason=fallback_reason,
        )
