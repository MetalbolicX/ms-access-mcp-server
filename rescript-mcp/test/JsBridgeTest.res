open Test

// Plan 010 — bridge smoke test: verify exnMessage bridges TS → ReScript correctly

// ---------------------------------------------------------------------------
// Case: ReScript Failure has no .message — exnMessage returns None.
// This proves the bridge correctly returns None for exceptions without .message.
// The caller (Winax/Odbc/ComVba) maps None → "Unknown error" / "Unknown".
// ---------------------------------------------------------------------------

test("exnMessage returns None for a Failure (no .message property)", () => {
  let caught = try {
    throw(Failure("no message here"))
  } catch {
    | e => Bindings.TsBridge.exnMessage(e)
  }
  switch caught {
  | Some(_m) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | None => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// Plan 011 — codec helpers: cp1252 round-trip
// ---------------------------------------------------------------------------

test("encodeCp1252: smart quote char encodes correctly", () => {
  // " (left double quotation mark, U+201C) is 0x93 in cp1252
  let smartQuote = "\u{201C}"  // "
  let bytes = Bindings.TsBridge.encodeCp1252(smartQuote)
  assertion(~operator="equal", (a, b) => a == b, bytes, [0x93])
})

test("decodeCp1252: byte decodes to smart quote char", () => {
  let text = Bindings.TsBridge.decodeCp1252([0x93])
  let expected = "\u{201C}"  // "
  assertion(~operator="equal", (a, b) => a == b, text, expected)
})

test("cp1252 round-trip: encode then decode returns original", () => {
  let smartQuote = "\u{201C}"  // "
  let original = "Hello " ++ smartQuote ++ "World" ++ smartQuote
  let encoded = Bindings.TsBridge.encodeCp1252(original)
  let decoded = Bindings.TsBridge.decodeCp1252(encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, original)
})

test("bufferToBytes: Buffer.toArray via bridge", () => {
  let buf = NodeJs.Buffer.fromStringWithEncoding("test", NodeJs.StringEncoding.utf8)
  let bytes = Bindings.TsBridge.bufferToBytes(buf)
  assertion(~operator="equal", (a, b) => a == b, bytes, [116, 101, 115, 116])
})

test("bytesFromString: mirrors encodeCp1252 for cp1252 encoding", () => {
  let smartQuote = "\u{201C}"  // "
  let bytes = Bindings.TsBridge.bytesFromString(smartQuote, "windows-1252")
  assertion(~operator="equal", (a, b) => a == b, bytes, [0x93])
})

test("bytesToString: mirrors decodeCp1252 for cp1252 encoding", () => {
  let text = Bindings.TsBridge.bytesToString([0x93], "windows-1252")
  let expected = "\u{201C}"  // "
  assertion(~operator="equal", (a, b) => a == b, text, expected)
})

test("decodeUtf16LeSkipBom: strips UTF-16LE BOM prefix", () => {
  // 0xFF 0xFE is the little-endian BOM; "A" is 0x41 0x00 in UTF-16LE
  let text = Bindings.TsBridge.decodeUtf16LeSkipBom([0xFF, 0xFE, 0x41, 0x00])
  assertion(~operator="equal", (a, b) => a == b, text, "A")
})

test("decodeUtf16LeSkipBom: empty array returns empty string", () => {
  let text = Bindings.TsBridge.decodeUtf16LeSkipBom([])
  assertion(~operator="equal", (a, b) => a == b, text, "")
})

test("decodeUtf16LeSkipBom: less than 2 bytes returns empty string", () => {
  let text = Bindings.TsBridge.decodeUtf16LeSkipBom([0x41])
  assertion(~operator="equal", (a, b) => a == b, text, "")
})

// ---------------------------------------------------------------------------
// Plan 011 — fs helpers: safeFilename
// ---------------------------------------------------------------------------

test("safeFilename: all special chars replaced globally", () => {
  let result = Bindings.TsBridge.safeFilename("a:b*c?d\"e<f>g|h")
  assertion(~operator="equal", (a, b) => a == b, result, "a_b_c_d_e_f_g_h")
})

test("safeFilename: backslash replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, Bindings.TsBridge.safeFilename("\\Path\\File"), "_Path_File")
})

test("safeFilename: no special chars returns unchanged", () => {
  assertion(~operator="equal", (a, b) => a == b, Bindings.TsBridge.safeFilename("MyForm"), "MyForm")
})

test("cleanName: strips .bas suffix", () => {
  // .bas stripped, then first underscore becomes space
  assertion(~operator="equal", (a, b) => a == b, Bindings.TsBridge.cleanName("01_My Form.bas"), "01 My Form")
})

test("cleanName: strips .txt suffix", () => {
  assertion(~operator="equal", (a, b) => a == b, Bindings.TsBridge.cleanName("form_data.txt"), "form data")
})

test("cleanName: first underscore becomes space", () => {
  assertion(~operator="equal", (a, b) => a == b, Bindings.TsBridge.cleanName("01_My Form.bas"), "01 My Form")
})

// ---------------------------------------------------------------------------
// Plan 011 — hash helpers: fileHash and isWindows
// ---------------------------------------------------------------------------

test("isWindows: returns boolean matching process.platform", () => {
  let result = Bindings.TsBridge.isWindows()
  let expected = if %raw("process.platform === 'win32'") { true } else { false }
  assertion(~operator="equal", (a, b) => a == b, result, expected)
})

test("fileHash: returns empty string for non-existent path", () => {
  let result = Bindings.TsBridge.fileHash("/nonexistent/path/file.xyz")
  assertion(~operator="equal", (a, b) => a == b, result, "")
})

test("fileHash: computes SHA256 of existing file", () => {
  // Create a temp file and hash it
  let tmpPath = Bindings.TsBridge.getTempDir() ++ "/mcp_bridge_test_" ++ Float.toString(Math.random() *. 99999.0) ++ ".txt"
  Bindings.TsBridge.writeFileSync(tmpPath, "hello")
  let hash = Bindings.TsBridge.fileHash(tmpPath)
  // SHA256 of "hello" = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
  assertion(~operator="equal", (a, b) => a == b, hash, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
  Bindings.TsBridge.deleteFile(tmpPath)
})

test("fileHash: empty file returns known SHA256", () => {
  let tmpPath = Bindings.TsBridge.getTempDir() ++ "/mcp_bridge_empty_" ++ Float.toString(Math.random() *. 99999.0) ++ ".txt"
  Bindings.TsBridge.writeFileSync(tmpPath, "")
  let hash = Bindings.TsBridge.fileHash(tmpPath)
  // SHA256 of "" = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  assertion(~operator="equal", (a, b) => a == b, hash, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
  Bindings.TsBridge.deleteFile(tmpPath)
})
