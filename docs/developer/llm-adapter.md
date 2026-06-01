# LLM Adapter — Developer Guide

This document covers how to work with the LLM adapter system in the MS Access MCP server.

## Overview

The LLM adapter provides a secure, deterministic bridge between the MCP server and external Language Models. Provider-specific SDKs are isolated into pluggable adapters so the core remains free of external network dependencies.

```
Client --> MCP Tools --> LlmService --> LlmAdapter (interface)
                                    |
                    +---------------+------------------+
                    |               |                  |
              LlmOpenAI       LlmGenericHttp     [future adapters]
```

## How to Add a Provider

### 1. Implement the `LlmAdapter` Protocol

Create a new file under `src/ms_access_mcp/adapters/`. The adapter must satisfy the `LlmAdapter` protocol:

```python
from ms_access_mcp.adapters.llm import LlmAdapter, LlmResponse, LlmTimeoutError

class LlmMyProvider:
    """MyProvider LLM adapter."""

    def __init__(self, config: LlmConfig) -> None:
        self.provider_name = "myprovider"  # used for telemetry
        self.model_name = config.model or "default"
        self._client = MyProviderSDK(api_key=os.environ[config.api_key_env_name])

    def chat_completion(
        self,
        prompt: str,
        context: dict | None = None,
        timeout: float = 5.0,
    ) -> LlmResponse:
        response = self._client.complete(prompt, timeout=timeout)
        return LlmResponse(content=response.text)

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed(texts)
```

### 2. Error Handling

Raise the appropriate exception from `ms_access_mcp.adapters.llm`:

| Condition | Exception |
|-----------|-----------|
| Request timeout | `LlmTimeoutError` |
| Provider unavailable | `LlmProviderError` |
| Rate limit hit | `LlmRateLimitError` |

### 3. Add Tests (Contract Tests)

Create `tests/unit/test_llm_myprovider_adapter.py`:

```python
from ms_access_mcp.adapters.llm import LlmAdapter

def test_myprovider_adapter_satisfies_protocol():
    """MyProvider adapter must satisfy LlmAdapter Protocol."""
    from ms_access_mcp.adapters.llm_myprovider import LlmMyProvider
    from ms_access_mcp.config import LlmConfig
    from ms_access_mcp.adapters.llm import LlmAdapter as Protocol

    # Verify structural compatibility
    adapter = LlmMyProvider(LlmConfig(provider="myprovider"))
    assert isinstance(adapter, Protocol)
```

### 4. Export from `adapters/__init__.py`

Add your adapter to the package exports so `LlmService` and other consumers can import it.

## Redaction Rules

All prompts are passed through a redaction hook before being sent to the LLM. The default hook is identity (no redaction). To add custom rules:

```python
from ms_access_mcp.services.llm_service import LlmService

def custom_sanitizer(prompt: str) -> str:
    # Remove patterns matching database secrets
    import re
    return re.sub(r'SECRET_KEY_\w+', '[REDACTED]', prompt)

service = LlmService(adapter=my_adapter, redaction_hook=custom_sanitizer)
```

## Configuration

`LlmConfig` (in `src/ms_access_mcp/config.py`) is the single configuration entry point:

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `False` | Must be `True` to activate LLM tools |
| `provider` | `None` | Provider name (e.g., `"openai"`) |
| `api_key_env_name` | `None` | Env var name holding the API key |
| `base_url` | `None` | Override provider's default endpoint |
| `model` | `None` | Model name (e.g., `"gpt-4"`) |
| `temperature` | `0.0` | Sampling temperature (0 = deterministic) |
| `timeout_seconds` | `5` | Request timeout |
| `allowlist` | `[]` | Approved model names (empty = all allowed) |
| `redact_rules` | `[]` | Regex patterns for pre-flight redaction |
| `telemetry_enabled` | `False` | Enable per-request audit logging |

**Important**: API keys are NEVER stored in config — always reference an environment variable name.

## Running Tests

LLM-related tests are in `tests/unit/` and follow a naming pattern:

```
test_llm_config.py          — LlmConfig defaults and validation
test_llm_adapter_protocol.py — Protocol compliance tests
test_llm_adapter_contracts.py — Adapter contract validation
test_llm_service.py         — LlmService behavior tests
test_mcp_llm_tools.py       — MCP tool guard behavior
test_metrics_noop.py        — Telemetry no-op behavior
```

Run all LLM tests:

```bash
pytest tests/unit/test_llm*.py tests/unit/test_mcp_llm_tools.py tests/unit/test_metrics_noop.py -v
```

Run all tests (including CI guard):

```bash
pytest -q
```

## CI Guard (Provider SDK Isolation)

The core `src/ms_access_mcp/` must NEVER import provider SDKs (OpenAI, Anthropic, etc.). A test at `tests/unit/test_no_provider_sdk_in_core.py` enforces this. If a core file imports any of:

- `openai`
- `anthropic`
- `google.generativeai`
- `cohere`
- `ollama`

...the test fails. All provider SDKs live exclusively in `src/ms_access_mcp/adapters/`.

## Telemetry

Metrics are in `src/ms_access_mcp/telemetry/metrics.py`. They work even without `prometheus_client` installed (no-op implementation). The following counters are available:

| Metric | Labels | Description |
|--------|--------|-------------|
| `llm_calls_total` | provider, model | Every LLM API call |
| `llm_calls_failed` | provider, model, error_type | Failed calls |
| `llm_calls_fallbacks` | provider, model | Fallback responses |
| `llm_latency_seconds` | provider, model | Call latency histogram |

Usage:

```python
from ms_access_mcp.telemetry.metrics import measure_latency, increment_calls_failed

with measure_latency("openai", "gpt-4"):
    result = llm_service.disambiguate_intent("show tables")
```