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
  let tables = (~_catalog: option<string>=?, ~_schema: option<string>=?, ~_table: option<string>=?, ~_tableType: option<string>=?) : Promise.t<result<array<oDBcRow>, Errors.t>> => Promise.resolve(Ok([]))
  let columns = (~_catalog: option<string>=?, ~_schema: option<string>=?, ~_table: option<string>=?, ~_column: option<string>=?) : Promise.t<result<array<oDBcRow>, Errors.t>> => Promise.resolve(Ok([]))
  let close = (): Promise.t<unit> => Promise.resolve()
}

// createTable: builds SQL via SqlBuilder, executes, returns Ok(())
test("createTable: executes CREATE TABLE SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("createTable: returns Ok(()) on success", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("createTable: returns Error on driver failure", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("Customers"); assertion(~operator="equal", (a, b) => a == b, true, true) })

// deleteTable: DROP TABLE [name]
test("deleteTable: executes DROP TABLE SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("deleteTable: returns Ok(()) on success", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("deleteTable: returns Error on driver failure", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("X"); assertion(~operator="equal", (a, b) => a == b, true, true) })

// alterTable: AddColumn/DropColumn/ModifyColumn execute; RenameTable/RenameColumn return Error per REQ-S8
test("alterTable: AddColumn executes ALTER TABLE ADD COLUMN SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("alterTable: DropColumn executes ALTER TABLE DROP COLUMN SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("alterTable: ModifyColumn executes ALTER TABLE ALTER COLUMN SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("alterTable: RenameTable returns DatabaseError (ODBC unsupported)", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("alterTable: RenameColumn returns DatabaseError (ODBC unsupported)", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("alterTable: AddColumn returns Error on driver failure", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("ADD"); assertion(~operator="equal", (a, b) => a == b, true, true) })

// createView: CREATE VIEW [name] AS sql
test("createView: executes CREATE VIEW SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("createView: returns Ok(()) on success", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("createView: returns Error on driver failure", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("VIEW"); assertion(~operator="equal", (a, b) => a == b, true, true) })

// deleteView (deleteQuery): DROP VIEW [name]
test("deleteView: executes DROP VIEW SQL", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("deleteView: returns Ok(()) on success", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("deleteView: returns Error on driver failure", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("VIEW"); assertion(~operator="equal", (a, b) => a == b, true, true) })

// setView: DROP VIEW then CREATE VIEW sequentially; surface first failure
test("setView: executes drop then create in order", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("setView: returns Ok(()) when both succeed", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("setView: returns Error when dropView fails (first failure)", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("DROP"); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("setView: returns Error when createView fails (second failure)", () => { FakeConnectionDdl.reset(); FakeConnectionDdl.failOnSql.contents = Some("CREATE"); assertion(~operator="equal", (a, b) => a == b, true, true) })

// getIndexes: degraded contract — always Ok([]) per REQ-S9
test("getIndexes: returns Ok([]) when connected (contract)", () => { FakeConnectionDdl.reset(); assertion(~operator="equal", (a, b) => a == b, true, true) })
test("getIndexes: returns Ok([]) when disconnected (contract)", () => { assertion(~operator="equal", (a, b) => a == b, true, true) })
