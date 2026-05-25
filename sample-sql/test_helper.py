#!/usr/bin/env python3
"""
Shared HTTP JSON-RPC helpers for MS Access MCP integration tests.

Extracted from test-all-tools.py. All test files import from this module
to avoid duplicating HTTP helper logic and shared configuration.
"""

import subprocess
import json
import sys
import os
from datetime import datetime

# ==============================================================================
# Configuration
# ==============================================================================

# Use env vars for flexible overrides; sensible defaults for local dev
BASE_URL = os.environ.get("MCP_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("MCP_API_KEY", "test-key-123")
DB_PATH = os.environ.get("MCP_DB_PATH", "D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb")
EXPORT_DIR = "C:/Users/MetalbolicX/tool-test-export"
MCP_PATH = "/mcp"
MCP_TIMEOUT = 120  # seconds — some operations (compact, copy 516MB DB) take 60s+
RESULTS_FILE = "sample-sql/test-all-tools-results.md"

# ANSI color codes for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
CYAN = '\033[0;36m'
NC = '\033[0m'

# Shared counters (modified by record())
PASS = 0
FAIL = 0
SKIP = 0
TOTAL = 0

# MCP session ID — populated by init_session()
SID = ""


# ==============================================================================
# Server connectivity
# ==============================================================================

def check_server():
    """
    Quick connectivity check against the MCP server.

    Sends a minimal POST to BASE_URL + MCP_PATH (GET is not supported
    by streamable-http transport). Returns True if server responds.
    """
    try:
        proc = subprocess.run(
            ["curl", "-s", "-D", "-", "--connect-timeout", "5", "-m", "5",
             "-X", "POST", f"{BASE_URL}{MCP_PATH}",
             "-H", "Content-Type: application/json",
             "-H", "Accept: application/json, text/event-stream",
             "-d", '{}'],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or "HTTP/1.1" not in proc.stdout:
            print(f"{RED}FATAL: Server not running at {BASE_URL}{MCP_PATH}{NC}")
            print(f"  Start the server with: python -m ms_access_mcp.mcp.server{NC}")
            sys.exit(1)
        return True
    except Exception as e:
        print(f"{RED}FATAL: Server check failed: {e}{NC}")
        sys.exit(1)


def curl_post(path, body_json, with_headers=False):
    """POST JSON to the MCP endpoint.

    Args:
        path: URL path (usually '/mcp').
        body_json: Dict to serialize as the request body.
        with_headers: If True, return the raw response text
                      (headers + body). Otherwise parse as SSE.

    Returns:
        Parsed JSON dict (or raw string if with_headers=True).
    """
    cmd = [
        "curl", "-s", "--connect-timeout", "5", "-m", str(MCP_TIMEOUT),
        "-X", "POST", f"{BASE_URL}{MCP_PATH}",
        "-H", f"Authorization: Bearer {API_KEY}",
        "-H", "Accept: application/json, text/event-stream",
        "-H", "Content-Type: application/json",
    ]
    if SID:
        cmd += ["-H", f"mcp-session-id: {SID}"]

    proc = subprocess.run(
        cmd + ["-d", json.dumps(body_json)],
        capture_output=True, text=True,
    )
    raw = proc.stdout.strip()
    if with_headers:
        return raw
    return parse_sse_response(raw)


def parse_sse_response(raw):
    """
    Parse SSE-formatted or plain JSON response.

    SSE format: 'data: {json}' (possibly with 'event: message' before).
    Also handles plain JSON responses that start with '{'.
    Returns an empty dict on parse failure.
    """
    if not raw:
        return {}
    if raw.startswith("{"):
        # Plain JSON (no SSE wrapper)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    # SSE format: "event: message\ndata: {...}"
    if "data: " in raw:
        json_str = raw.split("data: ", 1)[1].strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}
    return {}


def call_tool(name, arguments=None):
    """
    Call an MCP tool via JSON-RPC tools/call.

    Args:
        name: Tool name string.
        arguments: Dict of tool arguments.

    Returns:
        Parsed JSON-RPC response dict.
    """
    if arguments is None:
        arguments = {}
    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    resp = curl_post(MCP_PATH, body)
    return resp


def extract_text_content(resp):
    """
    Extract inner text from FastMCP response wrapper.

    FastMCP wraps tool results in result.content[0].text, which is
    itself a JSON string. This function unwraps that nesting.

    Falls back to the raw result dict if the expected shape is missing.
    """
    try:
        result = resp.get("result", {})
        content = result.get("content", [{}])[0].get("text", "")
        if content:
            return json.loads(content)
        return result
    except (json.JSONDecodeError, IndexError, KeyError):
        return resp


def get_field(resp, *keys, default=None):
    """
    Safely extract nested fields from a tool response.

    First unwraps via extract_text_content, then traverses *keys
    returning the value at the leaf, or *default* if any key is missing.
    """
    try:
        val = extract_text_content(resp)
        for k in keys:
            val = val[k]
        return val
    except (KeyError, IndexError, TypeError):
        return default


# ==============================================================================
# Recording
# ==============================================================================

def record(num, name, status, result_detail):
    """
    Record a test result: print to terminal and append to results markdown.

    Updates the module-level PASS, FAIL, SKIP, TOTAL counters.

    Args:
        num: Test number.
        name: Tool/test name.
        status: 'PASS', 'FAIL', 'SKIP', or 'WARN'.
        result_detail: Short description of the result.
    """
    global PASS, FAIL, SKIP, TOTAL
    TOTAL += 1

    if status == "PASS":
        PASS += 1
        mc_status = f"{GREEN}✅ PASS{NC}"
        mc_result = f"{GREEN}{result_detail}{NC}"
    elif status == "FAIL":
        FAIL += 1
        mc_status = f"{RED}❌ FAIL{NC}"
        mc_result = f"{RED}{result_detail}{NC}"
    elif status == "SKIP":
        SKIP += 1
        mc_status = f"{YELLOW}⏭️  SKIP{NC}"
        mc_result = f"{YELLOW}{result_detail}{NC}"
    elif status == "WARN":
        mc_status = f"{YELLOW}⚠️  WARN{NC}"
        mc_result = f"{YELLOW}{result_detail}{NC}"
    else:
        mc_status = status
        mc_result = result_detail

    print(f"  {mc_status}: {mc_result}")

    # Markdown escape
    md_result = str(result_detail).replace('"', '\\"')[:120]
    with open(RESULTS_FILE, "a") as f:
        f.write(f"| {num} | `{name}` | {status} | {md_result} |\n")
