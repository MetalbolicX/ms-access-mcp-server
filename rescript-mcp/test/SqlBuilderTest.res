open Test
open Adapters.SqlBuilder

// Task 1.6 RED test — SqlBuilder pure SQL/param builders
// REQ-D4/D5/D6/D9 — bracket quoting, param placeholders, WHERE builders, CRUD SQL

// ---------------------------------------------------------------------------
// bracket — wraps identifier in square brackets, escapes embedded ]
// ---------------------------------------------------------------------------

test("bracket wraps plain identifier", () => {
  let result = bracket("Orders")
  assertion(~operator="equal", (a, b) => a == b, result, "[Orders]")
})

test("bracket escapes embedded ]", () => {
  let result = bracket("Table[1]")
  assertion(~operator="equal", (a, b) => a == b, result, "[Table[1]]]")
})

test("bracket round-trips double-embedded ]", () => {
  let result = bracket("a]]b")
  assertion(~operator="equal", (a, b) => a == b, result, "[a]]]]b]")
})

test("bracket empty string", () => {
  let result = bracket("")
  assertion(~operator="equal", (a, b) => a == b, result, "[]")
})

// ---------------------------------------------------------------------------
// paramPlaceholders — generates (?, ?, ...) for INSERT VALUES
// ---------------------------------------------------------------------------

test("paramPlaceholders 0 returns empty parens", () => {
  let result = paramPlaceholders(0)
  assertion(~operator="equal", (a, b) => a == b, result, "()")
})

test("paramPlaceholders 1 returns single placeholder", () => {
  let result = paramPlaceholders(1)
  assertion(~operator="equal", (a, b) => a == b, result, "(?)")
})

test("paramPlaceholders 3 returns three placeholders", () => {
  let result = paramPlaceholders(3)
  assertion(~operator="equal", (a, b) => a == b, result, "(?, ?, ?)")
})

test("paramPlaceholders 5 returns five placeholders", () => {
  let result = paramPlaceholders(5)
  assertion(~operator="equal", (a, b) => a == b, result, "(?, ?, ?, ?, ?)")
})

// ---------------------------------------------------------------------------
// whereFromDict — dict conditions to WHERE + ordered params
// ---------------------------------------------------------------------------

test("whereFromDict single condition", () => {
  let dict: dict<JSON.t> = dict{"id": JSON.Number(42.0)}
  let (sql, params) = whereFromDict(dict)
  assertion(~operator="equal", (a, b) => a == b, sql, "[id] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Number(42.0)])
})

test("whereFromDict two conditions ANDed in insertion order", () => {
  let dict: dict<JSON.t> = dict{"name": JSON.String("x"), "status": JSON.String("active")}
  let (sql, params) = whereFromDict(dict)
  assertion(~operator="equal", (a, b) => a == b, sql, "[name] = ? AND [status] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.String("x"), JSON.String("active")])
})

test("whereFromDict three conditions", () => {
  let dict: dict<JSON.t> = dict{"a": JSON.Number(1.0), "b": JSON.Number(2.0), "c": JSON.Number(3.0)}
  let (sql, params) = whereFromDict(dict)
  assertion(~operator="equal", (a, b) => a == b, sql, "[a] = ? AND [b] = ? AND [c] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Number(1.0), JSON.Number(2.0), JSON.Number(3.0)])
})

test("whereFromDict empty dict returns empty string and empty params", () => {
  let dict: dict<JSON.t> = dict{}
  let (sql, params) = whereFromDict(dict)
  assertion(~operator="equal", (a, b) => a == b, sql, "")
  assertion(~operator="equal", (a, b) => a == b, params, [])
})

test("whereFromDict boolean param", () => {
  let dict: dict<JSON.t> = dict{"active": JSON.Number(1.0)}
  let (_sql, params) = whereFromDict(dict)
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Number(1.0)])
})

test("whereFromDict null param", () => {
  let dict: dict<JSON.t> = dict{"val": JSON.Null}
  let (_sql, params) = whereFromDict(dict)
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Null])
})

// ---------------------------------------------------------------------------
// whereFromRaw — whitelist validation + merge with dict
// ---------------------------------------------------------------------------

