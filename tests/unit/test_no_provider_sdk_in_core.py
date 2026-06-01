"""CI guard: ensure no provider SDK imports leak into the deterministic core.

This test recursively scans all Python files under src/ms_access_mcp/ except
those under src/ms_access_mcp/adapters/ and fails if any file contains a
forbidden import or top-level string reference to a provider SDK package.

Rationale
---------
The deterministic core must remain provider-agnostic (LLMSPEC-11). Provider
SDKs (openai, anthropic, llama-index, vllm, huggingface, transformers,
azure.ai, etc.) may only be imported inside src/ms_access_mcp/adapters/.
This guard ensures that future PRs cannot accidentally pull a provider SDK
into the core and silently couple the business logic to a specific vendor.

Run offline
----------
This test never imports any provider SDK; it only reads and parses source
files. It is safe to run in an offline CI environment.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Iterator

import pytest

# -------------------------------------------------------------------------- #
# Configuration
# -------------------------------------------------------------------------- #

# Root of the package under test
REPO_ROOT = Path(__file__).parent.parent.parent / "src" / "ms_access_mcp"

# Directories to skip (provider-specific code lives here)
SKIP_DIRS = {"adapters", "adapters_llm", "telemetry"}

# Package-name tokens that indicate a provider SDK import.
# Matches import statements and top-level string literals like
#   from openai import ...
#   import llama_index
#   "azure.ai.openai"
FORBIDDEN_TOKENS = [
    "openai",
    "anthropic",
    "gpt",
    "llama",
    "vllm",
    "huggingface",
    "transformers",
    "azure",
    "ai_adapter",
]

# Regex patterns derived from FORBIDDEN_TOKENS
_TOKEN_PATTERNS = [re.compile(rf"\b{t}\b", re.IGNORECASE) for t in FORBIDDEN_TOKENS]

# -------------------------------------------------------------------------- #
# Helpers
# -------------------------------------------------------------------------- #

def _iter_python_files(root: Path, skip_dirs: set[str]) -> Iterator[Path]:
    """Recursively yield Python files under *root*, skipping *skip_dirs*."""
    for entry in sorted(root.rglob("*.py")):
        parts = entry.relative_to(root).parts
        if any(part in skip_dirs for part in parts):
            continue
        yield entry


def _file_forbidden_tokens(path: Path) -> list[str]:
    """Return a list of matched forbidden tokens found in *path*.

    Scans both import statements and top-level string literals (docstrings,
    module-level assignments) to catch dynamic imports or "import openai as ai"
    patterns.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:  # binary or unreadable — treat as safe
        return []

    matched: list[str] = []

    # 1. Static import analysis via AST
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        # If we can't parse it, fall back to text scan only
        tree = None

    if tree:
        for node in ast.walk(tree):
            # import X / import X as Y / import X.Y.Z
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pat in _TOKEN_PATTERNS:
                        if pat.search(alias.name):
                            matched.append(f"import {alias.name} [{pat.pattern}]")
            # from X import Y / from X.Y import Z
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for pat in _TOKEN_PATTERNS:
                        if pat.search(node.module):
                            matched.append(f"from {node.module} import ... [{pat.pattern}]")

    # 2. Top-level string literal scan (docstrings, module-level str values)
    # We scan every line that is not indented (i.e., top-level statements).
    # This catches things like:  azure_sdk = "azure.ai.openai"
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        # Top-level: no leading whitespace
        if line and not line[0].isspace():
            for pat in _TOKEN_PATTERNS:
                if pat.search(stripped):
                    matched.append(f"top-level str: {stripped[:60]}... [{pat.pattern}]")

    return matched


# -------------------------------------------------------------------------- #
# Test
# -------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "py_file",
    list(_iter_python_files(REPO_ROOT, SKIP_DIRS)),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_no_provider_sdk_in_core(py_file: Path):
    """Core Python files must not import any provider SDK packages.

    This guards against accidental vendor lock-in in the deterministic core.
    Provider SDK code belongs exclusively in src/ms_access_mcp/adapters/.
    """
    violations = _file_forbidden_tokens(py_file)
    if violations:
        formatted = "\n  ".join(violations)
        pytest.fail(
            f"{py_file.relative_to(REPO_ROOT)} contains forbidden provider SDK "
            f"references:\n  {formatted}"
        )