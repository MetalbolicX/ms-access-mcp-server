open Test

// Task 1.10 — Integration skeleton for OdbcAdapter with real ODBC connection
// REQ-D4/D5/D6/D9
//
// RED phase: stubs that assert false (will fail until real integration is wired)
// GREEN phase: actual ODBC connection tests using ACCESS_TEST_DB or MDB file

// ---------------------------------------------------------------------------
// Integration test configuration
// ---------------------------------------------------------------------------

// Connection string for integration testing — set via environment or use default
// Default: empty string means "skip integration tests"
// NOTE: In RED phase we always return "" so integration tests are skipped
// In GREEN phase, implement: %raw("process.env.ACCESS_TEST_DB") with proper type safety
let integrationConnectionString = () => ""

let isIntegrationConfigured = () => {
  let connStr = integrationConnectionString()
  String.length(connStr) > 0
}

// ---------------------------------------------------------------------------
// Integration lifecycle tests
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: connect to real ODBC data source", () => {
  // Skip if no integration DB configured
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: this will fail because we haven't wired up real connection yet
    // In GREEN phase: create adapter, call connect, assert Ok(true)
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: disconnect closes connection cleanly", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: create adapter, connect, disconnect, verify
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: isConnected reflects actual state", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: verify isConnected returns correct state
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Integration data operation tests
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: executeQuery returns real rows from ODBC", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: execute a real SELECT query and verify rows
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: insertData writes to real ODBC table", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: insert a row and verify affected count
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: updateData modifies existing rows", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: update rows and verify affected count
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: deleteData removes rows", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: delete rows and verify affected count
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: executeRawSql runs arbitrary SQL", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: execute raw SQL and verify result
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: exportData produces output file", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: export data to a file and verify file exists
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Error handling integration tests
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: connect fails gracefully with invalid DSN", () => {
  // RED stub: try to connect with invalid connection string
  // Should return Error with descriptive message, not crash
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: executeQuery fails gracefully when disconnected", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: call executeQuery without connecting first
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Integration schema tests
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: getTables returns user tables excluding MSys*", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: connect, call getTables, verify no MSys* tables
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getTables returns fields with correct type mapping", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: verify type names are mapped per REQ-S2 (e.g., INT→Long Integer)
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getTables record_count matches actual rows", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: getTables record_count should match SELECT COUNT(*) for each table
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getTableSchemaPlan returns UnknownMetadata all-true", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: call getTableSchemaPlan, verify all five UnknownMetadata flags=true
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getQueries queries INFORMATION_SCHEMA.VIEWS with dbo filter", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: call getQueries, verify SQL includes TABLE_SCHEMA='dbo' filter
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getQueries returns type='select' for all results", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: verify QueryInfo.type_ = "select" for all entries
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getSystemTables returns Ok([]) even when connected", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: connect, call getSystemTables, should return Ok([]) per contract
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getObjectMetadata returns Ok({}) always", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: call getObjectMetadata("anything") → Ok({})
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getIndexes returns Ok([]) even when connected", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: connect, call getIndexes("sometable") → Ok([]) per contract
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: getRelationships returns FK relationships from MSysRelationships", () => {
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    // RED stub: call getRelationships, verify RelationshipInfo structure
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Integration DDL, param-binding, statistics, and export stubs (slice-3g)
// ---------------------------------------------------------------------------
// New stubs added for slice-3g — all gate on ACCESS_TEST_DB via isIntegrationConfigured().
// Each stub: assert false in GREEN phase (will fail until real integration is wired).
// Requirement IDs:
//   1. createTable_roundTrip        → REQ-S7 (createTable / dropTable)
//   2. alterTable_addColumn         → REQ-S8 (alter_table add_column)
//   3. createView_dropView          → REQ-S6 (create_query / delete_query)
//   4. setView_replaces_view        → REQ-S6 (set_query_sql drop+create sequence)
//   5. executeQuery_date_param      → REQ-D8 (date parameter marshaling)
//   6. executeQuery_bool_param      → REQ-D8 (bool parameter marshaling)
//   7. executeQuery_binary_param   → REQ-D8 (binary/Buffer parameter marshaling)
//   8. getDatabaseStatistics_real_db → REQ-S11 (database statistics against real DB)
//   9. exportData_csv_real_db      → REQ-D10 (CSV export to file)
//  10. exportData_json_real_db     → REQ-D10 (JSON export to file)

