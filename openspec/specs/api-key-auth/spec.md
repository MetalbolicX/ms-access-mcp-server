# API Key Authentication Specification

## Purpose

Protect HTTP MCP endpoints so only authorized clients can call tools.

## Requirements

### Requirement: Bearer Token Enforcement

The system MUST require a valid Bearer token for HTTP MCP tool calls.

#### Scenario: Missing token
- GIVEN the server is running in HTTP mode
- WHEN a client calls a tool without `Authorization: Bearer ...`
- THEN the system SHALL reject the request
- AND it SHALL return an authentication error

#### Scenario: Invalid token
- GIVEN the server is running in HTTP mode
- WHEN a client calls a tool with an incorrect bearer token
- THEN the system SHALL reject the request
- AND it SHALL return an authentication error

#### Scenario: Valid token
- GIVEN the server is running in HTTP mode
- WHEN a client calls a tool with the configured bearer token
- THEN the system SHALL allow the request
- AND it SHALL execute the target tool

### Requirement: Secure Startup Configuration

The system MUST fail startup when API key authentication is not configured for HTTP mode.

#### Scenario: Missing API key at startup
- GIVEN HTTP mode is requested
- WHEN API key configuration is missing
- THEN server startup SHALL fail with a clear configuration error
