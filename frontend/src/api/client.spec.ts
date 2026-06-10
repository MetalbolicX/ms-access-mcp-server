// Tests for the new schemaApi methods added in dashboard-refinement PR2.
// Verifies request bodies for getDatabaseStatistics and the four list* methods.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { schemaApi } from './client'

const API_BASE = 'http://localhost:8000'
const TOOL_CALL = `${API_BASE}/mcp/tools/call`

type FetchMock = ReturnType<typeof vi.fn>

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Internal Server Error',
    json: () => Promise.resolve(body),
  } as unknown as Response
}

describe('schemaApi (dashboard-refinement PR2)', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getDatabaseStatistics POSTs get_database_statistics to /mcp/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: true, objects: {}, file: {}, system: {} }),
    )

    await schemaApi.getDatabaseStatistics()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      TOOL_CALL,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'get_database_statistics',
          arguments: {},
        }),
      }),
    )
  })

  it('listForms POSTs get_forms to /mcp/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: true, items: ['Form1', 'Form2'], count: 2 }),
    )

    await schemaApi.listForms()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      TOOL_CALL,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'get_forms', arguments: {} }),
      }),
    )
  })

  it('listReports POSTs get_reports to /mcp/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: true, items: ['Report1'], count: 1 }),
    )

    await schemaApi.listReports()

    expect(fetchMock).toHaveBeenCalledWith(
      TOOL_CALL,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'get_reports', arguments: {} }),
      }),
    )
  })

  it('listMacros POSTs get_macros to /mcp/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: true, items: ['AutoExec'], count: 1 }),
    )

    await schemaApi.listMacros()

    expect(fetchMock).toHaveBeenCalledWith(
      TOOL_CALL,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'get_macros', arguments: {} }),
      }),
    )
  })

  it('listModules POSTs get_modules to /mcp/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: true, items: ['Module1'], count: 1 }),
    )

    await schemaApi.listModules()

    expect(fetchMock).toHaveBeenCalledWith(
      TOOL_CALL,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'get_modules', arguments: {} }),
      }),
    )
  })

  it('getDatabaseStatistics returns the parsed JSON response', async () => {
    const payload = {
      success: true,
      objects: {
        tables: 4,
        queries: 7,
        forms: 2,
        reports: 1,
        macros: 0,
        modules: 3,
      },
      file: {
        name: 'demo.accdb',
        size_bytes: 524288,
        modified: '2026-06-10T00:00:00Z',
      },
      system: {
        access_version: '16.0',
        com_available: true,
      },
    }
    fetchMock.mockResolvedValueOnce(jsonResponse(payload))

    const result = await schemaApi.getDatabaseStatistics()

    expect(result).toEqual(payload)
  })

  it('listForms returns the parsed JSON response', async () => {
    const payload = { success: true, items: ['LoginForm', 'EditForm'], count: 2 }
    fetchMock.mockResolvedValueOnce(jsonResponse(payload))

    const result = await schemaApi.listForms()

    expect(result).toEqual(payload)
  })
})
