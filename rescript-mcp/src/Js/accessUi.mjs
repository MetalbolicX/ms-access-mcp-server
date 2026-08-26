// accessUi.mts — Typed bridge for ComUi.res UI/form/report/control raw blocks
// All exports are arrow functions with static ESM imports only.
// No winax import — opaque app boundary uses unknown, narrowed internally.
import { readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { join as pathJoin } from "node:path";
import { randomBytes } from "node:crypto";
import { encodeCp1252 } from "./codec.mjs";
// ---------------------------------------------------------------------------
// Object type constants (Access Ac... enum values — must match ComUi.res)
// ---------------------------------------------------------------------------
const AC_FORM = 2;
const AC_REPORT = 4;
const AC_SAVE_NO = 2;
const AC_SAVE_YES = 1;
const AC_DESIGN = 1;
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
/** Open a form in design view, return the active form object or null.
 *  Tries DoCmd.OpenForm first (active), falls back to Forms collection. */
const openFormDesign = (app, formName) => {
    return new Promise((resolve) => {
        try {
            const accessApp = app;
            const docmd = accessApp.DoCmd;
            if (!docmd || !docmd.OpenForm) {
                resolve(null);
                return;
            }
            docmd.OpenForm(formName, AC_DESIGN)
                .then(() => {
                const form = accessApp.Screen?.ActiveForm;
                resolve(form ?? null);
            })
                .catch(() => {
                // Fallback: try Forms collection directly
                const forms = accessApp.Forms;
                if (forms) {
                    const fo = forms;
                    resolve(fo(formName));
                }
                else {
                    resolve(null);
                }
            });
        }
        catch {
            resolve(null);
        }
    });
};
/** Open a report in design view, return the report object or null. */
const openReportDesign = (app, reportName) => {
    return new Promise((resolve) => {
        try {
            const accessApp = app;
            const docmd = accessApp.DoCmd;
            if (!docmd || !docmd.OpenReport) {
                resolve(null);
                return;
            }
            docmd.OpenReport(reportName, AC_DESIGN)
                .then(() => {
                const reports = accessApp.Reports;
                if (reports) {
                    const ro = reports;
                    resolve(ro(reportName));
                }
                else {
                    resolve(null);
                }
            })
                .catch(() => resolve(null));
        }
        catch {
            resolve(null);
        }
    });
};
/** Close a form or report with the specified save option.
 *  objectType: acForm=2, acReport=4
 *  saveOption: acSaveNo=2, acSaveYes=1 */
const closeWithSave = (app, objectType, objectName, saveOption) => {
    return new Promise((resolve) => {
        try {
            const accessApp = app;
            const docmd = accessApp.DoCmd;
            if (!docmd || !docmd.Close) {
                resolve();
                return;
            }
            docmd.Close(objectType, objectName, saveOption)
                .then(resolve)
                .catch(() => resolve());
        }
        catch {
            resolve();
        }
    });
};
/** Enumerate properties of a COM object into Record<string, string>.
 *  Returns empty record on any error. */
const enumProperties = (obj) => {
    const result = {};
    try {
        const target = obj;
        if (!target.Properties)
            return result;
        const count = target.Properties.Count;
        for (let i = 0; i < count; i++) {
            try {
                const p = target.Properties(i);
                if (p.Name)
                    result[p.Name] = p.Value === null ? "" : String(p.Value);
            }
            catch { /* skip bad property */ }
        }
    }
    catch { /* ignore */ }
    return result;
};
/** Find a control by name in a form's Controls collection.
 *  Returns the control object or null. */
const findControl = (form, controlName) => {
    try {
        const f = form;
        if (!f.Controls)
            return null;
        const count = f.Controls.Count;
        for (let i = 0; i < count; i++) {
            try {
                const ctrl = f.Controls(i);
                if (ctrl.Name === controlName)
                    return ctrl;
            }
            catch { /* skip */ }
        }
    }
    catch { /* ignore */ }
    return null;
};
/** Convert raw control array from openFormDesign/getFormControls into summaries. */
const toControlSummaries = (raw) => raw.map((item) => {
    const o = item;
    return {
        name: o.name ? String(o.name) : "",
        controlType: o.controlType ? String(o.controlType) : "",
        properties: o.properties ?? {},
    };
});
/** Section index to name map */
const SECTION_NAMES = ["detail", "header", "footer", "page_header", "page_footer"];
// ---------------------------------------------------------------------------
// _saveObjectToText — export Access object via SaveAsText
// ---------------------------------------------------------------------------
export const _saveObjectToText = (app, objectType, objectName) => {
    return new Promise((resolve) => {
        const tmp = pathJoin(process.env.TEMP ?? process.env.TMP ?? "/tmp", "mcp_save_" + Math.random().toString(36).slice(2) + ".txt");
        try {
            writeFileSync(tmp, Buffer.alloc(0));
            const accessApp = app;
            const promise = accessApp.SaveAsText?.(objectType, objectName, tmp);
            if (promise && typeof promise.then === "function") {
                promise
                    .then(() => {
                    try {
                        const buf = readFileSync(tmp);
                        unlinkSync(tmp);
                        if (!buf || buf.length === 0) {
                            resolve("");
                            return;
                        }
                        // SaveAsText always outputs UTF-16LE with BOM
                        const content = buf.toString("utf16le").replace(/^\ufeff/, "");
                        resolve(content);
                    }
                    catch {
                        resolve("");
                    }
                })
                    .catch(() => {
                    try {
                        unlinkSync(tmp);
                    }
                    catch { /* ignore */ }
                    resolve("");
                });
            }
            else {
                // Synchronous or no-op
                try {
                    unlinkSync(tmp);
                }
                catch { /* ignore */ }
                resolve("");
            }
        }
        catch {
            try {
                unlinkSync(tmp);
            }
            catch { /* ignore */ }
            resolve("");
        }
    });
};
// ---------------------------------------------------------------------------
// _loadObjectFromText — import Access object via LoadFromText
// ---------------------------------------------------------------------------
export const _loadObjectFromText = (app, objectType, objectName, textData) => {
    return new Promise((resolve) => {
        const tmp = pathJoin(process.env.TEMP ?? process.env.TMP ?? "/tmp", "mcp_load_" + randomBytes(8).toString("hex") + ".txt");
        try {
            // acModule (5) → ANSI (no BOM), others → UTF-16LE with BOM
            let buf;
            if (objectType === 5) {
                // ANSI: cp1252 encoding via static import
                const bytes = encodeCp1252(textData);
                buf = Buffer.from(bytes);
            }
            else {
                buf = Buffer.from("\ufeff" + textData, "utf16le");
            }
            writeFileSync(tmp, buf);
            const accessApp = app;
            const promise = accessApp.LoadFromText?.(objectType, objectName, tmp);
            if (promise && typeof promise.then === "function") {
                promise
                    .then(() => {
                    try {
                        unlinkSync(tmp);
                    }
                    catch { /* ignore */ }
                    resolve(true);
                })
                    .catch(() => {
                    try {
                        unlinkSync(tmp);
                    }
                    catch { /* ignore */ }
                    resolve(false);
                });
            }
            else {
                try {
                    unlinkSync(tmp);
                }
                catch { /* ignore */ }
                resolve(false);
            }
        }
        catch {
            try {
                unlinkSync(tmp);
            }
            catch { /* ignore */ }
            resolve(false);
        }
    });
};
// ---------------------------------------------------------------------------
// getFormControls — get all controls in a form
// ---------------------------------------------------------------------------
export const getFormControls = (app, formName) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve([]);
                return;
            }
            const controls = [];
            try {
                const f = form;
                const count = f.Controls.Count;
                for (let i = 0; i < count; i++) {
                    try {
                        const ctrl = f.Controls(i);
                        controls.push({
                            name: ctrl.Name,
                            controlType: String(ctrl.ControlType),
                            properties: {},
                        });
                    }
                    catch { /* skip bad control */ }
                }
            }
            catch { /* ignore */ }
            closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(controls));
        })
            .catch(() => resolve([]));
    });
};
// ---------------------------------------------------------------------------
// getFormProperties — get all form properties
// ---------------------------------------------------------------------------
export const getFormProperties = (app, formName) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve({});
                return;
            }
            const props = enumProperties(form);
            closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(props));
        })
            .catch(() => resolve({}));
    });
};
// ---------------------------------------------------------------------------
// setFormProperty — set a single form property
// ---------------------------------------------------------------------------
export const setFormProperty = (app, formName, propertyName, value) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve(false);
                return;
            }
            try {
                const f = form;
                f.Properties(propertyName).Value = value;
                closeWithSave(app, AC_FORM, formName, AC_SAVE_YES).then(() => resolve(true));
            }
            catch {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(false));
            }
        })
            .catch(() => resolve(false));
    });
};
// ---------------------------------------------------------------------------
// createForm — create a new blank form
// ---------------------------------------------------------------------------
export const createForm = (app, formName) => {
    return new Promise((resolve) => {
        try {
            const accessApp = app;
            const docmd = accessApp.DoCmd;
            if (!docmd || !docmd.CreateForm) {
                resolve(false);
                return;
            }
            docmd.CreateForm()
                .then((formObj) => {
                try {
                    const fo = formObj;
                    if (fo && fo.Name)
                        fo.Name = formName;
                }
                catch { /* ignore name set failure */ }
                const actualName = formObj?.Name ?? formName;
                closeWithSave(app, AC_FORM, actualName, AC_SAVE_YES).then(() => resolve(true));
            })
                .catch(() => resolve(false));
        }
        catch {
            resolve(false);
        }
    });
};
// ---------------------------------------------------------------------------
// getReportControls — get all controls in a report
// ---------------------------------------------------------------------------
export const getReportControls = (app, reportName) => {
    return new Promise((resolve) => {
        openReportDesign(app, reportName)
            .then((report) => {
            if (!report) {
                resolve([]);
                return;
            }
            const controls = [];
            try {
                const r = report;
                const count = r.Controls.Count;
                for (let i = 0; i < count; i++) {
                    try {
                        const ctrl = r.Controls(i);
                        controls.push({
                            name: ctrl.Name,
                            controlType: String(ctrl.ControlType),
                            properties: {},
                        });
                    }
                    catch { /* skip bad control */ }
                }
            }
            catch { /* ignore */ }
            closeWithSave(app, AC_REPORT, reportName, AC_SAVE_NO).then(() => resolve(controls));
        })
            .catch(() => resolve([]));
    });
};
// ---------------------------------------------------------------------------
// createReport — create a new blank report
// ---------------------------------------------------------------------------
export const createReport = (app, reportName) => {
    return new Promise((resolve) => {
        try {
            const accessApp = app;
            const docmd = accessApp.DoCmd;
            if (!docmd || !docmd.CreateReport) {
                resolve(false);
                return;
            }
            docmd.CreateReport()
                .then((reportObj) => {
                try {
                    const ro = reportObj;
                    if (ro && ro.Name)
                        ro.Name = reportName;
                }
                catch { /* ignore name set failure */ }
                const actualName = reportObj?.Name ?? reportName;
                closeWithSave(app, AC_REPORT, actualName, AC_SAVE_YES).then(() => resolve(true));
            })
                .catch(() => resolve(false));
        }
        catch {
            resolve(false);
        }
    });
};
// ---------------------------------------------------------------------------
// getControlProperties — get all properties of a control in a form
// ---------------------------------------------------------------------------
export const getControlProperties = (app, formName, controlName) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve({});
                return;
            }
            const ctrl = findControl(form, controlName);
            if (!ctrl) {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve({}));
                return;
            }
            const props = enumProperties(ctrl);
            closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(props));
        })
            .catch(() => resolve({}));
    });
};
// ---------------------------------------------------------------------------
// setControlProperty — set a property of a control in a form
// ---------------------------------------------------------------------------
export const setControlProperty = (app, formName, controlName, propertyName, value) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve(false);
                return;
            }
            const ctrl = findControl(form, controlName);
            if (!ctrl) {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(false));
                return;
            }
            try {
                const c = ctrl;
                c.Properties(propertyName).Value = value;
                closeWithSave(app, AC_FORM, formName, AC_SAVE_YES).then(() => resolve(true));
            }
            catch {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(false));
            }
        })
            .catch(() => resolve(false));
    });
};
// ---------------------------------------------------------------------------
// addControl — add a control to a form
// ---------------------------------------------------------------------------
export const addControl = (app, formName, controlTypeId, newControlName, section) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve(false);
                return;
            }
            try {
                const accessApp = app;
                const docmd = accessApp.DoCmd;
                if (!docmd || !docmd.CreateControl) {
                    closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(false));
                    return;
                }
                const ctrl = docmd.CreateControl(formName, controlTypeId, section);
                try {
                    const c = ctrl;
                    if (c)
                        c.Name = newControlName;
                }
                catch { /* ignore name set failure */ }
                closeWithSave(app, AC_FORM, formName, AC_SAVE_YES).then(() => resolve(true));
            }
            catch {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(false));
            }
        })
            .catch(() => resolve(false));
    });
};
// ---------------------------------------------------------------------------
// removeControl — remove a control from a form
// ---------------------------------------------------------------------------
export const removeControl = (app, formName, controlName) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve(false);
                return;
            }
            let found = false;
            try {
                const c = form;
                if (c.Controls) {
                    const count = c.Controls.Count;
                    for (let i = 0; i < count; i++) {
                        const ctrl = c.Controls(i);
                        if (ctrl.Name !== controlName)
                            continue;
                        ctrl.SetFocus?.();
                        const accessApp = app;
                        // acCmdDelete = 365
                        accessApp.DoCmd?.RunCommand?.(365);
                        found = true;
                        break;
                    }
                }
            }
            catch { /* ignore */ }
            closeWithSave(app, AC_FORM, formName, found ? AC_SAVE_YES : AC_SAVE_NO).then(() => resolve(found));
        })
            .catch(() => resolve(false));
    });
};
export const getFormSections = (app, formName) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve([]);
                return;
            }
            const sections = [];
            try {
                const f = form;
                for (let i = 0; i < 5; i++) {
                    try {
                        const sec = f.Section(i);
                        sections.push({
                            index: i,
                            name: String(sec.Name),
                            sectionType: SECTION_NAMES[i] ?? "unknown",
                            visible: Boolean(sec.Visible),
                            height: Number(sec.Height),
                        });
                    }
                    catch { /* skip missing section */ }
                }
            }
            catch { /* ignore */ }
            closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(sections));
        })
            .catch(() => resolve([]));
    });
};
// ---------------------------------------------------------------------------
// getFormSectionProperties — get all properties of a form section
// ---------------------------------------------------------------------------
export const getFormSectionProperties = (app, formName, sectionId) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve({});
                return;
            }
            try {
                const f = form;
                const sec = f.Section(sectionId);
                const props = enumProperties(sec);
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(props));
            }
            catch {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve({}));
            }
        })
            .catch(() => resolve({}));
    });
};
// ---------------------------------------------------------------------------
// setFormSectionProperty — set a single property of a form section
// ---------------------------------------------------------------------------
export const setFormSectionProperty = (app, formName, sectionId, propertyName, value) => {
    return new Promise((resolve) => {
        openFormDesign(app, formName)
            .then((form) => {
            if (!form) {
                resolve(false);
                return;
            }
            try {
                const f = form;
                const sec = f.Section(sectionId);
                sec.Properties(propertyName).Value = value;
                closeWithSave(app, AC_FORM, formName, AC_SAVE_YES).then(() => resolve(true));
            }
            catch {
                closeWithSave(app, AC_FORM, formName, AC_SAVE_NO).then(() => resolve(false));
            }
        })
            .catch(() => resolve(false));
    });
};
