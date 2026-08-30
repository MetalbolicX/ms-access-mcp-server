open Test
open Adapters
open Adapters.ComInterfaces

// Plan 028: binding primitives smoke tests
// Verifies that the WINAX_BINDING module exposes the new `invokeAsObject`
// member and that the existing set/release/getCount/getItem members retain
// their signatures.
//
// These tests do NOT actually invoke the bindings — that requires a live
// Windows + winax environment. They verify the type signatures and module
// shape so that any future binding signature change is caught here.

// ---------------------------------------------------------------------------
// WINAX_BINDING module type includes invokeAsObject (added in plan 028)
// ---------------------------------------------------------------------------

test("WINAX_BINDING module exposes invokeAsObject as a function", () => {
  // Structural assertion: invokeAsObject exists on the module value and has
  // the expected signature. If invokeAsObject is missing or has the wrong
  // signature, this won't compile.
  let f: (
    ComInterfaces.comObject,
    string,
    array<ComInterfaces.variant>,
  ) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = Bindings.Winax.WINAX_BINDING.invokeAsObject
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

// ---------------------------------------------------------------------------
// Each binding primitive has the documented signature
// We take a reference to each function and bind it to a typed let, which
// forces ReScript to verify the signature without actually invoking.
// ---------------------------------------------------------------------------

test("createObject has signature string => Promise<result<comObject, Errors.t>>", () => {
  let f: string => Promise.t<result<ComInterfaces.comObject, Errors.t>> = Bindings.Winax.WINAX_BINDING.createObject
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("release has signature comObject => unit", () => {
  let f: ComInterfaces.comObject => unit = Bindings.Winax.WINAX_BINDING.release
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("get has signature (comObject, string) => Promise<result<JSON.t, Errors.t>>", () => {
  let f: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>> = Bindings.Winax.WINAX_BINDING.get
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("set has signature (comObject, string, variant) => Promise<result<unit, Errors.t>>", () => {
  let f: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>> = Bindings.Winax.WINAX_BINDING.set
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("invoke has signature (comObject, string, array<variant>) => Promise<result<JSON.t, Errors.t>>", () => {
  let f: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>> = Bindings.Winax.WINAX_BINDING.invoke
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("getCount has signature comObject => Promise<result<int, Errors.t>>", () => {
  let f: ComInterfaces.comObject => Promise.t<result<int, Errors.t>> = Bindings.Winax.WINAX_BINDING.getCount
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("getItem has signature (comObject, variant) => Promise<result<comObject, Errors.t>>", () => {
  let f: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = Bindings.Winax.WINAX_BINDING.getItem
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("toVariant has signature variant => Promise<result<JSON.t, Errors.t>>", () => {
  let f: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>> = Bindings.Winax.WINAX_BINDING.toVariant
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})

test("fromVariant has signature JSON.t => Promise<result<variant, Errors.t>>", () => {
  let f: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>> = Bindings.Winax.WINAX_BINDING.fromVariant
  assertion(~operator="equal", (a, b) => a == b, true, true)
  ignore(f)
})
