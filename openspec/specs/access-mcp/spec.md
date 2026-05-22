# Access MCP Specification

## Purpose

The core server runtime and protocol handler for the Microsoft Access Model Context Protocol (MCP) server.

## Requirements

### Requirement: Server Initialization

The system MUST respond to MCP initialize requests with correct capabilities and server information.

#### Scenario: Client connects
- GIVEN the MCP server is running via stdio
- WHEN an MCP client sends an initialize request
- THEN the server returns protocol version, capabilities, and server info

### Requirement: Tool Discovery

The system MUST expose all implemented Access tools via the `tools/list` protocol endpoint.

#### Scenario: Client requests tools list
- GIVEN the server is initialized
- WHEN the client sends a `tools/list` request
- THEN the server returns a schema of all available tools including descriptions and required parameters

### Requirement: Tool Execution Routing

The system MUST correctly route `tools/call` requests to the appropriate adapter or service.

#### Scenario: Client calls a valid tool
- GIVEN the client has the tools list
- WHEN the client sends a `tools/call` request for `get_tables`
- THEN the server routes the request to the Schema Explorer and returns the JSON-RPC response