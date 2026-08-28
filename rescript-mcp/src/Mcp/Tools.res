// Mcp/Tools.res — MCP tool registration via facadeOps seam
// T7a: connect_access, disconnect_access, list_connections, is_connected
// T7b: query_data, insert_data, update_data, delete_data (with B1 __raw__ normalization)
// T7c: get_tables, get_table_schema, get_queries, execute_raw_sql
// facadeOps: typed record injected at registration; tests inject spies.

open Bindings

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// facadeOps — one optional function per MCP tool.
// Production: each Some(...) calls the corresponding Facade.<op>(...) fn.
// Tests: each Some(...) is a spy that records args and returns canned responses.
// All handlers are sync: they call facade ops and return dict<JSON.t> directly.
type facadeOps = {
  connectAccess: option<(string, option<string>, option<string>, option<bool>, option<string>) => dict<JSON.t>>,
  disconnectAccess: option<(option<string>) => dict<JSON.t>>,
  listConnections: option<unit => dict<JSON.t>>,
  isConnected: option<(option<string>) => dict<JSON.t>>,
  setActiveConnection: option<(string) => dict<JSON.t>>,
  getActiveConnection: option<unit => dict<JSON.t>>,
  queryData: option<(string, option<array<JSON.t>>, option<string>) => dict<JSON.t>>,
  insertData: option<(string, JSON.t, option<string>) => dict<JSON.t>>,
  updateData: option<(string, dict<JSON.t>, option<dict<JSON.t>>, option<string>, option<bool>, option<bool>) => dict<JSON.t>>,
  deleteData: option<(string, dict<JSON.t>, option<string>, option<bool>, option<bool>) => dict<JSON.t>>,
  getTables: option<(option<string>) => dict<JSON.t>>,
  getTableSchema: option<(string, option<string>) => dict<JSON.t>>,
  getQueries: option<(option<string>) => dict<JSON.t>>,
  executeRawSql: option<(string, option<string>, option<bool>, option<bool>) => dict<JSON.t>>,
  getRelationships: option<(option<string>) => dict<JSON.t>>,
  getDatabaseStatistics: option<(option<string>) => dict<JSON.t>>,
  exportData: option<(string, string, string, option<string>, option<bool>, option<string>) => dict<JSON.t>>,
}

// toolDef — configuration for one MCP tool registration
type toolDef = {
  name: string,
  description: string,
  inputSchema: McpSdk.zObject,
  handler: (dict<JSON.t>, facadeOps) => JSON.t,
}

// ---------------------------------------------------------------------------
// Shared pass-through input schema.
//
// Handlers parse args defensively themselves, so the schema accepts anything.
// It MUST implement the full Zod-ish surface the SDK probes on tools/call:
// safeParseAsync + parseAsync (the SDK calls the async variants; missing
// them made every real stdio tools/call fail with
// "v3Schema.safeParseAsync is not a function").
// ---------------------------------------------------------------------------

let passThroughSchema: McpSdk.zObject = %raw(`({
  parse: (x) => x,
  parseAsync: async (x) => x,
  safeParse: (x) => ({success: true, data: x}),
  safeParseAsync: async (x) => ({success: true, data: x}),
})`)

let connectAccessSchema: McpSdk.zObject = passThroughSchema

// callConnectAccess — TDD seam: extracts args and forwards to facadeOps
// Exported so tests can call it directly without going through SDK transport.
let callConnectAccess = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.connectAccess {
  | Some(fn) => {
      let dbPath = switch Dict.get(args, "database_path") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      let name = switch Dict.get(args, "name") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
      }
      let password = switch Dict.get(args, "password") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
      }
      let useCom = switch Dict.get(args, "use_com") {
        | Some(JSON.Boolean(b)) => Some(b)
        | _ => None
      }
      let backend = switch Dict.get(args, "backend") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
      }
      JSON.Object(fn(dbPath, name, password, useCom, backend))
    }
  | None => JSON.Object(dict{"error": JSON.String("connectAccess not configured")})
  }
}

// ---------------------------------------------------------------------------
// disconnect_access
// Schema: {name?: string}
// ---------------------------------------------------------------------------

let disconnectAccessSchema: McpSdk.zObject = passThroughSchema

let callDisconnectAccess = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.disconnectAccess {
  | Some(fn) => {
      let name = switch Dict.get(args, "name") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
      }
      JSON.Object(fn(name))
    }
  | None => JSON.Object(dict{"error": JSON.String("disconnectAccess not configured")})
  }
}

// ---------------------------------------------------------------------------
// list_connections
// Schema: {} (no args)
// ---------------------------------------------------------------------------

let listConnectionsSchema: McpSdk.zObject = passThroughSchema

