// Winax.resi — sole winax importer: WINAX_BINDING module type
// winax is imported ONLY here; all other modules get the binding injected

// Preserved COM error record — plan 039. Mirrors the file-level declaration
// in Winax.res so external modules can reference the type without reaching
// into the WINAX_BINDING module.
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
  let releaseSyncAwait: ComInterfaces.comObject => Promise.t<unit>

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

// Expose the binding implementation as a sub-module for injection
module WINAX_BINDING: WINAX_BINDING
