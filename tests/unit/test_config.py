import os
import pytest
from ms_access_mcp.config import ServerConfig


class TestServerConfigNotConnected:
    """ServerConfig raises when ACCESS_MCP_API_KEY is not set."""

    def test_raises_value_error_when_api_key_missing(self, monkeypatch):
        """Missing ACCESS_MCP_API_KEY env var raises ValueError at construction."""
        monkeypatch.delenv("ACCESS_MCP_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ACCESS_MCP_API_KEY"):
            ServerConfig()

    def test_raises_value_error_when_api_key_empty(self, monkeypatch):
        """Empty ACCESS_MCP_API_KEY env var raises ValueError at construction."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "")
        with pytest.raises(ValueError, match="ACCESS_MCP_API_KEY"):
            ServerConfig()


class TestServerConfigDefaults:
    """ServerConfig applies correct defaults when env vars are absent."""

    def setup_method(self):
        # Always provide api_key to avoid the "required" error
        os.environ.setdefault("ACCESS_MCP_API_KEY", "test-key-for-defaults")

    def test_default_host_is_localhost(self, monkeypatch):
        """ACCESS_MCP_HOST not set → defaults to 127.0.0.1."""
        monkeypatch.delenv("ACCESS_MCP_HOST", raising=False)
        config = ServerConfig()
        assert config.host == "127.0.0.1"

    def test_default_port_is_8000(self, monkeypatch):
        """ACCESS_MCP_PORT not set → defaults to 8000."""
        monkeypatch.delenv("ACCESS_MCP_PORT", raising=False)
        config = ServerConfig()
        assert config.port == 8000

    def test_allowed_dirs_defaults_to_home(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS not set → defaults to user home directory."""
        monkeypatch.delenv("ACCESS_MCP_ALLOWED_DIRS", raising=False)
        config = ServerConfig()
        assert len(config.allowed_dirs) == 1
        assert str(config.allowed_dirs[0]).endswith(os.path.basename(os.path.expanduser("~")))


class TestServerConfigEnvOverrides:
    """ServerConfig reads from environment variables."""

    def test_api_key_read_from_env(self, monkeypatch):
        """ACCESS_MCP_API_KEY is read and stored."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "my-secret-key-123")
        config = ServerConfig()
        assert config.api_key == "my-secret-key-123"

    def test_host_read_from_env(self, monkeypatch):
        """ACCESS_MCP_HOST overrides default."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_HOST", "0.0.0.0")
        config = ServerConfig()
        assert config.host == "0.0.0.0"

    def test_port_read_from_env(self, monkeypatch):
        """ACCESS_MCP_PORT overrides default."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_PORT", "9000")
        config = ServerConfig()
        assert config.port == 9000

    def test_allowed_dirs_from_env_single(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS with single dir is parsed correctly."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data"]

    def test_allowed_dirs_from_env_multiple(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS with semicolon-separated dirs is parsed."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data;D:\\DBs;E:\\Apps")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data", "D:\\DBs", "E:\\Apps"]

    def test_allowed_dirs_trims_whitespace(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS entries with whitespace are trimmed."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data ; D:\\DBs ; ")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data", "D:\\DBs"]


class TestServerConfigTrustedLocations:
    """ServerConfig trusted locations settings."""

    def setup_method(self):
        os.environ.setdefault("ACCESS_MCP_API_KEY", "test-key")

    def test_default_preserve_trusted_locations_is_false(self, monkeypatch):
        """ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS not set → defaults to False."""
        monkeypatch.delenv("ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", raising=False)
        config = ServerConfig()
        assert config.preserve_trusted_locations is False

    def test_preserve_trusted_locations_true_from_env_var(self, monkeypatch):
        """ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS=true → True."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", "true")
        config = ServerConfig()
        assert config.preserve_trusted_locations is True

    @pytest.mark.parametrize("truthy_value", ["1", "yes"])
    def test_preserve_trusted_locations_accepts_truthy_values(self, monkeypatch, truthy_value):
        """ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS with truthy values → True."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", truthy_value)
        config = ServerConfig()
        assert config.preserve_trusted_locations is True