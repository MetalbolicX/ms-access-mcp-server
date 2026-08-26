// odbcBinding.mts — typed static-ESM bridge for odbc module unwrapping.
// Reuses the same CJS interop pattern as winaxBinding: prefer .default,
// fall back to identity.  Kept in a separate file to allow independent
// import paths from ReScript (TsBridge.res / JsOdbc.res externals).

import { unwrapCjsDefault } from "./cjsInterop.mjs"

/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Mirrors the ReScript %raw("m => m")(m) pattern but in typed TypeScript.
 *  Accepts any type since we bridge from ReScript's dict<odbcModule>. */
export const unwrapOdbcModule = (mod: unknown): unknown => unwrapCjsDefault(mod)
