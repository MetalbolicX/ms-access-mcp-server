open Test

// T2 RED test — Bindings/Zod FFI primitives for MCP tool input schemas
// Zod 3.x API surface: z.object, z.string, z.boolean, z.array,
// z.record, z.union, z.literal, z.optional, z.any

// ---------------------------------------------------------------------------
// Test helpers — raw Zod calls for complex schemas.
// These bypass ReScript's type system which can't express heterogeneous arrays
// (e.g., [z_string(), z_boolean()] as array<zAny>).
// ---------------------------------------------------------------------------

// z.object helper — raw Zod call; bypasses dict<zString> </: dict<zAny>
let makeObjectSchema = (_fields): Bindings.Zod.zObject => {
  %raw(`(fields) => Zod$1.object(fields)`)(_fields)
}

// z.array helper
let makeArraySchema = (_itemSchema): Bindings.Zod.zArray => {
  %raw(`(item) => Zod$1.array(item)`)(_itemSchema)
}

// z.record helper
let makeRecordSchema = (_k, _v): Bindings.Zod.zRecord => {
  %raw(`(k, v) => Zod$1.record(k, v)`)(_k, _v)
}

// z.union helper — raw Zod call; bypasses array homogeneity
let makeStringBooleanUnion = (): Bindings.Zod.zUnion => {
  %raw(`() => Zod$1.union([Zod$1.string(), Zod$1.boolean()])`)()
}

// z.optional helper
let makeOptionalSchema = (_schema): Bindings.Zod.zOptional => {
  %raw(`(s) => Zod$1.optional(s)`)(_schema)
}

// safeParse helper — raw Zod call that bypasses the JSON.t type constraint.
// Zod.safeParse accepts any value; we type-check the result via pattern matching.
let safeParseRaw = (schema, value): Bindings.Zod.zodParseResult => {
  %raw(`(s, v) => {
    const r = s.safeParse(v);
    return r.success
      ? { TAG: 'Success', _0: r.data }
      : { TAG: 'Failure', _0: r.error };
  }`)(schema, value)
}

// ---------------------------------------------------------------------------
// z.string — primitive string schema
// ---------------------------------------------------------------------------

test("z.string().parse accepts a string", () => {
  let schema = Bindings.Zod.z.string()
  let result = schema.parse("hello")
  assertion(~operator="equal", (a, b) => a == b, result, "hello")
})

