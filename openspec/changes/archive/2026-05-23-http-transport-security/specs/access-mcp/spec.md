# Delta for access-mcp

## MODIFIED Requirements

### Requirement: Server Initialization

The system MUST respond to MCP initialize requests with correct capabilities and server information across supported transports (stdio and HTTP).
(Previously: initialize behavior was defined only for stdio transport.)

#### Scenario: Client connects via stdio
- GIVEN the MCP server is running via stdio
- WHEN an MCP client sends an initialize request
- THEN the server returns protocol version, capabilities, and server info

#### Scenario: Client connects via HTTP
- GIVEN the MCP server is running via HTTP transport
- WHEN an MCP client sends an initialize request
- THEN the server returns protocol version, capabilities, and server info

### Requirement: Tool Execution Routing

The system MUST correctly route `tools/call` requests to the appropriate adapter or service, including access validation for sensitive tools.
(Previously: tool calls were routed without explicit transport-level authentication and path-validation constraints.)

#### Scenario: Client calls a valid tool
- GIVEN the client has the tools list
- WHEN the client sends a `tools/call` request for `get_tables`
- THEN the server routes the request to the Schema Explorer and returns the JSON-RPC response

#### Scenario: Client calls connect_access with disallowed path
- GIVEN the client is authenticated and calls `connect_access`
- WHEN `database_path` is outside allowed directories
- THEN the server rejects the request with a validation error
