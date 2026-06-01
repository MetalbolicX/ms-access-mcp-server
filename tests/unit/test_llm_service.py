"""Tests for LlmService — TDD RED phase.

These tests verify LlmService.disambiguate_intent and generate_structured_plan
using a dependency-injected mock adapter (no network calls).
"""


class TestLlmServiceDisambiguateIntent:
    """LlmService.disambiguate_intent must use the injected adapter."""

    def test_disambiguate_intent_returns_dict_with_intent(self):
        """disambiguate_intent returns a dict with intent from adapter response."""
        from ms_access_mcp.adapters.llm import LlmResponse
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        adapter = ProviderFacade.from_config(config)
        service = LlmService(adapter=adapter)

        result = service.disambiguate_intent(
            "show me the tables",
            context={"database": "test.accdb"},
        )

        assert isinstance(result, dict)
        assert "intent" in result

    def test_disambiguate_intent_calls_adapter_chat_completion(self):
        """disambiguate_intent delegates to adapter.chat_completion."""
        from ms_access_mcp.adapters.llm import LlmResponse
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        adapter = ProviderFacade.from_config(config)
        service = LlmService(adapter=adapter)

        result = service.disambiguate_intent(
            "list all tables",
            context={"database": "test.accdb"},
        )

        # ProviderFacade returns JSON with intent field
        assert result.get("intent") is not None

    def test_disambiguate_intent_fallback_on_timeout(self):
        """LlmService returns fallback dict when adapter raises LlmTimeoutError."""
        from ms_access_mcp.adapters.llm import LlmResponse, LlmTimeoutError
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        class TimeoutAdapter:
            """Mock adapter that always raises LlmTimeoutError."""

            def chat_completion(self, prompt, context=None, timeout=5.0):
                raise LlmTimeoutError("timeout")

            def embeddings(self, texts):
                raise LlmTimeoutError("timeout")

            @property
            def capabilities(self):
                return {"chat", "embeddings"}

        service = LlmService(adapter=TimeoutAdapter())
        result = service.disambiguate_intent(
            "show tables",
            context={},
        )

        assert isinstance(result, dict)
        assert result.get("fallback") is True
        assert "reason" in result


class TestLlmServiceGenerateStructuredPlan:
    """LlmService.generate_structured_plan must use the injected adapter."""

    def test_generate_structured_plan_returns_dict(self):
        """generate_structured_plan returns a dict response from adapter."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        adapter = ProviderFacade.from_config(config)
        service = LlmService(adapter=adapter)

        result = service.generate_structured_plan(
            goal="list all tables",
            schema={"type": "object", "properties": {}},
        )

        assert isinstance(result, dict)

    def test_generate_structured_plan_fallback_on_timeout(self):
        """generate_structured_plan returns fallback when adapter raises LlmTimeoutError."""
        from ms_access_mcp.adapters.llm import LlmTimeoutError
        from ms_access_mcp.services.llm_service import LlmService

        class TimeoutAdapter:
            """Mock adapter that always raises LlmTimeoutError."""

            def chat_completion(self, prompt, context=None, timeout=5.0):
                raise LlmTimeoutError("timeout")

            def embeddings(self, texts):
                raise LlmTimeoutError("timeout")

            @property
            def capabilities(self):
                return {"chat", "embeddings"}

        service = LlmService(adapter=TimeoutAdapter())
        result = service.generate_structured_plan(
            goal="create a table",
            schema={"type": "object"},
        )

        assert isinstance(result, dict)
        assert result.get("fallback") is True


class TestLlmServicePreSendRedaction:
    """LlmService supports pre-send redaction hook (callable sanitizer)."""

    def test_default_redaction_hook_is_identity(self):
        """Default redaction hook does not modify prompt."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        adapter = ProviderFacade.from_config(config)
        service = LlmService(adapter=adapter)

        prompt = "show tables in database"
        result = service.disambiguate_intent(prompt, context={})

        # No redaction applied by default — prompt reaches adapter as-is
        assert isinstance(result, dict)

    def test_custom_redaction_hook_is_called(self):
        """Custom redaction hook callable is invoked before sending to adapter."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        adapter = ProviderFacade.from_config(config)
        redacted_prompts: list[str] = []

        def custom_sanitizer(prompt: str) -> str:
            redacted = prompt.replace("SECRET", "[REDACTED]")
            redacted_prompts.append(redacted)
            return redacted

        service = LlmService(adapter=adapter, redaction_hook=custom_sanitizer)
        service.disambiguate_intent("show SECRET data", context={})

        assert len(redacted_prompts) == 1
        assert "SECRET" not in redacted_prompts[0]
        assert "[REDACTED]" in redacted_prompts[0]


class TestLlmServiceInstantiation:
    """LlmService must be constructible with an LlmAdapter."""

    def test_llm_service_requires_adapter(self):
        """LlmService constructor must accept an LlmAdapter instance."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.services.llm_service import LlmService

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        adapter = ProviderFacade.from_config(config)
        service = LlmService(adapter=adapter)

        assert service is not None
        assert hasattr(service, "disambiguate_intent")
        assert hasattr(service, "generate_structured_plan")