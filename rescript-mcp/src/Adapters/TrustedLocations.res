// TrustedLocations.res — Trusted Locations capture/restore via PowerShell subprocess
// Mirrors src/ms_access_mcp/adapters/trusted_locations.py (Python winreg → PowerShell)
// Non-fatal: registry errors are caught and return false/empty without throwing.

type trustedLocation = ComInterfaces.trustedLocation

// ---------------------------------------------------------------------------
// Platform check
// ---------------------------------------------------------------------------

let isWindows: unit => bool = (
  () => Bindings.TsBridge.isWindows()
)

// ---------------------------------------------------------------------------
// _runPs — run PowerShell script via child_process.spawn, return stdout
// Non-fatal: returns empty string on error.
// ---------------------------------------------------------------------------

let _runPs: string => Promise.t<string> = (
  (script: string) => {
    let _cmd = "powershell"
    let _args = ["-NoProfile", "-NonInteractive", "-Command", script]
    Bindings.TsBridge.runPowerShell(_cmd, _args)
  }
)

// ---------------------------------------------------------------------------
// capture — reads HKLM and HKCU Trusted Locations via PowerShell
// Returns Ok(array<trustedLocation>) or Error on failure.
// On non-Windows returns Ok([]).
// ---------------------------------------------------------------------------

let capture: unit => Promise.t<result<array<trustedLocation>, Errors.t>> = (
  () => {
    if !isWindows() {
      Promise.resolve(Ok([]))
    } else {
      let script = "try { " ++
        "$ErrorActionPreference='SilentlyContinue'; " ++
        "$locs=@(); " ++
        "foreach($hive in @('HKLM:\\SOFTWARE\\Microsoft\\Office\\16.0\\Access\\Security\\Trusted Locations','HKCU:\\SOFTWARE\\Microsoft\\Office\\16.0\\Access\\Security\\Trusted Locations')) { " ++
        "$isUser=$hive -match 'HKCU'; " ++
        "Get-ChildItem $hive -EA SilentlyContinue | ForEach-Object { " ++
        "$p=($_ | Get-ItemProperty -Name Path -EA SilentlyContinue).Path; " ++
        "if($p) { $locs += @{path=$p;isUser=$isUser} } }; " ++
        "}; " ++
        "$locs | ConvertTo-Json -Compress " ++
        "} catch { '' }"
      _runPs(script)
        ->Promise.then((raw: string) => {
          if raw == "" || raw == "null" || raw == "[]" {
            Promise.resolve(Ok([]))
          } else {
             let parsed = JSON.parseOrThrow(raw)
            let locs: array<trustedLocation> = switch parsed {
            | JSON.Array(arr) => {
                let rec makeArray: (int, array<trustedLocation>) => array<trustedLocation> = (
                  (i, acc) => {
                    if i >= Array.length(arr) { acc }
                    else {
                      switch Array.get(arr, i) {
                      | Some(item) => {
                          switch item {
                          | JSON.Object(obj) => {
                              let path = switch Dict.get(obj, "path") {
                              | Some(JSON.String(s)) => s
                              | _ => ""
                              }
                              let isUser = switch Dict.get(obj, "isUser") {
                              | Some(JSON.Boolean(b)) => b
                              | _ => false
                              }
                              let loc: trustedLocation = {path: path, allowSubFolders: false, isUser: isUser}
                              makeArray(i + 1, Belt.Array.concat(acc, [loc]))
                            }
                          | _ => makeArray(i + 1, acc)
                          }
                        }
                      | None => makeArray(i + 1, acc)
                      }
                    }
                  }
                )
                makeArray(0, [])
              }
            | JSON.Object(obj) => {
                let path = switch Dict.get(obj, "path") {
                | Some(JSON.String(s)) => s
                | _ => ""
                }
                let isUser = switch Dict.get(obj, "isUser") {
                | Some(JSON.Boolean(b)) => b
                | _ => false
                }
                [{path: path, allowSubFolders: false, isUser: isUser}]
              }
            | _ => []
            }
            Promise.resolve(Ok(locs))
          }
        })
        ->Promise.catch((_e: exn) => {
          Promise.resolve(Ok([]))
        })
    }
  }
)

// ---------------------------------------------------------------------------
// restore — writes Trusted Locations to HKLM and HKCU via PowerShell
// Uses LocationN naming. Non-fatal: logs warnings but does not throw.
// Returns Ok(true) on full success, Ok(false) on partial/failure.
// ---------------------------------------------------------------------------

let restore: array<trustedLocation> => Promise.t<result<bool, Errors.t>> = (
  (locs: array<trustedLocation>) => {
    if !isWindows() {
      Promise.resolve(Ok(false))
    } else if Array.length(locs) == 0 {
      Promise.resolve(Ok(true))
    } else {
      let rec buildHiveScript: (array<trustedLocation>, int, string, bool) => string = (
        (locs, idx, acc, isUser) => {
          if idx >= Array.length(locs) { acc }
          else {
            switch Array.get(locs, idx) {
            | Some(loc) => {
                let name = "Location" ++ Int.toString(idx + 1)
                let hive = if isUser { "HKCU" } else { "HKLM" }
                let base = hive ++ ":\\SOFTWARE\\Microsoft\\Office\\16.0\\Access\\Security\\Trusted Locations"
                // Use double-quoted string for -Value to avoid single-quote escaping issues
                let entry = "try { New-Item -Path \"" ++ base ++ "\\" ++ name ++ "\" -Force -EA SilentlyContinue | Out-Null; Set-ItemProperty -Path \"" ++ base ++ "\\" ++ name ++ "\" -Name Path -Value \"" ++ loc.path ++ "\" -EA SilentlyContinue | Out-Null } catch { } "
                buildHiveScript(locs, idx + 1, acc ++ entry, isUser)
              }
            | None => buildHiveScript(locs, idx + 1, acc, isUser)
            }
          }
        }
      )
      let hklm = buildHiveScript(locs, 0, "", false)
      let hkcu = buildHiveScript(locs, 0, "", true)
      let script = "try { " ++ hklm ++ hkcu ++ " $true } catch { $false }"
      _runPs(script)
        ->Promise.then((raw: string) => {
          let ok = raw == "True" || raw == "true"
          Promise.resolve(Ok(ok))
        })
        ->Promise.catch((_e: exn) => {
          Logging.warnWithTag(~tag="TrustedLocations", "restore PowerShell failed")
          Promise.resolve(Ok(false))
        })
    }
  }
)
