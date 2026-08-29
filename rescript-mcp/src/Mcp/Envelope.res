// Mcp/Envelope.res — translate Facade dict → MCP response envelope
// Transforms a Facade service-layer dict into the MCP JSON-RPC response shape:
//   { isError: bool, content: array<contentBlock> }
// where each contentBlock has type_:"text" and text:<JSON.stringify of the input dict>.

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// contentBlock — MCP content item with type_:"text" and the serialized input
type contentBlock = {
  type_: string,  // "text" for all current content blocks
  text: string,   // JSON.stringify of the original Facade dict
}

// response — MCP JSON-RPC response envelope
type response = {
  isError: bool,
  content: array<contentBlock>,
}

// ---------------------------------------------------------------------------
// Helper: check if dict signals an error via success:false
// Returns true only when dict["success"] === JSON.Boolean(false).
// Returns false when absent, JSON.Boolean(true), or any other type.
// ---------------------------------------------------------------------------

let _isError: dict<JSON.t> => bool = d => {
  switch Dict.get(d, "success") {
  | Some(JSON.Boolean(false)) => true
  | _ => false
  }
}

// ---------------------------------------------------------------------------
// transcribe — Facade dict → MCP response envelope
//
// Converts a Facade service-layer dict into the MCP JSON-RPC response envelope.
//
// Rules:
//   - When dict["success"] === JSON.Boolean(false), isError = true
//   - When dict["success"] is absent or JSON.Boolean(true), isError = false
//   - dry_run:true is NOT treated as an error (passes through as isError:false)
//   - Empty dict {} defaults to isError:false
//   - The text field always contains the JSON.stringify of the original input dict
// ---------------------------------------------------------------------------

let transcribe: JSON.t => response = input => {
  switch input {
  | JSON.Object(d) => {
      let isError = _isError(d)
      let text = JSON.stringify(input)
      let content: array<contentBlock> = [{type_: "text", text: text}]
      {isError: isError, content: content}
    }
  | _ => {
      // Defensive: non-object input is treated as empty and not an error
      let text = JSON.stringify(input)
      let content: array<contentBlock> = [{type_: "text", text: text}]
      {isError: false, content: content}
    }
  }
}

// ---------------------------------------------------------------------------
// transcribeJson — Facade dict → MCP CallToolResult as JSON.t
//
// Records compile their field names verbatim (type_), but the MCP wire format
// requires "type". Build the JS object through JSON.t so the wire shape is
// exactly { isError, content: [{ type: "text", text: <json> }] }.
// ---------------------------------------------------------------------------

let transcribeJson: JSON.t => JSON.t = input => {
  let r = transcribe(input)
  JSON.Object(dict{
    "isError": JSON.Boolean(r.isError),
    "content": JSON.Array(
      r.content->Array.map(b =>
        JSON.Object(dict{
          "type": JSON.String(b.type_),
          "text": JSON.String(b.text),
        })
      ),
    ),
  })
}
