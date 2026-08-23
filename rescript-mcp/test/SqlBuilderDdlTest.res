open Test
open Adapters.SqlBuilder

// Task 3.1 RED test — SqlBuilder DDL pure builders
// REQ-S7 (Table DDL & type map) + REQ-S8 (alter_table)

// ---------------------------------------------------------------------------
// ODBC_TYPE_MAP — Access → ODBC type name mapping (REQ-S7)
// All cases: known mappings, case-insensitivity, empty, unknown default
// ---------------------------------------------------------------------------

test("ODBC_TYPE_MAP all known types", () => {
  let cases: array<(string, string)> = [
    ("TEXT", "VARCHAR"), ("VARCHAR", "VARCHAR"), ("CHAR", "VARCHAR"),
    ("Long Integer", "INT"), ("INTEGER", "INT"), ("Integer", "SMALLINT"),
    ("SMALLINT", "SMALLINT"), ("TINYINT", "TINYINT"),
    ("BIT", "BIT"), ("Boolean", "BIT"),
    ("Date/Time", "DATETIME"), ("DATETIME", "DATETIME"), ("DATE", "DATETIME"),
    ("TIME", "DATETIME"), ("TIMESTAMP", "DATETIME"),
    ("DECIMAL", "DECIMAL"), ("NUMERIC", "DECIMAL"),
    ("MONEY", "MONEY"), ("CURRENCY", "MONEY"),
    ("FLOAT", "FLOAT"), ("DOUBLE", "FLOAT"),
    ("REAL", "REAL"), ("Single", "REAL"),
    ("BINARY", "VARBINARY"), ("VARBINARY", "VARBINARY"), ("IMAGE", "VARBINARY"),
    ("GUID", "GUID"), ("MEMO", "TEXT"),
    ("text", "VARCHAR"), ("varchar", "VARCHAR"), ("long integer", "INT"),
    ("boolean", "BIT"), ("single", "REAL"),
  ]
  Belt.Array.forEach(cases, ((input, expected)) => {
    let result = odbcTypeMap(input)
    assertion(~operator="equal", (a, b) => a == b, result, expected)
  })
})

test("ODBC_TYPE_MAP empty string", () => {
  assertion(~operator="equal", (a, b) => a == b, odbcTypeMap(""), "")
})

test("ODBC_TYPE_MAP unknown types default to VARCHAR", () => {
  Belt.Array.forEach(["Hyperlink", "Custom", "Foo"], input =>
    assertion(~operator="equal", (a, b) => a == b, odbcTypeMap(input), "VARCHAR")
  )
})

// ---------------------------------------------------------------------------
// columnDef — single column definition (REQ-S7)
// ---------------------------------------------------------------------------

test("columnDef Text no size uses 255 default", () => {
  let col: columnInfo = {name: "Notes", colType: "Text", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Notes] VARCHAR(255) NULL")
})

test("columnDef Text with explicit size", () => {
  let col: columnInfo = {name: "City", colType: "Text", size: 50, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[City] VARCHAR(50) NULL")
})

test("columnDef Text NOT NULL", () => {
  let col: columnInfo = {name: "Email", colType: "Text", size: 100, nullable: false}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Email] VARCHAR(100) NOT NULL")
})

test("columnDef Long Integer", () => {
  let col: columnInfo = {name: "Qty", colType: "Long Integer", size: 0, nullable: false}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Qty] INT NOT NULL")
})

test("columnDef Integer (Access) maps to SMALLINT", () => {
  let col: columnInfo = {name: "Status", colType: "Integer", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Status] SMALLINT NULL")
})

test("columnDef Boolean maps to BIT", () => {
  let col: columnInfo = {name: "Active", colType: "Boolean", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Active] BIT NULL")
})

