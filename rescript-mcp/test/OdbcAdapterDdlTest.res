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

test("DDL sync: createTable, deleteTable, alterTable (add/drop/modify) each capture real SqlBuilder output", () => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  // columnSchema from adapter → SqlBuilder.columnInfo for SqlBuilder calls
  let col = (~name: string, ~st: string, ~sz: option<int>, ~null: bool): Interfaces.columnSchema =>
    { name: name, sourceType: st, maxLength: sz, allowNull: null, isAutoincrement: false, defaultValue: None }
  let colInfo = (~name: string, ~ct: string, ~sz: int, ~null: bool): SqlBuilder.columnInfo =>
    { name: name, colType: ct, size: sz, nullable: null }
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
  // createTable — assert captured SQL matches SqlBuilder.createTable output
  let cols = [col(~name="ID", ~st="Long Integer", ~sz=None, ~null=false), col(~name="Name", ~st="Text", ~sz=Some(100), ~null=true)]
  let _ = OdbcAdapter.createTable(adapter, "Customers", cols)
  eq(SqlBuilder.createTable("Customers", [colInfo(~name="ID", ~ct="Long Integer", ~sz=0, ~null=false), colInfo(~name="Name", ~ct="Text", ~sz=100, ~null=true)]))
  // deleteTable — assert captured SQL matches SqlBuilder.dropTable output
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.deleteTable(adapter, "Orders")
  eq(SqlBuilder.dropTable("Orders"))
  // alterTable AddColumn — assert captured SQL matches SqlBuilder.alterTable output
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.alterTable(adapter, "Users", [dict("add_column", "Email", Some("Text"), Some(100.0), true)])
  eq(SqlBuilder.alterTable("Users", SqlBuilder.AddColumn(colInfo(~name="Email", ~ct="Text", ~sz=100, ~null=true)))->Option.getOr(""))
  // alterTable DropColumn
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.alterTable(adapter, "Users", [dict("drop_column", "Email", None, None, true)])
  eq(SqlBuilder.alterTable("Users", SqlBuilder.DropColumn("Email"))->Option.getOr(""))
  // alterTable ModifyColumn
  FakeConnectionDdl.reset()
  let _ = OdbcAdapter.alterTable(adapter, "Users", [dict("modify_column", "Email", Some("Text"), Some(255.0), false)])
  eq(SqlBuilder.alterTable("Users", SqlBuilder.ModifyColumn(colInfo(~name="Email", ~ct="Text", ~sz=255, ~null=false)))->Option.getOr(""))
})

// ---------------------------------------------------------------------------
// Async assertions (assertion + cb pattern from OdbcSchemaReaderTest)
// ---------------------------------------------------------------------------

