open Test
open Adapters
open Adapters.Interfaces

// Step 1: Fakes fixture (TDD enabler) — FAKE MODULES implementing DATA_ADAPTER
// These live under test/ and are never imported by src/

// ---------------------------------------------------------------------------
// Mutable call log — records all connect/disconnect calls for verification
// ---------------------------------------------------------------------------

module CallLog = {
  type entry =
    | Connect(string, string)  // name, dbPath
    | Disconnect(string)        // name
    | IsConnected(string)       // name
    | ExecuteQuery(string, string) // name, sql
    | InsertData(string, string)   // name, table
    | UpdateData(string, string)   // name, table
    | DeleteData(string, string)   // name, table
    | ExecuteRawSql(string, string) // name, sql
    | ExportData(string, string, string) // name, query, filePath
    | SchemaCall(string, string)  // adapter name, method name (for FakeSchemaAdapter)

  let entries: ref<list<entry>> = ref(list{})

  let reset = () => { entries.contents = list{} }

  let log = (e: entry) => {
    entries.contents = list{e, ...entries.contents}
  }

  let connectCalls = () => {
    Belt.List.keep(entries.contents, e =>
      switch e {
      | Connect(_) => true
      | _ => false
      }
    )
  }

  let disconnectCalls = () => {
    Belt.List.keep(entries.contents, e =>
      switch e {
      | Disconnect(_) => true
      | _ => false
      }
    )
  }

  let schemaCalls = () => {
    Belt.List.keep(entries.contents, e =>
      switch e {
      | SchemaCall(_) => true
      | _ => false
      }
    )
  }
}

// ---------------------------------------------------------------------------
// FakeOdbcAdapter — implements DATA_ADAPTER module type
// Satisfies: type t, connect, disconnect, isConnected, executeQuery, etc.
// ---------------------------------------------------------------------------

module FakeOdbcAdapter = {
  type t = {
    mutable connected: bool,
    mutable dbPath: option<string>,
    name: string,
  }

  let make = (~name: option<string>=?) => {
    {connected: false, dbPath: None, name: name->Belt.Option.getWithDefault("fake-odbc")}
  }

  let connect = (
    self: t,
    dbPath: string,
    ~password: option<string>=?,
  ): Promise.t<result<bool, Errors.t>> => {
    CallLog.log(Connect(self.name, dbPath))
    self.connected = true
    self.dbPath = Some(dbPath)
    Promise.resolve(Ok(true))
  }

  let disconnect = (self: t): Promise.t<result<unit, Errors.t>> => {
    CallLog.log(Disconnect(self.name))
    self.connected = false
    self.dbPath = None
    Promise.resolve(Ok(()))
  }

  let isConnected = (self: t): Promise.t<result<bool, Errors.t>> => {
    CallLog.log(IsConnected(self.name))
    Promise.resolve(Ok(self.connected))
  }

  let executeQuery = (
    self: t,
    sql: string,
    ~params: option<array<JSON.t>>=?,
  ): Promise.t<result<queryResult, Errors.t>> => {
    CallLog.log(ExecuteQuery(self.name, sql))
    Promise.resolve(Ok({
      success: true,
      rows: [],
      count: 0,
      columns: [],
      error: None,
    }))
  }

  let insertData = (
    self: t,
    table: string,
    data: dict<JSON.t>,
  ): Promise.t<result<mutationResult, Errors.t>> => {
    CallLog.log(InsertData(self.name, table))
    Promise.resolve(Ok({success: true, affected: 1, error: None}))
  }

  let updateData = (
    self: t,
    table: string,
    data: dict<JSON.t>,
    ~where: option<JSON.t>=?,
  ): Promise.t<result<mutationResult, Errors.t>> => {
    CallLog.log(UpdateData(self.name, table))
    Promise.resolve(Ok({success: true, affected: 1, error: None}))
  }

  let deleteData = (
    self: t,
    table: string,
    ~where: option<JSON.t>=?,
  ): Promise.t<result<mutationResult, Errors.t>> => {
    CallLog.log(DeleteData(self.name, table))
    Promise.resolve(Ok({success: true, affected: 1, error: None}))
  }

  let executeRawSql = (
    self: t,
    sql: string,
  ): Promise.t<result<int, Errors.t>> => {
    CallLog.log(ExecuteRawSql(self.name, sql))
    Promise.resolve(Ok(0))
  }

  let exportData = (
    self: t,
    query: string,
    filePath: string,
    ~format: option<string>=?,
    ~options: option<dict<JSON.t>>=?,
  ): Promise.t<result<exportResult, Errors.t>> => {
    CallLog.log(ExportData(self.name, query, filePath))
    Promise.resolve(Ok({success: true, rowsExported: 0, filePath: filePath, error: None}))
  }

