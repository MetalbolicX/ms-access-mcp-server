// hash.mts — SHA-256 file hashing using node:crypto ESM module.
// Replaces CJS require('crypto') in _fileHash (ComDbProps.res).

import { createHash } from "node:crypto"
import { readFileSync, existsSync } from "node:fs"

/** Compute SHA-256 hash of a file, returning hex string.
 *  Returns empty string on error (file not found, etc.).
 *  Mirrors: require('crypto').createHash('sha256').update(b).digest('hex') */
export const fileHash = (path: string): string => {
  try {
    if (!existsSync(path)) return ""
    const buf = readFileSync(path)
    return createHash("sha256").update(buf).digest("hex")
  } catch {
    return ""
  }
}
