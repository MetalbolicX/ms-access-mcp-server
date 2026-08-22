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