testAsync("DDL async success: createTable captures SQL matching SqlBuilder.createTable", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let cols: array<Interfaces.columnSchema> = [{ name: "ID", sourceType: "Long Integer", maxLength: None, allowNull: false, isAutoincrement: false, defaultValue: None }]
  let colInfo: SqlBuilder.columnInfo = { name: "ID", colType: "Long Integer", size: 0, nullable: false }
  let expectedSql = SqlBuilder.createTable("Orders", [colInfo])
  ignore(OdbcAdapter.createTable(adapter, "Orders", cols)
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: deleteTable captures SQL matching SqlBuilder.dropTable", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.dropTable("X")
  ignore(OdbcAdapter.deleteTable(adapter, "X")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: alterTable AddColumn captures SQL matching SqlBuilder.alterTable", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let colDict: dict<JSON.t> = dict{ "action": JSON.String("add_column"), "name": JSON.String("Email"), "colType": JSON.String("Text"), "size": JSON.Number(100.0), "nullable": JSON.Boolean(true) }
  let colInfo: SqlBuilder.columnInfo = { name: "Email", colType: "Text", size: 100, nullable: true }
  let expectedSql = SqlBuilder.alterTable("Users", SqlBuilder.AddColumn(colInfo))->Option.getOr("")
  ignore(OdbcAdapter.alterTable(adapter, "Users", [colDict])
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: createQuery captures SQL matching SqlBuilder.createView", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.createView(~name="qryTest", ~sql="SELECT ID FROM T")
  ignore(OdbcAdapter.createQuery(adapter, "qryTest", "SELECT ID FROM T")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: deleteQuery captures SQL matching SqlBuilder.dropView", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.dropView(~name="qryX")
  ignore(OdbcAdapter.deleteQuery(adapter, "qryX")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: setQuerySql captures [dropSql, createSql] in order", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let dropSql = SqlBuilder.dropView(~name="qryX")
  let createSql = SqlBuilder.createView(~name="qryX", ~sql="SELECT 1")
  ignore(OdbcAdapter.setQuerySql(adapter, "qryX", "SELECT 1")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let sqls = FakeConnectionDdl.executedSql.contents
          let captured0 = switch Belt.Array.get(sqls, 0) { | Some(s) => s | None => "" }
          let captured1 = switch Belt.Array.get(sqls, 1) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured0, dropSql)
          assertion(~operator="equal", (a, b) => a == b, captured1, createSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=3, ())
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

testAsync("setQuerySql: executes DROP VIEW then CREATE VIEW in order via SqlBuilder", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let dropSql = SqlBuilder.dropView(~name="qryOrders")
  let createSql = SqlBuilder.createView(~name="qryOrders", ~sql="SELECT ID FROM Orders")
  ignore(OdbcAdapter.setQuerySql(adapter, "qryOrders", "SELECT ID FROM Orders")
    ->Promise.then(_result => {
      let sqls = FakeConnectionDdl.executedSql.contents
      let captured0 = switch Belt.Array.get(sqls, 0) { | Some(s) => s | None => "" }
      let captured1 = switch Belt.Array.get(sqls, 1) { | Some(s) => s | None => "" }
      assertion(~operator="equal", (a, b) => a == b, captured0, dropSql)
      assertion(~operator="equal", (a, b) => a == b, captured1, createSql)
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

// ---------------------------------------------------------------------------
// Index DDL tests — SqlBuilder.createIndex / dropIndex assertions
// ---------------------------------------------------------------------------

testAsync("DDL async success: createIndex basic captures SQL matching SqlBuilder.createIndex", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.createIndex(~name="idxOrderID", ~table="Orders", ~columns=["OrderID"], ~unique=false)
  ignore(OdbcAdapter.createIndex(adapter, "idxOrderID", "Orders", ["OrderID"])
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: createIndex UNIQUE captures SQL matching SqlBuilder.createIndex", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.createIndex(~name="uidxCode", ~table="Products", ~columns=["Code"], ~unique=true)
  ignore(OdbcAdapter.createIndex(adapter, "uidxCode", "Products", ["Code"], ~unique=true)
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: createIndex UNIQUE+IGNORE NULL captures SQL with WITH IGNORE NULL", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.createIndex(~name="uidxCode", ~table="Products", ~columns=["Code"], ~unique=true, ~ignore_nulls=true)
  ignore(OdbcAdapter.createIndex(adapter, "uidxCode", "Products", ["Code"], ~unique=true, ~ignoreNulls=true)
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: createIndex ignoreNulls without UNIQUE omits WITH IGNORE NULL", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  // ignoreNulls=true but unique=false → no WITH IGNORE NULL
  let expectedSql = SqlBuilder.createIndex(~name="idxCode", ~table="Products", ~columns=["Code"], ~unique=false, ~ignore_nulls=true)
  ignore(OdbcAdapter.createIndex(adapter, "idxCode", "Products", ["Code"], ~unique=false, ~ignoreNulls=true)
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL async success: dropIndex captures SQL matching SqlBuilder.dropIndex", cb => {
  FakeConnectionDdl.reset()
  let adapter = makeAdapterDdl()
  let expectedSql = SqlBuilder.dropIndex(~name="idxOrderID", ~table="Orders")
  ignore(OdbcAdapter.dropIndex(adapter, "idxOrderID", "Orders")
    ->Promise.then(result => {
      switch result {
      | Ok(ddl) => {
          assertion(~operator="equal", (a, b) => a == b, ddl.success, true)
          let captured = switch Belt.Array.get(FakeConnectionDdl.executedSql.contents, 0) { | Some(s) => s | None => "" }
          assertion(~operator="equal", (a, b) => a == b, captured, expectedSql)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("DDL error: createIndex returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("INDEX")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.createIndex(adapter, "idxX", "T", ["Col"])
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

testAsync("DDL error: dropIndex returns Error(Driver error) when fake fails", cb => {
  FakeConnectionDdl.reset()
  FakeConnectionDdl.failOnSql.contents = Some("DROP")
  let adapter = makeAdapterDdl()
  ignore(OdbcAdapter.dropIndex(adapter, "idxX", "T")
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

