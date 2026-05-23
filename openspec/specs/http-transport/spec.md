# HTTP Transport Specification

## Purpose

Expose the MCP server over HTTP so non-local clients (for example Linux/WSL) can use Windows-hosted Access automation.

## Requirements

### Requirement: HTTP Transport Startup

The system MUST start an MCP HTTP endpoint on a configurable host and port.

#### Scenario: Start with defaults
- GIVEN host and port are not provided
- WHEN the server starts in HTTP transport mode
- THEN it SHALL bind to `127.0.0.1`
- AND it SHALL listen on port `8000`

#### Scenario: Start with explicit host and port
- GIVEN host and port are provided by configuration
- WHEN the server starts in HTTP transport mode
- THEN it SHALL bind to the configured host
- AND it SHALL listen on the configured port

### Requirement: HTTP Client Compatibility

The system MUST allow remote MCP clients to initialize and invoke tools through HTTP transport.

#### Scenario: Remote client initializes
- GIVEN the server is running in HTTP mode
- WHEN a remote MCP client sends `initialize`
- THEN the server SHALL return protocol and capability metadata

#### Scenario: Remote client calls tool
- GIVEN the client is initialized and authenticated
- WHEN the client sends `tools/call` for a valid tool
- THEN the server SHALL execute the tool and return its JSON result
