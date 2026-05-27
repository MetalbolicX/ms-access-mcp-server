from ms_access_mcp.services.verification import VerificationService


class _Capabilities:
    def __init__(self, *, supports_checksum: bool = True, supports_sampling: bool = True):
        self.supports_checksum = supports_checksum
        self.supports_sampling = supports_sampling


class _VerificationConnector:
    def __init__(self, *, count: int, checksum: str | None, sample_rows: list[dict]):
        self._count = count
        self._checksum = checksum
        self._sample_rows = sample_rows

    def get_capabilities(self):
        return _Capabilities()

    def get_row_count(self, table: str) -> int:
        _ = table
        return self._count

    def get_checksum(self, table: str, columns: list[str]) -> str | None:
        _ = table
        _ = columns
        return self._checksum

    def sample_rows(self, table: str, columns: list[str], limit: int, offset: int = 0) -> list[dict]:
        _ = table
        _ = columns
        return self._sample_rows[offset : offset + limit]


def test_verification_service_reports_pass_when_count_checksum_and_sample_match_with_normalization():
    source = _VerificationConnector(
        count=2,
        checksum="abc123",
        sample_rows=[{"ID": 1, "Name": "Alice "}, {"ID": 2, "Name": "Bob"}],
    )
    target = _VerificationConnector(
        count=2,
        checksum="abc123",
        sample_rows=[{"ID": "1", "Name": "Alice"}, {"ID": "2", "Name": "Bob"}],
    )

    service = VerificationService(normalize_value=lambda value: str(value).strip() if value is not None else None)
    result = service.verify_table(source, target, "Customers", ["ID", "Name"], sample_limit=2)

    assert result.status == "passed"
    signal_map = {signal.signal_type: signal for signal in result.signals}
    assert signal_map["count"].passed is True
    assert signal_map["checksum"].passed is True
    assert signal_map["sample"].passed is True


def test_verification_service_reports_structured_diffs_on_count_checksum_and_sample_mismatch():
    source = _VerificationConnector(
        count=3,
        checksum="source-hash",
        sample_rows=[{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Bob"}],
    )
    target = _VerificationConnector(
        count=2,
        checksum="target-hash",
        sample_rows=[{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Robert"}],
    )

    result = VerificationService().verify_table(source, target, "Customers", ["ID", "Name"], sample_limit=2)

    assert result.status == "failed"
    signal_map = {signal.signal_type: signal for signal in result.signals}

    count_signal = signal_map["count"]
    assert count_signal.passed is False
    assert count_signal.expected == "3"
    assert count_signal.actual == "2"

    checksum_signal = signal_map["checksum"]
    assert checksum_signal.passed is False
    assert checksum_signal.expected == "source-hash"
    assert checksum_signal.actual == "target-hash"

    sample_signal = signal_map["sample"]
    assert sample_signal.passed is False
    assert sample_signal.evidence["mismatches"] == [
        {
            "row_index": 1,
            "expected": {"ID": 2, "Name": "Bob"},
            "actual": {"ID": 2, "Name": "Robert"},
        }
    ]
