// McpServerTest.res — T9: in-process MCP server integration tests
// Uses InMemoryTransport.createLinkedPair() to test full MCP protocol:
// initialize handshake, tools/list, tools/call (get_tables, connect_access).
// NO real database needed for handshake/list tests; ACCESS_TEST_DB guards
// the tool-call-with-real-backend tests.

open Test

// ---------------------------------------------------------------------------
// Version helper (same logic as Mcp/Server.res; inlined to avoid import)
// ---------------------------------------------------------------------------

let getVersion = (): string => {
  // Hardcoded for ESM compatibility — require() not available in ESM context
  "1.0.0"
}

// ---------------------------------------------------------------------------
// JSON-RPC client over InMemoryTransport
// Uses a JS global as pending-request map to correlate request IDs with
// promise resolvers. This avoids any ReScript-specific async queue complexity.
// ---------------------------------------------------------------------------

type jsonRpcClient = {
  transport: Bindings.McpSdk.inMemoryTransport,
  mutable nextId: int,
}

let makeClient = (transport: Bindings.McpSdk.inMemoryTransport): jsonRpcClient => {
  {transport: transport, nextId: 0}
}

// sendRequest: sends a JSON-RPC request and returns a Promise.t (plain JS object).
// Single %raw block handles: setting up pending map, onmessage handler, and sending.
// Uses a JS-side resolver closure to correlate request IDs with promise resolve functions.
// Adds a 5-second timeout so tests fail fast if no response arrives.
let sendRequest = (client: jsonRpcClient, method: string, params: JSON.t) => {
  let id = client.nextId
  client.nextId = client.nextId + 1

  Promise.make((resolve, _reject) => {
    // Everything (pending map, onmessage setup, timeout, and send) in one %raw block.
    %raw(`
      (transport, id, method, params, resolve) => {
        // Initialize global pending map
        if (!global.__mcpPending) global.__mcpPending = {};
        const idNum = Number(id);
        const idStr = String(id);

        // Store the resolve function keyed by request id
        global.__mcpPending[idStr] = resolve;

        // Set up onmessage handler on the transport (only once)
        if (!transport.onmessage) {
          transport.onmessage = (msg) => {
            console.log('[sendRequest] got response for method=' + String(method) + ':', JSON.stringify(msg));
            const respId = msg.id !== undefined && msg.id !== null ? String(msg.id) : null;
            if (respId && global.__mcpPending[respId]) {
              global.__mcpPending[respId](msg);
              delete global.__mcpPending[respId];
            }
          };
        }

        // 5-second timeout — if no response, reject with timeout error
        const timeoutId = setTimeout(() => {
          console.log('[sendRequest] TIMEOUT for method=' + String(method));
          if (global.__mcpPending[idStr]) {
            global.__mcpPending[idStr]({
              jsonrpc: '2.0',
              id: idNum,
              error: { message: 'TIMEOUT: no response received in 5s for method: ' + String(method) }
            });
            delete global.__mcpPending[idStr];
          }
        }, 5000);

        // Build and send the JSON-RPC request
        const rpcMsg = {
          jsonrpc: '2.0',
          id: idNum,
          method: String(method),
          params: params,
        };
        console.log('[sendRequest] sending method=' + String(method) + ' id=' + idStr);
        transport.send(rpcMsg).catch(e => {
          clearTimeout(timeoutId);
          console.log('[sendRequest] send error for method=' + String(method) + ':', String(e));
          if (global.__mcpPending[idStr]) {
            global.__mcpPending[idStr]({
              jsonrpc: '2.0',
              id: idNum,
              error: { message: String(e) }
            });
            delete global.__mcpPending[idStr];
          }
        });
      }
    `)(client.transport, id, method, params, resolve)
  })
}

// sendNotification: fires a JSON-RPC notification (no id, no response expected).
// Used for "notifications/initialized" which the MCP spec requires after initialize.
let sendNotification = (client: jsonRpcClient, method: string, params: JSON.t): unit => {
  %raw(`
    (transport, method, params) => {
      const msg = {
        jsonrpc: '2.0',
        method: String(method),
        params: params,
      };
      // fire-and-forget: no catch needed, no response expected
      transport.send(msg);
    }
  `)(client.transport, method, params)
}

