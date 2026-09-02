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
  // DAO COM errors can land as plain JS objects/primitives without a .message
  // string, or wrapped by ReScript's {RE_EXN_ID, _1} envelope. Walk the most
  // common shapes and stringify whatever we find. Always return a non-empty
  // string so callers can surface a meaningful error to the test logs.
  // ReScript's %raw wraps the JS expression as `EXPR(e)` so the JS must
  // be a function literal `(e) => result`, NOT an IIFE — otherwise the
  // wrapper invokes the IIFE result (a string) with `(e)` and crashes.
  let raw: string = %raw(
    "(e) => { var inner = (e && typeof e === 'object' && e._1 && typeof e._1 === 'object') ? e._1 : e; var parts = []; var push = function (k, v) { if (v !== undefined && v !== null && v !== '') { parts.push(k + '=' + (typeof v === 'string' ? v : String(v))); } }; if (inner && typeof inner === 'object') { push('message', inner.message); push('description', inner.description); push('number', inner.number); push('code', inner.code); push('hresult', inner.hresult); push('source', inner.source); } if (parts.length === 0) { if (inner && typeof inner === 'object') { parts.push('toString=' + String(inner)); } else { parts.push('value=' + String(inner)); } } return parts.join(' | '); }"
  )(e)
  if Js.String.length(raw) > 0 {
    raw
  } else {
    "Unknown error"
  }
}

// ---------------------------------------------------------------------------
// _unwrapJsonT — handle FFI boundary encoding from JS parity runners
// JS sends {TAG:"String",_0:"val"} etc. which ReScript receives as-is
// (not as JSON.t variants); extract the inner value before switch.
// ---------------------------------------------------------------------------

type jsonVariant =
  | JsonNull
  | JsonBool(bool)
  | JsonNumber(float)
  | JsonString(string)
  | JsonArray(array<JSON.t>)
  | JsonObject(dict<JSON.t>)
  | JsonUnknown(JSON.t)

let _classify: JSON.t => jsonVariant = (j: JSON.t): jsonVariant => {
  switch j {
  | JSON.Null => JsonNull
  | JSON.Boolean(b) => JsonBool(b)
  | JSON.Number(n) => JsonNumber(n)
  | JSON.String(s) => JsonString(s)
  | JSON.Array(a) => JsonArray(a)
  | JSON.Object(o) => JsonObject(o)
  }
}

// _unwrapTag — detect and unwrap {TAG:"String",_0:"x"} FFI envelope from JS.
// ReScript receives these as JSON.Object at runtime; the TAG/_0 shape is
// preserved but pattern-matching on JSON.t variants fails because the object
// is structurally a plain JS object, not a tagged variant.
let _unwrapTag: JSON.t => JSON.t = (j: JSON.t): JSON.t => {
  switch j {
  | JSON.Object(o) => {
      switch (Js.Dict.get(o, "TAG"), Js.Dict.get(o, "_0")) {
      | (Some(JSON.String("Null")), _) => JSON.Null
      | (Some(JSON.String("Bool")), Some(JSON.Boolean(b))) => JSON.Boolean(b)
      | (Some(JSON.String("Number")), Some(JSON.Number(n))) => JSON.Number(n)
      | (Some(JSON.String("String")), Some(JSON.String(s))) => JSON.String(s)
      | (Some(JSON.String("Array")), Some(JSON.Array(a))) => JSON.Array(a)
      | (Some(JSON.String("Object")), Some(JSON.Object(o2))) => JSON.Object(o2)
      | _ => j  // not a tag envelope; return as-is
      }
    }
  | _ => j
  }
}

// ---------------------------------------------------------------------------
// _closeRecordset — explicitly close a DAO Recordset before release.
// DAO recordsets hold internal pointers to their parent Database object.
// Without explicit Close(), winax's async release defers the DispObject
// destructor until the event loop spins again — but that can be AFTER
// V8 isolate teardown, causing RemoveEnvironmentCleanupHook crash.
// Calling Close() forces synchronous DAO cleanup so the DispObject
// destructor runs before isolate teardown.
// ---------------------------------------------------------------------------

let _closeRecordset: ComInterfaces.comObject => Promise.t<unit> = (
  rs: ComInterfaces.comObject,
) => {
  Bindings.Winax.WINAX_BINDING.invoke(rs, "Close", [])
    ->Promise.then(_ => {
      Bindings.Winax.WINAX_BINDING.release(rs)->ignore
      Promise.resolve()
    })
    ->Promise.catch(_ => {
      Bindings.Winax.WINAX_BINDING.release(rs)->ignore
      Promise.resolve()
    })
}

// ---------------------------------------------------------------------------
// _formatValue — format a value for inline use in DAO SQL strings
// Matches Python wincom.py _format_dao_value
// Also handles FFI boundary {TAG,_0} envelopes from JS parity runners.
// ---------------------------------------------------------------------------

