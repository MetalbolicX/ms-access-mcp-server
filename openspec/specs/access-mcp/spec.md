# Access MCP Specification

## Purpose

The core server runtime and protocol handler for the Microsoft Access Model Context Protocol (MCP) server.

## Requirements

### Requirement: Server Initialization

The system MUST respond to MCP initialize requests with correct capabilities and server information across supported transports (stdio and HTTP).

#### Scenario: Client connects via stdio
- GIVEN the MCP server is running via stdio
- WHEN an MCP client sends an initialize request
- THEN the server returns protocol version, capabilities, and server info

#### Scenario: Client connects via HTTP
- GIVEN the MCP server is running via HTTP transport
- WHEN an MCP client sends an initialize request
- THEN the server returns protocol version, capabilities, and server info

### Requirement: Tool Discovery

The system MUST expose all implemented Access tools via the `tools/list` protocol endpoint.

#### Scenario: Client requests tools list
- GIVEN the server is initialized
- WHEN the client sends a `tools/list` request
- THEN the server returns a schema of all available tools including descriptions and required parameters

### Requirement: Tool Execution Routing

The system MUST correctly route `tools/call` requests to the appropriate adapter or service, including access validation for sensitive tools. All COM-based tool calls MUST execute on a single dedicated STA thread to prevent thread-affinity failures.

#### Scenario: Client calls a valid tool (COM)
- GIVEN the client has the tools list and is connected via WinComAdapter (use_com=true)
- WHEN the client sends a `tools/call` request for any COM-based tool (get_tables, execute_sql_script, get_forms, etc.)
- THEN the server routes the request to the Schema Explorer or COM Automation Service, which delegates to the WinComAdapter, which executes the operation on the dedicated STA thread and returns the result

#### Scenario: Client calls connect_access with disallowed path
- GIVEN the client is authenticated and calls `connect_access`
- WHEN `database_path` is outside allowed directories
- THEN the server rejects the request with a validation error

#### Scenario: Multiple concurrent COM tool calls
- GIVEN a client makes multiple COM tool calls in quick succession from different MCP sessions
- WHEN each call arrives at different async worker threads
- THEN all calls are serialized through the single STA thread dispatcher, execute in order, and each returns its result without thread-affinity errors