let callListConnections = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.listConnections {
  | Some(fn) => {
      JSON.Object(fn())
    }
  | None => JSON.Object(dict{"error": JSON.String("listConnections not configured")})
  }
}

// ---------------------------------------------------------------------------
// is_connected
// Schema: {name?: string}
// ---------------------------------------------------------------------------

let isConnectedSchema: McpSdk.zObject = passThroughSchema

let callIsConnected = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.isConnected {
  | Some(fn) => {
      let name = switch Dict.get(args, "name") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
      }
      JSON.Object(fn(name))
    }
  | None => JSON.Object(dict{"error": JSON.String("isConnected not configured")})
  }
}

// ---------------------------------------------------------------------------
// where_dict normalization — B1 __raw__ sentinel support
// normalizeWhereDict: converts MCP-level where_dict (string|object|undefined)
// to facade-level whereDict (dict<JSON.t>) with __raw__ wrapping for strings.
// Returns Error(dict) when where_dict is absent or empty.
// ---------------------------------------------------------------------------

let normalizeWhereDict = (whereDictArg: option<JSON.t>): result<dict<JSON.t>, dict<JSON.t>> => {
  switch whereDictArg {
  | Some(JSON.String(s)) =>
      if s == "" {
        Error(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: where_dict string is not a valid WHERE clause")})
      } else {
        Ok(dict{"__raw__": JSON.String(s)})
      }
  | Some(JSON.Object(d)) =>
      let entries = Js.Dict.entries(d)
      if Belt.Array.length(entries) == 0 {
        Error(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: where_dict is required (non-empty object or non-empty raw WHERE string)")})
      } else {
        Ok(d)
      }
  | Some(_) =>
      Error(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: where_dict must be an object or a raw WHERE string")})
  | None =>
      Error(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: where_dict is required (non-empty object or non-empty raw WHERE string)")})
  }
}

// ---------------------------------------------------------------------------
// query_data
// Schema: {sql: string (required), params?: array<unknown> (default []), connection_name?: string (default "default")}
// ---------------------------------------------------------------------------

let queryDataSchema: McpSdk.zObject = passThroughSchema

let callQueryData = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.queryData {
  | Some(fn) => {
      let sql = switch Dict.get(args, "sql") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      if sql == "" {
        JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("sql is required")})
      } else {
        let params = switch Dict.get(args, "params") {
        | Some(JSON.Array(arr)) => Some(arr)
        | _ => None
        }
        let name = switch Dict.get(args, "connection_name") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
        }
        JSON.Object(fn(sql, params, name))
      }
    }
  | None => JSON.Object(dict{"error": JSON.String("queryData not configured")})
  }
}

// ---------------------------------------------------------------------------
// insert_data
// Schema: {table_name: string (required), data: object|array<object> (required), connection_name?: string (default "default")}
// ---------------------------------------------------------------------------

let insertDataSchema: McpSdk.zObject = passThroughSchema

let callInsertData = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.insertData {
  | Some(fn) => {
      let tableName = switch Dict.get(args, "table_name") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      let data = switch Dict.get(args, "data") {
        | Some(d) => d
        | _ => JSON.Null
      }
      let name = switch Dict.get(args, "connection_name") {
      | Some(JSON.String(s)) => Some(s)
      | _ => None
      }
      JSON.Object(fn(tableName, data, name))
    }
  | None => JSON.Object(dict{"error": JSON.String("insertData not configured")})
  }
}

// ---------------------------------------------------------------------------
// update_data
// Schema: {table_name, set_dict, where_dict?: object|string, connection_name?, confirm?: bool, dry_run?: bool}
// ---------------------------------------------------------------------------

let updateDataSchema: McpSdk.zObject = passThroughSchema

let callUpdateData = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.updateData {
  | Some(fn) => {
      let tableName = switch Dict.get(args, "table_name") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      let setDict = switch Dict.get(args, "set_dict") {
        | Some(JSON.Object(d)) => d
        | _ => dict{}
      }
      let whereDictArg = Dict.get(args, "where_dict")
      let dryRun = switch Dict.get(args, "dry_run") {
        | Some(JSON.Boolean(b)) => Some(b)
        | _ => None
      }
      // Short-circuit for dry_run=true before normalization
      if dryRun == Some(true) {
        let result = Dict.make()
        Dict.set(result, "dry_run", JSON.Boolean(true))
        JSON.Object(result)
      } else {
        let normalized = normalizeWhereDict(whereDictArg)
        switch normalized {
        | Error(err) => JSON.Object(err)
        | Ok(whereDict) => {
            let confirm = switch Dict.get(args, "confirm") {
            | Some(JSON.Boolean(b)) => Some(b)
            | _ => None
            }
            let name = switch Dict.get(args, "connection_name") {
            | Some(JSON.String(s)) => Some(s)
            | _ => None
            }
            JSON.Object(fn(tableName, setDict, Some(whereDict), name, confirm, dryRun))
          }
        }
      }
    }
  | None => JSON.Object(dict{"error": JSON.String("updateData not configured")})
  }
}

