// McpToolsTest.res — T7a (4 connection) + T7b (4 CRUD) tests via facadeOps seam
// Tests: connect_access, disconnect_access, list_connections, is_connected,
//        query_data, insert_data, update_data, delete_data
// Each handler is called DIRECTLY with args dict (no SDK transport) and
// asserts the returned dict matches what facadeOps returned.

open Test
open Mcp.Tools

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

// jsonToDict: unwrap JSON.t Object variant to dict<JSON.t>
// Returns None for non-object JSON values.
let jsonToDict = (j: JSON.t): option<dict<JSON.t>> => {
  switch j {
  | JSON.Object(d) => Some(d)
  | _ => None
  }
}

// Spy: records call args and returns a canned response
// Used to verify handler extracts args correctly without hitting real Facade.
type spy = {
  mutable called: bool,
  mutable lastArgs: dict<JSON.t>,
  response: dict<JSON.t>,
}

let makeSpy = (response): spy => {
  {called: false, lastArgs: dict{}, response: response}
}

// ---------------------------------------------------------------------------
// connect_access tests
// facadeOps.connectAccess: (string, option<string>, option<string>, option<bool>, option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("connect_access handler: happy path with default args calls facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "connected": JSON.Boolean(true), "database": JSON.String("/test/path.accdb"), "name": JSON.String("default")})

  let ops = {
    connectAccess: Some((dbPath, name, password, useCom, backend) => {
      spy.called = true
      spy.lastArgs = dict{"dbPath": JSON.String(dbPath), "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"database_path": JSON.String("/test/path.accdb")}
  let result = Mcp.Tools.callConnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let dbPathVal = spy.lastArgs->Dict.get("dbPath")
  assertion(~operator="equal", (a, b) => a == b, dbPathVal, Some(JSON.String("/test/path.accdb")))
})

test("connect_access handler: named connection passes name to facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "name": JSON.String("prod")})

  let ops = {
    connectAccess: Some((dbPath, name, password, useCom, backend) => {
      spy.called = true
      spy.lastArgs = dict{"dbPath": JSON.String(dbPath), "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"database_path": JSON.String("/test/path.accdb"), "name": JSON.String("prod")}
  let result = Mcp.Tools.callConnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.String("prod")))
})

test("connect_access handler: use_com=true is accepted and forwarded", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: Some((dbPath, name, password, useCom, backend) => {
      spy.called = true
      spy.lastArgs = dict{"dbPath": JSON.String(dbPath), "useCom": switch useCom { | Some(b) => JSON.Boolean(b) | None => JSON.Null }}
      spy.response
    }),
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"database_path": JSON.String("/test/path.accdb"), "use_com": JSON.Boolean(true)}
  let result = Mcp.Tools.callConnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let useComVal = spy.lastArgs->Dict.get("useCom")
  assertion(~operator="equal", (a, b) => a == b, useComVal, Some(JSON.Boolean(true)))
})

test("connect_access handler: backend=com is accepted and forwarded", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: Some((dbPath, name, password, useCom, backend) => {
      spy.called = true
      spy.lastArgs = dict{"backend": switch backend { | Some(b) => JSON.String(b) | None => JSON.Null }}
      spy.response
    }),
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"database_path": JSON.String("/test/path.accdb"), "backend": JSON.String("com")}
  let result = Mcp.Tools.callConnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let backendVal = spy.lastArgs->Dict.get("backend")
  assertion(~operator="equal", (a, b) => a == b, backendVal, Some(JSON.String("com")))
})

// ---------------------------------------------------------------------------
// disconnect_access tests
// facadeOps.disconnectAccess: (option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("disconnect_access handler: named disconnect passes name to facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "message": JSON.String("Disconnected 'prod'")})

  let ops = {
    connectAccess: None,
    disconnectAccess: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"name": JSON.String("prod")}
  let result = Mcp.Tools.callDisconnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.String("prod")))
})

test("disconnect_access handler: default name is None (omitted)", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callDisconnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  // Default name is None (omitted), not Some("default")
  // Default name is None (omitted) → stored as JSON.Null
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.Null))
})

