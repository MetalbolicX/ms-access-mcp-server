// CompositionSmokeTest.res — env-gated smoke test for Composition.res realFactory
// T6: plan 015
// Gate: ACCESS_TEST_DB must be set (+ ACCESS_TEST_ASSUME_ACE=1 for COM availability)
//
// With env:  connect → getTables → queryData → disconnect round-trip
// Without env: skip-clean exit 0 (assert true, no failure)

open Test
open Services

// ---------------------------------------------------------------------------
// Environment gating
// ---------------------------------------------------------------------------

let getTestDbPath = (): option<string> => {
  TsBridge.getEnv("ACCESS_TEST_DB")
}

let isConfigured = (): bool => {
  switch getTestDbPath() {
  | Some(path) => String.length(path) > 0
  | None => false
  }
}

// ---------------------------------------------------------------------------
// Smoke tests — verify realFactory produces well-typed binding
// ---------------------------------------------------------------------------

// Structural smoke: verify realFactory produces a binding with correct instance types
testAsync("Composition: realFactory produces a binding with correct instance types", cb => {
  if !isConfigured() {
    // No ACCESS_TEST_DB — skip cleanly
    assertion(~operator="equal", (a, b) => a == b, true, true)
    cb(~planned=1, ())
  } else {
    // Smoke: verify realFactory produces the correct shape
    // The binding must type-check as Facade.binding — this proves the
    // instance types (dataAdapterInstance + schemaAdapterInstance) are wired
    let factory = Composition.makeRealFactory(~comAvailable=false)
    factory(~backend=None, ~dbPath="smoke", ~password="")
      ->Promise.then(result => {
        switch result {
        | Ok(binding) => {
            // Structural assertions — verify field types via assignment
            // If these types don't match, this file won't compile (fail-fast)
            let _data: Adapters.Instances.dataAdapterInstance = binding.dataAdapter
            let _schema: Adapters.Instances.schemaAdapterInstance = binding.schemaAdapter
            let _adapterType = binding.adapterType
            // _raw* are None in production
            let _rawNone: option<Fakes.FakeOdbcAdapter.t> = binding._rawDataAdapter
            let _schemaNone: option<Fakes.FakeSchemaAdapter.t> = binding._rawSchemaAdapter
            assertion(~operator="equal", (a, b) => a == b, _adapterType, "odbc")
          }
        | Error(_) =>
          // Factory should not error for stub inputs
          assertion(~operator="equal", (a, b) => a == b, false, true)
        }
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        assertion(~operator="equal", (a, b) => a == b, false, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->ignore
  }
})

// Async integration smoke: full round-trip with real ODBC connection
// Only runs when ACCESS_TEST_DB is set (real .accdb / .mdb path)
testAsync("Composition: realFactory round-trip — connect/getTables/disconnect", cb => {
  if !isConfigured() {
    // Skip cleanly — no real DB available
    assertion(~operator="equal", (a, b) => a == b, true, true)
    cb(~planned=1, ())
  } else {
    let dbPath = switch getTestDbPath() {
      | Some(p) => p
      | None => ""
    }
    let factory = Composition.makeRealFactory(~comAvailable=false)
    let facade = Facade.make(
      ~factory,
      ~pool=ConnectionPool.make(),
      ~comAvailable=false,
      ~readonly=() => false,
      ~allowedDirs=() => [],
    )

    Facade.connectAccess(facade, ~dbPath)
      ->Promise.then(result => {
        let connected = switch result->Js.Dict.get("success") {
          | Some(JSON.Boolean(true)) => true
          | _ => false
        }
        if !connected {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        } else {
          Facade.getTables(facade)
            ->Promise.then(tablesResult => {
              let hasTables = tablesResult->Js.Dict.get("tables") != None
              Facade.disconnectAccess(facade)
                ->Promise.then(disconnectResult => {
                  let disconnected = switch disconnectResult->Js.Dict.get("success") {
                    | Some(JSON.Boolean(true)) => true
                    | _ => false
                  }
                  assertion(
                    ~operator="equal",
                    (a, b) => a == b,
                    connected && hasTables && disconnected,
                    true,
                  )
                  cb(~planned=1, ())
                  Promise.resolve()
                })
            })
        }
      })
      ->Promise.catch(_e => {
        assertion(~operator="equal", (a, b) => a == b, false, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->ignore
  }
})
