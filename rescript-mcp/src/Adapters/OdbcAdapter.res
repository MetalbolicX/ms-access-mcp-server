// OdbcAdapter.res — DATA_ADAPTER implementation using Bindings.Odbc
// REQ-D4/D5/D6/D9 — lifecycle + data operations

// ---------------------------------------------------------------------------
// Exception message extraction
// ---------------------------------------------------------------------------

let _exnMessage = (e: exn): string => {
  let raw: option<string> = %raw("e => e && typeof e.message === 'string' ? e.message : null")(e)
  switch raw {
  | Some(m) => m
  | None => "Unknown error"
  }
}

// ---------------------------------------------------------------------------
// _buildWhereClause — parse JSON.t where clause into SqlBuilder.whereClause
// JSON Object with "Dict" key → Dict variant
// JSON Object with "Raw" key → Raw variant
// ---------------------------------------------------------------------------

type whereClause = SqlBuilder.whereClause

// Result state machine: all ops return Promise<result<'a, Errors.t>>
// Errors.t = ConfigError | PathGuardError | DatabaseError | ValidationError

// ---------------------------------------------------------------------------
// OdbcAdapter instance
// ---------------------------------------------------------------------------

type t = {
  mutable connection: option<Bindings.Odbc.connection>,
}

// ---------------------------------------------------------------------------
// _normalizeQueryResult — oDBcResult → Interfaces.queryResult
// All ODBC row values are converted to JSON via valueToJson
// ---------------------------------------------------------------------------

let _normalizeQueryResult = (result: Bindings.Odbc.oDBcResult): Interfaces.queryResult => {
  let jsonRows = Belt.Array.map(result.rows, row => {
    // Convert each oDBcRow (dict<oDBcValue>) to dict<JSON.t>
    let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
    let jsonEntry = Belt.Array.map(entries, ((k, v)) => (k, Bindings.Odbc.valueToJson(v)))
    let jsonDict: dict<JSON.t> = %raw("entries => Object.fromEntries(entries)")(jsonEntry)
    jsonDict
  })
  {
    success: true,
    rows: jsonRows,
    count: result.count,
    columns: result.columns,
    error: None,
  }
}

// ---------------------------------------------------------------------------
// _normalizeMutationResult — oDBcResult → Interfaces.mutationResult
// Returns affected row count from oDBcResult.count
// ---------------------------------------------------------------------------

let _normalizeMutationResult = (result: Bindings.Odbc.oDBcResult): Interfaces.mutationResult => {
  {
    success: true,
    affected: result.count,
    error: None,
  }
}

// ---------------------------------------------------------------------------
// connect — creates ODBC connection and stores in adapter state
// connectionString: ODBC connection string (DSN or full connection string)
// password: optional password for authentication
// ---------------------------------------------------------------------------

let connect = (
  adapter: t,
  connectionString: string,
  ~password: option<string>=?,
): Promise.t<result<bool, Errors.t>> => {
  let connStrWithPwd = switch password {
  | Some(pwd) => connectionString ++ ";PWD=" ++ pwd
  | None => connectionString
  }
  Bindings.Odbc.connect(connStrWithPwd)
    ->Promise.then(result => {
      switch result {
      | Ok(conn) => {
          adapter.connection = Some(conn)
          Promise.resolve(Ok(true))
        }
      | Error(err) => Promise.resolve(Error(err))
      }
    })
    ->Promise.catch(e => {
      let msg = _exnMessage(e)
      Promise.resolve(Error(Errors.databaseError(msg)))
    })
}

// ---------------------------------------------------------------------------
// disconnect — closes ODBC connection and clears adapter state
// ---------------------------------------------------------------------------

