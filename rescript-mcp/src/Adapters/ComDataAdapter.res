// ComDataAdapter.res — DATA_ADAPTER + SCHEMA_ADAPTER implementation via winax/DAO
// Mirrors Python win_com_adapter.py (ComDataAdapter -> WinComAdapter via DaoAdapter)
// COM calls run on Node's single-threaded event loop; ComDispatch (STA serializer)
// is retained for future STA needs, currently test-only.

open Interfaces

// ---------------------------------------------------------------------------
// Platform check — non-Windows returns a platform error envelope
// ---------------------------------------------------------------------------

let _isWindows: unit => bool = () => {
  Bindings.TsBridge.isWindows()
}

// ---------------------------------------------------------------------------
// Internal types
// ---------------------------------------------------------------------------

type comDataAdapterState = {
  mutable isConnected: bool,
  mutable dbPath: option<string>,
  mutable session: option<ComSession.t>,
}

// ---------------------------------------------------------------------------
// Make — factory for the internal state
// ---------------------------------------------------------------------------

let _make: unit => comDataAdapterState = () => {
  {
    isConnected: false,
    dbPath: None,
    session: None,
  }
}

// ---------------------------------------------------------------------------
// Platform error envelope — same shape as Python's COM-unavailable error
// ---------------------------------------------------------------------------

let _platformError: string => result<'a, Errors.t> = (
  msg: string) => {
  Error(Errors.databaseError("Platform not supported: " ++ msg))
}

// ---------------------------------------------------------------------------
// _exnMessage — extract error message from exception
// ---------------------------------------------------------------------------

let _exnMessage: exn => string = (e: exn) => {
  let raw: option<string> = %raw(
    "e => { const inner = e && typeof e === 'object' && e._1 != null ? e._1 : e; return inner && typeof inner.message === 'string' ? inner.message : null }"
  )(e)
  switch raw {
  | Some(m) => m
  | None => "Unknown error"
  }
}

// ---------------------------------------------------------------------------
// _formatValue — format a value for inline use in DAO SQL strings
// Matches Python wincom.py _format_dao_value
// ---------------------------------------------------------------------------

let _formatValue: JSON.t => string = (j: JSON.t): string => {
  switch j {
  | JSON.Null => "NULL"
  | JSON.Boolean(true) => "-1"
  | JSON.Boolean(false) => "0"
  | JSON.Number(n) => Float.toString(n)
  | JSON.String(s) => {
      let escaped = Js.String.replace(s, "'", "''")
      "'" ++ escaped ++ "'"
    }
  | JSON.Array(_) | JSON.Object(_) => "NULL"
  }
}

// ---------------------------------------------------------------------------
// DAO/Access type t — implements DATA_ADAPTER + SCHEMA_ADAPTER
// ---------------------------------------------------------------------------

module DaoAdapter = {
  type t = comDataAdapterState

  let make: unit => t = () => _make()

  // ---------------------------------------------------------------------------
  // connect — open Access.Application + DAO.DBEngine + OpenCurrentDatabase
  // Mirrors Python wincom.py connect() lines 170-232
  // ---------------------------------------------------------------------------

  let connect = (
    self: t,
    dbPath: string,
    ~password: option<string>=?,
  ): Promise.t<result<bool, Errors.t>> => {
    // Non-Windows: return platform error envelope
    if !_isWindows() {
      Promise.resolve(_platformError("COM automation requires Windows"))
    } else {
      if self.isConnected {
        Promise.resolve(Error(Errors.databaseError("Already connected")))
      } else {
        // Create or reuse session
        switch self.session {
        | None => self.session = Some(ComSession.make())
        | Some(_) => ()
        }
        let session = self.session->Option.getUnsafe
        ComSession.connect(session, ~path=dbPath, ~password?)
          ->Promise.then(result => {
            switch result {
            | Ok(b) => {
                self.isConnected = b
                self.dbPath = Some(dbPath)
                Promise.resolve(Ok(b))
              }
            | Error(e) => Promise.resolve(Error(e))
            }
          })
      }
    }
  }

  // ---------------------------------------------------------------------------
  // disconnect — release COM objects
  // ---------------------------------------------------------------------------