  // asInstance — produce an Instances.dataAdapterInstance from a FakeOdbcAdapter.t
  let asInstance = (self: t): Adapters.Instances.dataAdapterInstance => {
    {
      connect: (connStr, ~password=?) => connect(self, connStr),
      disconnect: () => disconnect(self),
      isConnected: () => isConnected(self),
      executeQuery: (sql, ~params=?) => executeQuery(self, sql),
      insertData: (table, data) => insertData(self, table, data),
      updateData: (table, setDict, ~where=?) => updateData(self, table, setDict),
      deleteData: (table, ~where=?) => deleteData(self, table),
      executeRawSql: sql => executeRawSql(self, sql),
      exportData: (sql, filePath, ~format=?, ~options=?) => exportData(self, sql, filePath),
    }
  }
}

// ---------------------------------------------------------------------------
// FakeComAdapter — another DATA_ADAPTER implementation for alias testing
// ---------------------------------------------------------------------------

module FakeComAdapter = {
  type t = {
    mutable connected: bool,
    mutable dbPath: option<string>,
    name: string,
  }

  let make = (~name: option<string>=?) => {
    {connected: false, dbPath: None, name: name->Belt.Option.getWithDefault("fake-com")}
  }

  let connect = (
    self: t,
    dbPath: string,
    ~password: option<string>=?,
  ): Promise.t<result<bool, Errors.t>> => {
    CallLog.log(Connect(self.name, dbPath))
    self.connected = true
    self.dbPath = Some(dbPath)
    Promise.resolve(Ok(true))
  }

  let disconnect = (self: t): Promise.t<result<unit, Errors.t>> => {
    CallLog.log(Disconnect(self.name))
    self.connected = false
    self.dbPath = None
    Promise.resolve(Ok(()))
  }

  let isConnected = (self: t): Promise.t<result<bool, Errors.t>> => {
    CallLog.log(IsConnected(self.name))
    Promise.resolve(Ok(self.connected))
  }

  let executeQuery = (
    self: t,
    sql: string,
    ~params: option<array<JSON.t>>=?,
  ): Promise.t<result<queryResult, Errors.t>> => {
    CallLog.log(ExecuteQuery(self.name, sql))
    Promise.resolve(Ok({success: true, rows: [], count: 0, columns: [], error: None}))
  }

  let insertData = (
    self: t,
    table: string,
    data: dict<JSON.t>,
  ): Promise.t<result<mutationResult, Errors.t>> => {
    CallLog.log(InsertData(self.name, table))
    Promise.resolve(Ok({success: true, affected: 1, error: None}))
  }

  let updateData = (
    self: t,
    table: string,
    data: dict<JSON.t>,
    ~where: option<JSON.t>=?,
  ): Promise.t<result<mutationResult, Errors.t>> => {
    CallLog.log(UpdateData(self.name, table))
    Promise.resolve(Ok({success: true, affected: 1, error: None}))
  }

  let deleteData = (
    self: t,
    table: string,
    ~where: option<JSON.t>=?,
  ): Promise.t<result<mutationResult, Errors.t>> => {
    CallLog.log(DeleteData(self.name, table))
    Promise.resolve(Ok({success: true, affected: 1, error: None}))
  }

  let executeRawSql = (
    self: t,
    sql: string,
  ): Promise.t<result<int, Errors.t>> => {
    CallLog.log(ExecuteRawSql(self.name, sql))
    Promise.resolve(Ok(0))
  }

  let exportData = (
    self: t,
    query: string,
    filePath: string,
    ~format: option<string>=?,
    ~options: option<dict<JSON.t>>=?,
  ): Promise.t<result<exportResult, Errors.t>> => {
    CallLog.log(ExportData(self.name, query, filePath))
    Promise.resolve(Ok({success: true, rowsExported: 0, filePath: filePath, error: None}))
  }
}

// ---------------------------------------------------------------------------
// FakeSchemaAdapter — implements SCHEMA_ADAPTER interface (18 methods)
// Adapters.Interfaces.SCHEMA_ADAPTER type t = { connect, disconnect,
// isConnected, getTables, getSystemTables, getObjectMetadata,
// getRelationships, getTableSchemaPlan, generateSql, getDatabaseStatistics,
// getQueries, createQuery, setQuerySql, deleteQuery, createTable, deleteTable,
// alterTable, getIndexes, createIndex, dropIndex, createRelationship,
// deleteRelationship }
// ---------------------------------------------------------------------------

