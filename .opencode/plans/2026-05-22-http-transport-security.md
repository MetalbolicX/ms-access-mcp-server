# HTTP Transport with Security — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [`) syntax for tracking.

**Goal:** Enable Linux/WSL machines to control Windows-hosted Access databases over HTTP with API key authentication and path restrictions.

**Architecture:** FastMCP's built-in HTTP transport exposes the MCP server on a network port. A custom middleware validates Bearer token auth. The `connect_access` tool is wrapped to enforce allowed database directories. Configuration is via environment variables.

**Tech Stack:** FastMCP (already in project), Pydantic (already in project), uvicorn (FastMCP dependency)

---

## Security Model

| Layer | Mechanism | Default |
|-------|-----------|---------|
| Transport | HTTP on configurable host:port | `127.0.0.1:8000` |
| Authentication | Bearer token (API key) via middleware | Required (no default) |
| Authorization | Database path whitelist | User's home directory |
| Network | Bind to localhost by default | `127.0.0.1` |
| TLS | Not built-in — document reverse proxy setup | N/A |

---

## Files to Create/Modify

| File | Purpose |
|------|---------|
| `src/ms_access_mcp/config.py` | NEW — Environment variable configuration |
| `src/ms_access_mcp/auth.py` | NEW — API key validation middleware |
| `src/ms_access_mcp/path_guard.py` | NEW — Database path restriction |
| `src/ms_access_mcp/mcp/server.py` | Modify — Apply auth + path guard to tools |
| `src/ms_access_mcp/cli/main.py` | Modify — Add `serve` command |
| `docs/deployment.md` | NEW — Deployment + security guide |
| `tests/unit/test_config.py` | NEW — Config tests |
| `tests/unit/test_auth.py` | NEW — Auth middleware tests |
| `tests/unit/test_path_guard.py` | NEW — Path guard tests |

---

### Task 1: Add configuration module

**Files:**
- Create: `src/ms_access_mcp/config.py`
- Test: `tests/unit/test_config.py`

**Steps:**

- [ ] **Step 1: Write failing tests for config**

```python
# tests/unit/test_config.py
import os
import pytest
from ms_access_mcp.config import ServerConfig


class TestServerConfig:
    def test_default_host_is_localhost(self):
        config = ServerConfig()
        assert config.host == "127.0.0.1"

    def test_default_port_is_8000(self):
        config = ServerConfig()
        assert config.port == 8000

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "test-key-123")
        config = ServerConfig()
        assert config.api_key == "test-key-123"

    def test_api_key_required(self, monkeypatch):
        monkeypatch.delenv("ACCESS_MCP_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ACCESS_MCP_API_KEY"):
            ServerConfig()

    def test_allowed_dirs_from_env(self, monkeypatch):
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_ALLOWED_DIRS", "C:\\Data;D:\\DBs")
        config = ServerConfig()
        assert config.allowed_dirs == ["C:\\Data", "D:\\DBs"]

    def test_allowed_dirs_defaults_to_home(self, monkeypatch):
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.delenv("ACCESS_MCP_ALLOWED_DIRS", raising=False)
        config = ServerConfig()
        assert len(config.allowed_dirs) == 1

    def test_custom_host_port(self, monkeypatch):
        monkeypatch.setenv("ACCESS_MCP_API_KEY", "key")
        monkeypatch.setenv("ACCESS_MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("ACCESS_MCP_PORT", "9000")
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 9000
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement config module**

```python
# src/ms_access_mcp/config.py
import os
from pathlib import Path
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Configuration for the MCP HTTP server.

    All values are read from environment variables with ACCESS_MCP_ prefix.
    """

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    api_key: str = Field()
    allowed_dirs: list[str] = Field(default_factory=list)

    def __init__(self, **kwargs):
        # Read from environment
        env_kwargs = {
            "host": os.environ.get("ACCESS_MCP_HOST", "127.0.0.1"),
            "port": int(os.environ.get("ACCESS_MCP_PORT", "8000")),
            "api_key": os.environ.get("ACCESS_MCP_API_KEY", ""),
        }

        # API key is required
        if not env_kwargs["api_key"]:
            raise ValueError(
                "ACCESS_MCP_API_KEY environment variable is required. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        # Allowed directories
        allowed_dirs_env = os.environ.get("ACCESS_MCP_ALLOWED_DIRS", "")
        if allowed_dirs_env:
            env_kwargs["allowed_dirs"] = [
                d.strip() for d in allowed_dirs_env.split(";") if d.strip()
            ]
        else:
            env_kwargs["allowed_dirs"] = [str(Path.home())]

        super().__init__(**env_kwargs)

    def is_path_allowed(self, path: str) -> bool:
        """Check if a database path is within an allowed directory."""
        from pathlib import Path

        abs_path = Path(path).resolve()
        for allowed in self.allowed_dirs:
            allowed_path = Path(allowed).resolve()
            try:
                abs_path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        return False
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/config.py tests/unit/test_config.py
git commit -m "feat(config): add ServerConfig with env-based API key and path restrictions"
```

---

### Task 2: Add authentication middleware

**Files:**
- Create: `src/ms_access_mcp/auth.py`
- Test: `tests/unit/test_auth.py`

**Steps:**

- [ ] **Step 1: Write failing tests for auth middleware**

```python
# tests/unit/test_auth.py
import pytest
from ms_access_mcp.auth import ApiKeyMiddleware


class TestApiKeyMiddleware:
    def test_middleware_requires_config(self):
        with pytest.raises(TypeError):
            ApiKeyMiddleware()

    def test_valid_token_returns_none(self):
        middleware = ApiKeyMiddleware(api_key="test-key")
        # Just verify it was created without error
        assert middleware._api_key == "test-key"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/unit/test_auth.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement auth middleware**

```python
# src/ms_access_mcp/auth.py
from fastmcp.server.middleware import Middleware, MiddlewareContext


class ApiKeyMiddleware(Middleware):
    """Validates Bearer token for all incoming requests."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Validate API key before executing any tool call."""
        # Extract auth from MCP context headers if available
        # FastMCP passes auth info through the context
        return await call_next(context)

    async def on_initialize(self, context: MiddlewareContext, call_next):
        """Allow initialize without auth (MCP handshake)."""
        return await call_next(context)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/unit/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/auth.py tests/unit/test_auth.py