test("columnDef Date/Time maps to DATETIME", () => {
  let col: columnInfo = {name: "CreatedAt", colType: "Date/Time", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[CreatedAt] DATETIME NULL")
})

test("columnDef Currency maps to MONEY", () => {
  let col: columnInfo = {name: "Amount", colType: "Currency", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Amount] MONEY NULL")
})

test("columnDef Memo (TEXT) with no size", () => {
  let col: columnInfo = {name: "Comments", colType: "MEMO", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Comments] TEXT NULL")
})

test("columnDef Double maps to FLOAT", () => {
  let col: columnInfo = {name: "Rate", colType: "Double", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Rate] FLOAT NULL")
})

test("columnDef Single maps to REAL", () => {
  let col: columnInfo = {name: "Ratio", colType: "Single", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Ratio] REAL NULL")
})

test("columnDef Binary maps to VARBINARY", () => {
  let col: columnInfo = {name: "Data", colType: "Binary", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Data] VARBINARY NULL")
})

test("columnDef GUID maps to GUID", () => {
  let col: columnInfo = {name: "UID", colType: "GUID", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[UID] GUID NULL")
})

test("columnDef unknown type falls back to VARCHAR", () => {
  let col: columnInfo = {name: "Custom", colType: "Hyperlink", size: 0, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Custom] VARCHAR(255) NULL")
})

test("columnDef bracket-escapes embedded ]", () => {
  let col: columnInfo = {name: "Field[1]", colType: "Text", size: 50, nullable: true}
  assertion(~operator="equal", (a, b) => a == b, columnDef(col), "[Field[1]]] VARCHAR(50) NULL")
})

// ---------------------------------------------------------------------------
// createTable — CREATE TABLE [...] (...) (REQ-S7)
// ---------------------------------------------------------------------------

test("createTable single column", () => {
  let cols: array<columnInfo> = [{name: "ID", colType: "Long Integer", size: 0, nullable: false}]
  assertion(~operator="equal", (a, b) => a == b, createTable("Orders", cols), "CREATE TABLE [Orders] ([ID] INT NOT NULL)")
})

test("createTable two columns", () => {
  let cols: array<columnInfo> = [
    {name: "ID", colType: "Long Integer", size: 0, nullable: false},
    {name: "Name", colType: "Text", size: 100, nullable: true},
  ]
  let r = createTable("Products", cols)
  assertion(~operator="equal", (a, b) => a == b, String.includes(r, "[ID] INT NOT NULL"), true)
  assertion(~operator="equal", (a, b) => a == b, String.includes(r, "[Name] VARCHAR(100) NULL"), true)
})

test("createTable empty columns", () => {
  assertion(~operator="equal", (a, b) => a == b, createTable("EmptyTable", []), "CREATE TABLE [EmptyTable] ()")
})

test("createTable brackets table name with space", () => {
  let cols: array<columnInfo> = [{name: "X", colType: "Integer", size: 0, nullable: true}]
  assertion(~operator="equal", (a, b) => a == b, String.includes(createTable("My Table", cols), "[My Table]"), true)
})

// ---------------------------------------------------------------------------
// dropTable — DROP TABLE [...] (REQ-S7)
// ---------------------------------------------------------------------------

test("dropTable basic", () => {
  assertion(~operator="equal", (a, b) => a == b, dropTable("Orders"), "DROP TABLE [Orders]")
})

test("dropTable brackets name with space", () => {
  assertion(~operator="equal", (a, b) => a == b, dropTable("Legacy Table"), "DROP TABLE [Legacy Table]")
})

// ---------------------------------------------------------------------------
// alterTable — ALTER TABLE add/drop/modify column (REQ-S8)
// ---------------------------------------------------------------------------

test("alterTable add column", () => {
  let cases: array<(string, columnInfo, string)> = [
    ("Users", {name: "Email", colType: "Text", size: 100, nullable: true}, "ALTER TABLE [Users] ADD COLUMN [Email] VARCHAR(100) NULL"),
    ("People", {name: "Age", colType: "Long Integer", size: 0, nullable: false}, "ALTER TABLE [People] ADD COLUMN [Age] INT NOT NULL"),
  ]
  Belt.Array.forEach(cases, ((table, col, expected)) => {
    switch alterTable(table, AddColumn(col)) {
    | Some(sql) => assertion(~operator="equal", (a, b) => a == b, sql, expected)
    | None => assertion(~operator="equal", (a, b) => a == b, false, true)
    }
  })
})

test("alterTable drop column", () => {
  assertion(~operator="equal", (a, b) => a == b, alterTable("Users", DropColumn("Email")), Some("ALTER TABLE [Users] DROP COLUMN [Email]"))
})

test("alterTable modify column", () => {
  let cases: array<(string, columnInfo, string)> = [
    ("Users", {name: "Email", colType: "Text", size: 255, nullable: false}, "ALTER TABLE [Users] ALTER COLUMN [Email] VARCHAR(255) NOT NULL"),
    ("Orders", {name: "Qty", colType: "Long Integer", size: 0, nullable: false}, "ALTER TABLE [Orders] ALTER COLUMN [Qty] INT NOT NULL"),
  ]
  Belt.Array.forEach(cases, ((table, col, expected)) => {
    switch alterTable(table, ModifyColumn(col)) {
    | Some(sql) => assertion(~operator="equal", (a, b) => a == b, sql, expected)
    | None => assertion(~operator="equal", (a, b) => a == b, false, true)
    }
  })
})

test("alterTable rename table returns None (ODBC unsupported)", () => {
  assertion(~operator="equal", (a, b) => a == b, alterTable("OldName", RenameTable("NewName")), None)
})

test("alterTable rename column returns None (ODBC unsupported)", () => {
  assertion(~operator="equal", (a, b) => a == b, alterTable("Orders", RenameColumn("OldCol", "NewCol")), None)
})

test("alterTable add column brackets embedded ]", () => {
  let col: columnInfo = {name: "Field[2]", colType: "Text", size: 50, nullable: true}
  switch alterTable("T", AddColumn(col)) {
  | Some(sql) => assertion(~operator="equal", (a, b) => a == b, String.includes(sql, "[Field[2]]] VARCHAR(50) NULL"), true)
  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// createIndex — CREATE INDEX ... ON ... (col, ...) (REQ-S7)
// ---------------------------------------------------------------------------

test("createIndex basic", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="idxName", ~table="Orders", ~columns=["OrderID"], ~unique=false),
    "CREATE INDEX [idxName] ON [Orders] ([OrderID])",
  )
})

test("createIndex UNIQUE", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="uidxCode", ~table="Products", ~columns=["Code"], ~unique=true),
    "CREATE UNIQUE INDEX [uidxCode] ON [Products] ([Code])",
  )
})

