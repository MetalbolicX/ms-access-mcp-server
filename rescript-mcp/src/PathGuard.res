// PathGuard.res — path validation against allowed directories whitelist
// Oracle: path_guard.py:5-16 (9 guarded arg names), path_guard.py:31-52 (validation logic)
// Uses rescript-nodejs (NodeJs.Path) — NOT Bindings/*

// ---------------------------------------------------------------------------
// PATH_ARG_NAMES — exactly 9 names from path_guard.py:5-16
// ---------------------------------------------------------------------------

let pathArgNames: array<string> = [
  "file_path",
  "output_path",
  "output_dir",
  "input_dir",
  "backup_path",
  "backup_dir",
  "script_path",
  "source",
  "dest",
]

// ---------------------------------------------------------------------------
// _isKnownPathArg: string => bool
// ---------------------------------------------------------------------------

let _isKnownPathArg = (argName: string): bool => {
  Belt.Array.getBy(pathArgNames, n => n == argName) != None
}

// ---------------------------------------------------------------------------
// _isUncPath: string => bool
// Rejects paths starting with \\ or // (UNC notation)
// Oracle: path_guard.py:33-34
// ---------------------------------------------------------------------------

let _isUncPath = (path: string): bool => {
  String.startsWith(path, "\\\\") || String.startsWith(path, "//")
}

// ---------------------------------------------------------------------------
// _hasTraversal: string => bool
// Checks for .. path traversal segments (separated by / or \)
// Oracle: path_guard.py:37-42
// ---------------------------------------------------------------------------

let _hasTraversal = (path: string): bool => {
  let segments = Js.String.split("/", path)->Belt.Array.concat(
    Js.String.split("\\", path)
  )
  Belt.Array.some(segments, s => s == "..")
}

// ---------------------------------------------------------------------------
// _isInsideAllowedDir: (path: string, allowedDirs: array<string>) => bool
// Oracle: path_guard.py:36-43
// ---------------------------------------------------------------------------

let _isInsideAllowedDir = (path: string, allowedDirs: array<string>): bool => {
  let resolved = NodeJs.Path.resolve([path])
  Belt.Array.some(allowedDirs, allowed => {
    String.startsWith(resolved, allowed)
  })
}

// ---------------------------------------------------------------------------
// validatePath: (~argName: string, ~value: string, ~allowedDirs: array<string>) => result<string, Errors.t>
// Returns Ok(resolvedAbsolutePath) on success, Err(...) on rejection
// Oracle: path_guard.py:45-52 message format
// ---------------------------------------------------------------------------

let validatePath = (
  ~argName: string,
  ~value: string,
  ~allowedDirs: array<string>,
): result<string, Errors.t> => {
  // Step 1: argName must be in whitelist
  if !_isKnownPathArg(argName) {
    Error(Errors.validationError("Unknown path arg name '" ++ argName ++ "'"))
  }
  // Step 2: UNC path rejection
  else if _isUncPath(value) {
    Error(Errors.pathGuardError("UNC paths not allowed"))
  }
  // Step 3: Traversal rejection
  else if _hasTraversal(value) {
    Error(Errors.pathGuardError("Path traversal not allowed"))
  }
  // Step 4: Allowed-dir check
  else if !_isInsideAllowedDir(value, allowedDirs) {
    let msg = argName ++ ": path not allowed: " ++ value ++ ". Allowed directories: [" ++ Belt.Array.joinWith(allowedDirs, ",", s => s) ++ "]"
    Error(Errors.pathGuardError(msg))
  }
  // Step 5: Return resolved absolute path on success
  else {
    Ok(NodeJs.Path.resolve([value]))
  }
}
