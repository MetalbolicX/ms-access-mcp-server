// accessDbProps.mts — Typed bridge for ComDbProps.res raw blocks
// All exports are arrow functions with static node: ESM imports only.
// No winax import — opaque app boundary uses unknown, narrowed internally.

import { join as pathJoin } from "node:path"
import { tmpdir } from "node:os"
import { readFileSync, writeFileSync, unlinkSync } from "node:fs"
import { randomBytes } from "node:crypto"

// ---------------------------------------------------------------------------
// getDatabaseProperties — reads CurrentDb.Properties and CurrentProject
// ---------------------------------------------------------------------------

export const getDatabaseProperties = (
  app: unknown,
  names: string[] | null
): Promise<{
  startup: Record<string, string>
  app: Record<string, string>
  project: Record<string, string>
  all: Record<string, string>
}> => {
  return new Promise((resolve) => {
    try {
      const accessApp = app as {
        CurrentDb?: () => unknown
        CurrentProject?: unknown
      }
      const db = accessApp.CurrentDb ? accessApp.CurrentDb() : null
      if (!db) {
        resolve({ startup: {}, app: {}, project: {}, all: {} })
        return
      }
      const dbObj = db as { Properties?: { Count: number; (i: number): { Name: string; Value: unknown } } }

      const namesFilter = names ? new Set(names.map((n) => n.toLowerCase())) : null
      const startup: Record<string, string> = {}
      const appProps: Record<string, string> = {}
      const project: Record<string, string> = {}
      const allProps: Record<string, string> = {}

      try {
        if (dbObj.Properties) {
          const count = dbObj.Properties.Count
          for (let i = 0; i < count; i++) {
            try {
              const prop: { Name: string; Value: unknown } = dbObj.Properties(i)
              const name = prop.Name
              if (!name) continue
              if (name.startsWith("_") || name.startsWith("MSys")) continue
              if (namesFilter && !namesFilter.has(name.toLowerCase())) continue
              let val: unknown = prop.Value
              if (val === null) val = ""
              else if (typeof val === "boolean") val = val ? "True" : "False"
              else val = String(val)
              allProps[name] = val as string
              const lname = name.toLowerCase()
              const startupSet = new Set([
                "apptitle", "startupform", "startupshowform", "allowfullmenus",
                "allowbuiltinpanels", "allowdefaultshortcutmenus", "allowshortcutmenus",
                "allowtoolbarchanges", "allowdesignchanges", "startmenubar",
                "startupmenubar", "startupshortcutmenubar", "startupshowstatusbar",
                "startupshowcontextmenus", "usesingledocumentinterface", "dontshowhelptext",
              ])
              const appSet = new Set([
                "author", "company", "description", "keywords", "subject",
                "manager", "category", "comments", "hyperlinkbase", "appversion",
              ])
              if (startupSet.has(lname)) startup[name] = val as string
              if (appSet.has(lname)) appProps[name] = val as string
            } catch (_e) {}
          }
        }
      } catch (_e) {}

      // Project info
      try {
        const cp = accessApp.CurrentProject as {
          FullName?: unknown
          Name?: unknown
          ProjectType?: unknown
        } | null
        if (cp) {
          project["Path"] = cp.FullName ? String(cp.FullName) : ""
          project["Name"] = cp.Name ? String(cp.Name) : ""
          project["ProjectType"] = cp.ProjectType ? "ADP" : "MDB/ACCDB"
        }
      } catch (_e) {}

      resolve({ startup, app: appProps, project, all: allProps })
    } catch (_e) {
      resolve({ startup: {}, app: {}, project: {}, all: {} })
    }
  })
}

// ---------------------------------------------------------------------------
// setDatabaseProperty — create or update a property on CurrentDb.Properties
// ---------------------------------------------------------------------------

