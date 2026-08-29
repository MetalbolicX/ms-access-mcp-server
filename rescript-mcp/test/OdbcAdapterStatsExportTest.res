open Test
open Bindings.Odbc

// Task 3.7/3.8 — statistics + export | REQ-S11, REQ-D10
// Notes: parameter names on FakeBase must match connection record type exactly
// to avoid ReScript's option-erosion pitfall.

module FakeBase = {
  let tables: (~catalog: option<string>=?, ~schema: option<string>=?, ~table: option<string>=?, ~tableType: option<string>=?) => Promise.t<result<array<oDBcRow>, Errors.t>> = (~catalog=?, ~schema=?, ~table=?, ~tableType=?) => Promise.resolve(Ok([]))
  let columns: (~catalog: option<string>=?, ~schema: option<string>=?, ~table: option<string>=?, ~column: option<string>=?) => Promise.t<result<array<oDBcRow>, Errors.t>> = (~catalog=?, ~schema=?, ~table=?, ~column=?) => Promise.resolve(Ok([]))
  let close: unit => Promise.t<unit> = () => Promise.resolve()
}

module FakeStatsConnection = {
  include FakeBase
  let msysRows: array<oDBcRow> = [
    dict{"Type": Int(1), "Count": Int(5)}, dict{"Type": Int(5), "Count": Int(3)},
    dict{"Type": Int(-32768), "Count": Int(2)}, dict{"Type": Int(-32764), "Count": Int(1)},
    dict{"Type": Int(-32766), "Count": Int(4)}, dict{"Type": Int(-32761), "Count": Int(1)},
  ]
  let query = (_sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> =>
    Promise.resolve(Ok({rows: msysRows, columns: ["Type","Count"], count: 6, statement: Some(_sql)}))
}

module FakeMsysDeniedConnection = {
  include FakeBase
  let tables: (~catalog: option<string>=?, ~schema: option<string>=?, ~table: option<string>=?, ~tableType: option<string>=?) => Promise.t<result<array<oDBcRow>, Errors.t>> = (~catalog=?, ~schema=?, ~table=?, ~tableType=?) =>
    Promise.resolve(Ok([dict{"TABLE_NAME": Str("Customers")}, dict{"TABLE_NAME": Str("Orders")}, dict{"TABLE_NAME": Str("Products")}, dict{"TABLE_NAME": Str("Suppliers")}]))
  let query = (_sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> =>
    Promise.resolve(Error(Errors.databaseError("MSysObjects access denied")))
}

module FakeExportConnection = {
  include FakeBase
  let lastQuery: ref<string> = ref("")
  let query = (sql: string, _params: array<JSON.t>): Promise.t<result<oDBcResult, Errors.t>> => {
    lastQuery.contents = sql
    Promise.resolve(Ok({rows: [dict{"id": Int(1), "name": Str("Widget")}, dict{"id": Int(2), "name": Str("Gadget")}], columns: ["id","name"], count: 2, statement: Some(sql)}))
  }
}

let _tmpCounter: ref<int> = ref(0)
let makeTmpPath = (ext: string): string => {
  _tmpCounter := _tmpCounter.contents + 1
  NodeJs.Os.tmpdir() ++ "/mcp-export-" ++ Int.toString(_tmpCounter.contents) ++ "." ++ ext
}
let fsExistsSync = (p: string): bool => NodeJs.Fs.existsSync(p)
let fsReadFileSync = (p: string): string => NodeJs.Fs.readFileSync(p)->NodeJs.Buffer.toStringWithEncoding(NodeJs.StringEncoding.utf8)
let fsUnlinkSafe = (p: string): unit => { try { NodeJs.Fs.unlinkSync(p) } catch { | _ => () } }

let mkAdapter = (q, t, c, cl, dbPath): OdbcAdapter.t => {
  let conn: Bindings.Odbc.connection = {query: q, tables: t, columns: c, close: cl}
  {connection: Some(conn), dbPath: dbPath}
}
let makeStatsAdapter = (dbPath: option<string>): OdbcAdapter.t => mkAdapter(FakeStatsConnection.query, FakeStatsConnection.tables, FakeStatsConnection.columns, FakeStatsConnection.close, dbPath)
let makeMsysDeniedAdapter = (): OdbcAdapter.t => mkAdapter(FakeMsysDeniedConnection.query, FakeMsysDeniedConnection.tables, FakeMsysDeniedConnection.columns, FakeMsysDeniedConnection.close, None)
let makeExportAdapter = (): OdbcAdapter.t => mkAdapter(FakeExportConnection.query, FakeExportConnection.tables, FakeExportConnection.columns, FakeExportConnection.close, None)
let makeDisconnectedAdapter = (): OdbcAdapter.t => {connection: None, dbPath: None}

// Helper: extract a numeric field from the nested `objects` dict.
let _countFromStats = (stats: dict<JSON.t>, field: string): option<JSON.t> => {
  switch Dict.get(stats, "objects") {
  | Some(JSON.Object(objDict)) => Dict.get(objDict, field)
  | _ => None
  }
}

// Helper: extract a string field from the nested `file` dict.
let _fileField = (stats: dict<JSON.t>, field: string): option<JSON.t> => {
  switch Dict.get(stats, "file") {
  | Some(JSON.Object(fileDict)) => Dict.get(fileDict, field)
  | _ => None
  }
}

// getDatabaseStatistics: disconnected → zero counts, empty file, no warning
testAsync("getDatabaseStatistics: disconnected returns zero counts, empty file, no warning", cb => {
  let adapter = makeDisconnectedAdapter()
  ignore(OdbcAdapter.getDatabaseStatistics(adapter)
    ->Promise.then(result => {
      switch result {
      | Ok(stats) => {
          assertion(~operator="equal", (a, b) => a == b, Dict.get(stats, "success"), Some(JSON.Boolean(true)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "tables"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "queries"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "forms"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "reports"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "macros"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "modules"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _fileField(stats, "name"), Some(JSON.String("")))
          assertion(~operator="equal", (a, b) => a == b, _fileField(stats, "size_bytes"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _fileField(stats, "modified"), Some(JSON.String("")))
          assertion(~operator="equal", (a, b) => a == b, Dict.get(stats, "warning"), Some(JSON.Null))
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=11, ()); Promise.resolve() })
    ->Promise.catch(_e => { assertion(~operator="equal", (a, b) => a == b, false, true); cb(~planned=1, ()); Promise.resolve() }))
})

// getDatabaseStatistics: lstatSync throws (nonexistent dbPath) → size=0, mtime=empty, warning=Null
testAsync("getDatabaseStatistics: lstatSync throws (nonexistent path) → size=0, mtime=empty, warning=Null", cb => {
  let adapter = makeStatsAdapter(Some("C:/nonexistent/path/missing.accdb"))
  ignore(OdbcAdapter.getDatabaseStatistics(adapter)
    ->Promise.then(result => {
      switch result {
      | Ok(stats) => {
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "tables"), Some(JSON.Number(5.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "queries"), Some(JSON.Number(3.0)))
          assertion(~operator="equal", (a, b) => a == b, _fileField(stats, "name"), Some(JSON.String("missing.accdb")))
          assertion(~operator="equal", (a, b) => a == b, _fileField(stats, "size_bytes"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _fileField(stats, "modified"), Some(JSON.String("")))
          assertion(~operator="equal", (a, b) => a == b, Dict.get(stats, "warning"), Some(JSON.Null))
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=6, ()); Promise.resolve() })
    ->Promise.catch(_e => { assertion(~operator="equal", (a, b) => a == b, false, true); cb(~planned=1, ()); Promise.resolve() }))
})

// getDatabaseStatistics: MSysObjects success maps Type codes to counts
testAsync("getDatabaseStatistics: MSysObjects query maps Type codes to counts correctly", cb => {
  let adapter = makeStatsAdapter(None)
  ignore(OdbcAdapter.getDatabaseStatistics(adapter)
    ->Promise.then(result => {
      switch result {
      | Ok(stats) => {
          assertion(~operator="equal", (a, b) => a == b, Dict.get(stats, "success"), Some(JSON.Boolean(true)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "tables"), Some(JSON.Number(5.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "queries"), Some(JSON.Number(3.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "forms"), Some(JSON.Number(2.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "reports"), Some(JSON.Number(1.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "macros"), Some(JSON.Number(4.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "modules"), Some(JSON.Number(1.0)))
          assertion(~operator="equal", (a, b) => a == b, Dict.get(stats, "warning"), Some(JSON.Null))
          // system.com_available
          assertion(~operator="equal", (a, b) => a == b, switch Dict.get(stats, "system") {
            | Some(JSON.Object(sys)) => Dict.get(sys, "com_available")
            | _ => None
          }, Some(JSON.Boolean(false)))
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=9, ()); Promise.resolve() })
    ->Promise.catch(_e => { assertion(~operator="equal", (a, b) => a == b, false, true); cb(~planned=1, ()); Promise.resolve() }))
})

// getDatabaseStatistics: MSysObjects denied falls back to getTables count
testAsync("getDatabaseStatistics: MSysObjects denied falls back to getTables count with warning", cb => {
  let adapter = makeMsysDeniedAdapter()
  ignore(OdbcAdapter.getDatabaseStatistics(adapter)
    ->Promise.then(result => {
      switch result {
      | Ok(stats) => {
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "tables"), Some(JSON.Number(4.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "queries"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "forms"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "reports"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "macros"), Some(JSON.Number(0.0)))
          assertion(~operator="equal", (a, b) => a == b, _countFromStats(stats, "modules"), Some(JSON.Number(0.0)))
          let warningStr = switch Dict.get(stats, "warning") {
          | Some(JSON.String(s)) => s | _ => ""
          }
          assertion(~operator="equal", (a, b) => a == b, String.includes(warningStr, "MSysObjects access denied"), true)
          assertion(~operator="equal", (a, b) => a == b, String.includes(warningStr, "table count"), true)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=8, ()); Promise.resolve() })
    ->Promise.catch(_e => { assertion(~operator="equal", (a, b) => a == b, false, true); cb(~planned=1, ()); Promise.resolve() }))
})

// exportData: CSV executes query, captures lastQuery, attempts write
testAsync("exportData: CSV executes query, captures lastQuery, attempts write", cb => {
  FakeExportConnection.lastQuery.contents = ""
  let tmpPath = makeTmpPath("csv")
  let adapter = makeExportAdapter()
  ignore(OdbcAdapter.exportData(adapter, "SELECT * FROM Items", tmpPath, ~format="csv")
    ->Promise.then(result => {
      switch result {
      | Ok(mutation) => {
          assertion(~operator="equal", (a, b) => a == b, mutation.success, true)
          assertion(~operator="equal", (a, b) => a == b, mutation.affected, 2)
          assertion(~operator="equal", (a, b) => a == b, FakeExportConnection.lastQuery.contents, "SELECT * FROM Items")
          assertion(~operator="equal", (a, b) => a == b, fsExistsSync(tmpPath), true)
          let content = fsReadFileSync(tmpPath)
          assertion(~operator="equal", (a, b) => a == b, String.includes(content, "id,name"), true)
          assertion(~operator="equal", (a, b) => a == b, String.includes(content, "1,Widget"), true)
          assertion(~operator="equal", (a, b) => a == b, String.includes(content, "2,Gadget"), true)
          fsUnlinkSafe(tmpPath)
        }
      | Error(_) => {
          // No longer reachable — production uses NodeJs.Fs.writeFileSync (ESM-safe).
          assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=7, ()); Promise.resolve() }))
})

// exportData: JSON executes query, captures lastQuery, attempts write
testAsync("exportData: JSON executes query, captures lastQuery, attempts write", cb => {
  FakeExportConnection.lastQuery.contents = ""
  let tmpPath = makeTmpPath("json")
  let adapter = makeExportAdapter()
  ignore(OdbcAdapter.exportData(adapter, "SELECT * FROM Items", tmpPath, ~format="json")
    ->Promise.then(result => {
      switch result {
      | Ok(mutation) => {
          assertion(~operator="equal", (a, b) => a == b, mutation.success, true)
          assertion(~operator="equal", (a, b) => a == b, mutation.affected, 2)
          assertion(~operator="equal", (a, b) => a == b, FakeExportConnection.lastQuery.contents, "SELECT * FROM Items")
          assertion(~operator="equal", (a, b) => a == b, fsExistsSync(tmpPath), true)
          let content = fsReadFileSync(tmpPath)
          assertion(~operator="equal", (a, b) => a == b, String.includes(content, "Widget"), true)
          assertion(~operator="equal", (a, b) => a == b, String.includes(content, "Gadget"), true)
          fsUnlinkSafe(tmpPath)
        }
      | Error(_) => {
          // No longer reachable — production uses NodeJs.Fs.writeFileSync (ESM-safe).
          assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=6, ()); Promise.resolve() }))
})

// exportData: unknown format returns Error without writing file
testAsync("exportData: unknown format returns Error without writing file", cb => {
  let tmpPath = makeTmpPath("xml")
  let adapter = makeExportAdapter()
  ignore(OdbcAdapter.exportData(adapter, "SELECT 1", tmpPath, ~format="xml")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => { assertion(~operator="equal", (a, b) => a == b, false, true); fsUnlinkSafe(tmpPath) }
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "unsupported export format"), true)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "xml"), true)
          assertion(~operator="equal", (a, b) => a == b, fsExistsSync(tmpPath), false)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=3, ()); Promise.resolve() })
    ->Promise.catch(_e => { fsUnlinkSafe(tmpPath); assertion(~operator="equal", (a, b) => a == b, false, true); cb(~planned=1, ()); Promise.resolve() }))
})

// exportData: disconnected returns Error without writing file
testAsync("exportData: disconnected returns Error without writing file", cb => {
  let tmpPath = makeTmpPath("csv")
  let adapter = makeDisconnectedAdapter()
  ignore(OdbcAdapter.exportData(adapter, "SELECT 1", tmpPath)
    ->Promise.then(result => {
      switch result {
      | Ok(_) => { assertion(~operator="equal", (a, b) => a == b, false, true); fsUnlinkSafe(tmpPath) }
      | Error(e) => {
          let d = Errors.toDict(e)
          assertion(~operator="equal", (a, b) => a == b, String.includes(d.message, "Not connected"), true)
          assertion(~operator="equal", (a, b) => a == b, fsExistsSync(tmpPath), false)
        }
      }
      Promise.resolve()
    })
    ->Promise.then(() => { cb(~planned=2, ()); Promise.resolve() })
    ->Promise.catch(_e => { fsUnlinkSafe(tmpPath); assertion(~operator="equal", (a, b) => a == b, false, true); cb(~planned=1, ()); Promise.resolve() }))
})
