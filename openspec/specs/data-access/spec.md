# Data Access Specification

## Purpose

Executes basic SQL queries and exports data from Access databases.

## Requirements

### Requirement: Execute SQL Queries

The system MUST allow execution of SELECT queries against the database and return results as JSON.

#### Scenario: Executing a SELECT query
- GIVEN a valid connection
- WHEN the `execute_query` tool is called with a valid SQL string
- THEN the system returns the dataset as an array of JSON objects

#### Scenario: Executing an invalid query
- GIVEN a valid connection
- WHEN the `execute_query` tool is called with malformed SQL
- THEN the system returns an error response with the Access engine error message

### Requirement: Export Data

The system MUST provide functionality to export an entire table to structured formats.

#### Scenario: Exporting table to JSON
- GIVEN a valid connection
- WHEN the `export_table` tool is called for a specific table and format `json`
- THEN the system streams or returns the entire table content serialized as JSON