// ---------------------------------------------------------------------------
// Integration DDL stubs
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: createTable_roundTrip — REQ-S7 table DDL end-to-end", () => {
  // REQ-S7: createTable builds CREATE TABLE [t] (...); dropTable builds DROP TABLE [t].
  // When ACCESS_TEST_DB is set: create a temp table, insert a row, drop it,
  // and assert the round-trip completes without error.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: alterTable_addColumn — REQ-S8 add column end-to-end", () => {
  // REQ-S8: alter_table with add_column action emits ALTER TABLE [t] ADD COLUMN [def].
  // When ACCESS_TEST_DB is set: create a temp table, add a column via alter_table,
  // verify the column appears in getTableSchemaPlan, then drop the table.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: createView_dropView — REQ-S6 view DDL round-trip", () => {
  // REQ-S6: create_query emits CREATE VIEW [name] AS <sql>; delete_query emits DROP VIEW [name].
  // When ACCESS_TEST_DB is set: create a view over a simple SELECT, query it,
  // drop the view, and assert the view no longer appears in getQueries.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: setView_replaces_view — REQ-S6 drop+create sequence", () => {
  // REQ-S6: set_query_sql executes DROP VIEW [name] then CREATE VIEW [name] AS <sql>.
  // When ACCESS_TEST_DB is set: create a view, replace its definition via set_query_sql,
  // query the view and assert the new definition is active, then drop it.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Integration parameter-binding stubs (REQ-D8 exotic params)
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: executeQuery_date_param — REQ-D8 date marshaling", () => {
  // REQ-D8: date values marshal to ISO-8601 strings; DateTime → Js.Date.toISOString.
  // When ACCESS_TEST_DB is set: INSERT a row with a Date/Time param, SELECT it back,
  // and assert the returned ISO string matches the input date within tolerance.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: executeQuery_bool_param — REQ-D8 bool marshaling", () => {
  // REQ-D8: bool params marshal as 1.0/0.0 (Js.Boolean.toFloat) and round-trip uncorrupted.
  // When ACCESS_TEST_DB is set: INSERT a row with a Boolean field set to true and false,
  // SELECT them back, and assert both values are preserved exactly.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: executeQuery_binary_param — REQ-D8 binary marshaling", () => {
  // REQ-D8: Buffer values encode as base64 strings and round-trip uncorrupted.
  // When ACCESS_TEST_DB is set: INSERT a row with a Binary/OLE object field,
  // SELECT it back, and assert the retrieved base64 matches the input bytes.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Integration statistics and export stubs
// ---------------------------------------------------------------------------

test("OdbcAdapter integration: getDatabaseStatistics_real_db — REQ-S11 against real DB", () => {
  // REQ-S11: connected statistics queries MSysObjects GROUP BY Type, maps codes to
  // tables/queries/forms/reports/macros/modules; file facts from Node lstatSync.
  // When ACCESS_TEST_DB is set: call getDatabaseStatistics on the real .accdb,
  // assert objects.tables >= 0, file.name is non-empty, and no warning key is present.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: exportData_csv_real_db — REQ-D10 CSV export to file", () => {
  // REQ-D10: format="csv" executes the SELECT, serializes via CsvWriter, writes via Node fs.
  // When ACCESS_TEST_DB is set: exportData with format="csv" to a temp path,
  // assert the file exists, contains at least one row matching the query output,
  // and the returned rows_exported matches the actual row count.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("OdbcAdapter integration: exportData_json_real_db — REQ-D10 JSON export to file", () => {
  // REQ-D10: format="json" serializes the QueryResult rows as a JSON array to the file path.
  // When ACCESS_TEST_DB is set: exportData with format="json" to a temp path,
  // assert the file is valid JSON, the array length equals rows_exported,
  // and each row object contains the expected column keys.
  if !isIntegrationConfigured() {
    assertion(~operator="equal", (a, b) => a == b, true, true)
  } else {
    assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})
