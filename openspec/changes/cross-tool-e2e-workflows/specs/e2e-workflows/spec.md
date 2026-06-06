# E2E Workflows Specification

## Purpose

Define cross-tool end-to-end workflow tests that chain multiple MCP tools in realistic scenarios, validating the system as a whole across pool (Tier 1) and HTTP (Tier 2) boundaries.

## Requirements

### Requirement: CRUD Cycle Workflow

The system SHALL support a full create-read-update-delete cycle through chained MCP tool calls against a pool connection.

#### Scenario: Complete CRUD cycle via pool

- GIVEN a `pool_with_sqlite` fixture connected as "default"
- WHEN `create_table` is called with table name `__e2e_test_products` and field definitions
- AND `insert_data` is called with sample rows
- AND `query_data` is called with `SELECT * FROM __e2e_test_products`
- AND `get_table_schema` is called for `__e2e_test_products`
- THEN each tool call SHALL return `success: true`
- AND `query_data` results SHALL contain the inserted rows
- AND `get_table_schema` SHALL return columns matching the original field definitions

### Requirement: Data Export Workflow

The system SHALL export query results to file formats (CSV, JSON) and verify the exported file exists with correct content.

#### Scenario: Export table data to CSV

- GIVEN a `pool_with_sqlite` fixture and a temporary export directory
- WHEN `create_table` creates `__e2e_test_export` with sample fields
- AND `insert_data` inserts 3 rows
- AND `export_data` is called with `SELECT * FROM __e2e_test_export` to CSV format
- THEN the export file SHALL exist in the temporary directory
- AND the file content SHALL contain headers plus 3 data rows

#### Scenario: Export table data to JSON

- GIVEN a `pool_with_sqlite` fixture and a temporary export directory
- WHEN `create_table` creates `__e2e_test_export_json` with sample fields
- AND `insert_data` inserts 2 rows
- AND `export_data` is called with `SELECT * FROM __e2e_test_export_json` to JSON format
- THEN the export file SHALL exist and contain valid JSON with 2 records

### Requirement: Multi-Table Workflow

The system SHALL support creating and listing multiple tables within a single connection.

#### Scenario: Create and list multiple tables

- GIVEN a `pool_with_sqlite` fixture
- WHEN `create_table` creates `__e2e_test_orders`
- AND `create_table` creates `__e2e_test_items`
- AND `get_tables` is called
- THEN `get_tables` result SHALL include both `__e2e_test_orders` and `__e2e_test_items`

### Requirement: Multi-Connection Isolation

The system SHALL isolate operations between named connections so one connection cannot see another's tables.

#### Scenario: Cross-connection table isolation

- GIVEN a `pool_with_two_adapters` fixture with connections "prod" and "dev"
- WHEN `create_table` creates `__e2e_test_secret` on "prod"
- AND `get_tables` is called on "dev"
- THEN "dev" tables SHALL NOT include `__e2e_test_secret`

#### Scenario: Connection independence after disconnect

- GIVEN a `pool_with_two_adapters` fixture with connections "prod" and "dev"
- WHEN `disconnect` is called on "prod"
- AND `get_tables` is called on "dev"
- THEN "dev" SHALL still return its tables successfully

### Requirement: Schema and ER Diagram Workflow

The system SHALL return structured schema metadata, relationships, and ER diagram data through chained tool calls.

#### Scenario: Schema, relationships, and ER diagram retrieval

- GIVEN a `pool_with_sqlite` fixture with existing tables
- WHEN `get_table_schema` is called for `__meta`
- AND `get_relationships` is called
- AND `get_er_diagram` is called
- THEN `get_table_schema` SHALL return columns with `name` and `type` fields
- AND `get_relationships` SHALL return a list (empty or populated)
- AND `get_er_diagram` SHALL return a structure containing `nodes` and `edges`

### Requirement: HTTP Transport Workflow

The system SHALL support a complete JSON-RPC workflow over HTTP transport including initialization, tool listing, and tool invocation.

#### Scenario: Full HTTP JSON-RPC workflow

- GIVEN a `TestClient` with a valid API key and initialized session
- WHEN `initialize` is sent via JSON-RPC
- AND `tools/list` is sent to retrieve available tools
- AND `tools/call` for `create_table` is sent with table arguments
- AND `tools/call` for `insert_data` is sent with row data
- AND `tools/call` for `query_data` is sent with a SELECT query
- THEN each JSON-RPC response SHALL have `jsonrpc: "2.0"`
- AND each response SHALL contain a `result` field
- AND tool call responses SHALL contain expected operation data

### Requirement: Test Isolation and Cleanup

All E2E tests SHALL use isolated test data and clean up resources regardless of test outcome.

#### Scenario: Test data isolation

- GIVEN any E2E test
- WHEN test objects are created (tables, files)
- THEN all created table names SHALL use the `__e2e_test_` prefix
- AND cleanup SHALL execute in `finally` blocks
- AND cleanup failures SHALL not mask test failures

#### Scenario: Export file isolation

- GIVEN any E2E test that exports data
- WHEN export files are created
- THEN `tempfile.TemporaryDirectory` SHALL be used for isolation
- AND the directory SHALL be cleaned up after the test completes
