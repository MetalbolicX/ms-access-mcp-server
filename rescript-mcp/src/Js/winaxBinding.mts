// winaxBinding.mts — typed static-ESM bridge for winax COM operations.
// The module receives the injected winax namespace (CJS interop) and opaque
// COM object handles as parameters.  No winax types are referenced here.

/** Minimal interface for the winax module shape we actually use.
 *  The injected `mod` is the CJS winax namespace (may have .default). */
export interface WinaxModule {
  Object: (progid: string) => unknown
  release: (...objects: unknown[]) => void
}

import { unwrapCjsDefault } from "./cjsInterop.mjs"

/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Mirrors the ReScript %raw("m => m")(m) pattern but in typed TypeScript. */
export const unwrapModule = (mod: Record<string, unknown>): unknown =>
  unwrapCjsDefault(mod)

// ---------------------------------------------------------------------------
// COM-proxy envelope — see winaxBinding.mjs for rationale.
// ---------------------------------------------------------------------------
type ComEnvelope = { __p__: unknown }
const _unwrap = (obj: unknown): unknown => {
  if (obj != null && typeof obj === "object" && "__p__" in (obj as ComEnvelope)) {
    return (obj as ComEnvelope).__p__
  }
  return obj
}
const _wrap = (proxy: unknown): ComEnvelope => ({ __p__: proxy })

/** Create a COM object by progid string. Returns an envelope wrapping the proxy. */
export const createObject = (
  mod: WinaxModule,
  progid: string,
): unknown => _wrap(mod.Object(progid))

/** Read a property from a COM object — direct bracket access on the unwrapped proxy. */
export const getProperty = (
  mod: WinaxModule,
  obj: unknown,
  prop: string,
): unknown => (_unwrap(obj) as Record<string, unknown>)[prop]

/** Invoke a method on a COM object — direct call on the unwrapped proxy. */
export const invokeMethod = (
  mod: WinaxModule,
  obj: unknown,
  method: string,
  args: unknown[],
): unknown => (_unwrap(obj) as Record<string, (...a: unknown[]) => unknown>)[method](...args)

/** Write a property on a COM object via direct assignment on the unwrapped proxy. */
export const setProperty = (
  mod: WinaxModule,
  obj: unknown,
  prop: string,
  value: unknown,
): void => {
  (_unwrap(obj) as Record<string, unknown>)[prop] = value
}

/** Release a COM object — unwraps envelope, then calls winax.release. */
export const release = (
  mod: WinaxModule,
  obj: unknown,
): void => {
  if (typeof mod.release === "function") {
    mod.release(_unwrap(obj))
  }
}

/** Invoke a method that returns a COM object — direct call on the unwrapped
 *  proxy, then wrap the returned proxy in an envelope. */
export const invokeReturningObject = (
  mod: WinaxModule,
  obj: unknown,
  method: string,
  args: unknown[],
): unknown => _wrap((_unwrap(obj) as Record<string, (...a: unknown[]) => unknown>)[method](...args))