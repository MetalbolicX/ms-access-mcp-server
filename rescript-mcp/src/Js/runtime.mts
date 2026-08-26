// Shared runtime helpers that ReScript's type system cannot express
// without %raw. Keep every function pure and side-effect-free.

/** Zero-cost type cast for ReScript FFI bridging (generic identity at runtime). */
export const identity = <T extends unknown>(x: T): T => x

/** Unsafely widen a dict's value type at the ReScript FFI boundary.
 *  Runtime: returns input unchanged (zero cost).
 *  Type-level: dict<oDBcValue> → dict<unknown> so dictEntriesUnknown accepts it.
 *  Call site must be at the node-odbc FFI boundary only. */
export const dictCastToUnknown = <T,>(d: Record<string, T>): Record<string, unknown> =>
  d as Record<string, unknown>

import { writeFileSync as _fsWriteFileSync, unlinkSync as _fsUnlinkSync } from "node:fs"
import { tmpdir } from "node:os"

/** Extract a message from an unknown thrown value.
 *  Returns undefined when the value carries no usable message —
 *  callers map that to their own default ("Unknown error", "Unknown"). */
export const exnMessage = (e: unknown): string | undefined => {
  const anyE = e as { message?: unknown } | null | undefined
  return anyE && anyE.message ? String(anyE.message) : undefined
}

/** Check if running on Windows (process.platform === 'win32'). */
export const isWindows = (): boolean => process.platform === "win32"

/** Get the system temp directory path. */
export const getTempDir = (): string => tmpdir()

/** Get an environment variable value.
 *  Returns undefined when the key is not present. */
export const getEnv = (key: string): string | undefined => process.env[key]

/** Trim whitespace from both ends of a string.
 *  Python parity: str.strip() equivalent. */
export const trimString = (s: string): string => s.trim()

/** Write content to a file synchronously (helper for bridge tests). */
export const writeFileSync = (path: string, content: string): void => {
  _fsWriteFileSync(path, content, "utf8")
}

/** Delete a file synchronously (helper for bridge tests). */
export const deleteFile = (path: string): void => {
  try {
    _fsUnlinkSync(path)
  } catch {
    // ignore errors
  }
}
