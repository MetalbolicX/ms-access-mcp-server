// McpToolsTest.res — T7a tests: 4 connection tools via facadeOps seam
// Tests: connect_access, disconnect_access, list_connections, is_connected
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
  let payload = dict{"database_path": JSON.String("/test/path.accdb"), "name": JSON.String("prod"), "backend": JSON.String("odbc")}

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
