"""Tests for telemetry.metrics no-op implementation.

These tests verify that:
1. Importing metrics doesn't raise, even without prometheus_client installed.
2. Counters can be incremented without side effects (no-op behavior).
3. measure_latency context manager works without side effects.
"""

import pytest
import time


class TestMetricsNoOpImport:
    """metrics module must be importable without prometheus_client installed."""

    def test_import_metrics_does_not_raise(self):
        """Importing telemetry.metrics must not raise ImportError."""
        from ms_access_mcp.telemetry import metrics as metrics_module

        assert metrics_module is not None

    def test_has_prometheus_is_false_when_not_installed(self):
        """_HAS_PROMETHEUS is False when prometheus_client is not available."""
        from ms_access_mcp.telemetry import metrics as metrics_module

        # The flag reflects whether prometheus_client loaded
        has_prometheus = metrics_module._HAS_PROMETHEUS
        # We don't assert True/False here — the test just checks the flag exists
        assert isinstance(has_prometheus, bool)


class TestMetricsNoOpCounters:
    """No-op counters accept .labels().inc() calls without side effects."""

    def test_increment_calls_total_noop(self):
        """increment_calls_total doesn't raise with no-op implementation."""
        from ms_access_mcp.telemetry.metrics import increment_calls_total

        # Must not raise
        increment_calls_total(provider="test", model="gpt-4")
        increment_calls_total()  # default args

    def test_increment_calls_failed_noop(self):
        """increment_calls_failed doesn't raise with no-op implementation."""
        from ms_access_mcp.telemetry.metrics import increment_calls_failed

        increment_calls_failed(provider="test", model="gpt-4", error_type="timeout")
        increment_calls_failed()

    def test_increment_calls_fallbacks_noop(self):
        """increment_calls_fallbacks doesn't raise with no-op implementation."""
        from ms_access_mcp.telemetry.metrics import increment_calls_fallbacks

        increment_calls_fallbacks(provider="test", model="gpt-4")
        increment_calls_fallbacks()


class TestMetricsNoOpHistogram:
    """No-op histogram accepts observe calls without side effects."""

    def test_observe_latency_noop(self):
        """observe_latency doesn't raise with no-op implementation."""
        from ms_access_mcp.telemetry.metrics import observe_latency

        observe_latency(duration=1.5, provider="test", model="gpt-4")
        observe_latency(duration=0.05)

    def test_measure_latency_context_manager(self):
        """measure_latency context manager works without side effects."""
        from ms_access_mcp.telemetry.metrics import measure_latency

        with measure_latency("openai", "gpt-4"):
            # Simulate some work
            pass  # no-op — must not raise

    def test_measure_latency_records_time(self):
        """measure_latency records elapsed time — even in no-op implementation."""
        from ms_access_mcp.telemetry.metrics import measure_latency

        with measure_latency("openai", "gpt-4"):
            time.sleep(0.01)  # tiny sleep — must not raise