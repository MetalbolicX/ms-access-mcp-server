// ComSession.resi — session lifecycle: SESSION module type
// Adapters.ComSession implements this module type

module type SESSION = {
  type t

  let connect: (t, ~path: string) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let getHandles: t => ComInterfaces.sessionHandles
}
