# Plan 008: Minimal local MCP stdio server over the facade (SDD)

> **Executor instructions**: Execute through the repo's SDD workflow
> (openspec): propose → spec → design → tasks → apply (strict TDD where
> unit-testable) → verify → archive. Use the SDD skills if available, else
> follow `openspec/` conventions manually. When done, update this plan's
> status row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 0b69c82..HEAD -- src/ms_access_mcp/mcp/ src/ms_access_mcp/mcp/server.py openspec/specs/access-mcp`
> The Python MCP tool modules are the tool-surface oracle. Material
> changes → reconcile; on mismatch, STOP.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/006-db-facade-sdd.md (and transitively 003-005)
- **Category**: migration
- **Methodology**: SDD. The MCP tool surface is a protocol contract: which
  tools exist, their names, input schemas, and output shapes — decided
  against the Python oracle (`mcp/*.py`) but deliberately trimmed to a
  minimal local set per the user's direction. Contract selection + FFI
  binding design over `@modelcontextprotocol/sdk` require spec and design
  before code. Server wiring tasks are integration-verified (in-process
  client against the stdio server), not unit-TDD'able; tool functions are
  thin and unit-tested against facade fakes.
- **Planned at**: commit `0b69c82`, 2026-08-18

## Why this matters

The user's deployment model is an AI harness (Claude Code, other MCP
clients) talking to local Access databases. The facade (plan 006) is the
engine; this phase exposes it as an MCP server over stdio — the transport
Python uses for local, no-auth operation (HTTP mode with API-key auth,
telemetry, sessions, and LLM tools are explicitly deferred/out of scope).
After this lands, an MCP client can replace the Python server for local
use, and plan 007's parity evidence carries over because tools are
transparent wrappers over the parity-proven facade.

## Current state

- Facade exists: `rescript-mcp/src/Services/Facade.res` (plan 006), all
  operations JSON-shaped, `Errors.t` serialized on failure.
- Python oracle: `src/ms_access_mcp/mcp/server.py` registers tools from
  23 tool modules via FastMCP; `python -m ms_access_mcp.mcp.server` runs
  stdio. Tool names + args live in the `mcp/*.py` modules — read them
  during explore; `connection.py`, `crud.py`, `schema.py`, `raw_sql.py`,
  `vba.py` cover the minimal set.
- npm package to bind: `@modelcontextprotocol/sdk` (official TS SDK) —
  `McpServer`, `registerTool`, `StdioServerTransport`, zod input schemas.
- ReScript 12 + rescript-nodejs toolchain working (plan 001); zod usage
  requires bindings (thin `@module`/`@send` externals — zod schemas can
  also be passed as raw JSON Schema objects if the SDK accepts them; the
  SDD design stage decides, favoring the least FFI surface).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install (after adding sdk dep) | `pnpm -C rescript-mcp install` | exit 0 |
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit tests | `pnpm -C rescript-mcp test` | all pass |
| Server smoke | `pnpm -C rescript-mcp server` | server starts on stdio, responds to initialize |

## Suggested executor toolkit

- SDD skills (sdd-propose … sdd-archive).
- MCP TS SDK docs: https://github.com/modelcontextprotocol/typescript-sdk
- Python `mcp/` modules for tool names/args/output shapes.

## Scope

**In scope**:
- `openspec/changes/rescript-mcp-server/**` (SDD artifacts)
- `rescript-mcp/src/Bindings/McpSdk.res` (FFI ONLY)
- `rescript-mcp/src/Bindings/Zod.res` (IF design chooses zod; keep minimal)
- `rescript-mcp/src/Mcp/Server.res`, `rescript-mcp/src/Mcp/Tools.res` (create)
- `rescript-mcp/package.json` (+`@modelcontextprotocol/sdk`, `zod`,
  `server` script)
- `rescript-mcp/test/McpServerTest.res` (in-process client tests)

**Out of scope** (explicitly deferred — do not build):
- HTTP/streamable-http transport, `ApiKeyMiddleware`/auth, sessions,
  rate limiting, Prometheus telemetry, audit logging.
- LLM tools (`ai_tools.py` behavior stays disabled).
- The 23-tool full surface — only the minimal set the spec pins.
- CLI framework parity (Typer) — a bare `server` npm script + bin is
  enough for this phase.

## Git workflow

- Branch: `rescript/008-mcp-stdio`.
- Conventional commits, e.g. `feat(rescript): register MCP stdio tools`.

## Steps (SDD stages with gates)

### Stage 1: Propose

SDD change `rescript-mcp-server`. Intent: minimal local stdio MCP server
exposing facade operations as tools, no auth (parity with Python stdio
mode, which requires no `ACCESS_MCP_API_KEY`).

### Stage 2: Spec (gate: tool contract pinned)

MUST decide, with one scenario per tool:
1. **Tool list (minimal)**: connect_access, disconnect, list_connections
   (if Python has it — check `mcp/connection.py`), execute_query,
   execute_sql (raw), insert_data, update_data, delete_data, get_tables,
   get_table_schema, get_queries, execute_vba, compact_repair. Each tool
   cites its Python counterpart; trimming is allowed, adding new tools is
   NOT.
2. **Names + input schemas**: tool names and argument names match the
   Python tools verbatim (AI harnesses may have prompts tuned to them).
3. **Output shapes**: tool returns = facade JSON (plan 006) = Python tool
   dict (plan 007 parity already proves this).
4. **Error contract**: errors surface as MCP tool errors (isError:true +
   serialized `Errors.t` payload), matching how Python tools report
   failures — check `server.py`/tool modules for the exact pattern.
5. **Server lifecycle**: name ("MS Access MCP Server" — match Python),
  version, stdio transport only, clean shutdown.

### Stage 3: Design

`Bindings/McpSdk.res` is the ONLY module importing the SDK. `Tools.res`
maps tool name → facade call (one function per tool, table-driven
registration). Input validation via zod bindings OR raw JSON schema —
design picks the smaller FFI surface and records why.

### Stage 4: Tasks

Tool functions unit-tested against facade fakes (strict TDD); server
wiring tasks verified by in-process client integration tests.

### Stage 5: Apply (strict TDD for tool functions)

- Unit: each tool function — valid args → facade called with exact args →
  facade JSON returned; facade error → error envelope. RED first.
- Integration: start server on stdio (in-process), connect an SDK client,
  initialize handshake, call each tool against facade fakes / ACCESS_TEST_DB,
  assert responses.

### Stage 6: Verify

- `pnpm -C rescript-mcp test` green.
- Manual smoke: `pnpm -C rescript-mcp server` + a real MCP client (or the
  SDK's client example) lists tools and runs `get_tables` against
  `ACCESS_TEST_DB`.

### Stage 7: Archive

Sync artifacts; update `plans/README.md`.

## Test plan

- Unit: per-tool arg passing + error envelope, table registration
  completeness (every spec'd tool registered).
- Integration: initialize handshake, tools/list contains the exact spec'd
  tool names, one tool call round-trip per tool.
- Structural pattern: `test/FacadeTest.res` fakes; in-process client per
  SDK examples.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] SDD change archived with the tool contract in specs
- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` exits 0 (unit + in-process client)
- [ ] `Bindings/McpSdk.res` is the only file importing the SDK
- [ ] tools/list returns exactly the spec'd tools with Python-verbatim
      names
- [ ] No auth/HTTP/telemetry code exists (grep for `ApiKey|prom-client`
      under `rescript-mcp/src` → no matches)
- [ ] `plans/README.md` status row updated

## STOP conditions

- The SDK's API differs materially from the documented surface (breaking
  change in a newer major) — report the version + diff; do not hand-roll
  the MCP protocol.
- A Python tool's name/args cannot be mapped to JSON schema (exotic
  typing) — report the tool; spec must pin the mapping.
- In-process client tests need > 2 fix attempts — report verbatim errors.

## Maintenance notes

- HTTP transport + auth, if ever wanted, is a NEW SDD change building on
  this server — the Python oracle (`server.py`, `auth.py`,
  `openspec/specs/http-transport`, `openspec/specs/api-key-auth`) already
  specifies it.
- Tool additions must keep Python-verbatim naming and add parity cases
  (plan 007 convention).
