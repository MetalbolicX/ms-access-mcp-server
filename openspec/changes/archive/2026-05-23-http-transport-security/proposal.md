# Proposal: HTTP Transport with Security

## Intent

Enable Linux/WSL machines to control Windows-hosted Access databases over HTTP.
Currently the MCP server runs via stdio only (local process). Exposing it as an HTTP server with API key authentication and database path restrictions allows remote Access automation from any machine on the network.

## Scope

### In Scope
- HTTP transport via FastMCP (`mcp.run(transport="http")`)
- Bearer token (API key) authentication via FastMCP middleware
- Database path whitelist (directory-based restriction, reject traversal and UNC)
- Environment-based configuration (no config file, env vars only)
- CLI `serve` command to start HTTP server
- `connect_access` tool wrapped with path guard validation

### Out of Scope
- Built-in HTTPS (use reverse proxy for TLS)
- OAuth (single API key sufficient for this use case)
- User management or multi-key support
- Rate limiting
- CORS configuration

## Capabilities

### New Capabilities
- `http-transport`: Expose MCP server over HTTP on configurable host:port
- `api-key-auth`: Validate Bearer token on all tool calls
- `path-guard`: Restrict database access to configured directory whitelist

### Modified Capabilities
- `access-mcp`: `connect_access` tool gains path validation and connection-state sharing via HTTP

## Approach

Use FastMCP's built-in HTTP transport. At server startup, read configuration from environment variables:
- `ACCESS_MCP_API_KEY` (required) — Bearer token
- `ACCESS_MCP_HOST` (default `127.0.0.1`) — bind address
- `ACCESS_MCP_PORT` (default `8000`) — bind port
- `ACCESS_MCP_ALLOWED_DIRS` (default `~`) — semicolon-separated directory whitelist

API key validation via FastMCP middleware. Path validation wraps `connect_access` tool — rejects any `.accdb`/`.mdb` path outside allowed directories. UNC paths and path traversal (`../`) are blocked.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ms_access_mcp/config.py` | New | Environment variable config loader |
| `src/ms_access_mcp/auth.py` | New | API key middleware |
| `src/ms_access_mcp/path_guard.py` | New | Database path restriction |
| `src/ms_access_mcp/mcp/server.py` | Modified | Wire auth + path guard, add HTTP run path |
| `src/ms_access_mcp/cli/main.py` | Modified | Add `serve` command |
| `docs/deployment.md` | New | Deployment + security guide |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Exposed API key in env var | Medium | Document firewall rules, use reverse proxy |
| Path traversal bypass | Low | PathGuard uses `resolve()` + relative_to check |
| No TLS on HTTP transport | Medium | Document nginx/caddy TLS termination |

## Rollback Plan

Delete `config.py`, `auth.py`, `path_guard.py`. Revert `server.py` to use module-level `mcp = FastMCP(...)` without config/middleware. Remove `serve` command from `main.py`. Delete `docs/deployment.md`. All changes are additive — no existing behavior modified.

## Dependencies

- FastMCP `>=3.2.0` (already in project, provides HTTP transport)
- Python `secrets` module (stdlib, for key generation docs)

## Success Criteria

- [ ] Server starts with `ACCESS_MCP_API_KEY` env var set and accepts HTTP requests
- [ ] Requests without valid Bearer token are rejected with 401
- [ ] `connect_access` rejects database paths outside allowed directories
- [ ] Path traversal (`../../etc/passwd.accdb`) is rejected
- [ ] UNC paths (`\\server\share\db.accdb`) are rejected
- [ ] All 75 existing tests pass
- [ ] New unit tests cover config, auth, and path guard modules