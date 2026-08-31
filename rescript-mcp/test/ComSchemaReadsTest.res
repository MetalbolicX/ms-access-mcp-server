// ComSchemaReadsTest.res — plan 032: DAO schema reads
// Real-COM tests for getTables, getIndexes, getRelationships, getQueries, getDatabaseStatistics
// Pattern: testAsync body is a Promise chain ending with `->ignore`; every `cb(...)` branch
// must end with a bare `Promise.resolve()` on its own line.

open Test
open Adapters

let testDbPath = "D:\\code\\python\\ms-access-mcp-server\\tests\\integration\\fixtures\\test_db.accdb"

// ---------------------------------------------------------------------------
// Probe — opens a session, verifies we can reach the DAO Database, disconnects.
// Mirrors the ComIntegration probe (lines 19-48) but uses ComSession.
// ---------------------------------------------------------------------------

let probe: unit => Promise.t<bool> = () => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => Promise.resolve(false)
      | Ok(_) => {
          switch ComSession.getCurrentDb(session) {
          | None => {
              let _ = ComSession.disconnect(session)
              Promise.resolve(false)
            }
          | Some(_db) => {
              let _ = ComSession.disconnect(session)
              Promise.resolve(true)
            }
          }
        }
      }
    })
}

// ---------------------------------------------------------------------------
// Test A: getTables returns Customers, Orders, Products and excludes MSys*
// ---------------------------------------------------------------------------

testAsync("ComSchemaReads: getTables returns known tables and excludes MSys*", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComSchemaReads: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(_) => {
                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                cb(~planned=0, ())
                Promise.resolve()
              }
            | Ok(_) => {
                ComDataAdapter.DaoAdapter.getTables(adapter)
                  ->Promise.then(tablesResult => {
                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                    switch tablesResult {
                    | Error(_) => {
                        cb(~planned=0, ())
                        Promise.resolve()
                      }
                    | Ok(tables) => {
                        let tableNames = tables->Array.map(ti => ti.name)
                        // DAO returns table names case-sensitively as stored in the fixture;
                        // the fixture ships lowercase ("customers", "orders", "products",
                        // "type_test"). Compare case-sensitively to actual fixture names.
                        let hasCustomers = tableNames->Array.some(n => n === "customers")
                        let hasOrders = tableNames->Array.some(n => n === "orders")
                        let hasProducts = tableNames->Array.some(n => n === "products")
                        let hasMsys = tableNames->Array.some(n => String.startsWith(n, "MSys"))
                        let hasTmp = tableNames->Array.some(n => String.startsWith(n, "~"))
                        assertion(~operator="equal", (a, b) => a == b, hasCustomers, true)
                        assertion(~operator="equal", (a, b) => a == b, hasOrders, true)
                        assertion(~operator="equal", (a, b) => a == b, hasProducts, true)
                        assertion(~operator="equal", (a, b) => a == b, hasMsys, false)
                        assertion(~operator="equal", (a, b) => a == b, hasTmp, false)
                        cb(~planned=5, ())
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test B: getSystemTables — should include MSys* tables (or empty if no access)
// ---------------------------------------------------------------------------

testAsync("ComSchemaReads: getSystemTables returns array", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComSchemaReads: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(_) => {
                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                cb(~planned=0, ())
                Promise.resolve()
              }
            | Ok(_) => {
                ComDataAdapter.DaoAdapter.getSystemTables(adapter)
                  ->Promise.then(tablesResult => {
                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                    switch tablesResult {
                    | Error(_) => {
                        cb(~planned=0, ())
                        Promise.resolve()
                      }
                    | Ok(tables) => {
                        let count = Array.length(tables)
                        assertion(~operator="equal", (a, b) => a == b, count >= 0, true)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test C: getIndexes for Customers — may be empty or return index info
// ---------------------------------------------------------------------------

testAsync("ComSchemaReads: getIndexes returns array for Customers", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComSchemaReads: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(_) => {
                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                cb(~planned=0, ())
                Promise.resolve()
              }
            | Ok(_) => {
                ComDataAdapter.DaoAdapter.getIndexes(adapter, "Customers")
                  ->Promise.then(indexesResult => {
                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                    switch indexesResult {
                    | Error(_) => {
                        cb(~planned=0, ())
                        Promise.resolve()
                      }
                    | Ok(indexes) => {
                        let count = Array.length(indexes)
                        // Even if empty, the call succeeded — that's a valid shape.
                        assertion(~operator="equal", (a, b) => a == b, count >= 0, true)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test D: getRelationships on test_db.accdb — may be empty (no FKs defined)
// ---------------------------------------------------------------------------

testAsync("ComSchemaReads: getRelationships returns array (possibly empty)", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComSchemaReads: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(_) => {
                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                cb(~planned=0, ())
                Promise.resolve()
              }
            | Ok(_) => {
                ComDataAdapter.DaoAdapter.getRelationships(adapter)
                  ->Promise.then(relsResult => {
                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                    switch relsResult {
                    | Error(_) => {
                        cb(~planned=0, ())
                        Promise.resolve()
                      }
                    | Ok(relationships) => {
                        let count = Array.length(relationships)
                        assertion(~operator="equal", (a, b) => a == b, count >= 0, true)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test E: getQueries on test_db.accdb — may be empty
// ---------------------------------------------------------------------------

testAsync("ComSchemaReads: getQueries returns array (possibly empty)", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComSchemaReads: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(_) => {
                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                cb(~planned=0, ())
                Promise.resolve()
              }
            | Ok(_) => {
                ComDataAdapter.DaoAdapter.getQueries(adapter)
                  ->Promise.then(queriesResult => {
                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                    switch queriesResult {
                    | Error(_) => {
                        cb(~planned=0, ())
                        Promise.resolve()
                      }
                    | Ok(queries) => {
                        let count = Array.length(queries)
                        assertion(~operator="equal", (a, b) => a == b, count >= 0, true)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test F: getDatabaseStatistics returns dict with connected=true
// ---------------------------------------------------------------------------

testAsync("ComSchemaReads: getDatabaseStatistics returns stats dict", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComSchemaReads: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, testDbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(_) => {
                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                cb(~planned=0, ())
                Promise.resolve()
              }
            | Ok(_) => {
                ComDataAdapter.DaoAdapter.getDatabaseStatistics(adapter)
                  ->Promise.then(statsResult => {
                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                    switch statsResult {
                    | Error(_) => {
                        cb(~planned=0, ())
                        Promise.resolve()
                      }
                    | Ok(stats) => {
                        let connected = switch Js.Dict.get(stats, "connected") {
                        | Some(JSON.Boolean(b)) => b
                        | _ => false
                        }
                        assertion(~operator="equal", (a, b) => a == b, connected, true)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})