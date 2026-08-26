// ComInterfaces.resi — dependency-free COM records and module types
// Foundation for plan-004 COM adapter; this module must NOT import winax
// Module types (SESSION, WINAX_BINDING, TRUSTED_LOCATIONS_PROVIDER) live in their own files

// ---------------------------------------------------------------------------
// Variant ADT — typed marshaling boundary for COM automation
// Mirrors python-win32 Variant semantics; excludes raw exn escape
// ---------------------------------------------------------------------------

type rec variant =
  | VBool(bool)
  | VDate(Date.t)
  | VNull
  | VEmpty
  | VInt(int)
  | VFloat(float)
  | VCurrency(float)  // OLE/Currency — 64-bit scaled integer
  | VDecimal(float)  // OLE Decimal
  | VStr(string)
  | VArray(array<variant>)
  | VByRef(ref<variant>)

// ---------------------------------------------------------------------------
// COM object — opaque handle from winax.Object constructor
// ---------------------------------------------------------------------------

type comObject = unit  // concrete — actual handle from winax wrapped here

// ---------------------------------------------------------------------------
// Dispatch error record — folded into Errors.DatabaseError
// ---------------------------------------------------------------------------

type dispatchError = {
  message: string,
  description: option<string>,
  source: option<string>,
  errorCode: option<int>,
}

// ---------------------------------------------------------------------------
// Session state — owned handles
// ---------------------------------------------------------------------------

type sessionHandles = {
  mutable accessApp: option<comObject>,
  mutable daoDb: option<comObject>,
  mutable adoConn: option<comObject>,
}

// ---------------------------------------------------------------------------
// Hang-stop result — mirrors com_dispatcher.py watchdog behaviour
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