// ---------------------------------------------------------------------------
// Tool registration helpers
// Each tool's SDK callbacks wrap the corresponding Facade operations.
// ---------------------------------------------------------------------------

// Tool callback types (from Bindings.McpSdk)
type toolCallback = Bindings.McpSdk.toolCallback

// Helper: extract string from dict
let getStr = (d: dict<JSON.t>, k: string): string => {
  switch Dict.get(d, k) {
  | Some(JSON.String(s)) => s
  | _ => ""
  }
}

let getStrOpt = (d: dict<JSON.t>, k: string): option<string> => {
  switch Dict.get(d, k) {
  | Some(JSON.String(s)) => Some(s)
  | _ => None
  }
}

let getBoolOpt = (d: dict<JSON.t>, k: string): option<bool> => {
  switch Dict.get(d, k) {
  | Some(JSON.Boolean(b)) => Some(b)
  | _ => None
  }
}

let getArrOpt = (d: dict<JSON.t>, k: string): option<array<JSON.t>> => {
  switch Dict.get(d, k) {
  | Some(JSON.Array(a)) => Some(a)
  | _ => None
  }
}

// connect_access callback
let makeConnectAccessCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let dbPath = getStr(d, "database_path")
    let name = getStrOpt(d, "name")
    let password = getStrOpt(d, "password")
    let useCom = getBoolOpt(d, "use_com")
    let backend = getStrOpt(d, "backend")
    Services.Facade.connectAccess(facade, ~dbPath, ~name?, ~useCom?, ~password?, ~backend?)
      ->Promise.then(result => Promise.resolve(JSON.Object(result)))
  }
}

// disconnect_access callback
let makeDisconnectAccessCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let name = getStrOpt(d, "name")
    Services.Facade.disconnectAccess(facade, ~name?)
      ->Promise.then(result => Promise.resolve(JSON.Object(result)))
  }
}

// list_connections callback
let makeListConnectionsCallback = (facade: Services.Facade.t): toolCallback => {
  (. _args) => {
    let result = Services.Facade.listConnections(facade)
    Promise.resolve(JSON.Object(result))
  }
}

// is_connected callback
let makeIsConnectedCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let name = getStrOpt(d, "name")
    let result = Services.Facade.isConnected(facade, ~name?)
    Promise.resolve(JSON.Object(result))
  }
}

// query_data callback
let makeQueryDataCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let sql = getStr(d, "sql")
    if sql == "" {
      Promise.resolve(JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("sql is required")}))
    } else {
      let params = getArrOpt(d, "params")
      let name = getStrOpt(d, "connection_name")
      Services.Facade.queryData(facade, ~sql, ~params?, ~name?)
        ->Promise.then(result => Promise.resolve(JSON.Object(result)))
    }
  }
}

// insert_data callback
let makeInsertDataCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let tableName = getStr(d, "table_name")
    let data = switch Dict.get(d, "data") {
    | Some(d) => d
    | _ => JSON.Null
    }
    let name = getStrOpt(d, "connection_name")
    Services.Facade.insertData(facade, ~table=tableName, ~data, ~name?)
      ->Promise.then(result => Promise.resolve(JSON.Object(result)))
  }
}

// update_data callback
let makeUpdateDataCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let tableName = getStr(d, "table_name")
    let setDict = switch Dict.get(d, "set_dict") {
    | Some(JSON.Object(obj)) => obj
    | _ => dict{}
    }
    let whereDictArg = Dict.get(d, "where_dict")
    let dryRun = getBoolOpt(d, "dry_run")
    if dryRun == Some(true) {
      Promise.resolve(JSON.Object(dict{"dry_run": JSON.Boolean(true)}))
    } else {
      let normalized = Mcp.Tools.normalizeWhereDict(whereDictArg)
      switch normalized {
      | Error(err) => Promise.resolve(JSON.Object(err))
      | Ok(whereDict) => {
          let confirm = getBoolOpt(d, "confirm")
          let name = getStrOpt(d, "connection_name")
          Services.Facade.updateData(facade, ~table=tableName, ~setDict, ~whereDict=?Some(whereDict), ~name?, ~confirm?, ~dryRun?)
            ->Promise.then(result => Promise.resolve(JSON.Object(result)))
        }
      }
    }
  }
}