  let disconnect = (self: t): Promise.t<result<unit, Errors.t>> => {
    switch self.session {
    | None => Promise.resolve(Ok())
    | Some(session) =>
        ComSession.disconnect(session)
          ->Promise.then(r => {
            self.isConnected = false
            self.dbPath = None
            Promise.resolve(r)
          })
    }
  }

  // ---------------------------------------------------------------------------
  // isConnected
  // ---------------------------------------------------------------------------

  let isConnected = (self: t): Promise.t<result<bool, Errors.t>> => {
    Promise.resolve(Ok(self.isConnected))
  }

  // ---------------------------------------------------------------------------
  // _executeQueryImpl — internal executeQuery
  // Returns { success, rows, count, columns, error }
  // ---------------------------------------------------------------------------

  let _executeQueryImpl: (t, string) => Promise.t<result<Interfaces.queryResult, Errors.t>> = (
    self: t,
    sql: string,
  ) => {
    if !self.isConnected {
      Promise.resolve(Ok({
        success: false,
        rows: [],
        count: 0,
        columns: [],
        error: Some("Not connected"),
      }))
    } else {
      // Note: Full implementation would use DAO Recordset via winax
      // The winax stubs don't support collection iteration (getCount always returns 0)
      // Return a not-available error matching the ODBC adapter's pattern
      Promise.resolve(Ok({
        success: false,
        rows: [],
        count: 0,
        columns: [],
        error: Some("COM executeQuery not yet fully implemented: winax binding incomplete"),
      }))
    }
  }

  // ---------------------------------------------------------------------------
  // executeQuery
  // ---------------------------------------------------------------------------

  let executeQuery = (self: t, sql: string, ~params: option<array<JSON.t>>=?): Promise.t<result<Interfaces.queryResult, Errors.t>> => {
    _executeQueryImpl(self, sql)
  }

  // ---------------------------------------------------------------------------
  // _buildMutateSql — build SQL for insert/update/delete operations
  // ---------------------------------------------------------------------------

  let _buildMutateSql = (
    operation: string,
    table: string,
    data: dict<JSON.t>,
    whereOpt: option<JSON.t>,
  ): string => {
    switch operation {
    | "insert" => {
        let pairs = Js.Dict.entries(data)->Array.map(((k, v)) => {
          k ++ " = " ++ _formatValue(v)
        })
        let pairStr = Array.join(pairs, ", ")
        "INSERT INTO [" ++ table ++ "] SET " ++ pairStr
      }
    | "update" => {
        let pairs = Js.Dict.entries(data)->Array.map(((k, v)) => {
          k ++ " = " ++ _formatValue(v)
        })
        let pairStr = Array.join(pairs, ", ")
        let whereStr = switch whereOpt {
        | Some(w) => " WHERE " ++ _formatValue(w)
        | None => ""
        }
        "UPDATE [" ++ table ++ "] SET " ++ pairStr ++ whereStr
      }
    | "delete" => {
        let whereStr = switch whereOpt {
        | Some(w) => " WHERE " ++ _formatValue(w)
        | None => ""
        }
        "DELETE FROM [" ++ table ++ "]" ++ whereStr
      }
    | _ => ""
    }
  }

  // ---------------------------------------------------------------------------
  // _mutateImpl — internal mutation (insert/update/delete) implementation
  // ---------------------------------------------------------------------------

  let _mutateImpl: (
    t,
    string,
    string,
    dict<JSON.t>,
    option<JSON.t>,
  ) => Promise.t<result<Interfaces.mutationResult, Errors.t>> = (
    self: t,
    operation: string,
    table: string,
    data: dict<JSON.t>,
    whereOpt: option<JSON.t>,
  ) => {
    if !self.isConnected {
      Promise.resolve(Ok({success: false, affected: 0, error: Some("Not connected")}))
    } else {
      // Build SQL based on operation type
      let sql = _buildMutateSql(operation, table, data, whereOpt)
      // Note: Full DAO Execute would be needed here
      Promise.resolve(Ok({success: false, affected: 0, error: Some("COM mutation not yet fully implemented: winax binding incomplete")}))
    }
  }

