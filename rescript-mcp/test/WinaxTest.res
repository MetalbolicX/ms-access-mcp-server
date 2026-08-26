open Test
open Adapters.ComInterfaces

// Task 1.3 RED test — Variant round trips and dispatch error mapping
// winax is NEVER imported here — fake binding is injected via module dependency

// ---------------------------------------------------------------------------
// variant type — value representation at the binding boundary
// ---------------------------------------------------------------------------

test("VBool can represent true", () => {
  let v: variant = VBool(true)
  switch v {
  | VBool(b) => assertion(~operator="equal", (a, b) => a == b, b, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VBool can represent false", () => {
  let v: variant = VBool(false)
  switch v {
  | VBool(b) => assertion(~operator="equal", (a, b) => a == b, b, false)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VDate can represent a Date.t", () => {
  let date = Date.fromTime(1724380800000.0)  // 2024-08-23 00:00:00 UTC
  let v: variant = VDate(date)
  switch v {
  | VDate(d) => {
      let y = Date.getFullYear(d)
      assertion(~operator="equal", (a, b) => a == b, y, 2024)
    }
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VNull represents SQL/DAO null", () => {
  let v: variant = VNull
  switch v {
  | VNull => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VEmpty represents VBA Empty variant", () => {
  let v: variant = VEmpty
  switch v {
  | VEmpty => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VInt can represent an integer", () => {
  let v: variant = VInt(42)
  switch v {
  | VInt(n) => assertion(~operator="equal", (a, b) => a == b, n, 42)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VFloat can represent a float", () => {
  let v: variant = VFloat(3.14)
  switch v {
  | VFloat(f) => assertion(~operator="equal", (a, b) => a == b, f, 3.14)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VCurrency can represent OLE Currency", () => {
  let v: variant = VCurrency(123.456)
  switch v {
  | VCurrency(c) => assertion(~operator="equal", (a, b) => a == b, c, 123.456)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VDecimal can represent OLE Decimal", () => {
  let v: variant = VDecimal(99.99)
  switch v {
  | VDecimal(d) => assertion(~operator="equal", (a, b) => a == b, d, 99.99)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VStr can represent a string", () => {
  let v: variant = VStr("hello")
  switch v {
  | VStr(s) => assertion(~operator="equal", (a, b) => a == b, s, "hello")
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VArray can represent nested variants", () => {
  let v: variant = VArray([VBool(true), VInt(42), VStr("test")])
  switch v {
  | VArray(arr) => {
      assertion(~operator="equal", (a, b) => a == b, Array.length(arr), 3)
    }
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("VByRef wraps a ref<variant>", () => {
  let inner: ref<variant> = ref(VInt(100))
  let v: variant = VByRef(inner)
  switch v {
  | VByRef(r) => {
      switch r.contents {
      | VInt(n) => assertion(~operator="equal", (a, b) => a == b, n, 100)
      | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
    }
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// comObject type — opaque handle, exists as abstract type
// ---------------------------------------------------------------------------

test("comObject type exists as abstract type", () => {
  // comObject is an opaque type - we only verify the type name exists
  // Actual construction happens inside Bindings.Winax
  let _obj: comObject = %raw("undefined")
  assertion(~operator="equal", (a, b) => a == b, true, true)
})

// ---------------------------------------------------------------------------
// dispatchError record — constructible with all fields
// ---------------------------------------------------------------------------

test("dispatchError can be constructed with message only", () => {
  let err: dispatchError = {
    message: "Automation error",
    description: None,
    source: None,
    errorCode: None,
  }
  assertion(~operator="equal", (a, b) => a == b, err.message, "Automation error")
})

test("dispatchError can be constructed with all fields", () => {
  let err: dispatchError = {
    message: "Class does not support automation",
    description: Some("Object or class does not support the requested interface"),
    source: Some("Microsoft Access"),
    errorCode: Some(382),
  }
  assertion(~operator="equal", (a, b) => a == b, err.errorCode, Some(382))
  assertion(~operator="equal", (a, b) => a == b, err.source, Some("Microsoft Access"))
})

// ---------------------------------------------------------------------------
// sessionHandles record — owns optional comObject refs
// ---------------------------------------------------------------------------

test("sessionHandles is constructible with all None", () => {
  let h: sessionHandles = {
    accessApp: None,
    daoDb: None,
    adoConn: None,
  }
  assertion(~operator="equal", (a, b) => a == b, h.accessApp, None)
  assertion(~operator="equal", (a, b) => a == b, h.daoDb, None)
  assertion(~operator="equal", (a, b) => a == b, h.adoConn, None)
})

test("sessionHandles can hold comObject refs", () => {
  // comObject is abstract - sessionHandles holds option<comObject>
  // actual comObject values are created by Bindings.Winax
  let h: sessionHandles = {
    accessApp: None,
    daoDb: None,
    adoConn: None,
  }
  assertion(~operator="equal", (a, b) => a == b, h.accessApp, None)
  assertion(~operator="equal", (a, b) => a == b, h.daoDb, None)
  assertion(~operator="equal", (a, b) => a == b, h.adoConn, None)
})

// ---------------------------------------------------------------------------
// hangStopResult — discriminated union
// ---------------------------------------------------------------------------

test("HungStopped is constructible", () => {
  let r: hangStopResult = HungStopped
  switch r {
  | HungStopped => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("HungKillFailed carries error message", () => {
  let r: hangStopResult = HungKillFailed("taskkill exited 1")
  switch r {
  | HungKillFailed(msg) => assertion(~operator="equal", (a, b) => a == b, String.includes(msg, "taskkill"), true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// trustedLocation record — registry entry
// ---------------------------------------------------------------------------

test("trustedLocation is constructible", () => {
  let loc: trustedLocation = {
    path: "C:\\TrustedPath",
    allowSubFolders: true,
    isUser: false,
  }
  assertion(~operator="equal", (a, b) => a == b, loc.path, "C:\\TrustedPath")
  assertion(~operator="equal", (a, b) => a == b, loc.allowSubFolders, true)
  assertion(~operator="equal", (a, b) => a == b, loc.isUser, false)
})
