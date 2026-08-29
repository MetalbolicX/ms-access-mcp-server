# ReScript MCP UI Assessment — Decision Memo

**Date**: 2026-08-28
**Plan**: 009 (UI assessment, decision memo only)
**Decision**: No UI migration in this wave.

---

## Decision

**Do not migrate, extend, or wire the Python SSR UI into the ReScript MCP deployment. Do not add HTTP transport or API-key auth in this wave.** The MCP server runs locally on the Windows computer that hosts Microsoft Access/ACE; MCP clients/harnesses are the sole interaction surface.

The existing Python SSR web UI (`src/ms_access_mcp/templates/`) and the independent Vue 3 frontend (`frontend/`) remain untouched and are explicitly out of scope. They are not deleted. Reopen UI or HTTP transport work only as a future, separately scoped SDD change.

---

## Deployment Context

The ReScript MCP server targets **local AI-harness-first deployment**:

- **Transport**: `stdio` — no HTTP server, no network listening.
- **Auth**: No API-key auth in stdio mode (matches the Python stdio fallback).
- **Location**: Runs on the same Windows machine as Access/ACE; the machine is trusted, not exposed to a network.
- **Interaction surface**: MCP clients and harnesses (e.g. Cursor, Windsurf, commercial LLM tooling) consume the server over stdio.
- **Active MCP path**: ReScript stdio server backed by `OdbcAdapter` (ODBC, not COM/VBA) for data operations.

The Python HTTP server (`uv run ms-access-mcp serve`) is **existing legacy functionality** and is not changed by this decision. It continues to work as-is for users who already rely on it.

---

## Current State (as of main @ 2026-08-28)

### Python SSR UI (`src/ms_access_mcp/templates/`)

Serves login, dashboard, ER diagram, and unified explorer pages via FastAPI/Jinja2 in HTTP mode only. Requires HTTP transport, session management, and API-key auth. No direct stdio path. The pages render MCP tool data (e.g. schema reads, query results) but are not required for the AI-harness use case — MCP clients handle all data display.

Evidence: `src/ms_access_mcp/templates/` (login, dashboard, er_diagram, unified explorer); `tests/unit/test_ssr_*` confirm HTTP-only serving.

### Vue 3 Frontend (`frontend/`)

Independent pnpm workspace (Vite 8, Element Plus, Vue Flow, AlpineJS). Its integration point is undocumented; `git log --oneline -10 -- frontend/` shows last material activity prior to the ReScript migration start. The frontend has no live backend defined against the ReScript server. It is dormant with respect to the current migration work.

Evidence: `frontend/package.json`; repo history.

### ReScript MCP Server (post plan 008)

Local stdio MCP server (`rescript-mcp/src/Mcp/Server.res`). Transport: stdio only. No HTTP, no SSR. 12 tools registered. ODBC-backed data path via `OdbcAdapter` and `Services/Composition.res`. Parity with Python facade verified (plan 007, 17/17 on stdio path).

Evidence: `rescript-mcp/src/Mcp/Server.res`; `rescript-mcp/src/Mcp/Tools.res`; `rescript-mcp/src/Services/Composition.res`; plan 008 merged to `main` at `e1bf8f4`.

---

## Options Evaluated

| Option | Effort | Risk | Buys | Loses |
|--------|--------|------|------|-------|
| **A — No UI (MCP clients are interface)** | S | Low | Zero extra runtime; stdio-only deployment is simple and secure by default; matches AI-harness-first goal | No browser-based dashboard or ER diagram for human inspection outside MCP clients |
| B — Keep Python HTTP+SSR alongside ReScript stdio | M | Medium | Existing UI stays available | Two runtimes; drift between Python SSR and ReScript facade; operational complexity |
| C — Port SSR to ReScript (requires HTTP transport) | L | High | Unified ReScript-only server | Reopens plan-008 out-of-scope list (HTTP, auth, sessions); months of work; breaks stdio simplicity |
| D — Wire Vue frontend to future ReScript HTTP | M | Medium | Vue Flow/Element Plus covers dashboard/ER needs | Vue has no live backend; HTTP transport is a prerequisite; not deployable today |

**Recommendation**: Option A. MCP clients are the interface; no UI migration or HTTP transport in this wave.

---

## Consequences & Risks

- **Human-facing dashboard/ER diagram**: Not available via browser in the ReScript stdio deployment. MCP clients must surface the data or the user queries it directly.
- **Python HTTP server**: Continues to exist as a separate runtime for users who already depend on it. It is not modified or deleted by this decision.
- **Vue frontend**: Remains dormant. If a future deployment requires a browser UI, Option D or a fresh Option C is the starting point — neither is ruled out permanently.
- **HTTP transport / API-key auth**: Not added in this wave. Revisit only via a new SDD change with its own scope and design.

---

## Trigger for Reopening UI / HTTP Work

Reopen only when:

1. **Deployment model changes**: A user or operator requires browser-based dashboard access from a machine other than the Access/ACE host, OR requires HTTP exposure across a trusted network.
2. **MCP clients are insufficient**: Evidence that the AI harness use case cannot function without a human-readable UI layer.
3. **New SDD**: Any reopening must be a separately scoped SDD change — not edits riding on this memo.

---

## Out of Scope (explicit)

- Migration of `src/ms_access_mcp/templates/` SSR pages to ReScript
- Addition of HTTP transport to the ReScript MCP server
- Addition of API-key or Bearer token auth to the ReScript MCP server
- Wiring the `frontend/` Vue app to any ReScript backend
- Deletion of the Python HTTP server or SSR UI
- Any COM/VBA work (separate ongoing SDD phases)

---

*This memo was produced by plan 009 execution against `main` @ 2026-08-28. The user's decision is explicit and binding. Any action on the above consequences requires a new SDD change.*
