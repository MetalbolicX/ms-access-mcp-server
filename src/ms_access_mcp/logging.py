"""Structured logging module for ms-access-mcp-server.

Provides:
- JSON-formatted log output via logging.dictConfig
- Correlation ID propagation via ContextVar (per-tool-call request context)
- Replaces bare print(file=sys.stderr) calls throughout the codebase
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any


# Correlation ID context variable — propagates through all log entries for a tool call
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context, or None if not set."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


class JsonFormatter(logging.Formatter):
    """JSON log formatter with correlation ID support and PWD redaction.

    Outputs one JSON object per log record with fields:
    timestamp, level, logger, correlation_id, tool_name, message, exc_info (optional)

    PWD=... values are redacted in the message field before logging to prevent
    credential exposure in log files.
    """

    # Regex to match PWD= followed by non-semicolon chars (with optional surrounding semicolons)
    _PWD_PATTERN = __import__("re").compile(r"PWD=[^;]*;?")

    def _sanitize_message(self, message: str) -> str:
        """Redact PWD=... from message string for safe logging.

        Replaces PWD=secret with PWD=***.
        """
        return self._PWD_PATTERN.sub("PWD=***", message)

    def format(self, record: logging.LogRecord) -> str:
        try:
            # Sanitize message to redact PWD= values
            sanitized_message = self._sanitize_message(record.getMessage())

            # Build the JSON-serializable dict
            log_entry: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": sanitized_message,
            }

            # Add correlation ID if set
            corr_id = correlation_id_var.get()
            if corr_id is not None:
                log_entry["correlation_id"] = corr_id

            # Add tool_name if present in record (set by tool caller)
            if hasattr(record, "tool_name"):
                log_entry["tool_name"] = record.tool_name  # type: ignore[attr-defined]

            # Add exception info if present
            if record.exc_info:
                log_entry["exc_info"] = self.formatException(record.exc_info)

            return json.dumps(log_entry)
        except Exception:
            # Fallback to plain text if JSON serialization fails
            return super().format(record)


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure the root logger for the application.

    Args:
        level: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, use JSON formatter; otherwise use standard formatter
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_output:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(log_level)

        logging.basicConfig(
            level=log_level,
            handlers=[handler],
            force=True,
        )
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            force=True,
        )

    # Ensure uncaught exceptions are logged
    logging.captureWarnings(True)


class LogContext:
    """Context manager for setting correlation ID within a block.

    Usage:
        with LogContext(tool_name="export_data", correlation_id="req-123"):
            logger.info("Starting export")
            # ... tool work ...
            logger.info("Export complete")
    """

    def __init__(
        self,
        correlation_id: str | None = None,
        tool_name: str | None = None,
    ):
        self.correlation_id = correlation_id
        self.tool_name = tool_name
        self._token: Any = None

    def __enter__(self) -> "LogContext":
        self._token = correlation_id_var.set(self.correlation_id)
        return self

    def __exit__(self, *args: Any) -> None:
        correlation_id_var.reset(self._token)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance configured with the application settings
    """
    return logging.getLogger(name)