test("whereFromRaw accepts simple column condition", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("id = 1", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE id = 1")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw accepts IN clause", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("id IN (1, 2, 3)", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE id IN (1, 2, 3)")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw accepts OR condition", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("name = 'x' OR status = 'y'", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE name = 'x' OR status = 'y'")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw accepts parenthesized expression", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("(a = 1 AND b = 2)", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE (a = 1 AND b = 2)")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw accepts LIKE pattern", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("name LIKE 'John%'", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE name LIKE 'John%'")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw accepts dot notation (table.column)", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("Orders.CustomerID = 5", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE Orders.CustomerID = 5")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw accepts empty dict and bare condition", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("id > 10", dict)
  switch result {
  | Ok(sql) => assertion(~operator="equal", (a, b) => a == b, sql, "WHERE id > 10")
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw merges raw with dict conditions using AND", () => {
  let dict: dict<JSON.t> = dict{"status": JSON.String("active")}
  let result = whereFromRaw("id > 10", dict)
  switch result {
  | Ok(sql) => {
      // raw appended after dict conditions
      assertion(~operator="equal", (a, b) => a == b, String.includes(sql, "status"), true)
      assertion(~operator="equal", (a, b) => a == b, String.includes(sql, "id > 10"), true)
    }
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("whereFromRaw REJECTS semicolon (SQL injection attempt)", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("id = 1; DROP TABLE Users", dict)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(err) => {
      let d = Errors.toDict(err)
      assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "disallowed"), true)
    }
  }
})

test("whereFromRaw REJECTS double-dash comment", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("id = 1 -- comment", dict)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(err) => {
      let d = Errors.toDict(err)
      assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "disallowed"), true)
    }
  }
})

test("whereFromRaw REJECTS block comment", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("id = 1 /* comment */", dict)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(err) => {
      let d = Errors.toDict(err)
      assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "disallowed"), true)
    }
  }
})

test("whereFromRaw REJECTS backtick", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("`id` = 1", dict)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(err) => {
      let d = Errors.toDict(err)
      assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "disallowed"), true)
    }
  }
})

test("whereFromRaw REJECTS backslash", () => {
  let dict: dict<JSON.t> = dict{}
  let result = whereFromRaw("name = 'o\\'reilly'", dict)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(err) => {
      let d = Errors.toDict(err)
      assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "disallowed"), true)
    }
  }
})

// ---------------------------------------------------------------------------
// insert — INSERT INTO [table] (cols) VALUES (?, ?, ...)
// ---------------------------------------------------------------------------

test("insert single column", () => {
  let record: dict<JSON.t> = dict{"name": JSON.String("Widget")}
  let (sql, params) = insert("Products", record)
  assertion(~operator="equal", (a, b) => a == b, sql, "INSERT INTO [Products] ([name]) VALUES (?)")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.String("Widget")])
})

test("insert multiple columns in insertion order", () => {
  let record: dict<JSON.t> = dict{
    "id": JSON.Number(1.0),
    "name": JSON.String("Test"),
    "qty": JSON.Number(100.0),
  }
  let (sql, params) = insert("Orders", record)
  assertion(~operator="equal", (a, b) => a == b, sql, "INSERT INTO [Orders] ([id], [name], [qty]) VALUES (?, ?, ?)")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Number(1.0), JSON.String("Test"), JSON.Number(100.0)])
})

test("insert empty record", () => {
  let record: dict<JSON.t> = dict{}
  let (sql, params) = insert("EmptyTable", record)
  assertion(~operator="equal", (a, b) => a == b, sql, "INSERT INTO [EmptyTable] () VALUES ()")
  assertion(~operator="equal", (a, b) => a == b, params, [])
})

test("insert column with bracket in name", () => {
  let record: dict<JSON.t> = dict{"col[1]": JSON.Number(5.0)}
  let (sql, params) = insert("Test", record)
  assertion(~operator="equal", (a, b) => a == b, sql, "INSERT INTO [Test] ([col[1]]]) VALUES (?)")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Number(5.0)])
})

// ---------------------------------------------------------------------------
// update — UPDATE [table] SET col = ?, ... WHERE ...
// ---------------------------------------------------------------------------

