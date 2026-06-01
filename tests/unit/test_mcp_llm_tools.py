"""Tests for MCP AI tools — disambiguate_intent tool under LlmConfig.enabled.

These tests verify that:
1. When LlmConfig.enabled is False, the tool returns a structured DisabledError
   and does NOT call the LlmService.
2. When LlmConfig.enabled is True, the tool calls LlmService.disambiguate_intent
   and returns its structured result (dependency injection used).
"""

import pytest


class TestDisambiguateIntentToolDisabled:
    """ai.disambiguate_intent must not call LlmService when LlmConfig.enabled is False."""

    def test_disambiguate_intent_returns_disabled_error_when_not_enabled(self):
        """Tool returns a structured DisabledError dict when LlmConfig.enabled is False.

        The tool must NOT instantiate or call LlmService in this case.
        """
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse

        # Track whether LlmService was instantiated/called
        service_called = False

        class FakeAdapter:
            """Minimal LlmAdapter implementation for protocol check."""

            def chat_completion(self, prompt: str, context=None, timeout=5.0) -> LlmResponse:
                return LlmResponse(content='{"intent": "fake"}')

            def embeddings(self, texts: list[str]) -> list[list[float]]:
                return [[0.0] * 768]

            @property
            def capabilities(self) -> set[str]:
                return {"chat"}

        # Patch LlmService AND the config/service getters in the module
        import ms_access_mcp.mcp.ai_tools as ai_tools_module

        original_service_class = ai_tools_module.LlmService
        original_get_service = ai_tools_module._get_llm_service
        original_enabled_config = ai_tools_module._enabled_config

        class MockLlmService:
            """Mock that doesn't call real service — tracks instantiation."""

            def __init__(self, adapter: LlmAdapter):
                pass

            def disambiguate_intent(self, nl: str, context: dict | None = None) -> dict:
                nonlocal service_called
                service_called = True
                return {"intent": "mock_service_called"}

        def mock_get_service() -> MockLlmService:
            return MockLlmService(FakeAdapter())

        disabled_config = LlmConfig(enabled=False, provider="openai", model="gpt-4")

        def mock_enabled_config() -> LlmConfig:
            return disabled_config

        ai_tools_module.LlmService = MockLlmService  # type: ignore
        ai_tools_module._get_llm_service = mock_get_service  # type: ignore
        ai_tools_module._enabled_config = mock_enabled_config  # type: ignore

        # Reset cached globals so config is re-read
        ai_tools_module._llm_service = None
        ai_tools_module._llm_config = None

        try:
            from ms_access_mcp.mcp.ai_tools import disambiguate_intent

            result = disambiguate_intent(nl="show me tables", context=None)

            # Assertions
            assert isinstance(result, dict)
            assert result.get("disabled") is True or "error" in result, (
                f"Expected disabled error dict, got: {result}"
            )
            assert service_called is False, (
                "LlmService.disambiguate_intent was called even though LlmConfig.enabled=False"
            )
        finally:
            ai_tools_module.LlmService = original_service_class  # type: ignore
            ai_tools_module._get_llm_service = original_get_service  # type: ignore
            ai_tools_module._enabled_config = original_enabled_config  # type: ignore


class TestDisambiguateIntentToolEnabled:
    """ai.disambiguate_intent must call LlmService when LlmConfig.enabled is True."""

    def test_disambiguate_intent_calls_llm_service_and_returns_result(self):
        """When enabled=True, tool delegates to LlmService.disambiguate_intent.

        Uses dependency injection to pass a mock LlmService so no real network call occurs.
        """
        from ms_access_mcp.config import LlmConfig
        from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse

        class FakeAdapter:
            """Minimal LlmAdapter implementation."""

            def chat_completion(self, prompt: str, context=None, timeout=5.0) -> LlmResponse:
                return LlmResponse(content='{"intent": "list_tables", "target": "tables"}')

            def embeddings(self, texts: list[str]) -> list[list[float]]:
                return [[0.0] * 768]

            @property
            def capabilities(self) -> set[str]:
                return {"chat"}

        # Patch LlmService AND the config/service getters in the module
        import ms_access_mcp.mcp.ai_tools as ai_tools_module

        original_service_class = ai_tools_module.LlmService
        original_get_service = ai_tools_module._get_llm_service
        original_enabled_config = ai_tools_module._enabled_config

        service_calls: list[tuple[str, dict | None]] = []

        class MockLlmService:
            """Mock that records calls and returns deterministic structured output."""

            def __init__(self, adapter: LlmAdapter):
                pass

            def disambiguate_intent(self, nl: str, context: dict | None = None) -> dict:
                service_calls.append((nl, context))
                return {"intent": "list_tables", "target": "tables", "action": "display"}

        def mock_get_service() -> MockLlmService:
            return MockLlmService(FakeAdapter())

        enabled_config = LlmConfig(enabled=True, provider="openai", model="gpt-4")

        def mock_enabled_config() -> LlmConfig:
            return enabled_config

        ai_tools_module.LlmService = MockLlmService  # type: ignore
        ai_tools_module._get_llm_service = mock_get_service  # type: ignore
        ai_tools_module._enabled_config = mock_enabled_config  # type: ignore

        # Reset cached globals so config is re-read
        ai_tools_module._llm_service = None
        ai_tools_module._llm_config = None

        try:
            from ms_access_mcp.mcp.ai_tools import disambiguate_intent

            result = disambiguate_intent(nl="show me all tables", context={"db": "test.accdb"})

            # Assertions
            assert isinstance(result, dict), f"Expected dict, got: {type(result).__name__}"
            assert "intent" in result, f"Expected 'intent' in result, got: {result}"
            assert result.get("intent") == "list_tables"
            assert len(service_calls) == 1, f"Expected 1 service call, got: {len(service_calls)}"
            assert service_calls[0][0] == "show me all tables"
        finally:
            ai_tools_module.LlmService = original_service_class  # type: ignore
            ai_tools_module._get_llm_service = original_get_service  # type: ignore
            ai_tools_module._enabled_config = original_enabled_config  # type: ignore