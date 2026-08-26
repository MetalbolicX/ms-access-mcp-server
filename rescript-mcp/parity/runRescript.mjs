// runRescript.mjs — ReScript child runner for the differential parity harness.
//
// Reads a case JSON (parity/cases/<op>.json), instantiates a Facade with
// Composition.realFactory, connects if needed, runs the case's operation,
// prints the envelope JSON. The parent (run.mjs) orchestrates fixture
// copying for mutating cases; this child treats ACCESS_TEST_DB as the
// canonical input.
//
// Usage:
//   node parity/runRescript.mjs <case.json> [connectName]
//
// Output: a single JSON object on stdout. Exits 0 on success, 1 on
// driver-level error (so the parent can distinguish "case failed" from
// "child crashed").

import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Resolve the compiled facade module via pathToFileURL so Windows paths
// (D:\...) parse as URLs and the runtime doesn't try to resolve them as
// POSIX relative paths.
const facadePath = pathToFileURL(
  resolve(__dirname, "..", "src", "Services", "Facade.res.mjs"),
).href;
const compositionPath = pathToFileURL(
  resolve(__dirname, "..", "src", "Services", "Composition.res.mjs"),
).href;

const Facade = await import(facadePath);
const Composition = await import(compositionPath);

// ---------------------------------------------------------------------------
// JSON.t adapter — convert plain JS values into the variant encoding the
// ReScript runtime uses for JSON.t at the FFI boundary.
// ReScript JSON.t encoding (per Stdlib_JSON.js classify):
//   null                          -> JSON.Null
//   { TAG: "Bool",    _0: bool }   -> JSON.Boolean
//   { TAG: "Number",  _0: number } -> JSON.Number
//   { TAG: "String",  _0: string } -> JSON.String
//   { TAG: "Array",   _0: array }  -> JSON.Array
//   { TAG: "Object",  _0: dict }   -> JSON.Object
// ---------------------------------------------------------------------------
function jsToJsonT(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === "boolean") return { TAG: "Bool", _0: v };
  if (typeof v === "number") return { TAG: "Number", _0: v };
  if (typeof v === "string") return { TAG: "String", _0: v };
  if (Array.isArray(v)) return { TAG: "Array", _0: v.map(jsToJsonT) };
  if (typeof v === "object") return { TAG: "Object", _0: jsToJsonDict(v) };
  throw new Error(`unsupported JSON.t value: ${typeof v}`);
}

function jsToJsonDict(obj) {
  const d = {};
  for (const k of Object.keys(obj)) {
    d[k] = jsToJsonT(obj[k]);
  }
  return d;
}

// option<T> at the FFI boundary is `undefined` (None) or `T` (Some).
// Pass through whereDict by wrapping the dict in JSON.Object; the facade
// does this internally but the JS-level encoded shape matches anyway.
function toOption(v) {
  return v === undefined || v === null ? undefined : v;
}

// ---------------------------------------------------------------------------
// Operation dispatch — one branch per facade op. Each branch uses the
// already-connected facade; connect/disconnect are orchestrated by the
// runner (run.mjs) via the wrapper function below.
// ---------------------------------------------------------------------------

async function runOperation(facade, operation, args) {
  switch (operation) {
    case "connect_access":
      return await Facade.connectAccess(facade, args.dbPath ?? process.env.ACCESS_TEST_DB);

    case "disconnect_access":
      return await Facade.disconnectAccess(facade);

    case "list_connections":
      return Facade.listConnections(facade);

    case "is_connected":
      return Facade.isConnected(facade);

    case "set_active_connection":
      return await Facade.setActiveConnection(facade, args.name);

    case "get_active_connection":
      return Facade.getActiveConnection(facade);

    case "query_data":
      return await Facade.queryData(facade, args.sql);

    case "get_tables":
      return await Facade.getTables(facade);

    case "get_table_schema":
      return await Facade.getTableSchema(facade, args.table);

    case "get_relationships":
      return await Facade.getRelationships(facade);

    case "get_queries":
      return await Facade.getQueries(facade);

    case "get_database_statistics":
      return await Facade.getDatabaseStatistics(facade);

    case "insert_data":
      return await Facade.insertData(facade, args.table, jsToJsonT(args.data));

    case "update_data": {
      const setDict = jsToJsonDict(args.setDict);
      const whereDict = args.whereDict ? jsToJsonDict(args.whereDict) : undefined;
      return await Facade.updateData(facade, args.table, setDict, whereDict, undefined, args.confirm ?? false, args.dryRun ?? false);
    }

    case "delete_data": {
      const whereDict = jsToJsonDict(args.whereDict);
      return await Facade.deleteData(
        facade,
        args.table,
        whereDict,
        undefined,
        args.confirm ?? false,
        args.dryRun ?? false,
      );
    }

    case "execute_raw_sql":
      return await Facade.executeRawSql(
        facade,
        args.sql,
        undefined,
        args.confirm ?? false,
        args.dryRun ?? false,
      );

    case "export_data": {
      let filePath = args.filePath;
      if (filePath === "REPLACE_AT_RUNTIME") {
        const dir = process.env.PARITY_EXPORT_DIR ?? (await import("node:os")).tmpdir();
        const path = await import("node:path");
        const fs = await import("node:fs");
        fs.mkdirSync(dir, { recursive: true });
        filePath = path.join(dir, `parity_export_${process.pid}.csv`);
      }
      return await Facade.exportData(facade, args.sql, filePath, args.format);
    }

    default:
      throw new Error(`unknown operation: ${operation}`);
  }
}