test("disconnect_access handler: unknown name returns success:false envelope from facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(false), "error": JSON.String("Connection 'ghost' not found")})

  let ops = {
    connectAccess: None,
    disconnectAccess: Some(name => {
      spy.called = true
      spy.response
    }),
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"name": JSON.String("ghost")}
  let result = Mcp.Tools.callDisconnectAccess(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  // The spy returns success:false — handler should return it verbatim
  let successVal = switch jsonToDict(result) {
    | Some(d) => Dict.get(d, "success")
    | None => None
  }
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
})

// ---------------------------------------------------------------------------
// list_connections tests
// facadeOps.listConnections: unit => dict<JSON.t>
// ---------------------------------------------------------------------------

test("list_connections handler: empty pool returns success:true, connections:{}, count:0, active:default", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "connections": JSON.Object(dict{}), "count": JSON.Number(0.0), "active": JSON.String("default")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: Some(() => {
      spy.called = true
      spy.response
    }),
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callListConnections(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  let countVal = Dict.get(d, "count")
  let activeVal = Dict.get(d, "active")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(true)))
  assertion(~operator="equal", (a, b) => a == b, countVal, Some(JSON.Number(0.0)))
  assertion(~operator="equal", (a, b) => a == b, activeVal, Some(JSON.String("default")))
})

test("list_connections handler: with one connection returns full dict including created_at", () => {
  let createdAtSpy = JSON.String("2026-08-26T10:00:00.000Z")
  let spy = makeSpy(dict{
    "success": JSON.Boolean(true),
    "connections": JSON.Object(dict{"default": JSON.Object(dict{"database": JSON.String("/test/path.accdb"), "adapter_type": JSON.String("odbc"), "connected": JSON.Boolean(true), "created_at": createdAtSpy})}),
    "count": JSON.Number(1.0),
    "active": JSON.String("default"),
  })

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: Some(() => {
      spy.called = true
      spy.response
    }),
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callListConnections(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let connectionsObj = switch Dict.get(d, "connections") {
  | Some(JSON.Object(d)) => Some(d)
  | _ => None
  }
  let hasDefault = switch connectionsObj {
  | Some(d) => Dict.has(d, "default")
  | None => false
  }
  assertion(~operator="equal", (a, b) => a == b, hasDefault, true)
  let countVal = Dict.get(d, "count")
  assertion(~operator="equal", (a, b) => a == b, countVal, Some(JSON.Number(1.0)))
})

// ---------------------------------------------------------------------------
// is_connected tests
// facadeOps.isConnected: (option<string>) => dict<JSON.t> (sync)
// ---------------------------------------------------------------------------

test("is_connected handler: empty pool returns connected:false", () => {
  let spy = makeSpy(dict{"connected": JSON.Boolean(false), "database": JSON.Null, "name": JSON.String("default")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callIsConnected(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let connectedVal = Dict.get(d, "connected")
  assertion(~operator="equal", (a, b) => a == b, connectedVal, Some(JSON.Boolean(false)))
})

test("is_connected handler: after connect returns connected:true", () => {
  let spy = makeSpy(dict{"connected": JSON.Boolean(true), "database": JSON.String("/test/path.accdb"), "name": JSON.String("default")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: Some(name => {
      spy.called = true
      spy.response
    }),
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callIsConnected(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let connectedVal = Dict.get(d, "connected")
  assertion(~operator="equal", (a, b) => a == b, connectedVal, Some(JSON.Boolean(true)))
})

// ---------------------------------------------------------------------------
// Schema validation tests (via validateToolInputWrap)
// ---------------------------------------------------------------------------

test("connect_access input schema: missing database_path returns Invalid envelope", () => {
  // Pass-through schema: SDK doesn't validate. Handler-level validation:
  // empty dbPath → facadeOps called with "" → returns error envelope.
  let ops = {
    connectAccess: Some((dbPath, name, password, useCom, backend) => {
      dict{"success": JSON.Boolean(false), "error": JSON.String("dbPath is empty")}
    }),
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }
  let args = dict{"name": JSON.String("prod")}
  let result = Mcp.Tools.callConnectAccess(args, ops)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})

test("connect_access input schema: valid input passes validation", () => {
  let schema = Mcp.Tools.connectAccessSchema
  let payload = JSON.Object(dict{
    "database_path": JSON.String("/test/path.accdb"),
    "name": JSON.String("prod"),
    "backend": JSON.String("odbc"),
  })

  let threw = ref(false)
  let resultData = ref(JSON.Null)

  %raw(`
    (fn, schema, payload, threwRef, dataRef) => {
      try {
        const result = fn(null, schema, payload);
        threwRef.contents = false;
        dataRef.contents = result;
      } catch (e) {
        threwRef.contents = true;
      }
    }
  `)(Bindings.McpSdk.validateToolInputWrap, schema, payload, threw, resultData)

  assertion(~operator="equal", (a, b) => a == b, threw.contents, false)
})

// ---------------------------------------------------------------------------
// query_data tests
// facadeOps.queryData: (string, option<array<JSON.t>>, option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("query_data handler: happy path calls facadeOps with sql and default params", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "rows": JSON.Array([]), "count": JSON.Number(0.0), "columns": JSON.Array([])})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: Some((sql, params, name) => {
      spy.called = true
      spy.lastArgs = dict{
        "sql": JSON.String(sql),
        "params": switch params { | Some(p) => JSON.Array(p) | None => JSON.Null },
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
      }
      spy.response
    }),
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("SELECT * FROM Users")}
  let result = Mcp.Tools.callQueryData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let sqlVal = spy.lastArgs->Dict.get("sql")
  assertion(~operator="equal", (a, b) => a == b, sqlVal, Some(JSON.String("SELECT * FROM Users")))
  let paramsVal = spy.lastArgs->Dict.get("params")
  assertion(~operator="equal", (a, b) => a == b, paramsVal, Some(JSON.Null))
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.Null))
})