let _formatValue: JSON.t => string = (j: JSON.t): string => {
  let unwrapped = _unwrapTag(j)
  switch unwrapped {
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

  // ---------------------------------------------------------------------------
  // _executeQueryImpl — internal executeQuery via DAO.OpenRecordset
  // Mirrors Python wincom.py:256-307
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
      switch self.session {
      | None => Promise.resolve(Ok({
          success: false,
          rows: [],
          count: 0,
          columns: [],
          error: Some("Not connected"),
        }))
      | Some(session) =>
        switch ComSession.getCurrentDb(session) {
        | None => Promise.resolve(Ok({
            success: false,
            rows: [],
            count: 0,
            columns: [],
            error: Some("Database not open"),
          }))
        | Some(currentDb) => {
            let sqlArg = ComInterfaces.VStr(sql)
            Bindings.Winax.WINAX_BINDING.invokeAsObject(currentDb, "OpenRecordset", [sqlArg])
              ->Promise.then(rsResult => {
                switch rsResult {
                | Error(e) => Promise.resolve(Error(e))
                | Ok(rs) => {
                    Bindings.Winax.WINAX_BINDING.get(rs, "EOF")
                      ->Promise.then(eofResult => {
                        switch eofResult {
                        | Ok(JSON.Boolean(true)) => {
                            _closeRecordset(rs)->ignore
                            Promise.resolve(Ok({
                              success: true,
                              rows: [],
                              count: 0,
                              columns: [],
                              error: None,
                            }))
                          }
                        | Ok(_) => {
                            Bindings.Winax.WINAX_BINDING.get(rs, "Fields")
                              ->Promise.then(fieldsResult => {
                                switch fieldsResult {
                                | Error(e) => {
                                    _closeRecordset(rs)->ignore
                                    Promise.resolve(Error(e))
                                  }
                                | Ok(fields) => {
                                    // Wrap fields COM object in envelope for getCount/getItem
                                    let fieldsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(fields)
                                    Bindings.Winax.WINAX_BINDING.getCount(fieldsHandle)
                                      ->Promise.then(countResult => {
                                        switch countResult {
                                        | Error(e) => {
                                            _closeRecordset(rs)->ignore
                                            Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                            Promise.resolve(Error(e))
                                          }
                                        | Ok(fieldCount) => {
                                            // Build column names array iteratively using for loop + promise chain
                                            let columnNames: array<string> = []
                                            let colIdx = ref(0)
                                            let rec colCollect: unit => Promise.t<result<array<string>, Errors.t>> = (
                                              (),
                                            ) => {
                                              if colIdx.contents >= fieldCount {
                                                Promise.resolve(Ok(columnNames))
                                              } else {
                                                let idxVar = ComInterfaces.VInt(colIdx.contents)
                                                Bindings.Winax.WINAX_BINDING.getItem(fieldsHandle, idxVar)
                                                  ->Promise.then(itemResult => {
                                                    switch itemResult {
                                                    | Error(e) => Promise.resolve(Error(e))
                                                    | Ok(fieldHandle) => {
                                                        Bindings.Winax.WINAX_BINDING.get(fieldHandle, "Name")
                                                          ->Promise.then(nameResult => {
                                                            Bindings.Winax.WINAX_BINDING.release(fieldHandle)->ignore
                                                            switch nameResult {
                                                            | Ok(JSON.String(colName)) => {
                                                                columnNames->Array.push(colName)->ignore
                                                                colIdx.contents = colIdx.contents + 1
                                                                colCollect()
                                                              }
                                                            | Ok(_) => {
                                                                colIdx.contents = colIdx.contents + 1
                                                                colCollect()
                                                              }
                                                            | Error(e) => Promise.resolve(Error(e))
                                                            }
                                                          })
                                                      }
                                                    }
                                                  })
                                              }
                                            }
                                            colCollect()
                                              ->Promise.then(colsResult => {
                                                Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                switch colsResult {
                                                | Error(e) => {
                                                    _closeRecordset(rs)->ignore
                                                    Promise.resolve(Error(e))
                                                  }
                                                | Ok(columns) => {
                                                    // Iterate all rows and collect results
                                                    let allRows: array<dict<JSON.t>> = []
                                                    let rec rowCollect: unit => Promise.t<result<array<dict<JSON.t>>, Errors.t>> = (
                                                      (),
                                                    ) => {
                                                      Bindings.Winax.WINAX_BINDING.get(rs, "EOF")
                                                        ->Promise.then(eofChk => {
                                                          switch eofChk {
                                                          | Ok(JSON.Boolean(true)) => Promise.resolve(Ok(allRows))
                                                          | Ok(_) => {
                                                              Bindings.Winax.WINAX_BINDING.get(rs, "Fields")
                                                                ->Promise.then(rfResult => {
                                                                  switch rfResult {
                                                                  | Error(e) => Promise.resolve(Error(e))
                                                                  | Ok(rowFieldsRaw) => {
                                                                      let rowFieldsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(rowFieldsRaw)
                                                                      Bindings.Winax.WINAX_BINDING.getCount(rowFieldsHandle)
                                                                        ->Promise.then(rfcResult => {
                                                                           switch rfcResult {
                                                                            | Error(_e) => {
                                                                                // Release rowFieldsHandle here — cCollect() is never called
                                                                                // when getCount fails, so there's no cCollect() error path
                                                                                // that could double-free. Do NOT release rs here — the
                                                                                // outer .catch() at line 413 handles rs release.
                                                                                Bindings.Winax.WINAX_BINDING.release(rowFieldsHandle)->ignore
                                                                                Promise.resolve(Error(_e))
                                                                              }
                                                                          | Ok(rfc) => {
                                                                            let rowDict: dict<JSON.t> = Dict.make()
                                                                            let cIdx = ref(0)
                                                                            let rec cCollect: unit => Promise.t<result<dict<JSON.t>, Errors.t>> = (
                                                                                (),
                                                                              ) => {
                                                                                if cIdx.contents >= rfc {
                                                                                  Promise.resolve(Ok(rowDict))
                                                                                } else {
                                                                                  let cVar = ComInterfaces.VInt(cIdx.contents)
                                                                                  Bindings.Winax.WINAX_BINDING.getItem(rowFieldsHandle, cVar)
                                                                                    ->Promise.then(ciResult => {
                                                                                      switch ciResult {
                                                                                      | Error(e) => Promise.resolve(Error(e))
                                                                                      | Ok(cItem) => {
                                                                                          Bindings.Winax.WINAX_BINDING.get(cItem, "Value")
                                                                                            ->Promise.then(valResult => {
                                                                                              Bindings.Winax.WINAX_BINDING.release(cItem)->ignore
                                                                                              switch valResult {
                                                                                              | Ok(val) => {
                                                                                                  let cName = switch Array.get(columns, cIdx.contents) {
                                                                                                  | Some(n) => n
                                                                                                  | None => "col" ++ Int.toString(cIdx.contents)
                                                                                                  }
                                                                                                  Dict.set(rowDict, cName, val)
                                                                                                  cIdx.contents = cIdx.contents + 1
                                                                                                  cCollect()
                                                                                                }
                                                                                              | Error(e) => {
                                                                                                  Promise.resolve(Error(e))
                                                                                                }
                                                                                              }
                                                                                            })
                                                                                        }
                                                                                      }
                                                                                    })
                                                                                }
                                                                              }
                                                                                  cCollect()
                                                                                  ->Promise.then(rowResult => {
                                                                                    switch rowResult {
                                                                                   | Error(e) => {
                                                                                         Bindings.Winax.WINAX_BINDING.release(rowFieldsHandle)->ignore
                                                                                         _closeRecordset(rs)->ignore
                                                                                         Promise.resolve(Error(e))
                                                                                       }
                                                                                   | Ok(_) => {
                                                                                       allRows->Array.push(rowDict)->ignore
                                                                                       Bindings.Winax.WINAX_BINDING.release(rowFieldsHandle)->ignore
                                                                                       Bindings.Winax.WINAX_BINDING.invoke(rs, "MoveNext", [])
                                                                                         ->Promise.then(_ => {
                                                                                           rowCollect()
                                                                                         })
                                                                                     }
                                                                                   }
                                                                                 })
                                                                            }
                                                                          }
                                                                        })
                                                                    }
                                                                  | Error(e) => Promise.resolve(Error(e))
                                                                  }
                                                                })
                                                            }
                                                          | Error(e) => Promise.resolve(Error(e))
                                                          }
                                                        })
                                                    }
                                                    rowCollect()
                                                      ->Promise.then(rowsResult => {
                                                        _closeRecordset(rs)->ignore
                                                        switch rowsResult {
                                                        | Error(e) => Promise.resolve(Error(e))
                                                        | Ok(rows) => {
                                                            Promise.resolve(Ok({
                                                              success: true,
                                                              rows: rows,
                                                              count: Array.length(rows),
                                                              columns: columns,
                                                              error: None,
                                                            }))
                                                          }
                                                        }
                                                      })
                                                  }
                                                }
                                              })
                                          }
                                        }
                                      })
                                  }
                                | Error(e) => {
                                    _closeRecordset(rs)->ignore
                                    Promise.resolve(Error(e))
                                  }
                                }
                              })
                          }
                        | Error(e) => {
                            _closeRecordset(rs)->ignore
                            Promise.resolve(Error(e))
                          }
                        }
                      })
                  }
                }
              })
              ->Promise.catch(exn => {
                Promise.resolve(Error(Errors.databaseError(_exnMessage(exn))))
              })
          }
        }
      }
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

  // _buildMutateSql — build SQL for insert/update/delete operations
  // WHERE clause: Facade wraps dict WHERE as JSON.Object({...}) → iterate Js.Dict.entries and AND-join.
  // Facade wraps raw string WHERE as JSON.String("...") → append raw string after "WHERE ".
  let _buildMutateSql = (
    operation: string,
    table: string,
    data: dict<JSON.t>,
    whereOpt: option<JSON.t>,
  ): string => {
    switch operation {
    | "insert" => {
        // INSERT INTO [table] (col1, col2, ...) VALUES ('val1', 'val2', ...)
        let entries = Js.Dict.entries(data)
        let keys = entries->Array.map(((k, _)) => k)
        let vals = entries->Array.map(((_, v)) => _formatValue(v))
        let colStr = Array.join(keys, ", ")
        let valStr = Array.join(vals, ", ")
        "INSERT INTO [" ++ table ++ "] (" ++ colStr ++ ") VALUES (" ++ valStr ++ ")"
      }
    | "update" => {
        let pairs = Js.Dict.entries(data)->Array.map(((k, v)) => {
          k ++ " = " ++ _formatValue(v)
        })
        let pairStr = Array.join(pairs, ", ")
        let whereStr = switch whereOpt {
        | Some(JSON.Object(o)) => {
            // dict → AND-joined equality conditions
            let clauses = Js.Dict.entries(o)->Array.map(((k, v)) => {
              k ++ " = " ++ _formatValue(v)
            })
            " WHERE " ++ Array.join(clauses, " AND ")
          }
        | Some(JSON.String(s)) => " WHERE " ++ s  // raw SQL fragment
        | Some(_) => ""
        | None => ""
        }
        "UPDATE [" ++ table ++ "] SET " ++ pairStr ++ whereStr
      }
    | "delete" => {
        let whereStr = switch whereOpt {
        | Some(JSON.Object(o)) => {
            let clauses = Js.Dict.entries(o)->Array.map(((k, v)) => {
              k ++ " = " ++ _formatValue(v)
            })
            " WHERE " ++ Array.join(clauses, " AND ")
          }
        | Some(JSON.String(s)) => " WHERE " ++ s
        | Some(_) => ""
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
      switch self.session {
      | None => Promise.resolve(Ok({success: false, affected: 0, error: Some("No session")}))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok({success: false, affected: 0, error: Some("No DB handle")}))
          | Some(db) => {
              let sql = _buildMutateSql(operation, table, data, whereOpt)
              // DAO_DB_FAIL_ON_ERROR = 128
              Bindings.Winax.WINAX_BINDING.invoke(db, "Execute", [ComInterfaces.VStr(sql), ComInterfaces.VInt(128)])
              ->Promise.then(execResult => {
                switch execResult {
                | Error(e) => {
                    // DAO-level error → return in Ok to match Python oracle (dao.py:663-668)
                    let msg = Errors._message(e)
                    Promise.resolve(Ok({success: false, affected: 0, error: Some(msg)}))
                  }
                | Ok(_) => {
                    // DAO.Execute is a void method. After it returns, the
                    // Database object's RecordsAffected *property* holds the
                    // count. Use get (DISPATCH_PROPERTYGET) — invoke
                    // (DISPATCH_METHOD) returns 0 for DAO's read-only
                    // RecordsAffected because no method dispid exists.
                    Bindings.Winax.WINAX_BINDING.get(db, "RecordsAffected")
                    ->Promise.then(ra => {
                      switch ra {
                      | Ok(JSON.Number(n)) => Promise.resolve(Ok({success: true, affected: int_of_float(n), error: None}))
                      | Ok(v) => {
                          // Fallback: try to extract a number from whatever we got
                          let affected = switch v {
                          | JSON.Number(n) => int_of_float(n)
                          | _ => 0
                          }
                          Promise.resolve(Ok({success: true, affected: affected, error: None}))
                        }
                      | Error(_) => Promise.resolve(Ok({success: true, affected: 0, error: None}))
                      }
                    })
                  }
                }
              })
            }
          }
        }
      }
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
    if !self.isConnected {
      Promise.resolve(Ok(0))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok(0))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok(0))
          | Some(db) => {
              Bindings.Winax.WINAX_BINDING.invoke(db, "Execute", [ComInterfaces.VStr(sql), ComInterfaces.VInt(128)])
              ->Promise.then(execResult => {
                switch execResult {
                | Error(_e) => Promise.resolve(Ok(0))
                | Ok(_) => {
                    // Use get for RecordsAffected (DISPATCH_PROPERTYGET) —
                    // DAO's read-only property has no method dispid, so
                    // invoke (DISPATCH_METHOD) would return 0.
                    Bindings.Winax.WINAX_BINDING.get(db, "RecordsAffected")
                    ->Promise.then(ra => {
                      switch ra {
                      | Ok(JSON.Number(n)) => Promise.resolve(Ok(int_of_float(n)))
                      | Ok(v) => {
                          let affected = switch v {
                          | JSON.Number(n) => int_of_float(n)
                          | _ => 0
                          }
                          Promise.resolve(Ok(affected))
                        }
                      | Error(_) => Promise.resolve(Ok(0))
                      }
                    })
                  }
                }
              })
            }
          }
        }
      }
    }
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
      switch self.session {
      | None => Promise.resolve(Ok([]))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok([]))
          | Some(db) => {
              Bindings.Winax.WINAX_BINDING.get(db, "TableDefs")
              ->Promise.then(tableDefsResult => {
                switch tableDefsResult {
                | Error(e) => Promise.resolve(Error(e))
                | Ok(tableDefs) => {
                    // Wrap TableDefs COM handle for getCount/getItem
                    let tableDefsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(tableDefs)
                    Bindings.Winax.WINAX_BINDING.getCount(tableDefsHandle)
                    ->Promise.then(countResult => {
                      switch countResult {
                      | Error(e) => {
                          Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                          Promise.resolve(Error(e))
                        }
                      | Ok(count) => {
                          let results: array<Interfaces.tableInfo> = []
                          let tableIdx = ref(0)
                          let rec collectLoop: unit => Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> = () => {
                            if tableIdx.contents >= count {
                              Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                              Promise.resolve(Ok(results))
                            } else {
                              let idxVar = ComInterfaces.VInt(tableIdx.contents)
                              Bindings.Winax.WINAX_BINDING.getItem(tableDefsHandle, idxVar)
                              ->Promise.then(itemResult => {
                                switch itemResult {
                                | Error(e) => {
                                    Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                    Promise.resolve(Error(e))
                                  }
                                | Ok(td) => {
                                    Bindings.Winax.WINAX_BINDING.get(td, "Name")
                                    ->Promise.then(nameResult => {
                                      switch nameResult {
                                      | Error(e) => {
                                          Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                          Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                          Promise.resolve(Error(e))
                                        }
                                      | Ok(JSON.String(name)) => {
                                          Bindings.Winax.WINAX_BINDING.get(td, "Type")
                                          ->Promise.then(typeResult => {
                                            Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                            switch typeResult {
                                            | Error(e) => {
                                                Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                                Promise.resolve(Error(e))
                                              }
                                            | Ok(typeVal) => {
                                                // DAO type: 1=TABLE, 5=SYSTEM, 8=QUERY
                                                let isSystem = name->String.startsWith("MSys") || name->String.startsWith("~") || name->String.startsWith("~$")
                                                let isQuery = switch typeVal {
                                                | JSON.Number(n) => n->Float.toInt === 8
                                                | _ => false
                                                }
                                                if isQuery {
                                                  tableIdx.contents = tableIdx.contents + 1
                                                  collectLoop()
                                                } else if systemOnly {
                                                  if isSystem {
                                                    let fi: Interfaces.fieldInfo = {
                                                      name: name,
                                                      type_: "SYSTEM",
                                                      size: 0,
                                                      required: false,
                                                      allowZeroLength: false,
                                                      defaultValue: None,
                                                      isAutoincrement: false,
                                                    }
                                                    let ti: Interfaces.tableInfo = {
                                                      name: name,
                                                      fields: [fi],
                                                      recordCount: 0,
                                                      primaryKey: None,
                                                    }
                                                    results->Array.push(ti)
                                                  }
                                                  tableIdx.contents = tableIdx.contents + 1
                                                  collectLoop()
                                                } else {
                                                  if !isSystem {
                                                    let fi: Interfaces.fieldInfo = {
                                                      name: name,
                                                      type_: "TABLE",
                                                      size: 0,
                                                      required: false,
                                                      allowZeroLength: false,
                                                      defaultValue: None,
                                                      isAutoincrement: false,
                                                    }
                                                    let ti: Interfaces.tableInfo = {
                                                      name: name,
                                                      fields: [fi],
                                                      recordCount: 0,
                                                      primaryKey: None,
                                                    }
                                                    results->Array.push(ti)
                                                  }
                                                  tableIdx.contents = tableIdx.contents + 1
                                                  collectLoop()
                                                }
                                              }
                                            }
                                          })
                                        }
                                      }
                                    })
                                  }
                                }
                              })
                            }
                          }
                          collectLoop()
                        }
                      }
                    })
                  }
                }
              })
            }
          }
        }
      }
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
      switch self.session {
      | None => Promise.resolve(Ok([]))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok([]))
          | Some(db) => {
              Bindings.Winax.WINAX_BINDING.get(db, "Relations")
              ->Promise.then(relsResult => {
                switch relsResult {
                | Error(_) => Promise.resolve(Ok([]))
                | Ok(rels) => {
                    let relsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(rels)
                    Bindings.Winax.WINAX_BINDING.getCount(relsHandle)
                    ->Promise.then(countResult => {
                      switch countResult {
                      | Error(_) => {
                          Bindings.Winax.WINAX_BINDING.release(relsHandle)->ignore
                          Promise.resolve(Ok([]))
                        }
                      | Ok(count) => {
                          let results: array<Interfaces.relationshipInfo> = []
                          let relIdx = ref(0)
                          let rec iterate: unit => Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>> = () => {
                            if relIdx.contents >= count {
                              Promise.resolve(Ok(results))
                            } else {
                              let idxVar = ComInterfaces.VInt(relIdx.contents)
                              Bindings.Winax.WINAX_BINDING.getItem(relsHandle, idxVar)
                              ->Promise.then(relResult => {
                                switch relResult {
                                | Error(_) => {
                                    relIdx.contents = relIdx.contents + 1
                                    iterate()
                                  }
                                | Ok(relHandle) => {
                                    // Read properties via raw accessors to bypass winax get/JSON.stringify.
                                    // relHandle is the envelope {__p__: realProxy}; access via __p__.
                                    let name: string = %raw("h => h && h.__p__ ? h.__p__.Name : ''")(relHandle)
                                    let tableName: string = %raw("h => h && h.__p__ ? h.__p__.Table : ''")(relHandle)
                                    let foreignTableName: string = %raw("h => h && h.__p__ ? h.__p__.ForeignTable : ''")(relHandle)
                                    let attrsStr: string = %raw("h => h && h.__p__ ? String(h.__p__.Attributes) : ''")(relHandle)
                                    let fcount: int = %raw("h => h && h.__p__ && h.__p__.Fields ? h.__p__.Fields.Count : 0")(relHandle)
                                    let colNames: array<string> = []
                                    let foreignColNames: array<string> = []
                                    let _ = for idx in 0 to fcount - 1 {
                                      let cn: string = %raw("(h, i) => h && h.__p__ && h.__p__.Fields ? h.__p__.Fields.Item(i).Name : ''")(relHandle, idx)
                                      let fcn: string = %raw("(h, i) => h && h.__p__ && h.__p__.Fields ? h.__p__.Fields.Item(i).ForeignName : ''")(relHandle, idx)
                                      colNames->Array.push(cn)->ignore
                                      foreignColNames->Array.push(fcn)->ignore
                                    }
                                    let _ = (colNames, foreignColNames)
                                    // Skip MSys and temporary relations
                                    if name->String.startsWith("MSys") || name->String.startsWith("~") || name == "" {
                                      Bindings.Winax.WINAX_BINDING.release(relHandle)->ignore
                                      relIdx.contents = relIdx.contents + 1
                                      iterate()
                                    } else {
                                      let relInfo: Interfaces.relationshipInfo = {
                                        name: name,
                                        table: tableName,
                                        foreignTable: foreignTableName,
                                        attributes: attrsStr,
                                        columns: colNames,
                                        foreignColumns: foreignColNames,
                                      }
                                      results->Array.push(relInfo)->ignore
                                      Bindings.Winax.WINAX_BINDING.release(relHandle)->ignore
                                      relIdx.contents = relIdx.contents + 1
                                      iterate()
                                    }
                                  }
                                }
                              })
                            }
                          }
                          iterate()
                          ->Promise.then(final => {
                            Bindings.Winax.WINAX_BINDING.release(relsHandle)->ignore
                            Promise.resolve(final)
                          })
                        }
                      }
                    })
                  }
                }
              })
            }
          }
        }
      }
    }
  }

  let getRelationships = (self: t): Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>> => {
    _getRelationshipsImpl(self)
  }

  let _getTableSchemaPlanImpl: t => Promise.t<result<(array<Interfaces.tableSchema>, Interfaces.unknownMetadata), Errors.t>> = (
    self: t,
  ) => {
    if !self.isConnected {
      Promise.resolve(Ok(([], {primaryKeys: false, foreignKeys: false, defaults: false, indexes: false, autoincrement: false})))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok(([], {primaryKeys: false, foreignKeys: false, defaults: false, indexes: false, autoincrement: false})))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok(([], {primaryKeys: false, foreignKeys: false, defaults: false, indexes: false, autoincrement: false})))
          | Some(db) => {
              Bindings.Winax.WINAX_BINDING.get(db, "TableDefs")
              ->Promise.then(tableDefsResult => {
                switch tableDefsResult {
                | Error(e) => Promise.resolve(Error(e))
                | Ok(tableDefs) => {
                    let tableDefsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(tableDefs)
                    Bindings.Winax.WINAX_BINDING.getCount(tableDefsHandle)
                    ->Promise.then(countResult => {
                      switch countResult {
                      | Error(e) => {
                          Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                          Promise.resolve(Error(e))
                        }
                      | Ok(count) => {
                          let results: array<Interfaces.tableSchema> = []
                          let tableIdx = ref(0)
                          let rec collectLoop: unit => Promise.t<result<array<Interfaces.tableSchema>, Errors.t>> = () => {
                            if tableIdx.contents >= count {
                              Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                              Promise.resolve(Ok(results))
                            } else {
                              let idxVar = ComInterfaces.VInt(tableIdx.contents)
                              Bindings.Winax.WINAX_BINDING.getItem(tableDefsHandle, idxVar)
                              ->Promise.then(itemResult => {
                                switch itemResult {
                                | Error(e) => {
                                    Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                    Promise.resolve(Error(e))
                                  }
                                | Ok(td) => {
                                    Bindings.Winax.WINAX_BINDING.get(td, "Name")
                                    ->Promise.then(nameResult => {
                                      switch nameResult {
                                      | Error(e) => {
                                          Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                          Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                          Promise.resolve(Error(e))
                                        }
                                      | Ok(JSON.String(name)) => {
                                          Bindings.Winax.WINAX_BINDING.get(td, "Type")
                                          ->Promise.then(typeResult => {
                                            Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                            switch typeResult {
                                            | Error(e) => {
                                                Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                                Promise.resolve(Error(e))
                                              }
                                            | Ok(typeVal) => {
                                                // DAO type: 1=TABLE, 5=SYSTEM, 8=QUERY
                                                let isSystem = name->String.startsWith("MSys") || name->String.startsWith("~") || name->String.startsWith("~$")
                                                let isQuery = switch typeVal {
                                                | JSON.Number(n) => n->Float.toInt === 8
                                                | _ => false
                                                }
                                                if isQuery || isSystem {
                                                  tableIdx.contents = tableIdx.contents + 1
                                                  collectLoop()
                                                } else {
                                                  // Get Fields collection for this table
                                                  Bindings.Winax.WINAX_BINDING.get(td, "Fields")
                                                  ->Promise.then(fieldsResult => {
                                                    switch fieldsResult {
                                                    | Error(e) => {
                                                        Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                                        Promise.resolve(Error(e))
                                                      }
                                                    | Ok(fields) => {
                                                        let fieldsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(fields)
                                                        Bindings.Winax.WINAX_BINDING.getCount(fieldsHandle)
                                                        ->Promise.then(fieldCountResult => {
                                                          switch fieldCountResult {
                                                          | Error(e) => {
                                                              Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                              Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                                              Promise.resolve(Error(e))
                                                            }
                                                          | Ok(fieldCount) => {
                                                              let columns: array<Interfaces.columnSchema> = []
                                                              let fieldIdx = ref(0)
                                                              let rec fieldCollect: unit => Promise.t<result<array<Interfaces.columnSchema>, Errors.t>> = () => {
                                                                if fieldIdx.contents >= fieldCount {
                                                                  Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                                  Promise.resolve(Ok(columns))
                                                                } else {
                                                                  let fVar = ComInterfaces.VInt(fieldIdx.contents)
                                                                  Bindings.Winax.WINAX_BINDING.getItem(fieldsHandle, fVar)
                                                                  ->Promise.then(fieldResult => {
                                                                    switch fieldResult {
                                                                    | Error(e) => {
                                                                        Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                                        Promise.resolve(Error(e))
                                                                      }
                                                                    | Ok(field) => {
                                                                        let colName: string = %raw("f => f && f.__p__ ? f.__p__.Name : ''")(field)
                                                                        let colType: string = %raw("f => f && f.__p__ ? String(f.__p__.Type) : ''")(field)
                                                                        let colSize: int = %raw("f => f && f.__p__ ? Number(f.__p__.Size) || 0 : 0")(field)
                                                                        let colAllowNull: bool = %raw("f => f && f.__p__ ? Boolean(f.__p__.AllowZeroLength) : true")(field)
                                                                        let colDefault: option<string> = %raw("f => f && f.__p__ && f.__p__.DefaultValue != null ? String(f.__p__.DefaultValue) : null")(field)
                                                                        let colAutoincrement: bool = %raw("f => f && f.__p__ ? Boolean(f.__p__.Attributes && (f.__p__.Attributes & 16)) : false")(field)
                                                                        Bindings.Winax.WINAX_BINDING.release(field)->ignore
                                                                        let colSchema: Interfaces.columnSchema = {
                                                                          name: colName,
                                                                          sourceType: colType,
                                                                          maxLength: if colSize > 0 { Some(colSize) } else { None },
                                                                          allowNull: colAllowNull,
                                                                          isAutoincrement: colAutoincrement,
                                                                          defaultValue: colDefault,
                                                                        }
                                                                        columns->Array.push(colSchema)->ignore
                                                                        fieldIdx.contents = fieldIdx.contents + 1
                                                                        fieldCollect()
                                                                      }
                                                                    }
                                                                  })
                                                                }
                                                              }
                                                              fieldCollect()
                                                              ->Promise.then(colsResult => {
                                                                switch colsResult {
                                                                | Error(e) => {
                                                                    Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                                                    Promise.resolve(Error(e))
                                                                  }
                                                                | Ok(cols) => {
                                                                    let tableSchema: Interfaces.tableSchema = {
                                                                      name: name,
                                                                      columns: cols,
                                                                      primaryKey: None,
                                                                      foreignKeys: [],
                                                                      indexes: [],
                                                                    }
                                                                    results->Array.push(tableSchema)->ignore
                                                                    tableIdx.contents = tableIdx.contents + 1
                                                                    collectLoop()
                                                                  }
                                                                }
                                                              })
                                                            }
                                                          }
                                                        })
                                                      }
                                                    | Error(e) => {
                                                        Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                                        Promise.resolve(Error(e))
                                                      }
                                                    }
                                                  })
                                                }
                                              }
                                            }
                                          })
                                        }
                                      | Ok(_) => {
                                          tableIdx.contents = tableIdx.contents + 1
                                          collectLoop()
                                        }
                                      }
                                    })
                                  }
                                }
                              })
                            }
                          }
                          collectLoop()
                          ->Promise.then(finalResult => {
                            switch finalResult {
                            | Error(e) => Promise.resolve(Error(e))
                            | Ok(schemas) => {
                                Promise.resolve(Ok((schemas, {primaryKeys: false, foreignKeys: false, defaults: false, indexes: false, autoincrement: false})))
                              }
                            }
                          })
                        }
                      }
                    })
                  }
                }
              })
            }
          }
        }
      }
    }
  }

  let getTableSchemaPlan = (self: t): Promise.t<result<(array<Interfaces.tableSchema>, Interfaces.unknownMetadata), Errors.t>> => {
    _getTableSchemaPlanImpl(self)
  }

  let generateSql = (self: t, _tableName: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    // dao.py:355 — generate_sql(output_path) delegates to SchemaSupport.
    // exportSchemaDdl writes ddl_tables.sql + ddl_relationships.sql to outputDir.
    // The tableName arg is not used (exportSchemaDdl exports all tables).
    if !self.isConnected {
      Promise.resolve(Ok({success: false, error: Some("Not connected")}))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok({success: false, error: Some("No session")}))
      | Some(session) => {
          let handles = ComSession.getHandles(session)
          // Use a temp dir inside the output dir (exportSchemaDdl appends /schema)
            let outputDir = Dict.get(NodeJs.Process.process.env, "TEMP")->Option.getOr("/tmp")
            // _getTablesImpl returns result<array<Interfaces.tableInfo>, Errors.t>;
            // exportSchemaDdl needs ComDbProps.tableInfo = {name, fields: {name,type_,required}}
            let getTables: unit => Promise.t<array<Adapters.ComDbProps.tableInfo>> = () =>
              _getTablesImpl(self, false)->Promise.then(tables =>
                switch tables {
                | Ok(a) => {
                    let converted = a->Array.map(t => (
                      {
                        name: t.name,
                        fields: t.fields->Array.map(f => (
                          {name: f.name, type_: f.type_, required: f.required}: Adapters.ComDbProps.tableFieldInfo
                        )),
                      }: Adapters.ComDbProps.tableInfo
                    ))
                    Promise.resolve(converted)
                  }
                | Error(_) => Promise.resolve([])
                }
              )
            // _getRelationshipsImpl returns result<array<Interfaces.relationshipInfo>, Errors.t>;
            // exportSchemaDdl needs ComDbProps.relationshipInfo = {name, table, foreignTable, attributes}
            let getRels: unit => Promise.t<array<Adapters.ComDbProps.relationshipInfo>> = () =>
              _getRelationshipsImpl(self)->Promise.then(rels =>
                switch rels {
                | Ok(a) => {
                    let converted = a->Array.map(r => (
                      {
                        name: r.name,
                        table: r.table,
                        foreignTable: r.foreignTable,
                        attributes: r.attributes,
                      }: Adapters.ComDbProps.relationshipInfo
                    ))
                    Promise.resolve(converted)
                  }
                | Error(_) => Promise.resolve([])
                }
              )
            Adapters.ComDbProps.exportSchemaDdl(
              handles,
              ~outputDir,
              ~getTablesFn=getTables,
              ~getRelationshipsFn=getRels
            )->Promise.then(schemaResult => {
              // Collect table names from getTables to populate the tables field
              getTables()->Promise.then(tableInfos => {
                let tableNames: array<string> = tableInfos->Array.map(info => info.name)
                // 034-F-002: read exported files back and return inline DDL to match
                // Python oracle's generate_sql envelope (writes file + returns content).
                // Python schema_inspector.generate_sql returns {success, path, statements, tables}.
                // ReScript exportSchemaDdl wrote ddl_tables.sql + ddl_relationships.sql.
                let inlineDdl: string = if schemaResult.success {
                  let tablesContent = Adapters.ComDbProps._readFileText(schemaResult.ddlTables)
                  let relsContent = Adapters.ComDbProps._readFileText(schemaResult.ddlRelationships)
                  tablesContent ++ "\n" ++ relsContent
                } else {
                  ""
                }
                let result: Interfaces.ddlResult = {
                  success: schemaResult.success,
                  error: schemaResult.error,
                  path: outputDir ++ "/schema",  // directory where files were written
                  statements: schemaResult.tablesExported + schemaResult.relationshipsExported,
                  tables: tableNames,
                  ddl: inlineDdl,
                }
                Promise.resolve(Ok(result))
              })
            })
        }
      }
    }
  }

  let _getDbStatsImpl: t => Promise.t<result<dict<JSON.t>, Errors.t>> = (self: t) => {
    let stats = Dict.make()
    Dict.set(stats, "connected", JSON.Boolean(self.isConnected))
    switch self.dbPath {
    | Some(path) => {
        Dict.set(stats, "file", JSON.String(path))
      }
    | None => ()
    }
    Promise.resolve(Ok(stats))
  }

  let getDatabaseStatistics = (self: t): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    _getDbStatsImpl(self)
  }

  let _getQueriesImpl: t => Promise.t<result<array<Interfaces.queryInfo>, Errors.t>> = (self: t) => {
    // DAO QueryDefs collection — deferred full implementation
    // Returns empty array until nested promise iteration is resolved
    Promise.resolve(Ok([]))
  }

  let getQueries = (self: t): Promise.t<result<array<Interfaces.queryInfo>, Errors.t>> => {
    _getQueriesImpl(self)
  }

  let createQuery = (self: t, name: string, sql: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    // dao.py:365-379 — Python DAO oracle uses db.CreateQueryDef(name, sql).
    // Use db.CreateQueryDef via winax invoke (matches python oracle). DAO Access
    // workspace auto-appends to QueryDefs when Name is non-empty.
    if !self.isConnected {
      Promise.resolve(Ok({success: false, error: Some("Not connected")}))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok({success: false, error: Some("No session")}))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok({success: false, error: Some("No DB handle")}))
          | Some(db) => {
              // Use invokeAsObject to handle CreateQueryDef's COM-return value safely.
              Bindings.Winax.WINAX_BINDING.invokeAsObject(db, "CreateQueryDef", [ComInterfaces.VStr(name), ComInterfaces.VStr(sql)])
              ->Promise.then(createResult => {
                switch createResult {
                | Error(e) => {
                    Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                  }
                | Ok(qdef) => {
                    // Release the new QueryDef COM handle — persistence is on the DB.
                    Bindings.Winax.WINAX_BINDING.release(qdef)->ignore
                    Promise.resolve(Ok({success: true, error: None}))
                  }
                }
              })
            }
          }
        }
      }
    }
  }

  let setQuerySql = (self: t, name: string, sql: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    // dao.py:381-394 — QueryDefs(name).SQL = sql
    if !self.isConnected {
      Promise.resolve(Ok({success: false, error: Some("Not connected")}))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok({success: false, error: Some("No session")}))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok({success: false, error: Some("No DB handle")}))
          | Some(db) => {
              // db.QueryDefs(name) — get the QueryDef by name
              Bindings.Winax.WINAX_BINDING.invokeAsObject(db, "QueryDefs", [ComInterfaces.VStr(name)])
              ->Promise.then(qdefResult => {
                switch qdefResult {
                | Error(e) => {
                    Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                  }
                | Ok(qdef) => {
                    // qdef.SQL = sql — set the SQL property using WINAX_BINDING.set
                    Bindings.Winax.WINAX_BINDING.set(qdef, "SQL", ComInterfaces.VStr(sql))
                    ->Promise.then(setResult => {
                      Bindings.Winax.WINAX_BINDING.release(qdef)->ignore
                      switch setResult {
                      | Error(e) => {
                          Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                        }
                      | Ok(_) => {
                          Promise.resolve(Ok({success: true, error: None}))
                        }
                      }
                    })
                  }
                }
              })
            }
          }
        }
      }
    }
  }

  let deleteQuery = (self: t, name: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    // dao.py:396-408 — QueryDefs.Delete(name)
    if !self.isConnected {
      Promise.resolve(Ok({success: false, error: Some("Not connected")}))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok({success: false, error: Some("No session")}))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok({success: false, error: Some("No DB handle")}))
          | Some(db) => {
              // db.QueryDefs — get the QueryDefs collection via property access (same pattern as TableDefs)
              Bindings.Winax.WINAX_BINDING.get(db, "QueryDefs")
              ->Promise.then(qdefsResult => {
                switch qdefsResult {
                | Error(e) => {
                    Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                  }
                | Ok(qdefs) => {
                    // Wrap proxy in envelope so DAO collection methods (Delete) are reachable
                    let qdefsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(qdefs)
                    Bindings.Winax.WINAX_BINDING.invoke(qdefsHandle, "Delete", [ComInterfaces.VStr(name)])
                    ->Promise.then(deleteResult => {
                      Bindings.Winax.WINAX_BINDING.release(qdefsHandle)->ignore
                      switch deleteResult {
                      | Error(e) => {
                          Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                        }
                      | Ok(_) => {
                          Promise.resolve(Ok({success: true, error: None}))
                        }
                      }
                    })
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
  // _accessSqlType — map Access type name to Jet SQL DDL type string
  // Matches Python dao.py:536-563
  // ---------------------------------------------------------------------------

  let _accessSqlType: (string, int) => string = (accessType: string, size: int): string => {
    switch accessType {
    | "Text" => {
        let actualSize = size <= 0 ? 255 : size
        "VARCHAR(" ++ Int.toString(actualSize) ++ ")"
      }
    | "Long Integer" => "INTEGER"
    | "Integer" => "SMALLINT"
    | "Byte" => "BYTE"
    | "Currency" => "MONEY"
    | "Single" => "SINGLE"
    | "Double" => "DOUBLE"
    | "Date/Time" => "DATETIME"
    | "Memo" => "MEMO"
    | "Boolean" => "BIT"
    | "Binary" => "BINARY"
    | "GUID" => "GUID"
    | "Big Integer" => "BIGINT"
    | "Counter" => "COUNTER"
    | "AutoNumber" => "COUNTER"
    | "Decimal" => "DECIMAL"
    | "Unsigned Byte" => "BYTE"
    | "Unsigned Integer" => "INTEGER"
    | "Unsigned Long Integer" => "INTEGER"
    | _ => {
        let actualSize = size <= 0 ? 255 : size
        "VARCHAR(" ++ Int.toString(actualSize) ++ ")"
      }
    }
  }

  // ---------------------------------------------------------------------------
  // _columnSchemaToDict — convert Interfaces.columnSchema to Python oracle dict shape
  // The oracle expects: name, type, size, required, is_autoincrement, primary_key
  // ReScript columnSchema has: name, sourceType (→type), maxLength (→size),
  //                           allowNull (→NOT required), isAutoincrement, no primary_key
  // We infer primary_key from isAutoincrement (the common case).
  // ---------------------------------------------------------------------------

  let _columnSchemaToOracleDict: Interfaces.columnSchema => dict<JSON.t> = (col: Interfaces.columnSchema): dict<JSON.t> => {
    let d = Dict.make()
    Dict.set(d, "name", JSON.String(col.name))
    Dict.set(d, "type", JSON.String(col.sourceType))
    let size = switch col.maxLength {
    | Some(n) => n
    | None => 255
    }
    Dict.set(d, "size", JSON.Number(float_of_int(size)))
    // allowNull=false means NOT NULL in DDL
    Dict.set(d, "required", JSON.Boolean(!col.allowNull))
    Dict.set(d, "is_autoincrement", JSON.Boolean(col.isAutoincrement))
    // Infer primary_key from isAutoincrement (common case); callers can override
    Dict.set(d, "primary_key", JSON.Boolean(col.isAutoincrement))
    d
  }

  // ---------------------------------------------------------------------------
  // _buildCreateTableSql — build Jet DDL CREATE TABLE SQL
  // Matches Python dao.py:856-905
  // ---------------------------------------------------------------------------

  let _buildCreateTableSql: (string, array<Interfaces.columnSchema>) => string = (
    tableName: string,
    columns: array<Interfaces.columnSchema>,
  ): string => {
    let colDefs: array<string> = []
    let pkCol: ref<option<string>> = ref(None)
    let i = ref(0)
    while i.contents < Array.length(columns) {
      let col = Array.unsafe_get(columns, i.contents)
      let colName = col.name
      let colType = col.sourceType
      let colSize = switch col.maxLength {
      | Some(n) => n
      | None => 255
      }
      let required = !col.allowNull
      let isAutoincrement = col.isAutoincrement
      let isPk = isAutoincrement // infer PK from autoincrement

      let typeSql = _accessSqlType(colType, colSize)
      let colDef = "[" ++ colName ++ "] " ++ typeSql
      let colDef = if isAutoincrement || isPk {
        colDef ++ " NOT NULL"
      } else if required {
        colDef ++ " NOT NULL"
      } else {
        colDef
      }
      let _ = Array.push(colDefs, colDef)
      if isAutoincrement {
        pkCol.contents = Some(colName)
      }
      i.contents = i.contents + 1
    }
    switch pkCol.contents {
    | Some(pk) => let _ = Array.push(colDefs, "PRIMARY KEY ([" ++ pk ++ "])"); ()
    | None => ()
    }
    let allColDefs = Js.Array.joinWith(", ", colDefs)
    "CREATE TABLE [" ++ tableName ++ "] (" ++ allColDefs ++ ")"
  }

  // ---------------------------------------------------------------------------
  // _deleteTableRelations — walk db.Relations in reverse, delete matches
  // Matches Python dao.py:927-932
  // ---------------------------------------------------------------------------

  let _deleteTableRelations: (ComInterfaces.comObject, string) => Promise.t<unit> = (
    db: ComInterfaces.comObject,
    tableName: string,
  ): Promise.t<unit> => {
    // Get Relations collection
    Bindings.Winax.WINAX_BINDING.get(db, "Relations")
    ->Promise.then(relationsResult => {
      switch relationsResult {
      | Error(e) => Promise.resolve()
      | Ok(relations) => {
          let relationsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(relations)
          Bindings.Winax.WINAX_BINDING.getCount(relationsHandle)
          ->Promise.then(countResult => {
            switch countResult {
            | Error(_) => {
                Bindings.Winax.WINAX_BINDING.release(relationsHandle)->ignore
                Promise.resolve()
              }
            | Ok(count) => {
                // Walk in reverse: for i = count-1 downto 0
                let idx = ref(count - 1)
                let rec loop: unit => Promise.t<unit> = () => {
                  if idx.contents < 0 {
                    Bindings.Winax.WINAX_BINDING.release(relationsHandle)->ignore
                    Promise.resolve()
                  } else {
                    let idxVar = ComInterfaces.VInt(idx.contents)
                    Bindings.Winax.WINAX_BINDING.getItem(relationsHandle, idxVar)
                    ->Promise.then(itemResult => {
                      switch itemResult {
                      | Error(_) => {
                          Bindings.Winax.WINAX_BINDING.release(relationsHandle)->ignore
                          Promise.resolve()
                        }
                      | Ok(rel) => {
                          Bindings.Winax.WINAX_BINDING.get(rel, "Table")
                          ->Promise.then(tableResult => {
                            Bindings.Winax.WINAX_BINDING.get(rel, "ForeignTable")
                            ->Promise.then(foreignTableResult => {
                              Bindings.Winax.WINAX_BINDING.get(rel, "Name")
                              ->Promise.then(nameResult => {
                                let shouldDelete = switch (tableResult, foreignTableResult) {
                                | (Ok(JSON.String(t)), Ok(JSON.String(ft))) =>
                                  t === tableName || ft === tableName
                                | _ => false
                                }
                                Bindings.Winax.WINAX_BINDING.release(rel)->ignore
                                if shouldDelete {
                                  switch nameResult {
                                  | Ok(JSON.String(relName)) => {
                                      Bindings.Winax.WINAX_BINDING.invoke(relationsHandle, "Delete", [ComInterfaces.VStr(relName)])
                                      ->Promise.then(_ => {
                                        idx.contents = idx.contents - 1
                                        loop()
                                      })
                                      ->Promise.catch(_ => {
                                        idx.contents = idx.contents - 1
                                        loop()
                                      })
                                    }
                                  | _ => {
                                      idx.contents = idx.contents - 1
                                      loop()
                                    }
                                  }
                                } else {
                                  idx.contents = idx.contents - 1
                                  loop()
                                }
                              })
                            })
                          })
                        }
                      }
                    })
                  }
                }
                loop()
              }
            }
          })
        }
      }
    })
    ->Promise.catch(_ => Promise.resolve())
  }

  // ---------------------------------------------------------------------------
  // _ddlExecute — execute a DDL SQL statement via DAO Execute with FAIL_ON_ERROR
  // Returns Promise.t<result<unit, Errors.t>>
  // ---------------------------------------------------------------------------

  let _ddlExecute: (t, string) => Promise.t<result<unit, Errors.t>> = (
    self: t,
    sql: string,
  ): Promise.t<result<unit, Errors.t>> => {
    if !self.isConnected {
      Promise.resolve(Error(Errors.databaseError("Not connected")))
    } else {
      switch self.session {
      | None => Promise.resolve(Error(Errors.databaseError("No session")))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Error(Errors.databaseError("No DB handle")))
          | Some(db) => {
              // DAO_DB_FAIL_ON_ERROR = 128
              Bindings.Winax.WINAX_BINDING.invoke(db, "Execute", [ComInterfaces.VStr(sql), ComInterfaces.VInt(128)])
              ->Promise.then(execResult => {
                switch execResult {
                | Error(e) => {
                    let msg = Errors._message(e)
                    Promise.resolve(Error(Errors.databaseError(msg)))
                  }
                | Ok(_) => Promise.resolve(Ok())
                }
              })
              ->Promise.catch(e => {
                let msg = _exnMessage(e)
                Promise.resolve(Error(Errors.databaseError(msg)))
              })
            }
          }
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // createTable — create table via Jet DDL
  // ---------------------------------------------------------------------------

  let createTable = (self: t, name: string, columns: array<Interfaces.columnSchema>): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    let sql = _buildCreateTableSql(name, columns)
    _ddlExecute(self, sql)
    ->Promise.then(result => {
      switch result {
      | Ok(_) => Promise.resolve(Ok({success: true, error: None}))
      | Error(e) => Promise.resolve(Error(e))
      }
    })
  }

  // ---------------------------------------------------------------------------
  // deleteTable — drop table after removing referencing relations
  // ---------------------------------------------------------------------------

  let deleteTable = (self: t, name: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    if !self.isConnected {
      Promise.resolve(Error(Errors.databaseError("Not connected")))
    } else {
      switch self.session {
      | None => Promise.resolve(Error(Errors.databaseError("No session")))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Error(Errors.databaseError("No DB handle")))
          | Some(db) => {
              _deleteTableRelations(db, name)
              ->Promise.then(_ => {
                let sql = "DROP TABLE [" ++ name ++ "]"
                _ddlExecute(self, sql)
                ->Promise.then(result => {
                  switch result {
                  | Ok(_) => Promise.resolve(Ok({success: true, error: None}))
                  | Error(e) => Promise.resolve(Error(e))
                  }
                })
              })
            }
          }
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // _jsonStr — extract string from JSON option with default
  // ---------------------------------------------------------------------------

  let _jsonStr: (option<JSON.t>, string) => string = (j: option<JSON.t>, default: string): string => {
    switch j {
    | Some(JSON.String(s)) => s
    | _ => default
    }
  }

  // ---------------------------------------------------------------------------
  // _jsonInt — extract int from JSON option with default
  // ---------------------------------------------------------------------------

  let _jsonInt: (option<JSON.t>, int) => int = (j: option<JSON.t>, default: int): int => {
    switch j {
    | Some(JSON.Number(n)) => Float.toInt(n)
    | _ => default
    }
  }

  // ---------------------------------------------------------------------------
  // _jsonBool — extract bool from JSON option with default
  // ---------------------------------------------------------------------------

  let _jsonBool: (option<JSON.t>, bool) => bool = (j: option<JSON.t>, default: bool): bool => {
    switch j {
    | Some(JSON.Boolean(b)) => b
    | _ => default
    }
  }

  // ---------------------------------------------------------------------------
  // _alterTableAddColumn — ADD COLUMN via ALTER TABLE DDL
  // ---------------------------------------------------------------------------

  let _alterTableAddColumn: (ComInterfaces.comObject, string, dict<JSON.t>) => Promise.t<result<dict<JSON.t>, Errors.t>> = (
    db: ComInterfaces.comObject,
    tableName: string,
    params: dict<JSON.t>,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    let colName = _jsonStr(Dict.get(params, "name"), "")
    // colType alias: prefer colType, fall back to type
    let colTypeRaw = switch Dict.get(params, "colType") {
      | Some(v) => Some(v)
      | None => Dict.get(params, "type")
    }
    let colType = _jsonStr(colTypeRaw, "Text")
    let size = _jsonInt(Dict.get(params, "size"), 255)
    let nullable = _jsonBool(Dict.get(params, "nullable"), true)
    let sqlType = _accessSqlType(colType, size)
    let nullableStr = if nullable { "" } else { " NOT NULL" }
    let sql = "ALTER TABLE [" ++ tableName ++ "] ADD COLUMN [" ++ colName ++ "] " ++ sqlType ++ nullableStr
    Bindings.Winax.WINAX_BINDING.invoke(db, "Execute", [ComInterfaces.VStr(sql), ComInterfaces.VInt(128)])
    ->Promise.then(execResult => {
      switch execResult {
      | Error(e) => Promise.resolve(Ok(Dict.fromArray([
          ("action", JSON.String("add_column")),
          ("success", JSON.Boolean(false)),
          ("error", JSON.String(Errors._message(e)))
        ])))
      | Ok(_) => Promise.resolve(Ok(Dict.fromArray([
          ("action", JSON.String("add_column")),
          ("success", JSON.Boolean(true))
        ])))
      }
    })
    ->Promise.catch(e => {
      Promise.resolve(Ok(Dict.fromArray([
        ("action", JSON.String("add_column")),
        ("success", JSON.Boolean(false)),
        ("error", JSON.String(_exnMessage(e)))
      ])))
    })
  }

  // ---------------------------------------------------------------------------
  // _alterTableDropColumn — DROP COLUMN via ALTER TABLE DDL
  // ---------------------------------------------------------------------------

  let _alterTableDropColumn: (ComInterfaces.comObject, string, dict<JSON.t>) => Promise.t<result<dict<JSON.t>, Errors.t>> = (
    db: ComInterfaces.comObject,
    tableName: string,
    params: dict<JSON.t>,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    let colName = _jsonStr(Dict.get(params, "name"), "")
    let sql = "ALTER TABLE [" ++ tableName ++ "] DROP COLUMN [" ++ colName ++ "]"
    Bindings.Winax.WINAX_BINDING.invoke(db, "Execute", [ComInterfaces.VStr(sql), ComInterfaces.VInt(128)])
    ->Promise.then(execResult => {
      switch execResult {
      | Error(e) => Promise.resolve(Ok(Dict.fromArray([
          ("action", JSON.String("drop_column")),
          ("success", JSON.Boolean(false)),
          ("error", JSON.String(Errors._message(e)))
        ])))
      | Ok(_) => Promise.resolve(Ok(Dict.fromArray([
          ("action", JSON.String("drop_column")),
          ("success", JSON.Boolean(true))
        ])))
      }
    })
    ->Promise.catch(e => {
      Promise.resolve(Ok(Dict.fromArray([
        ("action", JSON.String("drop_column")),
        ("success", JSON.Boolean(false)),
        ("error", JSON.String(_exnMessage(e)))
      ])))
    })
  }

  // ---------------------------------------------------------------------------
  // _alterTableModifyColumn — ALTER COLUMN via ALTER TABLE DDL
  // ---------------------------------------------------------------------------

  let _alterTableModifyColumn: (ComInterfaces.comObject, string, dict<JSON.t>) => Promise.t<result<dict<JSON.t>, Errors.t>> = (
    db: ComInterfaces.comObject,
    tableName: string,
    params: dict<JSON.t>,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    let colName = _jsonStr(Dict.get(params, "name"), "")
    // colType alias: prefer colType, fall back to type
    let colTypeRaw = switch Dict.get(params, "colType") {
      | Some(v) => Some(v)
      | None => Dict.get(params, "type")
    }
    let colType = _jsonStr(colTypeRaw, "Text")
    let size = _jsonInt(Dict.get(params, "size"), 255)
    let nullable = _jsonBool(Dict.get(params, "nullable"), true)
    let sqlType = _accessSqlType(colType, size)
    let nullableStr = if nullable { "" } else { " NOT NULL" }
    let sql = "ALTER TABLE [" ++ tableName ++ "] ALTER COLUMN [" ++ colName ++ "] " ++ sqlType ++ nullableStr
    Bindings.Winax.WINAX_BINDING.invoke(db, "Execute", [ComInterfaces.VStr(sql), ComInterfaces.VInt(128)])
    ->Promise.then(execResult => {
      switch execResult {
      | Error(e) => Promise.resolve(Ok(Dict.fromArray([
          ("action", JSON.String("modify_column")),
          ("success", JSON.Boolean(false)),
          ("error", JSON.String(Errors._message(e)))
        ])))
      | Ok(_) => Promise.resolve(Ok(Dict.fromArray([
          ("action", JSON.String("modify_column")),
          ("success", JSON.Boolean(true))
        ])))
      }
    })
    ->Promise.catch(e => {
      Promise.resolve(Ok(Dict.fromArray([
        ("action", JSON.String("modify_column")),
        ("success", JSON.Boolean(false)),
        ("error", JSON.String(_exnMessage(e)))
      ])))
    })
  }

  // ---------------------------------------------------------------------------
  // _alterTableRenameTable — rename via DAO TableDefs(name).Name = new_name
  // ---------------------------------------------------------------------------

  let _alterTableRenameTable: (ComInterfaces.comObject, string, dict<JSON.t>) => Promise.t<result<dict<JSON.t>, Errors.t>> = (
    db: ComInterfaces.comObject,
    tableName: string,
    params: dict<JSON.t>,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    let newName = _jsonStr(Dict.get(params, "new_name"), "")
    // Get TableDefs collection
    Bindings.Winax.WINAX_BINDING.invokeAsObject(db, "TableDefs", [ComInterfaces.VStr(tableName)])
    ->Promise.then(tdefResult => {
      switch tdefResult {
      | Error(e) => {
          Promise.resolve(Ok(Dict.fromArray([
            ("action", JSON.String("rename_table")),
            ("success", JSON.Boolean(false)),
            ("error", JSON.String(Errors._message(e)))
          ])))
        }
      | Ok(tdef) => {
          // Set the Name property
          Bindings.Winax.WINAX_BINDING.set(tdef, "Name", ComInterfaces.VStr(newName))
          ->Promise.then(setResult => {
            Bindings.Winax.WINAX_BINDING.releaseAsync(tdef)->ignore
            switch setResult {
            | Error(e) => Promise.resolve(Ok(Dict.fromArray([
                ("action", JSON.String("rename_table")),
                ("success", JSON.Boolean(false)),
                ("error", JSON.String(Errors._message(e)))
              ])))
            | Ok(_) => Promise.resolve(Ok(Dict.fromArray([
                ("action", JSON.String("rename_table")),
                ("success", JSON.Boolean(true))
              ])))
            }
          })
          ->Promise.catch(e => {
            Bindings.Winax.WINAX_BINDING.releaseAsync(tdef)->ignore
            Promise.resolve(Ok(Dict.fromArray([
              ("action", JSON.String("rename_table")),
              ("success", JSON.Boolean(false)),
              ("error", JSON.String(_exnMessage(e)))
            ])))
          })
        }
      }
    })
    ->Promise.catch(e => {
      Promise.resolve(Ok(Dict.fromArray([
        ("action", JSON.String("rename_table")),
        ("success", JSON.Boolean(false)),
        ("error", JSON.String(_exnMessage(e)))
      ])))
    })
  }

  // ---------------------------------------------------------------------------
  // _alterTableRenameColumn — rename via DAO TableDefs(name).Fields(old).Name = new
  // ---------------------------------------------------------------------------

  let _alterTableRenameColumn: (ComInterfaces.comObject, string, dict<JSON.t>) => Promise.t<result<dict<JSON.t>, Errors.t>> = (
    db: ComInterfaces.comObject,
    tableName: string,
    params: dict<JSON.t>,
  ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    let oldName = _jsonStr(Dict.get(params, "name"), "")
    let newName = _jsonStr(Dict.get(params, "new_name"), "")
    // Get TableDef for the table
    Bindings.Winax.WINAX_BINDING.invokeAsObject(db, "TableDefs", [ComInterfaces.VStr(tableName)])
    ->Promise.then(tdefResult => {
      switch tdefResult {
      | Error(e) => {
          Promise.resolve(Ok(Dict.fromArray([
            ("action", JSON.String("rename_column")),
            ("success", JSON.Boolean(false)),
            ("error", JSON.String(Errors._message(e)))
          ])))
        }
      | Ok(tdef) => {
          // Get the Field object
          Bindings.Winax.WINAX_BINDING.invokeAsObject(tdef, "Fields", [ComInterfaces.VStr(oldName)])
          ->Promise.then(fieldResult => {
            Bindings.Winax.WINAX_BINDING.releaseAsync(tdef)->ignore
            switch fieldResult {
            | Error(e) => Promise.resolve(Ok(Dict.fromArray([
                ("action", JSON.String("rename_column")),
                ("success", JSON.Boolean(false)),
                ("error", JSON.String(Errors._message(e)))
              ])))
            | Ok(field) => {
                // Set the Name property
                Bindings.Winax.WINAX_BINDING.set(field, "Name", ComInterfaces.VStr(newName))
                ->Promise.then(setResult => {
                  Bindings.Winax.WINAX_BINDING.releaseAsync(field)->ignore
                  switch setResult {
                  | Error(e) => Promise.resolve(Ok(Dict.fromArray([
                      ("action", JSON.String("rename_column")),
                      ("success", JSON.Boolean(false)),
                      ("error", JSON.String(Errors._message(e)))
                    ])))
                  | Ok(_) => Promise.resolve(Ok(Dict.fromArray([
                      ("action", JSON.String("rename_column")),
                      ("success", JSON.Boolean(true))
                    ])))
                  }
                })
                ->Promise.catch(e => {
                  Bindings.Winax.WINAX_BINDING.releaseAsync(field)->ignore
                  Promise.resolve(Ok(Dict.fromArray([
                    ("action", JSON.String("rename_column")),
                    ("success", JSON.Boolean(false)),
                    ("error", JSON.String(_exnMessage(e)))
                  ])))
                })
              }
            }
          })
          ->Promise.catch(e => {
            Bindings.Winax.WINAX_BINDING.releaseAsync(tdef)->ignore
            Promise.resolve(Ok(Dict.fromArray([
              ("action", JSON.String("rename_column")),
              ("success", JSON.Boolean(false)),
              ("error", JSON.String(_exnMessage(e)))
            ])))
          })
        }
      }
    })
    ->Promise.catch(e => {
      Promise.resolve(Ok(Dict.fromArray([
        ("action", JSON.String("rename_column")),
        ("success", JSON.Boolean(false)),
        ("error", JSON.String(_exnMessage(e)))
      ])))
    })
  }

  // ---------------------------------------------------------------------------
  // alterTable — batch DDL: add_column, drop_column, modify_column, rename_table, rename_column
  // Returns {success: bool, operations: [{action, success, error?}...]} envelope
  // ---------------------------------------------------------------------------

  let alterTable = (self: t, name: string, actions: array<dict<JSON.t>>): Promise.t<result<dict<JSON.t>, Errors.t>> => {
    if !self.isConnected {
      Promise.resolve(Error(Errors.databaseError("Not connected")))
    } else {
      switch self.session {
      | None => Promise.resolve(Error(Errors.databaseError("No session")))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Error(Errors.databaseError("No DB handle")))
          | Some(db) => {
              let rec processOps = (
                db: ComInterfaces.comObject,
                remaining: array<dict<JSON.t>>,
                acc: array<dict<JSON.t>>,
              ): Promise.t<result<dict<JSON.t>, Errors.t>> => {
                switch Array.get(remaining, 0) {
                | None => {
                    let allOk = Array.reduce(acc, true, (ok, op) => {
                      let success = switch Dict.get(op, "success") {
                      | Some(JSON.Boolean(b)) => b
                      | _ => false
                      }
                      ok && success
                    })
                    Promise.resolve(Ok(Dict.fromArray([
                      ("success", JSON.Boolean(allOk)),
                      ("operations", JSON.Array(Array.map(acc, op => JSON.Object(op))))
                    ])))
                  }
                | Some(actionDict) => {
                    let actionName = switch Dict.get(actionDict, "action") {
                    | Some(JSON.String(s)) => s
                    | _ => ""
                    }
                    let params = switch Dict.get(actionDict, "params") {
                    | Some(JSON.Object(p)) => p
                    | _ => Dict.make()
                    }
                    let rest = Array.slice(remaining, ~start=1, ~end=Array.length(remaining))
                    let resultPromise: Promise.t<result<dict<JSON.t>, Errors.t>> = switch actionName {
                    | "add_column" => _alterTableAddColumn(db, name, params)
                    | "drop_column" => _alterTableDropColumn(db, name, params)
                    | "modify_column" => _alterTableModifyColumn(db, name, params)
                    | "rename_table" => _alterTableRenameTable(db, name, params)
                    | "rename_column" => _alterTableRenameColumn(db, name, params)
                    | _ => Promise.resolve(Ok(Dict.fromArray([
                        ("action", JSON.String(actionName)),
                        ("success", JSON.Boolean(false)),
                        ("error", JSON.String("Unknown action: " ++ actionName))
                      ])))
                    }
                    resultPromise
                      ->Promise.then(opResult => {
                        let newAcc = switch opResult {
                        | Ok(opDict) => Array.concat(acc, [opDict])
                        | Error(_) => Array.concat(acc, [Dict.fromArray([
                            ("action", JSON.String(actionName)),
                            ("success", JSON.Boolean(false)),
                            ("error", JSON.String("Unexpected error in " ++ actionName))
                          ])])
                        }
                        processOps(db, rest, newAcc)
                      })
                  }
                }
              }
              processOps(db, actions, [])
            }
          }
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // _buildCreateIndexSql — build Jet DDL CREATE INDEX SQL
  // Matches Python dao.py:940-980
  // ---------------------------------------------------------------------------

  let _buildCreateIndexSql: (string, string, array<string>, bool, bool) => string = (
    indexName: string,
    tableName: string,
    columns: array<string>,
    unique: bool,
    ignoreNulls: bool,
  ): string => {
    let colList = Js.Array.joinWith(", ", Array.map(columns, c => "[" ++ c ++ "]"))
    let sql = "CREATE "
      ++ (unique ? "UNIQUE " : "")
      ++ "INDEX ["
      ++ indexName
      ++ "] ON ["
      ++ tableName
      ++ "] ("
      ++ colList
      ++ ")"
      ++ (ignoreNulls ? " WITH IGNORE NULL" : "")
    sql
  }

  // ---------------------------------------------------------------------------
  // _buildDropIndexSql — build Jet DDL DROP INDEX SQL
  // Matches Python dao.py:982-1010
  // The ON [table] clause is REQUIRED in Jet SQL.
  // ---------------------------------------------------------------------------

  let _buildDropIndexSql: (string, string) => string = (indexName: string, tableName: string): string => {
    "DROP INDEX [" ++ indexName ++ "] ON [" ++ tableName ++ "]"
  }

  // ---------------------------------------------------------------------------
  // createIndex — create index via Jet DDL
  // ---------------------------------------------------------------------------

  let createIndex = (
    self: t,
    indexName: string,
    table: string,
    columns: array<string>,
    ~unique: bool=false,
    ~ignoreNulls: bool=false,
  ): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    let sql = _buildCreateIndexSql(indexName, table, columns, unique, ignoreNulls)
    _ddlExecute(self, sql)
    ->Promise.then(result => {
      switch result {
      | Ok(_) => Promise.resolve(Ok({success: true, error: None}))
      | Error(e) => Promise.resolve(Error(e))
      }
    })
  }

  // ---------------------------------------------------------------------------
  // dropIndex — drop index via Jet DDL
  // ---------------------------------------------------------------------------

  let dropIndex = (self: t, indexName: string, table: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    let sql = _buildDropIndexSql(indexName, table)
    _ddlExecute(self, sql)
    ->Promise.then(result => {
      switch result {
      | Ok(_) => Promise.resolve(Ok({success: true, error: None}))
      | Error(e) => Promise.resolve(Error(e))
      }
    })
  }

  // ---------------------------------------------------------------------------
  // getIndexes — read indexes from DAO TableDefs(t).Indexes collection
  // ---------------------------------------------------------------------------

  let getIndexes = (self: t, tableName: string): Promise.t<result<array<Interfaces.indexInfo>, Errors.t>> => {
    if !self.isConnected {
      Promise.resolve(Error(Errors.databaseError("Not connected")))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok([]))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok([]))
          | Some(db) => {
              // Get TableDefs collection
              Bindings.Winax.WINAX_BINDING.get(db, "TableDefs")
              ->Promise.then(tableDefsResult => {
                switch tableDefsResult {
                | Error(e) => Promise.resolve(Error(e))
                | Ok(tableDefs) => {
                    let tableDefsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(tableDefs)
                    Bindings.Winax.WINAX_BINDING.getCount(tableDefsHandle)
                    ->Promise.then(countResult => {
                      switch countResult {
                      | Error(e) => {
                          Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                          Promise.resolve(Error(e))
                        }
                      | Ok(count) => {
                          // Find the TableDef by name using a while loop
                          let foundTd: ref<option<ComInterfaces.comObject>> = ref(None)
                          let i = ref(0)
                          let rec lookupLoop: unit => Promise.t<result<ComInterfaces.comObject, Errors.t>> = () => {
                            if i.contents >= count {
                              Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                              Promise.resolve(Error(Errors.databaseError("Table not found: " ++ tableName)))
                            } else {
                              let idxVar = ComInterfaces.VInt(i.contents)
                              Bindings.Winax.WINAX_BINDING.getItem(tableDefsHandle, idxVar)
                              ->Promise.then(itemResult => {
                                switch itemResult {
                                | Error(e) => {
                                    Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                    Promise.resolve(Error(e))
                                  }
                                | Ok(td) => {
                                    Bindings.Winax.WINAX_BINDING.get(td, "Name")
                                    ->Promise.then(nameResult => {
                                      switch nameResult {
                                      | Ok(JSON.String(name)) => {
                                          if name === tableName {
                                            foundTd.contents = Some(td)
                                            Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                            Promise.resolve(Ok(td))
                                          } else {
                                            Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                            i.contents = i.contents + 1
                                            lookupLoop()
                                          }
                                        }
                                      | Error(e) => {
                                          Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                          Bindings.Winax.WINAX_BINDING.release(tableDefsHandle)->ignore
                                          Promise.resolve(Error(e))
                                        }
                                      | _ => {
                                          Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                          i.contents = i.contents + 1
                                          lookupLoop()
                                        }
                                      }
                                    })
                                  }
                                }
                              })
                            }
                          }
                          lookupLoop()
                          ->Promise.then(findResult => {
                            switch findResult {
                            | Error(e) => Promise.resolve(Error(e))
                            | Ok(td) => {
                                // Get Indexes collection from the TableDef
                                Bindings.Winax.WINAX_BINDING.get(td, "Indexes")
                                ->Promise.then(indexesResult => {
                                  Bindings.Winax.WINAX_BINDING.release(td)->ignore
                                  switch indexesResult {
                                  | Error(e) => Promise.resolve(Error(e))
                                  | Ok(indexes) => {
                                      let indexesHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(indexes)
                                      Bindings.Winax.WINAX_BINDING.getCount(indexesHandle)
                                      ->Promise.then(countResult => {
                                        switch countResult {
                                        | Error(e) => {
                                            Bindings.Winax.WINAX_BINDING.release(indexesHandle)->ignore
                                            Promise.resolve(Error(e))
                                          }
                                        | Ok(count) => {
                                            let results: array<Interfaces.indexInfo> = []
                                            let idx2 = ref(0)
                                            // Collect indexes sequentially
                                            let rec collectLoop: unit => Promise.t<result<array<Interfaces.indexInfo>, Errors.t>> = () => {
                                              if idx2.contents >= count {
                                                Bindings.Winax.WINAX_BINDING.release(indexesHandle)->ignore
                                                Promise.resolve(Ok(results))
                                              } else {
                                                let idxVar = ComInterfaces.VInt(idx2.contents)
                                                Bindings.Winax.WINAX_BINDING.getItem(indexesHandle, idxVar)
                                                ->Promise.then(itemResult => {
                                                  switch itemResult {
                                                  | Error(e) => {
                                                      Bindings.Winax.WINAX_BINDING.release(indexesHandle)->ignore
                                                      Promise.resolve(Error(e))
                                                    }
                                                  | Ok(idxObj) => {
                                                      // Get all index properties in parallel
                                                      Bindings.Winax.WINAX_BINDING.get(idxObj, "Name")
                                                      ->Promise.then(nameResult => {
                                                        Bindings.Winax.WINAX_BINDING.get(idxObj, "Unique")
                                                        ->Promise.then(uniqueResult => {
                                                          Bindings.Winax.WINAX_BINDING.get(idxObj, "Primary")
                                                          ->Promise.then(primaryResult => {
                                                            Bindings.Winax.WINAX_BINDING.get(idxObj, "IgnoreNulls")
                                                            ->Promise.then(ignoreNullsResult => {
                                                              Bindings.Winax.WINAX_BINDING.get(idxObj, "Fields")
                                                              ->Promise.then(fieldsResult => {
                                                                Bindings.Winax.WINAX_BINDING.release(idxObj)->ignore
                                                                switch (nameResult, uniqueResult, primaryResult, ignoreNullsResult, fieldsResult) {
                                                                | (Ok(JSON.String(idxName)), Ok(JSON.Boolean(isUnique)), Ok(JSON.Boolean(isPrimary)), Ok(JSON.Boolean(ignoresNulls)), Ok(JSON.Object(fieldsObj))) => {
                                                                    // Extract column names from the Fields collection
                                                                    let fieldsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(fieldsObj)
                                                                    Bindings.Winax.WINAX_BINDING.getCount(fieldsHandle)
                                                                    ->Promise.then(fieldCountResult => {
                                                                      switch fieldCountResult {
                                                                      | Error(_) => {
                                                                          Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                                          let info: Interfaces.indexInfo = {
                                                                            name: idxName,
                                                                            columns: [],
                                                                            isUnique: isUnique,
                                                                            isPrimary: isPrimary,
                                                                            ignoreNulls: ignoresNulls,
                                                                          }
                                                                          let _ = Array.push(results, info)
                                                                          idx2.contents = idx2.contents + 1
                                                                          collectLoop()
                                                                        }
                                                                      | Ok(fieldCount) => {
                                                                          // Collect field names sequentially
                                                                          let colNames: array<string> = []
                                                                          let fieldIdx = ref(0)
                                                                          let rec fieldLoop: unit => Promise.t<unit> = () => {
                                                                            if fieldIdx.contents >= fieldCount {
                                                                              Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                                              Promise.resolve()
                                                                            } else {
                                                                              let fieldIdxVar = ComInterfaces.VInt(fieldIdx.contents)
                                                                              Bindings.Winax.WINAX_BINDING.getItem(fieldsHandle, fieldIdxVar)
                                                                              ->Promise.then(fieldItemResult => {
                                                                                switch fieldItemResult {
                                                                                | Error(_) => {
                                                                                    Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                                                                    Promise.resolve()
                                                                                  }
                                                                                | Ok(fieldObj) => {
                                                                                    Bindings.Winax.WINAX_BINDING.get(fieldObj, "Name")
                                                                                    ->Promise.then(fieldNameResult => {
                                                                                      Bindings.Winax.WINAX_BINDING.release(fieldObj)->ignore
                                                                                      switch fieldNameResult {
                                                                                      | Ok(JSON.String(fieldName)) => {
                                                                                          let _ = Array.push(colNames, fieldName)
                                                                                          fieldIdx.contents = fieldIdx.contents + 1
                                                                                          fieldLoop()
                                                                                        }
                                                                                      | _ => {
                                                                                          fieldIdx.contents = fieldIdx.contents + 1
                                                                                          fieldLoop()
                                                                                        }
                                                                                      }
                                                                                    })
                                                                                  }
                                                                                }
                                                                              })
                                                                            }
                                                                          }
                                                                          fieldLoop()
                                                                          ->Promise.then(_ => {
                                                                            let info: Interfaces.indexInfo = {
                                                                              name: idxName,
                                                                              columns: colNames,
                                                                              isUnique: isUnique,
                                                                              isPrimary: isPrimary,
                                                                              ignoreNulls: ignoresNulls,
                                                                            }
                                                                            let _ = Array.push(results, info)
                                                                            idx2.contents = idx2.contents + 1
                                                                            collectLoop()
                                                                          })
                                                                        }
                                                                      }
                                                                    })
                                                                  }
                                                                | _ => {
                                                                    // Fallback on any missing property
                                                                    let info: Interfaces.indexInfo = {
                                                                      name: "",
                                                                      columns: [],
                                                                      isUnique: false,
                                                                      isPrimary: false,
                                                                      ignoreNulls: false,
                                                                    }
                                                                    let _ = Array.push(results, info)
                                                                    idx2.contents = idx2.contents + 1
                                                                    collectLoop()
                                                                  }
                                                                }
                                                              })
                                                            })
                                                          })
                                                        })
                                                      })
                                                    }
                                                  }
                                                })
                                              }
                                            }
                                            collectLoop()
                                          }
                                        }
                                      })
                                    }
                                  }
                                })
                              }
                            }
                          })
                        }
                      }
                    })
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
  // createRelationship — DAO Relations.Append
  // dao.py:478-519: CreateRelation → CreateField × n → Fields.Append → Relations.Append
  // ---------------------------------------------------------------------------

  let createRelationship = (
    self: t,
    name: string,
    table: string,
    columns: array<string>,
    foreignTable: string,
    foreignColumns: array<string>,
  ): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    if !self.isConnected {
      Promise.resolve(Ok({success: false, error: Some("Not connected")}))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok({success: false, error: Some("No session")}))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok({success: false, error: Some("No DB handle")}))
          | Some(db) => {
              // rel = db.CreateRelation(name, table, foreignTable)
              Bindings.Winax.WINAX_BINDING.invokeAsObject(db, "CreateRelation", [ComInterfaces.VStr(name), ComInterfaces.VStr(table), ComInterfaces.VStr(foreignTable)])
              ->Promise.then(relResult => {
                switch relResult {
                | Error(e) => Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                | Ok(relJson) => {
                    let rel: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(relJson)
                    // Build sequential promise chain for each field: create → setForeignName → append
                    let rec loopFields = (idx: int): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
                      if idx >= Array.length(columns) {
                        // All fields created — append the relation to db.Relations
                        Bindings.Winax.WINAX_BINDING.get(db, "Relations")
                        ->Promise.then(relsResult => {
                          switch relsResult {
                          | Error(e) => {
                              Bindings.Winax.WINAX_BINDING.release(rel)->ignore
                              Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                            }
                          | Ok(relsJson) => {
                              let relsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(relsJson)
                              let relAsVariant: ComInterfaces.variant = %raw("(r) => r")(Obj.magic(rel))
                              Bindings.Winax.WINAX_BINDING.invoke(relsHandle, "Append", [relAsVariant])
                              ->Promise.then(_ => {
                                Bindings.Winax.WINAX_BINDING.release(rel)->ignore
                                Bindings.Winax.WINAX_BINDING.release(relsHandle)->ignore
                                Promise.resolve(Ok({success: true, error: None}))
                              })
                              ->Promise.catch(e => {
                                Bindings.Winax.WINAX_BINDING.release(relsHandle)->ignore
                                Promise.resolve(Ok({success: false, error: Some(_exnMessage(e))}))
                              })
                            }
                          }
                        })
                      } else {
                        let colName = Array.unsafe_get(columns, idx)
                        let foreignCol = Array.unsafe_get(foreignColumns, idx)
                        Bindings.Winax.WINAX_BINDING.invokeAsObject(rel, "CreateField", [ComInterfaces.VStr(colName)])
                        ->Promise.then(fieldResult => {
                          switch fieldResult {
                          | Error(e) => {
                              Bindings.Winax.WINAX_BINDING.release(rel)->ignore
                              Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                            }
                          | Ok(fieldJson) => {
                              let field: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(fieldJson)
                              Bindings.Winax.WINAX_BINDING.set(field, "ForeignName", ComInterfaces.VStr(foreignCol))
                              ->Promise.then(_ => {
                                Bindings.Winax.WINAX_BINDING.get(rel, "Fields")
                                ->Promise.then(fieldsResult => {
                                  switch fieldsResult {
                                  | Error(e) => {
                                      Bindings.Winax.WINAX_BINDING.release(field)->ignore
                                      Bindings.Winax.WINAX_BINDING.release(rel)->ignore
                                      Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                                    }
                                  | Ok(fieldsJson) => {
                                      let fieldsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(fieldsJson)
                                      let fieldAsVariant: ComInterfaces.variant = %raw("(f) => f")(Obj.magic(field))
                                      Bindings.Winax.WINAX_BINDING.invoke(fieldsHandle, "Append", [fieldAsVariant])
                                      ->Promise.then(_ => {
                                        Bindings.Winax.WINAX_BINDING.release(field)->ignore
                                        Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                        loopFields(idx + 1)
                                      })
                                      ->Promise.catch(e => {
                                        Bindings.Winax.WINAX_BINDING.release(fieldsHandle)->ignore
                                        Promise.resolve(Ok({success: false, error: Some(_exnMessage(e))}))
                                      })
                                    }
                                  }
                                })
                              })
                            }
                          }
                        })
                      }
                    }
                    loopFields(0)
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
  // deleteRelationship — DAO Relations.Delete
  // dao.py:525-546: db.Relations.Delete(name)
  // ---------------------------------------------------------------------------

  let deleteRelationship = (
    self: t,
    name: string,
    table: string,
  ): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
    if !self.isConnected {
      Promise.resolve(Ok({success: false, error: Some("Not connected")}))
    } else {
      switch self.session {
      | None => Promise.resolve(Ok({success: false, error: Some("No session")}))
      | Some(session) => {
          switch ComSession.getCurrentDb(session) {
          | None => Promise.resolve(Ok({success: false, error: Some("No DB handle")}))
          | Some(db) => {
              Bindings.Winax.WINAX_BINDING.get(db, "Relations")
              ->Promise.then(relsResult => {
                switch relsResult {
                | Error(e) => Promise.resolve(Ok({success: false, error: Some(Errors._message(e))}))
                | Ok(relsJson) => {
                    let relsHandle: ComInterfaces.comObject = %raw("v => ({ __p__: v })")(relsJson)
                    Bindings.Winax.WINAX_BINDING.invoke(relsHandle, "Delete", [ComInterfaces.VStr(name)])
                    ->Promise.then(_ => {
                      Bindings.Winax.WINAX_BINDING.release(relsHandle)->ignore
                      Promise.resolve(Ok({success: true, error: None}))
                    })
                    ->Promise.catch(e => {
Bindings.Winax.WINAX_BINDING.release(relsHandle)->ignore
                                Promise.resolve(Ok({success: false, error: Some(_exnMessage(e))}))
                    })
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
