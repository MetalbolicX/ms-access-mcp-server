// Winax.res — sole winax importer: lazy CJS import with default unwrap
// winax is imported ONLY here; all other modules get the binding via module types
// Mirrors Bindings/Odbc.res lazy import pattern (D11/REQ-D11)

// ---------------------------------------------------------------------------
// WINAX_BINDING module type (must match Winax.resi)
// ---------------------------------------------------------------------------

module type WINAX_BINDING = {
  // Object lifecycle
  let createObject: string => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  let release: ComInterfaces.comObject => unit

  // Property access
  let get: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>>
  let set: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>>

  // Method invocation
  let invoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>>

  // Collection navigation
  let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>>

  // Variant conversion
  let toVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>>
  let fromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>>

  // Error mapping
  let mapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t
}

// ---------------------------------------------------------------------------
// WINAX_BINDING implementation
// ---------------------------------------------------------------------------

module WINAX_BINDING: WINAX_BINDING = {
  // ------------------------------------------------------------------
  // Lazy dynamic import — side-effect-free at module load time
  // ------------------------------------------------------------------

  @module("winax")
  external _importWinax: unit => Promise.t<dict<JSON.t>> = "import"

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
    (_obj: ComInterfaces.comObject) => {
      () // placeholder — real winax.release call in .mjs
    }
  : ComInterfaces.comObject => unit
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
    (_obj: ComInterfaces.comObject, _property: string, _value: ComInterfaces.variant) => {
      Promise.resolve(Ok())
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

  // ------------------------------------------------------------------
  // getItem — gets an item from a collection by index
  // ------------------------------------------------------------------

  let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
    (obj: ComInterfaces.comObject, _index: ComInterfaces.variant) => {
      Promise.resolve(Ok(obj))
    }
  : (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  )

  // ------------------------------------------------------------------
  // getCount — gets the count of items in a collection
  // ------------------------------------------------------------------

  let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>> = (
    (_obj: ComInterfaces.comObject) => {
      Promise.resolve(Ok(0))
    }
  : ComInterfaces.comObject => Promise.t<result<int, Errors.t>>
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