export const setDatabaseProperty = (
  app: unknown,
  name: string,
  value: string,
  type_: string
): Promise<boolean> => {
  return new Promise((resolve) => {
    try {
      const accessApp = app as {
        CurrentDb?: () => unknown
      }
      const db = accessApp.CurrentDb ? accessApp.CurrentDb() : null
      if (!db) { resolve(false); return }

      const dbObj = db as {
        Properties?: {
          Count: number
          (i: number): { Name: string; Type?: number; Value?: unknown }
          Append?: (prop: unknown) => void
        }
        CreateProperty?: (name: string, type_: number, value: unknown) => unknown
      }

      // Determine DAO type
      let daoType: number
      let typeLabel: string
      if (type_) {
        const typeMap: Record<string, number> = {
          text: 10, str: 10, string: 10,
          long: 4, int: 4, integer: 3,
          boolean: 1, bool: 1,
          double: 7, float: 7,
          date: 8, datetime: 8,
          byte: 2,
        }
        daoType = typeMap[type_.toLowerCase()] ?? 10
        typeLabel = type_
      } else {
        // Auto-detect
        const lowered = value.toLowerCase()
        if (lowered === "true" || lowered === "false") { daoType = 1; typeLabel = "Boolean" }
        else if (/^\d+$/.test(value)) { daoType = 4; typeLabel = "Long" }
        else {
          const f = parseFloat(value)
          if (!isNaN(f)) { daoType = 7; typeLabel = "Double" }
          else { daoType = 10; typeLabel = "Text" }
        }
      }

      // Coerce value
      let coerced: unknown
      if (daoType === 1) coerced = ["true", "1", "yes", "-1"].includes(value.toLowerCase())
      else if (daoType === 2 || daoType === 3 || daoType === 4) coerced = parseInt(value) || 0
      else if (daoType === 7) coerced = parseFloat(value) || 0.0
      else coerced = value

      // Find existing property
      let existing: { Name: string; Type?: number; Value?: unknown } | null = null
      try {
        if (dbObj.Properties) {
          const count = dbObj.Properties.Count
          for (let i = 0; i < count; i++) {
            try {
              const prop = dbObj.Properties(i)
              if (prop.Name === name) { existing = prop; break }
            } catch (_e) {}
          }
        }
      } catch (_e) {}

      if (existing) {
        try { if (existing.Type !== undefined) existing.Type = daoType } catch (_e) {}
        existing.Value = coerced
        resolve(true)
      } else {
        try {
          if (dbObj.CreateProperty && dbObj.Properties && dbObj.Properties.Append) {
            const newProp = dbObj.CreateProperty(name, daoType, coerced)
            dbObj.Properties.Append(newProp)
          }
          resolve(true)
        } catch (_e) { resolve(false) }
      }
    } catch (_e) { resolve(false) }
  })
}

// ---------------------------------------------------------------------------
// exportModuleToText — export VBA module code from VBE (in-memory)
// ---------------------------------------------------------------------------

export const exportModuleToText = (
  app: unknown,
  moduleName: string
): Promise<string> => {
  return new Promise((resolve) => {
    try {
      const accessApp = app as {
        VBE?: {
          VBProjects: {
            Count: number
            (i: number): {
              VBComponents: {
                Count: number
                (i: number): {
                  Name: string
                  CodeModule?: {
                    CountOfLines: number
                    Lines: (start: number, count: number) => string
                  }
                }
              }
            }
          }
        }
      }
      const vbe = accessApp.VBE
      if (!vbe) { resolve(""); return }

      for (let pi = 1; pi <= vbe.VBProjects.Count; pi++) {
        const vbProj = vbe.VBProjects(pi)
        for (let ci = 1; ci <= vbProj.VBComponents.Count; ci++) {
          const comp = vbProj.VBComponents(ci)
          if (comp.Name === moduleName) {
            const cm = comp.CodeModule
            if (cm && cm.CountOfLines > 0) {
              resolve(cm.Lines(1, cm.CountOfLines))
            } else {
              resolve("")
            }
            return
          }
        }
      }
    } catch (_e) {}
    resolve("")
  })
}

// ---------------------------------------------------------------------------
// _tempSaveAsText — internal: use SaveAsText via COM, read temp file, return content
// ---------------------------------------------------------------------------

export const _tempSaveAsText = (
  app: unknown,
  objectType: number,
  objectName: string
): Promise<string> => {
  return new Promise((resolve) => {
    const tmp = pathJoin(
      tmpdir(),
      "mcp_exp_" + randomBytes(8).toString("hex") + ".txt"
    )
    try {
      const accessApp = app as {
        SaveAsText?: (objectType: number, objectName: string, path: string) => void
      }
      if (accessApp.SaveAsText) {
        accessApp.SaveAsText(objectType, objectName, tmp)
      }
      const buf = readFileSync(tmp)
      unlinkSync(tmp)
      // Decode UTF-16-LE, strip BOM
      const content = buf.toString("utf16le").replace(/^\ufeff/, "")
      resolve(content)
    } catch (_e) {
      try { unlinkSync(tmp) } catch (_e2) {}
      resolve("")
    }
  })
}

// ---------------------------------------------------------------------------
// _tempLoadFromText — internal: write content to temp file, call LoadFromText
// ---------------------------------------------------------------------------

export const _tempLoadFromText = (
  app: unknown,
  objectType: number,
  objectName: string,
  textData: string
): Promise<boolean> => {
  return new Promise((resolve) => {
    const tmp = pathJoin(
      tmpdir(),
      "mcp_imp_" + randomBytes(8).toString("hex") + ".txt"
    )
    try {
      // Write UTF-16LE with BOM for LoadFromText
      const buf = Buffer.from("\ufeff" + textData, "utf16le")
      writeFileSync(tmp, buf)
      const accessApp = app as {
        LoadFromText?: (objectType: number, objectName: string, path: string) => void
      }
      if (accessApp.LoadFromText) {
        accessApp.LoadFromText(objectType, objectName, tmp)
      }
      unlinkSync(tmp)
      resolve(true)
    } catch (_e) {
      try { unlinkSync(tmp) } catch (_e2) {}
      resolve(false)
    }
  })
}
