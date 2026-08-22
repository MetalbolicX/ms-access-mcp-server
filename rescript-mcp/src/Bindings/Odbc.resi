// Bindings/Odbc.resi — sole FFI owner of the odbc npm package
// Lazy dynamic import keeps this side-effect-free so unit tests
// run on machines without unixODBC/ACE drivers installed.
// Only this module may reference the odbc package.

/// <reference types="node" />  // node-odbc TypeScript declarations

// ---------------------------------------------------------------------------
// Value representation at the FFI boundary (D3)
// Null | Int | Float | Bool | Str | DateTime | Buffer
// ---------------------------------------------------------------------------

type oDBcValue = Null | Int(int) | Float(float) | Bool(bool) | Str(string) | DateTime(Date.t) | Buffer(NodeJs.Buffer.t)
type oDBcRow = dict<oDBcValue>

type oDBcResult = {
  rows: array<oDBcRow>,
  columns: array<string>,
  count: int,
  statement: option<string>,
}

type oDBcError = {
  message: string,
  code: option<string>,
  state: option<string>,
}

// ---------------------------------------------------------------------------
// Connection — plain record wrapper owned by Bindings only
// OdbcAdapter holds an instance; SqlBuilder is pure (no connection dependency)
// ---------------------------------------------------------------------------

type connection = {
  query: (string, array<JSON.t>) => Promise.t<result<oDBcResult, Errors.t>>,
  tables: (
    ~catalog: option<string>=?,
    ~schema: option<string>=?,
    ~table: option<string>=?,
    ~tableType: option<string>=?,
  ) => Promise.t<result<array<oDBcRow>, Errors.t>>,
  columns: (
    ~catalog: option<string>=?,
    ~schema: option<string>=?,
    ~table: option<string>=?,
    ~column: option<string>=?,
  ) => Promise.t<result<array<oDBcRow>, Errors.t>>,
  close: unit => Promise.t<unit>,
}

// ---------------------------------------------------------------------------
// CONNECTION module type — adapter injection interface
// ---------------------------------------------------------------------------

module type CONNECTION = {
  let query: (string, array<JSON.t>) => Promise.t<result<oDBcResult, Errors.t>>
  let tables: (
    ~catalog: option<string>=?,
    ~schema: option<string>=?,
    ~table: option<string>=?,
    ~tableType: option<string>=?,
  ) => Promise.t<result<array<oDBcRow>, Errors.t>>
  let columns: (
    ~catalog: option<string>=?,
    ~schema: option<string>=?,
    ~table: option<string>=?,
    ~column: option<string>=?,
  ) => Promise.t<result<array<oDBcRow>, Errors.t>>
  let close: unit => Promise.t<unit>
}

// ---------------------------------------------------------------------------
// Native connection — from node-odbc (for odbc lazy import type)
// ---------------------------------------------------------------------------

type nativeConnection = {
  query: (string, array<JSON.t>) => Promise.t<oDBcResult>,
  tables: (
    ~catalog: option<string>=?,
    ~schema: option<string>=?,
    ~name: option<string>=?,
    ~type_: option<string>=?,
  ) => Promise.t<array<oDBcRow>>,
  columns: (
    ~catalog: option<string>=?,
    ~schema: option<string>=?,
    ~name: option<string>=?,
    ~column: option<string>=?,
  ) => Promise.t<array<oDBcRow>>,
  close: unit => Promise.t<unit>,
}

type odbcModule = {
  connect: string => Promise.t<nativeConnection>,
}

// ---------------------------------------------------------------------------
// connect — connection factory
// Returns Promise<result<connection, Errors.t>>
// ---------------------------------------------------------------------------

let connect: string => Promise.t<result<connection, Errors.t>>

// ---------------------------------------------------------------------------
// mapNativeError — folds code/state into message → DatabaseError (D4)
// ---------------------------------------------------------------------------

let mapNativeError: (string, option<string>, option<string>) => Errors.t

// ---------------------------------------------------------------------------
// valueToJson — OdbcValue → JSON.t for row normalization (D3/D8)
// Null → JSON.Null, Int/Float → Number, Bool → Bool, Str → String,
// DateTime → ISO-8601, Buffer → base64 string
// ---------------------------------------------------------------------------

let valueToJson: oDBcValue => JSON.t

// ---------------------------------------------------------------------------
// jsonToValue — JSON.t → JSON.t for param encoding (D5)
// JSON.Null stays Null (driver handles conversion to SQL NULL)
// ---------------------------------------------------------------------------

let jsonToValue: JSON.t => JSON.t

// ---------------------------------------------------------------------------
// odbc — lazy import accessor (for tests)
// ---------------------------------------------------------------------------

let odbc: unit => Promise.t<dict<odbcModule>>