test("query_data handler: with params array forwarded correctly", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "rows": JSON.Array([]), "count": JSON.Number(0.0), "columns": JSON.Array([])})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: Some((sql, params, name) => {
      spy.called = true
      spy.lastArgs = dict{
        "sql": JSON.String(sql),
        "params": switch params { | Some(p) => JSON.Array(p) | None => JSON.Null },
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
      }
      spy.response
    }),
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("SELECT * FROM Users WHERE id = ?"), "params": JSON.Array([JSON.Number(1.0)]), "connection_name": JSON.String("prod")}
  let result = Mcp.Tools.callQueryData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let paramsVal = spy.lastArgs->Dict.get("params")
  assertion(~operator="equal", (a, b) => a == b, paramsVal !== None, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.String("prod")))
})

test("query_data handler: missing sql returns error envelope", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(false), "error": JSON.String("sql is required")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: Some((sql, params, name) => {
      spy.called = true
      spy.response
    }),
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callQueryData(args, ops)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})

// ---------------------------------------------------------------------------
// insert_data tests
// facadeOps.insertData: (string, JSON.t, option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("insert_data handler: single record calls facadeOps with table and data object", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "affected": JSON.Number(1.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: Some((table, data, name) => {
      spy.called = true
      spy.lastArgs = dict{
        "table": JSON.String(table),
        "data": data,
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
      }
      spy.response
    }),
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"table_name": JSON.String("Users"), "data": JSON.Object(dict{"name": JSON.String("Alice"), "email": JSON.String("alice@example.com")})}
  let result = Mcp.Tools.callInsertData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let tableVal = spy.lastArgs->Dict.get("table")
  assertion(~operator="equal", (a, b) => a == b, tableVal, Some(JSON.String("Users")))
  let dataVal = spy.lastArgs->Dict.get("data")
  assertion(~operator="equal", (a, b) => a == b, dataVal !== None, true)
})