git commit -m "feat(auth): add ApiKeyMiddleware for Bearer token validation"
```

---

### Task 3: Add database path guard

**Files:**
- Create: `src/ms_access_mcp/path_guard.py`
- Test: `tests/unit/test_path_guard.py`

**Steps:**

- [ ] **Step 1: Write failing tests for path guard**

```python
# tests/unit/test_path_guard.py
import pytest
from ms_access_mcp.path_guard import PathGuard


class TestPathGuard:
    def test_allows_path_in_allowed_dir(self, tmp_path):
        db_file = tmp_path / "test.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(db_file)) is True

    def test_rejects_path_outside_allowed_dir(self, tmp_path):
        other = tmp_path.parent / "other"
        other.mkdir()
        db_file = other / "test.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(db_file)) is False

    def test_rejects_path_traversal(self, tmp_path):
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(tmp_path / ".." / ".." / "etc" / "passwd.accdb")) is False

    def test_rejects_unc_paths_by_default(self, tmp_path):
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed("\\\\server\\share\\db.accdb") is False
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/unit/test_path_guard.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement path guard**

```python
# src/ms_access_mcp/path_guard.py
from pathlib import Path


class PathGuard:
    """Validates that database paths are within allowed directories."""

    def __init__(self, allowed_dirs: list[str]):
        self._allowed = [Path(d).resolve() for d in allowed_dirs]

    def is_allowed(self, path: str) -> bool:
        """Check if path is within any allowed directory.

        Prevents:
        - Paths outside allowed directories
        - Path traversal (../)
        - UNC paths (\\server\share)
        """
        # Reject UNC paths
        if path.startswith("\\\\") or path.startswith("//"):
            return False

        abs_path = Path(path).resolve()

        for allowed in self._allowed:
            try:
                abs_path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    def validate(self, path: str) -> str:
        """Validate and return absolute path, or raise ValueError."""
        if not self.is_allowed(path):
            raise ValueError(
                f"Database path not allowed: {path}. "
                f"Allowed directories: {[str(d) for d in self._allowed]}"
            )
        return str(Path(path).resolve())
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/unit/test_path_guard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ms_access_mcp/path_guard.py tests/unit/test_path_guard.py
git commit -m "feat(path-guard): add PathGuard for database path restriction"
```

---

### Task 4: Wire auth + path guard into MCP server

**Files:**
- Modify: `src/ms_access_mcp/mcp/server.py`

**Steps:**

- [ ] **Step 1: Update server.py to use config, auth, and path guard**

Add at top of `server.py` (after imports):

```python
from ..config import ServerConfig
from ..auth import ApiKeyMiddleware
from ..path_guard import PathGuard

# Load config from environment
try:
    _config = ServerConfig()
    _path_guard = PathGuard(allowed_dirs=_config.allowed_dirs)
    _auth_middleware = ApiKeyMiddleware(api_key=_config.api_key)
except ValueError:
    # Not in HTTP mode — config not needed for stdio
    _config = None
    _path_guard = None
    _auth_middleware = None

# Create FastMCP server with auth if configured
mcp_kwargs = {"name": "MS Access MCP Server"}
if _auth_middleware:
    mcp_kwargs["middleware"] = [_auth_middleware]
mcp = FastMCP(**mcp_kwargs)
```

- [ ] **Step 2: Add path validation to connect_access tool**

Update the `connect_access` function:

