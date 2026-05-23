# Path Guard Specification

## Purpose

Restrict database file access to approved directories when clients invoke `connect_access`.

## Requirements

### Requirement: Allowed Directory Enforcement

The system MUST only allow database paths within configured allowed directories.

#### Scenario: Path inside allowed directory
- GIVEN allowed directories are configured
- WHEN `connect_access` receives a path under an allowed directory
- THEN the system SHALL permit connection attempt

#### Scenario: Path outside allowed directory
- GIVEN allowed directories are configured
- WHEN `connect_access` receives a path outside all allowed directories
- THEN the system SHALL reject the request
- AND it SHALL return a validation error

### Requirement: Path Traversal and UNC Rejection

The system MUST reject unsafe path forms.

#### Scenario: Path traversal attempt
- GIVEN allowed directories are configured
- WHEN `connect_access` receives a traversal path (for example `../../secret.accdb`)
- THEN the system SHALL reject the request

#### Scenario: UNC path attempt
- GIVEN allowed directories are configured
- WHEN `connect_access` receives a UNC path (for example `\\server\share\db.accdb`)
- THEN the system SHALL reject the request
