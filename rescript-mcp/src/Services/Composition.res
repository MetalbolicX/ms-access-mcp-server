// Composition.res — root composition layer for real adapter instances
// Design: plan 015 T5
// This module is the ONLY src module that imports adapters + transitively Bindings.
// It provides the real factory that creates production Facade bindings.

open Adapters

// ---------------------------------------------------------------------------
// comAvailable — probe for winax availability on the current platform
// Used by makeRealFactory and Server.res to determine which adapter to build
// ---------------------------------------------------------------------------

let comAvailable: bool = Bindings.TsBridge.isWindows() && Bindings.TsBridge.isWinaxAvailable()

// ---------------------------------------------------------------------------
// asSchemaInstance — wrap an OdbcAdapter.t as a 22-field schemaAdapterInstance
// The same OdbcAdapter.t underlies both data and schema instances (shared state).
// createRelationship/deleteRelationship: delegate to SqlBuilder + conn.query
// ---------------------------------------------------------------------------

let asSchemaInstance = (dataT: OdbcAdapter.t): Instances.schemaAdapterInstance => {
  {
    connect: (connStr, ~password=?) => OdbcAdapter.connect(dataT, connStr, ~password?),
    disconnect: () => OdbcAdapter.disconnect(dataT),
    isConnected: () => OdbcAdapter.isConnected(dataT),
    getTables: () => OdbcAdapter.getTables(dataT),
    getSystemTables: () => OdbcAdapter.getSystemTables(dataT),
    getObjectMetadata: (name) => OdbcAdapter.getObjectMetadata(dataT, name),
    getRelationships: () => OdbcAdapter.getRelationships(dataT),
    getTableSchemaPlan: () => OdbcAdapter.getTableSchemaPlan(dataT),
    generateSql: (name) => OdbcAdapter.generateSql(dataT, name),
    getDatabaseStatistics: () => OdbcAdapter.getDatabaseStatistics(dataT),
    getQueries: () => OdbcAdapter.getQueries(dataT),
    createQuery: (name, sql) => OdbcAdapter.createQuery(dataT, name, sql),
    setQuerySql: (name, sql) => OdbcAdapter.setQuerySql(dataT, name, sql),
    deleteQuery: (name) => OdbcAdapter.deleteQuery(dataT, name),
    createTable: (name, columns) => OdbcAdapter.createTable(dataT, name, columns),
    deleteTable: (name) => OdbcAdapter.deleteTable(dataT, name),
    alterTable: (name, actions) => {
      OdbcAdapter.alterTable(dataT, name, actions)
        ->Promise.then(result => {
          switch result {
          | Ok(r) => {
              let d: dict<JSON.t> = Dict.fromArray([
                ("success", JSON.Boolean(r.success)),
                ("error", switch r.error {
                  | Some(e) => JSON.String(e)
                  | None => JSON.Null
                }),
              ])
              Promise.resolve(Ok(d))
            }
          | Error(e) => Promise.resolve(Error(e))
          }
        })
    },
    getIndexes: (table) => OdbcAdapter.getIndexes(dataT, table),
    createIndex: (name, table, columns, ~unique=?, ~ignoreNulls=?) =>
      OdbcAdapter.createIndex(dataT, name, table, columns, ~unique?, ~ignoreNulls?),
    dropIndex: (name, table) => OdbcAdapter.dropIndex(dataT, name, table),
    createRelationship: (name, table, cols, foreignTable, foreignCols) => {
      switch dataT.connection {
      | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
      | Some(conn) => {
          switch SqlBuilder.createRelationship(
            ~table,
            ~relationshipName=name,
            ~columns=cols,
            ~foreignTable=foreignTable,
            ~foreignColumns=foreignCols,
          ) {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(sql) => {
              conn.query(sql, [])
                ->Promise.then(result => {
                  switch result {
                  | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
                  | Error(e) => Promise.resolve(Error(e))
                  }
                })
                ->Promise.catch(e => {
                  let msg = switch %raw("e => e.message || String(e)")(e) {
                  | Some(m) => m
                  | None => "Unknown error"
                  }
                  Promise.resolve(Error(Errors.databaseError(msg)))
                })
            }
          }
        }
      }
    },
    deleteRelationship: (name, table) => {
      switch dataT.connection {
      | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
      | Some(conn) => {
          let sql = SqlBuilder.deleteRelationship(~table, ~relationshipName=name)
          conn.query(sql, [])
            ->Promise.then(result => {
              switch result {
              | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
              | Error(e) => Promise.resolve(Error(e))
              }
            })
            ->Promise.catch(e => {
              let msg = switch %raw("e => e.message || String(e)")(e) {
              | Some(m) => m
              | None => "Unknown error"
              }
              Promise.resolve(Error(Errors.databaseError(msg)))
            })
        }
      }
    },
  }
}

// ---------------------------------------------------------------------------
// makeRealFactory — creates a Facade.bindingFactory for production use
// comAvailable: currently fixed false (Windows COM adapter deferred)
// ---------------------------------------------------------------------------

let makeRealFactory = (~comAvailable: bool): Facade.bindingFactory => {
  (~backend: option<BackendSelector.backend>, ~dbPath: string, ~password: string) => {
    // Resolve the backend: default to ODBC, honor "com" if available
    let resolvedBackend = switch backend {
    | Some(BackendSelector.COM) => BackendSelector.COM
    | Some(BackendSelector.ODBC) | None => BackendSelector.ODBC
    }
    let useCom = resolvedBackend == BackendSelector.COM

    if useCom && comAvailable {
      // COM path: build ComDataAdapter + ComDataAdapter.asSchemaInstance
      let adapterType = "com"
      let dataT: ComDataAdapter.DaoAdapter.t = ComDataAdapter.DaoAdapter.make()
      let dataAdapter = ComDataAdapter.asInstance(dataT)
      let schemaAdapter = ComDataAdapter.asSchemaInstance(dataT)
      dataAdapter.connect(dbPath, ~password=?Some(password))
        ->Promise.then(connectResult => {
          switch connectResult {
          | Ok(_) =>
            Promise.resolve(Ok({
              dataAdapter: dataAdapter,
              schemaAdapter: schemaAdapter,
              _rawDataAdapter: None,
              _rawSchemaAdapter: None,
              dbPath: dbPath,
              adapterType: adapterType,
            }: Facade.binding))
          | Error(err) => Promise.resolve(Error(err))
          }
        })
    } else {
      // ODBC path: unchanged — build OdbcAdapter + OdbcAdapter.asSchemaInstance
      let adapterType = "odbc"
      let dataT: OdbcAdapter.t = {connection: None, dbPath: None}
      let dataAdapter = OdbcAdapter.asInstance(dataT)
      let schemaAdapter = asSchemaInstance(dataT)
      let connStr = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" ++ dbPath ++ ";"
      dataAdapter.connect(connStr)
        ->Promise.then(connectResult => {
          switch connectResult {
          | Ok(_) =>
            Promise.resolve(Ok({
              dataAdapter: dataAdapter,
              schemaAdapter: schemaAdapter,
              _rawDataAdapter: None,
              _rawSchemaAdapter: None,
              dbPath: dbPath,
              adapterType: adapterType,
            }: Facade.binding))
          | Error(err) => Promise.resolve(Error(err))
          }
        })
    }
  }
}

// ---------------------------------------------------------------------------
// realFactory — pre-built factory using the comAvailable probe
// ---------------------------------------------------------------------------

let realFactory: Facade.bindingFactory = makeRealFactory(~comAvailable)
