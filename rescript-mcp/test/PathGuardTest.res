// PathGuardTest.res — tests for PathGuard.validatePath()
// Oracle: path_guard.py:5-16 (9 guarded arg names), path_guard.py:31-52 (validation logic)

open Test
open Errors

// ---------------------------------------------------------------------------
// PathGuard.validatePath: (~argName, ~value) => result<string, Errors.t>
// Whitelist: exactly 9 names from path_guard.py:5-16
// file_path, output_path, output_dir, input_dir, backup_path, backup_dir,
// script_path, source, dest
// ---------------------------------------------------------------------------

// Use an absolute path inside an allowed dir as test fixture
// On CI/dev: /tmp is world-readable; we use NodeJs.Os.homedir() as fallback allowed dir
let _testAllowedDir = (): string => {
  let home = NodeJs.Os.homedir()
  if home !== "" && home !== "/" {
    home
  } else {
    "/tmp"
  }
}

let _testAllowedPath = (): string => {
  let dir = _testAllowedDir()
  NodeJs.Path.join2(dir, "test-file.csv")
}

// ---------------------------------------------------------------------------
// Tests: argName must be in the 9-name whitelist
// path_guard.py:5-16
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: file_path is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="file_path", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: output_path is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="output_path", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: output_dir is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="output_dir", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: input_dir is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="input_dir", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: backup_path is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="backup_path", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: backup_dir is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="backup_dir", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: script_path is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="script_path", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: source is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="source", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: dest is a valid arg name", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="dest", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: unknown arg names are rejected
// path_guard.py:79-83 error message format
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: unknown arg name returns Error(ValidationError)", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="unknown_arg", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Error(e) => {
      let d = Errors.toDict(e)
      let isValidation = d.error == "ValidationError"
      let hasName = String.includes(d.message, "unknown_arg")
      assertion(~operator="equal", (a, b) => a == b, isValidation && hasName, true)
    }
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: UNC paths are rejected
// path_guard.py:33-34 and path_guard.py:80-83
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: UNC path with \\\\ prefix is rejected", () => {
  let allowed = ["C:\\"]
  let result = PathGuard.validatePath(~argName="file_path", ~value="\\\\server\\share\\foo.csv", ~allowedDirs=allowed)
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: UNC path with // prefix is rejected", () => {
  let allowed = ["C:\\"]
  let result = PathGuard.validatePath(~argName="file_path", ~value="//server/share/foo.csv", ~allowedDirs=allowed)
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: Path traversal is rejected
// path_guard.py:37-42
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: traversal with /../ is rejected", () => {
  let allowed = [_testAllowedDir()]
  // /tmp/../../../etc/passwd — traversal out of allowed dir
  let result = PathGuard.validatePath(~argName="file_path", ~value="/allowed/../../../etc/passwd", ~allowedDirs=allowed)
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("PathGuard.validatePath: traversal with \\..\\ is rejected", () => {
  let allowed = ["C:\\allowed"]
  let result = PathGuard.validatePath(~argName="file_path", ~value="C:\\allowed\\..\\..\\etc\\passwd", ~allowedDirs=allowed)
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: Path outside allowed dirs is rejected
// path_guard.py:37-43 and path_guard.py:47-52
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: path outside allowed dirs returns Error(PathGuardError)", () => {
  let allowed = ["/allowed"]
  let result = PathGuard.validatePath(~argName="file_path", ~value="/notallowed/foo.csv", ~allowedDirs=allowed)
  switch result {
  | Error(e) => {
      let d = Errors.toDict(e)
      let isPathGuard = d.error == "PathGuardError"
      let hasPath = String.includes(d.message, "/notallowed/foo.csv")
      assertion(~operator="equal", (a, b) => a == b, isPathGuard && hasPath, true)
    }
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: Happy path — valid path inside allowed dirs returns Ok(resolved path)
// path_guard.py:37-43
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: valid path inside allowed dirs returns Ok with resolved path", () => {
  let allowed = [_testAllowedDir()]
  let result = PathGuard.validatePath(~argName="file_path", ~value=_testAllowedPath(), ~allowedDirs=allowed)
  switch result {
  | Ok(resolved) => {
      // Resolved path should be absolute
      let isAbs = NodeJs.Path.isAbsolute(resolved)
      assertion(~operator="equal", (a, b) => a == b, isAbs, true)
    }
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: Returns Error with exact message format from path_guard.py:80-83
// "argName: path not allowed: value. Allowed directories: [...]"
// ---------------------------------------------------------------------------

test("PathGuard.validatePath: error message format for outside allowed dirs", () => {
  let allowed = ["/allowed"]
  let result = PathGuard.validatePath(~argName="file_path", ~value="/outside/foo.csv", ~allowedDirs=allowed)
  switch result {
  | Error(e) => {
      let d = Errors.toDict(e)
      // Check message format: "file_path: path not allowed: /outside/foo.csv. Allowed directories: [...]"
      let hasArgName = String.includes(d.message, "file_path")
      let hasPath = String.includes(d.message, "/outside/foo.csv")
      let hasAllowed = String.includes(d.message, "Allowed directories")
      assertion(~operator="equal", (a, b) => a == b, hasArgName && hasPath && hasAllowed, true)
    }
  | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})
