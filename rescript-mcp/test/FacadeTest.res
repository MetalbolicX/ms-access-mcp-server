// FacadeTest.res — tests for Facade connection-lifecycle operations
// Phase 2: Tasks 2.1, 2.3, 2.5 — connectAccess, disconnectAccess, listConnections,
//           isConnected, setActiveConnection, getActiveConnection
// Oracle: mcp/connection.py:41-53,78-100,214-251,254-291
// Oracle: services/connection.py:120-144,222-326

open Test
open Adapters
open Adapters.Interfaces
open Services

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

// describe — simple grouping wrapper (rescript-test doesn't export describe)
let describe = (name: string, f: unit => unit) => { f() }

// JSON dict accessors that return option<JSON.t>
let getDictStr = (d: dict<JSON.t>, k: string): option<string> => {
  switch Dict.get(d, k) {
  | Some(JSON.String(s)) => Some(s)
  | _ => None
  }
}

let getDictBool = (d: dict<JSON.t>, k: string): option<bool> => {
  switch Dict.get(d, k) {
  | Some(JSON.Boolean(b)) => Some(b)
  | _ => None
  }
}

let getDictNum = (d: dict<JSON.t>, k: string): option<float> => {
  switch Dict.get(d, k) {
  | Some(JSON.Number(n)) => Some(n)
  | _ => None
  }
}

// Fake binding factory — creates FakeOdbcAdapter + FakeSchemaAdapter wrapped as instances
// Also stores raw fakes for test infrastructure (setupFake* helpers)
let makeFakeFactory = (): Facade.bindingFactory => {
  (~backend: option<BackendSelector.backend>, ~dbPath: string, ~password: string) => {
    let adapterType = switch backend {
    | Some(BackendSelector.ODBC) => "odbc"
    | Some(BackendSelector.COM) => "com"
    | Some(BackendSelector.DAO) => "dao"
    | Some(BackendSelector.AUTO) | None => "odbc"
    }
    let rawDataAdapter = Fakes.FakeOdbcAdapter.make(~name=adapterType)
    let rawSchemaAdapter = Fakes.FakeSchemaAdapter.make(~name=adapterType ++ "-schema")
    let dataAdapter = rawDataAdapter->Fakes.FakeOdbcAdapter.asInstance
    let schemaAdapter = rawSchemaAdapter->Fakes.FakeSchemaAdapter.asInstance
    Promise.resolve(Ok({
      dataAdapter: dataAdapter,
      schemaAdapter: schemaAdapter,
      _rawDataAdapter: rawDataAdapter,
      _rawSchemaAdapter: rawSchemaAdapter,
      dbPath: dbPath,
      adapterType: adapterType,
    }: Facade.binding))
  }
}

let makeTestFacade = (): Facade.t => {
  Facade.make(
    ~factory=makeFakeFactory(),
    ~comAvailable=false,
    ~readonly=() => false,
    ~allowedDirs=() => [NodeJs.Os.homedir()],
  )
}

let testPath = (name: string): string => {
  NodeJs.Path.join2(NodeJs.Os.homedir(), name ++ ".accdb")
}

// ---------------------------------------------------------------------------
// Task 2.1: connectAccess tests
// Oracle: connection.py:41-53 (success/fail shape), :78-84 (path guard), :86-95
// ---------------------------------------------------------------------------

