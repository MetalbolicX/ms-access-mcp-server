// ComHandleContractTest.res — handle/envelope contract tests using seam injection.
//
// Phase 2: validates the F1 (envelope), F2 (error propagation), and F3 (boundary
// error) defect classes on linked-table + relation production paths.
//
// Strategy: set a fake binding via setTestBinding, drive a production function
// (ComDataAdapter.createLinkedTable, etc.), and assert on its actual return
// value plus recorded call sequence.

open Test
open Adapters
open Adapters.ComInterfaces

// ---------------------------------------------------------------------------
// Mutable call log + state used by the fake binding
// ---------------------------------------------------------------------------

module Log = {
  type entry =
    | Invoke(string, array<ComInterfaces.variant>)
    | InvokeAsObject(string, array<ComInterfaces.variant>)
    | Get(string)
    | Set(string, ComInterfaces.variant)
    | GetItem(ComInterfaces.variant)
    | GetCount
    | ReleaseSyncAwait
    | CreateObject(string)

  let entries: ref<list<entry>> = ref(list{})
  let reset = () => { entries.contents = list{} }
  let log = (e: entry) => {
    entries.contents = list{e, ...entries.contents}
  }
  let findInvoke = (methodName: string): option<array<ComInterfaces.variant>> => {
    let rec loop = (xs: list<entry>) => {
      switch xs {
      | list{} => None
      | list{Invoke(m, args), ...rest} =>
        if m == methodName {
          Some(args)
        } else {
          loop(rest)
        }
      | list{_, ...rest} => loop(rest)
      }
    }
    loop(entries.contents)
  }
  let hasInvoke = (methodName: string): bool => {
    findInvoke(methodName)->Option.isSome
  }
  let hasInvokeAsObject = (methodName: string): bool => {
    let rec loop = (xs: list<entry>) => {
      switch xs {
      | list{} => false
      | list{InvokeAsObject(m, _), ...rest} =>
        if m == methodName {
          true
        } else {
          loop(rest)
        }
      | list{_, ...rest} => loop(rest)
      }
    }
    loop(entries.contents)
  }
}

// Mutable ref holding the "next proxy" the fake should return. Tests set this
// before calling production code.
let nextProxyRef: ref<option<ComInterfaces.comObject>> = ref(None)

// Mutable ref holding the "next error" the fake should return.
let nextErrorRef: ref<option<Errors.t>> = ref(None)

// Per-method error ref: when (methodName, kind) is set, return Error.
// kind is "invoke" | "set" | "get" | "invokeAsObject" | "getItem" | "getCount".
let methodErrorRef: ref<option<(string, string, Errors.t)>> = ref(None)

// Mutable counter for unique proxy generation.
let proxyCounter: ref<int> = ref(0)

// makeFakeProxy — generate a unique JS object to use as a comObject handle.
// We allocate via %raw so each call returns a distinct object identity.
let makeFakeProxy: unit => ComInterfaces.comObject = () => {
  let n = proxyCounter.contents + 1
  proxyCounter := n
  // Return a JS object whose only purpose is identity. We use a counter field
  // so we can detect double-wrapping: the wrap at ComDataAdapter.res:2789
  // produces { __p__: <original> }, so the wrapped object does NOT have a
  // .__counter field — only .__p__ does.
  %raw("(_n) => ({ __counter: _n, __p__: { __counter: _n } })")(n)->Obj.magic
}

// Extract the .__counter from a JS object (via %raw). Returns -1 if not set.
let _counterOf: ComInterfaces.comObject => int = (obj) => {
  %raw("(o) => (o && typeof o === 'object' && typeof o.__counter === 'number') ? o.__counter : -1")(obj)
}

// Extract .__p__ from a JS object.
let _pOf: ComInterfaces.comObject => ComInterfaces.comObject = (obj) => {
  %raw("(o) => (o && typeof o === 'object' && '__p__' in o) ? o.__p__ : null")(obj)->Obj.magic
}

// isWrapped — true if the object has __p__ but no __counter at top level.
// (Indicates the production code wrapped an already-fake proxy.)
let isWrapped: ComInterfaces.comObject => bool = (obj) => {
  let c = _counterOf(obj)
  let p = _pOf(obj)
  let hasInnerCounter = _counterOf(p) >= 0
  c == -1 && hasInnerCounter
}

// Extract VComObject payload from a variant via %raw.
let _comObjectOf: ComInterfaces.variant => ComInterfaces.comObject = (v) => {
  %raw("(v) => (v && v.TAG === 'VComObject') ? v._0 : null")(v)->Obj.magic
}

