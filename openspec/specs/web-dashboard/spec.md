# Web Dashboard Specification

## Purpose

A minimal Vue 3 UI for monitoring server status, connections, and background jobs.

## Requirements

### Requirement: Server Status Display

The system MUST display the current MCP server connection status and loaded database.

#### Scenario: Dashboard loads
- GIVEN the FastAPI backend is running
- WHEN a user opens the Vue frontend
- THEN the dashboard displays "Connected" and the current database path

### Requirement: Job Monitoring

The system MUST provide a view to monitor long-running tasks like migrations.

#### Scenario: Migration job running
- GIVEN an active migration task
- WHEN the user navigates to the Job Monitor tab
- THEN a progress bar reflects the current percentage of completion polled from the API