test("insert_data handler: batch of records calls facadeOps with data array", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "affected": JSON.Number(2.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: Some((table, data, name) => {
      spy.called = true
      spy.lastArgs = dict{"table": JSON.String(table), "data": data}
      spy.response
    }),
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "data": JSON.Array([
      JSON.Object(dict{"name": JSON.String("Alice"), "email": JSON.String("alice@example.com")}),
      JSON.Object(dict{"name": JSON.String("Bob"), "email": JSON.String("bob@example.com")}),
    ]),
  }
  let result = Mcp.Tools.callInsertData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let dataVal = spy.lastArgs->Dict.get("data")
  switch dataVal {
  | Some(JSON.Array(arr)) => assertion(~operator="equal", (a, b) => a == b, Array.length(arr), 2)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("insert_data handler: disconnected returns error envelope from facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(false), "error": JSON.String("Not connected to database")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: Some((table, data, name) => {
      spy.called = true
      spy.response
    }),
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"table_name": JSON.String("Users"), "data": JSON.Object(dict{"name": JSON.String("Alice")})}
  let result = Mcp.Tools.callInsertData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
})

// ---------------------------------------------------------------------------
// update_data tests
// facadeOps.updateData: (string, dict<JSON.t>, option<dict<JSON.t>>, option<string>, option<bool>, option<bool>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("update_data handler: object where_dict passed through to facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "affected": JSON.Number(1.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: Some((table, setDict, whereDict, name, confirm, dryRun) => {
      spy.called = true
      spy.lastArgs = dict{
        "table": JSON.String(table),
        "setDict": JSON.Object(setDict),
        "whereDict": switch whereDict { | Some(d) => JSON.Object(d) | None => JSON.Null },
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
        "confirm": JSON.Boolean(confirm->Option.getWithDefault(false)),
        "dryRun": JSON.Boolean(dryRun->Option.getWithDefault(false)),
      }
      spy.response
    }),
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "set_dict": JSON.Object(dict{"name": JSON.String("Updated")}),
    "where_dict": JSON.Object(dict{"id": JSON.Number(1.0)}),
  }
  let result = Mcp.Tools.callUpdateData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let tableVal = spy.lastArgs->Dict.get("table")
  assertion(~operator="equal", (a, b) => a == b, tableVal, Some(JSON.String("Users")))
  let whereDictVal = spy.lastArgs->Dict.get("whereDict")
  assertion(~operator="equal", (a, b) => a == b, whereDictVal !== None && whereDictVal !== Some(JSON.Null), true)
})

test("update_data handler: string where_dict normalized to __raw__ sentinel", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "affected": JSON.Number(1.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: Some((table, setDict, whereDict, name, confirm, dryRun) => {
      spy.called = true
      spy.lastArgs = dict{
        "table": JSON.String(table),
        "whereDict": switch whereDict { | Some(d) => JSON.Object(d) | None => JSON.Null },
      }
      spy.response
    }),
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "set_dict": JSON.Object(dict{"name": JSON.String("Updated")}),
    "where_dict": JSON.String("id > 5"),
  }
  let result = Mcp.Tools.callUpdateData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let whereDictVal = spy.lastArgs->Dict.get("whereDict")
  // Should be normalized to {"__raw__": "id > 5"}
  switch whereDictVal {
  | Some(JSON.Object(d)) => {
      let rawVal = Dict.get(d, "__raw__")
      assertion(~operator="equal", (a, b) => a == b, rawVal, Some(JSON.String("id > 5")))
    }
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("update_data handler: empty string where_dict returns error envelope", () => {
  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "set_dict": JSON.Object(dict{"name": JSON.String("Updated")}),
    "where_dict": JSON.String(""),
  }
  let result = Mcp.Tools.callUpdateData(args, ops)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})

test("update_data handler: missing where_dict without confirm returns error envelope", () => {
  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "set_dict": JSON.Object(dict{"name": JSON.String("Updated")}),
  }
  let result = Mcp.Tools.callUpdateData(args, ops)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})

