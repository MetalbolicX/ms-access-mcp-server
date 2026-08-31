// winaxBinding.mts — typed static-ESM bridge for winax COM operations.
// The module receives the injected winax namespace (CJS interop) and opaque
// COM object handles as parameters.  No winax types are referenced here.
import { unwrapCjsDefault } from "./cjsInterop.mjs";
/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Mirrors the ReScript %raw("m => m")(m) pattern but in typed TypeScript. */
export const unwrapModule = (mod) => unwrapCjsDefault(mod);

// ---------------------------------------------------------------------------
// COM-proxy envelope — defends against the winax proxy's hidden
// `BS_PRIVATE_NESTED_SOME_NONE` property, which causes ReScript's
// `Primitive_option.some(x)` to crash at runtime with
// "Cannot convert object to primitive value" when `x` is an ADODB/DAO
// proxy (the lookup returns a function, not undefined; the proxy's
// ToPrimitive algorithm rejects the function as non-primitive).
// Storing COM handles inside a plain-object envelope makes that lookup
// reliably return undefined, so `Some(envelope)` is safe. The real proxy
// is reachable via `envelope.__p__`; bridge functions transparently
// unwrap envelopes passed back in.
// ---------------------------------------------------------------------------
const _unwrap = (obj) => (obj != null && obj.__p__ !== undefined ? obj.__p__ : obj);
const _wrap = (proxy) => ({ __p__: proxy });

/** Create a COM object by progid string. Returns an envelope wrapping the proxy. */
export const createObject = (mod, progid) => _wrap(mod.Object(progid));

/** Read a property from a COM object — direct bracket access on the unwrapped proxy.
 *  Returns the raw value (string, number, COM envelope, primitive, etc.). */
export const getProperty = (mod, obj, prop) => _unwrap(obj)[prop];

/** Invoke a method on a COM object — direct call on the unwrapped proxy.
 *  Returns the raw method result; callers expecting a COM handle use
 *  `invokeReturningObject` instead, which always returns an envelope. */
export const invokeMethod = (mod, obj, method, args) => _unwrap(obj)[method](...args);

/** Write a property on a COM object via direct assignment on the unwrapped proxy. */
export const setProperty = (mod, obj, prop, value) => { _unwrap(obj)[prop] = value };

/** Release a COM object — unwraps envelope, then calls winax.free. */
export const release = (mod, obj) => {
  if (typeof mod.release === "function") mod.release(_unwrap(obj));
};

/** Invoke a method that returns a COM object handle — direct call on the
 *  unwrapped proxy, result is wrapped in an envelope before returning. */
export const invokeReturningObject = (mod, obj, method, args) =>
 _wrap(_unwrap(obj)[method](...args));