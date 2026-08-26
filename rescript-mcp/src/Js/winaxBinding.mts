// winaxBinding.mts — typed static-ESM bridge for winax COM operations.
// The module receives the injected winax namespace (CJS interop) and opaque
// COM object handles as parameters.  No winax types are referenced here.

/** Minimal interface for the winax module shape we actually use.
 *  The injected `mod` is the CJS winax namespace (may have .default). */
export interface WinaxModule {
  Object: (progid: string) => unknown
  cast: (obj: unknown, prop: string) => unknown
  invoke: (obj: unknown, method: string, args: unknown[]) => unknown
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

/** Read a property from a COM object via winax.cast. */
export const getProperty = (
  mod: WinaxModule,
  obj: unknown,
  prop: string,
): unknown => mod.cast(obj, prop)

/** Invoke a method on a COM object with an array of arguments. */
export const invokeMethod = (
  mod: WinaxModule,
  obj: unknown,
  method: string,
  args: unknown[],
): unknown => mod.invoke(obj, method, args)
