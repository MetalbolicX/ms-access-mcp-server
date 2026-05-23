# Delta for access-mcp — Tool Execution Routing

## MODIFIED Requirements

### Requirement: Tool Execution Routing

The system MUST correctly route `tools/call` requests to the appropriate adapter or service, including access validation for sensitive tools. All COM-based tool calls MUST execute on a single dedicated STA thread to prevent thread-affinity failures.

(Previously: Correct routing without mention of COM threading guarantees)

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