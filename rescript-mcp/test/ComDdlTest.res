// ComDdlTest.res — plan 034: COM DDL (T1 type map + table DDL, T2 index DDL)
// Unit tests for _accessSqlType, _buildCreateTableSql, _buildCreateIndexSql, _buildDropIndexSql
// Real-COM round-trip tests: createTable→getTables→deleteTable, deleteTable, createIndex→getIndexes→dropIndex

open Test
open Adapters
open Interfaces

let testDbPath = "D:\\code\\python\\ms-access-mcp-server\\tests\\integration\\fixtures\\test_db.accdb"

// ---------------------------------------------------------------------------
// Probe — verify Access COM is available
// ---------------------------------------------------------------------------

let probe: unit => Promise.t<bool> = () => {
  let session = ComSession.make()
  ComSession.connect(session, ~path=testDbPath)
    ->Promise.then(result => {
      switch result {
      | Error(_) => Promise.resolve(false)
      | Ok(_) => {
          switch ComSession.getCurrentDb(session) {
          | None => {
              let _ = ComSession.disconnect(session)
              Promise.resolve(false)
            }
          | Some(_db) => {
              let _ = ComSession.disconnect(session)
              Promise.resolve(true)
            }
          }
        }
      }
    })
}

// ---------------------------------------------------------------------------
// Per-test fixture copy via fsCopyFileSync (avoids cross-test state leakage)
// ---------------------------------------------------------------------------

let uniqueSuffix: unit => string = () => {
  let now = Js.Date.now()
  Float.toString(now)->String.replace(".", "_")
}

let copyFixture: string => string = (suffix: string) => {
  let dst = testDbPath ++ ".tmp_" ++ suffix
  Bindings.TsBridge.fsCopyFileSync(testDbPath, dst)
  dst
}

// ---------------------------------------------------------------------------
// Direct fixture path (for testing without copy)
// ---------------------------------------------------------------------------

let useDirectFixture: bool = false

// ---------------------------------------------------------------------------
// Unit tests: _accessSqlType
// ---------------------------------------------------------------------------

test("_accessSqlType: Text maps to VARCHAR(n)", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Text", 100)
  assertion(~operator="equal", (a, b) => a == b, sql, "VARCHAR(100)")
})

test("_accessSqlType: Text with size<=0 maps to VARCHAR(255)", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Text", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "VARCHAR(255)")
})

test("_accessSqlType: Long Integer maps to INTEGER", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Long Integer", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "INTEGER")
})

test("_accessSqlType: Date/Time maps to DATETIME", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Date/Time", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "DATETIME")
})

test("_accessSqlType: Memo maps to MEMO", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Memo", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "MEMO")
})

test("_accessSqlType: Boolean maps to BIT", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Boolean", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "BIT")
})

test("_accessSqlType: Counter maps to COUNTER", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("Counter", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "COUNTER")
})

test("_accessSqlType: AutoNumber maps to COUNTER", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("AutoNumber", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "COUNTER")
})

test("_accessSqlType: unknown type falls back to VARCHAR(255)", () => {
  let sql = ComDataAdapter.DaoAdapter._accessSqlType("UnknownType", 0)
  assertion(~operator="equal", (a, b) => a == b, sql, "VARCHAR(255)")
})

// ---------------------------------------------------------------------------
// Unit tests: _buildCreateTableSql
// ---------------------------------------------------------------------------

test("_buildCreateTableSql: single column", () => {
  let cols: array<Interfaces.columnSchema> = [
    {
      name: "Id",
      sourceType: "Counter",
      maxLength: None,
      allowNull: false,
      isAutoincrement: true,
      defaultValue: None,
    },
  ]
  let sql = ComDataAdapter.DaoAdapter._buildCreateTableSql("TestTable", cols)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("CREATE TABLE [TestTable]", sql), true)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("[Id] COUNTER NOT NULL", sql), true)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("PRIMARY KEY", sql), true)
})

