"""Tests for PWD redaction in logging output.

Verifies that JsonFormatter and log helpers sanitize PWD= from connection strings
before writing to log output.
"""
import pytest
import logging
from unittest.mock import MagicMock, patch

from ms_access_mcp.logging import JsonFormatter, configure_logging, get_logger


class TestJsonFormatterPasswordRedaction:
    """JsonFormatter should redact PWD= from log messages."""

    def test_format_redacts_password_from_message(self):
        """When record.msg contains PWD=, the formatted output should not include the password."""
        formatter = JsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Connection string: ODBC;DSN=MyDSN;PWD=secret123;",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        # Password should not appear in the formatted output
        assert "secret123" not in formatted
        assert "PWD=secret123" not in formatted
        # DSN should still be present
        assert "MyDSN" in formatted

    def test_format_redacts_pwd_value_from_message(self):
        """PWD= value should be redacted regardless of format (PWD=val or PWD=val;)."""
        formatter = JsonFormatter()

        # Test with PWD= without trailing semicolon
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="connect_string=PWD=mysecret",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "mysecret" not in formatted
        assert "PWD=mysecret" not in formatted

    def test_format_preserves_non_password_content(self):
        """Non-password content should be preserved in log output."""
        formatter = JsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Processing table Orders for server prod-db-01",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "Orders" in formatted
        assert "prod-db-01" in formatted

    def test_format_no_password_unchanged(self):
        """Log message without PWD= should be unchanged."""
        formatter = JsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Starting operation",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "Starting operation" in formatted


class TestLoggingConfiguration:
    """configure_logging should set up logging that redacts PWD."""

    def test_configure_logging_produces_redacted_output(self):
        """After configure_logging, logger output should not contain passwords."""
        # Capture log output
        import io
        import sys

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_logger("test_pwd")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            logger.info("ODBC;DSN=MyDSN;PWD=secret123;")
            output = stream.getvalue()
            assert "secret123" not in output
            assert "PWD=" not in output or "***" in output
            assert "MyDSN" in output
        finally:
            logger.removeHandler(handler)
            handler.close()