// ---------------------------------------------------------------------------
// Main — read case, decide whether to connect, run op, print envelope.
// Connection-lifecycle ops run without a prior connect.
// ---------------------------------------------------------------------------

async function main() {
  const casePath = process.argv[2];
  if (!casePath) {
    process.stderr.write("usage: runRescript.mjs <case.json>\n");
    process.exit(1);
  }
  const caseText = readFileSync(casePath, "utf8");
  const caseObj = JSON.parse(caseText);

  // PathGuard on the facade requires dbPath to be inside allowedDirs().
  // The harness sets ACCESS_MCP_ALLOWED_DIRS in run.mjs to include the
  // fixture dir + temp export dir; mirror that here.
  const homeDir = (await import("node:os")).homedir();
  const allowedDirs = (process.env.ACCESS_MCP_ALLOWED_DIRS ?? homeDir)
    .split(";")
    .filter((s) => s.length > 0);

  const facade = Facade.make(
    undefined,
    Composition.realFactory,
    false,
    undefined,
    () => allowedDirs,
  );

  // Connection-lifecycle ops do not require a prior connect. Everything
  // else does — connect first, then run.
  // setActiveConnection needs an existing connection; include it here so
  // the runner primes the pool. disconnectAccess, listConnections,
  // isConnected, getActiveConnection, connectAccess handle their own
  // preconditions (silent no-ops on empty pool, etc.).
  const lifecycle = new Set([
    "connect_access",
    "disconnect_access",
    "list_connections",
    "is_connected",
    "get_active_connection",
  ]);
  if (!lifecycle.has(caseObj.operation)) {
    const dbPath = process.env.ACCESS_TEST_DB;
    if (!dbPath) {
      throw new Error("ACCESS_TEST_DB not set");
    }
    const connectResult = await Facade.connectAccess(facade, dbPath);
    if (!connectResult.success) {
      // Return the connect failure as the envelope so the differ can
      // compare failure shapes.
      process.stdout.write(JSON.stringify(connectResult));
      return;
    }
    // Composition.realFactory creates the dataAdapter with
    // {connection: None, dbPath: None} and never opens the underlying
    // ODBC handle (parity harness finding 007-F-001). The facade's
    // connectAccess only registers the binding — it does not call
    // dataAdapter.connect(). Reach into the binding here and wire the
    // ODBC connection so the subsequent data op has a live cursor.
    const connStr = `Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=${dbPath};`;
    const binding = facade.bindings.find(([name]) => name === "default");
    if (binding) {
      const connectOutcome = await binding[1].dataAdapter.connect(connStr);
      if (connectOutcome.TAG !== "Ok") {
        process.stdout.write(
          JSON.stringify({
            success: false,
            error: `dataAdapter.connect failed: ${connectOutcome._0?.message ?? "unknown"}`,
          }),
        );
        return;
      }
    }
  }

  const envelope = await runOperation(facade, caseObj.operation, caseObj.args ?? {});

  // Disconnect after non-lifecycle ops to leave a clean pool for the next
  // child process. Errors here are non-fatal (the child is exiting anyway).
  if (!lifecycle.has(caseObj.operation)) {
    try {
      // First close the underlying ODBC connection we opened.
      const binding = facade.bindings.find(([name]) => name === "default");
      if (binding) {
        try {
          await binding[1].dataAdapter.disconnect();
        } catch {
          // ignore
        }
      }
      await Facade.disconnectAccess(facade);
    } catch {
      // ignore
    }
  }

  process.stdout.write(JSON.stringify(envelope));
}

main().catch((err) => {
  process.stderr.write(`runRescript: ${err?.message ?? err}\n`);
  if (err?.stack) process.stderr.write(err.stack + "\n");
  process.exit(1);
});