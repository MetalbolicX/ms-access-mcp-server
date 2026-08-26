// ComInterfaces.res — dependency-free COM records and module types (implementation)
// Mirrors src/ms_access_mcp/adapters/interfaces.py (ISP protocols)

// ---------------------------------------------------------------------------
// Variant ADT — typed marshaling boundary for COM automation
// ---------------------------------------------------------------------------

type rec variant =
  | VBool(bool)
  | VDate(Date.t)
  | VNull
  | VEmpty
  | VInt(int)
  | VFloat(float)
  | VCurrency(float)
  | VDecimal(float)
  | VStr(string)
  | VArray(array<variant>)
  | VByRef(ref<variant>)

// ---------------------------------------------------------------------------
// COM object — opaque handle (set internally by Bindings.Winax)
// ---------------------------------------------------------------------------

type comObject = unit  // concrete — winax returns JS objects, wrapped as unit here

// ---------------------------------------------------------------------------
// Dispatch error record
// ---------------------------------------------------------------------------

type dispatchError = {
  message: string,
  description: option<string>,
  source: option<string>,
  errorCode: option<int>,
}

// ---------------------------------------------------------------------------
// Session state — owned handles (opaque refs held by ComSession)
// ---------------------------------------------------------------------------

type sessionHandles = {
  mutable accessApp: option<comObject>,
  mutable daoDb: option<comObject>,
  mutable adoConn: option<comObject>,
}

// ---------------------------------------------------------------------------
// Hang-stop result
// ---------------------------------------------------------------------------

type hangStopResult =
  | HungStopped
  | HungKillFailed(string)

// ---------------------------------------------------------------------------
// Trusted Locations — registry-backed (WScript.Shell, Office 16.0 HKLM/HKCU)
// ---------------------------------------------------------------------------

type trustedLocation = {
  path: string,
  allowSubFolders: bool,
  isUser: bool,  // true = HKCU, false = HKLM
}