let disconnect = (adapter: t): Promise.t<result<unit, Errors.t>> => {
  switch adapter.connection {
  | None => Promise.resolve(Ok(()))
  | Some(conn) => {
      conn.close(())
        ->Promise.then(() => {
          adapter.connection = None
          Promise.resolve(Ok(()))
        })
        ->Promise.catch(e => {
          adapter.connection = None
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// isConnected — checks if adapter has an active connection
// ---------------------------------------------------------------------------

let isConnected = (adapter: t): Promise.t<result<bool, Errors.t>> => {
  Promise.resolve(Ok(switch adapter.connection {
  | Some(_) => true
  | None => false
  }))
}

// ---------------------------------------------------------------------------
// _requireConnection — returns Error if not connected, Some(conn) if connected
// ---------------------------------------------------------------------------

let _requireConnection = (adapter: t): option<Bindings.Odbc.connection> => {
  adapter.connection
}

// ---------------------------------------------------------------------------
// _buildWhereClause — parse JSON.t where clause into internal whereClause variant
// JSON Object with "Dict" key → Dict variant
// JSON Object with "Raw" key → Raw variant
// ---------------------------------------------------------------------------

let _buildWhereClause = (whereOpt: option<JSON.t>): option<whereClause> => {
  switch whereOpt {
  | None => None
  | Some(JSON.Object(props)) => {
      // Check for {"Dict": {"key": value}} or {"Raw": "condition"}
      let dictEntry = Dict.get(props, "Dict")
      let rawEntry = Dict.get(props, "Raw")
      switch (dictEntry, rawEntry) {
      | (Some(JSON.Object(d)), _) => Some(Dict(d))
      | (_, Some(JSON.String(s))) => Some(Raw(s))
      | (Some(JSON.String(k)), _) => {
          // Fallback: single string key with dict value → treat as Dict
          let d: dict<JSON.t> = %raw("k => ({[k]: null})")(k)
          Some(Dict(d))
        }
      | _ => None  // Invalid where JSON
      }
    }
  | _ => None
  }
}

// ---------------------------------------------------------------------------
// executeQuery — runs a SQL query and returns normalized result
// params: optional array of JSON values for parameterized queries
// ---------------------------------------------------------------------------

let executeQuery = (
  adapter: t,
  sql: string,
  ~params: option<array<JSON.t>>=?,
): Promise.t<result<Interfaces.queryResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let queryParams = switch params {
      | Some(p) => p
      | None => []
      }
      conn.query(sql, queryParams)
        ->Promise.then(result => {
          switch result {
          | Ok(r) => Promise.resolve(Ok(_normalizeQueryResult(r)))
          | Error(e) => Promise.resolve(Error(e))
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// insertData — INSERT a record into a table
// Uses SqlBuilder.insert for SQL building
// ---------------------------------------------------------------------------

let insertData = (
  adapter: t,
  table: string,
  record: dict<JSON.t>,
): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let (sql, params) = SqlBuilder.insert(table, record)
      conn.query(sql, params)
        ->Promise.then(result => {
          switch result {
          | Ok(r) => Promise.resolve(Ok(_normalizeMutationResult(r)))
          | Error(e) => Promise.resolve(Error(e))
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// updateData — UPDATE records in a table
// setDict: columns to update
// where: optional WHERE clause (Dict or Raw)
// Uses SqlBuilder.update for SQL building
// ---------------------------------------------------------------------------

let updateData = (
  adapter: t,
  table: string,
  setDict: dict<JSON.t>,
  ~where: option<JSON.t>=?,
): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let whereOpt = _buildWhereClause(where)
      let (sql, params) = SqlBuilder.update(table, setDict, whereOpt)
      conn.query(sql, params)
        ->Promise.then(result => {
          switch result {
          | Ok(r) => Promise.resolve(Ok(_normalizeMutationResult(r)))
          | Error(e) => Promise.resolve(Error(e))
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// deleteData — DELETE records from a table
// where: optional WHERE clause (Dict or Raw)
// Uses SqlBuilder.delete for SQL building
// ---------------------------------------------------------------------------

let deleteData = (
  adapter: t,
  table: string,
  ~where: option<JSON.t>=?,
): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let whereOpt = _buildWhereClause(where)
      let (sql, params) = SqlBuilder.delete(table, whereOpt)
      conn.query(sql, params)
        ->Promise.then(result => {
          switch result {
          | Ok(r) => Promise.resolve(Ok(_normalizeMutationResult(r)))
          | Error(e) => Promise.resolve(Error(e))
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// executeRawSql — execute arbitrary SQL without SqlBuilder wrapping
// Returns affected row count
// ---------------------------------------------------------------------------

let executeRawSql = (
  adapter: t,
  sql: string,
): Promise.t<result<int, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Ok(r) => Promise.resolve(Ok(r.count))
          | Error(e) => Promise.resolve(Error(e))
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// exportData — export table data to a file (stub — returns not-implemented)
// D3/D6: actual implementation delegates to ODBC driver capabilities
// ---------------------------------------------------------------------------

let exportData = (
  _adapter: t,
  _table: string,
  _filePath: string,
  ~_format: option<string>=?,
  ~_options: option<dict<JSON.t>>=?,
): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
  Promise.resolve(Error(Errors.databaseError("exportData not yet implemented")))
}

// ---------------------------------------------------------------------------
// _pyodbcTypeName — map ODBC TYPE_NAME to friendly names per REQ-S2
// Case-insensitive; unknown → passthrough; empty/None → ""
// ---------------------------------------------------------------------------

let _pyodbcTypeName = (sqlType: option<string>): string => {
  switch sqlType {
  | None => ""
  | Some(t) => {
      let upper: string = %raw("t => t.toUpperCase()")(t)
      switch upper {
      | "VARCHAR" => "Text"
      | "CHAR" => "Text"
      | "TEXT" => "Text"
      | "MEMO" => "Memo"
      | "INTEGER" => "Long Integer"
      | "INT" => "Long Integer"
      | "BIGINT" => "Big Integer"
      | "SMALLINT" => "Integer"
      | "TINYINT" => "Byte"
      | "BIT" => "Boolean"
      | "DATETIME" => "Date/Time"
      | "DATE" => "Date/Time"
      | "TIME" => "Date/Time"
      | "TIMESTAMP" => "Date/Time"
      | "DECIMAL" => "Decimal"
      | "NUMERIC" => "Decimal"
      | "MONEY" => "Currency"
      | "CURRENCY" => "Currency"
      | "FLOAT" => "Double"
      | "REAL" => "Single"
      | "DOUBLE" => "Double"
      | "BINARY" => "Binary"
      | "VARBINARY" => "Binary"
      | "IMAGE" => "Binary"
      | "GUID" => "GUID"
      | _ => t  // passthrough unknown types
      }
    }
  }
}

// ---------------------------------------------------------------------------
// _dictGet — safe JSON.t extraction from dict
// ---------------------------------------------------------------------------

let _dictGet = (d: dict<JSON.t>, k: string): option<JSON.t> => {
  Dict.get(d, k)
}

// ---------------------------------------------------------------------------
// _jsonToString — extract string from JSON.t, default ""
// ---------------------------------------------------------------------------

let _jsonToString = (j: option<JSON.t>): string => {
  switch j {
  | Some(JSON.String(s)) => s
  | _ => ""
  }
}

// ---------------------------------------------------------------------------
// _fieldInfoFromRow — convert ODBC column row to Interfaces.fieldInfo
// Uses _pyodbcTypeName for type mapping per REQ-S2
// ---------------------------------------------------------------------------

let _fieldInfoFromRow = (row: Bindings.Odbc.oDBcRow): Interfaces.fieldInfo => {
  let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
  let getStr = (k: string): string => {
    let v = Belt.Array.get(Belt.Array.keep(entries, ((key, _v)) => key == k), 0)
    switch v {
    | Some((_k, Bindings.Odbc.Str(s))) => s
    | _ => ""
    }
  }
  let getInt = (k: string): int => {
    let v = Belt.Array.get(Belt.Array.keep(entries, ((key, _v)) => key == k), 0)
    switch v {
    | Some((_k, Bindings.Odbc.Int(i))) => i
    | Some((_k, Bindings.Odbc.Float(f))) => Float.toInt(f)
    | _ => 0
    }
  }
  let name = getStr("COLUMN_NAME")
  let typeNameOpt = switch Belt.Array.get(Belt.Array.keep(entries, ((key, _v)) => key == "TYPE_NAME"), 0) {
  | Some((_k, Bindings.Odbc.Str(s))) => Some(s)
  | Some((_k, Bindings.Odbc.Null)) => None
  | _ => None
  }
  let type_ = _pyodbcTypeName(typeNameOpt)
  let size = getInt("COLUMN_SIZE")
  let nullable = getInt("NULLABLE")
  // nullable=0 means SQL_NO_NULLS → required=true; nullable=1 means NULL allowed → required=false
  let required = nullable == 0
  {
    name: name,
    type_: type_,
    size: size,
    required: required,
    allowZeroLength: true,  // hardcoded per REQ-S1
    defaultValue: None,
    isAutoincrement: false,
  }
}

// ---------------------------------------------------------------------------
// _buildCountQuery — SELECT COUNT(*) FROM [table] SQL
// ---------------------------------------------------------------------------

let _buildCountQuery = (tableName: string): string => {
  "SELECT COUNT(*) FROM [" ++ tableName ++ "]"
}

// ---------------------------------------------------------------------------
// getTables — enumerate user tables via SQLTables + SQLColumns + COUNT
// REQ-S1: filter MSys*, per-table fields + record_count, degrade gracefully
// ---------------------------------------------------------------------------

let getTables = (adapter: t): Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Ok([]))
  | Some(conn) => {
      conn.tables(~tableType=Some("TABLE"))
        ->Promise.then(result => {
          switch result {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(tableRows) => {
              // Filter out MSys* tables
              let userTableRows = Belt.Array.keep(tableRows, row => {
                let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
                let name = switch Belt.Array.get(Belt.Array.keep(entries, ((k, _)) => k == "TABLE_NAME"), 0) {
                | Some((_, Bindings.Odbc.Str(s))) => s
                | _ => ""
                }
                !String.startsWith(name, "MSys")
              })

              // Process each table: get columns + COUNT
              let rec processTables = (
                tables: array<Interfaces.tableInfo>,
                remaining: array<Bindings.Odbc.oDBcRow>,
              ): Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> => {
                switch Belt.Array.get(remaining, 0) {
                | None => Promise.resolve(Ok(tables))
                | Some(row) => {
                    let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
                    let name = switch Belt.Array.get(Belt.Array.keep(entries, ((k, _)) => k == "TABLE_NAME"), 0) {
                    | Some((_, Bindings.Odbc.Str(s))) => s
                    | _ => ""
                    }

                    // Get column metadata
                    conn.columns(~table=Some(name))
                      ->Promise.then(colResult => {
                        let fields = switch colResult {
                        | Ok(colRows) => Belt.Array.map(colRows, _fieldInfoFromRow)
                        | Error(_) => []
                        }

                        // Get record count
                        let countSql = _buildCountQuery(name)
                        conn.query(countSql, [])
                          ->Promise.then(countResult => {
                            let recordCount = switch countResult {
                            | Ok(r) if r.count > 0 => {
                                switch Belt.Array.get(r.rows, 0) {
                                | Some(firstRow) => {
                                    let rowEntries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(firstRow)
                                    switch Belt.Array.get(rowEntries, 0) {
                                    | Some((_, Bindings.Odbc.Int(i))) => i
                                    | Some((_, Bindings.Odbc.Float(f))) => Float.toInt(f)
                                    | _ => 0
                                    }
                                  }
                                | None => 0
                                }
                              }
                            | _ => 0
                            }

                            let tableInfo: Interfaces.tableInfo = {
                              name: name,
                              fields: fields,
                              recordCount: recordCount,
                              primaryKey: None,
                            }
                            processTables(
                              Belt.Array.concat(tables, [tableInfo]),
                              Belt.Array.sliceToEnd(remaining, 1),
                            )
                          })
                          ->Promise.catch(_e => {
                            // COUNT failure tolerated: table listed with recordCount=0
                            let tableInfo: Interfaces.tableInfo = {
                              name: name,
                              fields: fields,
                              recordCount: 0,
                              primaryKey: None,
                            }
                            processTables(
                              Belt.Array.concat(tables, [tableInfo]),
                              Belt.Array.sliceToEnd(remaining, 1),
                            )
                          })
                      })
                  }
                }
              }

              processTables([], userTableRows)
            }
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// getSystemTables — degraded contract per REQ-S12
// Always returns Ok([]) — ODBC cannot enumerate system tables
// ---------------------------------------------------------------------------

let getSystemTables = (_adapter: t): Promise.t<result<array<Interfaces.tableInfo>, Errors.t>> => {
  Promise.resolve(Ok([]))
}

// ---------------------------------------------------------------------------
// getObjectMetadata — degraded contract per REQ-S12
// Always returns Ok(empty dict) — not available via ODBC
// ---------------------------------------------------------------------------

let getObjectMetadata = (_adapter: t, _name: string): Promise.t<result<dict<JSON.t>, Errors.t>> => {
  Promise.resolve(Ok(Dict.make()))
}

// ---------------------------------------------------------------------------
// getIndexes — degraded contract per REQ-S12
// Always returns Ok([]) — ODBC cannot enumerate DAO indexes
// ---------------------------------------------------------------------------

let getIndexes = (_adapter: t, _table: string): Promise.t<result<array<Interfaces.indexInfo>, Errors.t>> => {
  Promise.resolve(Ok([]))
}

// ---------------------------------------------------------------------------
// getRelationships — delegates to OdbcSchemaReader per REQ-S4
// ---------------------------------------------------------------------------

let getRelationships = (adapter: t): Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Ok([]))
  | Some(conn) => {
      let issueQuery: OdbcSchemaReader.issueQuery = (~sql: string) => {
        conn.query(sql, [])
          ->Promise.then(result => {
            switch result {
            | Ok(r) => {
                // Convert oDBcResult.rows to array<dict<JSON.t>>
                let jsonRows = Belt.Array.map(r.rows, row => {
                  let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
                  let jsonEntry = Belt.Array.map(entries, ((k, v)) => (k, Bindings.Odbc.valueToJson(v)))
                  let jsonDict: dict<JSON.t> = %raw("entries => Object.fromEntries(entries)")(jsonEntry)
                  jsonDict
                })
                Promise.resolve(Ok(jsonRows))
              }
            | Error(e) => Promise.resolve(Error(e))
            }
          })
          ->Promise.catch(e => {
            let msg = _exnMessage(e)
            Promise.resolve(Error(Errors.databaseError(msg)))
          })
      }
      OdbcSchemaReader.readRelationships(~query=issueQuery)
    }
  }
}

// ---------------------------------------------------------------------------
// getTableSchemaPlan — build TableSchema from ODBC column metadata
// REQ-S3: all UnknownMetadata flags = true (ODBC cannot expose them)
// ---------------------------------------------------------------------------

let getTableSchemaPlan = (adapter: t): Promise.t<result<(array<Interfaces.tableSchema>, Interfaces.unknownMetadata), Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Ok(([], ({
    primaryKeys: true,
    foreignKeys: true,
    defaults: true,
    indexes: true,
    autoincrement: true,
  }: Interfaces.unknownMetadata))))
  | Some(_conn) => {
      getTables(adapter)
        ->Promise.then(tablesResult => {
          switch tablesResult {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(tables) => {
              let schemas = Belt.Array.map(tables, table => {
                let columns = Belt.Array.map(table.fields, field => (
                  {
                    name: field.name,
                    sourceType: field.type_,
                    maxLength: if field.size > 0 { Some(field.size) } else { None },
                    allowNull: !field.required,
                    isAutoincrement: false,
                    defaultValue: None,
                  }: Interfaces.columnSchema
                ))
                (
                  {
                    name: table.name,
                    columns: columns,
                    primaryKey: None,
                    foreignKeys: [],
                    indexes: [],
                  }: Interfaces.tableSchema
                )
              })
              let unknownMeta: Interfaces.unknownMetadata = {
                primaryKeys: true,
                foreignKeys: true,
                defaults: true,
                indexes: true,
                autoincrement: true,
              }
              Promise.resolve(Ok((schemas, unknownMeta)))
            }
          }
        })
        ->Promise.catch(e => {
          let msg = _exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// getQueries — enumerate saved queries via INFORMATION_SCHEMA.VIEWS
// REQ-S5: pinned Access quirks: dbo filter, type="select" hardcoded
// ---------------------------------------------------------------------------

let getQueries = (adapter: t): Promise.t<result<array<Interfaces.queryInfo>, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Ok([]))
  | Some(conn) => {
      let sql = "SELECT TABLE_NAME, VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME NOT LIKE '~%' ORDER BY TABLE_NAME"
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Ok(r) => {
              let queries = Belt.Array.map(r.rows, row => {
                let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
                let name = switch Belt.Array.get(Belt.Array.keep(entries, ((k, _)) => k == "TABLE_NAME"), 0) {
                | Some((_, Bindings.Odbc.Str(s))) => s
                | _ => ""
                }
                let sqlText = switch Belt.Array.get(Belt.Array.keep(entries, ((k, _)) => k == "VIEW_DEFINITION"), 0) {
                | Some((_, Bindings.Odbc.Str(s))) => s
                | _ => ""
                }
                (
                  {
                    name: name,
                    sql: sqlText,
                    type_: "select",  // hardcoded per REQ-S5 Access quirk
                  }: Interfaces.queryInfo
                )
              })
              Promise.resolve(Ok(queries))
            }
          | Error(_) => Promise.resolve(Ok([]))  // errors swallowed per REQ-S5
          }
        })
        ->Promise.catch(_e => {
          // Errors swallowed per REQ-S5
          Promise.resolve(Ok([]))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// generateSql — degraded contract per REQ-S12
// Always returns error "Not available via ODBC"
// ---------------------------------------------------------------------------

let generateSql = (_adapter: t, _outputPath: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  Promise.resolve(Ok(({success: false, error: Some("Not available via ODBC")}: Interfaces.ddlResult)))
}

// ---------------------------------------------------------------------------
// getDatabaseStatistics — degraded stub (statistics not yet implemented)
// ---------------------------------------------------------------------------

let getDatabaseStatistics = (_adapter: t): Promise.t<result<dict<JSON.t>, Errors.t>> => {
  Promise.resolve(Ok(Dict.make()))
}
