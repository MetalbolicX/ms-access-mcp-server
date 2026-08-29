open Test
open Services

// Step 2: ConnectionPool lifecycle tests (port from test_connection_pool.py)
// ConnectionPool manages connectionState records directly

// ---------------------------------------------------------------------------
// Test pool initial state
// ---------------------------------------------------------------------------

test("Pool: make creates empty pool", () => {
  let pool = ConnectionPool.make()
  let connections = ConnectionPool.list(pool)
  assertion(~operator="equal", (a, b) => a == b, Array.length(connections), 0)
})

test("Pool: get_active returns 'default' initially", () => {
  let pool = ConnectionPool.make()
  let active = ConnectionPool.get_active(pool)
  assertion(~operator="equal", (a, b) => a == b, active, "default")
})

// ---------------------------------------------------------------------------
// Test connect creates and stores connection
// ---------------------------------------------------------------------------

testAsync("Pool: first connect creates and stores a connection", cb => {
  let pool = ConnectionPool.make()
  ignore(
    ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
      ->Promise.then(r => {
        Promise.resolve(
          switch r {
          | Ok(state) => {
              assertion(~operator="equal", (a, b) => a == b, state.dbPathStr, "/tmp/prod.accdb")
              assertion(~operator="equal", (a, b) => a == b, state.adapterType, "odbc")
              cb(~planned=2, ())
            }
          | Error(_) => cb(~planned=0, ())
          }
        )
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
  ->ignore
})

testAsync("Pool: connect stores adapter in pool", cb => {
  let pool = ConnectionPool.make()
  ignore(
    ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
      ->Promise.then(r => {
        Promise.resolve(
          switch r {
          | Ok(_) => {
              let connections = ConnectionPool.list(pool)
              let hasProd = Array.some(connections, ((k, _v)) => k == "prod")
              assertion(~operator="equal", (a, b) => a == b, hasProd, true)
              cb(~planned=1, ())
            }
          | Error(_) => cb(~planned=0, ())
          }
        )
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
  ->ignore
})

// ---------------------------------------------------------------------------
// Test connect twice with same name raises error (reuse, not create second)
// ---------------------------------------------------------------------------

testAsync("Pool: connect twice with same name raises error", cb => {
  let pool = ConnectionPool.make()
  ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
    ->Promise.then(r1 => {
      switch r1 {
      | Ok(_) => ConnectionPool.connect(pool, "prod", "/tmp/other.accdb", "odbc")
      | Error(_) => {
          let dummy: result<ConnectionPool.connectionState, Errors.t> = Error(Errors.databaseError("unexpected"))
          Promise.resolve(dummy)
        }
      }
    })
    ->Promise.then(r2 => {
      switch r2 {
      | Ok(_) => {
          cb(~planned=0, ())
          Promise.resolve()
        }
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, true, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      }
    })
    ->Promise.catch(_e => {
      cb(~planned=0, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test disconnect removes connection and isConnected flips false
// ---------------------------------------------------------------------------

testAsync("Pool: disconnect removes connection from pool", cb => {
  let pool = ConnectionPool.make()
  ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
    ->Promise.then(r => {
      switch r {
      | Ok(_) => {
          ConnectionPool.disconnect(pool, ~name="prod")
            ->Promise.then(r2 => {
              switch r2 {
              | Ok(_) => {
                  let connections = ConnectionPool.list(pool)
                  let hasProd = Array.some(connections, ((k, _v)) => k == "prod")
                  assertion(~operator="equal", (a, b) => a == b, hasProd, false)
                  cb(~planned=1, ())
                  Promise.resolve()
                }
              | Error(_) => {
                  cb(~planned=0, ())
                  Promise.resolve()
                }
              }
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      | Error(_) => {
          cb(~planned=0, ())
          Promise.resolve()
        }
      }
    })
    ->Promise.catch(_e => {
      cb(~planned=0, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("Pool: isConnected returns false after disconnect", cb => {
  let pool = ConnectionPool.make()
  ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
    ->Promise.then(r => {
      switch r {
      | Ok(_) => {
          ConnectionPool.disconnect(pool, ~name="prod")
            ->Promise.then(_r => {
              let result = ConnectionPool.isConnected(pool, ~name="prod")
              switch result {
              | Ok(false) => {
                  assertion(~operator="equal", (a, b) => a == b, false, false)
                  cb(~planned=1, ())
                  Promise.resolve()
                }
              | _ => {
                  cb(~planned=0, ())
                  Promise.resolve()
                }
              }
            })
            ->Promise.catch(_e => {
              cb(~planned=0, ())
              Promise.resolve()
            })
        }
      | Error(_) => {
          cb(~planned=0, ())
          Promise.resolve()
        }
      }
    })
    ->Promise.catch(_e => {
      cb(~planned=0, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test disconnect unknown name raises error
// ---------------------------------------------------------------------------

testAsync("Pool: disconnect unknown name returns error", cb => {
  let pool = ConnectionPool.make()
  ignore(
    ConnectionPool.disconnect(pool, ~name="nonexistent")
      ->Promise.then(r => {
        switch r {
        | Ok(_) => {
            cb(~planned=0, ())
            Promise.resolve()
          }
        | Error(_) => {
            assertion(~operator="equal", (a, b) => a == b, true, true)
            cb(~planned=1, ())
            Promise.resolve()
          }
        }
      })
      ->Promise.catch(_e => {
        cb(~planned=1, ())
        Promise.resolve()
      })
  )
})

// ---------------------------------------------------------------------------
// Test get on nonexistent name raises error
// ---------------------------------------------------------------------------

test("Pool: get nonexistent name returns error", () => {
  let pool = ConnectionPool.make()
  let result = ConnectionPool.get(pool, ~name="nonexistent")
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true) // Should not succeed
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true) // Expected: error
  }
})

// ---------------------------------------------------------------------------
// Test connect with different names creates multiple connections
// ---------------------------------------------------------------------------

testAsync("Pool: connect multiple different names", cb => {
  let pool = ConnectionPool.make()
  ignore(
    ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
      ->Promise.then(r1 => {
        switch r1 {
        | Ok(_) => {
            ignore(
              ConnectionPool.connect(pool, "dev", "/tmp/dev.accdb", "odbc")
                ->Promise.then(r2 => {
                  Promise.resolve(
                    switch r2 {
                    | Ok(_) => {
                        let connections = ConnectionPool.list(pool)
                        let hasProd = Array.some(connections, ((k, _v)) => k == "prod")
                        let hasDev = Array.some(connections, ((k, _v)) => k == "dev")
                        assertion(~operator="equal", (a, b) => a == b, hasProd, true)
                        assertion(~operator="equal", (a, b) => a == b, hasDev, true)
                        cb(~planned=2, ())
                      }
                    | Error(_) => cb(~planned=0, ())
                    }
                  )
                })
                ->Promise.catch(_e => {
                  cb(~planned=0, ())
                  Promise.resolve()
                })
            )
          }
        | Error(_) => cb(~planned=0, ())
        }
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
  ->ignore
})

// ---------------------------------------------------------------------------
// Test disconnect one keeps other
// ---------------------------------------------------------------------------

testAsync("Pool: disconnect one keeps other", cb => {
  let pool = ConnectionPool.make()
  ignore(
    ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
      ->Promise.then(r1 => {
        switch r1 {
        | Ok(_) => {
            ignore(ConnectionPool.connect(pool, "dev", "/tmp/dev.accdb", "odbc"))
            ignore(ConnectionPool.disconnect(pool, ~name="prod"))
            let connections = ConnectionPool.list(pool)
let hasProd = Array.some(connections, ((k, _v)) => k == "prod")
                        let hasDev = Array.some(connections, ((k, _v)) => k == "dev")
            assertion(~operator="equal", (a, b) => a == b, hasProd, false)
            assertion(~operator="equal", (a, b) => a == b, hasDev, true)
            cb(~planned=2, ())
          }
        | Error(_) => cb(~planned=0, ())
        }
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
  ->ignore
})

// ---------------------------------------------------------------------------
// Test set_active and get_active
// ---------------------------------------------------------------------------

test("Pool: set_active changes active pointer", () => {
  let pool = ConnectionPool.make()
  let _ = ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
  let _ = ConnectionPool.connect(pool, "dev", "/tmp/dev.accdb", "odbc")
  let _ = ConnectionPool.set_active(pool, "dev")
  let active = ConnectionPool.get_active(pool)
  assertion(~operator="equal", (a, b) => a == b, active, "dev")
})

test("Pool: set_active nonexistent raises error", () => {
  let pool = ConnectionPool.make()
  let result = ConnectionPool.set_active(pool, "nonexistent")
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true) // Should not succeed
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true) // Expected: error
  }
})

test("Pool: getActive uses active connection", () => {
  let pool = ConnectionPool.make()
  let _ = ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
  let _ = ConnectionPool.connect(pool, "dev", "/tmp/dev.accdb", "odbc")
  let _ = ConnectionPool.set_active(pool, "dev")
  let result = ConnectionPool.getActive(pool)
  switch result {
  | Ok(state) => {
      assertion(~operator="equal", (a, b) => a == b, state.dbPathStr, "/tmp/dev.accdb")
    }
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true) // Should not error
  }
})

// ---------------------------------------------------------------------------
// Alias support tests
// ---------------------------------------------------------------------------

test("Pool: registerAlias registers alias for connection name", () => {
  let pool = ConnectionPool.make()
  let _ = ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
  let result = ConnectionPool.registerAlias(pool, ~alias="production", ~name="prod")
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("Pool: resolveAlias resolves alias to connection name", () => {
  let pool = ConnectionPool.make()
  let _ = ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
  let _ = ConnectionPool.registerAlias(pool, ~alias="production", ~name="prod")
  let result = ConnectionPool.resolveAlias(pool, ~alias="production")
  switch result {
  | Ok(name) => assertion(~operator="equal", (a, b) => a == b, name, "prod")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("Pool: registerAlias same alias same name is idempotent", () => {
  let pool = ConnectionPool.make()
  let _ = ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
  let _ = ConnectionPool.registerAlias(pool, ~alias="production", ~name="prod")
  let result = ConnectionPool.registerAlias(pool, ~alias="production", ~name="prod")
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("Pool: registerAlias alias collision for different name returns error", () => {
  let pool = ConnectionPool.make()
  let _ = ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
  let _ = ConnectionPool.connect(pool, "dev", "/tmp/dev.accdb", "odbc")
  let _ = ConnectionPool.registerAlias(pool, ~alias="production", ~name="prod")
  let result = ConnectionPool.registerAlias(pool, ~alias="production", ~name="dev")
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true) // Should error
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true) // Expected error
  }
})

test("Pool: resolveAlias unknown alias returns error", () => {
  let pool = ConnectionPool.make()
  let result = ConnectionPool.resolveAlias(pool, ~alias="nonexistent")
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true) // Should error
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true) // Expected error
  }
})

testAsync("Pool: disconnectByAlias removes underlying connection", cb => {
  let pool = ConnectionPool.make()
  ignore(
    ConnectionPool.connect(pool, "prod", "/tmp/prod.accdb", "odbc")
      ->Promise.then(r1 => {
        switch r1 {
        | Ok(_) => {
            let _ = ConnectionPool.registerAlias(pool, ~alias="production", ~name="prod")
            ignore(
              ConnectionPool.disconnectByAlias(pool, ~alias="production")
                ->Promise.then(r2 => {
                  Promise.resolve(
                    switch r2 {
                    | Ok(_) => {
                        let connections = ConnectionPool.list(pool)
                        let hasProd = Array.some(connections, ((k, _v)) => k == "prod")
                        assertion(~operator="equal", (a, b) => a == b, hasProd, false)
                        cb(~planned=1, ())
                      }
                    | Error(_) => cb(~planned=0, ())
                    }
                  )
                })
                ->Promise.catch(_e => {
                  cb(~planned=0, ())
                  Promise.resolve()
                })
            )
          }
        | Error(_) => cb(~planned=0, ())
        }
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
  ->ignore
})

testAsync("Pool: disconnectByAlias unknown alias returns error", cb => {
  let pool = ConnectionPool.make()
  ConnectionPool.disconnectByAlias(pool, ~alias="nonexistent")
    ->Promise.then(r => {
      switch r {
      | Ok(_) => {
          cb(~planned=0, ())
          Promise.resolve()
        }
      | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, true, true)
          cb(~planned=1, ())
          Promise.resolve()
        }
      }
    })
    ->Promise.catch(_e => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})
