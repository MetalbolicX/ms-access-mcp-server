open Test
open Bindings.Odbc

// Task 3.3/3.4 — OdbcAdapter DDL operations
// REQ-S6/S7/S8/S9 — wiring pure SqlBuilder DDL into OdbcAdapter

module FakeConnectionDdl = {
  let executedSql: ref<array<string>> = ref([])
  let failOnSql: ref<option<string>> = ref(None)
  let reset = () => { executedSql.contents = []; failOnSql.contents = None }
  let query = (sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> => {
    executedSql.contents = Belt.Array.concat(executedSql.contents, [sql])
    switch failOnSql.contents {
    | Some(pattern) if String.includes(sql, pattern) => Promise.resolve(Error(Errors.databaseError("Driver error")))
    | _ => Promise.resolve(Ok({rows: [], columns: [], count: 0, statement: Some(sql)}))
    }
  }
  let tables: (~catalog: option<string>=?, ~schema: option<string>=?, ~table: option<string>=?, ~tableType: option<string>=?) => Promise.t<result<array<oDBcRow>, Errors.t>> = (~catalog=?, ~schema=?, ~table=?, ~tableType=?) => Promise.resolve(Ok([]))
  let columns: (~catalog: option<string>=?, ~schema: option<string>=?, ~table: option<string>=?, ~column: option<string>=?) => Promise.t<result<array<oDBcRow>, Errors.t>> = (~catalog=?, ~schema=?, ~table=?, ~column=?) => Promise.resolve(Ok([]))
  let close = (): Promise.t<unit> => Promise.resolve()
}

let makeAdapterDdl = (): OdbcAdapter.t => {
  let conn: Bindings.Odbc.connection = {
    query: FakeConnectionDdl.query,
    tables: FakeConnectionDdl.tables,
    columns: FakeConnectionDdl.columns,
    close: FakeConnectionDdl.close,
  }
  { connection: Some(conn), dbPath: None }
}

// ---------------------------------------------------------------------------
// Sync SQL-capture assertions (FakeConnectionDdl.executedSql)
// ---------------------------------------------------------------------------

test("DDL sync: createTable, deleteTable, alterTable (add/drop/modify), createQuery, deleteQuery each capture SQL", () => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let col = (~name: string, ~st: string, ~sz: option<int>, ~null: bool): Interfaces.columnSchema =>
    { name: name, sourceType: st, maxLength: sz, allowNull: null, isAutoincrement: false, defaultValue: None }
  let dict = (act: string, n: string, ctOpt: option<string>, szOpt: option<float>, nu: bool): dict<JSON.t> => {
    let d = dict{}
    let _ = Dict.set(d, "action", JSON.String(act))
    let _ = Dict.set(d, "name", JSON.String(n))
    let _ = switch ctOpt { | Some(t) => Dict.set(d, "colType", JSON.String(t)) | None => () }
    let _ = switch szOpt { | Some(v) => Dict.set(d, "size", JSON.Number(v)) | None => () }
    let _ = Dict.set(d, "nullable", JSON.Boolean(nu))
    d
  }
  let eq = (expected: string) => {
    let actual = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) {
      | Some(s) => s | None => ""
    }
    if actual != expected { raise(Invalid_argument("Expected: " ++ expected ++ ", Got: " ++ actual)) }
  }
  let _ = OdbcAdapter.createTable(adapter, "Customers", [col(~name="ID", ~st="Long Integer", ~sz=None, ~null=false), col(~name="Name", ~st="Text", ~sz=Some(100), ~null=true)])
  eq("CREATE TABLE [Customers] ([ID] INT NOT NULL, [Name] VARCHAR(100) NULL)")
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.deleteTable(adapter, "Orders")
  eq("DROP TABLE [Orders]")
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.alterTable(adapter, "Users", [dict("add_column", "Email", Some("Text"), Some(100.0), true)])
  eq("ALTER TABLE [Users] ADD COLUMN [Email] VARCHAR(100) NULL")
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.alterTable(adapter, "Users", [dict("drop_column", "Email", None, None, true)])
  eq("ALTER TABLE [Users] DROP COLUMN [Email]")
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.alterTable(adapter, "Users", [dict("modify_column", "Email", Some("Text"), Some(255.0), false)])
  eq("ALTER TABLE [Users] ALTER COLUMN [Email] VARCHAR(255) NOT NULL")
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.createQuery(adapter, "qryActive", "SELECT * FROM Orders WHERE Status = 1")
  eq("CREATE VIEW [qryActive] AS SELECT * FROM Orders WHERE Status = 1")
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.deleteQuery(adapter, "qryOld")
  eq("DROP VIEW [qryOld]")
})

