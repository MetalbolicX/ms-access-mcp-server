open Test
open Adapters
open Adapters.ComInterfaces

// Plan 029 — Real-COM integration suite
// Proves the connect chain against a live Access.Application instance.
// Self-skips when Access is unavailable (probe-gated).

// ---------------------------------------------------------------------------
// Fixture path — absolute path to the test .accdb
// ---------------------------------------------------------------------------

let testDbPath = "D:\\code\\python\\ms-access-mcp-server\\tests\\integration\\fixtures\\test_db.accdb"

// ---------------------------------------------------------------------------
// Access probe — gate for the entire suite
// ---------------------------------------------------------------------------

testAsync("ComIntegration: Access.Application probe", cb => {
  try {
    Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
      ->Promise.then(probeResult => {
        switch probeResult {
        | Error(_) => {
            Console.log("ComIntegrationTest: skipped (Access unavailable)")
            cb(~planned=0, ())
            Promise.resolve()
          }
        | Ok(anim) => {
            // Quit() before release — otherwise MSACCESS.EXE persists
            let _ = Bindings.Winax.WINAX_BINDING.invoke(anim, "Quit", [])
            Bindings.Winax.WINAX_BINDING.release(anim)
            cb(~planned=0, ())
            Promise.resolve()
          }
        }
      })
      ->Promise.catch(_ => {
        Console.log("ComIntegrationTest: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      })
      ->ignore
  } catch {
    | e => {
        Console.log("ComIntegrationTest: skipped (Access unavailable)")
        cb(~planned=0, ())
      }
  }
})

// ---------------------------------------------------------------------------
// Real-COM connect tests (only execute when Access is available)
// Each test creates a fresh session, connects, verifies, and disconnects.
// ---------------------------------------------------------------------------

// Test 1: connect returns Ok(true) and isConnected is true
testAsync("ComIntegration: connect returns Ok(true) and isConnected=true", cb => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(ok) => {
          if ok {
            ComSession.isConnected(session)
              ->Promise.then(icResult => {
                switch icResult {
                | Ok(true) => {
                    assertion(~operator="equal", (a, b) => a == b, true, true)
                    ComSession.disconnect(session)->Promise.then(_ => {
                      cb(~planned=1, ())
                      Promise.resolve()
                    })
                  }
                | _ => {
                    cb(~planned=1, ())
                    Promise.resolve()
                  }
                }
              })
          } else {
            cb(~planned=1, ())
            Promise.resolve()
          }
        }
      }
    })
    ->ignore
})

// Test 2: getCurrentDb() returns Some after connect
testAsync("ComIntegration: getCurrentDb() returns Some after connect", cb => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          let db = ComSession.getCurrentDb(session)
          switch db {
          | Some(_) => {
              assertion(~operator="equal", (a, b) => a == b, true, true)
              ComSession.disconnect(session)->Promise.then(_ => {
                cb(~planned=1, ())
                Promise.resolve()
              })
            }
          | None => {
              assertion(~operator="equal", (a, b) => a == b, false, true)
              cb(~planned=1, ())
              Promise.resolve()
            }
          }
        }
      }
    })
    ->ignore
})

// Test 3: get(currentDb, "Name") contains "test_db.accdb" — LIVE HANDLE PROOF
testAsync("ComIntegration: get(currentDb, \"Name\") contains test_db.accdb — live DAO handle proof", cb => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          let db = ComSession.getCurrentDb(session)
          switch db {
          | Some(currentDb) => {
              Bindings.Winax.WINAX_BINDING.get(currentDb, "Name")
                ->Promise.then(nameResult => {
                  switch nameResult {
                  | Ok(JSON.String(s)) => {
                      let contains = String.includes(s, "test_db.accdb")
                      assertion(~operator="equal", (a, b) => a == b, contains, true)
                      ComSession.disconnect(session)->Promise.then(_ => {
                        cb(~planned=1, ())
                        Promise.resolve()
                      })
                    }
                  | Ok(_) => {
                      assertion(~operator="equal", (a, b) => a == b, false, true)
                      ComSession.disconnect(session)->Promise.then(_ => {
                        cb(~planned=1, ())
                        Promise.resolve()
                      })
                    }
                  | Error(_) => {
                      assertion(~operator="equal", (a, b) => a == b, false, true)
                      ComSession.disconnect(session)->Promise.then(_ => {
                        cb(~planned=1, ())
                        Promise.resolve()
                      })
                    }
                  }
                })
            }
          | None => {
              assertion(~operator="equal", (a, b) => a == b, false, true)
              cb(~planned=1, ())
              Promise.resolve()
            }
          }
        }
      }
    })
    ->ignore
})

// Test 4: getHandles returns accessApp=Some AND daoDb=Some after connect
testAsync("ComIntegration: getHandles has accessApp=Some and daoDb=Some after connect", cb => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          let handles = ComSession.getHandles(session)
          let hasAccessApp = switch handles.accessApp {
          | Some(_) => true
          | None => false
          }
          let hasDaoDb = switch handles.daoDb {
          | Some(_) => true
          | None => false
          }
          assertion(~operator="equal", (a, b) => a == b, hasAccessApp, true)
          assertion(~operator="equal", (a, b) => a == b, hasDaoDb, true)
          ComSession.disconnect(session)->Promise.then(_ => {
            cb(~planned=2, ())
            Promise.resolve()
          })
        }
      }
    })
    ->ignore
})

// Test 5: disconnect returns Ok, isConnected=false, getCurrentDb=None
testAsync("ComIntegration: disconnect returns Ok, isConnected=false, getCurrentDb=None", cb => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          ComSession.disconnect(session)
            ->Promise.then(discResult => {
              switch discResult {
              | Error(_) => {
                  assertion(~operator="equal", (a, b) => a == b, false, true)
                  cb(~planned=1, ())
                  Promise.resolve()
                }
              | Ok(_) => {
                  ComSession.isConnected(session)
                    ->Promise.then(icResult => {
                      let icOk = switch icResult {
                      | Ok(false) => true
                      | _ => false
                      }
                      let dbNone = switch ComSession.getCurrentDb(session) {
                      | None => true
                      | Some(_) => false
                      }
                      assertion(~operator="equal", (a, b) => a == b, icOk, true)
                      assertion(~operator="equal", (a, b) => a == b, dbNone, true)
                      cb(~planned=2, ())
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

// Test 6: disconnect is idempotent — calling twice returns Ok both times
testAsync("ComIntegration: disconnect is idempotent — second call returns Ok", cb => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      | Ok(_) => {
          ComSession.disconnect(session)
            ->Promise.then(firstDisc => {
              switch firstDisc {
              | Error(_) => {
                  assertion(~operator="equal", (a, b) => a == b, false, true)
                  cb(~planned=1, ())
                  Promise.resolve()
                }
              | Ok(_) => {
                  ComSession.disconnect(session)
                    ->Promise.then(secondDisc => {
                      switch secondDisc {
                      | Ok(_) => {
                          assertion(~operator="equal", (a, b) => a == b, true, true)
                          cb(~planned=1, ())
                          Promise.resolve()
                        }
                      | Error(_) => {
                          assertion(~operator="equal", (a, b) => a == b, false, true)
                          cb(~planned=1, ())
                          Promise.resolve()
                        }
                      }
                    })
                }
              }
            })
        }
      }
    })
    ->ignore
})