// delete_data callback
let makeDeleteDataCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let tableName = getStr(d, "table_name")
    let whereDictArg = Dict.get(d, "where_dict")
    let dryRun = getBoolOpt(d, "dry_run")
    if dryRun == Some(true) {
      Promise.resolve(JSON.Object(dict{"dry_run": JSON.Boolean(true)}))
    } else {
      let normalized = Mcp.Tools.normalizeWhereDict(whereDictArg)
      switch normalized {
      | Error(err) => Promise.resolve(JSON.Object(err))
      | Ok(whereDict) => {
          let confirm = getBoolOpt(d, "confirm")
          let name = getStrOpt(d, "connection_name")
          Services.Facade.deleteData(facade, ~table=tableName, ~whereDict, ~name?, ~confirm?, ~dryRun?)
            ->Promise.then(result => Promise.resolve(JSON.Object(result)))
        }
      }
    }
  }
}

// get_tables callback
let makeGetTablesCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let name = getStrOpt(d, "connection_name")
    Services.Facade.getTables(facade, ~name?)
      ->Promise.then(result => Promise.resolve(JSON.Object(result)))
  }
}

// get_table_schema callback
let makeGetTableSchemaCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let tableName = getStr(d, "table_name")
    if tableName == "" {
      Promise.resolve(JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: table_name is required")}))
    } else {
      let name = getStrOpt(d, "connection_name")
      Services.Facade.getTableSchema(facade, ~table=tableName, ~name?)
        ->Promise.then(result => Promise.resolve(JSON.Object(result)))
    }
  }
}

// get_queries callback
let makeGetQueriesCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let name = getStrOpt(d, "connection_name")
    Services.Facade.getQueries(facade, ~name?)
      ->Promise.then(result => Promise.resolve(JSON.Object(result)))
  }
}