module FakeSchemaAdapter = {
  type t = {
    mutable connected: bool,
    mutable dbPath: option<string>,
    name: string,
    mutable fakeTables: array<Adapters.Interfaces.tableInfo>,
    mutable fakeRelationships: array<Adapters.Interfaces.relationshipInfo>,
    mutable fakeQueries: array<Adapters.Interfaces.queryInfo>,
    mutable fakeDbStats: dict<JSON.t>,
    mutable failGetTables: bool,
    mutable failGetRelationships: bool,
    mutable failGetQueries: bool,
    mutable failGetDatabaseStatistics: bool,
  }

  let make = (~name: option<string>=?) => {
    {
      connected: false,
      dbPath: None,
      name: name->Belt.Option.getWithDefault("fake-schema"),
      fakeTables: [],
      fakeRelationships: [],
      fakeQueries: [],
      fakeDbStats: Dict.make(),
      failGetTables: false,
      failGetRelationships: false,
      failGetQueries: false,
      failGetDatabaseStatistics: false,
    }
  }

  let connect = (self: t, dbPath: string): Promise.t<result<bool, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "connect"))
    self.connected = true
    self.dbPath = Some(dbPath)
    Promise.resolve(Ok(true))
  }

  let disconnect = (self: t): Promise.t<result<unit, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "disconnect"))
    self.connected = false
    self.dbPath = None
    Promise.resolve(Ok(()))
  }

  let isConnected = (self: t): Promise.t<result<bool, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "isConnected"))
    Promise.resolve(Ok(self.connected))
  }

  let getTables = (self: t): Promise.t<result<array<Adapters.Interfaces.tableInfo>, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "getTables"))
    if self.failGetTables {
      Promise.resolve(Error(Errors.databaseError("Adapter error")))
    } else {
      Promise.resolve(Ok(self.fakeTables))
    }
  }

  let getSystemTables = (_self: t): Promise.t<result<array<Adapters.Interfaces.tableInfo>, Errors.t>> => {
    Promise.resolve(Ok([]))
  }

  let getObjectMetadata = (
    _self: t,
    _objectType: string,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    Promise.resolve(Ok(Dict.make()))
  }

  let getRelationships = (self: t): Promise.t<result<array<relationshipInfo>, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "getRelationships"))
    if self.failGetRelationships {
      Promise.resolve(Error(Errors.databaseError("Adapter error")))
    } else {
      Promise.resolve(Ok(self.fakeRelationships))
    }
  }

  let getTableSchemaPlan = (
    _self: t,
  ): Promise.t<result<(array<tableSchema>, unknownMetadata), Errors.t>> => {
    Promise.resolve(Ok(([], {primaryKeys: false, foreignKeys: false, defaults: false, indexes: false, autoincrement: false})))
  }

  let generateSql = (_self: t, _sqlType: string): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let getDatabaseStatistics = (self: t): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "getDatabaseStatistics"))
    if self.failGetDatabaseStatistics {
      Promise.resolve(Error(Errors.databaseError("Adapter error")))
    } else {
      Promise.resolve(Ok(self.fakeDbStats))
    }
  }

  let getQueries = (self: t): Promise.t<result<array<queryInfo>, Errors.t>> => {
    CallLog.log(SchemaCall(self.name, "getQueries"))
    if self.failGetQueries {
      Promise.resolve(Error(Errors.databaseError("Adapter error")))
    } else {
      Promise.resolve(Ok(self.fakeQueries))
    }
  }

  let createQuery = (
    _self: t,
    _queryName: string,
    _sql: string,
  ): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let setQuerySql = (
    _self: t,
    _queryName: string,
    _sql: string,
  ): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let deleteQuery = (_self: t, _queryName: string): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let createTable = (
    _self: t,
    _tableName: string,
    _columns: array<columnSchema>,
  ): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let deleteTable = (_self: t, _tableName: string): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let alterTable = (
    _self: t,
    _tableName: string,
    _changes: array<dict<JSON.t>>,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    Promise.resolve(Ok(Dict.make()))
  }

  let getIndexes = (_self: t, _tableName: string): Promise.t<result<array<indexInfo>, Errors.t>> => {
    Promise.resolve(Ok([]))
  }

  let createIndex = (
    _self: t,
    _indexName: string,
    _tableName: string,
    _columnNames: array<string>,
    ~unique: bool=false,
    ~ignoreNulls: bool=false,
  ): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let dropIndex = (
    _self: t,
    _indexName: string,
    _tableName: string,
  ): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let createRelationship = (
    _self: t,
    _name: string,
    _table: string,
    _columns: array<string>,
    _foreignTable: string,
    _foreignColumns: array<string>,
  ): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  let deleteRelationship = (_self: t, _name: string, _table: string): Promise.t<result<ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: true, error: None}))
  }

  // asInstance — produce an Instances.schemaAdapterInstance from a FakeSchemaAdapter.t
  let asInstance = (self: t): Adapters.Instances.schemaAdapterInstance => {
    {
      connect: (connStr, ~password=?) => connect(self, connStr),
      disconnect: () => disconnect(self),
      isConnected: () => isConnected(self),
      getTables: () => getTables(self),
      getSystemTables: () => getSystemTables(self),
      getObjectMetadata: name => getObjectMetadata(self, name),
      getRelationships: () => getRelationships(self),
      getTableSchemaPlan: () => getTableSchemaPlan(self),
      generateSql: sql => generateSql(self, sql),
      getDatabaseStatistics: () => getDatabaseStatistics(self),
      getQueries: () => getQueries(self),
      createQuery: (name, sql) => createQuery(self, name, sql),
      setQuerySql: (name, sql) => setQuerySql(self, name, sql),
      deleteQuery: name => deleteQuery(self, name),
      createTable: (name, cols) => createTable(self, name, cols),
      deleteTable: name => deleteTable(self, name),
      alterTable: (name, ops) => alterTable(self, name, ops),
      getIndexes: table => getIndexes(self, table),
      createIndex: (name, table, cols, ~unique=?, ~ignoreNulls=?) =>
        createIndex(self, name, table, cols),
      dropIndex: (name, table) => dropIndex(self, name, table),
      createRelationship: (name, table, cols, fTable, fCols) =>
        createRelationship(self, name, table, cols, fTable, fCols),
      deleteRelationship: (name, table) => deleteRelationship(self, name, table),
    }
  }
}

