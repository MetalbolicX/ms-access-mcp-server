// LinkedTableContractTest.res — DDL contract tests using seam injection.
//
// Phase 2: validates the F6 (getLinkedTables stub) defect, plus F1/F2 paths
// for recreateLinkedTable and refreshLinkedTable.

open Test
open Adapters
open Adapters.ComInterfaces

// ---------------------------------------------------------------------------
// Mutable call log
// ---------------------------------------------------------------------------

module Log = {
  type entry =
    | Invoke(string, array<ComInterfaces.variant>)
    | InvokeAsObject(string, array<ComInterfaces.variant>)
    | Get(string)
    | Set(string, ComInterfaces.variant)
    | GetItem(ComInterfaces.variant)
    | GetCount

  let entries: ref<list<entry>> = ref(list{})
  let reset = () => { entries.contents = list{} }
  let log = (e: entry) => { entries.contents = list{e, ...entries.contents} }
  let hasInvoke = (methodName: string): bool => {
    let rec loop = (xs: list<entry>) =>
      switch xs {
      | list{} => false
      | list{Invoke(m, _), ...rest} => m == methodName || loop(rest)
      | list{_, ...rest} => loop(rest)
      }
    loop(entries.contents)
  }
  let hasInvokeAsObject = (methodName: string): bool => {
    let rec loop = (xs: list<entry>) =>
      switch xs {
      | list{} => false
      | list{InvokeAsObject(m, _), ...rest} => m == methodName || loop(rest)
      | list{_, ...rest} => loop(rest)
      }
    loop(entries.contents)
  }
}

let nextProxyRef: ref<option<ComInterfaces.comObject>> = ref(None)
let nextErrorRef: ref<option<Errors.t>> = ref(None)
let methodErrorRef: ref<option<(string, string, Errors.t)>> = ref(None)
// Sequential proxies for getItem enumeration
let proxyListRef: ref<list<ComInterfaces.comObject>> = ref(list{})
// getCount return value
let getCountValueRef: ref<int> = ref(0)

let proxyCounter: ref<int> = ref(0)

let makeFakeProxy: unit => ComInterfaces.comObject = () => {
  let n = proxyCounter.contents + 1
  proxyCounter := n
  %raw("(_n) => ({ __counter: _n })")(n)->Obj.magic
}

let makeFakeBinding: unit => ComDataAdapter.winaxBindingOps = () => {
  releaseSyncAwait: _ => Promise.resolve(),
  createObject: progid => Promise.resolve(Ok(makeFakeProxy())),
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
      | None =>
        // Pop from the head of the list (deterministic per-call)
        switch proxyListRef.contents {
        | list{} => Promise.resolve(Ok(nextProxyRef.contents->Option.getUnsafe))
        | list{hd, ...tl} => {
            proxyListRef := tl
            Promise.resolve(Ok(hd))
          }
        }
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
      | None => Promise.resolve(Ok(getCountValueRef.contents))
      }
    }
  },
  toVariant: v => {
    let json: JSON.t = switch v {
    | ComInterfaces.VBool(b) => JSON.Boolean(b)
    | ComInterfaces.VStr(s) => JSON.String(s)
    | ComInterfaces.VInt(n) => JSON.Number(Int.toFloat(n))
    | ComInterfaces.VFloat(f) => JSON.Number(f)
    | _ => JSON.Null
    }
    Promise.resolve(Ok(json))
  },
  fromVariant: json => {
    let v: ComInterfaces.variant = switch json {
    | JSON.Null => ComInterfaces.VNull
    | JSON.String(s) => ComInterfaces.VStr(s)
    | JSON.Number(n) => ComInterfaces.VInt(Float.toInt(n))
    | _ => ComInterfaces.VNull
    }
    Promise.resolve(Ok(v))
  },
  mapDispatchError: (message, _d, _s, _c) => Errors.databaseError(message),
}

