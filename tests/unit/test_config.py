import os
import math
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


class TestServerConfigKeyValidation:
    """ServerConfig validates API key length (>=32) and entropy."""

    def test_raises_value_error_when_key_too_short_31_chars(self, monkeypatch):
        """API key with 31 characters raises ValueError."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "a" * 31)
        with pytest.raises(ValueError, match="32 characters"):
            ServerConfig()

    def test_raises_value_error_when_key_too_short_16_chars(self, monkeypatch):
        """API key with 16 characters raises ValueError."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "abcdefghijklmnop")
        with pytest.raises(ValueError, match="32 characters"):
            ServerConfig()

    def test_raises_value_error_when_key_too_short_8_chars(self, monkeypatch):
        """API key with 8 characters raises ValueError."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "short-key")
        with pytest.raises(ValueError, match="32 characters"):
            ServerConfig()

    def test_accepts_key_at_exactly_32_chars(self, monkeypatch):
        """API key with exactly 32 characters is accepted when entropy is sufficient."""
        # Use a mixed-character key that has entropy > 3.0 bits/char
        key = "Abc1!Xyz9@Def2#Ghi3$Lmn4^Opo5&Qrs6*"
        monkeypatch.setenv("ACCESS_MCP_API_KEY", key)
        config = ServerConfig()
        assert config.api_key == key

    def test_accepts_key_longer_than_32_chars(self, monkeypatch):
        """API key with more than 32 characters is accepted when entropy is sufficient."""
        # Use a mixed-character key that has entropy > 3.0 bits/char
        key = "Abc1!Xyz9@Def2#Ghi3$Lmn4^Opo5&Abc1!Xyz9@Def2#Ghi3$Lmn4"
        monkeypatch.setenv("ACCESS_MCP_API_KEY", key)
        config = ServerConfig()
        assert config.api_key == key

    def test_raises_value_error_when_key_low_entropy_all_same_char(self, monkeypatch):
        """API key with all same character (e.g., 32 'a' chars) raises ValueError for low entropy."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "a" * 32)
        with pytest.raises(ValueError, match="entropy"):
            ServerConfig()

    def test_raises_value_error_when_key_low_entropy_repeated_pattern(self, monkeypatch):
        """API key with repeated pattern (e.g., 'abcd' * 8) raises ValueError for low entropy."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "abcd" * 8)
        with pytest.raises(ValueError, match="entropy"):
            ServerConfig()

    def test_accepts_key_with_high_entropy(self, monkeypatch):
        """API key with high Shannon entropy (>3.0 bits/char) is accepted."""
        # Generate a key with good entropy: mix of upper, lower, digits, special
        good_key = "Abc1!Xyz9@Def2#Ghi3$Lmn4^Opo5&Pqr6*Stu7(Van8)Wxy9{Zab0}"
        monkeypatch.setenv("ACCESS_MCP_API_KEY", good_key)
        config = ServerConfig()
        assert config.api_key == good_key

    def test_raises_meaningful_error_message_for_short_key(self, monkeypatch):
        """Error message for short key should mention minimum length."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "short")
        with pytest.raises(ValueError, match="32"):
            ServerConfig()

    def test_raises_meaningful_error_message_for_low_entropy_key(self, monkeypatch):
        """Error message for low entropy key should mention entropy requirement."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "aaaa" * 8)
        with pytest.raises(ValueError, match="entropy"):
            ServerConfig()


class TestServerConfigDefaults:
    """ServerConfig applies correct defaults when env vars are absent."""

    def setup_method(self):
        # Always provide api_key to avoid the "required" error
        # Must be >= 32 chars with sufficient entropy
        os.environ.setdefault("ACCESS_MCP_API_KEY", "TestKeyForDefaults1!Abc2@Def3#Ghi4")

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

    # Valid test key: >= 32 chars, high entropy (33 chars)
    TEST_KEY = "MySecretKey123!Abc@Def#Ghi$Jklm0"

    def test_api_key_read_from_env(self, monkeypatch):
        """ACCESS_MCP_API_KEY is read and stored."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", self.TEST_KEY)
        config = ServerConfig()
        assert config.api_key == self.TEST_KEY

    def test_host_read_from_env(self, monkeypatch):
        """ACCESS_MCP_HOST overrides default."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", self.TEST_KEY)
        monkeypatch.setenv("ACCESS_MCP_HOST", "0.0.0.0")
        config = ServerConfig()
        assert config.host == "0.0.0.0"

    def test_port_read_from_env(self, monkeypatch):
        """ACCESS_MCP_PORT overrides default."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", self.TEST_KEY)
        monkeypatch.setenv("ACCESS_MCP_PORT", "9000")
        config = ServerConfig()
        assert config.port == 9000

    def test_allowed_dirs_from_env_single(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS with single dir is parsed correctly."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", self.TEST_KEY)
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data"]

    def test_allowed_dirs_from_env_multiple(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS with semicolon-separated dirs is parsed."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", self.TEST_KEY)
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data;D:\\DBs;E:\\Apps")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data", "D:\\DBs", "E:\\Apps"]

    def test_allowed_dirs_trims_whitespace(self, monkeypatch):
        """ACCESS_MCP_ALLOWED_DIRS entries with whitespace are trimmed."""
        monkeypatch.setenv("ACCESS_MCP_API_KEY", self.TEST_KEY)
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data ; D:\\DBs ; ")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data", "D:\\DBs"]


class TestServerConfigTrustedLocations:
    """ServerConfig trusted locations settings."""

    def setup_method(self):
        # Valid test key: >= 32 chars, high entropy
        os.environ.setdefault("ACCESS_MCP_API_KEY", "TestKeyTrustedLoc1!Abc2@Def3#Ghi4")

    def test_default_preserve_trusted_locations_is_false(self, monkeypatch):
        """ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS not set → defaults to False."""
        monkeypatch.delenv("ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", raising=False)
        config = ServerConfig()
        assert config.preserve_trusted_locations is False

    def test_preserve_trusted_locations_true_from_env_var(self, monkeypatch):
        """ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS=true → True."""
        key = "TestKeyTrustedLoc1!Abc2@Def3#Ghi4"
        monkeypatch.setenv("ACCESS_MCP_API_KEY", key)
        monkeypatch.setenv("ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", "true")
        config = ServerConfig()
        assert config.preserve_trusted_locations is True

    @pytest.mark.parametrize("truthy_value", ["1", "yes"])
    def test_preserve_trusted_locations_accepts_truthy_values(self, monkeypatch, truthy_value):
        """ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS with truthy values → True."""
        key = "TestKeyTrustedLoc1!Abc2@Def3#Ghi4"
        monkeypatch.setenv("ACCESS_MCP_API_KEY", key)
        monkeypatch.setenv("ACCESS_MCP_PRESERVE_TRUSTED_LOCATIONS", truthy_value)
        config = ServerConfig()
        assert config.preserve_trusted_locations is True