// ---------------------------------------------------------------------------
// Async assertions (assertion + cb pattern from OdbcSchemaReaderTest)
// ---------------------------------------------------------------------------

testAsync("DDL async success: createTable returns Ok(success=true)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let cols: array<Interfaces.columnSchema> = [{ name: "ID", sourceType: "Long Integer", maxLength: None, allowNull: false, isAutoincrement: false, defaultValue: None }]
  ignore(OdbcAdapter.createTable(adapter, "Orders", cols)
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: deleteTable returns Ok(success=true)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.deleteTable(adapter, "X")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: createQuery returns Ok(success=true)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.createQuery(adapter, "qryTest", "SELECT ID FROM T")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: deleteQuery returns Ok(success=true)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.deleteQuery(adapter, "qryX")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: setQuerySql returns Ok(success=true) when both succeed", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.setQuerySql(adapter, "qryX", "SELECT 1")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: createTable returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("Customers")
  let adapter = makeAdapterDdl()
  let cols: array<Interfaces.columnSchema> = [{ name: "ID", sourceType: "Long Integer", maxLength: None, allowNull: false, isAutoincrement: false, defaultValue: None }]
  ignore(OdbcAdapter.createTable(adapter, "Customers", cols)
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: deleteTable returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("X")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.deleteTable(adapter, "X")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: alterTable AddColumn returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("ADD")
  let adapter = makeAdapterDdl()
  let col: dict<JSON.t> = dict{ "action": JSON.String("add_column"), "name": JSON.String("X"), "colType": JSON.String("Text"), "size": JSON.Number(50.0), "nullable": JSON.Boolean(true) }
  ignore(OdbcAdapter.alterTable(adapter, "T", [col])
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: alterTable RenameTable returns Error(ODBC unsupported)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let action: dict<JSON.t> = dict{ "action": JSON.String("rename_table"), "name": JSON.String("OldName") }
  ignore(OdbcAdapter.alterTable(adapter, "OldName", [action])
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "rename_table is not supported via ODBC"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: alterTable RenameColumn returns Error(ODBC unsupported)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let action: dict<JSON.t> = dict{ "action": JSON.String("rename_column"), "name": JSON.String("OldCol") }
  ignore(OdbcAdapter.alterTable(adapter, "T", [action])
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "rename_column is not supported via ODBC"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: createQuery returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("VIEW")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.createQuery(adapter, "qryX", "SELECT 1")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: deleteQuery returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("VIEW")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.deleteQuery(adapter, "qryX")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("setQuerySql: executes DROP VIEW then CREATE VIEW in order", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.setQuerySql(adapter, "qryOrders", "SELECT ID FROM Orders")
    ->Promise.then(_result => {
      let sqls = FakeConnectionDdl.executedSql.contents
      let sql0 = switch Belt.Array.get(sqls, 0) { | Some(s) => s | None => "" }
      let sql1 = switch Belt.Array.get(sqls, 1) { | Some(s) => s | None => "" }
      assertion(~operator="equal", (a, b) => a == b, sql0, "DROP VIEW [qryOrders]")
      assertion(~operator="equal", (a, b) => a == b, sql1, "CREATE VIEW [qryOrders] AS SELECT ID FROM Orders")
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=2, ())
      Promise.resolve()
    }))
})

testAsync("setQuerySql: returns Error(Driver error) when DROP VIEW fails (first failure)", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("DROP")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.setQuerySql(adapter, "qryX", "SELECT 1")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("setQuerySql: returns Error(Driver error) when CREATE VIEW fails (second failure)", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("CREATE")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.setQuerySql(adapter, "qryX", "SELECT 1")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Driver error"), true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("getIndexes: returns Ok([]) when connected (contract)", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.getIndexes(adapter, "Orders")
    ->Promise.then(result => {
      switch result {
      | Ok(indexes) => assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(indexes), 0)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("getIndexes: returns Ok([]) when disconnected (contract)", cb => {
  let adapter: OdbcAdapter.t = { connection: None, dbPath: None }
  ignore(OdbcAdapter.getIndexes(adapter, "Orders")
    ->Promise.then(result => {
      switch result {
      | Ok(indexes) => assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(indexes), 0)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

