# MS Access MCP Server

A Model Context Protocol (MCP) server for Microsoft Access that enables AI assistants to interact with Access databases through a complete set of tools.

## Features

- **Connection Management** — Connect/disconnect to `.accdb` and `.mdb` files
- **Schema Exploration** — List tables, queries, relationships, and column metadata
- **Data Access** — Execute SQL queries and export data
- **COM Automation** — Launch Access, manage forms, reports, macros, and modules
- **VBA Extensibility** — Read, write, and compile VBA code
- **Versioning** — Export forms/reports/VBA to text files for Git version control
- **Migration** — Extract schema and transfer data to other databases

## Architecture

```
┌─────────────────────────────────────────────┐
│              AI Assistant (MCP Client)       │
└──────────────────────┬──────────────────────┘
                       │ MCP Protocol (stdio)
                       ▼
┌─────────────────────────────────────────────┐
│           FastMCP Server (Python)           │
├─────────────────────────────────────────────┤
│  Tools: connect_access, get_tables,          │
│  execute_query, set_vba_code, migrate_to... │
├─────────────────────────────────────────────┤
│            Adapter Layer                     │
│  ┌─────────────┐    ┌─────────────┐         │
│  │ WinComAdapter│    │ OdbcAdapter │         │
│  │ (pywin32)   │    │ (pyodbc)    │         │
│  └──────┬──────┘    └──────┬──────┘         │
│         │                 │                  │
│         ▼                 ▼                  │
│  ┌─────────────────┐  ┌──────────┐         │
│  │ MS Access (COM) │  │ .accdb   │         │
│  └─────────────────┘  └──────────┘         │
└─────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| MCP Server | Python 3.11+ / FastMCP |
| COM Automation | pywin32 |
| Data Access | pyodbc (ACE OLEDB driver) |
| CLI | Typer |
| Frontend | Vue 3 + TypeScript + Element Plus |
| State Management | TanStack Query (Vue) |

## Setup

### Prerequisites

- Python 3.11 or higher
- Microsoft Access installed (for COM automation)
- Node.js 18+ (for frontend development)

### Backend Installation

```bash
cd ms-access-mcp-server
uv sync --extra windows  # Install with Windows dependencies (pywin32)
```

### Linux Server (data-only, no COM)

On Linux you can run the server with ODBC only. COM-dependent operations
(VBA editing, forms, reports, macros, compact/repair) are unavailable.

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt install unixodbc mdbtools mdbtools-odbc

# Register the mdbtools driver in unixODBC
# (create /etc/odbcinst.ini or add the section below)
cat <<'EOF' | sudo tee -a /etc/odbcinst.ini
[MDBTools]
Description = MDB Tools ODBC driver
Driver      = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbc.so
Setup       = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbcS.so
EOF

# Register the driver alias that OdbcAdapter expects
# (OdbcAdapter uses the Windows driver name; create a matching alias)
cat <<'EOF' | sudo tee /etc/odbc.ini
[Microsoft Access Driver (*.mdb, *.accdb)]
Description = MDB Tools driver
Driver      = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbc.so
Setup       = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbcS.so
EOF

# Install Python deps (no --extra windows needed)
uv sync

# Run the server
uv run python -m ms_access_mcp.mcp.server
```

On Linux, `export_vba`, `export_all`, and other VBA/form operations will
raise `NotImplementedError`. Use `--backend com` on Windows for those.

### Running the MCP Server

```bash
# Run directly (stdio transport for MCP clients)
uv run python -m ms_access_mcp.mcp.server

# Or use the CLI
uv run ms-access-mcp --help
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## MCP Tools

### Connection Management
- `connect_access` — Connect to a database
- `disconnect_access` — Disconnect from current database
- `is_connected` — Check connection status

### Schema & Data
- `get_tables` — List all tables
- `get_table_schema` — Get table column details
- `get_queries` — List saved queries
- `get_relationships` — List foreign key relationships
- `execute_query` — Run SQL queries

### COM Automation
- `launch_access` — Start Access application
- `close_access` — Close Access
- `get_forms`, `get_reports`, `get_macros`, `get_modules`
- `open_form`, `close_form`

### VBA Extensibility
- `get_vba_projects`, `get_vba_code`, `set_vba_code`
- `add_vba_procedure`, `compile_vba`

### Versioning
- `export_form_to_text`, `import_form_from_text`
- `export_report_to_text`, `import_report_from_text`
- `export_module` / `import_module` for VBA

### Migration
- `list_migration_targets` — Supported target databases
- `extract_schema` — Get portable schema definition
- `migrate_to` — Transfer schema and data
- `upload_sql_schema` — Import `.sql` DDL files

## Configuration

### Trust Center Settings

For VBA code manipulation, enable Trust Center access:

1. Open Access
2. File → Options → Trust Center
3. Trust Center Settings → Macro Settings
4. Check "Trust access to the VBA project object model"

### Python/Office Bitness

Ensure Python and Microsoft Office have matching bitness (both 32-bit or both 64-bit).

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright
```

## License

MIT