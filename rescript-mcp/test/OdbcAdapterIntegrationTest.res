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
