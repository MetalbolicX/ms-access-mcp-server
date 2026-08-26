// Shared runtime helpers that ReScript's type system cannot express
// without %raw. Keep every function pure and side-effect-free.
/** Zero-cost type cast for ReScript FFI bridging (generic identity at runtime). */
export const identity = (x) => x;
/** Unsafely widen a dict's value type at the ReScript FFI boundary.
 *  Runtime: returns input unchanged (zero cost).
 *  Type-level: dict<oDBcValue> → dict<unknown> so dictEntriesUnknown accepts it.
 *  Call site must be at the node-odbc FFI boundary only. */
export const dictCastToUnknown = (d) => d;
import { writeFileSync as _fsWriteFileSync, unlinkSync as _fsUnlinkSync } from "node:fs";
import { tmpdir } from "node:os";
/** Extract a message from an unknown thrown value.
 *  Returns undefined when the value carries no usable message —
 *  callers map that to their own default ("Unknown error", "Unknown"). */
export const exnMessage = (e) => {
    const anyE = e;
    return anyE && anyE.message ? String(anyE.message) : undefined;
};
/** Check if running on Windows (process.platform === 'win32'). */
export const isWindows = () => process.platform === "win32";
/** Get the system temp directory path. */
export const getTempDir = () => tmpdir();
/** Get an environment variable value.
 *  Returns undefined when the key is not present. */
export const getEnv = (key) => process.env[key];
/** Trim whitespace from both ends of a string.
 *  Python parity: str.strip() equivalent. */
export const trimString = (s) => s.trim();
/** Write content to a file synchronously (helper for bridge tests). */
export const writeFileSync = (path, content) => {
    _fsWriteFileSync(path, content, "utf8");
};
/** Delete a file synchronously (helper for bridge tests). */
export const deleteFile = (path) => {
    try {
        _fsUnlinkSync(path);
    }
    catch {
        // ignore errors
    }
};
