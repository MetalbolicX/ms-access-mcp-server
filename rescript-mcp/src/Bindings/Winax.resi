// Winax.resi — sole winax importer: WINAX_BINDING module type
// winax is imported ONLY here; all other modules get the binding injected

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

// Expose the binding implementation as a sub-module for injection
module WINAX_BINDING: WINAX_BINDING