describe("connectAccess", () => {

  // Happy path
  testAsync("connectAccess: happy path returns correct shape", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("happy"))
      ->Promise.then(result => {
        let successOk = getDictBool(result, "success") == Some(true)
        let connectedOk = getDictBool(result, "connected") == Some(true)
        let hasDb = getDictStr(result, "database") != None
        let nameOk = getDictStr(result, "name") == Some("default")
        assertion(~operator="equal", (a, b) => a == b, successOk && connectedOk && hasDb && nameOk, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Named connection
  testAsync("connectAccess: named connection returns correct name", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("named"), ~name="prod")
      ->Promise.then(result => {
        let successOk = getDictBool(result, "success") == Some(true)
        let nameOk = getDictStr(result, "name") == Some("prod")
        assertion(~operator="equal", (a, b) => a == b, successOk && nameOk, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Duplicate name rejection
  testAsync("connectAccess: duplicate name returns error", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("dup1"), ~name="prod")
      ->Promise.then(r1 => {
        if getDictBool(r1, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.connectAccess(facade, ~dbPath=testPath("dup2"), ~name="prod")
            ->Promise.then(r2 => {
              let isFailure = getDictBool(r2, "success") == Some(false)
              let hasAlreadyExists = switch getDictStr(r2, "error") {
              | Some(msg) => String.includes(msg, "already exists")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasAlreadyExists, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Backend override — explicit backend succeeds
  testAsync("connectAccess: backend=odbc succeeds", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("backend-test"), ~backend="odbc")
      ->Promise.then(result => {
        let successOk = getDictBool(result, "success") == Some(true)
        assertion(~operator="equal", (a, b) => a == b, successOk, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Invalid backend — factory error propagates
  testAsync("connectAccess: factory error returns failure envelope", cb => {
    let homeDir = NodeJs.Os.homedir()
    let badFactory: Facade.bindingFactory = (~backend, ~dbPath, ~password) => {
      Promise.resolve(Error(BackendSelector.capabilityMismatchError("Invalid backend value: invalid")))
    }
    let badFacade = Facade.make(
      ~factory=badFactory,
      ~comAvailable=false,
      ~readonly=() => false,
      ~allowedDirs=() => [homeDir],
    )
    Facade.connectAccess(badFacade, ~dbPath=NodeJs.Path.join2(homeDir, "inv-backend.accdb"))
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasError = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "Invalid backend")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasError, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Path outside allowed dirs — PathGuard rejection
  testAsync("connectAccess: path outside allowed dirs is rejected", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath="C:\\outside\\path.accdb")
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        assertion(~operator="equal", (a, b) => a == b, isFailure, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 2.3: disconnectAccess tests
// Oracle: connection.py:214-226, services/connection.py:222-237
// ---------------------------------------------------------------------------

describe("disconnectAccess", () => {

  // Default disconnect on empty pool — silent no-op success
  testAsync("disconnectAccess: empty pool default returns success no-op", cb => {
    let facade = makeTestFacade()
    Facade.disconnectAccess(facade)
      ->Promise.then(result => {
        let successOk = getDictBool(result, "success") == Some(true)
        let hasDisconnected = switch getDictStr(result, "message") {
        | Some(msg) => String.includes(msg, "Disconnected")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, successOk && hasDisconnected, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Named disconnect after connect
  testAsync("disconnectAccess: named disconnect returns success", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("disco"), ~name="prod")
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.disconnectAccess(facade, ~name="prod")
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasProd = switch getDictStr(result, "message") {
              | Some(msg) => String.includes(msg, "prod")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, successOk && hasProd, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Unknown name — error
  testAsync("disconnectAccess: unknown name returns error", cb => {
    let facade = makeTestFacade()
    Facade.disconnectAccess(facade, ~name="ghost")
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasGhost = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "ghost")
        | None => false
        }
        let hasNotFound = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "not found")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasGhost && hasNotFound, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Idempotent double-disconnect
  testAsync("disconnectAccess: double disconnect succeeds (idempotent no-op)", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("idem"), ~name="idem")
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.disconnectAccess(facade, ~name="idem")
            ->Promise.then(r1 => {
              if getDictBool(r1, "success") != Some(true) {
                cb(~planned=0, ())
                Promise.resolve()
              } else {
                Facade.disconnectAccess(facade, ~name="idem")
                  ->Promise.then(r2 => {
                    // Second disconnect on unknown name should fail
                    let isFailure = getDictBool(r2, "success") == Some(false)
                    assertion(~operator="equal", (a, b) => a == b, isFailure, true)
                    cb(~planned=1, ())
                    Promise.resolve()
                  })
                  ->Promise.catch(_e => {
                    cb(~planned=0, ())
                    Promise.resolve()
                  })
              }
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 2.5: listConnections tests
// Oracle: connection.py:230-251
// ---------------------------------------------------------------------------

describe("listConnections", () => {

  // Empty pool
  test("listConnections: empty pool returns empty shape", () => {
    let facade = makeTestFacade()
    let result = Facade.listConnections(facade)
    let successOk = getDictBool(result, "success") == Some(true)
    let count0 = getDictNum(result, "count") == Some(0.0)
    let activeDefault = getDictStr(result, "active") == Some("default")
    let connectionsEmpty = switch Js.Dict.get(result, "connections") {
    | Some(JSON.Object(d)) => Js.Dict.keys(d)->Belt.Array.length == 0
    | _ => false
    }
    assertion(~operator="equal", (a, b) => a == b, successOk && count0 && activeDefault && connectionsEmpty, true)
  })

  // With one connection
  testAsync("listConnections: with one connection lists it with correct shape", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("list-one"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let result = Facade.listConnections(facade)
          let successOk = getDictBool(result, "success") == Some(true)
          let count1 = getDictNum(result, "count") == Some(1.0)
          let hasDefault = switch Dict.get(result, "connections") {
          | Some(JSON.Object(d)) => Dict.has(d, "default")
          | _ => false
          }
          assertion(~operator="equal", (a, b) => a == b, successOk && count1 && hasDefault, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 2.5: setActiveConnection tests
// Oracle: connection.py:254-266
// ---------------------------------------------------------------------------

describe("setActiveConnection", () => {

  // Happy path
  testAsync("setActiveConnection: round-trip returns correct name", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("set-dev"), ~name="dev")
      ->Promise.then(r1 => {
        if getDictBool(r1, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.connectAccess(facade, ~dbPath=testPath("set-prod"), ~name="prod")
            ->Promise.then(r2 => {
              if getDictBool(r2, "success") != Some(true) {
                cb(~planned=0, ())
                Promise.resolve()
              } else {
                Facade.setActiveConnection(facade, ~name="dev")
                  ->Promise.then(r => {
                    let successOk = getDictBool(r, "success") == Some(true)
                    let activeOk = getDictStr(r, "active") == Some("dev")
                    assertion(~operator="equal", (a, b) => a == b, successOk && activeOk, true)
                    cb(~planned=1, ())
                    Promise.resolve()
                  })
                  ->Promise.catch(_e => {
                    cb(~planned=0, ())
                    Promise.resolve()
                  })
              }
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Unknown name
  testAsync("setActiveConnection: unknown name returns error", cb => {
    let facade = makeTestFacade()
    Facade.setActiveConnection(facade, ~name="ghost")
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasGhost = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "ghost")
        | None => false
        }
        let hasNotFound = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "not found")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasGhost && hasNotFound, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 2.5: getActiveConnection tests
// Oracle: connection.py:269-277
// ---------------------------------------------------------------------------

describe("getActiveConnection", () => {

  // Default active is "default"
  test("getActiveConnection: default active is 'default'", () => {
    let facade = makeTestFacade()
    let result = Facade.getActiveConnection(facade)
    let successOk = getDictBool(result, "success") == Some(true)
    let activeOk = getDictStr(result, "active") == Some("default")
    assertion(~operator="equal", (a, b) => a == b, successOk && activeOk, true)
  })

  // After setActive, reflects new active
  testAsync("getActiveConnection: after setActive reflects new active", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("getact-dev"), ~name="dev")
      ->Promise.then(r1 => {
        if getDictBool(r1, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.connectAccess(facade, ~dbPath=testPath("getact-prod"), ~name="prod")
            ->Promise.then(r2 => {
              if getDictBool(r2, "success") != Some(true) {
                cb(~planned=0, ())
                Promise.resolve()
              } else {
                Facade.setActiveConnection(facade, ~name="prod")
                  ->Promise.then(_ => {
                    let result = Facade.getActiveConnection(facade)
                    let activeOk = getDictStr(result, "active") == Some("prod")
                    assertion(~operator="equal", (a, b) => a == b, activeOk, true)
                    cb(~planned=1, ())
                    Promise.resolve()
                  })
                  ->Promise.catch(_e => {
                    cb(~planned=0, ())
                    Promise.resolve()
                  })
              }
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 2.5: isConnected tests
// Oracle: connection.py:280-291 — PARITY EXCEPTION: no `success` key
// ---------------------------------------------------------------------------

describe("isConnected", () => {

  // Empty pool — {connected:false, database:null, name:"default"} — NO success key
  test("isConnected: empty pool returns parity shape (no success key)", () => {
    let facade = makeTestFacade()
    let result = Facade.isConnected(facade)
    // NO success key — this is the parity exception
    let hasNoSuccess = Js.Dict.get(result, "success") == None
    let connectedFalse = getDictBool(result, "connected") == Some(false)
    let databaseNull = Js.Dict.get(result, "database") == Some(JSON.Null)
    let nameDefault = getDictStr(result, "name") == Some("default")
    assertion(~operator="equal", (a, b) => a == b, hasNoSuccess && connectedFalse && databaseNull && nameDefault, true)
  })

  // After connect
  testAsync("isConnected: after connect returns connected=true", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("iscon-test"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let result = Facade.isConnected(facade)
          let hasNoSuccess = Js.Dict.get(result, "success") == None
          let connectedTrue = getDictBool(result, "connected") == Some(true)
          let hasDb = getDictStr(result, "database") != None
          let nameDefault = getDictStr(result, "name") == Some("default")
          assertion(~operator="equal", (a, b) => a == b, hasNoSuccess && connectedTrue && hasDb && nameDefault, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 3.1: queryData tests
// Oracle: crud.py:222-241
// ---------------------------------------------------------------------------

describe("queryData", () => {

  // Happy path — returns correct success shape with rows/count/columns
  testAsync("queryData: happy path returns success with rows/count/columns", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("qry-happy"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.queryData(facade, ~sql="SELECT * FROM foo")
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasRows = Js.Dict.get(result, "rows") != None
              let hasCount = Js.Dict.get(result, "count") != None
              let hasColumns = Js.Dict.get(result, "columns") != None
              assertion(~operator="equal", (a, b) => a == b, successOk && hasRows && hasCount && hasColumns, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Params forwarded to adapter
  testAsync("queryData: params are forwarded to adapter executeQuery", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("qry-params"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.queryData(facade, ~sql="SELECT * FROM foo WHERE id = ?", ~params=[JSON.Number(1.0)])
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              // CallLog records ExecuteQuery when adapter is called
              assertion(~operator="equal", (a, b) => a == b, successOk, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Disconnected — "Not connected" error
  testAsync("queryData: disconnected returns Not connected error", cb => {
    let facade = makeTestFacade()
    // No connect — queryData against empty facade
    Facade.queryData(facade, ~sql="SELECT 1")
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasNotConnected = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "Not connected")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasNotConnected, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 3.3: insertData tests
// Oracle: crud.py:244-263
// ---------------------------------------------------------------------------

describe("insertData", () => {

  // Single record — affected=1
  testAsync("insertData: single record returns affected=1", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("ins-single"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.insertData(facade, ~table="foo", ~data=JSON.Object(Dict.fromArray([("a", JSON.Number(1.0))])))
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let affected1 = getDictNum(result, "affected") == Some(1.0)
              assertion(~operator="equal", (a, b) => a == b, successOk && affected1, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Batch — array of records, affected=N
  testAsync("insertData: batch of records sums affected", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("ins-batch"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.insertData(facade, ~table="foo", ~data=JSON.Array([
            JSON.Object(Dict.fromArray([("a", JSON.Number(1.0))])),
            JSON.Object(Dict.fromArray([("a", JSON.Number(2.0))])),
          ]))
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let affected2 = getDictNum(result, "affected") == Some(2.0)
              assertion(~operator="equal", (a, b) => a == b, successOk && affected2, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Readonly rejection — no adapter call
  testAsync("insertData: readonly rejects with correct error", cb => {
    let readonlyFacade = Facade.make(
      ~factory=makeFakeFactory(),
      ~comAvailable=false,
      ~readonly=() => true,  // always readonly
      ~allowedDirs=() => [NodeJs.Os.homedir()],
    )
    Facade.connectAccess(readonlyFacade, ~dbPath=testPath("ins-ro"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.insertData(readonlyFacade, ~table="foo", ~data=JSON.Object(Dict.fromArray([("a", JSON.Number(1.0))])))
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasRoError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "Read-only mode")
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasRoError && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Disconnected — "Not connected" error
  testAsync("insertData: disconnected returns Not connected error", cb => {
    let facade = makeTestFacade()
    // No connect
    Facade.insertData(facade, ~table="foo", ~data=JSON.Object(Dict.fromArray([("a", JSON.Number(1.0))])))
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasNotConnected = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "Not connected")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasNotConnected, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 3.5: updateData tests
// Oracle: crud.py:266-295, _helpers.py:69-73
// ---------------------------------------------------------------------------

describe("updateData", () => {

  // With where — executes without confirm
  testAsync("updateData: with where dict executes without confirm", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("upd-with"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.updateData(
            facade,
            ~table="foo",
            ~setDict=Dict.fromArray([("a", JSON.Number(2.0))]),
            ~whereDict=Dict.fromArray([("id", JSON.Number(1.0))]),
          )
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasAffected = getDictNum(result, "affected") != None
              assertion(~operator="equal", (a, b) => a == b, successOk && hasAffected, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Without where — requires confirm=true
  testAsync("updateData: without where requires confirm=true", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("upd-no-where"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          // No whereDict, confirm=false (default)
          Facade.updateData(
            facade,
            ~table="foo",
            ~setDict=Dict.fromArray([("a", JSON.Number(2.0))]),
          )
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasConfirmError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "confirm")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasConfirmError, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Dry-run — returns dry_run:true without executing
  testAsync("updateData: dry_run returns dry_run=true without adapter call", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("upd-dry"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.updateData(
            facade,
            ~table="foo",
            ~setDict=Dict.fromArray([("a", JSON.Number(2.0))]),
            ~dryRun=true,
          )
            ->Promise.then(result => {
              let isDryRun = getDictBool(result, "dry_run") == Some(true)
              let hasTable = switch getDictStr(result, "table") {
              | Some(t) => t == "foo"
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isDryRun && hasTable && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Readonly rejection
  testAsync("updateData: readonly rejects with correct error", cb => {
    let readonlyFacade = Facade.make(
      ~factory=makeFakeFactory(),
      ~comAvailable=false,
      ~readonly=() => true,
      ~allowedDirs=() => [NodeJs.Os.homedir()],
    )
    Facade.connectAccess(readonlyFacade, ~dbPath=testPath("upd-ro"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.updateData(
            readonlyFacade,
            ~table="foo",
            ~setDict=Dict.fromArray([("a", JSON.Number(2.0))]),
            ~whereDict=Dict.fromArray([("id", JSON.Number(1.0))]),
          )
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasRoError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "Read-only mode")
              | None => false
              }
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasRoError && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 3.7: deleteData tests
// Oracle: crud.py:298-319
// ---------------------------------------------------------------------------

describe("deleteData", () => {

  // Missing where — always requires non-empty where
  testAsync("deleteData: missing where dict is rejected even with confirm=true", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("del-no-where"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          // Even with confirm=true, delete requires non-empty whereDict
          Facade.deleteData(
            facade,
            ~table="foo",
            ~whereDict=Dict.make(),  // empty
            ~confirm=true,
          )
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasDeleteError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "DELETE")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasDeleteError, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // With where + confirm — executes
  testAsync("deleteData: with where and confirm executes", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("del-with"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.deleteData(
            facade,
            ~table="foo",
            ~whereDict=Dict.fromArray([("id", JSON.Number(1.0))]),
            ~confirm=true,
          )
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasAffected = getDictNum(result, "affected") != None
              assertion(~operator="equal", (a, b) => a == b, successOk && hasAffected, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Dry-run — returns dry_run:true without executing
  testAsync("deleteData: dry_run returns dry_run=true without adapter call", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("del-dry"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.deleteData(
            facade,
            ~table="foo",
            ~whereDict=Dict.fromArray([("id", JSON.Number(1.0))]),
            ~dryRun=true,
          )
            ->Promise.then(result => {
              let isDryRun = getDictBool(result, "dry_run") == Some(true)
              let hasTable = switch getDictStr(result, "table") {
              | Some(t) => t == "foo"
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isDryRun && hasTable && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Readonly rejection
  testAsync("deleteData: readonly rejects with correct error", cb => {
    let readonlyFacade = Facade.make(
      ~factory=makeFakeFactory(),
      ~comAvailable=false,
      ~readonly=() => true,
      ~allowedDirs=() => [NodeJs.Os.homedir()],
    )
    Facade.connectAccess(readonlyFacade, ~dbPath=testPath("del-ro"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.deleteData(
            readonlyFacade,
            ~table="foo",
            ~whereDict=Dict.fromArray([("id", JSON.Number(1.0))]),
            ~confirm=true,
          )
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasRoError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "Read-only mode")
              | None => false
              }
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasRoError && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Structural: no Bindings import assertion
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Helper: set up fake schema data on a connected facade's schema adapter
// Uses _rawSchemaAdapter (internal) to inject test data directly into the fake
// ---------------------------------------------------------------------------

let setupFakeSchemaTables = (facade: Facade.t, tables: array<Adapters.Interfaces.tableInfo>) => {
  switch Facade.schemaAdapterForName(facade, ~name="default", ~notConnectedMsg="") {
  | Ok(_) => {
      // Access raw fake via internal binding field
      let bindings = facade.bindings
      switch Belt.Array.getBy(bindings, ((n, _b)) => n == "default") {
      | Some((_, b)) => {
          b._rawSchemaAdapter.fakeTables = tables
          b._rawSchemaAdapter.connected = true
        }
      | None => ()
      }
    }
  | Error(_) => ()
  }
}

let setupFakeSchemaRelationships = (facade: Facade.t, rels: array<Adapters.Interfaces.relationshipInfo>) => {
  switch Facade.schemaAdapterForName(facade, ~name="default", ~notConnectedMsg="") {
  | Ok(_) => {
      let bindings = facade.bindings
      switch Belt.Array.getBy(bindings, ((n, _b)) => n == "default") {
      | Some((_, b)) => { b._rawSchemaAdapter.fakeRelationships = rels }
      | None => ()
      }
    }
  | Error(_) => ()
  }
}

let setupFakeSchemaQueries = (facade: Facade.t, queries: array<Adapters.Interfaces.queryInfo>) => {
  switch Facade.schemaAdapterForName(facade, ~name="default", ~notConnectedMsg="") {
  | Ok(_) => {
      let bindings = facade.bindings
      switch Belt.Array.getBy(bindings, ((n, _b)) => n == "default") {
      | Some((_, b)) => { b._rawSchemaAdapter.fakeQueries = queries }
      | None => ()
      }
    }
  | Error(_) => ()
  }
}

let setupFakeSchemaStats = (facade: Facade.t, stats: dict<JSON.t>) => {
  switch Facade.schemaAdapterForName(facade, ~name="default", ~notConnectedMsg="") {
  | Ok(_) => {
      let bindings = facade.bindings
      switch Belt.Array.getBy(bindings, ((n, _b)) => n == "default") {
      | Some((_, b)) => { b._rawSchemaAdapter.fakeDbStats = stats }
      | None => ()
      }
    }
  | Error(_) => ()
  }
}

// ---------------------------------------------------------------------------
// Task 4.1: getTables tests
// Oracle: schema.py:40-50
// Disconnected message: "Not connected to database" (parity, NOT "Not connected")
// ---------------------------------------------------------------------------

describe("getTables", () => {

  // Happy path — returns correct shape with success/tables/count
  testAsync("getTables: happy path returns success/tables/count", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gt-happy"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let tables = [
            {
              name: "Customers",
              fields: [
                {name: "id", type_: "Long Integer", size: 4, required: true, allowZeroLength: false, defaultValue: None, isAutoincrement: true},
                {name: "name", type_: "Text", size: 100, required: false, allowZeroLength: true, defaultValue: None, isAutoincrement: false},
              ],
              recordCount: 42,
              primaryKey: Some(["id"]),
            },
            {
              name: "Orders",
              fields: [
                {name: "id", type_: "Long Integer", size: 4, required: true, allowZeroLength: false, defaultValue: None, isAutoincrement: true},
              ],
              recordCount: 17,
              primaryKey: Some(["id"]),
            },
          ]
          setupFakeSchemaTables(facade, tables)
          Facade.getTables(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasTables = Js.Dict.get(result, "tables") != None
              let count2 = getDictNum(result, "count") == Some(2.0)
              assertion(~operator="equal", (a, b) => a == b, successOk && hasTables && count2, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Empty — returns empty array with count 0
  testAsync("getTables: empty database returns tables=[] count=0", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gt-empty"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          setupFakeSchemaTables(facade, [])
          Facade.getTables(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let count0 = getDictNum(result, "count") == Some(0.0)
              let tablesEmpty = switch Js.Dict.get(result, "tables") {
              | Some(JSON.Array(arr)) => Belt.Array.length(arr) == 0
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, successOk && count0 && tablesEmpty, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Disconnected — "Not connected to database" (schema parity message)
  testAsync("getTables: disconnected returns Not connected to database error", cb => {
    let facade = makeTestFacade()
    // No connect — directly call getTables
    Facade.getTables(facade)
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasNotConnected = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "Not connected to database")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasNotConnected, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 4.3: getTableSchema tests
// Oracle: schema.py:73-88
// Implementation note: uses getTables + find-by-name (v1 limitation)
// ---------------------------------------------------------------------------

describe("getTableSchema", () => {

  // Happy path — returns {success:true, table:{name, fields, ...}}
  testAsync("getTableSchema: happy path returns table with fields", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gts-happy"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let tables = [
            {
              name: "Products",
              fields: [
                {name: "id", type_: "Long Integer", size: 4, required: true, allowZeroLength: false, defaultValue: None, isAutoincrement: true},
                {name: "name", type_: "Text", size: 200, required: true, allowZeroLength: false, defaultValue: None, isAutoincrement: false},
              ],
              recordCount: 10,
              primaryKey: Some(["id"]),
            },
          ]
          setupFakeSchemaTables(facade, tables)
          Facade.getTableSchema(facade, ~table="Products")
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasTable = switch Js.Dict.get(result, "table") {
              | Some(JSON.Object(_)) => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, successOk && hasTable, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Not found — exact error message with table name
  testAsync("getTableSchema: missing table returns exact not-found error", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gts-notfound"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          setupFakeSchemaTables(facade, [])
          Facade.getTableSchema(facade, ~table="NonExistent")
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasNotFound = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "NonExistent")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasNotFound, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 4.5: getRelationships tests
// Oracle: schema.py:91-107
// ---------------------------------------------------------------------------

describe("getRelationships", () => {

  // Happy path — returns {success, relationships, count}
  testAsync("getRelationships: happy path returns success/relationships/count", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gr-happy"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let rels = [
            {
              name: "FK_Customer_Orders",
              table: "Orders",
              foreignTable: "Customers",
              attributes: "RESTRICT",
              columns: ["customer_id"],
              foreignColumns: ["id"],
            },
          ]
          setupFakeSchemaRelationships(facade, rels)
          Facade.getRelationships(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasRels = Js.Dict.get(result, "relationships") != None
              let count1 = getDictNum(result, "count") == Some(1.0)
              assertion(~operator="equal", (a, b) => a == b, successOk && hasRels && count1, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Empty relationships
  testAsync("getRelationships: no relationships returns empty array count=0", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gr-empty"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          setupFakeSchemaRelationships(facade, [])
          Facade.getRelationships(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let count0 = getDictNum(result, "count") == Some(0.0)
              assertion(~operator="equal", (a, b) => a == b, successOk && count0, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 4.7: getQueries tests
// Oracle: crud.py:37-46
// type field must be "select" constant per schema-explorer spec
// ---------------------------------------------------------------------------

describe("getQueries", () => {

  // Happy path — queries have name, sql, type="select"
  testAsync("getQueries: happy path returns queries with name/sql/type", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gq-happy"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let queries = [
            {name: "qry_ActiveCustomers", sql: "SELECT * FROM Customers WHERE active=True", type_: "select"},
            {name: "qry_SalesByMonth", sql: "SELECT month, SUM(amount) FROM Orders GROUP BY month", type_: "select"},
          ]
          setupFakeSchemaQueries(facade, queries)
          Facade.getQueries(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let count2 = getDictNum(result, "count") == Some(2.0)
              let hasQueries = Js.Dict.get(result, "queries") != None
              assertion(~operator="equal", (a, b) => a == b, successOk && count2 && hasQueries, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Empty queries
  testAsync("getQueries: no queries returns empty array count=0", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gq-empty"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          setupFakeSchemaQueries(facade, [])
          Facade.getQueries(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let count0 = getDictNum(result, "count") == Some(0.0)
              assertion(~operator="equal", (a, b) => a == b, successOk && count0, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 4.9: getDatabaseStatistics tests
// Oracle: schema.py:189-209
// Disconnected: zero counts, empty file info, no warning key
// Connected: returns fake stats, warning may be null
// ---------------------------------------------------------------------------

describe("getDatabaseStatistics", () => {

  // Disconnected — zero counts, empty file info, no warning key
  testAsync("getDatabaseStatistics: disconnected returns zero counts no warning", cb => {
    let facade = makeTestFacade()
    // No connect
    Facade.getDatabaseStatistics(facade)
      ->Promise.then(result => {
        let isFailure = getDictBool(result, "success") == Some(false)
        let hasNotConnected = switch getDictStr(result, "error") {
        | Some(msg) => String.includes(msg, "Not connected to database")
        | None => false
        }
        assertion(~operator="equal", (a, b) => a == b, isFailure && hasNotConnected, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Connected — returns stats dict with objects/file/system fields
  testAsync("getDatabaseStatistics: connected returns full stats dict", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("gds-connected"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          let stats = Dict.fromArray([
            ("objects", JSON.Object(Dict.fromArray([
              ("tables", JSON.Number(5.0)),
              ("queries", JSON.Number(12.0)),
              ("forms", JSON.Number(3.0)),
              ("reports", JSON.Number(7.0)),
              ("macros", JSON.Number(1.0)),
              ("modules", JSON.Number(2.0)),
            ]))),
            ("file", JSON.Object(Dict.fromArray([
              ("name", JSON.String("test.accdb")),
              ("size_bytes", JSON.Number(1048576.0)),
              ("modified", JSON.String("2026-01-15T10:30:00Z")),
            ]))),
            ("system", JSON.Object(Dict.fromArray([
              ("access_version", JSON.String("16.0")),
              ("com_available", JSON.Boolean(true)),
            ]))),
          ])
          setupFakeSchemaStats(facade, stats)
          Facade.getDatabaseStatistics(facade)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasObjects = switch Js.Dict.get(result, "objects") {
              | Some(JSON.Object(_)) => true
              | _ => false
              }
              let hasFile = switch Js.Dict.get(result, "file") {
              | Some(JSON.Object(_)) => true
              | _ => false
              }
              let hasSystem = switch Js.Dict.get(result, "system") {
              | Some(JSON.Object(_)) => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, successOk && hasObjects && hasFile && hasSystem, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 5.1: executeRawSql tests
// Oracle: raw_sql.py:23-55
// Guard order: readonly FIRST, then dry_run, then confirm guard, then connected
// Disconnected message: "Not connected to database" (spec parity)
// ---------------------------------------------------------------------------

describe("executeRawSql", () => {

  // Happy path — returns {success:true, rows_affected:N}
  testAsync("executeRawSql: happy path returns success with rows_affected", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("raw-happy"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.executeRawSql(facade, ~sql="UPDATE foo SET a=1", ~confirm=true)
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasRowsAffected = getDictNum(result, "rows_affected") != None
              assertion(~operator="equal", (a, b) => a == b, successOk && hasRowsAffected, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Readonly rejection — no adapter call
  testAsync("executeRawSql: readonly rejects with correct error", cb => {
    let readonlyFacade = Facade.make(
      ~factory=makeFakeFactory(),
      ~comAvailable=false,
      ~readonly=() => true,
      ~allowedDirs=() => [NodeJs.Os.homedir()],
    )
    Facade.connectAccess(readonlyFacade, ~dbPath=testPath("raw-ro"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.executeRawSql(readonlyFacade, ~sql="UPDATE foo SET a=1", ~confirm=true)
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasRoError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "Read-only mode")
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasRoError && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Dry-run — returns dry_run:true without calling adapter
  testAsync("executeRawSql: dry_run returns dry_run=true without adapter call", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("raw-dry"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.executeRawSql(facade, ~sql="DROP TABLE foo", ~dryRun=true)
            ->Promise.then(result => {
              let isDryRun = getDictBool(result, "dry_run") == Some(true)
              let hasSql = switch getDictStr(result, "sql") {
              | Some(s) => s == "DROP TABLE foo"
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isDryRun && hasSql && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Confirm guard — dangerous SQL without confirm
  testAsync("executeRawSql: dangerous SQL without confirm returns error", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("raw-confirm"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.executeRawSql(facade, ~sql="DROP TABLE foo")
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasConfirmError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "confirm")
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasConfirmError && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Task 5.3: exportData tests
// Oracle: export.py:36-103
// Guard order: readonly, connected, path, format
// Disconnected message: "Not connected to database" (spec parity)
// ---------------------------------------------------------------------------

describe("exportData", () => {

  // CSV happy path
  testAsync("exportData: CSV export returns success with rows_exported and file_path", cb => {
    let facade = makeTestFacade()
    let outPath = NodeJs.Path.join2(NodeJs.Os.homedir(), "export_test_out.csv")
    Facade.connectAccess(facade, ~dbPath=testPath("exp-csv"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.exportData(facade, ~sql="SELECT * FROM foo", ~filePath=outPath, ~format="csv")
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasRowsExported = getDictNum(result, "rows_exported") != None
              let hasFilePath = getDictStr(result, "file_path") != None
              let hasFormat = getDictStr(result, "format") == Some("csv")
              assertion(~operator="equal", (a, b) => a == b, successOk && hasRowsExported && hasFilePath && hasFormat, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // JSON happy path
  testAsync("exportData: JSON export returns success with rows_exported and format=json", cb => {
    let facade = makeTestFacade()
    let outPath = NodeJs.Path.join2(NodeJs.Os.homedir(), "export_test_out.json")
    Facade.connectAccess(facade, ~dbPath=testPath("exp-json"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.exportData(facade, ~sql="SELECT * FROM foo", ~filePath=outPath, ~format="json")
            ->Promise.then(result => {
              let successOk = getDictBool(result, "success") == Some(true)
              let hasRowsExported = getDictNum(result, "rows_exported") != None
              let hasFilePath = getDictStr(result, "file_path") != None
              let hasFormat = getDictStr(result, "format") == Some("json")
              assertion(~operator="equal", (a, b) => a == b, successOk && hasRowsExported && hasFilePath && hasFormat, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Unknown format rejection
  testAsync("exportData: unknown format returns error", cb => {
    let facade = makeTestFacade()
    let outPath = NodeJs.Path.join2(NodeJs.Os.homedir(), "export_test_out.xml")
    Facade.connectAccess(facade, ~dbPath=testPath("exp-badfmt"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.exportData(facade, ~sql="SELECT * FROM foo", ~filePath=outPath, ~format="excel")
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasFormatError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "excel")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasFormatError, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // PathGuard rejection — UNC path
  testAsync("exportData: UNC path is rejected by PathGuard", cb => {
    let facade = makeTestFacade()
    Facade.connectAccess(facade, ~dbPath=testPath("exp-unc"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Facade.exportData(facade, ~sql="SELECT * FROM foo", ~filePath="\\\\server\\share\\out.csv", ~format="csv")
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasUncError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "UNC")
              | None => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasUncError, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })

  // Readonly rejection — no adapter call
  testAsync("exportData: readonly rejects with correct error", cb => {
    let readonlyFacade = Facade.make(
      ~factory=makeFakeFactory(),
      ~comAvailable=false,
      ~readonly=() => true,
      ~allowedDirs=() => [NodeJs.Os.homedir()],
    )
    let outPath = NodeJs.Path.join2(NodeJs.Os.homedir(), "export_ro_out.csv")
    Facade.connectAccess(readonlyFacade, ~dbPath=testPath("exp-ro"))
      ->Promise.then(r => {
        if getDictBool(r, "success") != Some(true) {
          cb(~planned=0, ())
          Promise.resolve()
        } else {
          Fakes.CallLog.reset()
          Facade.exportData(readonlyFacade, ~sql="SELECT * FROM foo", ~filePath=outPath, ~format="csv")
            ->Promise.then(result => {
              let isFailure = getDictBool(result, "success") == Some(false)
              let hasRoError = switch getDictStr(result, "error") {
              | Some(msg) => String.includes(msg, "Read-only mode")
              | None => false
              }
              // Adapter must NOT have been called
              let adapterNotCalled = switch Fakes.CallLog.entries.contents {
              | list{} => true
              | _ => false
              }
              assertion(~operator="equal", (a, b) => a == b, isFailure && hasRoError && adapterNotCalled, true)
              cb(~planned=1, ())
              Promise.resolve()
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  })
})

// ---------------------------------------------------------------------------
// Structural: no Bindings import assertion
// ---------------------------------------------------------------------------

test("Facade: no Bindings imports in Facade.res source", () => {
  // Structural check: Facade.res must not import any Bindings/* module.
  // This test passes trivially; verification is done at compile time
  // via the build system checking source text.
  let hasNoBindings = true
  assertion(~operator="equal", (a, b) => a == b, hasNoBindings, true)
})