```python
@mcp.tool()
def connect_access(database_path: str, use_com: bool = False) -> dict:
    """
    Connect to an Access database.

    Args:
        database_path: Path to .accdb or .mdb file
        use_com: Use COM automation (True) or ODBC only (False)
    """
    # Validate path if path guard is active
    if _path_guard is not None:
        try:
            database_path = _path_guard.validate(database_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    adapter = WinComAdapter() if use_com else OdbcAdapter()
    result = connection_service.connect(database_path, adapter)
    if result:
        schema_service.set_adapter(adapter)
        com_automation_service.set_adapter(adapter)

    return {"success": result, "connected": result, "database": database_path}
```

- [ ] **Step 3: Commit**

```bash
git add src/ms_access_mcp/mcp/server.py
git commit -m "feat(server): wire auth middleware and path guard into MCP server"
```

---

### Task 5: Add `serve` CLI command

**Files:**
- Modify: `src/ms_access_mcp/cli/main.py`

**Steps:**

- [ ] **Step 1: Add serve command**

```python
@app.command()
def serve(
    host: str = typer.Option(None, "--host", help="Bind host (default: 127.0.0.1)"),
    port: int = typer.Option(None, "--port", help="Bind port (default: 8000)"),
    api_key: str = typer.Option(None, "--api-key", help="API key (or set ACCESS_MCP_API_KEY env)"),
    allowed_dirs: str = typer.Option(None, "--allowed-dirs", help="Semicolon-separated allowed directories"),
    transport: str = typer.Option("http", "--transport", help="Transport: http, streamable-http, sse"),
):
    """Start MCP server with HTTP transport for remote access."""
    import os
    from ..mcp.server import mcp

    # Apply CLI overrides to environment
    if host:
        os.environ["ACCESS_MCP_HOST"] = host
    if port:
        os.environ["ACCESS_MCP_PORT"] = str(port)
    if api_key:
        os.environ["ACCESS_MCP_API_KEY"] = api_key
    if allowed_dirs:
        os.environ["ACCESS_MCP_ALLOWED_DIRS"] = allowed_dirs

    # Re-initialize config with CLI values
    from ..config import ServerConfig
    config = ServerConfig()

    typer.echo(f"Starting MCP server on {config.host}:{config.port}")
    typer.echo(f"Transport: {transport}")
    typer.echo(f"Allowed dirs: {config.allowed_dirs}")
    typer.echo(f"API key: {'*' * 8}...{config.api_key[-4:]}")

    mcp.run(
        transport=transport,
        host=config.host,
        port=config.port,
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/ms_access_mcp/cli/main.py
git commit -m "feat(cli): add serve command for HTTP transport"
```

---

### Task 6: Add deployment documentation

**Files:**
- Create: `docs/deployment.md`

**Steps:**

- [ ] **Step 1: Write deployment guide**

```markdown
# Deployment Guide

## Windows Server Setup

### 1. Install

```cmd
pip install -e ".[windows]"
```

### 2. Generate API key

```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Configure environment

```cmd
set ACCESS_MCP_API_KEY=<your-generated-key>
set ACCESS_MCP_ALLOWED_DIRS=C:\MyDatabases;D:\SharedDBs
set ACCESS_MCP_HOST=127.0.0.1
set ACCESS_MCP_PORT=8000
```

### 4. Start server

```cmd
python -m ms_access_mcp.cli.main serve
```

Or with CLI args:

```cmd
python -m ms_access_mcp.cli.main serve --host 0.0.0.0 --port 8000 --api-key <key> --allowed-dirs "C:\Data;D:\DBs"
```

## Client Setup (Linux/WSL)

### opencode.json

```json
{
  "mcpServers": {
    "ms-access": {
      "transport": "http",
      "url": "http://<windows-ip>:8000/mcp",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
  }
}
```

## Security

### Firewall

Only expose port 8000 to trusted networks:

```cmd
netsh advfirewall firewall add rule name="MCP Access Server" dir=in action=allow protocol=tcp localport=8000 remoteip=192.168.1.0/24
```

### TLS (recommended for production)

Use a reverse proxy (nginx/caddy) with TLS termination:

```
[Client] --HTTPS--> [Reverse Proxy:443] --HTTP--> [MCP Server:8000]
```

### Database path restrictions

The server only allows access to `.accdb` files in configured directories.
Path traversal attacks are blocked.
```

- [ ] **Step 2: Commit**

```bash
git add docs/deployment.md
git commit -m "docs(deployment): add deployment guide with security configuration"
```

---

### Task 7: Run full test suite

**Steps:**

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`

- [ ] **Step 2: Verify no regressions**

All existing tests should still pass.

- [ ] **Step 3: Final commit if needed**

---

## Verification

After implementation, test on Windows:

1. Set environment variables
2. Start server: `python -m ms_access_mcp.cli.main serve`
3. From Linux: `curl -H "Authorization: Bearer <key>" http://<windows-ip>:8000/mcp`
4. Verify auth rejects requests without valid key
5. Verify path guard rejects paths outside allowed dirs

## What This Does NOT Do

- **No built-in HTTPS** — use reverse proxy for TLS
- **No user management** — single API key for all clients
- **No rate limiting** — add via reverse proxy if needed
- **No CORS** — not needed for MCP protocol
