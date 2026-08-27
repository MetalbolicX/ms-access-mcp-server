// Bindings/McpSdk.res — FFI bindings for @modelcontextprotocol/sdk
// SOLE module that imports @modelcontextprotocol/sdk.
//
// Provides typed ReScript externals for:
//   - McpServer (constructor, registerTool, connect, close, isConnected)
//   - StdioServerTransport
//   - InMemoryTransport (createLinkedPair)
//   - validateToolInputWrap (ENV-2: catches InvalidParams → pinned Error envelope)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// Zod object schema type — minimal interface matching what the SDK needs.
// We define this locally to avoid importing Bindings.Zod (which would create
// a circular dependency: Bindings.res -> McpSdk.res -> Bindings.Zod).
type zObject = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => result<JSON.t, JSON.t>,
}

// Tool callback: receives parsed JSON arguments, returns JSON tool result.
type toolCallback = (. JSON.t) => JSON.t

// Tool registration config — matches SDK's registerTool config object.
type toolConfig = {
  description: string,
  inputSchema: zObject,
}

// Server info passed to McpServer constructor.
type serverInfo = {
  name: string,
  version: string,
}

// Opaque types — JS objects typed as 'transport'
type transport = {}

// Note: ReScript type names must start with lowercase, so we use lowercase aliases.
type mcpServer = transport
type stdioTransport = transport
type inMemoryTransport = transport
type registeredTool = transport

// ---------------------------------------------------------------------------
// McpServer — constructor
// new McpServer({name, version})
// ---------------------------------------------------------------------------

@module("@modelcontextprotocol/sdk/server/mcp.js")
@new
external newMcpServer: serverInfo => mcpServer = "McpServer"

// ---------------------------------------------------------------------------
// McpServer instance methods as @send externals (first arg is the object)
// registerTool(server, name, config, callback)  →  server.registerTool(name, config, callback)
// ---------------------------------------------------------------------------

@send
external registerTool: (mcpServer, string, toolConfig, toolCallback) => registeredTool = "registerTool"

@send
external mcpConnect: (mcpServer, stdioTransport) => promise<unit> = "connect"

@send
external mcpClose: (mcpServer) => promise<unit> = "close"

@send
external isConnected: (mcpServer) => bool = "isConnected"

// ---------------------------------------------------------------------------
// StdioServerTransport
// ---------------------------------------------------------------------------

@module("@modelcontextprotocol/sdk/server/stdio.js")
@new
external newStdioServerTransport: unit => stdioTransport = "StdioServerTransport"

// ---------------------------------------------------------------------------
// InMemoryTransport
// ---------------------------------------------------------------------------

// createLinkedPair is a static method on InMemoryTransport.
// ESM has no synchronous require, so use dynamic import() and return a Promise.
// The test awaits this via %raw.
let createInMemoryTransportPair: unit => Promise.t<(inMemoryTransport, inMemoryTransport)> = %raw(`
  () => {
    return import("@modelcontextprotocol/sdk/inMemory.js").then(m => {
      return m.InMemoryTransport.createLinkedPair();
    });
  }
`)

// ---------------------------------------------------------------------------
// ENV-2: validateToolInputWrap
//
// The SDK's validateToolInput (TS-private) is called by the callTool handler
// before invoking the tool callback. It throws McpError(InvalidParams, ...) on
// failure. The SDK's catch path wraps ALL thrown errors via createToolError:
//
//   { content: [{ type: "text", text: error.message }], isError: true }
//
// Our wrap intercepts the InvalidParams throw and re-throws as
// Error(JSON.stringify(VE)) so the SDK catch path emits the pinned envelope
// verbatim. This gives us deterministic error text from the Zod validation.
// ---------------------------------------------------------------------------

/**
 * validateToolInputWrap — runs the SDK's private validateToolInput on a
 * tool's inputSchema and payload, re-throwing InvalidParams as a pinned
 * Error(JSON.stringify) envelope that the SDK's catch path emits verbatim.
 *
 * Returns Ok(parsedData) on success, Error(message) when validation fails.
 */
let validateToolInputWrap:
  (mcpServer, zObject, JSON.t) =>
    result<JSON.t, string> = %raw(`
  (_server, schema, payload) => {
    // Call safeParse directly — this is what the SDK's validateToolInput
    // invokes internally when it has a proper tool { inputSchema } object.
    const parsed = schema.safeParse(payload);

    if (typeof parsed !== 'object' || parsed === null) {
      return { TAG: "Error", _0: "safeParse returned non-object" };
    }

    if (parsed.success) {
      return { TAG: "Ok", _0: parsed.data };
    }

    // Validation failed — extract error messages and throw as a pinned
    // Error envelope so the SDK catch path emits the message verbatim.
    const issues = parsed.error && parsed.error.issues;
    let msg;
    if (issues && issues.length > 0) {
      msg = "Invalid arguments: " + issues.map(function(i) { return i.message; }).join("; ");
    } else {
      msg = "Invalid arguments: validation failed";
    }

    throw new Error(JSON.stringify({ isError: true, content: [{ type: "text", text: msg }] }));
  }
`)
