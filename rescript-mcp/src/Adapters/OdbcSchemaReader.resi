// OdbcSchemaReader.resi — pure MSysRelationships reader
// REQ-S4 / D6 — relationship SQL, grouping, deterministic naming, graceful degradation

// ---------------------------------------------------------------------------
// IssueQuery — the query-issuance seam (makes the module testable)
// ---------------------------------------------------------------------------

type issueQuery = (~sql: string) => Promise.t<result<array<dict<JSON.t>>, Errors.t>>

// ---------------------------------------------------------------------------
// readRelationships — main entry point
// Executes MSysRelationships query, groups rows, returns Ok(list) or Ok([]) on error
// Uses Logging.warn for degradation warnings (mirrors python odbc_schema_reader.py pattern)
// ---------------------------------------------------------------------------

let readRelationships: (~query: issueQuery) => Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>>
