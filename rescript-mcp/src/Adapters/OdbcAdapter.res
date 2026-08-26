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
  mutable dbPath: option<string>,
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
    count: Belt.Array.length(jsonRows),
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
  // Extract DBQ=<path> from connection string for file metadata
  let dbqMatch: option<string> = %raw(
    "s => { const m = s.match(/DBQ=([^;]+)/i); return m ? m[1] : null }"
  )(connectionString)
  Bindings.Odbc.connect(connStrWithPwd)
    ->Promise.then(result => {
      switch result {
      | Ok(conn) => {
          adapter.connection = Some(conn)
          adapter.dbPath = dbqMatch
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
          adapter.dbPath = None
          Promise.resolve(Ok(()))
        })
        ->Promise.catch(e => {
          adapter.connection = None
          adapter.dbPath = None
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
          | Ok(r) => Promise.resolve(Ok(r.count >= 0 ? r.count : 0))
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
// exportData — export query results to CSV or JSON file (REQ-D10)
// executeQuery → format → write via node:fs → Ok(mutationResult)
// Disconnected → Error | Unknown format → Error | Success → Ok with affected
// ---------------------------------------------------------------------------

let exportData = (
  adapter: t,
  query: string,
  filePath: string,
  ~format: option<string>=?,
  ~_options: option<dict<JSON.t>>=?,
): Promise.t<result<Interfaces.mutationResult, Errors.t>> => {
  switch adapter.connection {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let fmt = switch format {
      | Some(f) => f
      | None => "csv"
      }
      conn.query(query, [])
        ->Promise.then(result => {
          switch result {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(r) => {
              let jsonRows = r.rows
              let rowCount = Belt.Array.length(jsonRows)
              let columns = r.columns
              // Serialize based on format — unknown format returns Error
              let contentOpt: option<string> = if fmt == "csv" {
                Some(
                  CsvWriter.serializeWithHeaders(
                    columns,
                    Belt.Array.map(jsonRows, row => {
                      Belt.Array.map(columns, col => {
                        let v: option<Bindings.Odbc.oDBcValue> = Dict.get(row, col)
                        switch v {
                        | Some(Bindings.Odbc.Str(s)) => s
                        | Some(Bindings.Odbc.Int(i)) => Belt.Int.toString(i)
                        | Some(Bindings.Odbc.Float(f)) => Belt.Float.toString(f)
                        | Some(Bindings.Odbc.Null) => ""
                        | Some(Bindings.Odbc.Bool(b)) => b ? "true" : "false"
                        | Some(Bindings.Odbc.DateTime(d)) => Date.toISOString(d)
                        | Some(Bindings.Odbc.Buffer(b)) => %raw("buf => buf.toString('base64')")(b)
                        | None => ""
                        }
                      })
                    }),
                  ),
                )
              } else if fmt == "json" {
                Some(
                  JSON.stringify(
                    JSON.Array(
                      Belt.Array.map(jsonRows, row => {
                        let obj: dict<JSON.t> = Belt.Array.reduce(columns, Dict.make(), (acc, col) => {
                          let v: option<Bindings.Odbc.oDBcValue> = Dict.get(row, col)
                          let jsonVal: JSON.t = switch v {
                          | Some(Bindings.Odbc.Null) => JSON.Null
                          | Some(Bindings.Odbc.Int(i)) => JSON.Number(Float.fromInt(i))
                          | Some(Bindings.Odbc.Float(f)) => JSON.Number(f)
                          | Some(Bindings.Odbc.Bool(b)) => JSON.Boolean(b)
                          | Some(Bindings.Odbc.Str(s)) => JSON.String(s)
                          | Some(Bindings.Odbc.DateTime(d)) => JSON.String(Date.toISOString(d))
                          | Some(Bindings.Odbc.Buffer(b)) => JSON.String(%raw("buf => buf.toString('base64')")(b))
                          | None => JSON.Null
                          }
                          Dict.set(acc, col, jsonVal)
                          acc
                        })
                        JSON.Object(obj)
                      }),
                    ),
                  ),
                )
              } else {
                None
              }
              switch contentOpt {
              | None => Promise.resolve(Error(Errors.validationError("unsupported export format: " ++ fmt)))
              | Some(content) => {
                  let _written: unit = NodeJs.Fs.writeFileSync(filePath, NodeJs.Buffer.fromString(content))
                  let result: Interfaces.mutationResult = {success: true, affected: rowCount, error: None}
                  Promise.resolve(Ok(result))
                }
              }
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
// _lstatFile — get file size and mtime via node:fs lstatSync
// Returns (size_bytes, modified_iso) — (0, "") on error
// ---------------------------------------------------------------------------

let _lstatFile = (path: string): (int, string) => {
  try {
    let stats: NodeJs.Fs.Stats.t = NodeJs.Fs.lstatSync(#String(path))
    let modified: string = Date.toISOString(Date.fromTime(stats.mtimeMs))
    (stats.size, modified)
  } catch {
  | _ => (0, "")
  }
}

// ---------------------------------------------------------------------------
// _mapMsysType — map MSysObjects Type code to statistics key
// Returns Some(("tables"|"queries"|"forms"|"reports"|"macros"|"modules", count))
// or None for unmapped types
// ---------------------------------------------------------------------------

let _mapMsysType = (typeCode: int, count: int): option<(string, int)> => {
  switch typeCode {
  | 1 | 4 | 6 => Some(("tables", count))
  | 5 => Some(("queries", count))
  | -32768 => Some(("forms", count))
  | -32764 => Some(("reports", count))
  | -32766 => Some(("macros", count))
  | -32761 => Some(("modules", count))
  | _ => None
  }
}

// ---------------------------------------------------------------------------
// getDatabaseStatistics — REQ-S11
// Connected: query MSysObjects GROUP BY Type → map codes to counts
// MSys denied: fall back to getTables() count, log warning
// Disconnected: empty counts, empty file, no warning
// ---------------------------------------------------------------------------

let getDatabaseStatistics = (adapter: t): Promise.t<result<dict<JSON.t>, Errors.t>> => {
  switch adapter.connection {
  | None => {
      // Disconnected: zero counts, empty file, no warning
      let stats: dict<JSON.t> = Dict.fromArray([
        ("success", JSON.Boolean(true)),
        ("tables", JSON.Number(0.0)),
        ("queries", JSON.Number(0.0)),
        ("forms", JSON.Number(0.0)),
        ("reports", JSON.Number(0.0)),
        ("macros", JSON.Number(0.0)),
        ("modules", JSON.Number(0.0)),
        ("file_name", JSON.String("")),
        ("file_size_bytes", JSON.Number(0.0)),
        ("file_modified", JSON.String("")),
        ("access_version", JSON.Null),
        ("com_available", JSON.Boolean(false)),
        ("warning", JSON.Null),
      ])
      Promise.resolve(Ok(stats))
    }
  | Some(conn) => {
      let sql = "SELECT Type, Count(*) AS Count FROM MSysObjects GROUP BY Type"
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Error(_) => {
              // MSysObjects denied — fall back to getTables count
              conn.tables(~tableType=Some("TABLE"))
                ->Promise.then(tableResult => {
                  let tableCount = switch tableResult {
                  | Ok(rows) => Belt.Array.length(rows)
                  | Error(_) => 0
                  }
                  let (size, modified) = switch adapter.dbPath {
                  | Some(path) => _lstatFile(path)
                  | None => (0, "")
                  }
                  let stats: dict<JSON.t> = Dict.fromArray([
                    ("success", JSON.Boolean(true)),
                    ("tables", JSON.Number(Float.fromInt(tableCount))),
                    ("queries", JSON.Number(0.0)),
                    ("forms", JSON.Number(0.0)),
                    ("reports", JSON.Number(0.0)),
                    ("macros", JSON.Number(0.0)),
                    ("modules", JSON.Number(0.0)),
                    ("file_name", JSON.String(switch adapter.dbPath {
                      | Some(p) => %raw("s => s.split(/[\\\\/]/).pop()")(p)
                      | None => ""
                    })),
                    ("file_size_bytes", JSON.Number(Float.fromInt(size))),
                    ("file_modified", JSON.String(modified)),
                    ("access_version", JSON.Null),
                    ("com_available", JSON.Boolean(false)),
                    ("warning", JSON.String("MSysObjects access denied — table count from cursor.tables(), other counts unavailable")),
                  ])
                  Promise.resolve(Ok(stats))
                })
                ->Promise.catch(_e => {
                  let emptyStats: dict<JSON.t> = Dict.fromArray([
                    ("success", JSON.Boolean(true)),
                    ("tables", JSON.Number(0.0)),
                    ("queries", JSON.Number(0.0)),
                    ("forms", JSON.Number(0.0)),
                    ("reports", JSON.Number(0.0)),
                    ("macros", JSON.Number(0.0)),
                    ("modules", JSON.Number(0.0)),
                    ("file_name", JSON.String("")),
                    ("file_size_bytes", JSON.Number(0.0)),
                    ("file_modified", JSON.String("")),
                    ("access_version", JSON.Null),
                    ("com_available", JSON.Boolean(false)),
                    ("warning", JSON.String("MSysObjects access denied — table count from cursor.tables(), other counts unavailable")),
                  ])
                  Promise.resolve(Ok(emptyStats))
                })
            }
          | Ok(r) => {
              // Aggregate from MSysObjects
              let tables = ref(0)
              let queries = ref(0)
              let forms = ref(0)
              let reports = ref(0)
              let macros = ref(0)
              let modules = ref(0)
              let _procRows = Belt.Array.map(r.rows, row => {
                let entries: array<(string, Bindings.Odbc.oDBcValue)> = %raw("d => Object.entries(d)")(row)
                let typeCode = ref(0)
                let count = ref(0)
                let _ = Belt.Array.map(entries, ((k, v)) => {
                  switch k {
                  | "Type" => switch v {
                    | Bindings.Odbc.Int(i) => typeCode := i
                    | Bindings.Odbc.Float(f) => typeCode := Float.toInt(f)
                    | _ => ()
                    }
                  | "Count" => switch v {
                    | Bindings.Odbc.Int(i) => count := i
                    | Bindings.Odbc.Float(f) => count := Float.toInt(f)
                    | _ => ()
                    }
                  | _ => ()
                  }
                })
                switch _mapMsysType(typeCode.contents, count.contents) {
                | Some(("tables", n)) => tables := n
                | Some(("queries", n)) => queries := n
                | Some(("forms", n)) => forms := n
                | Some(("reports", n)) => reports := n
                | Some(("macros", n)) => macros := n
                | Some(("modules", n)) => modules := n
                | Some(_) | None => ()
                }
              })
              let (size, modified) = switch adapter.dbPath {
              | Some(path) => _lstatFile(path)
              | None => (0, "")
              }
              let stats: dict<JSON.t> = Dict.fromArray([
                ("success", JSON.Boolean(true)),
                ("tables", JSON.Number(Float.fromInt(tables.contents))),
                ("queries", JSON.Number(Float.fromInt(queries.contents))),
                ("forms", JSON.Number(Float.fromInt(forms.contents))),
                ("reports", JSON.Number(Float.fromInt(reports.contents))),
                ("macros", JSON.Number(Float.fromInt(macros.contents))),
                ("modules", JSON.Number(Float.fromInt(modules.contents))),
                ("file_name", JSON.String(switch adapter.dbPath {
                  | Some(p) => %raw("s => s.split(/[\\\\/]/).pop()")(p)
                  | None => ""
                })),
                ("file_size_bytes", JSON.Number(Float.fromInt(size))),
                ("file_modified", JSON.String(modified)),
                ("access_version", JSON.Null),
                ("com_available", JSON.Boolean(false)),
                ("warning", JSON.Null),
              ])
              Promise.resolve(Ok(stats))
            }
          }
        })
        ->Promise.catch(_e => {
          // Unexpected error during MSysObjects query — degrade gracefully
          let emptyStats: dict<JSON.t> = Dict.fromArray([
            ("success", JSON.Boolean(true)),
            ("tables", JSON.Number(0.0)),
            ("queries", JSON.Number(0.0)),
            ("forms", JSON.Number(0.0)),
            ("reports", JSON.Number(0.0)),
            ("macros", JSON.Number(0.0)),
            ("modules", JSON.Number(0.0)),
            ("file_name", JSON.String("")),
            ("file_size_bytes", JSON.Number(0.0)),
            ("file_modified", JSON.String("")),
            ("access_version", JSON.Null),
            ("com_available", JSON.Boolean(false)),
            ("warning", JSON.String("MSysObjects access denied — table count from cursor.tables(), other counts unavailable")),
          ])
          Promise.resolve(Ok(emptyStats))
        })
    }
  }
}

// ---------------------------------------------------------------------------
// _columnSchemaToColumnInfo — convert Interfaces.columnSchema to SqlBuilder.columnInfo
// Used by createTable to build DDL SQL
// ---------------------------------------------------------------------------

let _columnSchemaToColumnInfo = (s: Interfaces.columnSchema): SqlBuilder.columnInfo => {
  {
    name: s.name,
    colType: s.sourceType,
    size: switch s.maxLength {
    | Some(n) => n
    | None => 0
    },
    nullable: s.allowNull,
  }
}

// ---------------------------------------------------------------------------
// createTable — builds SQL via SqlBuilder.createTable, executes, returns Ok(()) on success
// REQ-S7
// ---------------------------------------------------------------------------

let createTable = (
  adapter: t,
  name: string,
  columns: array<Interfaces.columnSchema>,
): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let cols = Belt.Array.map(columns, _columnSchemaToColumnInfo)
      let sql = SqlBuilder.createTable(name, cols)
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
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
// deleteTable — DROP TABLE [name]
// REQ-S7
// ---------------------------------------------------------------------------

let deleteTable = (adapter: t, name: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let sql = SqlBuilder.dropTable(name)
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
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
// createIndex — CREATE [UNIQUE] INDEX ... ON ... (col, ...) (REQ-S7)
// ---------------------------------------------------------------------------

let createIndex = (
  adapter: t,
  name: string,
  table: string,
  columns: array<string>,
  ~unique: bool=false,
  ~ignoreNulls: bool=false,
): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let sql = SqlBuilder.createIndex(~name, ~table, ~columns, ~unique, ~ignore_nulls=ignoreNulls)
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
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
// dropIndex — DROP INDEX ... ON ... (REQ-S7)
// ---------------------------------------------------------------------------

let dropIndex = (
  adapter: t,
  name: string,
  table: string,
): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let sql = SqlBuilder.dropIndex(~name, ~table)
      conn.query(sql, [])
        ->Promise.then(result => {
          switch result {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
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
// _dictToColumnInfo — extract columnInfo from action dict
// ---------------------------------------------------------------------------

let _dictToColumnInfo = (d: dict<JSON.t>): SqlBuilder.columnInfo => {
  let name = _jsonToString(Dict.get(d, "name"))
  let colType = _jsonToString(Dict.get(d, "colType"))
  let size = switch Dict.get(d, "size") {
  | Some(JSON.Number(n)) => Float.toInt(n)
  | _ => 0
  }
  let nullable = switch Dict.get(d, "nullable") {
  | Some(JSON.Boolean(b)) => b
  | _ => true
  }
  {name: name, colType: colType, size: size, nullable: nullable}
}

// ---------------------------------------------------------------------------
// alterTable — handles AddColumn/DropColumn/ModifyColumn; RenameTable/RenameColumn
// return Error(DatabaseError(...)) per REQ-S8
// REQ-S8
// ---------------------------------------------------------------------------

let alterTable = (
  adapter: t,
  name: string,
  actions: array<dict<JSON.t>>,
): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let rec processActions = (
        actionDicts: array<dict<JSON.t>>,
      ): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
        switch Belt.Array.get(actionDicts, 0) {
        | None => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
        | Some(actionDict) => {
            let actionName = switch Dict.get(actionDict, "action") {
            | Some(JSON.String(s)) => s
            | _ => ""
            }
            switch actionName {
            | "add_column" => {
                let colInfo = _dictToColumnInfo(actionDict)
                switch SqlBuilder.alterTable(name, SqlBuilder.AddColumn(colInfo)) {
                | Some(sql) => {
                    conn.query(sql, [])
                      ->Promise.then(result => {
                        switch result {
                        | Ok(_) => processActions(Belt.Array.sliceToEnd(actionDicts, 1))
                        | Error(e) => Promise.resolve(Error(e))
                        }
                      })
                      ->Promise.catch(e => {
                        let msg = _exnMessage(e)
                        Promise.resolve(Error(Errors.databaseError(msg)))
                      })
                  }
                | None => Promise.resolve(Error(Errors.databaseError("alter_table returned None unexpectedly")))
                }
              }
            | "drop_column" => {
                let colName = _jsonToString(Dict.get(actionDict, "name"))
                switch SqlBuilder.alterTable(name, SqlBuilder.DropColumn(colName)) {
                | Some(sql) => {
                    conn.query(sql, [])
                      ->Promise.then(result => {
                        switch result {
                        | Ok(_) => processActions(Belt.Array.sliceToEnd(actionDicts, 1))
                        | Error(e) => Promise.resolve(Error(e))
                        }
                      })
                      ->Promise.catch(e => {
                        let msg = _exnMessage(e)
                        Promise.resolve(Error(Errors.databaseError(msg)))
                      })
                  }
                | None => Promise.resolve(Error(Errors.databaseError("alter_table returned None unexpectedly")))
                }
              }
            | "modify_column" => {
                let colInfo = _dictToColumnInfo(actionDict)
                switch SqlBuilder.alterTable(name, SqlBuilder.ModifyColumn(colInfo)) {
                | Some(sql) => {
                    conn.query(sql, [])
                      ->Promise.then(result => {
                        switch result {
                        | Ok(_) => processActions(Belt.Array.sliceToEnd(actionDicts, 1))
                        | Error(e) => Promise.resolve(Error(e))
                        }
                      })
                      ->Promise.catch(e => {
                        let msg = _exnMessage(e)
                        Promise.resolve(Error(Errors.databaseError(msg)))
                      })
                  }
                | None => Promise.resolve(Error(Errors.databaseError("alter_table returned None unexpectedly")))
                }
              }
            | "rename_table" => {
                Promise.resolve(Error(Errors.databaseError("rename_table is not supported via ODBC. Use WinComAdapter.")))
              }
            | "rename_column" => {
                Promise.resolve(Error(Errors.databaseError("rename_column is not supported via ODBC. Use WinComAdapter.")))
              }
            | _ => {
                // Unknown action — continue with remaining actions
                processActions(Belt.Array.sliceToEnd(actionDicts, 1))
              }
            }
          }
        }
      }
      processActions(actions)
    }
  }
}

// ---------------------------------------------------------------------------
// createQuery — CREATE VIEW [name] AS sql (REQ-S6)
// ---------------------------------------------------------------------------

let createQuery = (
  adapter: t,
  name: string,
  sql: string,
): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let ddl = SqlBuilder.createView(~name, ~sql)
      conn.query(ddl, [])
        ->Promise.then(result => {
          switch result {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
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
// deleteQuery — DROP VIEW [name] (REQ-S6)
// ---------------------------------------------------------------------------

let deleteQuery = (adapter: t, name: string): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let ddl = SqlBuilder.dropView(~name)
      conn.query(ddl, [])
        ->Promise.then(result => {
          switch result {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
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
// setQuerySql — DROP VIEW then CREATE VIEW sequentially; surface first failure
// REQ-S6
// ---------------------------------------------------------------------------

let setQuerySql = (
  adapter: t,
  name: string,
  sql: string,
): Promise.t<result<Interfaces.ddlResult, Errors.t>> => {
  switch _requireConnection(adapter) {
  | None => Promise.resolve(Error(Errors.databaseError("Not connected")))
  | Some(conn) => {
      let dropSql = SqlBuilder.dropView(~name)
      conn.query(dropSql, [])
        ->Promise.then(result => {
          switch result {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(_) => {
              let createSql = SqlBuilder.createView(~name, ~sql)
              conn.query(createSql, [])
                ->Promise.then(result2 => {
                  switch result2 {
          | Ok(_) => Promise.resolve(Ok(({success: true, error: None}: Interfaces.ddlResult)))
          | Error(e) => Promise.resolve(Error(e))
                  }
                })
                ->Promise.catch(e => {
                  let msg = _exnMessage(e)
                  Promise.resolve(Error(Errors.databaseError(msg)))
                })
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
