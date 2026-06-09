"""RED tests for CredentialVault — XOR-encrypted in-memory credential store.

Tests describe the expected API and behavior of CredentialVault per the spec:
- store/retrieve credentials with XOR encryption
- overwrite existing entries
- unknown server_id returns None
- clear() wipes all credentials and zeros the encryption key
- Two vaults are isolated (different keys cannot decrypt each other)
"""
import pytest


class TestCredentialVaultStoreAndRetrieve:
    """store() and retrieve() work as a pair."""

    def test_retrieve_stored_credential_returns_original(self):
        """When a credential is stored, retrieve() returns the original value."""
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault = CredentialVault()
        vault.store("srv1", "secret123")
        result = vault.retrieve("srv1")
        assert result == "secret123"

    def test_retrieve_unknown_server_id_returns_none(self):
        """When server_id has no stored credential, retrieve() returns None."""
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault = CredentialVault()
        result = vault.retrieve("unknown-srv")
        assert result is None


class TestCredentialVaultOverwrite:
    """store() overwrites existing credentials for the same server_id."""

    def test_store_overwrites_existing_credential(self):
        """Storing a new password for the same server_id replaces the old one."""
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault = CredentialVault()
        vault.store("srv1", "old-password")
        vault.store("srv1", "new-password")
        result = vault.retrieve("srv1")
        assert result == "new-password"


class TestCredentialVaultClear:
    """clear() wipes all credentials and zeros the encryption key."""

    def test_clear_wipes_all_credentials(self):
        """After clear(), all retrieve() calls return None."""
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault = CredentialVault()
        vault.store("srv1", "secret1")
        vault.store("srv2", "secret2")
        vault.clear()
        assert vault.retrieve("srv1") is None
        assert vault.retrieve("srv2") is None

    def test_clear_zeros_the_encryption_key(self):
        """After clear(), the encryption key is destroyed.

        Isolation test: vault A stores before clear; vault B cannot read vault A's
        pre-clear data (proves key was zeroed and vault is empty).
        """
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault_a = CredentialVault()
        vault_a.store("srv1", "secret")
        vault_a.clear()
        # Vault A is now empty
        assert vault_a.retrieve("srv1") is None
        # Vault B (fresh instance) stores its own data
        vault_b = CredentialVault()
        vault_b.store("srv1", "different-secret")
        # Vault B cannot decrypt vault A's pre-clear data (different key + vault A empty)
        assert vault_b.retrieve("srv1") == "different-secret"
        # Vault A cannot decrypt vault B's data
        assert vault_a.retrieve("srv1") is None


class TestCredentialVaultIsolation:
    """Two separate vault instances cannot decrypt each other's data."""

    def test_two_vaults_are_isolated(self):
        """A credential stored in vault A cannot be retrieved from vault B."""
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault_a = CredentialVault()
        vault_b = CredentialVault()
        vault_a.store("srv1", "secret-from-a")
        result = vault_b.retrieve("srv1")
        assert result is None

    def test_different_server_ids_are_independent(self):
        """Credentials for different server_ids are stored independently."""
        from ms_access_mcp.orchestrators.credential_vault import CredentialVault

        vault = CredentialVault()
        vault.store("srv1", "password1")
        vault.store("srv2", "password2")
        assert vault.retrieve("srv1") == "password1"
        assert vault.retrieve("srv2") == "password2"
        # Clear one does not affect the other
        vault.store("srv1", "password1-updated")
        assert vault.retrieve("srv2") == "password2"
