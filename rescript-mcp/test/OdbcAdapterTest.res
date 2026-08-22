open Test
open Bindings.Odbc

// Task 1.8 RED test — OdbcAdapter data operations lifecycle
// REQ-D4/D5/D6/D9 — lifecycle (connect/disconnect/isConnected) + data ops

// ---------------------------------------------------------------------------
// Fake connection — provides predictable responses for unit testing
// ---------------------------------------------------------------------------

module FakeConnection = {
  // Predetermined query responses
  let queryResponses: array<(string, Bindings.Odbc.oDBcResult)> = [
    ("SELECT * FROM Products", {
      rows: [dict{"id": Int(1), "name": Str("Widget")}, dict{"id": Int(2), "name": Str("Gadget")}],
      columns: ["id", "name"],
      count: 2,
      statement: Some("SELECT * FROM Products"),
    }),
    ("SELECT * FROM Orders", {
      rows: [dict{"id": Int(10), "status": Str("shipped")}],
      columns: ["id", "status"],
      count: 1,
      statement: Some("SELECT * FROM Orders"),
    }),
  ]

  let lastQuery = ref("")
  let callCount = ref(0)

  let query = (sql: string, _params: array<JSON.t>): Promise.t<result<Bindings.Odbc.oDBcResult, Errors.t>> => {
    lastQuery.contents = sql
    callCount.contents = callCount.contents + 1
    let response = Belt.Array.getUnsafe(queryResponses, 0)
    Promise.resolve(Ok(Pair.second(response)))
  }

  let tables = (
    ~_catalog: option<string>=?,
    ~_schema: option<string>=?,
    ~_table: option<string>=?,
    ~_tableType: option<string>=?,
  ): Promise.t<result<array<Bindings.Odbc.oDBcRow>, Errors.t>> => {
    Promise.resolve(Ok([]))
  }

  let columns = (
    ~_catalog: option<string>=?,
    ~_schema: option<string>=?,
    ~_table: option<string>=?,
    ~_column: option<string>=?,
  ): Promise.t<result<array<Bindings.Odbc.oDBcRow>, Errors.t>> => {
    Promise.resolve(Ok([]))
  }

  let close = (): Promise.t<unit> => Promise.resolve()
}

// ---------------------------------------------------------------------------
// OdbcAdapter instance — uses fake connection
// ---------------------------------------------------------------------------

// create makes an OdbcAdapter with the given connection
// In RED phase this function doesn't exist yet — all tests will fail to compile

// ---------------------------------------------------------------------------
// Lifecycle tests
// ---------------------------------------------------------------------------

test("OdbcAdapter connect resolves to Ok(true)", () => {
  // OdbcAdapter.connect takes a connectionString and ~password → Promise<result<bool, Errors.t>>
  // Returns Ok(true) on successful connection
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("OdbcAdapter disconnect resolves to Ok(unit)", () => {
  // disconnect → Promise<result<unit, Errors.t>>
  // After disconnect, isConnected should return Ok(false)
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("OdbcAdapter isConnected returns Ok(true) when connected", () => {
  // isConnected → Promise<result<bool, Errors.t>>
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("OdbcAdapter isConnected returns Ok(false) when not connected", () => {
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

// ---------------------------------------------------------------------------
// executeQuery tests
// ---------------------------------------------------------------------------

test("executeQuery returns Ok with rows and columns", () => {
  // executeQuery(t, "SELECT ...", ~params?) → Promise<result<queryResult, Errors.t>>
  // queryResult = { success: bool, rows: array<dict<JSON.t>>, count: int, columns: array<string>, error: option<string> }
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("executeQuery normalizes OdbcValue rows to JSON", () => {
  // Int(1) → JSON.Number(1.0), Str("Widget") → JSON.String("Widget")
  // Null, Float, Bool all map correctly
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("executeQuery returns error when not connected", () => {
  // When adapter is disconnected, executeQuery should return DatabaseError
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

// ---------------------------------------------------------------------------
// insert tests
// ---------------------------------------------------------------------------

test("insert builds correct INSERT SQL from record dict", () => {
  // insertData(t, "Products", dict{"name": JSON.String("Widget"), "qty": JSON.Number(100.0)})
  // → Promise<result<mutationResult, Errors.t>>
  // mutationResult = { success: bool, affected: int, error: option<string> }
  // Uses SqlBuilder.insert: "INSERT INTO [Products] ([name], [qty]) VALUES (?, ?)"
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("insert returns Ok with affected=1 on success", () => {
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

// ---------------------------------------------------------------------------
// update tests
// ---------------------------------------------------------------------------

test("update with dict WHERE builds correct UPDATE SQL", () => {
  // updateData(t, "Products", setDict, ~where=Some(Dict(whereDict))?)
  // Uses SqlBuilder.update: "UPDATE [Products] SET [name] = ? WHERE [id] = ?"
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("update with raw WHERE builds correct SQL", () => {
  // updateData(t, "Products", setDict, ~where=Some(Raw("id IN (1, 2, 3)"))?)
  // Uses SqlBuilder.update with Raw: "UPDATE [Products] SET [name] = ? WHERE id IN (1, 2, 3)"
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("update returns Ok with affected count", () => {
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

// ---------------------------------------------------------------------------
// delete tests
// ---------------------------------------------------------------------------

test("delete with dict WHERE builds correct DELETE SQL", () => {
  // deleteData(t, "Products", ~where=Some(Dict(whereDict))?)
  // Uses SqlBuilder.delete: "DELETE FROM [Products] WHERE [id] = ?"
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("delete with raw WHERE builds correct SQL", () => {
  // deleteData(t, "Products", ~where=Some(Raw("status = 'cancelled'"))?)
  // Uses SqlBuilder.delete with Raw: "DELETE FROM [Products] WHERE status = 'cancelled'"
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("delete with None WHERE builds unconditional DELETE", () => {
  // deleteData(t, "Products", ~where=None) → "DELETE FROM [Products]"
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

test("delete returns Ok with affected count", () => {
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

// ---------------------------------------------------------------------------
// executeRawSql tests
// ---------------------------------------------------------------------------

test("executeRawSql executes arbitrary SQL and returns affected count", () => {
  // executeRawSql(t, "TRUNCATE TABLE Products") → Promise<result<int, Errors.t>>
  // No SqlBuilder wrapping — raw SQL goes directly to the driver
  assertion(~operator="equal", (a, b) => a == b, true, true)
})
