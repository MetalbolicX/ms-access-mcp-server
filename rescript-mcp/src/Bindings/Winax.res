// Winax.res — sole winax importer: lazy CJS import with default unwrap
// winax is imported ONLY here; all other modules get the binding via module types
// Mirrors Bindings/Odbc.res lazy import pattern (D11/REQ-D11)

// ---------------------------------------------------------------------------
// WINAX_BINDING module type (must match Winax.resi)
// ---------------------------------------------------------------------------

// Preserved COM error record — plan 039. Keeps the numeric scode and structured
// description for callers (e.g. executeSqlScript) that need accessErrorCode
// parity with the Python oracle. Exported through WINAX_BINDING below.
type preservedError = {
  message: string,
  number: option<int>,
  code: option<int>,
  hresult: option<int>,
  description: option<string>,
  source: option<string>,
}

module type WINAX_BINDING = {
  // Object lifecycle
  let createObject: string => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  let release: ComInterfaces.comObject => unit
  let releaseAsync: ComInterfaces.comObject => Promise.t<unit>

  // Property access
  let get: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>>
  let set: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>>

  // Method invocation
  let invoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>>

  // Collection navigation
  let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>>

  // invokeAsObject — for methods returning COM handles (OpenDatabase, OpenRecordset, etc.)
  let invokeAsObject: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<ComInterfaces.comObject, Errors.t>>

  // Variant conversion
  let toVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>>
  let fromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>>

  // Error mapping
  let mapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t

  // Plan 039: structured-error invoke — preserves .number/.description for
  // accessErrorCode parity. Same call path as invoke, but the catch returns
  // the raw COM error fields instead of flattening to a string.
  let invokePreservingError: (
    ComInterfaces.comObject,
    string,
    array<ComInterfaces.variant>,
  ) => Promise.t<result<JSON.t, preservedError>>
}

// ---------------------------------------------------------------------------
// WINAX_BINDING implementation
// ---------------------------------------------------------------------------

module WINAX_BINDING: WINAX_BINDING = {
  // ------------------------------------------------------------------
  // Lazy dynamic import — side-effect-free at module load time
  // ------------------------------------------------------------------

