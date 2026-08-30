// ComSession.resi — session lifecycle: SESSION module type
// Adapters.ComSession implements this module type

type t = {
  mutable handles: ComInterfaces.sessionHandles,
  mutable isConnected: bool,
  mutable pid: option<int>,
}

module type SESSION = {
  let connect: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let getHandles: t => ComInterfaces.sessionHandles
}

let make: unit => t
let connect: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
let disconnect: t => Promise.t<result<unit, Errors.t>>
let isConnected: t => Promise.t<result<bool, Errors.t>>
let getHandles: t => ComInterfaces.sessionHandles
