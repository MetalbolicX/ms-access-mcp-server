// access.d.ts — Structural types for Access COM object properties and methods
// Used by accessDbProps.mts as the opaque app boundary (unknown)
// No any — all internal narrowing is done in the .mts layer

export interface PropertyCategories {
  startup: Record<string, string>
  app: Record<string, string>
  project: Record<string, string>
  all: Record<string, string>
}

export interface DbPropResult {
  startup: Record<string, string>
  app: Record<string, string>
  project: Record<string, string>
  all: Record<string, string>
}

export interface SetPropertyResult {
  success: boolean
}

export interface ModuleExportResult {
  content: string
}

export interface TempFileResult {
  content: string
}

export interface LoadFromTextResult {
  success: boolean
}

// ---------------------------------------------------------------------------
// UI / Form / Report / Control types
// ---------------------------------------------------------------------------

export interface ControlSummary {
  name: string
  controlType: string
  properties: Record<string, string>
}

export interface SectionSummary {
  index: number
  name: string
  sectionType: string
  visible: boolean
  height: number
}