// ---------------------------------------------------------------------------
// delete_data
// Schema: {table_name, where_dict?: object|string, connection_name?, confirm?: bool, dry_run?: bool}
// ---------------------------------------------------------------------------

let deleteDataSchema: McpSdk.zObject = passThroughSchema

let callDeleteData = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.deleteData {
  | Some(fn) => {
      let tableName = switch Dict.get(args, "table_name") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      let whereDictArg = Dict.get(args, "where_dict")
      let dryRun = switch Dict.get(args, "dry_run") {
        | Some(JSON.Boolean(b)) => Some(b)
        | _ => None
      }
      // Short-circuit for dry_run=true before normalization
      if dryRun == Some(true) {
        let result = Dict.make()
        Dict.set(result, "dry_run", JSON.Boolean(true))
        JSON.Object(result)
      } else {
        let normalized = normalizeWhereDict(whereDictArg)
        switch normalized {
        | Error(err) => JSON.Object(err)
        | Ok(whereDict) => {
            let confirm = switch Dict.get(args, "confirm") {
            | Some(JSON.Boolean(b)) => Some(b)
            | _ => None
            }
            let name = switch Dict.get(args, "connection_name") {
            | Some(JSON.String(s)) => Some(s)
            | _ => None
            }
            JSON.Object(fn(tableName, whereDict, name, confirm, dryRun))
          }
        }
      }
    }
  | None => JSON.Object(dict{"error": JSON.String("deleteData not configured")})
  }
}

// ---------------------------------------------------------------------------
// get_tables
// Schema: {connection_name?: string (default "default")}
// ---------------------------------------------------------------------------

let getTablesSchema: McpSdk.zObject = passThroughSchema

let callGetTables = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.getTables {
  | Some(fn) => {
      let name = switch Dict.get(args, "connection_name") {
      | Some(JSON.String(s)) => Some(s)
      | _ => None
      }
      JSON.Object(fn(name))
    }
  | None => JSON.Object(dict{"error": JSON.String("getTables not configured")})
  }
}

// ---------------------------------------------------------------------------
// get_table_schema
// Schema: {table_name: string (required), connection_name?: string (default "default")}
// ---------------------------------------------------------------------------

let getTableSchemaSchema: McpSdk.zObject = passThroughSchema

let callGetTableSchema = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.getTableSchema {
  | Some(fn) => {
      let tableName = switch Dict.get(args, "table_name") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      if tableName == "" {
        JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: table_name is required")})
      } else {
        let name = switch Dict.get(args, "connection_name") {
        | Some(JSON.String(s)) => Some(s)
        | _ => None
        }
        JSON.Object(fn(tableName, name))
      }
    }
  | None => JSON.Object(dict{"error": JSON.String("getTableSchema not configured")})
  }
}

// ---------------------------------------------------------------------------
// get_queries
// Schema: {connection_name?: string (default "default")}
// ---------------------------------------------------------------------------

let getQueriesSchema: McpSdk.zObject = passThroughSchema

let callGetQueries = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.getQueries {
  | Some(fn) => {
      let name = switch Dict.get(args, "connection_name") {
      | Some(JSON.String(s)) => Some(s)
      | _ => None
      }
      JSON.Object(fn(name))
    }
  | None => JSON.Object(dict{"error": JSON.String("getQueries not configured")})
  }
}

// ---------------------------------------------------------------------------
// execute_raw_sql
// Schema: {sql: string (required), connection_name?: string, confirm?: bool, dry_run?: bool}
// dangerous pattern: ^\s*(drop|delete|update)\b (case-insensitive)
// ---------------------------------------------------------------------------

let executeRawSqlSchema: McpSdk.zObject = passThroughSchema

// isDangerousSql: returns true if SQL matches ^\s*(drop|delete|update)\b (case-insensitive)
let isDangerousSql = (sql: string): bool => {
  let trimmed = Js.String.trim(sql)
  let lowered = Js.String.toLowerCase(trimmed)
  let pattern = %raw(`/^\s*(drop|delete|update)\b/i`)
  %raw(`(pattern, lowered) => pattern.test(lowered)`)(pattern, lowered)
}