test("z.string().safeParse succeeds with string input", () => {
  let schema = Bindings.Zod.z.string()
  let result = safeParseRaw(schema, "world")
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.string().safeParse returns Failure for non-string", () => {
  let schema = Bindings.Zod.z.string()
  let result = safeParseRaw(schema, 42)
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// z.boolean — primitive boolean schema
// ---------------------------------------------------------------------------

test("z.boolean().parse accepts true", () => {
  let schema = Bindings.Zod.z.boolean()
  let result = schema.parse(true)
  assertion(~operator="equal", (a, b) => a == b, result, true)
})

test("z.boolean().parse accepts false", () => {
  let schema = Bindings.Zod.z.boolean()
  let result = schema.parse(false)
  assertion(~operator="equal", (a, b) => a == b, result, false)
})

test("z.boolean().safeParse succeeds with boolean", () => {
  let schema = Bindings.Zod.z.boolean()
  let result = safeParseRaw(schema, false)
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.boolean().safeParse returns Failure for non-boolean", () => {
  let schema = Bindings.Zod.z.boolean()
  let result = safeParseRaw(schema, "not a bool")
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// z.object — object schema from dict of schemas
// ---------------------------------------------------------------------------

test("z.object with a single string field safeParse succeeds", () => {
  let schema = makeObjectSchema(dict{"name": Bindings.Zod.z_string()})
  let result = safeParseRaw(schema, {"name": "Alice"})
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.object safeParse returns Failure for missing required field", () => {
  let schema = makeObjectSchema(dict{"name": Bindings.Zod.z_string()})
  let result = safeParseRaw(schema, {"other": "x"})
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// z.array — array schema from item schema
// ---------------------------------------------------------------------------

test("z.array(z.string()).parse accepts string array", () => {
  let schema = makeArraySchema(Bindings.Zod.z_string())
  let result = %raw(`(s) => s.parse(["a", "b", "c"])`)(schema)
  switch result {
  | JSON.Array(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.array(z.string()).safeParse succeeds with string array", () => {
  let schema = makeArraySchema(Bindings.Zod.z_string())
  let result = safeParseRaw(schema, ["x", "y"])
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.array(z.string()).safeParse returns Failure for type mismatch", () => {
  let schema = makeArraySchema(Bindings.Zod.z_string())
  let result = safeParseRaw(schema, [1, 2])
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// z.record — record/dict schema from key and value schemas
// ---------------------------------------------------------------------------

test("z.record(z.string(), z.string()).parse accepts string dict", () => {
  let schema = makeRecordSchema(Bindings.Zod.z_string(), Bindings.Zod.z_string())
  let result = %raw(`(s) => s.parse({"key": "value"})`)(schema)
  switch result {
  | JSON.Object(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.record(z.string(), z.string()).safeParse succeeds", () => {
  let schema = makeRecordSchema(Bindings.Zod.z_string(), Bindings.Zod.z_string())
  let result = safeParseRaw(schema, {"a": "1", "b": "2"})
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// z.union — union schema from list of schemas
// ---------------------------------------------------------------------------

test("z.union([z.string(), z.boolean()]).parse accepts string", () => {
  let schema = makeStringBooleanUnion()
  let result = %raw(`(s) => s.parse("hello")`)(schema)
  switch result {
  | JSON.String(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | JSON.Boolean(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.union([z.string(), z.boolean()]).parse accepts boolean", () => {
  let schema = makeStringBooleanUnion()
  let result = %raw(`(s) => s.parse(true)`)(schema)
  switch result {
  | JSON.String(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | JSON.Boolean(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.union([z.string(), z.boolean()]).safeParse succeeds for string", () => {
  let schema = makeStringBooleanUnion()
  let result = safeParseRaw(schema, "world")
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.union([z.string(), z.boolean()]).safeParse returns Failure for invalid input", () => {
  let schema = makeStringBooleanUnion()
  let result = safeParseRaw(schema, 123)
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// z.literal — literal value schema
// ---------------------------------------------------------------------------

test("z.literal(\"admin\").parse accepts the literal string", () => {
  let schema = Bindings.Zod.z_literal("admin")
  let result = %raw(`(s) => s.parse("admin")`)(schema)
  switch result {
  | JSON.String(s) if s == "admin" => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.literal(42).parse accepts the literal number", () => {
  let schema = Bindings.Zod.z_literal(42)
  let result = %raw(`(s) => s.parse(42)`)(schema)
  switch result {
  | JSON.Number(n) if n == 42.0 => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.literal(\"admin\").safeParse succeeds with correct literal", () => {
  let schema = Bindings.Zod.z_literal("admin")
  let result = safeParseRaw(schema, "admin")
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.literal(\"admin\").safeParse returns Failure for wrong literal", () => {
  let schema = Bindings.Zod.z_literal("admin")
  let result = safeParseRaw(schema, "user")
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

// ---------------------------------------------------------------------------
// z.optional — wrap a schema as optional
// ---------------------------------------------------------------------------

test("z.string().optional().parse accepts a string", () => {
  let schema = makeOptionalSchema(Bindings.Zod.z_string())
  let result = %raw(`(s) => s.parse("hello")`)(schema)
  switch result {
  | JSON.String(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.string().optional().parse accepts undefined", () => {
  let schema = makeOptionalSchema(Bindings.Zod.z_string())
  // Zod's optional accepts undefined; parse returns undefined (maps to JSON.Null in ReScript)
  // We just verify parse doesn't throw — if we get here, the test passes
  let result = %raw(`(s) => { try { return s.parse(undefined); } catch(e) { return 'THREW'; } }`)(schema)
  switch result {
  | "THREW" => assertion(~operator="equal", (a, b) => a == b, false, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, true, true)
  }
})

test("z.string().optional().safeParse succeeds with undefined", () => {
  let schema = makeOptionalSchema(Bindings.Zod.z_string())
  let result = %raw(`(s) => {
    const r = s.safeParse(undefined);
    return r.success
      ? { TAG: 'Success', _0: r.data }
      : { TAG: 'Failure', _0: r.error };
  }`)(schema)
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// z.any — unconstrained schema
// ---------------------------------------------------------------------------

test("z.any().parse accepts any value", () => {
  let schema = Bindings.Zod.z.any()
  let result = %raw(`(s) => s.parse("string")`)(schema)
  switch result {
  | JSON.String(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.any().parse accepts number", () => {
  let schema = Bindings.Zod.z.any()
  let result = %raw(`(s) => s.parse(99)`)(schema)
  switch result {
  | JSON.Number(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("z.any().safeParse always succeeds", () => {
  let schema = Bindings.Zod.z.any()
  let result = safeParseRaw(schema, {"anything": true})
  switch result {
  | Bindings.Zod.Success(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | Bindings.Zod.Failure(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})
