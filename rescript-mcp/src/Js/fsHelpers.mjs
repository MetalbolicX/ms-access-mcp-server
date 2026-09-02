// fsHelpers.mts — filesystem helper functions replacing %raw blocks.
// Mirrors the regex-based transformations in ComDbProps.res.
import { existsSync, copyFileSync as _fsCopyFileSync } from "node:fs";
/** Replace all forbidden filename characters with underscore.
 *  Replaces: \ / : * ? " < > |
 *  Mirrors: name.replace(/[\\/:*?"<>|]/g, '_') */
export const safeFilename = (name) => name.replace(/[\\/:*?"<>|]/g, "_");
/** Strip .bas/.txt suffix and replace first underscore with space.
 *  Used to convert Access export filenames like "01_My Form.bas" → "01_My Form".
 *  Mirrors: name.replace(/\.bas$/, '').replace(/\.txt$/, '').replace('_', ' ') */
export const cleanName = (name) => name.replace(/\.bas$/, "").replace(/\.txt$/, "").replace("_", " ");
/** Check if a file exists (synchronous). Used for pre-driver path validation. */
export const fileExists = (path) => existsSync(path);
/** Copy a file from source to destination synchronously. Throws on error. */
export const copyFileSync = (src, dest) => _fsCopyFileSync(src, dest);
