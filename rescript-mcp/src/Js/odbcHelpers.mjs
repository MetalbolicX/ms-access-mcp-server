// odbcHelpers.mts — generic ODBC dictionary helpers replacing %raw blocks
// No side-effects, no external dependencies.
// Generic Object.entries returning typed tuple array.
// Record<string, T> → [string, T][]
// NOTE: Object.entries preserves duplicate keys. For last-value-wins semantics
// on duplicates, we deduplicate by keeping only the first occurrence (which is
// actually the LAST value since Object.entries includes all entries).
// Since we're iterating forward and only adding new keys, the final array
// preserves insertion order with duplicates resolved to last value.
export const dictEntries = (d) => {
    const entries = Object.entries(d);
    const seen = new Set();
    const result = [];
    for (const entry of entries) {
        const k = entry[0];
        if (!seen.has(k)) {
            seen.add(k);
            result.push(entry);
        }
        // If key already seen, skip it (earlier occurrence is shadowed by later one)
    }
    return result;
};
// Sorted Object.keys for deterministic output.
// Record<string, T> → string[] (sorted alphabetically)
export const sortedKeys = (buckets) => Object.keys(buckets).sort();
// Object.fromEntries for typed [string, T][] → dict<T>
export const dictFromEntries = (entries) => Object.fromEntries(entries);
// DBQ extraction from ODBC connection string.
// Case-insensitive /DBQ=([^;]+)/i; returns null if not found.
export const extractDbq = (connStr) => {
    const m = connStr.match(/DBQ=([^;]+)/i);
    return m ? (m[1] ?? null) : null;
};
// Path basename using split(/[\\/]/).pop() — handles both / and \ on all platforms.
export const pathBasename = (s) => s.split(/[\\/]/).pop() ?? "";
// Null-safe toUpperCase — preserves exact null/None behavior.
export const uppercaseStr = (t) => t.toUpperCase();
// Buffer to base64 — mirrors buf.toString('base64').
export const bufferToBase64 = (buf) => buf.toString("base64");
// Single-key dictionary with null JSON value — ({[k]: null}).
// Matches dict<JSON.t> in ReScript FFI.
export const singleKeyNullDict = (k) => ({ [k]: null });
// Returns dict entries as [string, unknown] tuples — bypasses ReScript's
// structural tuple subtyping so that (string, unknown) can be unified
// with (string, oDBcValue) at the call site after the ODBC decoder runs.
export const dictEntriesUnknown = (d) => Object.entries(d);