// execute_raw_sql callback
let makeExecuteRawSqlCallback = (facade: Services.Facade.t): toolCallback => {
  (. args) => {
    let d = switch args {
    | JSON.Object(obj) => obj
    | _ => dict{}
    }
    let sql = getStr(d, "sql")
    if sql == "" {
      Promise.resolve(JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("Invalid arguments: sql is required")}))
    } else {
      let dryRun = getBoolOpt(d, "dry_run")
      if dryRun == Some(true) {
        Promise.resolve(JSON.Object(dict{
          "success": JSON.Boolean(true),
          "dry_run": JSON.Boolean(true),
          "sql": JSON.String(sql),
        }))
      } else {
        let confirm = getBoolOpt(d, "confirm")
        let name = getStrOpt(d, "connection_name")
        if Mcp.Tools.isDangerousSql(sql) && confirm != Some(true) {
          Promise.resolve(JSON.Object(dict{"success": JSON.Boolean(false), "error": JSON.String("confirm=True required for execute_raw_sql")}))
        } else {
          Services.Facade.executeRawSql(facade, ~sql, ~name?, ~confirm?, ~dryRun?)
            ->Promise.then(result => Promise.resolve(JSON.Object(result)))
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Test harness — builds server + client pair, registers all 11 tools
// ---------------------------------------------------------------------------

let buildTestHarness = (): Promise.t<(Bindings.McpSdk.inMemoryTransport, Bindings.McpSdk.mcpServer, Services.Facade.t)> => {
  Bindings.McpSdk.createInMemoryTransportPair()
    ->Promise.then(pair => {
      let (clientTransport, serverTransport) = pair

      // Build server info
      let version = getVersion()
      let serverInfo: Bindings.McpSdk.serverInfo = {name: "MS Access MCP Server", version: version}

      // Build real facade
      let allowedDirs = switch TsBridge.getEnv("ACCESS_TEST_DB") {
      | Some(path) if String.length(path) > 0 => [NodeJs.Os.homedir(), path]
      | _ => [NodeJs.Os.homedir()]
      }
      let facade = Services.Facade.make(
        ~factory=Composition.realFactory,
        ~comAvailable=false,
        ~readonly=() => false,
        ~allowedDirs=() => allowedDirs,
      )

      // Create server
      let server = Bindings.McpSdk.newMcpServer(serverInfo)

      // Register production schemas so tools/list exercises the metadata that
      // a real MCP client receives; callbacks remain local test seams.
      let allTools = [
        ("connect_access", "Connect to an Access database (.accdb, .mdb) using ODBC.", Mcp.Tools.connectAccessSchema, makeConnectAccessCallback(facade)),
        ("disconnect_access", "Disconnect a named Access database connection.", Mcp.Tools.disconnectAccessSchema, makeDisconnectAccessCallback(facade)),
        ("list_connections", "List all active database connections and their status.", Mcp.Tools.listConnectionsSchema, makeListConnectionsCallback(facade)),
        ("is_connected", "Check whether a named connection is currently active.", Mcp.Tools.isConnectedSchema, makeIsConnectedCallback(facade)),
        ("query_data", "Execute a SQL SELECT query and return rows.", Mcp.Tools.queryDataSchema, makeQueryDataCallback(facade)),
        ("insert_data", "Insert one or more records into a table.", Mcp.Tools.insertDataSchema, makeInsertDataCallback(facade)),
        ("update_data", "Update records in a table matching a WHERE clause.", Mcp.Tools.updateDataSchema, makeUpdateDataCallback(facade)),
        ("delete_data", "Delete records from a table matching a WHERE clause.", Mcp.Tools.deleteDataSchema, makeDeleteDataCallback(facade)),
        ("get_tables", "List all user tables in the connected database.", Mcp.Tools.getTablesSchema, makeGetTablesCallback(facade)),
        ("get_table_schema", "Get the field schema for a specific table.", Mcp.Tools.getTableSchemaSchema, makeGetTableSchemaCallback(facade)),
        ("get_queries", "List all saved queries in the database.", Mcp.Tools.getQueriesSchema, makeGetQueriesCallback(facade)),
        ("execute_raw_sql", "Execute arbitrary SQL (including DDL) with safety guards.", Mcp.Tools.executeRawSqlSchema, makeExecuteRawSqlCallback(facade)),
      ]

      Belt.Array.forEach(allTools, ((name, description, inputSchema, callback)) => {
        let envelopeCallback: toolCallback = (. args) => {
          callback(args)
            ->Promise.then(result => Promise.resolve(Mcp.Envelope.transcribeJson(result)))
        }
        ignore(Bindings.McpSdk.registerTool(
          server,
          name,
          {description: description, inputSchema: inputSchema},
          envelopeCallback,
        ))
      })

      // Connect server to transport
      Bindings.McpSdk.mcpConnect(server, serverTransport)
        ->Promise.then(_ => {
          // Set up client transport's onmessage handler (must be done before any sendRequest).
          // This handler drains responses from global.__mcpPending by correlation id.
          // We do it here so it is active for the FIRST sendRequest call.
          %raw(`
            (clientTransport) => {
              if (!global.__mcpPending) global.__mcpPending = {};
              if (!clientTransport.onmessage) {
                clientTransport.onmessage = (msg) => {
                  const respId = msg.id !== undefined && msg.id !== null ? String(msg.id) : null;
                  if (respId && global.__mcpPending[respId]) {
                    global.__mcpPending[respId](msg);
                    delete global.__mcpPending[respId];
                  }
                };
              }
            }
          `)(clientTransport)
          Promise.resolve((clientTransport, server, facade))
        })
        ->Promise.catch(_ => {
          %raw(`
            (clientTransport) => {
              if (!global.__mcpPending) global.__mcpPending = {};
              if (!clientTransport.onmessage) {
                clientTransport.onmessage = (msg) => {
                  const respId = msg.id !== undefined && msg.id !== null ? String(msg.id) : null;
                  if (respId && global.__mcpPending[respId]) {
                    global.__mcpPending[respId](msg);
                    delete global.__mcpPending[respId];
                  }
                };
              }
            }
          `)(clientTransport)
          Promise.resolve((clientTransport, server, facade))
        })
    })
}

// ---------------------------------------------------------------------------
// Test 1: Initialize handshake
// ---------------------------------------------------------------------------

testAsync("MCP server: initialize returns serverInfo.name='MS Access MCP Server', version, and tools capability", cb => {
  buildTestHarness()
    ->Promise.then(result => {
      let (clientTransport, _server, _facade) = result
      let client = makeClient(clientTransport)

      let params = JSON.Object(dict{
        "protocolVersion": JSON.String("2024-11-05"),
        "capabilities": JSON.Object(dict{}),
        "clientInfo": JSON.Object(dict{"name": JSON.String("test-client"), "version": JSON.String("1.0.0")}),
      })

      sendRequest(client, "initialize", params)
        ->Promise.then(response => {
          let resultObj: option<JSON.t> = switch response {
          | JSON.Object(o) => Dict.get(o, "result")
          | _ => None
          }
          let nameOk: bool = switch resultObj {
          | Some(JSON.Object(r)) => {
              switch Dict.get(r, "serverInfo") {
              | Some(JSON.Object(si)) => {
                  switch Dict.get(si, "name") {
                  | Some(JSON.String(n)) => n == "MS Access MCP Server"
                  | _ => false
                  }
                }
              | _ => false
              }
            }
          | _ => false
          }
          let versionOk: bool = switch resultObj {
          | Some(JSON.Object(r)) => {
              switch Dict.get(r, "serverInfo") {
              | Some(JSON.Object(si)) => {
                  switch Dict.get(si, "version") {
                  | Some(JSON.String(v)) => v != ""
                  | _ => false
                  }
                }
              | _ => false
              }
            }
          | _ => false
          }
          let capsOk: bool = switch resultObj {
          | Some(JSON.Object(r)) => {
              switch Dict.get(r, "capabilities") {
              | Some(JSON.Object(c)) => Dict.has(c, "tools")
              | _ => false
              }
            }
          | _ => false
          }
          assertion(~operator="equal", (a, b) => a == b, nameOk, true)
          assertion(~operator="equal", (a, b) => a == b, versionOk, true)
          assertion(~operator="equal", (a, b) => a == b, capsOk, true)
          cb(~planned=3, ())
          Promise.resolve()
        })
        ->Promise.catch(_e => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        })
    })
    ->Promise.catch(_e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test 2: tools/list — names and non-vacuous per-tool input metadata
// ---------------------------------------------------------------------------

testAsync("MCP server: tools/list returns exactly 12 tools with Python-verbatim names", cb => {
  buildTestHarness()
    ->Promise.then(result => {
      let (clientTransport, _server, _facade) = result
      let client = makeClient(clientTransport)

      // Initialize first (required before other requests)
      let initParams = JSON.Object(dict{
        "protocolVersion": JSON.String("2024-11-05"),
        "capabilities": JSON.Object(dict{}),
        "clientInfo": JSON.Object(dict{"name": JSON.String("test"), "version": JSON.String("1.0")}),
      })

      sendRequest(client, "initialize", initParams)
        ->Promise.then(_ => {
          sendNotification(client, "notifications/initialized", JSON.Object(dict{}))
          sendRequest(client, "tools/list", JSON.Object(dict{}))
        })
        ->Promise.then(response => {
          let d = switch response { | JSON.Object(o) => o | _ => dict{} }
          let toolsArr = switch Dict.get(d, "result") {
          | Some(JSON.Object(r)) => {
              switch Dict.get(r, "tools") {
              | Some(JSON.Array(a)) => Some(a) | _ => None
              }
            }
          | _ => None
          }

          let countOk = switch toolsArr {
          | Some(a) => Belt.Array.length(a) == 12
          | None => false
          }

          // Extract names
          let names = switch toolsArr {
          | Some(a) => Belt.Array.map(a, item => {
              switch item {
              | JSON.Object(o) => {
                  switch Dict.get(o, "name") {
                  | Some(JSON.String(n)) => Some(n) | _ => None
                  }
                }
              | _ => None
              }
            })
          | None => []
          }

          let expected = [
            "connect_access", "disconnect_access", "list_connections", "is_connected",
            "query_data", "insert_data", "update_data", "delete_data",
            "get_tables", "get_table_schema", "get_queries", "execute_raw_sql",
          ]

          let namesMatch = Belt.Array.every(expected, e => {
            Belt.Array.some(names, n => n == Some(e))
          })

          // Assert published JSON Schema properties rather than merely checking
          // that tools/list contains entries. This catches a pass-through Zod
          // replacement, which serializes to an empty inputSchema.
          let schemasMatch = switch toolsArr {
          | Some(tools) =>
              %raw(`(tools) => {
                const byName = Object.fromEntries(tools.map(tool => [tool.name, tool.inputSchema]));
                const hasProperties = (name, properties, required = []) => {
                  const schema = byName[name];
                  return schema
                    && schema.type === "object"
                    && properties.every(property => Object.hasOwn(schema.properties || {}, property))
                    && required.every(property => (schema.required || []).includes(property));
                };
                return hasProperties("connect_access", ["database_path", "name", "password", "use_com", "backend"], ["database_path"])
                  && hasProperties("query_data", ["sql", "params", "connection_name"], ["sql"])
                  && hasProperties("insert_data", ["table_name", "data", "connection_name"], ["table_name", "data"])
                  && hasProperties("update_data", ["table_name", "set_dict", "where_dict", "confirm", "dry_run"], ["table_name", "set_dict"])
                  && hasProperties("delete_data", ["table_name", "where_dict", "confirm", "dry_run"], ["table_name"])
                  && hasProperties("get_table_schema", ["table_name", "connection_name"], ["table_name"])
                  && hasProperties("execute_raw_sql", ["sql", "confirm", "dry_run"], ["sql"]);
              }`)(tools)
          | None => false
          }

          assertion(~operator="equal", (a, b) => a == b, countOk, true)
          assertion(~operator="equal", (a, b) => a == b, namesMatch, true)
          assertion(~operator="equal", (a, b) => a == b, schemasMatch, true)
          cb(~planned=3, ())
          Promise.resolve()
        })
        ->Promise.catch(_e => {
          assertion(~operator="equal", (a, b) => a == b, false, true)
          cb(~planned=1, ())
          Promise.resolve()
        })
    })
    ->Promise.catch(_e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Test 3: tools/call — get_tables (ACCESS_TEST_DB required)
// ---------------------------------------------------------------------------

testAsync("MCP server: tools/call get_tables returns content[0].type=text, isError=false (ACCESS_TEST_DB required)", cb => {
  let testDb = %raw(`() => process.env.ACCESS_TEST_DB`)()
  if testDb == None || testDb == "" {
    cb(~planned=0, ())
  } else {
    buildTestHarness()
      ->Promise.then(result => {
        let (clientTransport, _server, _facade) = result
        let client = makeClient(clientTransport)

        let initParams = JSON.Object(dict{
          "protocolVersion": JSON.String("2024-11-05"),
          "capabilities": JSON.Object(dict{}),
          "clientInfo": JSON.Object(dict{"name": JSON.String("test"), "version": JSON.String("1.0")}),
        })

        sendRequest(client, "initialize", initParams)
          ->Promise.then(_ => {
            // First connect
            let connectArgs = JSON.Object(dict{
              "database_path": JSON.String(testDb),
              "backend": JSON.String("odbc"),
            })
            sendRequest(client, "tools/call", JSON.Object(dict{
              "name": JSON.String("connect_access"),
              "arguments": connectArgs,
            }))
          })
          ->Promise.then(_connectResp => {
            // Now call get_tables
            sendRequest(client, "tools/call", JSON.Object(dict{
              "name": JSON.String("get_tables"),
              "arguments": JSON.Object(dict{}),
            }))
          })
          ->Promise.then(response => {
            let d = switch response { | JSON.Object(o) => o | _ => dict{} }
            let resultObj = switch Dict.get(d, "result") {
            | Some(JSON.Object(r)) => Some(r) | _ => None
            }
            let contentArr = switch resultObj {
            | Some(r) => {
                switch Dict.get(r, "content") {
                | Some(JSON.Array(a)) => Some(a) | _ => None
                }
              }
            | None => None
            }

            // content[0].type === "text"
            let firstType = switch contentArr {
            | Some(a) => {
                switch Belt.Array.get(a, 0) {
                | Some(JSON.Object(item)) => {
                    switch Dict.get(item, "type") {
                    | Some(JSON.String(t)) => Some(t) | _ => None
                    }
                  }
                | _ => None
                }
              }
            | None => None
            }
            let typeOk = firstType == Some("text")

            // isError === false
            let isErr = switch resultObj {
            | Some(r) => {
                switch Dict.get(r, "isError") {
                | Some(JSON.Boolean(b)) => Some(b) | _ => Some(false)
                }
              }
            | None => Some(false)
            }
            let noErrorOk = isErr == Some(false)

            assertion(~operator="equal", (a, b) => a == b, typeOk, true)
            assertion(~operator="equal", (a, b) => a == b, noErrorOk, true)
            cb(~planned=2, ())
            Promise.resolve()
          })
          ->Promise.catch(_e => {
            assertion(~operator="equal", (a, b) => a == b, false, true)
            cb(~planned=1, ())
            Promise.resolve()
          })
      })
      ->Promise.catch(_e => {
        assertion(~operator="equal", (a, b) => a == b, false, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->ignore
  }
})

// ---------------------------------------------------------------------------
// Test 4: tools/call — connect_access (ACCESS_TEST_DB required)
// ---------------------------------------------------------------------------

testAsync("MCP server: tools/call connect_access returns content text with success:true, connected:true, adapter_type odbc (ACCESS_TEST_DB required)", cb => {
  let testDb = %raw(`() => process.env.ACCESS_TEST_DB`)()
  if testDb == None || testDb == "" {
    cb(~planned=0, ())
  } else {
    buildTestHarness()
      ->Promise.then(result => {
        let (clientTransport, _server, _facade) = result
        let client = makeClient(clientTransport)

        let initParams = JSON.Object(dict{
          "protocolVersion": JSON.String("2024-11-05"),
          "capabilities": JSON.Object(dict{}),
          "clientInfo": JSON.Object(dict{"name": JSON.String("test"), "version": JSON.String("1.0")}),
        })

        sendRequest(client, "initialize", initParams)
          ->Promise.then(_ => {
            let args = JSON.Object(dict{
              "database_path": JSON.String(testDb),
              "backend": JSON.String("odbc"),
            })
            sendRequest(client, "tools/call", JSON.Object(dict{
              "name": JSON.String("connect_access"),
              "arguments": args,
            }))
          })
          ->Promise.then(response => {
            let d = switch response { | JSON.Object(o) => o | _ => dict{} }
            let resultObj = switch Dict.get(d, "result") {
            | Some(JSON.Object(r)) => Some(r) | _ => None
            }
            let contentArr = switch resultObj {
            | Some(r) => {
                switch Dict.get(r, "content") {
                | Some(JSON.Array(a)) => Some(a) | _ => None
                }
              }
            | None => None
            }
            let textContent = switch contentArr {
            | Some(a) => {
                switch Belt.Array.get(a, 0) {
                | Some(JSON.Object(item)) => {
                    switch Dict.get(item, "text") {
                    | Some(JSON.String(t)) => Some(t) | _ => None
                    }
                  }
                | _ => None
                }
              }
            | None => None
            }

            let successOk = switch textContent {
            | Some(t) => String.includes(t, "\"success\":true") || String.includes(t, "\"success\": true")
            | None => false
            }
            let connectedOk = switch textContent {
            | Some(t) => String.includes(t, "\"connected\":true") || String.includes(t, "\"connected\": true")
            | None => false
            }
            let adapterOk = switch textContent {
            | Some(t) => String.includes(t, "\"adapter_type\":\"odbc\"") || String.includes(t, "\"adapter_type\": \"odbc\"")
            | None => false
            }

            assertion(~operator="equal", (a, b) => a == b, successOk, true)
            assertion(~operator="equal", (a, b) => a == b, connectedOk, true)
            assertion(~operator="equal", (a, b) => a == b, adapterOk, true)
            cb(~planned=3, ())
            Promise.resolve()
          })
          ->Promise.catch(_e => {
            assertion(~operator="equal", (a, b) => a == b, false, true)
            cb(~planned=1, ())
            Promise.resolve()
          })
      })
      ->Promise.catch(_e => {
        assertion(~operator="equal", (a, b) => a == b, false, true)
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->ignore
  }
})
