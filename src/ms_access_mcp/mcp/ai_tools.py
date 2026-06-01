"""AI tools for MCP.

These tools are guarded by LlmConfig.enabled:
- When disabled, they return a structured DisabledError and do not call LlmService.
- When enabled, they delegate to LlmService and return its structured response.

No provider SDK imports — this lives in the deterministic core.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ms_access_mcp.config import LlmConfig
from ms_access_mcp.adapters.llm import LlmAdapter
from ms_access_mcp.services.llm_service import LlmService

if TYPE_CHECKING:
    from ms_access_mcp.adapters.llm_openai import ProviderFacade


# Global service instance — initialized lazily on first enabled call
_llm_service: LlmService | None = None
_llm_config: LlmConfig | None = None


def _get_llm_service() -> LlmService:
    """Lazily initialize or return the cached LlmService singleton."""
    global _llm_service, _llm_config

    if _llm_service is None:
        # Import here to avoid circular refs and keep core free of adapter imports at module load
        from ms_access_mcp.adapters.llm_openai import ProviderFacade

        if _llm_config is None:
            _llm_config = LlmConfig()  # reads env defaults

        adapter: LlmAdapter = ProviderFacade.from_config(_llm_config)
        _llm_service = LlmService(adapter=adapter)

    return _llm_service


def _disabled_response(reason: str = "llm_disabled") -> dict:
    """Return a structured disabled-error response."""
    return {
        "error": "LLM feature is disabled",
        "code": "LLM_DISABLED",
        "reason": reason,
        "disabled": True,
    }


def _enabled_config() -> LlmConfig:
    """Return current LlmConfig (lazily initialized from environment)."""
    global _llm_config
    if _llm_config is None:
        _llm_config = LlmConfig()
    return _llm_config


# ---------------------------------------------------------------------------
# Tool definitions — FastMCP namespace 'ai'
# ---------------------------------------------------------------------------


def disambiguate_intent(nl: str, context: dict | None = None) -> dict:
    """Translate a natural-language request into a structured intent.

    Guarded by LlmConfig.enabled — returns DisabledError if not enabled.
    When enabled, delegates to LlmService.disambiguate_intent.

    Args:
        nl: Natural-language prompt from the MCP client.
        context: Optional context dict (database name, user session, etc.).

    Returns:
        dict with at least one key from the LLM response.
        When disabled: ``{"error": "...", "code": "LLM_DISABLED", "disabled": True}``.
    """
    config = _enabled_config()

    if not config.enabled:
        return _disabled_response()

    service = _get_llm_service()
    return service.disambiguate_intent(nl=nl, context=context)


def generate_structured_plan(goal: str, schema: dict) -> dict:
    """Generate a structured plan for a given goal using the LLM.

    Guarded by LlmConfig.enabled — returns DisabledError if not enabled.
    When enabled, delegates to LlmService.generate_structured_plan.

    Args:
        goal: High-level goal description.
        schema: Expected output schema.

    Returns:
        dict representing the structured plan.
        When disabled: ``{"error": "...", "code": "LLM_DISABLED", "disabled": True}``.
    """
    config = _enabled_config()

    if not config.enabled:
        return _disabled_response()

    service = _get_llm_service()
    return service.generate_structured_plan(goal=goal, schema=schema)


# Re-export disambiguate_intent at module level for backward-compatible access
__all__ = ["disambiguate_intent", "generate_structured_plan"]