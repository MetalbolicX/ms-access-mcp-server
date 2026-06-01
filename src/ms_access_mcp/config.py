import os
from pathlib import Path


class ServerConfig:
    """Load and validate server configuration from environment variables.

    Environment variables (all optional except ACCESS_MCP_API_KEY):
        ACCESS_MCP_API_KEY   -- Required. Bearer token for HTTP auth.
        ACCESS_MCP_HOST     -- Bind address. Default: 127.0.0.1
        ACCESS_MCP_PORT     -- Bind port. Default: 8000
        ACCESS_MCP_ALLOWED_DIRS -- Semicolon-separated directory whitelist.
                                  Default: user home directory.
    """

    def __init__(self):
        api_key = os.environ.get("ACCESS_MCP_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ACCESS_MCP_API_KEY environment variable is required. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
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