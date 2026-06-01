"""LLM Service — orchestrates LLM interactions for the deterministic MCP core.

This service layer:
    - Accepts an LlmAdapter instance (dependency injection — no provider SDK)
    - Provides disambiguate_intent(nl, context) for natural language → structured intent
    - Provides generate_structured_plan(goal, schema) for plan generation
    - Handles LlmTimeoutError with a deterministic fallback response
    - Supports a pre-send redaction hook (callable) — default: identity

No provider SDK imports — this lives in the deterministic core (LLMSPEC-11).
"""

from __future__ import annotations

import time
from typing import Callable

from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse, LlmTimeoutError
from ms_access_mcp.config import LlmConfig
from ms_access_mcp.telemetry.metrics import (
    increment_calls_fallbacks,
    increment_calls_failed,
    increment_calls_total,
    measure_latency,
)


# Default redaction hook: identity (no-op)
def _identity_sanitizer(prompt: str) -> str:
    return prompt


class LlmService:
    """Orchestrates LLM calls via a pluggable LlmAdapter.

    Args:
        adapter: An LlmAdapter-compatible instance (e.g., ProviderFacade,
            LlmGenericHttpAdapter). The service never imports provider SDKs.
        redaction_hook: A callable(prompt: str) -> str applied before each
            LLM call. Default is identity (no redaction). Replace with a
            real redaction pipeline in production.
    """

    def __init__(
        self,
        adapter: LlmAdapter,
        redaction_hook: Callable[[str], str] | None = None,
    ) -> None:
        self._adapter = adapter
        self._redaction_hook = redaction_hook or _identity_sanitizer

    def disambiguate_intent(self, nl: str, context: dict | None = None) -> dict:
        """Translate a natural-language request into a structured intent dict.

        Args:
            nl: Natural-language prompt from the MCP client.
            context: Optional context dict (database name, user session, etc.).

        Returns:
            dict with at least one key from the LLM response.
            On timeout: ``{"fallback": True, "reason": "llm_timeout"}``.
        """
        provider = getattr(self._adapter, "provider_name", "unknown")
        model = getattr(self._adapter, "model_name", "unknown")

        redacted_prompt = self._redaction_hook(nl)
        with measure_latency(provider, model):
            increment_calls_total(provider, model)
            try:
                response = self._adapter.chat_completion(
                    prompt=redacted_prompt,
                    context=context,
                )
                return self._parse_response(response)
            except LlmTimeoutError:
                increment_calls_fallbacks(provider, model)
                return {"fallback": True, "reason": "llm_timeout"}
            except Exception:
                increment_calls_failed(provider, model, "provider_error")
                raise

    def generate_structured_plan(self, goal: str, schema: dict) -> dict:
        """Generate a structured plan for a given goal using the LLM.

        Args:
            goal: High-level goal description.
            schema: Expected output schema (passed to the LLM as context).

        Returns:
            dict representing the structured plan.
            On timeout: ``{"fallback": True, "reason": "llm_timeout"}``.
        """
        provider = getattr(self._adapter, "provider_name", "unknown")
        model = getattr(self._adapter, "model_name", "unknown")

        redacted_goal = self._redaction_hook(goal)
        with measure_latency(provider, model):
            increment_calls_total(provider, model)
            try:
                response = self._adapter.chat_completion(
                    prompt=f"Generate a structured plan for: {redacted_goal}\nSchema: {schema}",
                    context={"goal": goal, "schema": schema},
                )
                return self._parse_response(response)
            except LlmTimeoutError:
                increment_calls_fallbacks(provider, model)
                return {"fallback": True, "reason": "llm_timeout"}
            except Exception:
                increment_calls_failed(provider, model, "provider_error")
                raise

    @staticmethod
    def _parse_response(response: LlmResponse) -> dict:
        """Parse LlmResponse.content as JSON, falling back to raw content."""
        import json

        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"content": content}

    @property
    def capabilities(self) -> set[str]:
        """Delegate to the underlying adapter's capabilities."""
        adapter_capabilities = getattr(self._adapter, "capabilities", None)
        if callable(adapter_capabilities):
            return adapter_capabilities()
        if adapter_capabilities is not None:
            return adapter_capabilities
        return set()