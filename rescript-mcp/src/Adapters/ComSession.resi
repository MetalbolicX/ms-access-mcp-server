// ComSession.resi — session lifecycle: SESSION module type
// Adapters.ComSession implements this module type

// winaxBindingOps type — mirrored from ComDataAdapter for seam test injection
type winaxBindingOps = {
  releaseSyncAwait: ComInterfaces.comObject => Promise.t<unit>,
  createObject: string => Promise.t<result<ComInterfaces.comObject, Errors.t>>,
  get: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>>,
  set: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>>,
  invoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>>,
  invokeAsObject: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<ComInterfaces.comObject, Errors.t>>,
  getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>>,
  getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>>,
  toVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>>,
  fromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>>,
  mapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t,
}

type t = {
  mutable handles: ComInterfaces.sessionHandles,
  mutable isConnected: bool,
  mutable pid: option<int>,
  mutable currentDb: option<ComInterfaces.comObject>,  // opened DAO Database (NOT DBEngine)
  mutable tempHandles: list<ComInterfaces.comObject>,  // Phase 5: per-op temp COM handles
}

module type SESSION = {
  let connect: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let getHandles: t => ComInterfaces.sessionHandles
  let getCurrentDb: t => option<ComInterfaces.comObject>
}

let make: unit => t
let connect: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
let disconnect: t => Promise.t<result<unit, Errors.t>>
let isConnected: t => Promise.t<result<bool, Errors.t>>
let getHandles: t => ComInterfaces.sessionHandles
let getCurrentDb: t => option<ComInterfaces.comObject>

// Seam exports for test injection
let setTestBinding: winaxBindingOps => unit
let clearTestBinding: unit => unit

// Phase 5: internal helpers for ComDataAdapter temp handle queue
let _enqueueTempRelease: (t, ComInterfaces.comObject) => Promise.t<unit>
let _flushTempHandles: t => Promise.t<unit>
