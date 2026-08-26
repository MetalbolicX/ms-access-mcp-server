// Facade.res — connection-lifecycle facade (Phase 2: connectAccess, disconnectAccess,
//             listConnections, isConnected, setActiveConnection, getActiveConnection)
// Oracle: mcp/connection.py:41-53,78-100,214-251,254-291
// Oracle: services/connection.py:120-144,222-326
// Design: obs 1031 decisions A, B, E, F, G
// NO Bindings/* imports — all dependencies arrive via Facade.make injection

open ConnectionPool

// ---------------------------------------------------------------------------
// Binding — holds adapter instances + metadata for a named connection
// Decision E: Facade owns mutable bindings array; pool untouched
// The dataAdapter and schemaAdapter fields store concrete adapter instances.
// The bindingFactory injected at make() creates these instances.
// ---------------------------------------------------------------------------

type binding = {
  dataAdapter: Adapters.Instances.dataAdapterInstance,
  schemaAdapter: Adapters.Instances.schemaAdapterInstance,
  // Internal: raw fake adapters for test infrastructure access (T3 migration helper)
  // These allow test helpers (setupFake*) to inject test data directly.
  // Prefixed with _ to signal they are test-only internals.
  // option<> so production bindings can use None (real adapters don't need mutation)
  _rawDataAdapter: option<Fakes.FakeOdbcAdapter.t>,
  _rawSchemaAdapter: option<Fakes.FakeSchemaAdapter.t>,
  dbPath: string,
  adapterType: string,
}

// bindingFactory: creates a binding (adapter pair) for a dbPath + backend
// Injected at Facade.make; tests inject fakeFactory
type bindingFactory = (
  ~backend: option<BackendSelector.backend>,
  ~dbPath: string,
  ~password: string,
) => Promise.t<result<binding, Errors.t>>

// ---------------------------------------------------------------------------
// Facade record — injected pool + factory, owns bindings array
// Decision A: pool owned in make; Decision B: t-first free fns
// ---------------------------------------------------------------------------

// pool_t: local alias to avoid constructor shadowing after open ConnectionPool
type pool_t = ConnectionPool.pool

type t = {
  mutable pool: pool_t,
  mutable bindings: array<(string, binding)>,
  factory: bindingFactory,
  comAvailable: bool,
  readonly: unit => bool,
  allowedDirs: unit => array<string>,
}

// ---------------------------------------------------------------------------
// Private helpers
// Decision G: Errors.t never escapes; failures return {success:false, error}
// ---------------------------------------------------------------------------

// assertNotReadonly: guard for mutating ops (insert_data, update_data, etc.)
// Connection-lifecycle ops pass through (readonly registry = 5 M-ops only)
let assertNotReadonly = (
  facade: t,
  ~opName: string,
): result<unit, Errors.t> => {
  if facade.readonly() {
    Error(Errors.validationError("Read-only mode: " ++ opName ++ " not allowed"))
  } else {
    Ok(())
  }
}

// shapeErr: convert Errors.t to public failure dict
let shapeErr = (err: Errors.t): dict<JSON.t> => {
  let d = Errors.toDict(err)
  Dict.fromArray([
    ("success", JSON.Boolean(false)),
    ("error", JSON.String(d.message)),
  ])
}

// _bindingForName: find a binding by name in facade.bindings
let _bindingForName = (
  facade: t,
  name: string,
): option<binding> => {
  Belt.Array.getBy(facade.bindings, ((n, _b)) => n == name)->Option.map(((_n, b)) => b)
}

// adapterForName: get the dataAdapterInstance for a named connection
// Used by CRUD ops (future phases); connection lifecycle doesn't call this
let adapterForName = (
  facade: t,
  ~name: string,
  ~notConnectedMsg: string,
): result<Adapters.Instances.dataAdapterInstance, Errors.t> => {
  switch _bindingForName(facade, name) {
  | Some(binding) => Ok(binding.dataAdapter)
  | None => Error(Errors.databaseError(notConnectedMsg))
  }
}

// schemaAdapterForName: get the schemaAdapterInstance for a named connection
let schemaAdapterForName = (
  facade: t,
  ~name: string,
  ~notConnectedMsg: string,
): result<Adapters.Instances.schemaAdapterInstance, Errors.t> => {
  switch _bindingForName(facade, name) {
  | Some(binding) => Ok(binding.schemaAdapter)
  | None => Error(Errors.databaseError(notConnectedMsg))
  }
}