let callExecuteRawSql = (args: dict<JSON.t>, ops: facadeOps): JSON.t => {
  switch ops.executeRawSql {
  | Some(fn) => {
      let sql = switch Dict.get(args, "sql") {
        | Some(JSON.String(s)) => s
        | _ => ""
      }
      if sql == "" {
        JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: sql is required")})
      } else {
        let dryRun = switch Dict.get(args, "dry_run") {
        | Some(JSON.Boolean(b)) => Some(b)
        | _ => None
        }
        // Short-circuit for dry_run=true
        if dryRun == Some(true) {
          let result = Dict.make()
          Dict.set(result, "success", JSON.Boolean(true))
          Dict.set(result, "dry_run", JSON.Boolean(true))
          Dict.set(result, "sql", JSON.String(sql))
          JSON.Object(result)
        } else {
          let confirm = switch Dict.get(args, "confirm") {
          | Some(JSON.Boolean(b)) => Some(b)
          | _ => None
          }
          let name = switch Dict.get(args, "connection_name") {
          | Some(JSON.String(s)) => Some(s)
          | _ => None
          }
          // Guard: dangerous SQL without confirm
          if isDangerousSql(sql) && confirm != Some(true) {
            JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("confirm=True required for execute_raw_sql")})
          } else {
            JSON.Object(fn(sql, name, confirm, dryRun))
          }
        }
      }
    }
  | None => JSON.Object(dict{"error": JSON.String("executeRawSql not configured")})
  }
}

// ---------------------------------------------------------------------------
// tools list — all 11 registered tools (T7a: 4 connection, T7b: 4 CRUD, T7c: 4 schema)
// Each entry matches SDK registerTool(server, name, {description, inputSchema}, callback)
// ---------------------------------------------------------------------------

let makeTools = (ops: facadeOps): array<toolDef> => [
  {
    name: "connect_access",
    description: "Connect to an Access database (.accdb, .mdb) using ODBC.",
    inputSchema: connectAccessSchema,
    handler: callConnectAccess,
  },
  {
    name: "disconnect_access",
    description: "Disconnect a named Access database connection.",
    inputSchema: disconnectAccessSchema,
    handler: callDisconnectAccess,
  },
  {
    name: "list_connections",
    description: "List all active database connections and their status.",
    inputSchema: listConnectionsSchema,
    handler: callListConnections,
  },
  {
    name: "is_connected",
    description: "Check whether a named connection is currently active.",
    inputSchema: isConnectedSchema,
    handler: callIsConnected,
  },
  {
    name: "query_data",
    description: "Execute a SQL SELECT query and return rows.",
    inputSchema: queryDataSchema,
    handler: callQueryData,
  },
  {
    name: "insert_data",
    description: "Insert one or more records into a table.",
    inputSchema: insertDataSchema,
    handler: callInsertData,
  },
  {
    name: "update_data",
    description: "Update records in a table matching a WHERE clause.",
    inputSchema: updateDataSchema,
    handler: callUpdateData,
  },
  {
    name: "delete_data",
    description: "Delete records from a table matching a WHERE clause.",
    inputSchema: deleteDataSchema,
    handler: callDeleteData,
  },
  {
    name: "get_tables",
    description: "List all user tables in the connected database.",
    inputSchema: getTablesSchema,
    handler: callGetTables,
  },
  {
    name: "get_table_schema",
    description: "Get the field schema for a specific table.",
    inputSchema: getTableSchemaSchema,
    handler: callGetTableSchema,
  },
  {
    name: "get_queries",
    description: "List all saved queries in the database.",
    inputSchema: getQueriesSchema,
    handler: callGetQueries,
  },
  {
    name: "execute_raw_sql",
    description: "Execute arbitrary SQL (including DDL) with safety guards.",
    inputSchema: executeRawSqlSchema,
    handler: callExecuteRawSql,
  },
]

// ---------------------------------------------------------------------------
// registerAll — register all tools with an McpServer instance
// Called once at server startup with real facadeOps; called per-test with spy ops.
// Uses %raw to create callbacks that bridge ReScript handler → SDK callback.
// ---------------------------------------------------------------------------

let registerAll = (server: McpSdk.mcpServer, ops: facadeOps): unit => {
  let toolDefs = makeTools(ops)
  Belt.Array.forEach(toolDefs, def => {
    // Use %raw to create the SDK callback from the handler.
    // The SDK's registerTool expects (args: JSON.t) => JSON.t.
    // Our handler takes (args: dict<JSON.t>) => JSON.t.
    let sdkCallback = %raw(`(handler, ops) => {
      return (args) => {
        // args is JSON.t — convert to dict if needed, then call handler
        const d = typeof args === 'object' && args !== null ? args : {};
        return handler(d, ops);
      };
    }`)(def.handler, ops)
    ignore(McpSdk.registerTool(
      server,
      def.name,
      {description: def.description, inputSchema: def.inputSchema},
      sdkCallback,
    ))
  })
}
