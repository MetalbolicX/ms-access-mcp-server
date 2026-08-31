// winaxBinding.mts — typed static-ESM bridge for winax COM operations.
// The module receives the injected winax namespace (CJS interop) and opaque
// COM object handles as parameters.  No winax types are referenced here.
import { unwrapCjsDefault } from "./cjsInterop.mjs";
/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Mirrors the ReScript %raw("m => m")(m) pattern but in typed TypeScript. */
export const unwrapModule = (mod) => unwrapCjsDefault(mod);
/** Create a COM object by progid string. */
export const createObject = (mod, progid) => mod.Object(progid);
/** Read a property from a COM object — direct bracket access on winax proxy; winax.cast is variant type-conversion, not property access. */
export const getProperty = (mod, obj, prop) => obj[prop];
/** Invoke a method on a COM object — direct call on the winax proxy. */
export const invokeMethod = (mod, obj, method, args) => obj[method](...args);
/** Write a property on a COM object via direct assignment on the proxy. */
export const setProperty = (mod, obj, prop, value) => { (obj)[prop] = value };
/** Release one or more COM objects via winax.free function. */
export const release = (mod, obj) => { if (typeof mod.release === "function") mod.release(obj) };
/** Invoke a method that returns a COM object — direct call on the winax proxy (same body as invokeMethod; return contract differs). */
export const invokeReturningObject = (mod, obj, method, args) => obj[method](...args);
