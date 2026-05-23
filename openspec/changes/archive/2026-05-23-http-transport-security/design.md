# Design: HTTP Transport with Security

## Technical Approach

Add a secure HTTP runtime path to the existing FastMCP server without breaking current stdio usage. The design introduces three focused modules (`config`, `auth`, `path_guard`) and wires them into `mcp/server.py`. HTTP runtime is started via a new CLI `serve` command. The `connect_access` tool is the authorization boundary for filesystem paths.

## Architecture Decisions

### Decision: API key middleware over OAuth

**Choice**: Use Bearer API key validation middleware.
**Alternatives considered**: OAuth provider integration.
**Rationale**: Lower operational complexity, sufficient for trusted LAN/WSL-to-Windows usage, faster delivery.

### Decision: Env-only configuration

**Choice**: Read host/port/api-key/allowed-dirs from environment variables.
**Alternatives considered**: YAML/TOML runtime config file.
**Rationale**: Secrets stay outside repo, simple deployment for Windows services/shell profiles.

### Decision: Path restriction at tool boundary

**Choice**: Validate `database_path` inside `connect_access` before adapter creation.
**Alternatives considered**: Adapter-level validation, middleware-level path validation.
**Rationale**: Single ingress point for DB file access; explicit error response at MCP tool layer.

### Decision: Preserve stdio default behavior

**Choice**: Keep `mcp.run()` default path and add explicit HTTP startup via CLI `serve`.
**Alternatives considered**: Convert default runtime to HTTP.
**Rationale**: Avoid breaking existing local MCP integrations and tests.

## Data Flow

```text
Linux/WSL MCP Client
    |
    | HTTP + Authorization: Bearer <token>
    v
FastMCP HTTP runtime (Windows)
    |
    +--> ApiKeyMiddleware validates token
    |
    +--> tools/call: connect_access(database_path, use_com)
             |
             +--> PathGuard validates allowed directory + safe path form
             |
             +--> ConnectionService.connect(adapter)
                     |
                     +--> WinComAdapter (COM) or OdbcAdapter
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ms_access_mcp/config.py` | Create | Load and validate env config (`ACCESS_MCP_*`). |
| `src/ms_access_mcp/auth.py` | Create | Middleware for Bearer token validation. |
| `src/ms_access_mcp/path_guard.py` | Create | Resolve and validate path against allowed dirs; reject UNC/traversal. |
| `src/ms_access_mcp/mcp/server.py` | Modify | Initialize middleware/config and enforce path guard in `connect_access`. |
| `src/ms_access_mcp/cli/main.py` | Modify | Add `serve` command with host/port/transport options. |
| `tests/unit/test_config.py` | Create | Config validation tests. |
| `tests/unit/test_auth.py` | Create | Auth middleware behavior tests. |
| `tests/unit/test_path_guard.py` | Create | Path guard acceptance/rejection tests. |
| `docs/deployment.md` | Create | Windows host + Linux/WSL client deployment and security guidance. |

## Interfaces / Contracts

```python
# src/ms_access_mcp/config.py
class ServerConfig:
    host: str  # default 127.0.0.1
    port: int  # default 8000
    api_key: str  # required for HTTP mode
    allowed_dirs: list[str]  # default [home]
```

```python
# src/ms_access_mcp/path_guard.py
class PathGuard:
    def is_allowed(self, path: str) -> bool: ...
    def validate(self, path: str) -> str: ...  # raises ValueError on reject
```

```python
# src/ms_access_mcp/auth.py
class ApiKeyMiddleware(Middleware):
    async def on_call_tool(self, context, call_next): ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Config defaults and required API key | `pytest` with monkeypatch env vars |
| Unit | Auth pass/fail paths | middleware unit tests with mocked context |
| Unit | Path allow/deny and unsafe paths | `pytest` temp dirs + traversal/UNC cases |
| Integration | HTTP startup args and tool routing | local FastMCP HTTP run test (non-COM path) |
| Existing regression | Current adapter/service behavior | run existing 75-unit suite |

## Migration / Rollout

No data migration required.

Rollout sequence:
1. Deploy code to Windows host.
2. Set `ACCESS_MCP_API_KEY` and `ACCESS_MCP_ALLOWED_DIRS`.
3. Start via `serve` command with localhost binding.
4. Open firewall only for trusted client range (if remote needed).
5. Optionally place behind TLS reverse proxy.

## Open Questions

- [ ] Should invalid auth responses be standardized to explicit HTTP 401 payload shape in all transports?
- [ ] Do we need optional multi-key support (rotation window) in first release or defer to follow-up?