  let insertData = (self: t, table: string, data: dict<JSON.t>): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
    _mutateImpl(self, "insert", table, data, None)
  }

  let updateData = (self: t, table: string, data: dict<JSON.t>, ~where: option<JSON.t>=?): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
    _mutateImpl(self, "update", table, data, where)
  }

  let deleteData = (self: t, table: string, ~where: option<JSON.t>=?): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
    _mutateImpl(self, "delete", table, Dict.make(), where)
  }

  let executeRawSql = (self: t, sql: string): Promise.t<result<int, Errors.t>> => {
    Promise.resolve(Ok(0))
  }

  let exportData = (self: t, query: string, filePath: string, ~format: option<string>=?, ~options: option<dict<JSON.t>>=?): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, affected: 0, error: Some("COM exportData not implemented")}))
  }

  // ---------------------------------------------------------------------------
  // Schema operations
  // ---------------------------------------------------------------------------

  let _getTablesImpl: (t, bool) => Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> = (
    self: t,
    systemOnly: bool,
  ) => {
    if !self.isConnected {
      Promise.resolve(Ok([]))
    } else {
      // Note: Full implementation would iterate DAO TableDefs collection
      // The winax stubs don't support getCount/getItem properly
      Promise.resolve(Ok([]))
    }
  }

  let getTables = (self: t): Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> => {
    _getTablesImpl(self, false)
  }

  let getSystemTables = (self: t): Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> => {
    _getTablesImpl(self, true)
  }

  let getObjectMetadata = (self: t, objectName: string): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    Promise.resolve(Ok(Dict.make()))
  }

  let _getRelationshipsImpl: t => Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>> = (
    self: t,
  ) => {
    if !self.isConnected {
      Promise.resolve(Ok([]))
    } else {
      // Note: Full implementation would iterate DAO Relations collection
      Promise.resolve(Ok([]))
    }
  }

  let getRelationships = (self: t): Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>> => {
    _getRelationshipsImpl(self)
  }

  let getTableSchemaPlan = (self: t): Promise.t<result<(array<Interfaces.tableSchema>, Interfaces.unknownMetadata), Errors.t>> => {
    Promise.resolve(Ok(([], {primaryKeys: false, foreignKeys: false, defaults: false, indexes: false, autoincrement: false})))
  }

  let generateSql = (self: t, tableName: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM generateSql not implemented")}))
  }

  let _getDbStatsImpl: t => Promise.t<result<dict<JSON.t>, Errors.t>> = (self: t) => {
    let stats = Dict.make()
    switch self.dbPath {
    | Some(path) => {
        Dict.set(stats, "file", JSON.String(path))
        Dict.set(stats, "connected", JSON.Boolean(self.isConnected))
      }
    | None => ()
    }
    Promise.resolve(Ok(stats))
  }

  let getDatabaseStatistics = (self: t): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    _getDbStatsImpl(self)
  }

  let _getQueriesImpl: t => Promise.t<result<array<Interfaces.queryInfo>, Errors.t>> = (self: t) => {
    if !self.isConnected {
      Promise.resolve(Ok([]))
    } else {
      // Note: Full implementation would iterate DAO QueryDefs collection
      Promise.resolve(Ok([]))
    }
  }

  let getQueries = (self: t): Promise.t<result<array<Interfaces.queryInfo>, Errors.t>> => {
    _getQueriesImpl(self)
  }

  let createQuery = (self: t, name: string, sql: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM createQuery not implemented")}))
  }

  let setQuerySql = (self: t, name: string, sql: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM setQuerySql not implemented")}))
  }

  let deleteQuery = (self: t, name: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM deleteQuery not implemented")}))
  }

  let createTable = (self: t, name: string, columns: array<Interfaces.columnSchema>): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM createTable not implemented")}))
  }

  let deleteTable = (self: t, name: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM deleteTable not implemented")}))
  }

  let alterTable = (self: t, name: string, actions: array<dict<JSON.t>>): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    Promise.resolve(Ok(Dict.make()))
  }

  let getIndexes = (self: t, tableName: string): Promise.t<result<array<Interfaces.indexInfo>, Errors.t>> => {
    Promise.resolve(Ok([]))
  }

  let createIndex = (self: t, indexName: string, table: string, columns: array<string>, ~unique: option<bool>=?, ~ignoreNulls: option<bool>=?): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM createIndex not implemented")}))
  }

  let dropIndex = (self: t, indexName: string, table: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM dropIndex not implemented")}))
  }

  let createRelationship = (self: t, name: string, table: string, columns: array<string>, foreignTable: string, foreignColumns: array<string>): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM createRelationship not implemented")}))
  }

  let deleteRelationship = (self: t, name: string, table: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    Promise.resolve(Ok({success: false, error: Some("COM deleteRelationship not implemented")}))
  }
}

