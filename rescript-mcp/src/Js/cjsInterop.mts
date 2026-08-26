// cjsInterop.mts — neutral CJS default-module unwrapping.
// Shared by winaxBinding and odbcBinding to avoid duplicated logic.

/** Unwrap a CJS module namespace: prefer .default, fall back to identity.
 *  Uses unknown + safe structural narrowing — no any, no require. */
export const unwrapCjsDefault = (mod: unknown): unknown => {
  if (mod !== null && typeof mod === "object" && !Array.isArray(mod)) {
    const record = mod as Record<string, unknown>
    const d = record.default
    if (d !== undefined) {
      return d
    }
  }
  return mod
}
