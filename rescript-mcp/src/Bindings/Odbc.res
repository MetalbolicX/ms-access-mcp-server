// Bindings/Odbc.res — sole FFI owner of the odbc npm package
// All other modules (SqlBuilder, OdbcAdapter) import types from here, never odbc directly.

/// <reference types="node" />  // node-odbc TypeScript declarations

// ---------------------------------------------------------------------------
// Types (mirrored from .resi)
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
// Connection — plain record wrapper (avoids complex first-class module syntax)
// Owned by Bindings only — OdbcAdapter holds an instance
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
// Connection factory module type (used by OdbcAdapter via module injection)
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
// Native connection interface (from node-odbc)
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

// ---------------------------------------------------------------------------
// odbc module type (returned by dynamic import)
// ---------------------------------------------------------------------------

// odbcModule — the shape of the dynamic import result
// In practice, node-odbc is a CJS module with a 'default' property containing the actual module.
// We treat the import result as opaque and narrow the type at the access point.
type odbcModule = {
  connect: string => Promise.t<nativeConnection>,
}

// ---------------------------------------------------------------------------
// Lazy dynamic import (D11/REQ-D11) — side-effect-free at module load time
// ---------------------------------------------------------------------------

@module("odbc")
// The import returns a CJS module namespace object.
// We treat it as dict<odbcModule> to access 'connect' and 'default'.
external _importOdbc: unit => Promise.t<dict<odbcModule>> = "import"

// ---------------------------------------------------------------------------
// Error mapping (D4) — fold code/state into message
// ---------------------------------------------------------------------------

let mapNativeError: (string, option<string>, option<string>) => Errors.t = (
  (message, code, state) => {
    let full = switch (code, state) {
    | (Some(c), Some(s)) => message ++ " [SQLSTATE " ++ s ++ ", " ++ c ++ "]"
    | (Some(c), None) => message ++ " [" ++ c ++ "]"
    | (None, Some(s)) => message ++ " [SQLSTATE " ++ s ++ "]"
    | (None, None) => message
    }
    Errors.databaseError(full)
  }
)

// ---------------------------------------------------------------------------
// exnMessage — extracts .message from a caught JS exception (exn type)
// ---------------------------------------------------------------------------

let exnMessage: exn => string = e => {
  let raw: option<string> = %raw("e => e && typeof e.message === 'string' ? e.message : null")(e)
  switch raw {
  | Some(m) => m
  | None => "Unknown error"
  }
}

// ---------------------------------------------------------------------------
// connect — creates a typed connection wrapper
// ---------------------------------------------------------------------------

let connect: string => Promise.t<result<connection, Errors.t>> = (
  (connectionString: string) => {
    _importOdbc(())
      ->Promise.then(m => {
        // Handle CJS: prefer default export, fall back to m itself
        // m is dict<odbcModule> from the @module("odbc") import
        let rawDefault: option<odbcModule> = Dict.get(m, "default")
        let rawMod: odbcModule = switch rawDefault {
        | Some(d) => d
        | None => %raw("m => m")(m)
        }
        rawMod.connect(connectionString)
          ->Promise.then(conn => {
            // Wrap native connection in our typed interface
            let c: connection = {
              query: ((sql, params) => {
                conn.query(sql, params)
                  ->Promise.then(r => Promise.resolve(Ok(r)))
                  ->Promise.catch(e => {
                    let msg = exnMessage(e)
                    Promise.resolve(Error(mapNativeError(msg, None, None)))
                  })
              }),
              tables: ((~catalog=?, ~schema=?, ~table=?, ~tableType=?) => {
                conn.tables(~catalog?, ~schema?, ~name=?table, ~type_=?tableType)
                  ->Promise.then(rows => Promise.resolve(Ok(rows)))
                  ->Promise.catch(e => {
                    let msg = exnMessage(e)
                    Promise.resolve(Error(mapNativeError(msg, None, None)))
                  })
              }),
              columns: ((~catalog=?, ~schema=?, ~table=?, ~column=?) => {
                conn.columns(~catalog?, ~schema?, ~name=?table, ~column?)
                  ->Promise.then(rows => Promise.resolve(Ok(rows)))
                  ->Promise.catch(e => {
                    let msg = exnMessage(e)
                    Promise.resolve(Error(mapNativeError(msg, None, None)))
                  })
              }),
              close: (() => conn.close(())),
            }
            Promise.resolve(Ok(c))
          })
          ->Promise.catch(e => {
            let msg = exnMessage(e)
            Promise.resolve(Error(mapNativeError(msg, None, None)))
          })
      })
      ->Promise.catch(e => {
        let msg = exnMessage(e)
        Promise.resolve(Error(Errors.databaseError(msg)))
      })
  }
: string => Promise.t<result<connection, Errors.t>>
)

// ---------------------------------------------------------------------------
// Value normalization (D3/D8) — OdbcValue → JSON.t
// ---------------------------------------------------------------------------

let valueToJson: oDBcValue => JSON.t = (
  (v: oDBcValue) => {
    switch v {
    | Null => JSON.Null
    | Int(n) => JSON.Number(Int.toFloat(n))
    | Float(f) => JSON.Number(f)
    | Bool(b) => JSON.Number(b ? 1.0 : 0.0)
    | Str(s) => JSON.String(s)
    | DateTime(d) => JSON.String(Date.toISOString(d))
    | Buffer(b) => {
        // Buffer → base64 string (D3: round-trips uncorrupted, not Python raw bytes)
        let encoded: string = %raw("b => b && typeof b.toString === 'function' ? b.toString('base64') : ''")(b)
        JSON.String(encoded)
      }
    }
  }
)

// ---------------------------------------------------------------------------
// Param encoding (D5) — JSON.t → JSON.t for driver params
// JSON.Null → Js.null (SQL NULL)
// ---------------------------------------------------------------------------

let jsonToValue: JSON.t => JSON.t = (
  (j: JSON.t) => {
    switch j {
    | JSON.Null => JSON.Null
    | JSON.Boolean(b) => JSON.Number(b ? 1.0 : 0.0)
    | JSON.Number(n) => {
        // JSON numbers don't distinguish int vs float — return as-is
        JSON.Number(n)
      }
    | JSON.String(s) => JSON.String(s)
    | JSON.Object(_) | JSON.Array(_) => {
        // Complex JSON — return as-is, driver serializes
        j
      }
    }
  }
)

// ---------------------------------------------------------------------------
// odbc — lazy import accessor for tests
// ---------------------------------------------------------------------------

let odbc: unit => Promise.t<dict<odbcModule>> = _importOdbc