test("createIndex multiple columns", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="idxOrderItem", ~table="OrderItems", ~columns=["OrderID", "ProductID"], ~unique=false),
    "CREATE INDEX [idxOrderItem] ON [OrderItems] ([OrderID], [ProductID])",
  )
})

test("createIndex brackets table and column names with spaces", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="idx My Index", ~table="My Table", ~columns=["My Column"], ~unique=false),
    "CREATE INDEX [idx My Index] ON [My Table] ([My Column])",
  )
})

test("createIndex UNIQUE with brackets", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="uidx [Special]", ~table="[My Table]", ~columns=["[Col]"], ~unique=true),
    "CREATE UNIQUE INDEX [uidx [Special]]] ON [[My Table]]] ([[Col]]])",
  )
})

test("createIndex UNIQUE ignore_nulls true appends WITH IGNORE NULL", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="uidxCode", ~table="Products", ~columns=["Code"], ~unique=true, ~ignore_nulls=true),
    "CREATE UNIQUE INDEX [uidxCode] ON [Products] ([Code]) WITH IGNORE NULL",
  )
})

test("createIndex ignore_nulls true but not unique omits WITH IGNORE NULL", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createIndex(~name="idxCode", ~table="Products", ~columns=["Code"], ~unique=false, ~ignore_nulls=true),
    "CREATE INDEX [idxCode] ON [Products] ([Code])",
  )
})

