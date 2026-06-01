"""LLM Adapter protocol and error types.

This module defines the provider-agnostic LLM interface used by the deterministic
core. It deliberately contains no provider SDK imports — those live in pluggable
adapters under src/ms_access_mcp/adapters/ only (LLMSPEC-11).

Protocol contract (LLMSPEC-04, LLMSPEC-05, LLMSPEC-06):
    - chat_completion(prompt, context, timeout) -> LlmResponse
    - embeddings(texts) -> list[list[float]]

Error hierarchy (LLMSPEC-14):
    - LlmTimeoutError     — request exceeded timeout
    - LlmProviderError     — provider returned an error or was unreachable
    - LlmRateLimitError   — provider throttling response
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class LlmResponse:
    """Structured response from an LLM chat completion.

    Attributes:
        content: The text content of the model's response.
    """

    content: str


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LlmTimeoutError(Exception):
    """Raised when an LLM request exceeds its configured timeout.

    Code: LLM_TIMEOUT
    """

    code: str = "LLM_TIMEOUT"

    def __init__(self, message: str = "LLM request timed out"):
        self.message = message
        super().__init__(message)


class LlmProviderError(Exception):
    """Raised when the LLM provider returns an error or is unreachable.

    Code: PROVIDER_UNAVAILABLE
    """

    code: str = "PROVIDER_UNAVAILABLE"

    def __init__(self, message: str = "LLM provider error"):
        self.message = message
        super().__init__(message)


class LlmRateLimitError(Exception):
    """Raised when the LLM provider signals a rate-limit or quota error.

    Code: RATE_LIMIT_EXCEEDED
    """

    code: str = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "LLM rate limit exceeded"):
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class LlmAdapter(Protocol):
    """Protocol for pluggable LLM adapter implementations.

    Any adapter (HTTP, OpenAI SDK, Anthropic SDK, etc.) must satisfy this
    protocol. The deterministic core depends only on this interface — never on
    a specific provider SDK (LLMSPEC-11).

    Methods are synchronous stubs here; concrete adapters implement them with
    actual I/O. This keeps the core free of async and network dependencies.
    """

    def chat_completion(
        self,
        prompt: str,
        context: dict | None = None,
        timeout: float = 5.0,
    ) -> LlmResponse:
        """Send a text prompt and return the model's reply.

        Args:
            prompt: The user-facing text prompt.
            context: Optional dict with additional call context (model name,
                temperature, etc.). Adapters may ignore unexpected keys.
            timeout: Maximum seconds to wait for the provider. Default 5.0.

        Returns:
            LlmResponse with the model's content string.

        Raises:
            LlmTimeoutError: When the request exceeds ``timeout``.
            LlmProviderError: When the provider returns a non-retryable error.
            LlmRateLimitError: When the provider signals throttling.
        """
        ...

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for one or more text strings.

        Args:
            texts: List of texts to embed. The adapter maps each input to
                exactly one output vector, preserving cardinality.

        Returns:
            list[list[float]]: Embedding vectors, one per input text.

        Raises:
            LlmProviderError: When the provider returns an error.
            LlmRateLimitError: When the provider signals throttling.
        """
        ...