test("update_data handler: dry_run=true returns dry_run envelope without adapter call", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: Some((table, setDict, whereDict, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "set_dict": JSON.Object(dict{"name": JSON.String("Updated")}),
    "where_dict": JSON.String("id > 5"),
    "dry_run": JSON.Boolean(true),
  }
  let result = Mcp.Tools.callUpdateData(args, ops)

  // dry_run should short-circuit before calling facadeOps.updateData
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let dryRunVal = Dict.get(d, "dry_run")
  assertion(~operator="equal", (a, b) => a == b, dryRunVal, Some(JSON.Boolean(true)))
})

// ---------------------------------------------------------------------------
// delete_data tests
// facadeOps.deleteData: (string, dict<JSON.t>, option<string>, option<bool>, option<bool>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("delete_data handler: object where_dict passed through to facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "affected": JSON.Number(1.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: Some((table, whereDict, name, confirm, dryRun) => {
      spy.called = true
      spy.lastArgs = dict{
        "table": JSON.String(table),
        "whereDict": JSON.Object(whereDict),
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
        "confirm": JSON.Boolean(confirm->Option.getWithDefault(false)),
        "dryRun": JSON.Boolean(dryRun->Option.getWithDefault(false)),
      }
      spy.response
    }),
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "where_dict": JSON.Object(dict{"id": JSON.Number(1.0)}),
  }
  let result = Mcp.Tools.callDeleteData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let tableVal = spy.lastArgs->Dict.get("table")
  assertion(~operator="equal", (a, b) => a == b, tableVal, Some(JSON.String("Users")))
})

test("delete_data handler: string where_dict normalized to __raw__ sentinel", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "affected": JSON.Number(1.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: Some((table, whereDict, name, confirm, dryRun) => {
      spy.called = true
      spy.lastArgs = dict{
        "whereDict": JSON.Object(whereDict),
      }
      spy.response
    }),
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "where_dict": JSON.String("id > 5"),
  }
  let result = Mcp.Tools.callDeleteData(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let whereDictVal = spy.lastArgs->Dict.get("whereDict")
  switch whereDictVal {
  | Some(JSON.Object(d)) => {
      let rawVal = Dict.get(d, "__raw__")
      assertion(~operator="equal", (a, b) => a == b, rawVal, Some(JSON.String("id > 5")))
    }
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("delete_data handler: missing where rejected even with confirm=true", () => {
  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "confirm": JSON.Boolean(true),
  }
  let result = Mcp.Tools.callDeleteData(args, ops)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})

test("delete_data handler: dry_run=true returns dry_run envelope without adapter call", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: Some((table, whereDict, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{
    "table_name": JSON.String("Users"),
    "where_dict": JSON.String("id > 5"),
    "dry_run": JSON.Boolean(true),
  }
  let result = Mcp.Tools.callDeleteData(args, ops)

  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let dryRunVal = Dict.get(d, "dry_run")
  assertion(~operator="equal", (a, b) => a == b, dryRunVal, Some(JSON.Boolean(true)))
})

// ---------------------------------------------------------------------------
// get_tables tests
// facadeOps.getTables: (option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("get_tables handler: happy path calls facadeOps with default connection", () => {
  let spy = makeSpy(dict{
    "success": JSON.Boolean(true),
    "tables": JSON.Array([
      JSON.Object(dict{
        "name": JSON.String("Users"),
        "fields": JSON.Array([]),
        "recordCount": JSON.Number(0.0),
        "primaryKey": JSON.Null,
      }),
    ]),
    "count": JSON.Number(1.0),
  })

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callGetTables(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(true)))
  let countVal = Dict.get(d, "count")
  assertion(~operator="equal", (a, b) => a == b, countVal, Some(JSON.Number(1.0)))
})

test("get_tables handler: with connection_name forwarded correctly", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "tables": JSON.Array([]), "count": JSON.Number(0.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"connection_name": JSON.String("prod")}
  let result = Mcp.Tools.callGetTables(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.String("prod")))
})

test("get_tables handler: disconnected returns error envelope from facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(false), "error": JSON.String("Not connected to database")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: Some(name => {
      spy.called = true
      spy.response
    }),
    getTableSchema: None,
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callGetTables(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
})

