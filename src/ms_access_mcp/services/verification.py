from collections.abc import Callable
from typing import Any

from ..models.migration import VerificationResult, VerificationSignal


class VerificationService:
    """Runs deterministic count/checksum/sample verification for a migrated table."""

    def __init__(self, normalize_value: Callable[[Any], Any] | None = None):
        self._normalize_value = normalize_value or (lambda value: value)

    def verify_table(
        self,
        source_connector: Any,
        target_connector: Any,
        table: str,
        columns: list[str],
        *,
        sample_limit: int = 10,
        sample_offset: int = 0,
    ) -> VerificationResult:
        signals = [
            self._verify_count(source_connector, target_connector, table),
            self._verify_checksum(source_connector, target_connector, table, columns),
            self._verify_sample(
                source_connector,
                target_connector,
                table,
                columns,
                sample_limit=sample_limit,
                sample_offset=sample_offset,
            ),
        ]
        status = "passed" if all(signal.passed for signal in signals) else "failed"
        return VerificationResult(table=table, status=status, signals=signals)

    def _verify_count(self, source_connector: Any, target_connector: Any, table: str) -> VerificationSignal:
        source_count = int(source_connector.get_row_count(table))
        target_count = int(target_connector.get_row_count(table))
        passed = source_count == target_count
        return VerificationSignal(
            signal_type="count",
            passed=passed,
            expected=str(source_count),
            actual=str(target_count),
        )

    def _verify_checksum(
        self,
        source_connector: Any,
        target_connector: Any,
        table: str,
        columns: list[str],
    ) -> VerificationSignal:
        if not self._signal_supported(source_connector, target_connector, "supports_checksum"):
            return VerificationSignal(
                signal_type="checksum",
                passed=True,
                evidence={"skipped": "checksum unsupported"},
            )

        source_checksum = source_connector.get_checksum(table, columns)
        target_checksum = target_connector.get_checksum(table, columns)
        passed = source_checksum == target_checksum
        return VerificationSignal(
            signal_type="checksum",
            passed=passed,
            expected=source_checksum,
            actual=target_checksum,
        )

    def _verify_sample(
        self,
        source_connector: Any,
        target_connector: Any,
        table: str,
        columns: list[str],
        *,
        sample_limit: int,
        sample_offset: int,
    ) -> VerificationSignal:
        if not self._signal_supported(source_connector, target_connector, "supports_sampling"):
            return VerificationSignal(
                signal_type="sample",
                passed=True,
                evidence={"skipped": "sampling unsupported"},
            )

        source_rows = source_connector.sample_rows(table, columns, sample_limit, offset=sample_offset)
        target_rows = target_connector.sample_rows(table, columns, sample_limit, offset=sample_offset)
        normalized_source = [self._normalize_row(row) for row in source_rows]
        normalized_target = [self._normalize_row(row) for row in target_rows]

        mismatches: list[dict[str, Any]] = []
        max_rows = max(len(normalized_source), len(normalized_target))
        for idx in range(max_rows):
            expected = normalized_source[idx] if idx < len(normalized_source) else None
            actual = normalized_target[idx] if idx < len(normalized_target) else None
            if expected != actual:
                mismatches.append({"row_index": idx, "expected": expected, "actual": actual})

        return VerificationSignal(
            signal_type="sample",
            passed=len(mismatches) == 0,
            evidence={"mismatches": mismatches},
        )

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {column: self._normalize_value(value) for column, value in row.items()}

    @staticmethod
    def _signal_supported(source_connector: Any, target_connector: Any, capability_flag: str) -> bool:
        source_capabilities = source_connector.get_capabilities()
        target_capabilities = target_connector.get_capabilities()
        return bool(getattr(source_capabilities, capability_flag, False)) and bool(
            getattr(target_capabilities, capability_flag, False)
        )
