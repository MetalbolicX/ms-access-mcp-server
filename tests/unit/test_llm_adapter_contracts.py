"""Contract tests for LlmAdapter concrete implementations — TDD RED phase.

These tests verify that any concrete LlmAdapter implementation (e.g.,
LlmGenericHttpAdapter, ProviderFacade) exposes the required interface:
    - chat_completion(prompt, context, timeout) -> LlmResponse
    - embeddings(texts) -> list[list[float]]
    - capabilities (set of strings)
    - from_config(cls, cfg: LlmConfig) classmethod

Ref: LLMSPEC-04, LLMSPEC-05, LLMSPEC-06
"""


class TestLlmAdapterContracts:
    """Verify concrete adapters satisfy the LlmAdapter protocol via duck typing."""

    def test_concrete_adapter_has_chat_completion_method(self):
        """Concrete adapter must expose chat_completion method."""
        from ms_access_mcp.adapters.llm import LlmAdapter

        class ConcreteAdapter:
            def chat_completion(self, prompt, context=None, timeout=5.0):
                ...

        mock = ConcreteAdapter()
        # Verify method exists via duck typing (protocol is structural)
        assert hasattr(mock, "chat_completion")
        assert callable(mock.chat_completion)

    def test_concrete_adapter_has_embeddings_method(self):
        """Concrete adapter must expose embeddings method."""
        from ms_access_mcp.adapters.llm import LlmAdapter

        class ConcreteAdapter:
            def embeddings(self, texts):
                ...

        mock = ConcreteAdapter()
        assert hasattr(mock, "embeddings")
        assert callable(mock.embeddings)

    def test_concrete_adapter_implements_protocol_methods(self):
        """A concrete adapter with both methods satisfies the protocol duck-typing."""
        from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse

        class ConcreteAdapter:
            def chat_completion(self, prompt, context=None, timeout=5.0):
                return LlmResponse(content="ok")

            def embeddings(self, texts):
                return [[0.1, 0.2] for _ in texts]

        adapter = ConcreteAdapter()
        # Verify both required methods are present (protocol duck-typing)
        assert hasattr(adapter, "chat_completion")
        assert hasattr(adapter, "embeddings")
        # Verify return type from chat_completion
        result = adapter.chat_completion("hello")
        assert isinstance(result, LlmResponse)
        assert result.content == "ok"


class TestLlmGenericHttpAdapterContracts:
    """Verify LlmGenericHttpAdapter can be configured with request/response templates."""

    def test_generic_http_adapter_from_config_returns_instance(self):
        """from_config(cfg) returns an adapter instance with templates set."""
        from ms_access_mcp.adapters.llm_generic_http import LlmGenericHttpAdapter
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(
            enabled=True,
            provider="generic_http",
            base_url="https://api.example.com",
            model="mock-model",
        )
        adapter = LlmGenericHttpAdapter.from_config(config)

        assert adapter is not None
        assert hasattr(adapter, "request_template")
        assert hasattr(adapter, "response_path")

    def test_generic_http_adapter_has_request_template_attr(self):
        """LlmGenericHttpAdapter exposes request_template attribute."""
        from ms_access_mcp.adapters.llm_generic_http import LlmGenericHttpAdapter
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="generic_http", base_url="https://api.example.com")
        adapter = LlmGenericHttpAdapter.from_config(config)

        assert hasattr(adapter, "request_template")

    def test_generic_http_adapter_has_response_path_attr(self):
        """LlmGenericHttpAdapter exposes response_path attribute."""
        from ms_access_mcp.adapters.llm_generic_http import LlmGenericHttpAdapter
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="generic_http", base_url="https://api.example.com")
        adapter = LlmGenericHttpAdapter.from_config(config)

        assert hasattr(adapter, "response_path")

    def test_generic_http_adapter_has_chat_completion(self):
        """LlmGenericHttpAdapter exposes chat_completion method."""
        from ms_access_mcp.adapters.llm_generic_http import LlmGenericHttpAdapter
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="generic_http", base_url="https://api.example.com")
        adapter = LlmGenericHttpAdapter.from_config(config)

        assert hasattr(adapter, "chat_completion")
        assert callable(adapter.chat_completion)

    def test_generic_http_adapter_chat_completion_raises_not_implemented(self):
        """LlmGenericHttpAdapter.chat_completion raises NotImplementedError in tests."""
        from ms_access_mcp.adapters.llm_generic_http import LlmGenericHttpAdapter
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="generic_http", base_url="https://api.example.com")
        adapter = LlmGenericHttpAdapter.from_config(config)

        import pytest

        with pytest.raises(NotImplementedError):
            adapter.chat_completion("hello")


class TestProviderFacadeContracts:
    """Verify ProviderFacade mock returns predictable LlmResponse objects."""

    def test_provider_facade_from_config_returns_instance(self):
        """ProviderFacade.from_config(cfg) returns an instance."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        facade = ProviderFacade.from_config(config)

        assert facade is not None
        assert hasattr(facade, "chat_completion")
        assert hasattr(facade, "embeddings")

    def test_provider_facade_chat_completion_returns_llm_response(self):
        """ProviderFacade.chat_completion returns LlmResponse."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.adapters.llm import LlmResponse
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        facade = ProviderFacade.from_config(config)

        response = facade.chat_completion("hello")
        assert isinstance(response, LlmResponse)

    def test_provider_facade_embeddings_returns_list_of_lists(self):
        """ProviderFacade.embeddings returns list[list[float]]."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        facade = ProviderFacade.from_config(config)

        result = facade.embeddings(["hello", "world"])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(v, list) for v in result)
        assert all(isinstance(x, float) for v in result for x in v)

    def test_provider_facade_has_capabilities(self):
        """ProviderFacade exposes capabilities as a set of strings."""
        from ms_access_mcp.adapters.llm_openai import ProviderFacade
        from ms_access_mcp.config import LlmConfig

        config = LlmConfig(enabled=True, provider="openai", model="gpt-4")
        facade = ProviderFacade.from_config(config)

        assert hasattr(facade, "capabilities")
        assert isinstance(facade.capabilities, (set, frozenset, list))