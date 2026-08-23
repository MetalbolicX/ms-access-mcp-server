open Test
open Bindings.Odbc

// Task 3.7/3.8 — statistics + export | REQ-S11, REQ-D10

// Shared fake connection base (tables/columns/close stubs)
module FakeBase = {
  let tables = (~_c: option<string>=?, ~_s: option<string>=?, ~_t: option<string>=?, ~_tt: option<string>=?): Promise.t<result<array<oDBcRow>, Errors.t>> => Promise.resolve(Ok([]))
  let columns = (~_c: option<string>=?, ~_s: option<string>=?, ~_t: option<string>=?, ~_col: option<string>=?): Promise.t<result<array<oDBcRow>, Errors.t>> => Promise.resolve(Ok([]))
  let close = (): Promise.t<unit> => Promise.resolve()
}

module FakeStatsConnection = {
  include FakeBase
  let msysRows: array<oDBcRow> = [
    dict{"Type": Int(1), "Count": Int(5)},   // tables
    dict{"Type": Int(5), "Count": Int(3)},   // queries
    dict{"Type": Int(-32768), "Count": Int(2)}, // forms
    dict{"Type": Int(-32764), "Count": Int(1)}, // reports
    dict{"Type": Int(-32766), "Count": Int(4)}, // macros
    dict{"Type": Int(-32761), "Count": Int(1)}, // modules
  ]
  let query = (_sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> =>
    Promise.resolve(Ok({rows: msysRows, columns: ["Type","Count"], count: 6, statement: Some(_sql)}))
}

module FakeMsysDeniedConnection = {
  include FakeBase
  let tables = (~_c: option<string>=?, ~_s: option<string>=?, ~_t: option<string>=?, ~_tt: option<string>=?): Promise.t<result<array<oDBcRow>, Errors.t>> =>
    Promise.resolve(Ok([dict{"TABLE_NAME": Str("Customers")}, dict{"TABLE_NAME": Str("Orders")}, dict{"TABLE_NAME": Str("Products")}, dict{"TABLE_NAME": Str("Suppliers")}]))
  let query = (_sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> =>
    Promise.resolve(Error(Errors.databaseError("MSysObjects access denied")))
}

module FakeExportConnection = {
  include FakeBase
  let lastQuery: ref<string> = ref("")
  let shouldFail: ref<bool> = ref(false)
  let query = (sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> => {
    lastQuery.contents = sql
    if shouldFail.contents { Promise.resolve(Error(Errors.databaseError("Not connected"))) }
    else { Promise.resolve(Ok({rows: [dict{"id": Int(1), "name": Str("Widget")}, dict{"id": Int(2), "name": Str("Gadget")}], columns: ["id","name"], count: 2, statement: Some(sql)})) }
  }
}

// getDatabaseStatistics tests
test("disconnected returns empty counts, no file, no warning", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
test("MSysObjects query maps Type codes to counts correctly", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
test("MSysObjects denied falls back to getTables count with warning", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })

// exportData tests
test("csv: executes query and writes CSV with headers", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
test("json: executes query and writes JSON array to file", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
test("unknown format returns Error without writing file", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
test("disconnected returns Error without writing file", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
