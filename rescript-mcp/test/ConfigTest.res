// ConfigTest.res — tests for Config.readonly() and Config.allowedDirs()
// Oracle: config.py:119 for readonly parsing; config.py:100-106 for allowedDirs
// Tests use NodeJs.Process.env setter to verify call-time env reading

open Test

// ---------------------------------------------------------------------------
// Config.readonly: unit => bool — ACCESS_MCP_READONLY env parsing
// ---------------------------------------------------------------------------

// Oracle: config.py:119 — "true", "1", "yes" (lowercased) → true; everything else → false

test("Config.readonly: ACCESS_MCP_READONLY=1 returns true", () => {
  // Set env at call time via NodeJs.Process.process.env
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "1")
  let result = Config.readonly()
  // Reset to avoid polluting other tests
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, true)
})

test("Config.readonly: ACCESS_MCP_READONLY=true returns true (lowercase)", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "true")
  let result = Config.readonly()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, true)
})

test("Config.readonly: ACCESS_MCP_READONLY=TRUE returns true (uppercase)", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "TRUE")
  let result = Config.readonly()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, true)
})

test("Config.readonly: ACCESS_MCP_READONLY=yes returns true", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "yes")
  let result = Config.readonly()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, true)
})

test("Config.readonly: ACCESS_MCP_READONLY=yes returns true (YES)", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "YES")
  let result = Config.readonly()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, true)
})

test("Config.readonly: ACCESS_MCP_READONLY=0 returns false", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "0")
  let result = Config.readonly()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, false)
})

test("Config.readonly: ACCESS_MCP_READONLY=false returns false", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "false")
  let result = Config.readonly()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  assertion(~operator="equal", (a, b) => a == b, result, false)
})

test("Config.readonly: unset ACCESS_MCP_READONLY returns false", () => {
  // Ensure the env var is not set
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_READONLY", "")
  let result = Config.readonly()
  assertion(~operator="equal", (a, b) => a == b, result, false)
})

// ---------------------------------------------------------------------------
// Config.allowedDirs: unit => array<string> — semicolon-split + default home
// Oracle: config.py:100-106
// ---------------------------------------------------------------------------

test("Config.allowedDirs: ACCESS_MCP_ALLOWED_DIRS semicolon-split", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_ALLOWED_DIRS", "/a;/b;/c")
  let result = Config.allowedDirs()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_ALLOWED_DIRS", "")
  // Should parse to array of 3 dirs (order preserved)
  let expected = ["/a", "/b", "/c"]
  let lenMatch = Belt.Array.length(result) == Belt.Array.length(expected)
  // Check each index matches
  let i0 = Belt.Array.get(result, 0) == Belt.Array.get(expected, 0)
  let i1 = Belt.Array.get(result, 1) == Belt.Array.get(expected, 1)
  let i2 = Belt.Array.get(result, 2) == Belt.Array.get(expected, 2)
  assertion(~operator="equal", (a, b) => a == b, lenMatch && i0 && i1 && i2, true)
})

test("Config.allowedDirs: empty string defaults to [userHome]", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_ALLOWED_DIRS", "")
  let result = Config.allowedDirs()
  // Should default to user's home directory
  let home = NodeJs.Os.homedir()
  let matches = Belt.Array.length(result) == 1 && Belt.Array.get(result, 0) == Some(home)
  assertion(~operator="equal", (a, b) => a == b, matches, true)
})

test("Config.allowedDirs: trims whitespace from each dir", () => {
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_ALLOWED_DIRS", " /a ; /b ; ")
  let result = Config.allowedDirs()
  NodeJs.Process.process.env->Dict.set("ACCESS_MCP_ALLOWED_DIRS", "")
  // Should trim each entry — verify no leading/trailing whitespace
  // A trimmed string equals itself when whitespace is stripped from both ends
  let allTrimmed = Belt.Array.every(result, dir => {
    let trimmed = String.trim(dir)
    dir == trimmed
  })
  assertion(~operator="equal", (a, b) => a == b, allTrimmed, true)
})
