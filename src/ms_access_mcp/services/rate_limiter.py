"""In-memory IP-based rate limiter for login endpoint protection.

Enforces max_attempts within a sliding window. Tracks per-IP counters
with automatic expiration. Suitable for single-instance MCP servers.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _IPRecord:
    """Tracks attempt timestamps for a single IP address."""

    attempts: list[float] = field(default_factory=list)

    def add_attempt(self, timestamp: float) -> None:
        """Record an attempt at the given timestamp."""
        self.attempts.append(timestamp)

    def cleanup(self, cutoff: float) -> None:
        """Remove attempts older than cutoff timestamp."""
        self.attempts = [t for t in self.attempts if t > cutoff]


class RateLimiter:
    """In-memory rate limiter enforcing max_attempts per IP within a time window.

    Thread-safe via a lock protecting the IP records dictionary.

    Attributes:
        max_attempts: Maximum allowed attempts in the window. Default: 5.
        window_seconds: Size of the sliding window in seconds. Default: 60.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._lock = threading.RLock()
        self._records: dict[str, _IPRecord] = {}

    @property
    def max_attempts(self) -> int:
        """Return the max attempts limit."""
        return self._max_attempts

    @property
    def window_seconds(self) -> int:
        """Return the window size in seconds."""
        return self._window_seconds

    def check(self, ip_address: str) -> bool:
        """Check if an IP address is within its rate limit.

        Args:
            ip_address: The client IP address to check.

        Returns:
            True if the IP is allowed (under limit), False if rate limited.
        """
        with self._lock:
            now = time.time()
            cutoff = now - self._window_seconds

            record = self._records.get(ip_address)
            if record is None:
                record = _IPRecord()
                self._records[ip_address] = record

            # Cleanup old attempts
            record.cleanup(cutoff)

            # Check if over limit
            if len(record.attempts) >= self._max_attempts:
                return False

            # Record this attempt
            record.add_attempt(now)
            return True

    def get_retry_after(self, ip_address: str) -> int:
        """Get seconds until the oldest attempt expires (for Retry-After header).

        Args:
            ip_address: The client IP address.

        Returns:
            Seconds until the IP can retry, or 0 if not rate limited.
        """
        with self._lock:
            record = self._records.get(ip_address)
            if record is None or len(record.attempts) < self._max_attempts:
                return 0
            oldest = min(record.attempts)
            elapsed = time.time() - oldest
            remaining = self._window_seconds - elapsed
            return max(1, int(remaining))

    def reset(self, ip_address: Optional[str] = None) -> None:
        """Reset rate limit counters.

        Args:
            ip_address: If provided, reset only that IP. If None, reset all.
        """
        with self._lock:
            if ip_address is None:
                self._records.clear()
            elif ip_address in self._records:
                del self._records[ip_address]
