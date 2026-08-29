// runRescript.ts — ReScript child runner for the differential parity harness.
//
// Reads a case JSON (parity/cases/<op>.json), instantiates a Facade with
// Composition.realFactory, connects if needed, runs the case's operation,
// prints the envelope JSON. The parent (run.ts) orchestrates fixture
// copying for mutating cases; this child treats ACCESS_TEST_DB as the
// canonical input.
//
// Usage:
//   node parity/runRescript.mjs <case.json> [connectName]
//
// Output: a single JSON object on stdout. Exits 0 on success, 1 on
// driver-level error (so the parent can distinguish "case failed" from
// "child crashed").

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
// __dirname is parity/dist/ (one level deeper than parity/runRescript.mjs), so two levels up
const FACADE_PATH = resolve(__dirname, "..", "..", "src", "Services", "Facade.res.mjs");
const COMPOSITION_PATH = resolve(__dirname, "..", "..", "src", "Services", "Composition.res.mjs");

const FacadeModule = await import(pathToFileURL(FACADE_PATH).href);
const CompositionModule = await import(pathToFileURL(COMPOSITION_PATH).href);

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
function jsToJsonT(v: unknown): JsonT | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "boolean") return { TAG: "Bool", _0: v } as JsonT;
  if (typeof v === "number") return { TAG: "Number", _0: v } as JsonT;
  if (typeof v === "string") return { TAG: "String", _0: v } as JsonT;
  if (Array.isArray(v)) return { TAG: "Array", _0: v.map(jsToJsonT) } as JsonT;
  if (typeof v === "object") return { TAG: "Object", _0: jsToJsonDict(v as Record<string, unknown>) } as JsonT;
  throw new Error(`unsupported JSON.t value: ${typeof v}`);
}

function jsToJsonDict(obj: Record<string, unknown>): Record<string, JsonT> {
  const d: Record<string, JsonT> = {};
  for (const k of Object.keys(obj)) {
    d[k] = jsToJsonT(obj[k]) ?? { TAG: "Null" };
  }
  return d;
}

// option<T> at the FFI boundary is `undefined` (None) or `T` (Some).
// Pass through whereDict by wrapping the dict in JSON.Object; the facade
// does this internally but the JS-level encoded shape matches anyway.
function toOption<T>(v: T | undefined | null): T | undefined {
  return v === undefined || v === null ? undefined : v;
}

// ---------------------------------------------------------------------------
// JSON.t discriminated union (mirrors ReScript JSON.t)
// ---------------------------------------------------------------------------
type JsonT =
  | { TAG: "Null" }
  | { TAG: "String"; _0: string }
  | { TAG: "Number"; _0: number }
  | { TAG: "Bool"; _0: boolean }
  | { TAG: "Object"; _0: Record<string, JsonT> }
  | { TAG: "Array"; _0: JsonT[] };

// ---------------------------------------------------------------------------
// Case file shape
// ---------------------------------------------------------------------------
interface CaseFile {
  operation: string;
  args?: Record<string, unknown>;
  mutating?: boolean;
  volatileFields?: string[];
}

// ---------------------------------------------------------------------------
// Facade module — functions are module-level (not instance methods).
// The facade record returned by make() is passed as first arg to each fn.
// ---------------------------------------------------------------------------

interface FacadeRecord {
  pool: unknown;
  bindings: Array<[string, unknown]>;
  factory: (backend: string | null, dbPath: string, password: string) => Promise<unknown>;
  comAvailable: boolean;
  readonly: () => boolean;
  allowedDirs: () => string[];
}

interface FacadeModule {
  make: (
    pool: unknown,
    factory: (backend: string | null, dbPath: string, password: string) => Promise<unknown>,
    comAvailable: boolean,
    readonly: (() => boolean) | undefined,
    allowedDirs: (() => string[]) | undefined,
  ) => FacadeRecord;
  connectAccess: (facade: FacadeRecord, dbPath: string, name?: string, useCom?: boolean, password?: string, backend?: string) => Promise<Record<string, JsonT>>;
  disconnectAccess: (facade: FacadeRecord, name?: string) => Promise<Record<string, JsonT>>;
  listConnections: (facade: FacadeRecord) => Record<string, JsonT>;
  isConnected: (facade: FacadeRecord, name?: string) => Record<string, JsonT>;
  setActiveConnection: (facade: FacadeRecord, name: string) => Promise<Record<string, JsonT>>;
  getActiveConnection: (facade: FacadeRecord) => Record<string, JsonT>;
  queryData: (facade: FacadeRecord, sql: string, name?: string) => Promise<Record<string, JsonT>>;
  getTables: (facade: FacadeRecord, name?: string) => Promise<Record<string, JsonT>>;
  getTableSchema: (facade: FacadeRecord, table: string, name?: string) => Promise<Record<string, JsonT>>;
  getRelationships: (facade: FacadeRecord, name?: string) => Promise<Record<string, JsonT>>;
  getQueries: (facade: FacadeRecord, name?: string) => Promise<Record<string, JsonT>>;
  getDatabaseStatistics: (facade: FacadeRecord, name?: string) => Promise<Record<string, JsonT>>;
  insertData: (facade: FacadeRecord, table: string, data: Record<string, JsonT>, name?: string) => Promise<Record<string, JsonT>>;
  updateData: (facade: FacadeRecord, table: string, setDict: Record<string, JsonT>, whereDict: Record<string, JsonT> | undefined, name: string | undefined, confirm: boolean, dryRun: boolean) => Promise<Record<string, JsonT>>;
  deleteData: (facade: FacadeRecord, table: string, whereDict: Record<string, JsonT>, name: string | undefined, confirm: boolean, dryRun: boolean) => Promise<Record<string, JsonT>>;
  executeRawSql: (facade: FacadeRecord, sql: string, name: string | undefined, confirm: boolean, dryRun: boolean) => Promise<Record<string, JsonT>>;
  exportData: (facade: FacadeRecord, sql: string, filePath: string, format: string, delimiter?: string, header?: boolean, name?: string) => Promise<Record<string, JsonT>>;
}

