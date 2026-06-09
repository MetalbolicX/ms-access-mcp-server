"""ConnectPolicy — connection string validation with Specification pattern.

Implements composable validation rules per the password-security SDD:
- Allowed driver patterns (configurable)
- TrustServerCertificate blocking
- Server name filtering
- Canonical PWD= stripping via sanitize()

Design: Specification/Template Method pattern — rules are independently
testable, composable, and execute uniformly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ConnectPolicyResult:
    """Structured result of a connection string validation.

    Attributes:
        allowed: True if the connection string passes all rules.
        reasons: List of rejection reasons (empty if allowed).
                Each reason describes a specific rule violation.
    """
    allowed: bool
    reasons: list[str] = field(default_factory=list)


class ConnectPolicy:
    """Validates connection strings against configurable security rules.

    Always allows:
    - ODBC; prefix (any ODBC connection string)
    - Provider=Microsoft.ACE.OLEDB.* (any Access OLEDB provider)

    Configurable rules:
    - allowed_drivers: List of fnmatch-style patterns for permitted Driver= values
    - block_trust_server_certificate: Reject TrustServerCertificate=Yes
    - allowed_servers: List of fnmatch-style patterns for permitted Server= values

    Usage:
        policy = ConnectPolicy(
            allowed_drivers=["Microsoft Access Driver*", "SQL Server*"],
            block_trust_server_certificate=True,
            allowed_servers=["prod-db-*", "uk-prod-*"],
        )
        result = policy.validate("ODBC;DSN=MyDSN;TrustServerCertificate=Yes")
        # result.allowed == False, result.reasons == ["TrustServerCertificate blocked"]
    """

    # Patterns that are ALWAYS allowed regardless of allowed_drivers config
    _ALWAYS_ALLOWED_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"^ODBC;", re.IGNORECASE),
        re.compile(r"^Provider=Microsoft\.ACE\.OLEDB\.\d+", re.IGNORECASE),
    )

    def __init__(
        self,
        allowed_drivers: list[str] | None = None,
        block_trust_server_certificate: bool = False,
        allowed_servers: list[str] | None = None,
    ) -> None:
        """Initialize ConnectPolicy with configurable rules.

        Args:
            allowed_drivers: List of fnmatch patterns for allowed Driver= values.
                            Empty list means only always-allowed patterns pass.
            block_trust_server_certificate: If True, reject TrustServerCertificate=Yes.
            allowed_servers: List of fnmatch patterns for allowed Server= values.
                           Empty/None means all servers are allowed.
        """
        self._allowed_drivers = allowed_drivers or []
        self._block_trust_server_certificate = block_trust_server_certificate
        self._allowed_servers = allowed_servers or []
        # Pre-compile driver patterns for performance
        self._driver_patterns = [self._compile_pattern(p) for p in self._allowed_drivers]
        # Pre-compile server patterns
        self._server_patterns = [self._compile_pattern(p) for p in self._allowed_servers]

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern[str]:
        """Convert fnmatch-style pattern to compiled regex.

        Converts shell-style wildcards to regex:
        - '*' -> '.*'
        - '?' -> '.'
        - '.' -> '\\.'
        """
        regex = re.escape(pattern)
        regex = regex.replace(r"\*", ".*")
        regex = regex.replace(r"\?", ".")
        return re.compile(f"^{regex}$", re.IGNORECASE)

    def validate(self, connect_string: str) -> ConnectPolicyResult:
        """Validate a connection string against all configured rules.

        Args:
            connect_string: The connection string to validate.

        Returns:
            ConnectPolicyResult with allowed=True and empty reasons if all
            rules pass; otherwise allowed=False and reasons describing violations.
        """
        reasons: list[str] = []
        cs = connect_string.strip()

        # Rule 0: Always-allowed patterns (ODBC;, ACE OLEDB)
        # ODBC/ACE connections skip the driver allowlist check but still
        # undergo TrustServerCertificate and server filtering.
        is_always_allowed = any(p.match(cs) for p in self._ALWAYS_ALLOWED_PATTERNS)

        # Rule 1: Driver pattern allowlist — only for non-always-allowed providers.
        # When allowed_drivers is non-empty, the provider must match one of the patterns.
        # When allowed_drivers is empty, any non-ODBC/non-ACE provider is rejected
        # (no patterns exist to validate against).
        if not is_always_allowed:
            if self._driver_patterns:
                driver_match = re.search(r"Driver=\{([^}]+)\}", cs, re.IGNORECASE)
                if driver_match:
                    driver_value = driver_match.group(1)
                    matched = any(p.match(driver_value) for p in self._driver_patterns)
                    if not matched:
                        reasons.append(f"Driver not in allowlist: {driver_value}")
            else:
                # No driver patterns configured and not always-allowed → reject
                reasons.append("Provider not in allowlist")

        # Rule 2: TrustServerCertificate blocking — ALWAYS checked
        if self._block_trust_server_certificate:
            if re.search(r"TrustServerCertificate\s*=\s*Yes", cs, re.IGNORECASE):
                reasons.append("TrustServerCertificate=Yes is not allowed")

        # Rule 3: Server name filter — applies to all connection strings
        if self._server_patterns:
            server_match = re.search(r"Server=([^;]+)", cs, re.IGNORECASE)
            if server_match:
                server_value = server_match.group(1).strip()
                matched = any(p.match(server_value) for p in self._server_patterns)
                if not matched:
                    reasons.append(f"Server not in allowlist: {server_value}")

        allowed = len(reasons) == 0
        return ConnectPolicyResult(allowed=allowed, reasons=reasons)

    def sanitize(self, connect_string: str) -> str:
        """Strip PWD=... from connection string for safe display/logging.

        Removes the password portion to prevent credential exposure in
        logs, error messages, or any persisted output.

        Args:
            connect_string: Connection string that may contain PWD=...

        Returns:
            Connection string with PWD=... removed.
        """
        # Match PWD=... with optional trailing semicolon, but NOT the leading
        # semicolon (which is the field separator before PWD). This preserves
        # the structure: ODBC;DSN=MyDSN;PWD=secret; -> ODBC;DSN=MyDSN;
        return re.sub(r"PWD=[^;]*;?", "", connect_string)