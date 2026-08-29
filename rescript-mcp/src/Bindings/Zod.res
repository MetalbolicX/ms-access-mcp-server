// Bindings/Zod.res — typed FFI for Zod 3.x schema primitives
// Used by Mcp/Server.res and Mcp/Tools.res for MCP tool input validation.
// Zod API: z.object(dict), z.string(), z.boolean(), z.array(item),
// z.record(keyType, valueType), z.union([...]), z.literal(val),
// z.optional(schema), z.any().

// ---------------------------------------------------------------------------
// safeParse result — discriminated union matching Zod's {success, data|error}.
// Callers pattern-match on the Success/Failure variant and inspect .success.
// ---------------------------------------------------------------------------

type zodParseResult = Success(JSON.t) | Failure(dict<JSON.t>)

// ---------------------------------------------------------------------------
// Per-schema types — concrete: safeParse accepts JSON.t (MCP always sends JSON).
// ---------------------------------------------------------------------------

type rec zString = {
  parse: string => string,
  safeParse: JSON.t => zodParseResult,
  min: int => zString,
  max: int => zString,
}

type zBoolean = {
  parse: bool => bool,
  safeParse: JSON.t => zodParseResult,
}

type zArray = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
}

type zObject = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
  parseAsync: JSON.t => promise<JSON.t>,
  safeParseAsync: JSON.t => promise<zodParseResult>,
}

type zRecord = {
  parse: dict<JSON.t> => dict<JSON.t>,
  safeParse: JSON.t => zodParseResult,
}

type zUnion = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
}

type zLiteral = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
}

type zAny = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
}

// zOptional and zNullable are mutually recursive — same `and` block.
// The label-collision warnings for nullable are benign.
type rec zOptional = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
  optional: unit => zOptional,
  nullable: unit => zNullable,
}

and zNullable = {
  parse: JSON.t => JSON.t,
  safeParse: JSON.t => zodParseResult,
  optional: unit => zOptional,
  nullable: unit => zNullable,
}

// ---------------------------------------------------------------------------
// Externals — typed bindings to Zod JS module functions
// ---------------------------------------------------------------------------

@module("zod")
external z_string: unit => zString = "string"

@module("zod")
external z_boolean: unit => zBoolean = "boolean"

@module("zod")
external z_array: zAny => zArray = "array"

@module("zod")
external z_record: (zAny, zAny) => zRecord = "record"

@module("zod")
external z_union: array<zAny> => zUnion = "union"

@module("zod")
external z_literal: 'a => zLiteral = "literal"

@module("zod")
external z_optional: zAny => zOptional = "optional"

@module("zod")
external z_any: unit => zAny = "any"

@module("zod")
external z_object: dict<zAny> => zObject = "object"

// ReScript records are homogeneous, while Zod object shapes contain several
// schema subtypes. This is an identity cast at the FFI boundary only.
external asAny: 'a => zAny = "%identity"

// ---------------------------------------------------------------------------
// zNamespace type — convenience object matching the Zod JS API.
// ---------------------------------------------------------------------------

type zNamespace = {
  string: unit => zString,
  boolean: unit => zBoolean,
  object: dict<zAny> => zObject,
  array: zAny => zArray,
  record: (zAny, zAny) => zRecord,
  union: array<zAny> => zUnion,
  optional: zAny => zOptional,
  any: unit => zAny,
}

// ---------------------------------------------------------------------------
// z — convenience namespace grouping all Zod factory functions.
// Usage: z.string(), z.boolean(), z.object({"name": z.string()}), etc.
// ---------------------------------------------------------------------------

let z: zNamespace = {
  string: () => z_string(),
  boolean: () => z_boolean(),
  object: shape => z_object(shape),
  array: (item) => z_array(item),
  record: (keyType, valueType) => z_record(keyType, valueType),
  union: (schemas) => z_union(schemas),
  optional: (schema) => z_optional(schema),
  any: () => z_any(),
}