test("update single set", () => {
  let setDict: dict<JSON.t> = dict{"name": JSON.String("NewName")}
  let (sql, params) = update("Products", setDict, None)
  assertion(~operator="equal", (a, b) => a == b, sql, "UPDATE [Products] SET [name] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.String("NewName")])
})

test("update multiple set columns", () => {
  let setDict: dict<JSON.t> = dict{
    "name": JSON.String("Updated"),
    "qty": JSON.Number(50.0),
  }
  let (sql, params) = update("Products", setDict, None)
  assertion(~operator="equal", (a, b) => a == b, sql, "UPDATE [Products] SET [name] = ?, [qty] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.String("Updated"), JSON.Number(50.0)])
})

test("update with dict WHERE clause", () => {
  let setDict: dict<JSON.t> = dict{"status": JSON.String("shipped")}
  let whereDict: dict<JSON.t> = dict{"id": JSON.Number(7.0)}
  let (sql, params) = update("Orders", setDict, Some(Dict(whereDict)))
  assertion(~operator="equal", (a, b) => a == b, sql, "UPDATE [Orders] SET [status] = ? WHERE [id] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.String("shipped"), JSON.Number(7.0)])
})

test("update with raw WHERE clause", () => {
  let setDict: dict<JSON.t> = dict{"status": JSON.String("shipped")}
  let (sql, params) = update("Orders", setDict, Some(Raw("id IN (1, 2, 3)")))
  assertion(~operator="equal", (a, b) => a == b, sql, "UPDATE [Orders] SET [status] = ? WHERE id IN (1, 2, 3)")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.String("shipped")])
})

test("update with raw WHERE and additional dict conditions", () => {
  let setDict: dict<JSON.t> = dict{"active": JSON.Number(1.0)}
  let (sql, _params) = update("Users", setDict, Some(Raw("role = 'admin'")))
  // dict conditions come first, then raw
  assertion(~operator="equal", (a, b) => a == b, String.includes(sql, "[active]"), true)
  assertion(~operator="equal", (a, b) => a == b, String.includes(sql, "role = 'admin'"), true)
})

test("update with bracket-quoted column in SET", () => {
  let setDict: dict<JSON.t> = dict{"col[1]": JSON.Number(10.0)}
  let (sql, _params) = update("Test", setDict, None)
  assertion(~operator="equal", (a, b) => a == b, sql, "UPDATE [Test] SET [col[1]]] = ?")
})

// ---------------------------------------------------------------------------
// delete — DELETE FROM [table] WHERE ...
// ---------------------------------------------------------------------------

test("delete with dict WHERE", () => {
  let whereDict: dict<JSON.t> = dict{"id": JSON.Number(5.0)}
  let (sql, params) = delete("Orders", Some(Dict(whereDict)))
  assertion(~operator="equal", (a, b) => a == b, sql, "DELETE FROM [Orders] WHERE [id] = ?")
  assertion(~operator="equal", (a, b) => a == b, params, [JSON.Number(5.0)])
})

test("delete with raw WHERE", () => {
  let (sql, params) = delete("Orders", Some(Raw("status = 'cancelled'")))
  assertion(~operator="equal", (a, b) => a == b, sql, "DELETE FROM [Orders] WHERE status = 'cancelled'")
  assertion(~operator="equal", (a, b) => a == b, params, [])
})

test("delete with None WHERE — unconditional (D9 parity)", () => {
  let (sql, params) = delete("Orders", None)
  assertion(~operator="equal", (a, b) => a == b, sql, "DELETE FROM [Orders]")
  assertion(~operator="equal", (a, b) => a == b, params, [])
})

test("delete with None WHERE — no WHERE keyword at all", () => {
  let (sql, _params) = delete("LargeTable", None)
  // Must NOT contain "WHERE" — unconditional delete per D9
  assertion(~operator="equal", (a, b) => a == b, String.includes(sql, "WHERE"), false)
})

test("delete with complex raw WHERE", () => {
  let (sql, params) = delete("Orders", Some(Raw("(status = 'pending' AND qty > 0) OR priority = 1")))
  assertion(~operator="equal", (a, b) => a == b, sql, "DELETE FROM [Orders] WHERE (status = 'pending' AND qty > 0) OR priority = 1")
  assertion(~operator="equal", (a, b) => a == b, params, [])
})
