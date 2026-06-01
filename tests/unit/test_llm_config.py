"""Tests for LlmConfig — TDD RED phase.

These tests assert the expected shape and defaults of LlmConfig.
"""


class TestLlmConfigDefaults:
    """LlmConfig must default to disabled (LLMSPEC-01)."""

    def test_llm_config_defaults_to_disabled(self):
        """LlmConfig().enabled must be False by default."""
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig()
        assert config.enabled is False

    def test_llm_config_has_expected_fields(self):
        """LlmConfig exposes all required fields from spec."""
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig()
        assert hasattr(config, "enabled")
        assert hasattr(config, "provider")
        assert hasattr(config, "api_key_env_name")
        assert hasattr(config, "base_url")
        assert hasattr(config, "model")
        assert hasattr(config, "temperature")
        assert hasattr(config, "timeout_seconds")
        assert hasattr(config, "allowlist")
        assert hasattr(config, "redact_rules")
        assert hasattr(config, "telemetry_enabled")

    def test_llm_config_defaults_are_spec_compliant(self):
        """LlmConfig defaults match SDD spec values."""
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig()
        assert config.enabled is False
        assert config.provider is None
        assert config.api_key_env_name is None
        assert config.base_url is None
        assert config.model is None
        assert config.temperature == 0.0
        assert config.timeout_seconds == 5
        assert config.allowlist == []
        assert config.redact_rules == []
        assert config.telemetry_enabled is False

    def test_llm_config_supports_env_var_api_key(self, monkeypatch):
        """api_key_env_name allows wiring to an env var name."""
        from ms_access_mcp.config import LlmConfig

        monkeypatch.setenv("MY_LLM_KEY", "secret-key-123")
        config = LlmConfig(api_key_env_name="MY_LLM_KEY")
        assert config.api_key_env_name == "MY_LLM_KEY"
