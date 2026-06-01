"""Generic HTTP adapter for LLM providers — configurable via request/response templates.

This adapter allows any HTTP-based LLM API to be plugged in by providing:
    - request_template: JSON body template with placeholders
    - response_path: dot-notation path to extract content from response

No provider SDK imports — operates via generic HTTP only (LLMSPEC-11).
"""

from __future__ import annotations

from typing import Any

from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse, LlmTimeoutError
from ms_access_mcp.config import LlmConfig


class LlmGenericHttpAdapter:
    """Pluggable HTTP adapter for arbitrary LLM APIs.

    Configure via ``from_config(cfg)`` with ``request_template`` and
    ``response_path`` set on the returned instance.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        request_template: str | None = None,
        response_path: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.request_template = request_template
        self.response_path = response_path

    @classmethod
    def from_config(cls, cfg: LlmConfig) -> "LlmGenericHttpAdapter":
        """Build an adapter instance from LlmConfig (no network call)."""
        return cls(
            base_url=cfg.base_url,
            api_key=cfg.api_key_env_name,
            model=cfg.model,
            request_template=None,  # set via setter or env
            response_path=None,     # set via setter or env
        )

    def chat_completion(
        self,
        prompt: str,
        context: dict | None = None,
        timeout: float = 5.0,
    ) -> LlmResponse:
        """Raise NotImplementedError — actual HTTP call requires network I/O."""
        raise NotImplementedError(
            "LlmGenericHttpAdapter.chat_completion requires a real HTTP library "
            "and network I/O — use a mock in tests."
        )

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        """Raise NotImplementedError — actual HTTP call requires network I/O."""
        raise NotImplementedError(
            "LlmGenericHttpAdapter.embeddings requires a real HTTP library "
            "and network I/O — use a mock in tests."
        )

    def set_templates(self, request_template: str, response_path: str) -> None:
        """Set HTTP request/response templates after construction."""
        self.request_template = request_template
        self.response_path = response_path