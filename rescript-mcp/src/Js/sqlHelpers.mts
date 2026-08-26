// sqlHelpers.mts — pure SQL helpers replacing %raw blocks in SqlBuilder.res
// No side-effects, no external dependencies.

// Global replace of ] → ]] for Access/Jet bracket escaping.
// Mirrors: name.replace(/]/g, "]]")
export const bracketEscape = (name: string): string =>
  name.replace(/]/g, "]]")

// Pre-compiled regex: -- (SQL single-line comment start)
export const regexDashDash = (): RegExp => new RegExp("--")

// Pre-compiled regex: /* (SQL multi-line comment start)
// Escaped for JS string: \\/\\* becomes \/\* in the RegExp
export const regexSlashStar = (): RegExp => new RegExp("\\/\\*")

// Pre-compiled regex: */ (SQL multi-line comment end)
// Escaped for JS string: \\*\\/ becomes \*\/ in the RegExp
export const regexStarSlash = (): RegExp => new RegExp("\\*\\/")

// Pre-compiled regex for raw WHERE validation.
export const rawWhitelist = (): RegExp => /^[\w\s.,=<>()'"%-]+$/

// Test string against precompiled regex.
// Mirrors: r.test(s)
export const regexTest = (str: string, re: RegExp): boolean => re.test(str)

// Null-safe lowercase: (s ?? '').toLowerCase()
export const nullSafeLowercase = (s: string | null | undefined): string =>
  (s ?? "").toLowerCase()