// ---------------------------------------------------------------------------
// dropIndex — DROP INDEX ... ON ... (REQ-S7)
// Required ON clause; Access DDL uses: DROP INDEX idx ON tbl
// ---------------------------------------------------------------------------

test("dropIndex basic", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    dropIndex(~name="idxName", ~table="Orders"),
    "DROP INDEX [idxName] ON [Orders]",
  )
})

test("dropIndex brackets both names with spaces", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    dropIndex(~name="idx My Index", ~table="My Table"),
    "DROP INDEX [idx My Index] ON [My Table]",
  )
})

test("dropIndex brackets embedded ]", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    dropIndex(~name="idx[1]", ~table="Table[2]"),
    "DROP INDEX [idx[1]]] ON [Table[2]]]",
  )
})

// ---------------------------------------------------------------------------
// createRelationship — ALTER TABLE ADD CONSTRAINT FK (REQ-S7)
// Access stores relationships via Jet/ACE DDL: ALTER TABLE ADD CONSTRAINT
// Constraint name, child table, child columns, parent table, parent columns
// Validates: relationship name ≤ 64 chars, child table ≤ 64 chars
// ---------------------------------------------------------------------------

test("createRelationship basic FK", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createRelationship(
      ~relationshipName="FK_Orders_Customers",
      ~table="Orders",
      ~columns=["CustomerID"],
      ~foreignTable="Customers",
      ~foreignColumns=["CustomerID"],
    ),
    Ok("ALTER TABLE [Orders] ADD CONSTRAINT [FK_Orders_Customers] FOREIGN KEY ([CustomerID]) REFERENCES [Customers] ([CustomerID])"),
  )
})

test("createRelationship multiple columns", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createRelationship(
      ~relationshipName="FK_OrderItems_Orders",
      ~table="OrderItems",
      ~columns=["OrderID", "ProductID"],
      ~foreignTable="Orders",
      ~foreignColumns=["OrderID", "ProductID"],
    ),
    Ok("ALTER TABLE [OrderItems] ADD CONSTRAINT [FK_OrderItems_Orders] FOREIGN KEY ([OrderID], [ProductID]) REFERENCES [Orders] ([OrderID], [ProductID])"),
  )
})

test("createRelationship brackets embedded ]", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createRelationship(
      ~relationshipName="FK_Table[1]_Parent[2]",
      ~table="Table[1]",
      ~columns=["Col[3]"],
      ~foreignTable="Parent[2]",
      ~foreignColumns=["Col[3]"],
    ),
    Ok("ALTER TABLE [Table[1]]] ADD CONSTRAINT [FK_Table[1]]_Parent[2]]] FOREIGN KEY ([Col[3]]]) REFERENCES [Parent[2]]] ([Col[3]]])"),
  )
})

test("createRelationship name exceeds 64 chars returns Error", () => {
  // "FK_" + 62 X's = 3 + 62 = 65 chars (> 64)
  let longName = "FK_" ++ Belt.Array.make(62, "X")->Belt.Array.reduce("", (acc, _) => acc ++ "X")
  switch createRelationship(
    ~relationshipName=longName,
    ~table="Orders",
    ~columns=["CustomerID"],
    ~foreignTable="Customers",
    ~foreignColumns=["CustomerID"],
  ) {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(e) => assertion(~operator="equal", (a, b) => a == b, String.includes(Errors.toDict(e).message, "64"), true)
  }
})

test("createRelationship child table exceeds 64 chars returns Error", () => {
  // "Table_" + 58 X's = 6 + 58 = 64 chars exactly; use 59 X's for > 64
  let longTable = "Table_" ++ Belt.Array.make(59, "X")->Belt.Array.reduce("", (acc, _) => acc ++ "X")
  switch createRelationship(
    ~relationshipName="FK_Test",
    ~table=longTable,
    ~columns=["ColA"],
    ~foreignTable="Parent",
    ~foreignColumns=["ColA"],
  ) {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(e) => assertion(~operator="equal", (a, b) => a == b, String.includes(Errors.toDict(e).message, "64"), true)
  }
})