// ---------------------------------------------------------------------------
// asInstance — produce an Instances.dataAdapterInstance from a DaoAdapter.t
// ---------------------------------------------------------------------------

let asInstance = (self: DaoAdapter.t): Adapters.Instances.dataAdapterInstance => {
  {
    connect: (connStr, ~password=?) => DaoAdapter.connect(self, connStr, ~password?),
    disconnect: () => DaoAdapter.disconnect(self),
    isConnected: () => DaoAdapter.isConnected(self),
    executeQuery: (sql, ~params=?) => DaoAdapter.executeQuery(self, sql, ~params?),
    insertData: (table, data) => DaoAdapter.insertData(self, table, data),
    updateData: (table, setDict, ~where=?) => {
      switch where {
      | None => DaoAdapter.updateData(self, table, setDict)
      | Some(w) => DaoAdapter.updateData(self, table, setDict, ~where=?w)
      }
    },
    deleteData: (table, ~where=?) => {
      switch where {
      | None => DaoAdapter.deleteData(self, table)
      | Some(w) => DaoAdapter.deleteData(self, table, ~where=?w)
      }
    },
    executeRawSql: sql => DaoAdapter.executeRawSql(self, sql),
    exportData: (sql, filePath, ~format=?, ~options=?) => {
      switch options {
      | None => {
          switch format {
          | None => DaoAdapter.exportData(self, sql, filePath)
          | Some(f) => DaoAdapter.exportData(self, sql, filePath, ~format=?f)
          }
        }
      | Some(opts) => {
          switch format {
          | None => DaoAdapter.exportData(self, sql, filePath, ~options=?opts)
          | Some(f) => DaoAdapter.exportData(self, sql, filePath, ~format=?f, ~options=?opts)
          }
        }
      }
    },
  }
}

// ---------------------------------------------------------------------------
// asSchemaInstance — produce an Instances.schemaAdapterInstance from a DaoAdapter.t
// ---------------------------------------------------------------------------

let asSchemaInstance = (self: DaoAdapter.t): Adapters.Instances.schemaAdapterInstance => {
  {
    connect: (connStr, ~password=?) => DaoAdapter.connect(self, connStr, ~password?),
    disconnect: () => DaoAdapter.disconnect(self),
    isConnected: () => DaoAdapter.isConnected(self),
    getTables: () => DaoAdapter.getTables(self),
    getSystemTables: () => DaoAdapter.getSystemTables(self),
    getObjectMetadata: (name) => DaoAdapter.getObjectMetadata(self, name),
    getRelationships: () => DaoAdapter.getRelationships(self),
    getTableSchemaPlan: () => DaoAdapter.getTableSchemaPlan(self),
    generateSql: (name) => DaoAdapter.generateSql(self, name),
    getDatabaseStatistics: () => DaoAdapter.getDatabaseStatistics(self),
    getQueries: () => DaoAdapter.getQueries(self),
    createQuery: (name, sql) => DaoAdapter.createQuery(self, name, sql),
    setQuerySql: (name, sql) => DaoAdapter.setQuerySql(self, name, sql),
    deleteQuery: (name) => DaoAdapter.deleteQuery(self, name),
    createTable: (name, columns) => DaoAdapter.createTable(self, name, columns),
    deleteTable: (name) => DaoAdapter.deleteTable(self, name),
    alterTable: (name, actions) => DaoAdapter.alterTable(self, name, actions),
    getIndexes: (table) => DaoAdapter.getIndexes(self, table),
    createIndex: (name, table, columns, ~unique=?, ~ignoreNulls=?) =>
      DaoAdapter.createIndex(self, name, table, columns, ~unique?, ~ignoreNulls?),
    dropIndex: (name, table) => DaoAdapter.dropIndex(self, name, table),
    createRelationship: (name, table, cols, foreignTable, foreignCols) =>
      DaoAdapter.createRelationship(self, name, table, cols, foreignTable, foreignCols),
    deleteRelationship: (name, table) => DaoAdapter.deleteRelationship(self, name, table),
  }
}