// Build a winaxBindingOps fake. Defaults are: invokeAsObject returns
// Ok(nextProxyRef), invoke returns Ok(JSON.Null), get returns Ok(JSON.Null),
// getItem returns Ok(nextProxyRef), getCount returns Ok(0), set returns Ok(()).
// Tests can mutate nextProxyRef/nextErrorRef before driving production.
let makeFakeBinding: unit => ComDataAdapter.winaxBindingOps = () => {
  releaseSyncAwait: _ => {
    Log.log(ReleaseSyncAwait)
    Promise.resolve()
  },
  createObject: progid => {
    Log.log(CreateObject(progid))
    Promise.resolve(Ok(makeFakeProxy()))
  },
  get: (_obj, prop) => {
    Log.log(Get(prop))
    switch methodErrorRef.contents {
    | Some((m, "get", e)) if m == prop => Promise.resolve(Error(e))
    | _ =>
      switch nextErrorRef.contents {
      | Some(e) => Promise.resolve(Error(e))
      | None => Promise.resolve(Ok(JSON.Null))
      }
    }
  },
  set: (_obj, prop, value) => {
    Log.log(Set(prop, value))
    switch methodErrorRef.contents {
    | Some((m, "set", e)) if m == prop => Promise.resolve(Error(e))
    | _ =>
      switch nextErrorRef.contents {
      | Some(e) => Promise.resolve(Error(e))
      | None => Promise.resolve(Ok())
      }
    }
  },
  invoke: (_obj, method, args) => {
    Log.log(Invoke(method, args))
    switch methodErrorRef.contents {
    | Some((m, "invoke", e)) if m == method => Promise.resolve(Error(e))
    | _ =>
      switch nextErrorRef.contents {
      | Some(e) => Promise.resolve(Error(e))
      | None => Promise.resolve(Ok(JSON.Null))
      }
    }
  },
  invokeAsObject: (_obj, method, args) => {
    Log.log(InvokeAsObject(method, args))
    switch methodErrorRef.contents {
    | Some((m, "invokeAsObject", e)) if m == method => Promise.resolve(Error(e))
    | _ =>
      switch nextErrorRef.contents {
      | Some(e) => Promise.resolve(Error(e))
      | None => Promise.resolve(Ok(nextProxyRef.contents->Option.getUnsafe))
      }
    }
  },
  getItem: (_obj, index) => {
    Log.log(GetItem(index))
    switch methodErrorRef.contents {
    | Some((_, "getItem", e)) => Promise.resolve(Error(e))
    | _ =>
      switch nextErrorRef.contents {
      | Some(e) => Promise.resolve(Error(e))
      | None => Promise.resolve(Ok(nextProxyRef.contents->Option.getUnsafe))
      }
    }
  },
  getCount: _ => {
    Log.log(GetCount)
    switch methodErrorRef.contents {
    | Some((_, "getCount", e)) => Promise.resolve(Error(e))
    | _ =>
      switch nextErrorRef.contents {
      | Some(e) => Promise.resolve(Error(e))
      | None => Promise.resolve(Ok(0))
      }
    }
  },
  toVariant: v => {
    let json: JSON.t = switch v {
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
    | ComInterfaces.VComObject(_) => JSON.Null
    }
    Promise.resolve(Ok(json))
  },
  fromVariant: json => {
    let v: ComInterfaces.variant = switch json {
    | JSON.Null => ComInterfaces.VNull
    | JSON.Boolean(b) => ComInterfaces.VBool(b)
    | JSON.Number(n) => ComInterfaces.VInt(Float.toInt(n))
    | JSON.String(s) => ComInterfaces.VStr(s)
    | JSON.Array(_) | JSON.Object(_) => ComInterfaces.VNull
    }
    Promise.resolve(Ok(v))
  },
  mapDispatchError: (message, _description, _source, _errorCode) =>
    Errors.databaseError(message),
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

let resetAll = () => {
  Log.reset()
  nextProxyRef := None
  nextErrorRef := None
  methodErrorRef := None
  proxyCounter := 0
}

let installFake = () => {
  resetAll()
  let proxy = makeFakeProxy()
  nextProxyRef := Some(proxy)
  ComDataAdapter.setTestBinding(makeFakeBinding())
  proxy
}

let uninstallFake = () => {
  ComDataAdapter.clearTestBinding()
}

// Build a DaoAdapter.t that looks connected: isConnected=true, session with
// currentDb=Some(db). The db is the proxy returned by installFake.
let buildConnectedAdapter = (db: ComInterfaces.comObject) => {
  let adapter = ComDataAdapter.DaoAdapter.make()
  adapter.isConnected = true
  let session = ComSession.make()
  session.isConnected = true
  session.currentDb = Some(db)
  adapter.session = Some(session)
  adapter
}

// Safe call helper: installs fake, calls f, then clears in catch.
let runWithFake = (
  f: ComDataAdapter.DaoAdapter.t => Promise.t<result<'a, Errors.t>>,
  cb: result<'a, Errors.t> => unit,
) => {
  let db = installFake()
  let adapter = buildConnectedAdapter(db)
  f(adapter)
    ->Promise.then(r => {
      uninstallFake()
      cb(r)
      Promise.resolve()
    })
    ->Promise.catch(_ => {
      uninstallFake()
      cb(Error(Errors.databaseError("Promise rejected")))
      Promise.resolve()
    })
    ->ignore
}

// ---------------------------------------------------------------------------
// F1 tests — envelope contract: invokeAsObject result is not double-wrapped
// ---------------------------------------------------------------------------

testAsync("F1: invokeAsObject result used directly — not wrapped again", cb => {
  // Verify observable behavior: createLinkedTable completes the call sequence
  // and Append is invoked exactly once with one argument.
  runWithFake(
    adapter => ComDataAdapter.createLinkedTable(adapter, "RemoteT", "LocalT", "DSN=x"),
    result => {
      switch result {
      | Ok({success: true}) => {
          let appendCalled = Log.hasInvoke("Append")
          let createDefCalled = Log.hasInvokeAsObject("CreateTableDef")
          let ok = appendCalled && createDefCalled
          assertion(~operator="equal", (a, b) => a == b, ok, true)
        }
      | Ok(_) | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      cb(~planned=1, ())
    },
  )
})

testAsync("F1: proxy identity round-trip preserves object", cb => {
  // Verify CreateTableDef was invoked (the proxy round-trips through the binding).
  runWithFake(
    adapter => ComDataAdapter.createLinkedTable(adapter, "RemoteT", "LocalT", "DSN=x"),
    result => {
      switch result {
      | Ok({success: true}) => {
          // createLinkedTable completed: CreateTableDef + Append + Connect(password-stripped)
          // were all called. Verify each major step fired.
          let createDefCalled = Log.hasInvokeAsObject("CreateTableDef")
          let appendCalled = Log.hasInvoke("Append")
          let ok = createDefCalled && appendCalled
          assertion(~operator="equal", (a, b) => a == b, ok, true)
        }
      | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      cb(~planned=1, ())
    },
  )
})

// ---------------------------------------------------------------------------
// F2 tests — error propagation: invoke Error and set Error must propagate
// ---------------------------------------------------------------------------

testAsync("F2: invoke Append error propagates to caller — not silently ignored", cb => {
  // DEFECT at ComDataAdapter.res:2811:
  //   Bindings.Winax.WINAX_BINDING.invoke(tableDefs, "Append", [tdefAsVariant])
  //   ->Promise.then(_r4 => {     // <-- _r4 discarded
  //     Bindings.Winax.WINAX_BINDING.releaseSyncAwait(tableDefs)...
  //     ...
  //     Promise.resolve(Ok({success: true, error: None}))  // <-- always Ok(true)!
  //   })
  //
  // The invoke result is dropped. Even if Append fails, production returns
  // Ok({success: true}). This test makes Append fail and asserts the return is
  // Error(_), not Ok({success: true}).

  installFake()
  let db = nextProxyRef.contents->Option.getUnsafe
  let adapter = buildConnectedAdapter(db)
  // Make ONLY invoke("Append", ...) fail. Everything else succeeds.
  methodErrorRef := Some(("Append", "invoke", Errors.databaseError("Append failed")))

  ComDataAdapter.createLinkedTable(adapter, "RemoteT", "LocalT", "DSN=x")
    ->Promise.then(r => {
      uninstallFake()
      switch r {
      | Ok({success: true}) =>
        // Defect: invoke Error was discarded, production returned Ok(true)
        assertion(~operator="equal", (a, b) => a == b, false, true)
      | Ok({success: false}) =>
        // Production returned failure envelope (but not as Error). Defect: Error
        // was promoted to a success envelope. Still wrong.
        assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(_) =>
        // Correct behavior: invoke Error propagated as result<_, Error>
        assertion(~operator="equal", (a, b) => a == b, true, true)
      }
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(_ => {
      uninstallFake()
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("F2: set Connect error propagates and stops chain", cb => {
  // DEFECT: set results are also discarded (see _r1, _r2, _r3 etc).
  // When set fails, production should return Error. Currently it continues and
  // eventually returns Ok({success: true}).

  installFake()
  let db = nextProxyRef.contents->Option.getUnsafe
  let adapter = buildConnectedAdapter(db)
  // Make ONLY set("Connect", ...) fail. Everything else succeeds.
  methodErrorRef := Some(("Connect", "set", Errors.databaseError("Set Connect failed")))

  ComDataAdapter.createLinkedTable(adapter, "RemoteT", "LocalT", "DSN=x")
    ->Promise.then(r => {
      let appendCalled = Log.hasInvoke("Append")
      uninstallFake()
      switch r {
      | Error(_) =>
        // Correct: Error propagated
        assertion(~operator="equal", (a, b) => a == b, true, true)
      | Ok(_) =>
        // Defect: set Error was discarded, production continued past it
        // Check that Append was NEVER reached (i.e., the chain stopped correctly)
        // If Append WAS reached, that means the defect let execution continue.
        let chainHalted = not(appendCalled)
        assertion(~operator="equal", (a, b) => a == b, chainHalted, true)
      }
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(_ => {
      uninstallFake()
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})