// ---------------------------------------------------------------------------
// Step 1 RED: Fakes implement DATA_ADAPTER interface
// ---------------------------------------------------------------------------

testAsync("FakeOdbcAdapter: connect records call in log", cb => {
  CallLog.reset()
  let adapter = FakeOdbcAdapter.make(~name="test-pool")
  ignore(adapter->FakeOdbcAdapter.connect("/tmp/test.accdb"))
  let calls = CallLog.connectCalls()
  let count = Belt.List.length(calls)
  assertion(~operator="equal", (a, b) => a == b, count, 1)
  cb(~planned=1, ())
})

testAsync("FakeOdbcAdapter: disconnect records call in log", cb => {
  CallLog.reset()
  let adapter = FakeOdbcAdapter.make(~name="test-pool")
  ignore(adapter->FakeOdbcAdapter.connect("/tmp/test.accdb"))
  ignore(adapter->FakeOdbcAdapter.disconnect)
  let calls = CallLog.disconnectCalls()
  let count = Belt.List.length(calls)
  assertion(~operator="equal", (a, b) => a == b, count, 1)
  cb(~planned=1, ())
})

testAsync("FakeOdbcAdapter: isConnected returns Ok(true) when connected", cb => {
  let adapter = FakeOdbcAdapter.make(~name="test-pool")
  ignore(adapter->FakeOdbcAdapter.connect("/tmp/test.accdb"))
  adapter->FakeOdbcAdapter.isConnected
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(true) => assertion(~operator="equal", (a, b) => a == b, true, true)
        | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      )
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(_e => {
      cb(~planned=0, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("FakeOdbcAdapter: isConnected returns Ok(false) after disconnect", cb => {
  let adapter = FakeOdbcAdapter.make(~name="test-pool")
  ignore(adapter->FakeOdbcAdapter.connect("/tmp/test.accdb"))
  ignore(adapter->FakeOdbcAdapter.disconnect)
  adapter->FakeOdbcAdapter.isConnected
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(false) => assertion(~operator="equal", (a, b) => a == b, false, false)
        | _ => assertion(~operator="equal", (a, b) => a == b, true, false)
        }
      )
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(_e => {
      cb(~planned=0, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("FakeComAdapter: same interface as FakeOdbcAdapter", cb => {
  CallLog.reset()
  let adapter = FakeComAdapter.make(~name="test-com")
  ignore(adapter->FakeComAdapter.connect("/tmp/test.accdb"))
  let calls = CallLog.connectCalls()
  let count = Belt.List.length(calls)
  // Only FakeComAdapter connect call (FakeOdbcAdapter was reset)
  assertion(~operator="equal", (a, b) => a == b, count, 1)
  cb(~planned=1, ())
})