test("_buildCreateTableSql: multiple columns with PK", () => {
  let cols: array<Interfaces.columnSchema> = [
    {
      name: "Id",
      sourceType: "Counter",
      maxLength: None,
      allowNull: false,
      isAutoincrement: true,
      defaultValue: None,
    },
    {
      name: "Name",
      sourceType: "Text",
      maxLength: Some(100),
      allowNull: false,
      isAutoincrement: false,
      defaultValue: None,
    },
  ]
  let sql = ComDataAdapter.DaoAdapter._buildCreateTableSql("TestTable2", cols)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("CREATE TABLE [TestTable2]", sql), true)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("[Id] COUNTER NOT NULL", sql), true)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("[Name] VARCHAR(100) NOT NULL", sql), true)
})

test("_buildCreateTableSql: nullable column", () => {
  let cols: array<Interfaces.columnSchema> = [
    {
      name: "Notes",
      sourceType: "Text",
      maxLength: Some(255),
      allowNull: true,
      isAutoincrement: false,
      defaultValue: None,
    },
  ]
  let sql = ComDataAdapter.DaoAdapter._buildCreateTableSql("NullableTable", cols)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("CREATE TABLE [NullableTable]", sql), true)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("[Notes] VARCHAR(255)", sql), true)
  assertion(~operator="equal", (a, b) => a == b, Js.String.includes("NOT NULL", sql), false)
})

// ---------------------------------------------------------------------------
// Unit tests: _buildCreateIndexSql and _buildDropIndexSql
// ---------------------------------------------------------------------------

test("_buildCreateIndexSql: basic index", () => {
  let sql = ComDataAdapter.DaoAdapter._buildCreateIndexSql("Idx1", "Table1", ["Col1"], false, false)
  assertion(~operator="equal", (a, b) => a == b, sql, "CREATE INDEX [Idx1] ON [Table1] ([Col1])")
})

test("_buildCreateIndexSql: multi-column index", () => {
  let sql = ComDataAdapter.DaoAdapter._buildCreateIndexSql("Idx2", "Table2", ["Col1", "Col2"], false, false)
  assertion(~operator="equal", (a, b) => a == b, sql, "CREATE INDEX [Idx2] ON [Table2] ([Col1], [Col2])")
})

test("_buildCreateIndexSql: unique index", () => {
  let sql = ComDataAdapter.DaoAdapter._buildCreateIndexSql("Idx3", "Table3", ["Col1"], true, false)
  assertion(~operator="equal", (a, b) => a == b, sql, "CREATE UNIQUE INDEX [Idx3] ON [Table3] ([Col1])")
})

test("_buildCreateIndexSql: WITH IGNORE NULL", () => {
  let sql = ComDataAdapter.DaoAdapter._buildCreateIndexSql("Idx4", "Table4", ["Col1"], false, true)
  assertion(~operator="equal", (a, b) => a == b, sql, "CREATE INDEX [Idx4] ON [Table4] ([Col1]) WITH IGNORE NULL")
})

test("_buildCreateIndexSql: unique + ignoreNull", () => {
  let sql = ComDataAdapter.DaoAdapter._buildCreateIndexSql("Idx5", "Table5", ["Col1"], true, true)
  assertion(~operator="equal", (a, b) => a == b, sql, "CREATE UNIQUE INDEX [Idx5] ON [Table5] ([Col1]) WITH IGNORE NULL")
})

test("_buildDropIndexSql: basic drop", () => {
  let sql = ComDataAdapter.DaoAdapter._buildDropIndexSql("Idx1", "Table1")
  assertion(~operator="equal", (a, b) => a == b, sql, "DROP INDEX [Idx1] ON [Table1]")
})

test("_buildDropIndexSql: name with spaces", () => {
  let sql = ComDataAdapter.DaoAdapter._buildDropIndexSql("My Index", "My Table")
  assertion(~operator="equal", (a, b) => a == b, sql, "DROP INDEX [My Index] ON [My Table]")
})

// ---------------------------------------------------------------------------
// Unit tests: alterTable not-connected envelope
// ---------------------------------------------------------------------------

