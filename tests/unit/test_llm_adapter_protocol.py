"""Contract tests for LlmAdapter protocol — TDD RED phase.

These tests verify that the LlmAdapter Protocol is importable from
adapters.llm and defines the required methods (LLMSPEC-04, LLMSPEC-05, LLMSPEC-06).
"""


class TestLlmAdapterProtocolExists:
    """LlmAdapter Protocol must be importable and define required methods."""

    def test_llm_adapter_protocol_importable(self):
        """importing adapters.llm defines LlmAdapter."""
        from ms_access_mcp.adapters import llm

        assert hasattr(llm, "LlmAdapter")

    def test_llm_adapter_has_chat_completion_method(self):
        """LlmAdapter defines chat_completion method."""
        from ms_access_mcp.adapters import llm

        assert hasattr(llm.LlmAdapter, "chat_completion")

    def test_llm_adapter_has_embeddings_method(self):
        """LlmAdapter defines embeddings method."""
        from ms_access_mcp.adapters import llm

        assert hasattr(llm.LlmAdapter, "embeddings")

    def test_llm_response_dataclass_exists(self):
        """LlmResponse dataclass is exported."""
        from ms_access_mcp.adapters import llm

        assert hasattr(llm, "LlmResponse")

    def test_llm_error_classes_exist(self):
        """All required error classes are exported (LLMSPEC-14)."""
        from ms_access_mcp.adapters import llm

        assert hasattr(llm, "LlmTimeoutError")
        assert hasattr(llm, "LlmProviderError")
        assert hasattr(llm, "LlmRateLimitError")

    def test_llm_timeout_error_is_exception(self):
        """LlmTimeoutError extends Exception."""
        from ms_access_mcp.adapters import llm

        assert issubclass(llm.LlmTimeoutError, Exception)

    def test_llm_provider_error_is_exception(self):
        """LlmProviderError extends Exception."""
        from ms_access_mcp.adapters import llm

        assert issubclass(llm.LlmProviderError, Exception)

    def test_llm_rate_limit_error_is_exception(self):
        """LlmRateLimitError extends Exception."""
        from ms_access_mcp.adapters import llm

        assert issubclass(llm.LlmRateLimitError, Exception)

    def test_llm_response_has_content_field(self):
        """LlmResponse dataclass has a content field."""
        from ms_access_mcp.adapters import llm

        # LlmResponse should be a dataclass with content field
        assert hasattr(llm.LlmResponse, "__dataclass_fields__")
        assert "content" in llm.LlmResponse.__dataclass_fields__
