// ComUi.resi — Interface for UI forms/reports/controls/macros + encoding operations
// Task 4.2 GREEN: UI + SaveAsText/LoadFromText ops

// ---------------------------------------------------------------------------
// Object type constants
// ---------------------------------------------------------------------------

let acForm: int
let acReport: int
let acModule: int
let acMacro: int

// Section constants
let sectionDetail: int
let sectionHeader: int
let sectionFooter: int
let sectionPageHeader: int
let sectionPageFooter: int

// ---------------------------------------------------------------------------
// Control type helpers
// ---------------------------------------------------------------------------

let controlTypeId: string => int
let controlTypeName: int => string
let sectionName: int => string

// ---------------------------------------------------------------------------
// Encoding helpers (exposed for testing)
// ---------------------------------------------------------------------------

let _systemAnsiEncoding: unit => string
let _encodeForSave: (int, string) => array<int>
let _decodeFromLoad: (int, array<int>) => string

// ---------------------------------------------------------------------------
// Named result types
// ---------------------------------------------------------------------------

type formSummary = {
  name: string,
  recordSource: string,
}

type reportSummary = {
  name: string,
  recordSource: string,
}

type controlSummary = {
  name: string,
  controlType: string,
  properties: dict<string>,
}

type sectionSummary = {
  index: int,
  name: string,
  sectionType: string,
  visible: bool,
  height: int,
}

type macroSummary = {
  name: string,
  macroType: string,
}

// ---------------------------------------------------------------------------
// SaveAsText / LoadFromText
// ---------------------------------------------------------------------------

let exportFormToText: (ComInterfaces.sessionHandles, string) => Promise.t<string>
let importFormFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>
let exportReportToText: (ComInterfaces.sessionHandles, string) => Promise.t<string>
let importReportFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>
let exportMacroToText: (ComInterfaces.sessionHandles, string) => Promise.t<string>
let importMacroFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>

// ---------------------------------------------------------------------------
// Form operations
// ---------------------------------------------------------------------------

let getForms: ComInterfaces.sessionHandles => Promise.t<array<formSummary>>
let formExists: (ComInterfaces.sessionHandles, string) => Promise.t<bool>
let getFormControls: (ComInterfaces.sessionHandles, string) => Promise.t<array<controlSummary>>
let getFormProperties: (ComInterfaces.sessionHandles, string) => Promise.t<dict<string>>
let setFormProperty: (ComInterfaces.sessionHandles, string, string, string) => Promise.t<bool>
let createForm: (ComInterfaces.sessionHandles, string) => Promise.t<bool>
let deleteForm: (ComInterfaces.sessionHandles, string) => Promise.t<bool>
let renameForm: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>

// ---------------------------------------------------------------------------
// Report operations
// ---------------------------------------------------------------------------

let getReports: ComInterfaces.sessionHandles => Promise.t<array<reportSummary>>
let reportExists: (ComInterfaces.sessionHandles, string) => Promise.t<bool>
let getReportControls: (ComInterfaces.sessionHandles, string) => Promise.t<array<controlSummary>>
let createReport: (ComInterfaces.sessionHandles, string) => Promise.t<bool>
let deleteReport: (ComInterfaces.sessionHandles, string) => Promise.t<bool>

// ---------------------------------------------------------------------------
// Macro operations
// ---------------------------------------------------------------------------

let getMacros: ComInterfaces.sessionHandles => Promise.t<array<macroSummary>>

// ---------------------------------------------------------------------------
// Control operations
// ---------------------------------------------------------------------------

let getControlProperties: (ComInterfaces.sessionHandles, string, string) => Promise.t<dict<string>>
let setControlProperty: (ComInterfaces.sessionHandles, string, string, string, string) => Promise.t<bool>
let addControl: (ComInterfaces.sessionHandles, string, string, string, int) => Promise.t<bool>
let removeControl: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>

// ---------------------------------------------------------------------------
// Form section operations
// ---------------------------------------------------------------------------

let getFormSections: (ComInterfaces.sessionHandles, string) => Promise.t<array<sectionSummary>>
let getFormSectionProperties: (ComInterfaces.sessionHandles, string, int) => Promise.t<dict<string>>
let setFormSectionProperty: (ComInterfaces.sessionHandles, string, int, string, string) => Promise.t<bool>
