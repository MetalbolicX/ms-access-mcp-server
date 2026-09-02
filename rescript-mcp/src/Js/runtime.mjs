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
 *  callers map that to their own default ("Unknown error", "Unknown").
 *  Walks common shapes: ReScript {RE_EXN_ID,_1} envelope, DAO COM errors
 *  ({description, number, code, hresult}), and primitive fallbacks.
 *  Primitives without a string coercion (boolean, number) yield undefined
 *  to preserve the "Failure" case where ReScript throws a bare variant
 *  with no .message property. */
export const exnMessage = (e) => {
    try {
        const inner = (e && typeof e === "object" && e._1 && typeof e._1 === "object") ? e._1 : e;
        if (inner && typeof inner === "object") {
            const parts = [];
            const push = (k, v) => { if (v !== undefined && v !== null && v !== "") { parts.push(k + "=" + (typeof v === "string" ? v : String(v))); } };
            push("message", inner.message);
            push("description", inner.description);
            push("number", inner.number);
            push("code", inner.code);
            push("hresult", inner.hresult);
            push("source", inner.source);
            if (parts.length > 0) {
                return parts.join(" | ");
            }
        }
        if (typeof inner === "string") {
            return inner.length > 0 ? inner : undefined;
        }
        return undefined;
    }
    catch (_err) {
        return undefined;
    }
};
/** Check if running on Windows (process.platform === 'win32'). */
export const isWindows = () => process.platform === "win32";
/** Check if winax package is available (can be required on Windows). */
import { createRequire } from "node:module";
const _require = createRequire(import.meta.url);
export const isWinaxAvailable = () => {
    try {
        _require("winax");
        return true;
    }
    catch {
        return false;
    }
};
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