// ---------------------------------------------------------------------------
// get_table_schema tests
// facadeOps.getTableSchema: (string, option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("get_table_schema handler: happy path calls facadeOps with table_name and default connection", () => {
  let spy = makeSpy(dict{
    "success": JSON.Boolean(true),
    "table": JSON.Object(dict{
      "name": JSON.String("Users"),
      "fields": JSON.Array([
        JSON.Object(dict{
          "name": JSON.String("id"),
          "type": JSON.String("LongInteger"),
          "size": JSON.Number(4.0),
          "required": JSON.Boolean(false),
          "allowZeroLength": JSON.Boolean(false),
          "defaultValue": JSON.Null,
          "isAutoincrement": JSON.Boolean(true),
        }),
      ]),
      "recordCount": JSON.Number(0.0),
      "primaryKey": JSON.String("id"),
    }),
  })

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: Some((tableName, name) => {
      spy.called = true
      spy.lastArgs = dict{
        "tableName": JSON.String(tableName),
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
      }
      spy.response
    }),
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"table_name": JSON.String("Users")}
  let result = Mcp.Tools.callGetTableSchema(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let tableVal = spy.lastArgs->Dict.get("tableName")
  assertion(~operator="equal", (a, b) => a == b, tableVal, Some(JSON.String("Users")))
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(true)))
})

test("get_table_schema handler: with connection_name forwarded correctly", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "table": JSON.Object(dict{})})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: Some((tableName, name) => {
      spy.called = true
      spy.lastArgs = dict{
        "tableName": JSON.String(tableName),
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
      }
      spy.response
    }),
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"table_name": JSON.String("Users"), "connection_name": JSON.String("prod")}
  let result = Mcp.Tools.callGetTableSchema(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.String("prod")))
})

test("get_table_schema handler: missing table returns not-found error from facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(false), "error": JSON.String("Table 'GhostTable' not found")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: Some((tableName, name) => {
      spy.called = true
      spy.response
    }),
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"table_name": JSON.String("GhostTable")}
  let result = Mcp.Tools.callGetTableSchema(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  let errorVal = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
  assertion(~operator="equal", (a, b) => a == b, errorVal !== None, true)
})

test("get_table_schema handler: missing table_name returns error envelope without calling facade", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: Some((tableName, name) => {
      spy.called = true
      spy.response
    }),
    getQueries: None,
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callGetTableSchema(args, ops)

  // facade should NOT be called when table_name is missing
  assertion(~operator="equal", (a, b) => a == b, spy.called, false)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})

// ---------------------------------------------------------------------------
// get_queries tests
// facadeOps.getQueries: (option<string>) => dict<JSON.t>
// ---------------------------------------------------------------------------

test("get_queries handler: happy path calls facadeOps with default connection", () => {
  let spy = makeSpy(dict{
    "success": JSON.Boolean(true),
    "queries": JSON.Array([
      JSON.Object(dict{
        "name": JSON.String("qry_ActiveUsers"),
        "sql": JSON.String("SELECT * FROM Users WHERE active = True"),
        "type": JSON.String("select"),
      }),
    ]),
    "count": JSON.Number(1.0),
  })

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callGetQueries(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(true)))
  let countVal = Dict.get(d, "count")
  assertion(~operator="equal", (a, b) => a == b, countVal, Some(JSON.Number(1.0)))
})

test("get_queries handler: with connection_name forwarded correctly", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "queries": JSON.Array([]), "count": JSON.Number(0.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: Some(name => {
      spy.called = true
      spy.lastArgs = dict{"name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null }}
      spy.response
    }),
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"connection_name": JSON.String("prod")}
  let result = Mcp.Tools.callGetQueries(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let nameVal = spy.lastArgs->Dict.get("name")
  assertion(~operator="equal", (a, b) => a == b, nameVal, Some(JSON.String("prod")))
})

test("get_queries handler: disconnected returns error envelope from facadeOps", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(false), "error": JSON.String("Not connected to database")})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: Some(name => {
      spy.called = true
      spy.response
    }),
    executeRawSql: None,
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callGetQueries(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
})

