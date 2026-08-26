// TsBridge.res — typed externals for strict TypeScript modules in src/Js.
// With in-source ESM output, this path resolves to src/Js/runtime.mjs.
@module("../Js/runtime.mjs")
external exnMessage: exn => option<string> = "exnMessage"

@module("../Js/runtime.mjs")
external isWindows: unit => bool = "isWindows"

@module("../Js/runtime.mjs")
external getTempDir: unit => string = "getTempDir"

@module("../Js/runtime.mjs")
external writeFileSync: (string, string) => unit = "writeFileSync"

@module("../Js/runtime.mjs")
external deleteFile: string => unit = "deleteFile"

@module("../Js/runtime.mjs")
external getEnv: string => option<string> = "getEnv"

// ---------------------------------------------------------------------------
// identity — zero-cost type cast for FFI bridging
// ---------------------------------------------------------------------------

@module("../Js/runtime.mjs")
external identity: 'a => 'a = "identity"

@module("../Js/runtime.mjs")
external trimString: string => string = "trimString"

// ---------------------------------------------------------------------------
// codec.mts — cp1252 / UTF-16LE encoding helpers
// ---------------------------------------------------------------------------

@module("../Js/codec.mjs")
external encodeCp1252: string => array<int> = "encodeCp1252"

@module("../Js/codec.mjs")
external bufferToBytes: NodeJs.Buffer.t => array<int> = "bufferToBytes"

@module("../Js/codec.mjs")
external decodeCp1252: array<int> => string = "decodeCp1252"

@module("../Js/codec.mjs")
external decodeUtf16LeSkipBom: array<int> => string = "decodeUtf16LeSkipBom"

@module("../Js/codec.mjs")
external encodeToBuffer: (string, string) => NodeJs.Buffer.t = "encodeToBuffer"

@module("../Js/codec.mjs")
external bytesFromString: (string, string) => array<int> = "bytesFromString"

@module("../Js/codec.mjs")
external bytesToString: (array<int>, string) => string = "bytesToString"

// ---------------------------------------------------------------------------
// fsHelpers.mts — filename sanitization helpers
// ---------------------------------------------------------------------------

@module("../Js/fsHelpers.mjs")
external safeFilename: string => string = "safeFilename"

@module("../Js/fsHelpers.mjs")
external cleanName: string => string = "cleanName"

@module("../Js/fsHelpers.mjs")
external fileExists: string => bool = "fileExists"

// ---------------------------------------------------------------------------
// hash.mts — file hashing helpers
// ---------------------------------------------------------------------------

@module("../Js/hash.mjs")
external fileHash: string => string = "fileHash"

// ---------------------------------------------------------------------------
// winaxBinding.mts — typed winax COM binding helpers
// ---------------------------------------------------------------------------

@module("../Js/winaxBinding.mjs")
external unwrapWinaxModule: dict<JSON.t> => JSON.t = "unwrapModule"

@module("../Js/winaxBinding.mjs")
external winaxCreateObject: (JSON.t, string) => ComInterfaces.comObject = "createObject"

@module("../Js/winaxBinding.mjs")
external winaxGetProperty: (JSON.t, 'a, string) => JSON.t = "getProperty"

@module("../Js/winaxBinding.mjs")
external winaxInvokeMethod: (JSON.t, 'a, string, array<JSON.t>) => JSON.t = "invokeMethod"

// ---------------------------------------------------------------------------
// odbcBinding.mts — typed odbc module unwrap helper
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// sqlHelpers.mts — SQL helpers replacing %raw blocks in SqlBuilder.res
// ---------------------------------------------------------------------------

@module("../Js/sqlHelpers.mjs")
external bracketEscape: string => string = "bracketEscape"

@module("../Js/sqlHelpers.mjs")
external regexDashDash: unit => RegExp.t = "regexDashDash"

@module("../Js/sqlHelpers.mjs")
external regexSlashStar: unit => RegExp.t = "regexSlashStar"

@module("../Js/sqlHelpers.mjs")
external regexStarSlash: unit => RegExp.t = "regexStarSlash"

@module("../Js/sqlHelpers.mjs")
external rawWhitelist: unit => RegExp.t = "rawWhitelist"

@module("../Js/sqlHelpers.mjs")
external regexTest: (string, RegExp.t) => bool = "regexTest"

@module("../Js/sqlHelpers.mjs")
external nullSafeLowercase: string => string = "nullSafeLowercase"

// ---------------------------------------------------------------------------
// trustedLocations.mts — child_process.spawn bridge for TrustedLocations.res
// ---------------------------------------------------------------------------

@module("../Js/trustedLocations.mjs")
external runPowerShell: (string, array<string>) => Promise.t<string> = "runPowerShell"

// ---------------------------------------------------------------------------
// odbcHelpers.mts — generic ODBC dict helpers replacing %raw in OdbcSchemaReader
// ---------------------------------------------------------------------------

@module("../Js/odbcHelpers.mjs")
external dictEntries: dict<'a> => array<(string, 'a)> = "dictEntries"

@module("../Js/odbcHelpers.mjs")
external dictEntriesUnknown: dict<unknown> => array<(string, unknown)> = "dictEntriesUnknown"

@module("../Js/runtime.mjs")
external dictCastToUnknown: dict<'a> => dict<unknown> = "dictCastToUnknown"

@module("../Js/odbcHelpers.mjs")
external sortedKeys: dict<'a> => array<string> = "sortedKeys"

@module("../Js/odbcHelpers.mjs")
external dictFromEntries: array<(string, 'a)> => dict<'a> = "dictFromEntries"

@module("../Js/odbcHelpers.mjs")
external extractDbq: string => option<string> = "extractDbq"

@module("../Js/odbcHelpers.mjs")
external pathBasename: string => string = "pathBasename"

@module("../Js/odbcHelpers.mjs")
external uppercaseStr: string => string = "uppercaseStr"

@module("../Js/odbcHelpers.mjs")
external bufferToBase64: NodeJs.Buffer.t => string = "bufferToBase64"

@module("../Js/odbcHelpers.mjs")
external singleKeyNullDict: string => dict<JSON.t> = "singleKeyNullDict"

