// Config.res — environment variable access for readonly mode and allowed directories
// Oracle: config.py:119 for readonly; config.py:100-106 for allowedDirs
// Uses rescript-nodejs (NodeJs.Process / NodeJs.Os) — NOT Bindings/*

// ---------------------------------------------------------------------------
// readonly: unit => bool
// ACCESS_MCP_READONLY: "true"|"1"|"yes" (case-insensitive) => true; else false
// Oracle: config.py:119
// ---------------------------------------------------------------------------

let readonly = (): bool => {
  switch Dict.get(NodeJs.Process.process.env, "ACCESS_MCP_READONLY") {
  | None => false
  | Some(v) => {
      let lower = String.toLowerCase(String.trim(v))
      lower == "true" || lower == "1" || lower == "yes"
    }
  }
}

// ---------------------------------------------------------------------------
// allowedDirs: unit => array<string>
// ACCESS_MCP_ALLOWED_DIRS: semicolon-separated; default [user home]
// Oracle: config.py:100-106
// ---------------------------------------------------------------------------

let _parseDirs = (raw: string): array<string> => {
  let parts = Js.String.split(";", raw)
  parts
    ->Belt.Array.map(s => String.trim(s))
    ->Belt.Array.keep(s => s !== "")
}

let allowedDirs = (): array<string> => {
  switch Dict.get(NodeJs.Process.process.env, "ACCESS_MCP_ALLOWED_DIRS") {
  | None | Some("") => [NodeJs.Os.homedir()]
  | Some(raw) => {
      let dirs = _parseDirs(raw)
      if Belt.Array.length(dirs) == 0 {
        [NodeJs.Os.homedir()]
      } else {
        dirs
      }
    }
  }
}
