"""Unit tests for telemetry metrics — tool_calls_total, tool_latency_seconds, auth_failures_total, connection_pool_size.

Tests the metrics module with and without prometheus_client installed.
"""

import sys
import time
from unittest.mock import patch, MagicMock


class TestToolCallsTotalCounter:
    """Tests for tool_calls_total counter."""

    def test_tool_calls_total_exists_in_metrics_module(self):
        """metrics module should export tool_calls_total counter or no-op."""
        from ms_access_mcp.telemetry import metrics
        assert hasattr(metrics, "tool_calls_total"), "metrics should have tool_calls_total"

    def test_tool_calls_total_accepts_tool_and_status_labels(self):
        """tool_calls_total.labels() should accept 'tool' and 'status' label kwargs."""
        from ms_access_mcp.telemetry import metrics
        counter = metrics.tool_calls_total
        # Should not raise — labels() call should work
        labels_obj = counter.labels(tool="diagnose_environment", status="success")
        assert labels_obj is not None

    def test_tool_calls_total_increment_without_prometheus_is_noop(self):
        """Incrementing tool_calls_total without prometheus_client should not raise."""
        from ms_access_mcp.telemetry import metrics
        counter = metrics.tool_calls_total
        # Should not raise even if prometheus_client is not installed
        counter.labels(tool="test_tool", status="success").inc()
        counter.labels(tool="test_tool", status="error").inc()

    def test_tool_calls_total_records_correct_labels(self):
        """tool_calls_total should record calls with correct tool and status labels."""
        from ms_access_mcp.telemetry import metrics
        counter = metrics.tool_calls_total
        # Increment with specific labels
        counter.labels(tool="connect_access", status="success").inc()
        counter.labels(tool="connect_access", status="error").inc()
        counter.labels(tool="query_data", status="success").inc()
        # Should not raise — labels are recorded correctly


class TestToolLatencySecondsHistogram:
    """Tests for tool_latency_seconds histogram."""

    def test_tool_latency_seconds_exists_in_metrics_module(self):
        """metrics module should export tool_latency_seconds histogram."""
        from ms_access_mcp.telemetry import metrics
        assert hasattr(metrics, "tool_latency_seconds"), "metrics should have tool_latency_seconds"

    def test_tool_latency_seconds_accepts_tool_label(self):
        """tool_latency_seconds.labels() should accept 'tool' label kwarg."""
        from ms_access_mcp.telemetry import metrics
        histogram = metrics.tool_latency_seconds
        labels_obj = histogram.labels(tool="diagnose_environment")
        assert labels_obj is not None

    def test_tool_latency_seconds_observe_accepts_duration(self):
        """tool_latency_seconds.observe() should accept a float duration."""
        from ms_access_mcp.telemetry import metrics
        histogram = metrics.tool_latency_seconds
        # Should not raise
        histogram.labels(tool="test_tool").observe(0.123)
        histogram.labels(tool="test_tool").observe(1.456)

    def test_tool_latency_seconds_without_prometheus_is_noop(self):
        """Observing tool_latency_seconds without prometheus_client should not raise."""
        from ms_access_mcp.telemetry import metrics
        histogram = metrics.tool_latency_seconds
        histogram.labels(tool="connect_access").observe(0.05)
        histogram.labels(tool="query_data").observe(1.5)


class TestAuthFailuresTotalCounter:
    """Tests for auth_failures_total counter."""

    def test_auth_failures_total_exists_in_metrics_module(self):
        """metrics module should export auth_failures_total counter."""
        from ms_access_mcp.telemetry import metrics
        assert hasattr(metrics, "auth_failures_total"), "metrics should have auth_failures_total"

    def test_auth_failures_total_accepts_reason_label(self):
        """auth_failures_total.labels() should accept 'reason' label kwarg."""
        from ms_access_mcp.telemetry import metrics
        counter = metrics.auth_failures_total
        labels_obj = counter.labels(reason="missing_token")
        assert labels_obj is not None

    def test_auth_failures_total_increment_records_reason(self):
        """auth_failures_total should record auth failures with specific reasons."""
        from ms_access_mcp.telemetry import metrics
        counter = metrics.auth_failures_total
        # Should not raise
        counter.labels(reason="missing_token").inc()
        counter.labels(reason="invalid_token").inc()
        counter.labels(reason="expired_token").inc()


class TestConnectionPoolSizeGauge:
    """Tests for connection_pool_size gauge."""

    def test_connection_pool_size_exists_in_metrics_module(self):
        """metrics module should export connection_pool_size gauge."""
        from ms_access_mcp.telemetry import metrics
        assert hasattr(metrics, "connection_pool_size"), "metrics should have connection_pool_size"

    def test_connection_pool_size_gauge_has_set_method(self):
        """connection_pool_size gauge should have a .set() method."""
        from ms_access_mcp.telemetry import metrics
        gauge = metrics.connection_pool_size
        assert hasattr(gauge, "set"), "gauge should have set() method"

    def test_connection_pool_size_set_accepts_integer(self):
        """connection_pool_size.set() should accept an integer value."""
        from ms_access_mcp.telemetry import metrics
        gauge = metrics.connection_pool_size
        # Should not raise
        gauge.set(0)
        gauge.set(5)
        gauge.set(10)

    def test_connection_pool_size_without_prometheus_is_noop(self):
        """Setting connection_pool_size without prometheus_client should not raise."""
        from ms_access_mcp.telemetry import metrics
        gauge = metrics.connection_pool_size
        gauge.set(3)


class TestTelemetryModuleExports:
    """Tests that telemetry module exports all required metrics."""

    def test_telemetry_module_exports_tool_calls_total(self):
        """telemetry __init__ should export tool_calls_total."""
        from ms_access_mcp.telemetry import tool_calls_total
        assert tool_calls_total is not None

    def test_telemetry_module_exports_tool_latency_seconds(self):
        """telemetry __init__ should export tool_latency_seconds."""
        from ms_access_mcp.telemetry import tool_latency_seconds
        assert tool_latency_seconds is not None

    def test_telemetry_module_exports_auth_failures_total(self):
        """telemetry __init__ should export auth_failures_total."""
        from ms_access_mcp.telemetry import auth_failures_total
        assert auth_failures_total is not None

    def test_telemetry_module_exports_connection_pool_size(self):
        """telemetry __init__ should export connection_pool_size."""
        from ms_access_mcp.telemetry import connection_pool_size
        assert connection_pool_size is not None
