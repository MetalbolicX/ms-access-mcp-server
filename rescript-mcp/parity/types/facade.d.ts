// Hand-maintained type shim for the compiled ReScript facade module.
//
// When facade ops change, update this shim in the same commit that updates
// rescript-mcp/src/Services/Facade.res. We deliberately do NOT use a generator
// from .resi because ReScript->TS type emission is not stable.
//
// The dynamic import in runRescript.ts resolves through this shim.

/** JSON.t discriminated union mirroring the ReScript runtime encoding */
export type JsonT =
  | { TAG: "Null" }
  | { TAG: "String"; _0: string }
  | { TAG: "Number"; _0: number }
  | { TAG: "Boolean"; _0: boolean }
  | { TAG: "Object"; _0: Record<string, JsonT> }
  | { TAG: "Array"; _0: JsonT[] };

/** Facade.t binding — opaque to the harness (invoked only via facade methods) */
export type FacadeBinding = unknown;

/** bindingFactory signature (injected at Facade.make) */
export type BindingFactory = (
  backend: string | null,
  dbPath: string,
  password: string,
) => Promise<unknown>;

/** Allowed dirs getter (injected at Facade.make) */
export type AllowedDirsGetter = () => string[];

/** make() parameters */
export interface FacadeMakeOpts {
  pool?: unknown;
  factory: BindingFactory;
  comAvailable?: boolean;
  readonly_?: () => boolean;
  allowedDirs?: AllowedDirsGetter;
}

/** Facade instance — opaque to harness, used only to pass to facade methods */
export interface Facade {
  connectAccess: (facade: Facade, dbPath: string, opts?: ConnectOpts) => Promise<Record<string, JsonT>>;
  disconnectAccess: (facade: Facade, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  listConnections: (facade: Facade) => Record<string, JsonT>;
  isConnected: (facade: Facade, opts?: { name?: string }) => Record<string, JsonT>;
  setActiveConnection: (facade: Facade, name: string) => Promise<Record<string, JsonT>>;
  getActiveConnection: (facade: Facade) => Record<string, JsonT>;
  queryData: (facade: Facade, sql: string, opts?: QueryOpts) => Promise<Record<string, JsonT>>;
  getTables: (facade: Facade, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  getTableSchema: (facade: Facade, table: string, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  getRelationships: (facade: Facade, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  getQueries: (facade: Facade, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  getDatabaseStatistics: (facade: Facade, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  insertData: (facade: Facade, table: string, data: Record<string, JsonT>, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
  updateData: (facade: Facade, table: string, setDict: Record<string, JsonT>, whereDict: Record<string, JsonT> | undefined, name: string | undefined, confirm: boolean, dryRun: boolean) => Promise<Record<string, JsonT>>;
  deleteData: (facade: Facade, table: string, whereDict: Record<string, JsonT>, name: string | undefined, confirm: boolean, dryRun: boolean) => Promise<Record<string, JsonT>>;
  executeRawSql: (facade: Facade, sql: string, name: string | undefined, confirm: boolean, dryRun: boolean) => Promise<Record<string, JsonT>>;
  exportData: (facade: Facade, sql: string, filePath: string, format: string, opts?: ExportOpts) => Promise<Record<string, JsonT>>;
}

export interface ConnectOpts {
  name?: string;
  useCom?: boolean;
  password?: string;
  backend?: string;
}

export interface QueryOpts {
  params?: JsonT[];
  name?: string;
}

export interface ExportOpts {
  delimiter?: string;
  header?: boolean;
  name?: string;
}

/** Composition.realFactory — returns a Promise<FacadeBinding> */
export type RealFactory = () => Promise<unknown>;

/** Dynamic module exports from the compiled ReScript facade */
export interface FacadeModule {
  make: (opts: FacadeMakeOpts) => Facade;
  default: (factory: BindingFactory) => unknown;
}