// ---------------------------------------------------------------------------
// Operation dispatch — one branch per facade op. Each branch uses the
// already-connected facade; connect/disconnect are orchestrated by the
// runner (run.ts) via the wrapper function below.
// ---------------------------------------------------------------------------

async function runOperation(Facade: FacadeModule, facade: FacadeRecord, operation: string, args: Record<string, unknown>): Promise<Record<string, JsonT>> {
  switch (operation) {
    case "connect_access":
      return await Facade.connectAccess(facade, args.dbPath as string ?? process.env.ACCESS_TEST_DB ?? "");

    case "disconnect_access":
      return await Facade.disconnectAccess(facade, args.name as string | undefined);

    case "list_connections":
      return Facade.listConnections(facade);

    case "is_connected":
      return Facade.isConnected(facade, args.name as string | undefined);

    case "set_active_connection":
      return await Facade.setActiveConnection(facade, args.name as string);

    case "get_active_connection":
      return Facade.getActiveConnection(facade);

    case "query_data":
      return await Facade.queryData(facade, args.sql as string, args.name as string | undefined);

    case "get_tables":
      return await Facade.getTables(facade, args.name as string | undefined);

    case "get_table_schema":
      return await Facade.getTableSchema(facade, args.table as string, args.name as string | undefined);

    case "get_relationships":
      return await Facade.getRelationships(facade, args.name as string | undefined);

    case "get_queries":
      return await Facade.getQueries(facade, args.name as string | undefined);

    case "get_database_statistics":
      return await Facade.getDatabaseStatistics(facade, args.name as string | undefined);

    case "insert_data": {
      const data = (args.data as Record<string, unknown>) ?? {};
      return await Facade.insertData(facade, args.table as string, jsToJsonDict(data) as Record<string, JsonT>, args.name as string | undefined);
    }

    case "update_data": {
      const setDict = jsToJsonDict((args.setDict as Record<string, unknown>) ?? {});
      const whereDict = args.whereDict ? jsToJsonDict(args.whereDict as Record<string, unknown>) : undefined;
      return await Facade.updateData(facade, args.table as string, setDict, whereDict, args.name as string | undefined, (args.confirm as boolean) ?? false, (args.dryRun as boolean) ?? false);
    }

    case "delete_data": {
      const whereDict = jsToJsonDict((args.whereDict as Record<string, unknown>) ?? {});
      return await Facade.deleteData(facade, args.table as string, whereDict, args.name as string | undefined, (args.confirm as boolean) ?? false, (args.dryRun as boolean) ?? false);
    }

    case "execute_raw_sql":
      return await Facade.executeRawSql(facade, args.sql as string, args.name as string | undefined, (args.confirm as boolean) ?? false, (args.dryRun as boolean) ?? false);

    case "export_data": {
      let filePath = args.filePath as string;
      if (filePath === "REPLACE_AT_RUNTIME") {
        const { tmpdir: td } = await import("node:os");
        const { join: j } = await import("node:path");
        const { mkdirSync: ms } = await import("node:fs");
        const dir = process.env.PARITY_EXPORT_DIR ?? td();
        ms(dir, { recursive: true });
        filePath = j(dir, `parity_export_${process.pid}.csv`);
      }
      return await Facade.exportData(facade, args.sql as string, filePath, args.format as string);
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
  const caseObj: CaseFile = JSON.parse(caseText);

  // PathGuard on the facade requires dbPath to be inside allowedDirs().
  // The harness sets ACCESS_MCP_ALLOWED_DIRS in run.ts to include the
  // fixture dir + temp export dir; mirror that here.
  const { homedir } = await import("node:os");
  const allowedDirs = (process.env.ACCESS_MCP_ALLOWED_DIRS ?? homedir())
    .split(";")
    .filter((s) => s.length > 0);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Composition = CompositionModule as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Facade = FacadeModule as FacadeModule;

  const factory = Composition.realFactory as () => Promise<unknown>;
  const facade = Facade.make(
    undefined, // pool
    factory,   // factory
    false,     // comAvailable
    undefined, // readonly
    () => allowedDirs, // allowedDirs
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
  }

  const envelope = await runOperation(Facade, facade, caseObj.operation, caseObj.args ?? {});

  // Disconnect after non-lifecycle ops to leave a clean pool for the next
  // child process. Errors here are non-fatal (the child is exiting anyway).
  if (!lifecycle.has(caseObj.operation)) {
    try {
      await Facade.disconnectAccess(facade);
    } catch {
      // ignore
    }
  }

  process.stdout.write(JSON.stringify(envelope));
}

main().catch((err: unknown) => {
  process.stderr.write(`runRescript: ${(err as Error)?.message ?? String(err)}\n`);
  if ((err as Error)?.stack) process.stderr.write((err as Error).stack + "\n");
  process.exit(1);
});
