// winaxBinding.mts — typed static-ESM bridge for winax COM operations.
// The module receives the injected winax namespace (CJS interop) and opaque
// COM object handles as parameters.  No winax types are referenced here.
import { unwrapCjsDefault } from "./cjsInterop.mjs";
/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Mirrors the ReScript %raw("m => m")(m) pattern but in typed TypeScript. */
export const unwrapModule = (mod) => unwrapCjsDefault(mod);
/** Create a COM object by progid string. */
export const createObject = (mod, progid) => mod.Object(progid);
/** Read a property from a COM object via winax.cast. */
export const getProperty = (mod, obj, prop) => mod.cast(obj, prop);
/** Invoke a method on a COM object with an array of arguments. */
export const invokeMethod = (mod, obj, method, args) => mod.invoke(obj, method, args);
