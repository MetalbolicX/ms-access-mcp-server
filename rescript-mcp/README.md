# MS Access MCP Server — ReScript Implementation

MCP (Model Context Protocol) server exposing MS Access database operations over
stdio, built in ReScript 12. The server wraps the facade layer
(`src/Services/Facade.res`) — the same engine verified by the plan 007 parity
harness — and exposes it as an MCP tool surface for AI harnesses (Claude Code,
etc.).

## Quick start

```bash
# Install dependencies (Node >= 24 required)
pnpm install --ignore-scripts

# Build the ReScript project
pnpm -C rescript-mcp build

# Run the MCP server (stdio transport — no API key required)
pnpm -C rescript-mcp server
```

## Tool reference

| Tool | Description |
|------|-------------|
| `connect_access` | Open an `.accdb` file via ODBC |
| `disconnect_access` | Close the current connection |
| `list_connections` | List open named connections |
| `is_connected` | Ping the active connection |
| `query_data` | Execute a SELECT query, return rows as JSON |
| `insert_data` | Insert a row into a table |
| `update_data` | Update rows matching a WHERE clause |
| `delete_data` | Delete rows matching a WHERE clause |
| `get_tables` | List user tables in the database |
| `get_table_schema` | Describe a table's column layout |
| `get_queries` | List saved queries / views |
| `execute_raw_sql` | Execute arbitrary SQL (SELECT only) |
| `execute_vba` | Run a named VBA function (Windows-only via COM) |
| `compact_repair` | Compact and repair the database file |

Tool names and argument shapes match the Python oracle (`src/ms_access_mcp/mcp/`)
verbatim — prompts tuned to the Python tool names work unchanged against this
server.

## Testing

```bash
# Unit + in-process integration tests (retest)
pnpm -C rescript-mcp test
```

Tests live under `test/` and are written in ReScript via `rescript-test`.
In-process client tests verify the MCP handshake and round-trip each registered
tool.

## Parity verification

```bash
# Validate parity case files (JSON Schema check)
pnpm -C rescript-mcp lint:cases

# Run full differential parity vs the Python original
pnpm -C rescript-mcp parity
```

The parity harness exercises every facade operation against both the Python and
ReScript implementations on the same `.accdb` fixture and diffs the JSON
envelopes. See `parity/README.md` for full documentation.

Current parity score: **17/17 operations matched** (plan 007 evidence carried
forward to plan 008).

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `ACCESS_TEST_DB` | for tests/parity | — | Path to `.accdb` fixture, e.g. `D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb` |
| `ACCESS_TEST_ASSUME_ACE` | no | `false` | Set `true` to skip COM availability probe on non-Windows CI |
| `ACCESS_MCP_ALLOWED_DIRS` | no | user home | Semicolon-separated list of permitted database directories (PathGuard) |

## Architecture

```
AI Harness (MCP client)
        │
        │ stdio
        ▼
src/Mcp/Server.res        ← MCP server (stdio transport, tool registration)
        │
        │ thin wrapper
        ▼
src/Services/Facade.res   ← Business logic (plan 006)
        │
        ├── OdbcAdapter    ← ODBC path (plan 003)
        └── WinComAdapter  ← COM path (plan 004, Windows-only)
```

HTTP transport, API-key auth, sessions, and LLM tools are explicitly deferred —
they require a new SDD change.

## Build commands

| Command | Effect |
|---------|--------|
| `pnpm -C rescript-mcp install --ignore-scripts` | Install deps (use `--ignore-scripts` if node-gyp/Python fail) |
| `pnpm -C rescript-mcp build` | Compile ReScript → `lib/bs/` |
| `pnpm -C rescript-mcp dev` | Watch mode (rebuild on save) |
| `pnpm -C rescript-mcp clean` | Delete `lib/bs/` |
| `pnpm -C rescript-mcp test` | Run test suite |
| `pnpm -C rescript-mcp lint:cases` | Validate parity case JSON files |
| `pnpm -C rescript-mcp parity` | Run differential parity harness |
| `pnpm -C rescript-mcp server` | Start the MCP stdio server |

## Known limitations

- Requires Node >= 24 (ReScript 12 + `rescript-test@8.0.1` peer requirement).
- On Windows, the `odbc` package needs the ACE ODBC driver installed.
- `execute_vba` and `compact_repair` require Windows + COM (winax binding);
  they are skipped cleanly on non-Windows.
- HTTP/streamable-http, API-key auth, sessions, rate-limiting, telemetry, and
  LLM tools are out of scope for this phase — new SDD change required.
