"""OpenAI-compatible provider facade — local mock for tests and illustration.

This module provides a ProviderFacade class that simulates OpenAI-compatible
responses WITHOUT importing the openai SDK. It is used for:
    1. Test fixtures that need predictable LLM responses
    2. Development without a live API key
    3. Contract tests verifying the LlmAdapter interface

No provider SDK imports — this is purely illustrative (LLMSPEC-11).
"""

from __future__ import annotations

from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse
from ms_access_mcp.config import LlmConfig


class ProviderFacade:
    """Simulated OpenAI-compatible provider facade for tests.

    This class satisfies the LlmAdapter protocol but returns hard-coded
    responses. It is NOT a real OpenAI implementation — it exists so tests
    and demos can run without network access or SDK credentials.
    """

    def __init__(
        self,
        model: str = "mock-gpt-4",
        capabilities: set[str] | None = None,
    ) -> None:
        self.model = model
        self._capabilities = capabilities or {"chat", "embeddings"}

    @classmethod
    def from_config(cls, cfg: LlmConfig) -> "ProviderFacade":
        """Build a facade from LlmConfig (no network call)."""
        return cls(model=cfg.model or "mock-gpt-4")

    def chat_completion(
        self,
        prompt: str,
        context: dict | None = None,
        timeout: float = 5.0,
    ) -> LlmResponse:
        """Return a predictable mock response."""
        prompt_lower = prompt.lower()
        if any(
            kw in prompt_lower
            for kw in (
                "intent",
                "disambiguate",
                "what",
                "which",
                "should",
                "show",
                "list",
                "tables",
                "find",
            )
        ):
            content = '{"intent": "query_tables", "confidence": 0.95}'
        elif "plan" in prompt_lower or "structured" in prompt_lower:
            content = '{"steps": [{"action": "list_tables", "target": "database"}]}'
        else:
            content = '{"content": "Mock response to: ' + prompt[:40] + '"}'
        return LlmResponse(content=content)

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic mock embedding vectors."""
        # Return a fixed-dimensional vector per text
        return [[0.01 * (i + 1) for i in range(10)] for _ in texts]

    @property
    def capabilities(self) -> set[str]:
        """Return supported capability set."""
        return self._capabilities