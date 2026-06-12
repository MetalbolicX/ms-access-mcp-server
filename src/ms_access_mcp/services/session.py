"""Session management service using itsdangerous for signed cookie sessions.

Provides secure httpOnly session cookies via itsdangerous Signer.
Used by SessionMiddleware to resolve API keys from browser sessions.
"""

from __future__ import annotations

import time
from typing import Optional

try:
    import itsdangerous
except ImportError:
    itsdangerous = None  # type: ignore[assignment]


class SessionService:
    """Manages signed session cookies for browser-based authentication.

    Uses itsdangerous.Signer with a secret key to create tamper-proof cookies
    that encode the API key. Cookies include a max-age timestamp.

    Attributes:
        secret_key: Secret key used for HMAC signing (from ACCESS_MCP_SESSION_SECRET).
        cookie_name: Name of the session cookie. Default: "mcp_session".
        max_age: Maximum cookie age in seconds. Default: 3600 (1 hour).
        salt: Salt used in signing. Default: "ms-access-mcp-session".
    """

    def __init__(
        self,
        secret_key: str,
        cookie_name: str = "mcp_session",
        max_age: int = 3600,
        salt: str = "ms-access-mcp-session",
    ):
        if itsdangerous is None:
            raise ImportError(
                "itsdangerous is required for session management. "
                "Install with: pip install itsdangerous"
            )
        self._secret_key = secret_key
        self._cookie_name = cookie_name
        self._max_age = max_age
        self._salt = salt
        self._signer = itsdangerous.Signer(secret_key, salt=salt)

    @property
    def cookie_name(self) -> str:
        """Return the session cookie name."""
        return self._cookie_name

    @property
    def max_age(self) -> int:
        """Return the session max age in seconds."""
        return self._max_age

    def sign(self, api_key: str) -> str:
        """Create a signed session cookie value for the given API key.

        Args:
            api_key: The API key to encode in the session cookie.

        Returns:
            A signed, timestamped cookie string suitable for Set-Cookie header.
        """
        timestamp = str(int(time.time()))
        # itsdangerous encodes as base64 by default
        signed = self._signer.sign(f"{api_key}|{timestamp}")
        return signed.decode("utf-8") if isinstance(signed, bytes) else signed

    def validate(self, cookie_value: str) -> Optional[str]:
        """Validate a session cookie and return the embedded API key.

        Args:
            cookie_value: The raw cookie value (from Cookie header).

        Returns:
            The API key if the cookie is valid and not expired, else None.
        """
        try:
            if not self._signer.validate(cookie_value):
                return None
            # Unsign to get the original payload
            unsigned = self._signer.unsign(cookie_value)
            if unsigned is None:
                return None
            payload = unsigned.decode("utf-8")
            parts = payload.rsplit("|", 1)
            if len(parts) != 2:
                return None
            api_key, timestamp_str = parts
            timestamp = int(timestamp_str)
            # Check max age
            if time.time() - timestamp > self._max_age:
                return None
            return api_key
        except Exception:
            return None

    def clear_cookie_params(self) -> dict:
        """Return dict of parameters for clearing the session cookie (Max-Age=0)."""
        return {
            "name": self._cookie_name,
            "max_age": 0,
            "httponly": True,
            "samesite": "Lax",
        }
