"""Telemetry package — metrics and observability."""

from ms_access_mcp.telemetry.metrics import (
    auth_failures_total,
    connection_pool_size,
    increment_calls_fallbacks,
    increment_calls_failed,
    increment_calls_total,
    measure_latency,
    observe_latency,
    tool_calls_total,
    tool_latency_seconds,
)

__all__ = [
    "auth_failures_total",
    "connection_pool_size",
    "increment_calls_fallbacks",
    "increment_calls_failed",
    "increment_calls_total",
    "measure_latency",
    "observe_latency",
    "tool_calls_total",
    "tool_latency_seconds",
]