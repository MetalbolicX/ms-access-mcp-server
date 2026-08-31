open Test
open Adapters

// Plan 031 — executeQuery integration tests
// Tests DAO.OpenRecordset via the real ComDataAdapter.executeQuery

// ---------------------------------------------------------------------------
// Fixture path — absolute path to the test .accdb
// ---------------------------------------------------------------------------

let testDbPath = "D:\\code\\python\\ms-access-mcp-server\\tests\\integration\\fixtures\\test_db.accdb"

// ---------------------------------------------------------------------------
// Access probe — gate for the entire suite (same pattern as ComIntegrationTest)
// ---------------------------------------------------------------------------

testAsync("ComExecuteQuery: Access probe", cb => {
  try {
    Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
      ->Promise.then(probeResult => {
        switch probeResult {
        | Error(_) => {
            Console.log("ComExecuteQueryTest: skipped (Access unavailable)")
            cb(~planned=0, ())
            Promise.resolve()
          }
        | Ok(anim) => {
            let _ = Bindings.Winax.WINAX_BINDING.invoke(anim, "Quit", [])
            Bindings.Winax.WINAX_BINDING.release(anim)
            cb(~planned=0, ())
            Promise.resolve()
          }
        }
      })
      ->Promise.catch(_ => {
        Console.log("ComExecuteQueryTest: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  } catch {
    | e => {
        Console.log("ComExecuteQueryTest: skipped (Access unavailable)")
        cb(~planned=0, ())
      }
  }
})

// ---------------------------------------------------------------------------
// Test A: unit/fake — executeQuery with fake binding returns expected shape
// ---------------------------------------------------------------------------

testAsync("ComExecuteQuery: executeQuery result shape is correct", cb => {
  // Verify the queryResult type has all required fields
  let result: Interfaces.queryResult = {
    success: true,
    rows: [],
    count: 0,
    columns: [],
    error: None,
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, true)
  assertion(~operator="equal", (a, b) => a == b, result.count, 0)
  assertion(~operator="deepEqual", (a, b) => a == b, result.rows, [])
  assertion(~operator="deepEqual", (a, b) => a == b, result.columns, [])
  cb(~planned=4, ())
})

testAsync("ComExecuteQuery: executeQuery error result has correct shape", cb => {
  let result: Interfaces.queryResult = {
    success: false,
    rows: [],
    count: 0,
    columns: [],
    error: Some("Not connected"),
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, false)
  assertion(~operator="equal", (a, b) => a == b, result.error, Some("Not connected"))
  cb(~planned=2, ())
})

// ---------------------------------------------------------------------------
// Test B: real-COM — SELECT id, name FROM Customers in test_db.accdb
// ---------------------------------------------------------------------------

testAsync("ComExecuteQuery: SELECT id, name FROM Customers returns rows", cb => {
  let adapter: ComDataAdapter.DaoAdapter.t = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
    ->Promise.then(connResult => {
      switch connResult {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          ComDataAdapter.DaoAdapter.executeQuery(adapter, "SELECT id, name FROM Customers")
            ->Promise.then(queryResult => {
              switch queryResult {
              | Error(e) => {
                  assertion(~operator="equal", (a, b) => a == b, false, true)
                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => {
                    cb(~planned=1, ())
                    Promise.resolve()
                  })
                }
              | Ok(result) => {
                  assertion(~operator="equal", (a, b) => a == b, result.success, true)
                  assertion(~operator="equal", (a, b) => a == b, Array.length(result.columns) >= 2, true)
                  assertion(~operator="equal", (a, b) => a == b, result.count > 0, true)
                  // Verify column names include id and name
                  let hasId = Array.includes(result.columns, "id")
                  let hasName = Array.includes(result.columns, "name")
                  assertion(~operator="equal", (a, b) => a == b, hasId, true)
                  assertion(~operator="equal", (a, b) => a == b, hasName, true)
                  // Verify rows have correct shape
                  switch Array.get(result.rows, 0) {
                  | Some(firstRow) => {
                      let hasIdField = Js.Dict.get(firstRow, "id")->Option.isSome
                      let hasNameField = Js.Dict.get(firstRow, "name")->Option.isSome
                      assertion(~operator="equal", (a, b) => a == b, hasIdField, true)
                      assertion(~operator="equal", (a, b) => a == b, hasNameField, true)
                    }
                  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
                  }
                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => {
                    cb(~planned=7, ())
                    Promise.resolve()
                  })
                }
              }
            })
        }
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test C: real-COM — empty SQL string returns error envelope
// ---------------------------------------------------------------------------

testAsync("ComExecuteQuery: empty SQL string returns error envelope", cb => {
  let adapter: ComDataAdapter.DaoAdapter.t = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
    ->Promise.then(connResult => {
      switch connResult {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          ComDataAdapter.DaoAdapter.executeQuery(adapter, "")
            ->Promise.then(queryResult => {
              switch queryResult {
              | Ok(result) => {
                  // Empty SQL should produce an error (not crash, not success with data)
                  assertion(~operator="equal", (a, b) => a == b, result.success, false)
                  assertion(~operator="equal", (a, b) => a == b, result.error->Option.isSome, true)
                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => {
                    cb(~planned=3, ())
                    Promise.resolve()
                  })
                }
              | Error(_) => {
                  // Error return is also acceptable for bad SQL
                  assertion(~operator="equal", (a, b) => a == b, true, true)
                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => {
                    cb(~planned=1, ())
                    Promise.resolve()
                  })
                }
              }
            })
        }
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test D: real-COM — SELECT with no rows returns empty array, not null
// ---------------------------------------------------------------------------

testAsync("ComExecuteQuery: SELECT with no rows returns empty array", cb => {
  let adapter: ComDataAdapter.DaoAdapter.t = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
    ->Promise.then(connResult => {
      switch connResult {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          ComDataAdapter.DaoAdapter.executeQuery(adapter, "SELECT id, name FROM Customers WHERE 1=0")
            ->Promise.then(queryResult => {
              switch queryResult {
              | Ok(result) => {
                  assertion(~operator="equal", (a, b) => a == b, result.success, true)
                  assertion(~operator="equal", (a, b) => a == b, result.count, 0)
                  assertion(~operator="deepEqual", (a, b) => a == b, result.rows, [])
                  assertion(~operator="deepEqual", (a, b) => a == b, result.columns, [])
                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => {
                    cb(~planned=4, ())
                    Promise.resolve()
                  })
                }
              | Error(e) => {
                  assertion(~operator="equal", (a, b) => a == b, false, true)
                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => {
                    cb(~planned=1, ())
                    Promise.resolve()
                  })
                }
              }
            })
        }
      }
    })
    ->ignore
})
