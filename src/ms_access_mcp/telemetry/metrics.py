"""Minimal telemetry interface — no-op counters if prometheus_client absent.

Provides:
- Counter: llm.calls_total (increment on each LLM call)
- Counter: llm.calls_failed (increment on provider/timeout errors)
- Counter: llm.calls_fallbacks (increment on fallback responses)
- Histogram: llm.latency_seconds (record call latency)

When prometheus_client is not installed, all operations are no-ops (safe to call
everywhere without side effects).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from prometheus_client import Counter, Histogram

try:
    from prometheus_client import Counter, Histogram, REGISTRY  # noqa: F401

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

# ---------------------------------------------------------------------------
# Metric definitions — always valid, no-ops when prometheus_client absent
# ---------------------------------------------------------------------------

_llm_calls_total: "Counter | _NoOpCounter"
_llm_calls_failed: "Counter | _NoOpCounter"
_llm_calls_fallbacks: "Counter | _NoOpCounter"
_llm_latency_seconds: "Histogram | _NoOpHistogram"


class _NoOpLabels:
    """No-op that supports .labels() chaining and .inc()/.observe()."""

    def inc(self, amount: float = 1.0) -> None:
        pass

    def observe(self, amount: float) -> None:
        pass


class _NoOpCounter:
    """No-op counter that accepts .labels() and .inc() without side effects."""

    def labels(self, **kwargs: object) -> _NoOpLabels:
        return _NoOpLabels()

    def inc(self, amount: float = 1.0) -> None:
        pass


class _NoOpHistogram:
    """No-op histogram that accepts .labels() and .observe() without side effects."""

    def labels(self, **kwargs: object) -> _NoOpLabels:
        return _NoOpLabels()

    def observe(self, amount: float) -> None:
        pass


if _HAS_PROMETHEUS:
    _llm_calls_total = Counter(
        "llm_calls_total",
        "Total number of LLM API calls",
        ["provider", "model"],
    )
    _llm_calls_failed = Counter(
        "llm_calls_failed",
        "Total number of failed LLM API calls",
        ["provider", "model", "error_type"],
    )
    _llm_calls_fallbacks = Counter(
        "llm_calls_fallbacks",
        "Total number of LLM calls that returned fallback response",
        ["provider", "model"],
    )
    _llm_latency_seconds = Histogram(
        "llm_latency_seconds",
        "LLM API call latency in seconds",
        ["provider", "model"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
    )
else:
    _llm_calls_total = _NoOpCounter()
    _llm_calls_failed = _NoOpCounter()
    _llm_calls_fallbacks = _NoOpCounter()
    _llm_latency_seconds = _NoOpHistogram()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def increment_calls_total(provider: str = "unknown", model: str = "unknown") -> None:
    """Increment the total LLM calls counter."""
    _llm_calls_total.labels(provider=provider, model=model).inc()


def increment_calls_failed(
    provider: str = "unknown",
    model: str = "unknown",
    error_type: str = "unknown",
) -> None:
    """Increment the failed LLM calls counter."""
    _llm_calls_failed.labels(provider=provider, model=model, error_type=error_type).inc()


def increment_calls_fallbacks(provider: str = "unknown", model: str = "unknown") -> None:
    """Increment the fallback LLM calls counter."""
    _llm_calls_fallbacks.labels(provider=provider, model=model).inc()


def observe_latency(
    duration: float,
    provider: str = "unknown",
    model: str = "unknown",
) -> None:
    """Record LLM call latency in seconds."""
    _llm_latency_seconds.labels(provider=provider, model=model).observe(duration)


@contextmanager
def measure_latency(provider: str, model: str) -> Iterator[None]:
    """Context manager that records LLM call latency.

    Usage:
        with measure_latency("openai", "gpt-4"):
            llm_service.disambiguate_intent(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        observe_latency(time.perf_counter() - start, provider, model)