  // _importWinax — dynamic-import the winax package as a JS Promise.
  // Was `@module("winax") external … = "import"` which compiled to
  // `Winax.import()` (a named export that does not exist on the winax CJS
  // module). The %raw escape hatch delegates to a real dynamic
  // `import("winax")`. Mirrors Bindings/Odbc.res (D11/REQ-D11).
  let _importWinax: unit => Promise.t<dict<JSON.t>> = () => {
    %raw("(p) => import(p)")("winax")->Promise.resolve
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  let exnMessage: exn => string = e => {
    let raw: option<string> = TsBridge.exnMessage(e)
    switch raw {
    | Some(m) => m
    | None => "Unknown error"
    }
  }

  let hexString: int => string = n => "0x" ++ Int.toString(n)

  // ------------------------------------------------------------------
  // variantToJson — synchronous variant ADT → JSON.t marshaling
  // ------------------------------------------------------------------

  let variantToJson: ComInterfaces.variant => JSON.t = (v: ComInterfaces.variant) => {
    switch v {
    | ComInterfaces.VBool(b) => JSON.Boolean(b)
    | ComInterfaces.VDate(d) => JSON.String(Date.toISOString(d))
    | ComInterfaces.VNull => JSON.Null
    | ComInterfaces.VEmpty => JSON.Null
    | ComInterfaces.VInt(n) => JSON.Number(Int.toFloat(n))
    | ComInterfaces.VFloat(f) => JSON.Number(f)
    | ComInterfaces.VCurrency(c) => JSON.Number(c)
    | ComInterfaces.VDecimal(d) => JSON.Number(d)
    | ComInterfaces.VStr(s) => JSON.String(s)
    | ComInterfaces.VArray(_) => JSON.Null
    | ComInterfaces.VByRef(_) => JSON.Null
    }
  }

  // ------------------------------------------------------------------
  // Error mapping — fold dispatch errors to Errors.DatabaseError
  // ------------------------------------------------------------------

  let mapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t = (
    (message, description, source, errorCode) => {
      let full = switch (description, source, errorCode) {
      | (Some(d), Some(s), Some(c)) => message ++ " [" ++ s ++ ": " ++ d ++ " (" ++ hexString(c) ++ ")]"
      | (Some(d), Some(s), None) => message ++ " [" ++ s ++ ": " ++ d ++ "]"
      | (Some(d), None, Some(c)) => message ++ " [" ++ d ++ " (" ++ hexString(c) ++ ")]"
      | (Some(d), None, None) => message ++ " [" ++ d ++ "]"
      | (None, Some(s), Some(c)) => message ++ " [" ++ s ++ " (" ++ hexString(c) ++ ")]"
      | (None, Some(s), None) => message ++ " [" ++ s ++ "]"
      | (None, None, Some(c)) => message ++ " [" ++ hexString(c) ++ "]"
      | (None, None, None) => message
      }
      Errors.databaseError(full)
    }
  )

  // ------------------------------------------------------------------
  // createObject — creates a COM object by progid
  // ------------------------------------------------------------------

  let createObject: string => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
    (progid: string) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          let obj: ComInterfaces.comObject = TsBridge.winaxCreateObject(rawMod, progid)
          Promise.resolve(Ok(obj))
        })
        ->Promise.catch(e => {
          let msg = exnMessage(e)
          Promise.resolve(Error(Errors.databaseError(msg)))
        })
    }
  : string => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  )

  // ------------------------------------------------------------------
  // release — releases a COM object
  // ------------------------------------------------------------------

  let release: ComInterfaces.comObject => unit = (
    (obj: ComInterfaces.comObject) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          TsBridge.winaxRelease(rawMod, obj)
          Promise.resolve()
        })
        ->Promise.catch(_ => Promise.resolve())
        ->ignore
    }
  : ComInterfaces.comObject => unit
  )

  let releaseAsync: ComInterfaces.comObject => Promise.t<unit> = (
    (obj: ComInterfaces.comObject) => {
      _importWinax(())->Promise.then(m => {
        let rawMod = TsBridge.unwrapWinaxModule(m)
        TsBridge.winaxRelease(rawMod, obj)
        Promise.resolve()
      })->Promise.catch(_ => Promise.resolve())
    }: ComInterfaces.comObject => Promise.t<unit>
  )

  // ------------------------------------------------------------------
  // get — reads a property from a COM object via winax.cast(obj, prop)
  // ------------------------------------------------------------------

  let get: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>> = (
    (obj: ComInterfaces.comObject, property: string) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          let value: JSON.t = TsBridge.winaxGetProperty(rawMod, obj, property)
          Promise.resolve(Ok(value))
        })
        ->Promise.catch(e => {
          let msg = exnMessage(e)
          Promise.resolve(Error(mapDispatchError(msg, None, None, None)))
        })
    }
  : (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>>
  )

  // ------------------------------------------------------------------
  // set — writes a property on a COM object
  // ------------------------------------------------------------------

  let set: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>> = (
    (obj: ComInterfaces.comObject, property: string, value: ComInterfaces.variant) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          TsBridge.winaxSetProperty(rawMod, obj, property, variantToJson(value))
          Promise.resolve(Ok())
        })
        ->Promise.catch(e => {
          let msg = exnMessage(e)
          Promise.resolve(Error(mapDispatchError(msg, None, None, None)))
        })
    }
  : (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>>
  )

  // ------------------------------------------------------------------
  // invoke — calls a method on a COM object
  // ------------------------------------------------------------------

  let invoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>> = (
    (obj: ComInterfaces.comObject, method: string, args: array<ComInterfaces.variant>) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          // Marshal each variant synchronously — winax accepts raw JS values directly
          let rawArgs: array<JSON.t> = Array.map(args, v => variantToJson(v))
          let value: JSON.t = TsBridge.winaxInvokeMethod(rawMod, obj, method, rawArgs)
          Promise.resolve(Ok(value))
        })
        ->Promise.catch(e => {
          let msg = exnMessage(e)
          Promise.resolve(Error(mapDispatchError(msg, None, None, None)))
        })
    }
  : (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>>
  )

  // --------------------------------------------------------------------------
  // invokeAsObject — calls a method that returns a COM handle (not JSON data)
  // --------------------------------------------------------------------------

  let invokeAsObject: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
    (obj: ComInterfaces.comObject, method: string, args: array<ComInterfaces.variant>) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          let rawArgs: array<JSON.t> = Array.map(args, v => variantToJson(v))
          let result: ComInterfaces.comObject = TsBridge.winaxInvokeReturningObject(rawMod, obj, method, rawArgs)
          Promise.resolve(Ok(result))
        })
        ->Promise.catch(e => {
          let msg = exnMessage(e)
          Promise.resolve(Error(mapDispatchError(msg, None, None, None)))
        })
    }
  : (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  )

  // ------------------------------------------------------------------
  // invokePreservingError — plan 039. Same call path as `invoke`, but the
  // catch arm returns the raw COM error fields (scode, description, source)
  // instead of flattening to a string via mapDispatchError. This preserves
  // accessErrorCode for parity with the Python oracle's _extract_com_error.
  // The %raw body is a FUNCTION LITERAL `(e) => {...}` — never an IIFE
  // (see ComDataAdapter.res:57-59 for the rationale).
  //
  // Note on `number` vs `code`: pywin32 surfaces the scode on the COMError
  // as `.number`; winax surfaces it as `.code` (verified via probe — the
  // thrown error has keys [errno, code, source, description], `.code` is
  // the numeric scode, `.number` is undefined). The `number` slot in the
  // preservedError record is populated by falling back to `.code` so the
  // executeSqlScript caller can use a single field for parity with Python.
  // ------------------------------------------------------------------

  let invokePreservingError: (
    ComInterfaces.comObject,
    string,
    array<ComInterfaces.variant>,
  ) => Promise.t<result<JSON.t, preservedError>> = (
    (obj: ComInterfaces.comObject, method: string, args: array<ComInterfaces.variant>) => {
      _importWinax(())
        ->Promise.then(m => {
          let rawMod = TsBridge.unwrapWinaxModule(m)
          let rawArgs: array<JSON.t> = Array.map(args, v => variantToJson(v))
          let value: JSON.t = TsBridge.winaxInvokeMethod(rawMod, obj, method, rawArgs)
          Promise.resolve(Ok(value))
        })
        ->Promise.catch(e => {
          let captured: preservedError = %raw(
            "(e) => { var inner = (e && typeof e === 'object' && e._1 && typeof e._1 === 'object') ? e._1 : e; var numOrNull = function(v) { return (typeof v === 'number' && v !== 0) ? v : null; }; var strOrNull = function(v) { return (typeof v === 'string' && v.length > 0) ? v : null; }; if (!inner || typeof inner !== 'object') { return { message: 'Unknown error', number: null, code: null, hresult: null, description: null, source: null }; } var pyNum = numOrNull(inner.number); var wxCode = numOrNull(inner.code); var wxHres = numOrNull(inner.hresult); var numberOut = (pyNum !== null) ? pyNum : (wxCode !== null) ? wxCode : (wxHres !== null) ? wxHres : null; return { message: (inner.message !== undefined && inner.message !== null && inner.message !== '') ? String(inner.message) : 'Unknown error', number: numberOut, code: wxCode, hresult: wxHres, description: strOrNull(inner.description), source: strOrNull(inner.source) }; }"
          )(e)
          Promise.resolve(Error(captured))
        })
    }: (
      ComInterfaces.comObject,
      string,
      array<ComInterfaces.variant>,
    ) => Promise.t<result<JSON.t, preservedError>>
  )

  // ------------------------------------------------------------------
  // getCount — gets the count of items in a collection
  // ------------------------------------------------------------------

  let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>> = (
    (obj: ComInterfaces.comObject) => {
      get(obj, "Count")
        ->Promise.then(r => switch r {
        | Ok(JSON.Number(n)) => Promise.resolve(Ok(Float.toInt(n)))
        | Ok(JSON.String(s)) => Promise.resolve(Ok(Int.fromString(s)->Option.getOr(0)))
        | Ok(_) => Promise.resolve(Error(Errors.databaseError("Count not numeric")))
        | Error(e) => Promise.resolve(Error(e))
        })
    }
  : ComInterfaces.comObject => Promise.t<result<int, Errors.t>>
  )

  // ------------------------------------------------------------------
  // getItem — gets an item from a collection by index
  // ------------------------------------------------------------------

  let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
    (obj: ComInterfaces.comObject, index: ComInterfaces.variant) => {
      invokeAsObject(obj, "Item", [index])
    }
  : (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  )

  // ------------------------------------------------------------------
  // toVariant — converts our variant ADT to winax-compatible JSON
  // ------------------------------------------------------------------

  let toVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>> = (
    (v: ComInterfaces.variant) => Promise.resolve(Ok(variantToJson(v)))
  )

  // ------------------------------------------------------------------
  // fromVariant — converts winax JSON back to our variant ADT
  // ------------------------------------------------------------------

  let fromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>> = (
    (json: JSON.t) => {
      let v: ComInterfaces.variant = switch json {
      | JSON.Null => ComInterfaces.VNull
      | JSON.Boolean(b) => ComInterfaces.VBool(b)
      | JSON.Number(n) => {
          let i = Float.toInt(n)
          if n == Int.toFloat(i) {
            ComInterfaces.VInt(i)
          } else {
            ComInterfaces.VFloat(n)
          }
        }
      | JSON.String(s) => ComInterfaces.VStr(s)
      | JSON.Array(_) | JSON.Object(_) => ComInterfaces.VNull
      }
      Promise.resolve(Ok(v))
    }
  )
}
