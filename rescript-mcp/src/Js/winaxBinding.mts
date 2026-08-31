// winaxBinding.mts — typed static-ESM bridge for winax COM operations.
// The module receives the injected winax namespace (CJS interop) and opaque
// COM object handles as parameters.  No winax types are referenced here.

/** Minimal interface for the winax module shape we actually use.
 *  winax.cast is variant type-conversion (not property access); winax.invoke does not exist.
 *  Property/method access on COM proxies is direct bracket/dot access. */
export interface WinaxModule {
  Object: (progid: string) => unknown
  release: (...objects: unknown[]) => void
}

import { unwrapCjsDefault } from "./cjsInterop.mjs"

/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Mirrors the ReScript %raw("m => m")(m) pattern but in typed TypeScript. */
export const unwrapModule = (mod: Record<string, unknown>): unknown =>
  unwrapCjsDefault(mod)

/** Create a COM object by progid string. */
export const createObject = (
  mod: WinaxModule,
  progid: string,
): unknown => mod.Object(progid)

/** Read a property from a COM object — direct bracket access on winax proxy; winax.cast is variant type-conversion, not property access. */
export const getProperty = (
  mod: WinaxModule,
  obj: unknown,
  prop: string,
): unknown => (obj as Record<string, unknown>)[prop]

/** Invoke a method on a COM object — direct call on the winax proxy. */
export const invokeMethod = (
  mod: WinaxModule,
  obj: unknown,
  method: string,
  args: unknown[],
): unknown => (obj as Record<string, unknown>)[method](...args)

/** Write a property on a COM object via direct assignment on the proxy. */
export const setProperty = (
  mod: WinaxModule,
  obj: unknown,
  prop: string,
  value: unknown,
): void => {
  // winax COM proxies support direct property assignment on the JS wrapper.
  (obj as Record<string, unknown>)[prop] = value
}

/** Release one or more COM objects via winax.free function. */
export const release = (
  mod: WinaxModule,
  obj: unknown,
): void => {
  if (typeof mod.release === "function") {
    mod.release(obj)
  }
}

/** Invoke a method that returns a COM object — direct call on the winax proxy (same body as invokeMethod; return contract differs). */
export const invokeReturningObject = (
  mod: WinaxModule,
  obj: unknown,
  method: string,
  args: unknown[],
): unknown => (obj as Record<string, unknown>)[method](...args)
