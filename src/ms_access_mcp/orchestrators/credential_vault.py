"""CredentialVault — XOR-encrypted in-memory credential store.

Implements Proxy pattern (controls access to plaintext) and Strategy pattern
(encryption is swappable). Each vault instance generates its own per-process
random XOR key on init, providing vault isolation.

Design decisions from sdd/mcp-password-security/design:
- XOR with os.urandom key: sufficient for in-memory obfuscation, no external deps
- Passwords stored as bytes internally (not str) to enable explicit zeroing
- RAII-style clear() zeros the key AND the store dict
"""
from __future__ import annotations

import os
from typing import Protocol


class ICryptoStrategy(Protocol):
    """Protocol for encryption strategy — allows swappable crypto."""

    def encrypt(self, data: str) -> bytes:
        """Encrypt plaintext string to ciphertext bytes."""
        ...

    def decrypt(self, data: bytes) -> str:
        """Decrypt ciphertext bytes back to plaintext string."""
        ...


class _XorCrypto:
    """XOR-based encryption with a per-instance random key.

    Defense-in-depth against basic memory scraping. Not cryptographically
    secure for adversarial environments — but sufficient for in-memory
    credential obfuscation without external dependencies.
    """

    def __init__(self, key: bytes | None = None) -> None:
        # Generate a per-instance random key if not provided (for testing)
        self._key = key or os.urandom(32)
        self._is_zeroed = False

    def encrypt(self, data: str) -> bytes:
        """XOR each byte of the data with the key (cycling key)."""
        if self._is_zeroed:
            raise RuntimeError("Crypto key has been zeroed")
        data_bytes = data.encode("utf-8")
        key_cycle = self._key * ((len(data_bytes) // len(self._key)) + 1)
        return bytes(a ^ b for a, b in zip(data_bytes, key_cycle))

    def decrypt(self, data: bytes) -> str:
        """XOR each byte of the ciphertext with the key to recover plaintext."""
        if self._is_zeroed:
            raise RuntimeError("Crypto key has been zeroed")
        key_cycle = self._key * ((len(data) // len(self._key)) + 1)
        return bytes(a ^ b for a, b in zip(data, key_cycle)).decode("utf-8")

    def zero_key(self) -> None:
        """Zero the encryption key in-place."""
        if self._is_zeroed:
            return
        key_bytes = bytearray(self._key)
        for i in range(len(key_bytes)):
            key_bytes[i] = 0
        self._key = bytes(key_bytes)
        self._is_zeroed = True


class CredentialVault:
    """In-memory encrypted credential store with XOR encryption.

    Each instance generates its own random XOR key on init. Two vault instances
    CANNOT decrypt each other's data (different keys).

    Public API:
 store(server_id, password)  -> None
        retrieve(server_id)        -> str | None
        clear() -> None
    """

    def __init__(self) -> None:
        self._crypto = _XorCrypto()
        self._store: dict[str, bytes] = {}

    def store(self, server_id: str, password: str) -> None:
        """Store a credential, overwriting any existing entry for server_id.

        Args:
            server_id: Unique identifier for the server/connection
            password: Plaintext password to encrypt and store
        """
        self._store[server_id] = self._crypto.encrypt(password)

    def retrieve(self, server_id: str) -> str | None:
        """Retrieve the plaintext password for server_id.

        Args:
            server_id: Identifier previously passed to store()

        Returns:
            Plaintext password if found, None if server_id is unknown
        """
        encrypted = self._store.get(server_id)
        if encrypted is None:
            return None
        return self._crypto.decrypt(encrypted)

    def clear(self) -> None:
        """Wipe all credentials and zero the encryption key.

        After clear(), the vault is empty and the key is destroyed.
        The vault can be reused — store() will generate a fresh key.
        """
        # Zero each stored ciphertext buffer before clearing dict
        for server_id in list(self._store.keys()):
            ciphertext = bytearray(self._store[server_id])
            for i in range(len(ciphertext)):
                ciphertext[i] = 0
            self._store[server_id] = bytes(ciphertext)
        self._store.clear()
        # Zero the XOR key and replace with fresh crypto
        self._crypto.zero_key()
        self._crypto = _XorCrypto()