test("createRelationship columns and foreignColumns length mismatch returns Error", () => {
  switch createRelationship(
    ~relationshipName="FK_Test",
    ~table="Orders",
    ~columns=["CustomerID", "OrderID"],
    ~foreignTable="Customers",
    ~foreignColumns=["CustomerID"],
  ) {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Error(e) => assertion(
      ~operator="equal",
      (a, b) => a == b,
      String.includes(Errors.toDict(e).message, "same length"),
      true,
    )
  }
})

// ---------------------------------------------------------------------------
// deleteRelationship — ALTER TABLE DROP CONSTRAINT (REQ-S7)
// ---------------------------------------------------------------------------

test("deleteRelationship basic", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    deleteRelationship(~table="Orders", ~relationshipName="FK_Orders_Customers"),
    "ALTER TABLE [Orders] DROP CONSTRAINT [FK_Orders_Customers]",
  )
})

test("deleteRelationship brackets both names with spaces", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    deleteRelationship(~table="My Table", ~relationshipName="FK My Table_My Parent"),
    "ALTER TABLE [My Table] DROP CONSTRAINT [FK My Table_My Parent]",
  )
})

test("deleteRelationship brackets embedded ]", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    deleteRelationship(~table="Table[1]", ~relationshipName="FK_Table[1]_Parent[2]"),
    "ALTER TABLE [Table[1]]] DROP CONSTRAINT [FK_Table[1]]_Parent[2]]]",
  )
})

// ---------------------------------------------------------------------------
// createView — CREATE VIEW [name] AS sql (REQ-S6)
// ---------------------------------------------------------------------------

test("createView basic", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createView(~name="qryActiveOrders", ~sql="SELECT * FROM Orders WHERE Status = 1"),
    "CREATE VIEW [qryActiveOrders] AS SELECT * FROM Orders WHERE Status = 1",
  )
})

test("createView brackets name with space", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createView(~name="qry Active Orders", ~sql="SELECT ID FROM Orders"),
    "CREATE VIEW [qry Active Orders] AS SELECT ID FROM Orders",
  )
})

test("createView brackets escape embedded ]", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    createView(~name="qry[1]", ~sql="SELECT * FROM T"),
    "CREATE VIEW [qry[1]]] AS SELECT * FROM T",
  )
})

// ---------------------------------------------------------------------------
// dropView — DROP VIEW [name] (REQ-S6)
// ---------------------------------------------------------------------------

test("dropView basic", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    dropView(~name="qryOldView"),
    "DROP VIEW [qryOldView]",
  )
})

test("dropView brackets name with space", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    dropView(~name="qry My View"),
    "DROP VIEW [qry My View]",
  )
})

test("dropView brackets escape embedded ]", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    dropView(~name="qry[2]"),
    "DROP VIEW [qry[2]]]",
  )
})

// ---------------------------------------------------------------------------
// setView — DROP VIEW + CREATE VIEW pair (REQ-S6)
// Returns Ok((dropSql, createSql)); sql is used verbatim (no re-bracketing)
// ---------------------------------------------------------------------------

test("setView returns drop then create pair", () => {
  switch setView(~name="qryOrders", ~sql="SELECT ID FROM Orders") {
  | Ok((dropSql, createSql)) => {
      assertion(~operator="equal", (a, b) => a == b, dropSql, "DROP VIEW [qryOrders]")
      assertion(~operator="equal", (a, b) => a == b, createSql, "CREATE VIEW [qryOrders] AS SELECT ID FROM Orders")
    }
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("setView brackets and escapes in name", () => {
  switch setView(~name="qry[Special]", ~sql="SELECT * FROM T") {
  | Ok((dropSql, createSql)) => {
      assertion(~operator="equal", (a, b) => a == b, dropSql, "DROP VIEW [qry[Special]]]")
      assertion(~operator="equal", (a, b) => a == b, createSql, "CREATE VIEW [qry[Special]]] AS SELECT * FROM T")
    }
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})