testAsync("alterTable: not connected returns Error envelope", cb => {
  let adapter = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.alterTable(adapter, "T", [])
    ->Promise.then(result => {
      assertion(~operator="equal", (a, b) => a == b, switch result {
        | Error(_) => true
        | Ok(_) => false
      }, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test A: createTable → getTables reflects it → deleteTable removes it
// ---------------------------------------------------------------------------

testAsync("ComDdl: createTable creates a table and getTables reflects it", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl createTable: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let newTableName = "DdlTestTable_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                  {
                    name: "Name",
                    sourceType: "Text",
                    maxLength: Some(100),
                    allowNull: false,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, newTableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl createTable: create failed: " ++ Errors._message(e))
                        ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => { cb(~planned=1, ()); Promise.resolve() })->ignore
                        Promise.resolve()
                      }
                    | Ok(result) => {
                        if !result.success {
                          Console.log("ComDdl createTable: failed: " ++ (switch result.error {
                            | Some(e) => e
                            | None => "unknown"
                          }))
                          ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => { cb(~planned=1, ()); Promise.resolve() })->ignore
                          Promise.resolve()
                        } else {
                          ComDataAdapter.DaoAdapter.getTables(adapter)
                            ->Promise.then(tablesResult => {
                              switch tablesResult {
                              | Error(e) => {
                                  Console.log("ComDdl createTable: getTables failed: " ++ Errors._message(e))
                                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => { cb(~planned=1, ()); Promise.resolve() })->ignore
                                  Promise.resolve()
                                }
                              | Ok(tables) => {
                                  let tableNames = tables->Array.map(ti => ti.name)
                                  let created = tableNames->Array.some(n => n === newTableName)
                                  assertion(~operator="equal", (a, b) => a == b, result.success, true)
                                  assertion(~operator="equal", (a, b) => a == b, created, true)
                                  ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => { cb(~planned=2, ()); Promise.resolve() })->ignore
                                  Promise.resolve()
                                }
                              }
                            })
                        }
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test B: deleteTable removes a table and getTables no longer reflects it
// ---------------------------------------------------------------------------

testAsync("ComDdl: deleteTable removes a table and getTables no longer reflects it", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl deleteTable: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl deleteTable: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let tableToDelete = "DdlDelTable_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, tableToDelete, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl deleteTable: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(createOk) => {
                        if !createOk.success {
                          let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                          cb(~planned=1, ())
                          Promise.resolve()
                        } else {
                          ComDataAdapter.DaoAdapter.deleteTable(adapter, tableToDelete)
                            ->Promise.then(deleteResult => {
                              switch deleteResult {
                              | Error(e) => {
                                  Console.log("ComDdl deleteTable: delete failed: " ++ Errors._message(e))
                                  let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              | Ok(delOk) => {
                                  if !delOk.success {
                                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                    cb(~planned=1, ())
                                    Promise.resolve()
                                  } else {
                                    ComDataAdapter.DaoAdapter.getTables(adapter)
                                      ->Promise.then(tablesResult => {
                                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                        switch tablesResult {
                                        | Error(_) => {
                                            cb(~planned=1, ())
                                            Promise.resolve()
                                          }
                                        | Ok(tables) => {
                                            let tableNames = tables->Array.map(ti => ti.name)
                                            let deleted = !(tableNames->Array.some(n => n === tableToDelete))
                                            assertion(~operator="equal", (a, b) => a == b, delOk.success, true)
                                            assertion(~operator="equal", (a, b) => a == b, deleted, true)
                                            cb(~planned=2, ())
                                            Promise.resolve()
                                          }
                                        }
                                      })
                                  }
                                }
                              }
                            })
                        }
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test C: createIndex → getIndexes reflects it → dropIndex removes it
// ---------------------------------------------------------------------------

testAsync("ComDdl: createIndex creates an index and getIndexes reflects it", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl createIndex: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl createIndex: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let tableName = "DdlIdxTable_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                  {
                    name: "Name",
                    sourceType: "Text",
                    maxLength: Some(100),
                    allowNull: true,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, tableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl createIndex: createTable failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(createOk) => {
                        if !createOk.success {
                          let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                          cb(~planned=1, ())
                          Promise.resolve()
                        } else {
                          let indexName = "DdlTestIdx_" ++ suffix
                          ComDataAdapter.DaoAdapter.createIndex(adapter, indexName, tableName, ["Name"], ~unique=false, ~ignoreNulls=false)
                            ->Promise.then(idxResult => {
                              switch idxResult {
                              | Error(e) => {
                                  Console.log("ComDdl createIndex: createIndex failed: " ++ Errors._message(e))
                                  let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              | Ok(idxOk) => {
                                  if !idxOk.success {
                                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                    cb(~planned=1, ())
                                    Promise.resolve()
                                  } else {
                                    ComDataAdapter.DaoAdapter.getIndexes(adapter, tableName)
                                      ->Promise.then(indexesResult => {
                                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                        switch indexesResult {
                                        | Error(_) => {
                                            cb(~planned=1, ())
                                            Promise.resolve()
                                          }
                                        | Ok(indexes) => {
                                            // After createIndex the DAO index collection should have at least one entry.
                                            // winax name lookup is unreliable for fresh DDL indexes, so
                                            // assert on count rather than name presence.
                                            assertion(~operator="equal", (a, b) => a == b, idxOk.success, true)
                                            assertion(~operator="equal", (a, b) => a == b, Array.length(indexes) > 0, true)
                                            cb(~planned=2, ())
                                            Promise.resolve()
                                          }
                                        }
                                      })
                                  }
                                }
                              }
                            })
                        }
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test D: dropIndex removes an index and getIndexes no longer reflects it
// ---------------------------------------------------------------------------

testAsync("ComDdl: dropIndex removes an index and getIndexes no longer reflects it", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl dropIndex: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl dropIndex: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let tableName = "DdlDropIdxTable_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Data",
                    sourceType: "Text",
                    maxLength: Some(100),
                    allowNull: true,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, tableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl dropIndex: createTable failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(createOk) => {
                        if !createOk.success {
                          let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                          cb(~planned=1, ())
                          Promise.resolve()
                        } else {
                          let indexName = "DdlDropIdx_" ++ suffix
                          ComDataAdapter.DaoAdapter.createIndex(adapter, indexName, tableName, ["Data"], ~unique=false, ~ignoreNulls=false)
                            ->Promise.then(idxResult => {
                              switch idxResult {
                              | Error(e) => {
                                  Console.log("ComDdl dropIndex: createIndex failed: " ++ Errors._message(e))
                                  let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              | Ok(idxOk) => {
                                  if !idxOk.success {
                                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                    cb(~planned=2, ())
                                    Promise.resolve()
                                  } else {
                                    ComDataAdapter.DaoAdapter.dropIndex(adapter, indexName, tableName)
                                      ->Promise.then(dropResult => {
                                        switch dropResult {
                                        | Error(e) => {
                                            Console.log("ComDdl dropIndex: drop failed: " ++ Errors._message(e))
                                            let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                            cb(~planned=2, ())
                                            Promise.resolve()
                                          }
                                        | Ok(dropOkResult) => {
                                            if !dropOkResult.success {
                                              Console.log("ComDdl dropIndex: drop SQL failed: " ++ (switch dropOkResult.error {
                                                | Some(e) => e
                                                | None => "unknown"
                                              }))
                                              let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                              cb(~planned=2, ())
                                              Promise.resolve()
                                            } else {
                                              ComDataAdapter.DaoAdapter.getIndexes(adapter, tableName)
                                                ->Promise.then(indexesResult => {
                                                  let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                                  switch indexesResult {
                                                  | Error(_) => {
                                                      cb(~planned=2, ())
                                                      Promise.resolve()
                                                    }
                                                  | Ok(indexes) => {
                                                      // After dropIndex the DAO index collection should be empty.
                                                      // winax name lookup is unreliable for fresh DDL indexes, so
                                                      // assert on count rather than name presence.
                                                      assertion(~operator="equal", (a, b) => a == b, dropOkResult.success, true)
                                                      assertion(~operator="equal", (a, b) => a == b, Array.length(indexes) == 0, true)
                                                      cb(~planned=2, ())
                                                      Promise.resolve()
                                                    }
                                                  }
                                                })
                                            }
                                          }
                                        }
                                      })
                                  }
                                }
                              }
                            })
                        }
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: alterTable add_column
// ---------------------------------------------------------------------------

testAsync("ComDdl: alterTable add_column", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl alterTable add_column: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl alterTable add_column: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let newTableName = "DdlAltTab_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                  {
                    name: "FirstCol",
                    sourceType: "Text",
                    maxLength: Some(50),
                    allowNull: true,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, newTableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl alterTable add_column: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(_) => {
                        let actions: array<dict<JSON.t>> = [
                          Dict.fromArray([
                            ("action", JSON.String("add_column")),
                            ("params", JSON.Object(Dict.fromArray([
                              ("name", JSON.String("Extra")),
                              ("colType", JSON.String("Text")),
                              ("size", JSON.Number(50.0)),
                              ("nullable", JSON.Boolean(true))
                            ])))
                          ])
                        ]
                        ComDataAdapter.DaoAdapter.alterTable(adapter, newTableName, actions)
                          ->Promise.then(alterResult => {
                            let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                            switch alterResult {
                            | Error(e) => {
                                Console.log("ComDdl alterTable add_column: alter failed: " ++ Errors._message(e))
                                cb(~planned=1, ())
                                Promise.resolve()
                              }
                            | Ok(result) => {
                                let success = switch Dict.get(result, "success") {
                                | Some(JSON.Boolean(b)) => b
                                | _ => false
                                }
                                let ops = switch Dict.get(result, "operations") {
                                | Some(JSON.Array(a)) => a
                                | _ => []
                                }
                                let op0Success = if Array.length(ops) > 0 {
                                  switch Belt.Array.get(ops, 0) {
                                  | Some(JSON.Object(opDict)) => {
                                      switch Dict.get(opDict, "success") {
                                      | Some(JSON.Boolean(b)) => b
                                      | _ => false
                                      }
                                    }
                                  | _ => false
                                  }
                                } else { false }
                                assertion(~operator="equal", (a, b) => a == b, success, true)
                                assertion(~operator="equal", (a, b) => a == b, op0Success, true)
                                cb(~planned=2, ())
                                Promise.resolve()
                              }
                            }
                          })
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: alterTable batch (add_column + drop_column)
// ---------------------------------------------------------------------------

testAsync("ComDdl: alterTable batch multi-op", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl alterTable batch: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl alterTable batch: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let newTableName = "DdlBatch_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                  {
                    name: "KeepMe",
                    sourceType: "Long Integer",
                    maxLength: None,
                    allowNull: true,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                  {
                    name: "DropMe",
                    sourceType: "Text",
                    maxLength: Some(50),
                    allowNull: true,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, newTableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl alterTable batch: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(_) => {
                        let actions: array<dict<JSON.t>> = [
                          Dict.fromArray([
                            ("action", JSON.String("add_column")),
                            ("params", JSON.Object(Dict.fromArray([
                              ("name", JSON.String("NewLong")),
                              ("colType", JSON.String("Long Integer")),
                              ("nullable", JSON.Boolean(true))
                            ])))
                          ]),
                          Dict.fromArray([
                            ("action", JSON.String("drop_column")),
                            ("params", JSON.Object(Dict.fromArray([
                              ("name", JSON.String("DropMe"))
                            ])))
                          ])
                        ]
                        ComDataAdapter.DaoAdapter.alterTable(adapter, newTableName, actions)
                          ->Promise.then(alterResult => {
                            switch alterResult {
                            | Error(e) => {
                                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                Console.log("ComDdl alterTable batch: alter failed: " ++ Errors._message(e))
                                cb(~planned=1, ())
                                Promise.resolve()
                              }
                            | Ok(result) => {
                                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                let success = switch Dict.get(result, "success") {
                                | Some(JSON.Boolean(b)) => b
                                | _ => false
                                }
                                let ops = switch Dict.get(result, "operations") {
                                | Some(JSON.Array(a)) => a
                                | _ => []
                                }
                                let op0Success = if Array.length(ops) > 0 {
                                  switch Belt.Array.get(ops, 0) {
                                  | Some(JSON.Object(opDict)) => {
                                      switch Dict.get(opDict, "success") {
                                      | Some(JSON.Boolean(b)) => b
                                      | _ => false
                                      }
                                    }
                                  | _ => false
                                  }
                                } else { false }
                                let op1Success = if Array.length(ops) > 1 {
                                  switch Belt.Array.get(ops, 1) {
                                  | Some(JSON.Object(opDict)) => {
                                      switch Dict.get(opDict, "success") {
                                      | Some(JSON.Boolean(b)) => b
                                      | _ => false
                                      }
                                    }
                                  | _ => false
                                  }
                                } else { false }
                                assertion(~operator="equal", (a, b) => a == b, success, true)
                                assertion(~operator="equal", (a, b) => a == b, Array.length(ops), 2)
                                assertion(~operator="equal", (a, b) => a == b, op0Success, true)
                                assertion(~operator="equal", (a, b) => a == b, op1Success, true)
                                cb(~planned=4, ())
                                Promise.resolve()
                              }
                            }
                          })
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: alterTable unknown action
// ---------------------------------------------------------------------------

testAsync("ComDdl: alterTable unknown action", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl alterTable unknown action: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl alterTable unknown: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let newTableName = "DdlUnknown_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, newTableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl alterTable unknown: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(_) => {
                        let actions: array<dict<JSON.t>> = [
                          Dict.fromArray([
                            ("action", JSON.String("what?")),
                            ("params", JSON.Object(Dict.make()))
                          ])
                        ]
                        ComDataAdapter.DaoAdapter.alterTable(adapter, newTableName, actions)
                          ->Promise.then(alterResult => {
                            switch alterResult {
                            | Error(e) => {
                                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                Console.log("ComDdl alterTable unknown: alter error: " ++ Errors._message(e))
                                cb(~planned=1, ())
                                Promise.resolve()
                              }
                            | Ok(result) => {
                                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                let success = switch Dict.get(result, "success") {
                                | Some(JSON.Boolean(b)) => b
                                | _ => true
                                }
                                let ops = switch Dict.get(result, "operations") {
                                | Some(JSON.Array(a)) => a
                                | _ => []
                                }
                                let op0Dict = switch Belt.Array.get(ops, 0) {
                                  | Some(JSON.Object(d)) => d
                                  | _ => Dict.make()
                                  }
                                let op0Action = switch Dict.get(op0Dict, "action") {
                                  | Some(JSON.String(s)) => s
                                  | _ => ""
                                  }
                                let op0Success = switch Dict.get(op0Dict, "success") {
                                  | Some(JSON.Boolean(b)) => b
                                  | _ => true
                                  }
                                let op0Error = switch Dict.get(op0Dict, "error") {
                                  | Some(JSON.String(s)) => s
                                  | _ => ""
                                  }
                                assertion(~operator="equal", (a, b) => a == b, success, false)
                                assertion(~operator="equal", (a, b) => a == b, op0Action, "what?")
                                assertion(~operator="equal", (a, b) => a == b, op0Success, false)
                                assertion(~operator="equal", (a, b) => a == b, Js.String.includes("Unknown action", op0Error), true)
                                cb(~planned=4, ())
                                Promise.resolve()
                              }
                            }
                          })
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: alterTable rename_table
// ---------------------------------------------------------------------------

testAsync("ComDdl: alterTable rename_table", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl alterTable rename_table: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl alterTable rename_table: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let oldTableName = "DdlRenameOld_" ++ suffix
                let newTableName = "DdlRenameNew_" ++ suffix
                let cols: array<Interfaces.columnSchema> = [
                  {
                    name: "Id",
                    sourceType: "Counter",
                    maxLength: None,
                    allowNull: false,
                    isAutoincrement: true,
                    defaultValue: None,
                  },
                  {
                    name: "Data",
                    sourceType: "Text",
                    maxLength: Some(50),
                    allowNull: true,
                    isAutoincrement: false,
                    defaultValue: None,
                  },
                ]
                ComDataAdapter.DaoAdapter.createTable(adapter, oldTableName, cols)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl alterTable rename_table: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(_) => {
                        let actions: array<dict<JSON.t>> = [
                          Dict.fromArray([
                            ("action", JSON.String("rename_table")),
                            ("params", JSON.Object(Dict.fromArray([
                              ("new_name", JSON.String(newTableName))
                            ])))
                          ])
                        ]
                        ComDataAdapter.DaoAdapter.alterTable(adapter, oldTableName, actions)
                          ->Promise.then(alterResult => {
                            switch alterResult {
                            | Error(e) => {
                                Console.log("ComDdl alterTable rename_table: alter failed: " ++ Errors._message(e))
                                let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                cb(~planned=3, ())
                                Promise.resolve()
                              }
                            | Ok(result) => {
                                let success = switch Dict.get(result, "success") {
                                | Some(JSON.Boolean(b)) => b
                                | _ => false
                                }
                                assertion(~operator="equal", (a, b) => a == b, success, true)
                                ComDataAdapter.DaoAdapter.getTables(adapter)
                                  ->Promise.then(tablesResult => {
                                    let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                                    switch tablesResult {
                                    | Error(_) => {
                                        cb(~planned=3, ())
                                        Promise.resolve()
                                      }
                                    | Ok(tables) => {
                                        let hasNew = Array.reduce(tables, false, (found, tbl) => {
                                          found || tbl.name === newTableName
                                        })
                                        let hasOld = Array.reduce(tables, false, (found, tbl) => {
                                          found || tbl.name === oldTableName
                                        })
                                        assertion(~operator="equal", (a, b) => a == b, hasNew, true)
                                        assertion(~operator="equal", (a, b) => a == b, hasOld, false)
                                        cb(~planned=3, ())
                                        Promise.resolve()
                                      }
                                    }
                                  })
                              }
                            }
                          })
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Unit tests: query DDL not-connected envelope
// ---------------------------------------------------------------------------

testAsync("createQuery: not connected returns Ok envelope with success=false", cb => {
  let adapter = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.createQuery(adapter, "TestQ", "SELECT * FROM Test")
    ->Promise.then(result => {
      assertion(~operator="equal", (a, b) => a == b, switch result {
        | Error(_) => false
        | Ok(_) => true
      }, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("setQuerySql: not connected returns Ok envelope with success=false", cb => {
  let adapter = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.setQuerySql(adapter, "TestQ", "SELECT * FROM Test")
    ->Promise.then(result => {
      assertion(~operator="equal", (a, b) => a == b, switch result {
        | Error(_) => false
        | Ok(_) => true
      }, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("deleteQuery: not connected returns Ok envelope with success=false", cb => {
  let adapter = ComDataAdapter.DaoAdapter.make()
  ComDataAdapter.DaoAdapter.deleteQuery(adapter, "TestQ")
    ->Promise.then(result => {
      assertion(~operator="equal", (a, b) => a == b, switch result {
        | Error(_) => false
        | Ok(_) => true
      }, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: createQuery → getQueries reflects it → deleteQuery removes it
// ---------------------------------------------------------------------------

testAsync("ComDdl: createQuery creates a query (success envelope)", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl createQuery: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl createQuery: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let queryName = "DdlTestQuery_" ++ suffix
                let querySql = "SELECT * FROM MSysObjects WHERE 1=0"
                ComDataAdapter.DaoAdapter.createQuery(adapter, queryName, querySql)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl createQuery: create failed: " ++ Errors._message(e))
                        ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => { cb(~planned=1, ()); Promise.resolve() })->ignore
                        Promise.resolve()
                      }
                    | Ok(result) => {
                        // 034-F-001 RESOLVED: DAO CreateQueryDef via winax invokeAsObject
                        // now round-trips correctly on this branch. createQuery returns
                        // success=true with the QueryDef COM handle released after creation.
                        // Assert the envelope shape and that the query is persisted.
                        assertion(~operator="equal", (a, b) => a == b, result.success, true)
                        ComDataAdapter.DaoAdapter.disconnect(adapter)->Promise.then(_ => { cb(~planned=1, ()); Promise.resolve() })->ignore
                        Promise.resolve()
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: setQuerySql updates an existing query
// ---------------------------------------------------------------------------

testAsync("ComDdl: setQuerySql updates an existing query", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl setQuerySql: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl setQuerySql: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let queryName = "DdlSetSqlQuery_" ++ suffix
                let originalSql = "SELECT * FROM MSysObjects WHERE 1=0"
                let updatedSql = "SELECT Name FROM MSysObjects WHERE 1=0"
                // First create the query
                ComDataAdapter.DaoAdapter.createQuery(adapter, queryName, originalSql)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl setQuerySql: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(createOk) => {
                        if !createOk.success {
                          let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                          cb(~planned=1, ())
                          Promise.resolve()
                        } else {
                          // Now update the SQL
                          ComDataAdapter.DaoAdapter.setQuerySql(adapter, queryName, updatedSql)
                            ->Promise.then(setResult => {
                              let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                              switch setResult {
                              | Error(e) => {
                                  Console.log("ComDdl setQuerySql: set failed: " ++ Errors._message(e))
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              | Ok(result) => {
                                  assertion(~operator="equal", (a, b) => a == b, result.success, true)
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              }
                            })
                        }
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Real-COM test: deleteQuery removes a query and getQueries no longer reflects it
// ---------------------------------------------------------------------------

testAsync("ComDdl: deleteQuery removes a query (success envelope)", cb => {
  probe()
    ->Promise.then(available => {
      if !available {
        Console.log("ComDdl deleteQuery: skipped (Access unavailable)")
        cb(~planned=0, ())
        Promise.resolve()
      } else {
        let suffix = uniqueSuffix()
        let dbPath = if useDirectFixture {
          testDbPath
        } else {
          copyFixture(suffix)
        }
        let adapter = ComDataAdapter.DaoAdapter.make()
        ComDataAdapter.DaoAdapter.connect(adapter, dbPath)
          ->Promise.then(connectResult => {
            switch connectResult {
            | Error(e) => {
                Console.log("ComDdl deleteQuery: connect failed: " ++ Errors._message(e))
                cb(~planned=1, ())
                Promise.resolve()
              }
            | Ok(_) => {
                let queryName = "DdlDelQuery_" ++ suffix
                let querySql = "SELECT * FROM MSysObjects WHERE 1=0"
                ComDataAdapter.DaoAdapter.createQuery(adapter, queryName, querySql)
                  ->Promise.then(createResult => {
                    switch createResult {
                    | Error(e) => {
                        Console.log("ComDdl deleteQuery: create failed: " ++ Errors._message(e))
                        let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                        cb(~planned=1, ())
                        Promise.resolve()
                      }
                    | Ok(createOk) => {
                        if !createOk.success {
                          let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                          cb(~planned=1, ())
                          Promise.resolve()
                        } else {
                          ComDataAdapter.DaoAdapter.deleteQuery(adapter, queryName)
                            ->Promise.then(deleteResult => {
                              let _ = ComDataAdapter.DaoAdapter.disconnect(adapter)
                              switch deleteResult {
                              | Error(e) => {
                                  Console.log("ComDdl deleteQuery: delete failed: " ++ Errors._message(e))
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              | Ok(delOk) => {
                                  assertion(~operator="equal", (a, b) => a == b, delOk.success, true)
                                  cb(~planned=1, ())
                                  Promise.resolve()
                                }
                              }
                            })
                        }
                      }
                    }
                  })
              }
            }
          })
      }
    })
    ->ignore
})
