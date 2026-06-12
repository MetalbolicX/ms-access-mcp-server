import math
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LlmConfig:
    """LLM adapter configuration — defaults to disabled for safety (LLMSPEC-01).

    All secrets (API keys) are referenced by environment variable name, never
    stored directly in config. The deterministic core is never impacted when
    LLM is disabled — all existing MCP tools remain fully functional.

    Attributes:
        enabled: Whether LLM features are active. Default False (safe default).
        provider: LLM provider name (e.g. "openai", "anthropic"). None = unset.
        api_key_env_name: Name of the env var holding the API key.
        base_url: Base URL for the LLM API endpoint. None = provider default.
        model: Model name to request (e.g. "gpt-4"). None = provider default.
        temperature: Sampling temperature; 0.0 = deterministic. Default 0.0.
        timeout_seconds: Request timeout in seconds. Default 5.
        allowlist: List of approved model names. Empty = all allowed (when enabled).
        redact_rules: List of regex patterns for pre-flight redaction.
        telemetry_enabled: Whether to write per-request audit logs. Default False.
    """

    enabled: bool = False
    provider: str | None = None
    api_key_env_name: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float = 0.0
    timeout_seconds: int = 5
    allowlist: list[str] = field(default_factory=list)
    redact_rules: list[str] = field(default_factory=list)
    telemetry_enabled: bool = False


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy in bits/character for a string."""
    if not s:
        return 0.0
    freq: dict[str, float] = {}
    for char in s:
        freq[char] = freq.get(char, 0.0) + 1.0
    entropy = 0.0
    length = len(s)
    for count in freq.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


class ServerConfig:
    """Load and validate server configuration from environment variables.

    Environment variables (all optional except ACCESS_MCP_API_KEY):
        ACCESS_MCP_API_KEY   -- Required. Bearer token for HTTP auth.
                                Must be at least 32 characters with sufficient entropy.
        ACCESS_MCP_HOST     -- Bind address. Default: 127.0.0.1
        ACCESS_MCP_PORT     -- Bind port. Default: 8000
        ACCESS_MCP_ALLOWED_DIRS -- Semicolon-separated directory whitelist.
                                  Default: user home directory.
    """

    MIN_KEY_LENGTH = 32
    MIN_ENTROPY = 3.0  # bits per character

    def __init__(self):
        api_key = os.environ.get("ACCESS_MCP_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ACCESS_MCP_API_KEY environment variable is required. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        # Validate key length
        if len(api_key) < self.MIN_KEY_LENGTH:
            raise ValueError(
                f"API key must be at least {self.MIN_KEY_LENGTH} characters. "
                f"Current length: {len(api_key)}. "
                "Generate a suitable key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        # Validate key entropy
        entropy = _shannon_entropy(api_key)
        if entropy < self.MIN_ENTROPY:
            raise ValueError(
                f"API key has insufficient entropy ({entropy:.2f} bits/char). "
                f"Minimum required: {self.MIN_ENTROPY} bits/char. "
                "Use a high-entropy random key generator."
            )

        self.api_key = api_key
        self.host = os.environ.get("ACCESS_MCP_HOST", "127.0.0.1")
        self.port = int(os.environ.get("ACCESS_MCP_PORT", "8000"))

        allowed_dirs_raw = os.environ.get("ACCESS_MCP_ALLOWED_DIRS", "")
        if allowed_dirs_raw:
            self.allowed_dirs = [
                d.strip() for d in allowed_dirs_raw.split(";") if d.strip()
            ]
        else:
            self.allowed_dirs = [str(Path.home())]

        # Trusted Locations preservation (opt-in, Windows only)
        # When True, captures registry Trusted Locations before and restores after VBA-modifying operations.
        self.preserve_trusted_locations = os.environ.get(
            "ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", "false"
        ).lower() in ("true", "1", "yes")

        # Session management
        self.session_secret = os.environ.get("ACCESS_MCP_SESSION_SECRET", "")
        self.session_cookie_name = os.environ.get("ACCESS_MCP_SESSION_COOKIE_NAME", "mcp_session")
        self.session_max_age = int(os.environ.get("ACCESS_MCP_SESSION_MAX_AGE", "3600"))

        # Read-only mode
        self.readonly = os.environ.get("ACCESS_MCP_READONLY", "false").lower() in ("true", "1", "yes")

        # Rate limiting
        self.rate_limit_max_attempts = int(os.environ.get("ACCESS_MCP_RATE_LIMIT_MAX_ATTEMPTS", "5"))
        self.rate_limit_window_seconds = int(os.environ.get("ACCESS_MCP_RATE_LIMIT_WINDOW_SECONDS", "60"))

    def is_path_allowed(self, path: str) -> bool:
        """Check if a database path is within an allowed directory.

        Rejects UNC paths and path traversal attempts.
        """
        if path.startswith("\\\\") or path.startswith("//"):
            return False

        try:
            abs_path = Path(path).resolve()
            for allowed in self.allowed_dirs:
                allowed_resolved = Path(allowed).resolve()
                abs_path.relative_to(allowed_resolved)
                return True
        except ValueError:
            pass
        return False

    def validate_path(self, path: str) -> str:
        """Validate path and return absolute path, or raise ValueError."""
        if not self.is_path_allowed(path):
            raise ValueError(
                f"Database path not allowed: {path}. "
                f"Allowed directories: {self.allowed_dirs}"
            )
        return str(Path(path).resolve())