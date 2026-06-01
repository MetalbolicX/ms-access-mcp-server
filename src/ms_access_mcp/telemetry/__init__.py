"""Telemetry package — metrics and observability."""

from ms_access_mcp.telemetry.metrics import (
    increment_calls_fallbacks,
    increment_calls_failed,
    increment_calls_total,
    measure_latency,
    observe_latency,
)

__all__ = [
    "increment_calls_fallbacks",
    "increment_calls_failed",
    "increment_calls_total",
    "measure_latency",
    "observe_latency",
]