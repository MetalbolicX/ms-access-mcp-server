// normalize.ts — shared normalizer for the differential parity harness.
//
// Both the Python driver and the ReScript runner print JSON envelopes to
// stdout. They are not byte-identical: keys arrive in different orders,
// int-valued floats come through as "1.0" on one side and "1" on the
// other, Windows paths mix separators, timestamps come through with
// different precision, and the odbc package's error-wrapping drops the
// .message field on the ReScript side. The normalizer canonicalizes all
// of these so the differ can do a structural compare.
//
// Rules (per plan 007 amendments 2, 10):
//   - Sort object keys (deep).
//   - Numbers: int-valued floats canonicalize to integer form BEFORE
//     comparison (1.0 -> 1); float tolerance 1e-9 applies only to
//     non-int-valued floats.
//   - Windows path normalization: backslash vs forward slash, drive-letter
//     case.
//   - Float tolerance 1e-9 for non-int-valued floats.
//   - ISO timestamps.
//   - Drop volatile fields (recorded in case's volatileFields).
//
// Usage:
//   import { normalize } from "./normalize.js";
//   const a = normalize(pyOutput, volatileFields);
//   const b = normalize(rsOutput, volatileFields);
//   diff(a, b)  // -> null on match, or {path, expected, actual} on mismatch

const FLOAT_TOL = 1e-9;
const WIN_DRIVE_RE = /^([A-Za-z]):([/\\])/;

/**
 * Normalize a Windows path string. Both sides of the harness run on
 * Windows (driver + pyodbc + node-odbc); cross-platform CI is a clean
 * skip. The normalizer only canonicalizes separator direction and
 * drive-letter case so that PathGuard-validated paths compare equal even
 * if one side returned "D:\\foo\\bar" and the other "d:/foo/bar".
 */
function normalizeWindowsPath(p: string): string {
  if (typeof p !== "string") return p;
  const m = p.match(WIN_DRIVE_RE);
  if (!m) {
    // No drive letter — just normalize separator direction.
    return p.replace(/\//g, "\\");
  }
  return `${m[1]!.toUpperCase()}:\\${p.slice(3).replace(/[\\/]+/g, "\\")}`;
}

/**
 * Canonicalize a number. Int-valued floats become integers in the JSON
 * output. Non-int-valued floats are kept as-is for tolerance comparison
 * in the differ (not here — the differ compares them with FLOAT_TOL).
 */
function canonicalizeNumber(n: number): number {
  if (typeof n !== "number") return n;
  if (!Number.isFinite(n)) return n;
  if (Number.isInteger(n)) return n;
  // 1.0 -> 1, 0.0 -> 0; preserves precision for non-ints.
  if (Math.abs(n - Math.round(n)) < FLOAT_TOL) return Math.round(n);
  return n;
}

/**
 * Recursively normalize a JSON-shaped value.
 *  - Sort object keys (deep) so differ sees a stable order.
 *  - Canonicalize int-valued floats to integers.
 *  - Normalize Windows-path strings via normalizeWindowsPath.
 *  - Drop fields whose name appears in volatileFields (deep).
 */
export function normalize(value: unknown, volatileFields: string[] = []): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "number") return canonicalizeNumber(value);
  if (typeof value === "string") {
    // Heuristic: a string that contains a backslash or starts with a
    // Windows drive letter is treated as a path. We avoid pathifying
    // arbitrary strings (e.g. SQL error messages with colons).
    if (value.includes("\\") && WIN_DRIVE_RE.test(value)) {
      return normalizeWindowsPath(value);
    }
    return value;
  }
  if (typeof value === "boolean") return value;
  if (Array.isArray(value)) {
    return value.map((v) => normalize(v, volatileFields));
  }
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    const keys = Object.keys(value as Record<string, unknown>).sort();
    for (const k of keys) {
      if (volatileFields.includes(k)) continue;
      out[k] = normalize((value as Record<string, unknown>)[k], volatileFields);
    }
    return out;
  }
  return value;
}

/**
 * Deep-compare two normalized JSON values. Returns null on match, or
 * { path, expected, actual } on mismatch.
 */
export function diff(
  expected: unknown,
  actual: unknown,
  path = "$",
): { path: string; expected: unknown; actual: unknown } | null {
  if (expected === actual) return null;
  if (typeof expected === "number" && typeof actual === "number") {
    if (Number.isNaN(expected) && Number.isNaN(actual)) return null;
    if (Math.abs(expected - actual) < FLOAT_TOL) return null;
    return { path, expected, actual };
  }
  if (expected === null || actual === null) {
    return { path, expected, actual };
  }
  if (typeof expected !== typeof actual) {
    return { path, expected, actual };
  }
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual)) return { path, expected, actual };
    if (expected.length !== actual.length) {
      return { path, expected: `array length ${expected.length}`, actual: `array length ${actual.length}` };
    }
    for (let i = 0; i < expected.length; i++) {
      const r = diff(expected[i], actual[i], `${path}[${i}]`);
      if (r !== null) return r;
    }
    return null;
  }
  if (typeof expected === "object") {
    const ek = Object.keys(expected as Record<string, unknown>).sort();
    const ak = Object.keys(actual as Record<string, unknown>).sort();
    const ekSet = new Set(ek);
    const akSet = new Set(ak);
    const missingFromActual = ek.filter((k) => !akSet.has(k));
    const missingFromExpected = ak.filter((k) => !ekSet.has(k));
    if (missingFromActual.length > 0) {
      return { path, expected: missingFromActual, actual: "missing" };
    }
    if (missingFromExpected.length > 0) {
      return { path, expected: "missing", actual: missingFromExpected };
    }
    for (const k of ek) {
      const r = diff(
        (expected as Record<string, unknown>)[k],
        (actual as Record<string, unknown>)[k],
        `${path}.${k}`,
      );
      if (r !== null) return r;
    }
    return null;
  }
  return { path, expected, actual };
}
