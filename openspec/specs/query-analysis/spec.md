# Query Analysis Specification

## Purpose

Provide SQL complexity analysis, schema index checks, and execution timing for MS Access queries — approximating EXPLAIN ANALYZE absent from Jet/ACE.

## Requirements

### Requirement: analyze_query Tool Interface

The system SHALL expose an `analyze_query` MCP tool accepting `sql` (string, required), `params` (list, optional), `connection_name` (string, optional), `dry_run` (bool, default false), `sample_size` (int, default 0). Returns JSON dict.

#### Scenario: Successful call

- GIVEN a valid SELECT and active connection
- WHEN `analyze_query` is called with defaults
- THEN response contains `complexity`, `timing`, `schema_analysis`, `recommendations`
- AND `complexity.score` is int 0-100

#### Scenario: Empty SQL

- GIVEN empty sql string
- WHEN `analyze_query` is called
- THEN error response with descriptive message is returned

### Requirement: SQL Complexity Scoring

The system SHALL parse SELECT queries via regex, scoring 0-100: simple (0-25), moderate (26-50), complex (51-75), heavy (76-100). Detects: joins, subqueries (correlated/regular), DISTINCT, ORDER BY, GROUP BY, aggregates, functions in WHERE, leading wildcard LIKE, cartesian joins, NOT IN/NOT EXISTS, OR, UNION vs UNION ALL.

#### Scenario: Simple query

- GIVEN `SELECT * FROM Customers WHERE ID = 1`
- WHEN analyzed
- THEN score is 0-25, category is "simple"

#### Scenario: Heavy query

- GIVEN 3+ joins, correlated subquery, leading LIKE, NOT IN
- WHEN analyzed
- THEN score is 76-100, category is "heavy", detected_issues lists each pattern

#### Scenario: Non-SELECT rejected

- GIVEN INSERT/UPDATE/DELETE statement
- WHEN analyzed
- THEN error indicates only SELECT supported

### Requirement: Execution Timing

The system SHOULD measure duration when dry_run=false via `SELECT COUNT(*) FROM (sql)` with `time.perf_counter()`.

#### Scenario: Successful timing

- GIVEN valid SELECT, dry_run=false
- WHEN executed
- THEN `timing.duration_ms` is positive float, `timing.row_count` reflects COUNT

#### Scenario: Execution failure

- GIVEN query referencing missing table
- WHEN wrapped query fails
- THEN `timing.error` contains DB error message, other results still present

### Requirement: Schema Index Analysis

The system SHALL check indexes on WHERE/JOIN columns. WinComAdapter: full lookup. OdbcAdapter: graceful fallback.

#### Scenario: Missing index (WinCom)

- GIVEN query filtering on unindexed `Customers.Email`
- WHEN schema analyzed with WinComAdapter
- THEN `missing_indexes` includes `Customers.Email`, recommendation suggests index

#### Scenario: OdbcAdapter fallback

- GIVEN OdbcAdapter connection
- WHEN schema analyzed
- THEN `index_check_available` is false, other results still returned

### Requirement: Performance Recommendations

The system SHOULD generate actionable recommendations from detected issues and missing indexes.

#### Scenario: Leading wildcard warning

- GIVEN `SELECT * FROM T WHERE Name LIKE '%foo%'`
- WHEN recommendations generated
- THEN warning about leading wildcard preventing index use

#### Scenario: Clean query

- GIVEN simple indexed query, no anti-patterns
- WHEN recommendations generated
- THEN empty list or "no issues" message

### Requirement: Dry Run Mode

The system MUST skip execution when dry_run=true.

#### Scenario: Dry run

- GIVEN any SELECT, dry_run=true
- WHEN executed
- THEN `timing` is null/absent, `complexity` and `schema_analysis` populated

### Requirement: Sample Mode

The system SHOULD support `sample_size`. When > 0 and dry_run=false, executes `SELECT TOP N * FROM (sql)`.

#### Scenario: Sample execution

- GIVEN query, sample_size=100, dry_run=false
- WHEN executed
- THEN `timing.sample_duration_ms` populated, `timing.sample_size` is 100

#### Scenario: Ignored in dry run

- GIVEN sample_size=50, dry_run=true
- WHEN executed
- THEN no sample query runs

### Requirement: Adapter Compatibility

The system MUST work with WinComAdapter (full) and OdbcAdapter (timing+complexity only).

#### Scenario: WinComAdapter full

- GIVEN WinComAdapter, dry_run=false
- WHEN executed
- THEN all sections present: complexity, timing, schema_analysis, recommendations

#### Scenario: OdbcAdapter partial

- GIVEN OdbcAdapter, dry_run=false
- WHEN executed
- THEN complexity and timing present, `schema_analysis.index_check_available` is false
