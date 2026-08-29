// Mcp/Server.res — MCP stdio server bootstrap
// T8: bootstraps the MCP server using StdioServerTransport and real Facade wiring.
// Creates SDK callbacks directly that call Facade operations.
// Does NOT live in the Mcp barrel (Mcp.res) to avoid potential module cycles.

open McpSdk

// ---------------------------------------------------------------------------
// envelopeResult — route every runtime tool result through the MCP envelope
// (T4). Raw facade dicts at the top level of a CallToolResult leak protocol
// noise and hide errors from strict clients (content:[] + no isError).
// ---------------------------------------------------------------------------

let envelopeResult = (d: dict<JSON.t>): JSON.t =>
  Mcp.Envelope.transcribeJson(JSON.Object(d))

// ---------------------------------------------------------------------------
// Version — ESM-safe read of package.json relative to this compiled module.
// ---------------------------------------------------------------------------

// ESM-safe: resolve package.json relative to this compiled module's URL.
// (require() does not exist in ESM — "type": "module" is set.)
@module("node:fs") external readFileSyncUtf8: (string, string) => string = "readFileSync"

let getVersion = (): string => {
  // import.meta.dirname (Node >=20.11; engines floor is >=24) resolves to
  // src/Mcp/ at runtime — package.json sits two levels up.
  let pkgPath: string = %raw(`import.meta.dirname + "/../../package.json"`)
  let json = Js.Json.parseExn(readFileSyncUtf8(pkgPath, "utf8"))
  switch Js.Json.decodeObject(json) {
  | Some(obj) =>
    switch Js.Dict.get(obj, "version") {
    | Some(v) => Js.Json.decodeString(v)->Option.getWithDefault("0.0.0")
    | None => "0.0.0"
    }
  | None => "0.0.0"
  }
}

// ---------------------------------------------------------------------------
// Argument parsing helpers — extract typed args from JSON.t dict
// ---------------------------------------------------------------------------

// parseArgs: convert JSON.t args to dict (handles null/non-object gracefully)
let parseArgs = (args: JSON.t): dict<JSON.t> => {
  switch args {
  | JSON.Object(d) => d
  | _ => dict{}
  }
}

let getString = (d: dict<JSON.t>, key: string): string => {
  switch Dict.get(d, key) {
  | Some(JSON.String(s)) => s
  | _ => ""
  }
}

let getStringOpt = (d: dict<JSON.t>, key: string): option<string> => {
  switch Dict.get(d, key) {
  | Some(JSON.String(s)) => Some(s)
  | _ => None
  }
}

let getBoolOpt = (d: dict<JSON.t>, key: string): option<bool> => {
  switch Dict.get(d, key) {
  | Some(JSON.Boolean(b)) => Some(b)
  | _ => None
  }
}

let getArrayOpt = (d: dict<JSON.t>, key: string): option<array<JSON.t>> => {
  switch Dict.get(d, key) {
  | Some(JSON.Array(arr)) => Some(arr)
  | _ => None
  }
}

// ---------------------------------------------------------------------------
// SDK callbacks — each calls the corresponding Facade op and returns JSON.t
// All return Promise<JSON.t> (the SDK toolCallback signature).
// ---------------------------------------------------------------------------

let makeConnectAccessCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let dbPath = getString(d, "database_path")
    let name = getStringOpt(d, "name")
    let password = getStringOpt(d, "password")
    let useCom = getBoolOpt(d, "use_com")
    let backend = getStringOpt(d, "backend")
    Facade.connectAccess(facade, ~dbPath, ~name?, ~useCom?, ~password?, ~backend?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeDisconnectAccessCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getStringOpt(d, "name")
    Facade.disconnectAccess(facade, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeListConnectionsCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. _args) => {
    let result = Facade.listConnections(facade)
    Promise.resolve(envelopeResult(result))
  }
}

let makeIsConnectedCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getStringOpt(d, "name")
    let result = Facade.isConnected(facade, ~name?)
    Promise.resolve(envelopeResult(result))
  }
}

let makeSetActiveConnectionCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getString(d, "name")
    Facade.setActiveConnection(facade, ~name)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeGetActiveConnectionCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. _args) => {
    let result = Facade.getActiveConnection(facade)
    Promise.resolve(envelopeResult(result))
  }
}

let makeQueryDataCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let sql = getString(d, "sql")
    if sql == "" {
      Promise.resolve(envelopeResult(dict{"success": JSON.Boolean(false), "error": JSON.String("sql is required")}))
    } else {
      let params = getArrayOpt(d, "params")
      let name = getStringOpt(d, "connection_name")
      Facade.queryData(facade, ~sql, ~params?, ~name?)
        ->Promise.then(result => Promise.resolve(envelopeResult(result)))
    }
  }
}

let makeInsertDataCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let tableName = getString(d, "table_name")
    let data = switch Dict.get(d, "data") {
      | Some(d) => d
      | _ => JSON.Null
    }
    let name = getStringOpt(d, "connection_name")
    Facade.insertData(facade, ~table=tableName, ~data, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeUpdateDataCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let tableName = getString(d, "table_name")
    let setDict = switch Dict.get(d, "set_dict") {
      | Some(JSON.Object(obj)) => obj
      | _ => dict{}
    }
    let whereDictArg = Dict.get(d, "where_dict")
    let dryRun = getBoolOpt(d, "dry_run")
    // Short-circuit for dry_run=true
    if dryRun == Some(true) {
      Promise.resolve(envelopeResult(dict{"dry_run": JSON.Boolean(true)}))
    } else {
      // Normalize where_dict (same logic as Tools.res)
      let normalized = Mcp.Tools.normalizeWhereDict(whereDictArg)
      switch normalized {
      | Error(err) => Promise.resolve(JSON.Object(err))
      | Ok(whereDict) => {
          let confirm = getBoolOpt(d, "confirm")
          let name = getStringOpt(d, "connection_name")
          Facade.updateData(facade, ~table=tableName, ~setDict, ~whereDict=?Some(whereDict), ~name?, ~confirm?, ~dryRun?)
            ->Promise.then(result => Promise.resolve(envelopeResult(result)))
        }
      }
    }
  }
}

let makeDeleteDataCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let tableName = getString(d, "table_name")
    let whereDictArg = Dict.get(d, "where_dict")
    let dryRun = getBoolOpt(d, "dry_run")
    // Short-circuit for dry_run=true
    if dryRun == Some(true) {
      Promise.resolve(envelopeResult(dict{"dry_run": JSON.Boolean(true)}))
    } else {
      let normalized = Mcp.Tools.normalizeWhereDict(whereDictArg)
      switch normalized {
      | Error(err) => Promise.resolve(JSON.Object(err))
      | Ok(whereDict) => {
          let confirm = getBoolOpt(d, "confirm")
          let name = getStringOpt(d, "connection_name")
          Facade.deleteData(facade, ~table=tableName, ~whereDict, ~name?, ~confirm?, ~dryRun?)
            ->Promise.then(result => Promise.resolve(envelopeResult(result)))
        }
      }
    }
  }
}

let makeGetTablesCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getStringOpt(d, "connection_name")
    Facade.getTables(facade, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeGetTableSchemaCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let tableName = getString(d, "table_name")
    if tableName == "" {
      Promise.resolve(envelopeResult(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: table_name is required")}))
    } else {
      let name = getStringOpt(d, "connection_name")
      Facade.getTableSchema(facade, ~table=tableName, ~name?)
        ->Promise.then(result => Promise.resolve(envelopeResult(result)))
    }
  }
}

let makeGetQueriesCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getStringOpt(d, "connection_name")
    Facade.getQueries(facade, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeExecuteRawSqlCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let sql = getString(d, "sql")
    if sql == "" {
      Promise.resolve(envelopeResult(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: sql is required")}))
    } else {
      let dryRun = getBoolOpt(d, "dry_run")
      if dryRun == Some(true) {
        Promise.resolve(envelopeResult(dict{
          "success": JSON.Boolean(true),
          "dry_run": JSON.Boolean(true),
          "sql": JSON.String(sql),
        }))
      } else {
        let confirm = getBoolOpt(d, "confirm")
        let name = getStringOpt(d, "connection_name")
        // Guard: dangerous SQL without confirm
        if Mcp.Tools.isDangerousSql(sql) && confirm != Some(true) {
          Promise.resolve(envelopeResult(dict{"success": JSON.Boolean(false), "error": JSON.String("confirm=True required for execute_raw_sql")}))
        } else {
          Facade.executeRawSql(facade, ~sql, ~name?, ~confirm?, ~dryRun?)
            ->Promise.then(result => Promise.resolve(envelopeResult(result)))
        }
      }
    }
  }
}

let makeGetRelationshipsCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getStringOpt(d, "connection_name")
    Facade.getRelationships(facade, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeGetDatabaseStatisticsCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let name = getStringOpt(d, "connection_name")
    Facade.getDatabaseStatistics(facade, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

let makeExportDataCallback = (facade: Facade.t): McpSdk.toolCallback => {
  (. args) => {
    let d = parseArgs(args)
    let sql = getString(d, "sql")
    let filePath = getString(d, "file_path")
    let format = getString(d, "format")
    let delimiter = getStringOpt(d, "delimiter")
    let header = getBoolOpt(d, "header")
    let name = getStringOpt(d, "connection_name")
    Facade.exportData(facade, ~sql, ~filePath, ~format, ~delimiter?, ~header?, ~name?)
      ->Promise.then(result => Promise.resolve(envelopeResult(result)))
  }
}

// ---------------------------------------------------------------------------
// registerTools — register all 11 MCP tools with the server
// Uses SDK callbacks that call Facade operations directly (bypasses facadeOps).
// ---------------------------------------------------------------------------

let registerTools = (server: mcpServer, facade: Facade.t): unit => {
  // Tool definitions: (name, description, inputSchema, callback)
  let tools = [
    (
      "connect_access",
      "Connect to an Access database (.accdb, .mdb) using ODBC.",
      Mcp.Tools.connectAccessSchema,
      makeConnectAccessCallback(facade),
    ),
    (
      "disconnect_access",
      "Disconnect a named Access database connection.",
      Mcp.Tools.disconnectAccessSchema,
      makeDisconnectAccessCallback(facade),
    ),
    (
      "list_connections",
      "List all active database connections and their status.",
      Mcp.Tools.listConnectionsSchema,
      makeListConnectionsCallback(facade),
    ),
    (
      "is_connected",
      "Check whether a named connection is currently active.",
      Mcp.Tools.isConnectedSchema,
      makeIsConnectedCallback(facade),
    ),
    (
      "query_data",
      "Execute a SQL SELECT query and return rows.",
      Mcp.Tools.queryDataSchema,
      makeQueryDataCallback(facade),
    ),
    (
      "insert_data",
      "Insert one or more records into a table.",
      Mcp.Tools.insertDataSchema,
      makeInsertDataCallback(facade),
    ),
    (
      "update_data",
      "Update records in a table matching a WHERE clause.",
      Mcp.Tools.updateDataSchema,
      makeUpdateDataCallback(facade),
    ),
    (
      "delete_data",
      "Delete records from a table matching a WHERE clause.",
      Mcp.Tools.deleteDataSchema,
      makeDeleteDataCallback(facade),
    ),
    (
      "get_tables",
      "List all user tables in the connected database.",
      Mcp.Tools.getTablesSchema,
      makeGetTablesCallback(facade),
    ),
    (
      "get_table_schema",
      "Get the field schema for a specific table.",
      Mcp.Tools.getTableSchemaSchema,
      makeGetTableSchemaCallback(facade),
    ),
    (
      "get_queries",
      "List all saved queries in the database.",
      Mcp.Tools.getQueriesSchema,
      makeGetQueriesCallback(facade),
    ),
    (
      "execute_raw_sql",
      "Execute arbitrary SQL (including DDL) with safety guards.",
      Mcp.Tools.executeRawSqlSchema,
      makeExecuteRawSqlCallback(facade),
    ),
  ]

  Array.forEach(tools, ((name, description, inputSchema, callback)) => {
    ignore(McpSdk.registerTool(
      server,
      name,
      {description, inputSchema},
      callback,
    ))
  })
}

// ---------------------------------------------------------------------------
// shutdown — disconnect all named connections and close the MCP server
// ---------------------------------------------------------------------------

let shutdown = (server: mcpServer, facade: Facade.t): Promise.t<unit> => {
  let connections = Facade.listConnections(facade)
  let connNames = Js.Dict.keys(connections)
  let rec disconnectAll = (names: array<string>): Promise.t<unit> => {
    if Array.length(names) == 0 {
      Promise.resolve()
    } else {
      let name = names[0]->Option.getWithDefault("default")
      let rest = Array.slice(names, ~start=1)
      Facade.disconnectAccess(facade, ~name)
        ->Promise.then(_ => disconnectAll(rest))
    }
  }
  disconnectAll(connNames)
    ->Promise.then(_ => mcpClose(server))
    ->Promise.then(_ => Promise.resolve())
}

// ---------------------------------------------------------------------------
// waitForSignal — resolves when SIGINT or SIGTERM is received
// ---------------------------------------------------------------------------

let waitForSignal = (): Promise.t<unit> => {
  %raw(`() => {
    return new Promise((resolve) => {
      const onSignal = () => { resolve(); };
      process.on('SIGINT', onSignal);
      process.on('SIGTERM', onSignal);
    });
  }`)()
}

// ---------------------------------------------------------------------------
// run — main entry: builds server with real Facade and runs stdio transport
// ---------------------------------------------------------------------------

let run = (): Promise.t<unit> => {
  let version = getVersion()
  let serverInfo = {name: "MS Access MCP Server", version: version}

  // Respect the documented env contract: ACCESS_MCP_READONLY and
  // ACCESS_MCP_ALLOWED_DIRS (semicolon-separated; defaults to user home).
  let facade = Facade.make(
    ~factory=Composition.realFactory,
    ~comAvailable=false,
    ~readonly=Config.readonly,
    ~allowedDirs=Config.allowedDirs,
  )

  // Create MCP server
  let server = newMcpServer(serverInfo)

  // Register all tools with direct Facade callbacks
  registerTools(server, facade)

  // Create stdio transport
  let transport = newStdioServerTransport()

  // Connect transport then wait for signal
  mcpConnect(server, transport)
    ->Promise.then(_ => waitForSignal())
    ->Promise.catch(_ => waitForSignal())
    ->Promise.then(_ => shutdown(server, facade))
    ->Promise.then(_ => Promise.resolve())
}

// ---------------------------------------------------------------------------
// runWith — test entry: connect provided server/transport/ops without signals
// ---------------------------------------------------------------------------

let runWith = (server: mcpServer, transport: transport): Promise.t<unit> => {
  mcpConnect(server, transport)
    ->Promise.then(_ => Promise.resolve())
    ->Promise.catch(_ => Promise.resolve())
}
