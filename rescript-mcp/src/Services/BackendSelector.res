// BackendSelector.res — pure decision logic for adapter selection
// Takes ~comAvailable: bool injection (no module-load platform detection)
// Decision table via match-style explicit dispatch

// ---------------------------------------------------------------------------
// BackendCapabilities — Flag enum with 10 capability flags
// ---------------------------------------------------------------------------

type backendCapability =
  | CAN_READ_DATA
  | CAN_WRITE_DATA
  | CAN_INTROSPECT_SCHEMA
  | CAN_HANDLE_VBA
  | CAN_HANDLE_FORMS
  | CAN_HANDLE_REPORTS
  | CAN_HANDLE_MACROS
  | CAN_COMPACT
  | CAN_CREATE_LINKED_TABLE
  | CAN_IMPORT_EXPORT_TEXT

type capabilities = list<backendCapability>

// ---------------------------------------------------------------------------
// Backend types
// ---------------------------------------------------------------------------

type backend =
  | ODBC
  | COM
  | DAO
  | AUTO

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

let capabilityMismatchError = (msg: string): Errors.t => Errors.databaseError(msg)
let unavailableError = (msg: string): Errors.t => Errors.databaseError(msg)

// ---------------------------------------------------------------------------
// _isComOnlyCapability — check if capability requires COM backend
// ---------------------------------------------------------------------------

let _isComOnlyCapability = (cap: backendCapability): bool => {
  switch cap {
  | CAN_HANDLE_VBA => true
  | CAN_HANDLE_FORMS => true
  | CAN_HANDLE_REPORTS => true
  | CAN_HANDLE_MACROS => true
  | CAN_COMPACT => true
  | CAN_IMPORT_EXPORT_TEXT => true
  | _ => false
  }
}

let _requiresCom = (caps: option<capabilities>): bool => {
  switch caps {
  | None => false
  | Some(c) => Belt.List.some(c, _isComOnlyCapability)
  }
}

// ---------------------------------------------------------------------------
// _normalizeBackend — validate and normalize backend string
// ---------------------------------------------------------------------------

let _normalizeBackend = (value: string): result<backend, Errors.t> => {
  let normalized = Js.String.toLowerCase(Js.String.trim(value))
  switch normalized {
  | "odbc" => Ok(ODBC)
  | "com" => Ok(COM)
  | "dao" => Ok(DAO)
  | "auto" => Ok(AUTO)
  | _ => Error(capabilityMismatchError("Invalid backend value: " ++ value))
  }
}

// ---------------------------------------------------------------------------
// _resolveAuto — resolve AUTO backend based on capabilities and comAvailable
// ---------------------------------------------------------------------------

let _resolveAuto = (~caps: option<capabilities>, ~comAvailable: bool): backend => {
  if _requiresCom(caps) {
    COM
  } else if comAvailable {
    DAO  // DAO is preferred on Windows when available
  } else {
    ODBC
  }
}

// ---------------------------------------------------------------------------
// getAdapter — pure decision function returning which adapter to construct
// Returns backend type decision; caller constructs actual adapter
// ---------------------------------------------------------------------------

let getAdapter = (
  ~dbPath: string,
  ~backend: option<string>=?,
  ~capabilities: option<capabilities>=?,
  ~comAvailable: bool,
): result<backend, Errors.t> => {
  let _ = dbPath // Reserved for future path-based routing hints
  // Resolve explicit backend arg or default to AUTO
  let normalizedBackend: result<backend, Errors.t> = switch backend {
  | Some(b) => _normalizeBackend(b)
  | None => Ok(AUTO)
  }

  switch normalizedBackend {
  | Error(e) => Error(e)
  | Ok(ODBC) =>
    // Validate ODBC doesn't conflict with COM-only capabilities
    if _requiresCom(capabilities) {
      Error(capabilityMismatchError("ODBC backend conflicts with COM-only capability"))
    } else {
      Ok(ODBC)
    }
  | Ok(AUTO) => Ok(_resolveAuto(~caps=capabilities, ~comAvailable))
  | Ok(bk) => Ok(bk)
  }
}