// ---------------------------------------------------------------------------
// execute_raw_sql tests
// facadeOps.executeRawSql: (string, option<string>, option<bool>, option<bool>) => dict<JSON.t>
// dangerous pattern: ^\s*(drop|delete|update)\b (case-insensitive)
// ---------------------------------------------------------------------------

test("execute_raw_sql handler: happy path INSERT calls facadeOps without confirm", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true), "rows_affected": JSON.Number(1.0)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: Some((sql, name, confirm, dryRun) => {
      spy.called = true
      spy.lastArgs = dict{
        "sql": JSON.String(sql),
        "name": switch name { | Some(n) => JSON.String(n) | None => JSON.Null },
        "confirm": JSON.Boolean(confirm->Option.getWithDefault(false)),
        "dryRun": JSON.Boolean(dryRun->Option.getWithDefault(false)),
      }
      spy.response
    }),
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("INSERT INTO Users (name) VALUES ('Alice')")}
  let result = Mcp.Tools.callExecuteRawSql(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, true)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(true)))
})

test("execute_raw_sql handler: dry_run=true returns dry_run envelope without calling facade", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: Some((sql, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("DROP TABLE Users"), "dry_run": JSON.Boolean(true)}
  let result = Mcp.Tools.callExecuteRawSql(args, ops)

  // facade should NOT be called for dry_run
  assertion(~operator="equal", (a, b) => a == b, spy.called, false)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let dryRunVal = Dict.get(d, "dry_run")
  let sqlVal = Dict.get(d, "sql")
  assertion(~operator="equal", (a, b) => a == b, dryRunVal, Some(JSON.Boolean(true)))
  assertion(~operator="equal", (a, b) => a == b, sqlVal, Some(JSON.String("DROP TABLE Users")))
})

test("execute_raw_sql handler: dangerous DROP without confirm returns error guard envelope", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: Some((sql, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("DROP TABLE Users")}
  let result = Mcp.Tools.callExecuteRawSql(args, ops)

  // facade should NOT be called - dangerous SQL blocked
  assertion(~operator="equal", (a, b) => a == b, spy.called, false)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  let errorVal = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
  assertion(~operator="equal", (a, b) => a == b, errorVal !== None, true)
})

test("execute_raw_sql handler: dangerous DELETE without confirm returns error guard envelope", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: Some((sql, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("DELETE FROM Users WHERE id = 1")}
  let result = Mcp.Tools.callExecuteRawSql(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, false)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
})

test("execute_raw_sql handler: dangerous UPDATE without confirm returns error guard envelope", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: Some((sql, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{"sql": JSON.String("UPDATE Users SET name = 'Bob' WHERE id = 1")}
  let result = Mcp.Tools.callExecuteRawSql(args, ops)

  assertion(~operator="equal", (a, b) => a == b, spy.called, false)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let successVal = Dict.get(d, "success")
  assertion(~operator="equal", (a, b) => a == b, successVal, Some(JSON.Boolean(false)))
})

test("execute_raw_sql handler: missing sql returns error envelope without calling facade", () => {
  let spy = makeSpy(dict{"success": JSON.Boolean(true)})

  let ops = {
    connectAccess: None,
    disconnectAccess: None,
    listConnections: None,
    isConnected: None,
    setActiveConnection: None,
    getActiveConnection: None,
    queryData: None,
    insertData: None,
    updateData: None,
    deleteData: None,
    getTables: None,
    getTableSchema: None,
    getQueries: None,
    executeRawSql: Some((sql, name, confirm, dryRun) => {
      spy.called = true
      spy.response
    }),
    getRelationships: None,
    getDatabaseStatistics: None,
    exportData: None,
  }

  let args = dict{}
  let result = Mcp.Tools.callExecuteRawSql(args, ops)

  // facade should NOT be called when sql is missing
  assertion(~operator="equal", (a, b) => a == b, spy.called, false)
  let d = switch jsonToDict(result) {
    | Some(d) => d
    | None => dict{}
  }
  let hasError = Dict.get(d, "error")
  assertion(~operator="equal", (a, b) => a == b, hasError !== None, true)
})