let resetAll = () => {
  Log.reset()
  nextProxyRef := None
  nextErrorRef := None
  methodErrorRef := None
  proxyListRef := list{}
  getCountValueRef := 0
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

let buildConnectedAdapter = (db: ComInterfaces.comObject) => {
  let adapter = ComDataAdapter.DaoAdapter.make()
  adapter.isConnected = true
  let session = ComSession.make()
  session.isConnected = true
  session.currentDb = Some(db)
  adapter.session = Some(session)
  adapter
}

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
// F6: getLinkedTables must enumerate TableDefs, not return empty stub
// ---------------------------------------------------------------------------

testAsync("F6: getLinkedTables enumerates TableDefs — not empty stub", cb => {
  // DEFECT at ComDataAdapter.res:2848-2864:
  //   | Some(_db) =>
  //     Promise.resolve(Ok({success: true, error: None, linkedTables: []}))
  //
  // Production returns empty array without ever calling get("TableDefs"),
  // getCount, or getItem. Configure the fake to return 2 TableDef entries.
  installFake()
  let db = nextProxyRef.contents->Option.getUnsafe
  let adapter = buildConnectedAdapter(db)
  getCountValueRef := 2
  proxyListRef := list{makeFakeProxy(), makeFakeProxy()}

  ComDataAdapter.getLinkedTables(adapter)
    ->Promise.then(r => {
      uninstallFake()
      switch r {
      | Ok({success: true, linkedTables}) =>
        assertion(~operator="equal", (a, b) => a == b, Array.length(linkedTables) >= 2, true)
      | Ok(_) | Error(_) =>
        assertion(~operator="equal", (a, b) => a == b, false, true)
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

// ---------------------------------------------------------------------------
// F2: recreateLinkedTable — Delete error must propagate AND CreateTableDef NOT called
// ---------------------------------------------------------------------------

testAsync("F2: recreateLinkedTable Delete error propagates and CreateTableDef is not called", cb => {
  // DEFECT: in recreateLinkedTable, the Delete invoke result is also discarded,
  // so production continues and calls CreateTableDef even if Delete failed.
  installFake()
  let db = nextProxyRef.contents->Option.getUnsafe
  let adapter = buildConnectedAdapter(db)
  methodErrorRef := Some(("Delete", "invoke", Errors.databaseError("Delete failed")))

  ComDataAdapter.recreateLinkedTable(adapter, "T", "Src", "DSN=x")
    ->Promise.then(r => {
      let createTableDefCalled = Log.hasInvokeAsObject("CreateTableDef")
      uninstallFake()
      switch r {
      | Error(_) =>
        // Correct: Error propagated. Verify CreateTableDef was NOT called.
        assertion(~operator="equal", (a, b) => a == b, createTableDefCalled, false)
      | Ok(_) =>
        // Defect: Error was discarded, production continued to CreateTableDef.
        assertion(~operator="equal", (a, b) => a == b, false, true)
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

// ---------------------------------------------------------------------------
// F2: refreshLinkedTable — set Connect error must propagate AND RefreshLink NOT called
// ---------------------------------------------------------------------------

testAsync("F2: refreshLinkedTable set Connect error propagates and RefreshLink is not called", cb => {
  // DEFECT: in refreshLinkedTable, set Connect result is discarded.
  installFake()
  let db = nextProxyRef.contents->Option.getUnsafe
  let adapter = buildConnectedAdapter(db)
  methodErrorRef := Some(("Connect", "set", Errors.databaseError("Set Connect failed")))

  ComDataAdapter.refreshLinkedTable(adapter, "T", ~connectString=?Some("DSN=x"))
    ->Promise.then(r => {
      let refreshLinkCalled = Log.hasInvoke("RefreshLink")
      uninstallFake()
      switch r {
      | Error(_) =>
        assertion(~operator="equal", (a, b) => a == b, refreshLinkCalled, false)
      | Ok(_) =>
        // Defect: Error was discarded, production continued to RefreshLink.
        assertion(~operator="equal", (a, b) => a == b, false, true)
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
