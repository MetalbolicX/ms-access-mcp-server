// JsCom.res — Typed externals for accessDbProps.mjs and accessUi.mjs
// Replaces %raw blocks in ComDbProps.res and ComUi.res

type dbPropResult = {
  startup: dict<string>,
  app: dict<string>,
  project: dict<string>,
  all: dict<string>,
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

// @unsafe is used here because the COM object type (ComInterfaces.comObject)
// is typed as unit in the bindings but is actually a live COM object at runtime.
// The TypeScript side accepts 'unknown' which ReScript approximates with @unsafe.
@unsafe
@module("../Js/accessDbProps.mjs")
external getDatabaseProperties: (
  ComInterfaces.comObject,
  option<array<string>>
) => Promise.t<dbPropResult> = "getDatabaseProperties"

@unsafe
@module("../Js/accessDbProps.mjs")
external setDatabaseProperty: (
  ComInterfaces.comObject,
  ~name: string,
  ~value: string,
  ~type_: string
) => Promise.t<bool> = "setDatabaseProperty"

@unsafe
@module("../Js/accessDbProps.mjs")
external exportModuleToText: (
  ComInterfaces.comObject,
  string
) => Promise.t<string> = "exportModuleToText"

@unsafe
@module("../Js/accessDbProps.mjs")
external _tempSaveAsText: (
  ComInterfaces.comObject,
  int,
  string
) => Promise.t<string> = "_tempSaveAsText"

@unsafe
@module("../Js/accessDbProps.mjs")
external _tempLoadFromText: (
  ComInterfaces.comObject,
  int,
  string,
  string
) => Promise.t<bool> = "_tempLoadFromText"

// ---------------------------------------------------------------------------
// UI bridge — accessUi.mjs
// ---------------------------------------------------------------------------

@unsafe
@module("../Js/accessUi.mjs")
external _saveObjectToText: (
  ComInterfaces.comObject,
  int,
  string
) => Promise.t<string> = "_saveObjectToText"

@unsafe
@module("../Js/accessUi.mjs")
external _loadObjectFromText: (
  ComInterfaces.comObject,
  int,
  string,
  string
) => Promise.t<bool> = "_loadObjectFromText"

@unsafe
@module("../Js/accessUi.mjs")
external getFormControls: (
  ComInterfaces.comObject,
  string
) => Promise.t<array<controlSummary>> = "getFormControls"

@unsafe
@module("../Js/accessUi.mjs")
external getFormProperties: (
  ComInterfaces.comObject,
  string
) => Promise.t<dict<string>> = "getFormProperties"

@unsafe
@module("../Js/accessUi.mjs")
external setFormProperty: (
  ComInterfaces.comObject,
  string,
  string,
  string
) => Promise.t<bool> = "setFormProperty"

@unsafe
@module("../Js/accessUi.mjs")
external createForm: (
  ComInterfaces.comObject,
  string
) => Promise.t<bool> = "createForm"

@unsafe
@module("../Js/accessUi.mjs")
external getReportControls: (
  ComInterfaces.comObject,
  string
) => Promise.t<array<controlSummary>> = "getReportControls"

@unsafe
@module("../Js/accessUi.mjs")
external createReport: (
  ComInterfaces.comObject,
  string
) => Promise.t<bool> = "createReport"

@unsafe
@module("../Js/accessUi.mjs")
external getControlProperties: (
  ComInterfaces.comObject,
  string,
  string
) => Promise.t<dict<string>> = "getControlProperties"

@unsafe
@module("../Js/accessUi.mjs")
external setControlProperty: (
  ComInterfaces.comObject,
  string,
  string,
  string,
  string
) => Promise.t<bool> = "setControlProperty"

@unsafe
@module("../Js/accessUi.mjs")
external addControl: (
  ComInterfaces.comObject,
  string,
  string,
  string,
  int
) => Promise.t<bool> = "addControl"

@unsafe
@module("../Js/accessUi.mjs")
external removeControl: (
  ComInterfaces.comObject,
  string,
  string
) => Promise.t<bool> = "removeControl"

@unsafe
@module("../Js/accessUi.mjs")
external getFormSections: (
  ComInterfaces.comObject,
  string
) => Promise.t<array<sectionSummary>> = "getFormSections"

@unsafe
@module("../Js/accessUi.mjs")
external getFormSectionProperties: (
  ComInterfaces.comObject,
  string,
  int
) => Promise.t<dict<string>> = "getFormSectionProperties"

@unsafe
@module("../Js/accessUi.mjs")
external setFormSectionProperty: (
  ComInterfaces.comObject,
  string,
  int,
  string,
  string
) => Promise.t<bool> = "setFormSectionProperty"
