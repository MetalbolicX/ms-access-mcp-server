# Schema Explorer Specification

## Purpose

Reads tables, queries, relationships, and metadata from an Access database.

## Requirements

### Requirement: List Tables

The system MUST provide a tool to list all user tables in the connected database.

#### Scenario: Requesting tables list
- GIVEN a valid connection to an Access database
- WHEN the `get_tables` tool is called
- THEN the system returns an array of table names, excluding system tables (MSys*) unless explicitly requested

### Requirement: Get Table Schema

The system MUST return the column definitions, types, and primary keys for a specific table.

#### Scenario: Requesting specific table schema
- GIVEN a valid connection
- WHEN the `get_table_schema` tool is called with `table_name`
- THEN the system returns a list of fields with their Access data types, sizes, and required flags

### Requirement: List Relationships

The system MUST extract foreign key relationships defined in the database.

#### Scenario: Requesting relationships
- GIVEN a valid connection
- WHEN the `get_relationships` tool is called
- THEN the system returns an array of relationships indicating the source table, foreign table, and keys