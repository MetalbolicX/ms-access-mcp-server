open Test

// Task 1.2 RED test — Interfaces records construction and field access

test("TableInfo record can be constructed and fields accessed", () => {
  let info: Interfaces.tableInfo = {
    name: "Orders",
    fields: [],
    recordCount: 0,
    primaryKey: None,
  }
  assertion(~operator="equal", (a, b) => a == b, info.name, "Orders")
  assertion(~operator="equal", (a, b) => a == b, info.recordCount, 0)
})

test("FieldInfo record can be constructed with all fields", () => {
  let field: Interfaces.fieldInfo = {
    name: "OrderID",
    type_: "Long Integer",
    size: 0,
    required: true,
    allowZeroLength: false,
    defaultValue: None,
    isAutoincrement: true,
  }
  assertion(~operator="equal", (a, b) => a == b, field.name, "OrderID")
  assertion(~operator="equal", (a, b) => a == b, field.type_, "Long Integer")
  assertion(~operator="equal", (a, b) => a == b, field.required, true)
  assertion(~operator="equal", (a, b) => a == b, field.isAutoincrement, true)
  assertion(~operator="equal", (a, b) => a == b, field.defaultValue, None)
})

test("QueryInfo record can be constructed", () => {
  let info: Interfaces.queryInfo = {
    name: "qry_ActiveOrders",
    sql: "SELECT * FROM Orders WHERE Status='Active'",
    type_: "select",
  }
  assertion(~operator="equal", (a, b) => a == b, info.name, "qry_ActiveOrders")
  assertion(~operator="equal", (a, b) => a == b, info.type_, "select")
})

test("RelationshipInfo record can be constructed", () => {
  let rel: Interfaces.relationshipInfo = {
    name: "FK_Orders_Customers",
    table: "Orders",
    foreignTable: "Customers",
    attributes: "",
    columns: ["CustomerID"],
    foreignColumns: ["ID"],
  }
  assertion(~operator="equal", (a, b) => a == b, rel.name, "FK_Orders_Customers")
  assertion(~operator="equal", (a, b) => a == b, rel.columns, ["CustomerID"])
  assertion(~operator="equal", (a, b) => a == b, rel.foreignColumns, ["ID"])
})

test("TableSchema record can be constructed", () => {
  let schema: Interfaces.tableSchema = {
    name: "Products",
    columns: [],
    primaryKey: None,
    foreignKeys: [],
    indexes: [],
  }
  assertion(~operator="equal", (a, b) => a == b, schema.name, "Products")
})

test("UnknownMetadata all-flags-true record", () => {
  let meta: Interfaces.unknownMetadata = {
    primaryKeys: true,
    foreignKeys: true,
    defaults: true,
    indexes: true,
    autoincrement: true,
  }
  assertion(~operator="equal", (a, b) => a == b, meta.primaryKeys, true)
  assertion(~operator="equal", (a, b) => a == b, meta.foreignKeys, true)
  assertion(~operator="equal", (a, b) => a == b, meta.indexes, true)
})

test("QueryResult success record", () => {
  let result: Interfaces.queryResult = {
    success: true,
    rows: [],
    count: 0,
    columns: [],
    error: None,
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, true)
  assertion(~operator="equal", (a, b) => a == b, result.count, 0)
  assertion(~operator="equal", (a, b) => a == b, result.error, None)
})

test("QueryResult failure record with error", () => {
  let result: Interfaces.queryResult = {
    success: false,
    rows: [],
    count: 0,
    columns: [],
    error: Some("Syntax error in SQL"),
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, false)
  assertion(~operator="equal", (a, b) => a == b, result.error, Some("Syntax error in SQL"))
})

test("MutationResult success record", () => {
  let result: Interfaces.mutationResult = {
    success: true,
    affected: 5,
    error: None,
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, true)
  assertion(~operator="equal", (a, b) => a == b, result.affected, 5)
})

test("MutationResult failure record", () => {
  let result: Interfaces.mutationResult = {
    success: false,
    affected: 0,
    error: Some("Table not found"),
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, false)
  assertion(~operator="equal", (a, b) => a == b, result.error, Some("Table not found"))
})