// _resolveBackend: convert optional string backend to BackendSelector.backend variant
// connection.py:86-95 — explicit backend wins; else useCom; else odbc
let _resolveBackend = (
  ~backend: option<string>,
  ~useCom: bool,
): option<BackendSelector.backend> => {
  switch backend {
  | Some("odbc") => Some(BackendSelector.ODBC)
  | Some("com") => Some(BackendSelector.COM)
  | Some("dao") => Some(BackendSelector.DAO)
  | Some("auto") => Some(BackendSelector.AUTO)
  | Some(_) => Some(BackendSelector.ODBC)
  | None =>
    if useCom {
      Some(BackendSelector.COM)
    } else {
      Some(BackendSelector.ODBC)
    }
  }
}

// _validateDatabasePath: validate dbPath against allowed directories
// Per spec: database_path validated explicitly (not via PathGuard's 9-name registry)
let _validateDatabasePath = (
  facade: t,
  dbPath: string,
): result<string, Errors.t> => {
  let allowed = facade.allowedDirs()
  if String.startsWith(dbPath, "\\\\") || String.startsWith(dbPath, "//") {
    Error(Errors.pathGuardError("UNC paths not allowed"))
  } else {
    let segments = Js.String.split("/", dbPath)->Belt.Array.concat(
      Js.String.split("\\", dbPath)
    )
    if Belt.Array.some(segments, s => s == "..") {
      Error(Errors.pathGuardError("Path traversal not allowed"))
    } else {
      let resolved = NodeJs.Path.resolve([dbPath])
      if !Belt.Array.some(allowed, dir => String.startsWith(resolved, dir)) {
        let msg = "database_path: path not allowed: " ++ dbPath ++ ". Allowed directories: [" ++ Belt.Array.joinWith(allowed, ",", s => s) ++ "]"
        Error(Errors.pathGuardError(msg))
      } else {
        Ok(resolved)
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Facade.make — constructor
// Decision A: pool owned, injectable; Decision F: params only
// ---------------------------------------------------------------------------

let make = (
  ~pool: option<pool_t>=?,
  ~factory: bindingFactory,
  ~comAvailable: option<bool>=?,
  ~readonly: option<(unit => bool)>=?,
  ~allowedDirs: option<(unit => array<string>)>=?,
): t => {
  {
    pool: pool->Belt.Option.getWithDefault(ConnectionPool.make()),
    bindings: [],
    factory: factory,
    comAvailable: comAvailable->Belt.Option.getWithDefault(false),
    readonly: readonly->Belt.Option.getWithDefault(() => false),
    allowedDirs: allowedDirs->Belt.Option.getWithDefault(() => [NodeJs.Os.homedir()]),
  }
}

// ---------------------------------------------------------------------------
// _ensureNoDuplicateConnection — raises if name already in bindings
// Decision E: check bindings, not pool, for duplicate detection
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// connectAccess — connect a named database
// Oracle: connection.py:41-53 (shape), :78-84 (path guard), :86-95 (backend)
// Data flow: validatePath → backend resolve → factory → pool.connect → register binding
// ---------------------------------------------------------------------------

let connectAccess = (
  facade: t,
  ~dbPath: string,
  ~name: option<string>=?,
  ~useCom: option<bool>=?,
  ~password: option<string>=?,
  ~backend: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  let connPassword = password->Belt.Option.getWithDefault("")

  // Step 1: Validate path
  switch _validateDatabasePath(facade, dbPath) {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(resolvedPath) => {
      let resolvedBackend = _resolveBackend(~backend=backend, ~useCom=useCom->Belt.Option.getWithDefault(false))

      // Step 2: Call factory to get binding
      facade.factory(~backend=resolvedBackend, ~dbPath=resolvedPath, ~password=connPassword)
        ->Promise.then(factoryResult => {
          switch factoryResult {
          | Error(err) => Promise.resolve(shapeErr(err))
          | Ok(binding) => {
              // Step 3: Check duplicate name in facade.bindings
              switch _bindingForName(facade, connName) {
              | Some(_) => {
                  let msg = "Connection '" ++ connName ++ "' already exists. Use disconnect('" ++ connName ++ "') first."
                  Promise.resolve(shapeErr(Errors.databaseError(msg)))
                }
              | None => {
                  // Step 4: pool.connect
                  ConnectionPool.connect(facade.pool, connName, resolvedPath, binding.adapterType, ~password=connPassword)
                    ->Promise.then(connectResult => {
                      switch connectResult {
                      | Error(err) => Promise.resolve(shapeErr(err))
                      | Ok(_state) => {
                          // Step 5: Register binding
                          facade.bindings = Belt.Array.concat(facade.bindings, [(connName, binding)])
                          // Step 6: Return success shape
                          let result = Dict.fromArray([
                            ("success", JSON.Boolean(true)),
                            ("connected", JSON.Boolean(true)),
                            ("database", JSON.String(resolvedPath)),
                            ("name", JSON.String(connName)),
                          ])
                          Promise.resolve(result)
                        }
                      }
                    })
                }
              }
            }
          }
        })
    }
  }
}

// ---------------------------------------------------------------------------
// disconnectAccess — disconnect a named connection
// Oracle: connection.py:214-226, services/connection.py:222-237
// ---------------------------------------------------------------------------

let disconnectAccess = (
  facade: t,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")

  switch _bindingForName(facade, connName) {
  | None =>
    // Absent "default" is silent no-op (Python parity)
    if connName == "default" {
      Promise.resolve(Dict.fromArray([
        ("success", JSON.Boolean(true)),
        ("message", JSON.String("Disconnected '" ++ connName ++ "'")),
      ]))
    } else {
      let msg = "Connection '" ++ connName ++ "' not found"
      Promise.resolve(shapeErr(Errors.databaseError(msg)))
    }
  | Some(_binding) => {
      // Remove from facade.bindings first
      facade.bindings = Belt.Array.keep(facade.bindings, ((n, _b)) => n != connName)
      ConnectionPool.disconnect(facade.pool, ~name=connName)
        ->Promise.then(_result => {
          Promise.resolve(Dict.fromArray([
            ("success", JSON.Boolean(true)),
            ("message", JSON.String("Disconnected '" ++ connName ++ "'")),
          ]))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// listConnections — list all connections with status
// Oracle: connection.py:230-251
// ---------------------------------------------------------------------------

let listConnections = (facade: t): dict<JSON.t> => {
  let poolConnections = ConnectionPool.list(facade.pool)
  let connectionsDict = Dict.make()

  Belt.Array.forEach(poolConnections, ((connName, _state)) => {
    switch _bindingForName(facade, connName) {
    | Some(binding) => {
        let info = Dict.fromArray([
          ("database", JSON.String(binding.dbPath)),
          ("adapter_type", JSON.String(binding.adapterType)),
          ("connected", JSON.Boolean(true)),
        ])
        Dict.set(connectionsDict, connName, JSON.Object(info))
      }
    | None => {
        let info = Dict.fromArray([
          ("database", JSON.Null),
          ("adapter_type", JSON.String("unknown")),
          ("connected", JSON.Boolean(false)),
        ])
        Dict.set(connectionsDict, connName, JSON.Object(info))
      }
    }
  })

  let count = Belt.Array.length(poolConnections)
  let active = ConnectionPool.get_active(facade.pool)

  Dict.fromArray([
    ("success", JSON.Boolean(true)),
    ("connections", JSON.Object(connectionsDict)),
    ("count", JSON.Number(float_of_int(count))),
    ("active", JSON.String(active)),
  ])
}

// ---------------------------------------------------------------------------
// isConnected — check if a connection is connected
// Oracle: connection.py:280-291 — PARITY EXCEPTION: no `success` key
// services/connection.py:397-406 — database mirrors ACTIVE connection path
// ---------------------------------------------------------------------------

let isConnected = (
  facade: t,
  ~name: option<string>=?,
): dict<JSON.t> => {
  let connName = name->Belt.Option.getWithDefault("default")

  let poolConnected = switch ConnectionPool.isConnected(facade.pool, ~name=connName) {
  | Ok(c) => c
  | Error(_) => false
  }

  // database mirrors the ACTIVE connection's path (parity quirk)
  let activeDbPath = switch ConnectionPool.getActive(facade.pool) {
  | Ok(activeState) => activeState.dbPathStr
  | Error(_) => ""
  }

  let result = Dict.make()
  Dict.set(result, "connected", if poolConnected { JSON.Boolean(true) } else { JSON.Boolean(false) })
  Dict.set(result, "database", if activeDbPath == "" { JSON.Null } else { JSON.String(activeDbPath) })
  Dict.set(result, "name", JSON.String(connName))
  result
}

// ---------------------------------------------------------------------------
// setActiveConnection — set the active connection pointer
// Oracle: connection.py:254-266
// ---------------------------------------------------------------------------

let setActiveConnection = (
  facade: t,
  ~name: string,
): Promise.t<dict<JSON.t>> => {
  switch ConnectionPool.set_active(facade.pool, name) {
  | Ok(_) => {
      let result = Dict.fromArray([
        ("success", JSON.Boolean(true)),
        ("active", JSON.String(name)),
      ])
      Promise.resolve(result)
    }
  | Error(err) => Promise.resolve(shapeErr(err))
  }
}

// ---------------------------------------------------------------------------
// getActiveConnection — get the active connection name
// Oracle: connection.py:269-277
// ---------------------------------------------------------------------------

let getActiveConnection = (facade: t): dict<JSON.t> => {
  let active = ConnectionPool.get_active(facade.pool)
  Dict.fromArray([
    ("success", JSON.Boolean(true)),
    ("active", JSON.String(active)),
  ])
}

// ---------------------------------------------------------------------------
// queryData — execute SQL query
// Oracle: crud.py:222-241
// Guard order: none (read-only op)
// ---------------------------------------------------------------------------

let queryData = (
  facade: t,
  ~sql: string,
  ~params: option<array<JSON.t>>=?,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  switch adapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(adapter) =>
    adapter.executeQuery(sql, ~params?)
      ->Promise.then(r => {
        switch r {
        | Error(e) => Promise.resolve(shapeErr(e))
        | Ok(q) => {
            let rowsJson = JSON.Array(Belt.Array.map(q.rows, r => JSON.Object(r)))
            let colsJson = JSON.Array(Belt.Array.map(q.columns, c => JSON.String(c)))
            let result = Dict.make()
            Dict.set(result, "success", JSON.Boolean(true))
            Dict.set(result, "rows", rowsJson)
            Dict.set(result, "count", JSON.Number(Int.toFloat(Belt.Array.length(q.rows))))
            Dict.set(result, "columns", colsJson)
            Dict.set(result, "error", JSON.Null)
            Promise.resolve(result)
          }
        }
      })
  }
}

// ---------------------------------------------------------------------------
// insertData — insert one or more rows
// Oracle: crud.py:244-263
// Guard order: readonly FIRST, then connected
// ---------------------------------------------------------------------------

let insertData = (
  facade: t,
  ~table: string,
  ~data: JSON.t,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  // Guard 1: readonly (mutating op)
  switch assertNotReadonly(facade, ~opName="insert_data") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(_) =>
    // Guard 2: connected
    switch adapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected") {
    | Error(err) => Promise.resolve(shapeErr(err))
    | Ok(adapter) =>
      // Detect single vs batch at runtime
      let dataDicts: array<dict<JSON.t>> = switch data {
      | JSON.Object(d) => [d]
      | JSON.Array(arr) =>
        Belt.Array.map(arr, item => {
          switch item {
          | JSON.Object(d) => d
          | _ => Dict.make()
          }
        })
      | _ => []
      }
      // Execute insert for each dict and sum affected
      let rec recurse = (
        adapter: Adapters.Instances.dataAdapterInstance,
        remaining: array<dict<JSON.t>>,
        ~acc: int,
      ): Promise.t<dict<JSON.t>> => {
        if Belt.Array.length(remaining) == 0 {
          let result = Dict.make()
          Dict.set(result, "success", JSON.Boolean(true))
          Dict.set(result, "affected", JSON.Number(Int.toFloat(acc)))
          Promise.resolve(result)
        } else {
          let head = Belt.Array.getUnsafe(remaining, 0)
          let tail = Belt.Array.sliceToEnd(remaining, 1)
          adapter.insertData(table, head)
            ->Promise.then(r => {
              switch r {
              | Error(e) => Promise.resolve(shapeErr(e))
              | Ok(mut) => recurse(adapter, tail, ~acc=acc + mut.affected)
              }
            })
        }
      }
      recurse(adapter, dataDicts, ~acc=0)
    }
  }
}

// ---------------------------------------------------------------------------
// updateData — update rows
// Oracle: crud.py:266-295, _helpers.py:69-73
// Guard order: readonly FIRST, then connected, then mass-update guard
// ---------------------------------------------------------------------------

let updateData = (
  facade: t,
  ~table: string,
  ~setDict: dict<JSON.t>,
  ~whereDict: option<dict<JSON.t>>=?,
  ~name: option<string>=?,
  ~confirm: bool=false,
  ~dryRun: bool=false,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  // Guard 1: readonly (mutating op)
  switch assertNotReadonly(facade, ~opName="update_data") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(_) => {
      // Guard 2: connected
      switch adapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected") {
      | Error(err) => Promise.resolve(shapeErr(err))
      | Ok(adapter) => {
          // Guard 3: mass-update (only when whereDict is absent/empty)
          let whereIsEmpty = switch whereDict {
          | None => true
          | Some(d) => Belt.Array.length(Js.Dict.entries(d)) == 0
          }
          if whereIsEmpty {
            if dryRun {
              let result = Dict.make()
              Dict.set(result, "dry_run", JSON.Boolean(true))
              Dict.set(result, "table", JSON.String(table))
              Promise.resolve(result)
            } else if !confirm {
              let msg = "confirm=True required for update_data"
              Promise.resolve(shapeErr(Errors.validationError(msg)))
            } else {
adapter.updateData(table, setDict, ~where=?whereDict->Belt.Option.map(d => JSON.Object(d))->Belt.Option.map(v => Some(v)))
              ->Promise.then(r => {
                switch r {
                | Error(e) => Promise.resolve(shapeErr(e))
                | Ok(mut) => {
                    let result = Dict.make()
                    Dict.set(result, "success", JSON.Boolean(true))
                    Dict.set(result, "affected", JSON.Number(Int.toFloat(mut.affected)))
                    Promise.resolve(result)
                  }
                }
              })
            }
          } else {
            // Targeted update (whereDict present) — no confirm required
            adapter.updateData(table, setDict, ~where=?whereDict->Belt.Option.map(d => JSON.Object(d))->Belt.Option.map(v => Some(v)))
              ->Promise.then(r => {
                switch r {
                | Error(e) => Promise.resolve(shapeErr(e))
                | Ok(mut) => {
                    let result = Dict.make()
                    Dict.set(result, "success", JSON.Boolean(true))
                    Dict.set(result, "affected", JSON.Number(Int.toFloat(mut.affected)))
                    Promise.resolve(result)
                  }
                }
              })
          }
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// deleteData — delete rows
// Oracle: crud.py:298-319
// Guard order: readonly FIRST, then connected, then WHERE guard (always)
// ---------------------------------------------------------------------------

let deleteData = (
  facade: t,
  ~table: string,
  ~whereDict: dict<JSON.t>,
  ~name: option<string>=?,
  ~confirm: bool=false,
  ~dryRun: bool=false,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  // Guard 1: readonly (mutating op)
  switch assertNotReadonly(facade, ~opName="delete_data") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(_) =>
    // Guard 2: connected
    switch adapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected") {
    | Error(err) => Promise.resolve(shapeErr(err))
    | Ok(adapter) => {
        // Guard 3: WHERE must be non-empty (always required for delete)
        let whereEntries = Js.Dict.entries(whereDict)
        if Belt.Array.length(whereEntries) == 0 {
          let msg = "DELETE requires non-empty WHERE clause"
          Promise.resolve(shapeErr(Errors.validationError(msg)))
        } else if dryRun {
          let result = Dict.make()
          Dict.set(result, "dry_run", JSON.Boolean(true))
          Dict.set(result, "table", JSON.String(table))
          Promise.resolve(result)
        } else if !confirm {
          let msg = "confirm=True required for delete_data"
          Promise.resolve(shapeErr(Errors.validationError(msg)))
        } else {
          adapter.deleteData(table, ~where=?Some(JSON.Object(whereDict))->Belt.Option.map(v => Some(v)))
            ->Promise.then(r => {
              switch r {
              | Error(e) => Promise.resolve(shapeErr(e))
              | Ok(mut) => {
                  let result = Dict.make()
                  Dict.set(result, "success", JSON.Boolean(true))
                  Dict.set(result, "affected", JSON.Number(Int.toFloat(mut.affected)))
                  Promise.resolve(result)
                }
              }
            })
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// getTables — list all user tables
// Oracle: schema.py:40-50
// Guard order: schemaAdapterForName (notConnectedMsg="Not connected to database")
// Schema ops are read-only — no assertNotReadonly
// ---------------------------------------------------------------------------

let getTables = (
  facade: t,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  switch schemaAdapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(adapter) =>
    adapter.getTables()
      ->Promise.then(r => {
        switch r {
        | Error(e) => Promise.resolve(shapeErr(e))
        | Ok(tables) => {
            let result = Dict.make()
            Dict.set(result, "success", JSON.Boolean(true))
            Dict.set(result, "tables", JSON.Array(Belt.Array.map(tables, t => {
              let d = Dict.make()
              Dict.set(d, "name", JSON.String(t.name))
              Dict.set(d, "fields", JSON.Array(Belt.Array.map(t.fields, f => {
                let fd = Dict.make()
                Dict.set(fd, "name", JSON.String(f.name))
                Dict.set(fd, "type", JSON.String(f.type_))
                Dict.set(fd, "size", JSON.Number(Int.toFloat(f.size)))
                Dict.set(fd, "required", JSON.Boolean(f.required))
                Dict.set(fd, "allowZeroLength", JSON.Boolean(f.allowZeroLength))
                Dict.set(fd, "defaultValue", switch f.defaultValue {
                  | Some(v) => JSON.String(v)
                  | None => JSON.Null
                })
                Dict.set(fd, "isAutoincrement", JSON.Boolean(f.isAutoincrement))
                JSON.Object(fd)
              })))
              Dict.set(d, "recordCount", JSON.Number(Int.toFloat(t.recordCount)))
              Dict.set(d, "primaryKey", switch t.primaryKey {
                | Some(pk) => JSON.Array(Belt.Array.map(pk, s => JSON.String(s)))
                | None => JSON.Null
              })
              JSON.Object(d)
            })))
            Dict.set(result, "count", JSON.Number(Int.toFloat(Belt.Array.length(tables))))
            Promise.resolve(result)
          }
        }
      })
  }
}

// ---------------------------------------------------------------------------
// getTableSchema — get schema for a specific table
// Oracle: schema.py:73-88
// Guard order: schemaAdapterForName (notConnectedMsg="Not connected to database")
// v1 limitation: implemented as getTables + find-by-name (no per-table adapter method)
// ---------------------------------------------------------------------------

let getTableSchema = (
  facade: t,
  ~table: string,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  switch schemaAdapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(adapter) =>
    adapter.getTables()
      ->Promise.then(r => {
        switch r {
        | Error(e) => Promise.resolve(shapeErr(e))
        | Ok(tables) =>
          switch Belt.Array.getBy(tables, t => t.name == table) {
          | None => Promise.resolve(shapeErr(Errors.validationError("Table '" ++ table ++ "' not found")))
          | Some(t) => {
              let d = Dict.make()
              Dict.set(d, "name", JSON.String(t.name))
              Dict.set(d, "fields", JSON.Array(Belt.Array.map(t.fields, f => {
                let fd = Dict.make()
                Dict.set(fd, "name", JSON.String(f.name))
                Dict.set(fd, "type", JSON.String(f.type_))
                Dict.set(fd, "size", JSON.Number(Int.toFloat(f.size)))
                Dict.set(fd, "required", JSON.Boolean(f.required))
                Dict.set(fd, "allowZeroLength", JSON.Boolean(f.allowZeroLength))
                Dict.set(fd, "defaultValue", switch f.defaultValue {
                  | Some(v) => JSON.String(v)
                  | None => JSON.Null
                })
                Dict.set(fd, "isAutoincrement", JSON.Boolean(f.isAutoincrement))
                JSON.Object(fd)
              })))
              Dict.set(d, "recordCount", JSON.Number(Int.toFloat(t.recordCount)))
              Dict.set(d, "primaryKey", switch t.primaryKey {
                | Some(pk) => JSON.Array(Belt.Array.map(pk, s => JSON.String(s)))
                | None => JSON.Null
              })
              let result = Dict.make()
              Dict.set(result, "success", JSON.Boolean(true))
              Dict.set(result, "table", JSON.Object(d))
              Promise.resolve(result)
            }
          }
        }
      })
  }
}

// ---------------------------------------------------------------------------
// getRelationships — list all foreign key relationships
// Oracle: schema.py:91-107
// Guard order: schemaAdapterForName (notConnectedMsg="Not connected to database")
// Schema ops are read-only — no assertNotReadonly
// ---------------------------------------------------------------------------

let getRelationships = (
  facade: t,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  switch schemaAdapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(adapter) =>
    adapter.getRelationships()
      ->Promise.then(r => {
        switch r {
        | Error(e) => Promise.resolve(shapeErr(e))
        | Ok(rels) => {
            let result = Dict.make()
            Dict.set(result, "success", JSON.Boolean(true))
            Dict.set(result, "relationships", JSON.Array(Belt.Array.map(rels, rel => {
              let d = Dict.make()
              Dict.set(d, "name", JSON.String(rel.name))
              Dict.set(d, "table", JSON.String(rel.table))
              Dict.set(d, "foreignTable", JSON.String(rel.foreignTable))
              Dict.set(d, "attributes", JSON.String(rel.attributes))
              Dict.set(d, "columns", JSON.Array(Belt.Array.map(rel.columns, s => JSON.String(s))))
              Dict.set(d, "foreignColumns", JSON.Array(Belt.Array.map(rel.foreignColumns, s => JSON.String(s))))
              JSON.Object(d)
            })))
            Dict.set(result, "count", JSON.Number(Int.toFloat(Belt.Array.length(rels))))
            Promise.resolve(result)
          }
        }
      })
  }
}

// ---------------------------------------------------------------------------
// getQueries — list all saved queries
// Oracle: crud.py:37-46
// Guard order: schemaAdapterForName (notConnectedMsg="Not connected to database")
// Schema ops are read-only — no assertNotReadonly
// ---------------------------------------------------------------------------

let getQueries = (
  facade: t,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  switch schemaAdapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(adapter) =>
    adapter.getQueries()
      ->Promise.then(r => {
        switch r {
        | Error(e) => Promise.resolve(shapeErr(e))
        | Ok(queries) => {
            let result = Dict.make()
            Dict.set(result, "success", JSON.Boolean(true))
            Dict.set(result, "queries", JSON.Array(Belt.Array.map(queries, q => {
              let d = Dict.make()
              Dict.set(d, "name", JSON.String(q.name))
              Dict.set(d, "sql", JSON.String(q.sql))
              Dict.set(d, "type", JSON.String(q.type_))
              JSON.Object(d)
            })))
            Dict.set(result, "count", JSON.Number(Int.toFloat(Belt.Array.length(queries))))
            Promise.resolve(result)
          }
        }
      })
  }
}

// ---------------------------------------------------------------------------
// getDatabaseStatistics — get database statistics
// Oracle: schema.py:189-209
// Guard order: schemaAdapterForName (notConnectedMsg="Not connected to database")
// Schema ops are read-only — no assertNotReadonly
// ---------------------------------------------------------------------------

let getDatabaseStatistics = (
  facade: t,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  switch schemaAdapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(adapter) =>
    adapter.getDatabaseStatistics()
      ->Promise.then(r => {
        switch r {
        | Error(e) => Promise.resolve(shapeErr(e))
        | Ok(stats) => {
            let result = Dict.make()
            Dict.set(result, "success", JSON.Boolean(true))
            // Merge stats dict directly (objects/file/system structure from adapter)
            Js.Dict.entries(stats)->Belt.Array.forEach(((k, v)) => {
              Dict.set(result, k, v)
            })
            Promise.resolve(result)
          }
        }
      })
  }
}

// ---------------------------------------------------------------------------
// executeRawSql — execute arbitrary SQL
// Oracle: raw_sql.py:23-55
// Guard order: readonly FIRST, then dry_run, then confirm guard, then connected
// Disconnected message: "Not connected to database" (spec parity)
// ---------------------------------------------------------------------------

let executeRawSql = (
  facade: t,
  ~sql: string,
  ~name: option<string>=?,
  ~confirm: bool=false,
  ~dryRun: bool=false,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  // Guard 1: readonly (unconditional — dry_run does not bypass)
  switch assertNotReadonly(facade, ~opName="execute_raw_sql") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(_) => {
      // Guard 2: dry_run preview
      if dryRun {
        let result = Dict.make()
        Dict.set(result, "success", JSON.Boolean(true))
        Dict.set(result, "dry_run", JSON.Boolean(true))
        Dict.set(result, "sql", JSON.String(sql))
        Promise.resolve(result)
      } else {
        // Guard 3: confirm guard for dangerous SQL (DROP/DELETE/UPDATE)
        let dangerousRe = Js.Re.fromString("^\\s*(?i)(drop|delete|update)\\b")
        if Js.Re.exec_(dangerousRe, sql) != None && !confirm {
          let msg = "confirm=True required for execute_raw_sql"
          Promise.resolve(shapeErr(Errors.validationError(msg)))
        } else {
          // Guard 4: connected
          switch adapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
          | Error(err) => Promise.resolve(shapeErr(err))
          | Ok(adapter) => {
              adapter.executeRawSql(sql)
                ->Promise.then(r => {
                  switch r {
                  | Error(e) => Promise.resolve(shapeErr(e))
                  | Ok(rowsAffected) => {
                      let result = Dict.make()
                      Dict.set(result, "success", JSON.Boolean(true))
                      // Clamp -1 to 0 per spec
                      let clamped = rowsAffected < 0 ? 0 : rowsAffected
                      Dict.set(result, "rows_affected", JSON.Number(Int.toFloat(clamped)))
                      Promise.resolve(result)
                    }
                  }
                })
            }
          }
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// exportData — export SQL result to CSV or JSON file
// Oracle: export.py:36-103
// Guard order: readonly, connected, path (file_path), format
// Disconnected message: "Not connected to database" (spec parity)
// v1: only CSV and JSON formats (Excel deferred)
// ---------------------------------------------------------------------------

// _validateExportPath — same logic as _validateDatabasePath but for file_path arg
let _validateExportPath = (
  facade: t,
  filePath: string,
): result<string, Errors.t> => {
  let allowed = facade.allowedDirs()
  if String.startsWith(filePath, "\\\\") || String.startsWith(filePath, "//") {
    Error(Errors.pathGuardError("UNC paths not allowed"))
  } else {
    let segments = Js.String.split("/", filePath)->Belt.Array.concat(
      Js.String.split("\\", filePath)
    )
    if Belt.Array.some(segments, s => s == "..") {
      Error(Errors.pathGuardError("Path traversal not allowed"))
    } else {
      let resolved = NodeJs.Path.resolve([filePath])
      if !Belt.Array.some(allowed, dir => String.startsWith(resolved, dir)) {
        let msg = "file_path: path not allowed: " ++ filePath ++ ". Allowed directories: [" ++ Belt.Array.joinWith(allowed, ",", s => s) ++ "]"
        Error(Errors.pathGuardError(msg))
      } else {
        Ok(resolved)
      }
    }
  }
}

// _jsonValueToString — serialize a JSON.t value to a display string
let _jsonValueToString = (v: JSON.t): string => {
  switch v {
  | JSON.String(s) => s
  | JSON.Number(n) => Js.Float.toString(n)
  | JSON.Boolean(b) => b ? "true" : "false"
  | JSON.Null => ""
  | JSON.Array(_) => JSON.stringify(JSON.Array([]))
  | JSON.Object(_) => JSON.stringify(JSON.Object(Dict.make()))
  }
}

let exportData = (
  facade: t,
  ~sql: string,
  ~filePath: string,
  ~format: string,
  ~delimiter: option<string>=?,
  ~header: option<bool>=?,
  ~name: option<string>=?,
): Promise.t<dict<JSON.t>> => {
  let connName = name->Belt.Option.getWithDefault("default")
  // Guard 1: readonly
  switch assertNotReadonly(facade, ~opName="export_data") {
  | Error(err) => Promise.resolve(shapeErr(err))
  | Ok(_) => {
      // Guard 2: format validation (only CSV and JSON in v1)
      if format != "csv" && format != "json" {
        let msg = "Unknown format '" ++ format ++ "'"
        Promise.resolve(shapeErr(Errors.validationError(msg)))
      } else {
        // Guard 3: path validation (file_path arg)
        switch _validateExportPath(facade, filePath) {
        | Error(err) => Promise.resolve(shapeErr(err))
        | Ok(resolvedPath) => {
            // Guard 4: connected
            switch adapterForName(facade, ~name=connName, ~notConnectedMsg="Not connected to database") {
            | Error(err) => Promise.resolve(shapeErr(err))
            | Ok(adapter) => {
                // Execute the SELECT query to get rows
                adapter.executeQuery(sql)
                  ->Promise.then(r => {
                    switch r {
                    | Error(e) => Promise.resolve(shapeErr(e))
                    | Ok(q) => {
                        // Build rows as array<array<string>> for CSV serialization
                        let rows: array<array<string>> = Belt.Array.map(q.rows, rowDict => {
                          Belt.Array.map(q.columns, col => {
                            switch Js.Dict.get(rowDict, col) {
                            | Some(v) => _jsonValueToString(v)
                            | None => ""
                            }
                          })
                        })
                        let csvDelimiter = delimiter->Belt.Option.getWithDefault(",")
                        let csvHeader = header->Belt.Option.getWithDefault(true)
                        let content = if format == "csv" {
                          Adapters.CsvWriter.serializeWithHeaders(
                            q.columns,
                            rows,
                            ~delimiter=csvDelimiter,
                          )
                        } else {
                          // JSON format
                          JSON.stringify(JSON.Array(Belt.Array.map(q.rows, r => JSON.Object(r))))
                        }
                        // Write file
                        let _ = NodeJs.Fs.writeFileSync(resolvedPath, NodeJs.Buffer.fromString(content))
                        let result = Dict.make()
                        Dict.set(result, "success", JSON.Boolean(true))
                        Dict.set(result, "rows_exported", JSON.Number(Int.toFloat(Belt.Array.length(q.rows))))
                        Dict.set(result, "file_path", JSON.String(resolvedPath))
                        Dict.set(result, "format", JSON.String(format))
                        Promise.resolve(result)
                      }
                    }
                  })
              }
            }
          }
        }
      }
    }
  }
}
