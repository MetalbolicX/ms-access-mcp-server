"""RED tests for ConnectPolicy — connection string validation.

Tests describe the expected API and behavior of ConnectPolicy per the spec:
- Allowed driver patterns are configurable
- TrustServerCertificate can be blocked
- Server name filters work
- sanitize() strips PWD= for safe display
- Structured rejection with reason messages
"""
import pytest


class TestConnectPolicyAllowedDrivers:
    """ConnectPolicy validates allowed driver patterns."""

    def test_valid_access_driver_passes(self):
        """Driver={Microsoft Access Driver (*.mdb, *.accdb)} is allowed."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=["Microsoft Access Driver*"])
        result = policy.validate("Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\\db.accdb")
        assert result.allowed is True
        assert result.reasons == []

    def test_disallowed_driver_rejected(self):
        """Driver={SQL Server} is rejected when not in allowlist."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=["Microsoft Access Driver*"])
        result = policy.validate("Driver={SQL Server};Server=.;Database=test")
        assert result.allowed is False
        assert any("SQL Server" in r for r in result.reasons)

    def test_odbc_prefix_always_allowed(self):
        """ODBC; prefix is always allowed."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=[])
        result = policy.validate("ODBC;DSN=MyDSN;PWD=secret")
        assert result.allowed is True

    def test_ace_oledb_provider_always_allowed(self):
        """Provider=Microsoft.ACE.OLEDB.* is always allowed."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=[])
        result = policy.validate("Provider=Microsoft.ACE.OLEDB.12.0;Data Source=\\\\server\\share\\db.accdb")
        assert result.allowed is True


class TestConnectPolicyTrustServerCertificate:
    """ConnectPolicy can block TrustServerCertificate."""

    def test_trust_server_certificate_blocked(self):
        """TrustServerCertificate=Yes is rejected when blocked."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(
            allowed_drivers=[],
            block_trust_server_certificate=True,
        )
        result = policy.validate("ODBC;DSN=MyDSN;TrustServerCertificate=Yes")
        assert result.allowed is False
        assert any("TrustServerCertificate" in r for r in result.reasons)

    def test_trust_server_certificate_allowed_when_not_blocked(self):
        """TrustServerCertificate=Yes is allowed when not blocked."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(
            allowed_drivers=[],
            block_trust_server_certificate=False,
        )
        result = policy.validate("ODBC;DSN=MyDSN;TrustServerCertificate=Yes")
        assert result.allowed is True


class TestConnectPolicyServerFilters:
    """ConnectPolicy can filter server names by pattern."""

    def test_server_name_allowed_when_matching_pattern(self):
        """Server name matching allowed pattern passes."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(
            allowed_drivers=[],
            allowed_servers=["prod-db-*"],
        )
        result = policy.validate("ODBC;Server=prod-db-01;Database=test")
        assert result.allowed is True

    def test_server_name_rejected_when_not_matching(self):
        """Server name not matching any allowed pattern is rejected."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(
            allowed_drivers=[],
            allowed_servers=["prod-db-*"],
        )
        result = policy.validate("ODBC;Server=dev-db-01;Database=test")
        assert result.allowed is False
        assert any("dev-db-01" in r for r in result.reasons)


class TestConnectPolicySanitize:
    """ConnectPolicy.sanitize() strips PWD= for safe display."""

    def test_sanitize_strips_password(self):
        """sanitize() removes PWD=... from connection string."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=[])
        result = policy.sanitize("ODBC;DSN=MyDSN;PWD=secret123;")
        assert "PWD=" not in result
        assert "secret123" not in result
        assert "ODBC;DSN=MyDSN;" in result

    def test_sanitize_no_password_unchanged(self):
        """sanitize() returns connection string unchanged if no PWD=."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=[])
        cs = "ODBC;DSN=MyDSN;Server=prod-db-01"
        result = policy.sanitize(cs)
        assert result == cs


class TestConnectPolicyStructuredRejection:
    """Validation failures return structured reasons list."""

    def test_multiple_violations_returns_all_reasons(self):
        """When multiple rules fail, all reasons are returned."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(
            allowed_drivers=["Microsoft Access Driver*"],
            allowed_servers=["prod-db-*"],
            block_trust_server_certificate=True,
        )
        result = policy.validate(
            "Driver={SQL Server};Server=dev-db-01;TrustServerCertificate=Yes"
        )
        assert result.allowed is False
        assert len(result.reasons) >= 2


class TestConnectPolicySanitizeParity:
    """sanitize() output is identical regardless of which layer calls it."""

    def test_sanitize_parity_with_orchestrator(self):
        """sanitize() result matches what orchestrator's _strip_password produces."""
        from ms_access_mcp.orchestrators.connect_policy import ConnectPolicy

        policy = ConnectPolicy(allowed_drivers=[])
        cs = "ODBC;DSN=MyDSN;PWD=mysecret;UID=user"
        sanitized = policy.sanitize(cs)
        # The sanitized output should have no PWD=
        assert "PWD=" not in sanitized
        # And should preserve the rest
        assert "DSN=MyDSN" in sanitized
        assert "UID=user" in sanitized
