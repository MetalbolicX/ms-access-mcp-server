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
