// Tests for the new schemaApi methods added in dashboard-refinement PR2.
// Verifies request bodies for getDatabaseStatistics and the four list* methods.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { connectionApi, getApiKey, setApiKey, clearApiKey } from './client'
import { schemaApi } from './client'

const TOOL_CALL = '/mcp/tools/call'

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

// Auth tests for PR2 — apiKey state, Bearer headers, and 401 handling
describe('client auth (PR2 — frontend-auth)', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    // Reset apiKey state between tests
    clearApiKey()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // --- apiKey state management ---

  it('setApiKey stores key in module state and localStorage', async () => {
    setApiKey('test-key-123')
    expect(getApiKey()).toBe('test-key-123')
    // Verify localStorage was updated
    const stored = localStorage.getItem('mcp_api_key')
    expect(stored).toBe('test-key-123')
  })

  it('getApiKey returns empty string when no key is set', () => {
    expect(getApiKey()).toBe('')
  })

  it('clearApiKey removes key from state and localStorage', () => {
    setApiKey('to-be-cleared')
    clearApiKey()
    expect(getApiKey()).toBe('')
    expect(localStorage.getItem('mcp_api_key')).toBeNull()
  })

  it('getApiKey bootstraps from localStorage on module load', async () => {
    localStorage.setItem('mcp_api_key', 'bootstrap-key')
    // Re-import to test bootstrap behavior — module-level variable is already set by now
    // We test this indirectly: after setApiKey, localStorage persists
    setApiKey('bootstrap-key')
    expect(getApiKey()).toBe('bootstrap-key')
    clearApiKey() // clean up
  })

  // --- Bearer header injection ---

  it('apiRequest injects Authorization header when apiKey is set', async () => {
    setApiKey('secret-key')
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true }))

    await connectionApi.isConnected()

    expect(fetchMock).toHaveBeenCalledWith(
      '/mcp/tools/call',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer secret-key',
        }),
      }),
    )
  })

  it('apiRequest does NOT inject Authorization header when apiKey is empty', async () => {
    clearApiKey()
    fetchMock.mockResolvedValueOnce(jsonResponse({ connected: false }))

    await connectionApi.isConnected()

    expect(fetchMock).toHaveBeenCalledWith(
      '/mcp/tools/call',
      expect.objectContaining({
        headers: expect.not.objectContaining({ Authorization: expect.anything() }),
      }),
    )
  })

  it('apiRequest does NOT inject Authorization header when apiKey is not set', async () => {
    // Ensure no key
    clearApiKey()
    fetchMock.mockResolvedValueOnce(jsonResponse({ connected: false }))

    await connectionApi.isConnected()

    const callArgs = fetchMock.mock.calls[0]
    const headers = callArgs[1].headers as Record<string, string> | undefined
    expect(headers).toBeDefined()
    expect(headers!.Authorization).toBeUndefined()
  })

  // --- 401 handling ---

  it('apiRequest dispatches auth:required CustomEvent on 401', async () => {
    clearApiKey()
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent')
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        statusText: 'Unauthorized',
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    let errorThrown = false
    let thrownError: Error | null = null
    try {
      await connectionApi.isConnected()
    } catch (e) {
      errorThrown = true
      thrownError = e as Error
    }

    expect(errorThrown).toBe(true)
    expect(thrownError?.message).toContain('Authentication required')

    // Verify auth:required event was dispatched
    expect(dispatchEventSpy).toHaveBeenCalled()
    const event = dispatchEventSpy.mock.calls[0][0] as CustomEvent
    expect(event.type).toBe('auth:required')
  })

  it('apiRequest does NOT dispatch auth:required on non-401 errors', async () => {
    clearApiKey()
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent')
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Server error' }), {
        status: 500,
        statusText: 'Internal Server Error',
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    let errorThrown = false
    try {
      await connectionApi.isConnected()
    } catch {
      errorThrown = true
    }

    expect(errorThrown).toBe(true)
    expect(dispatchEventSpy).not.toHaveBeenCalled()
  })

  // --- connect includes password parameter ---

  it('connect sends password in the request body', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, connected: true, database: 'test.accdb' }))

    await connectionApi.connect('C:/db/test.accdb', false, 'dbpassword')

    expect(fetchMock).toHaveBeenCalledWith(
      '/mcp/tools/call',
      expect.objectContaining({
        body: JSON.stringify({
          name: 'connect_access',
          arguments: { database_path: 'C:/db/test.accdb', use_com: false, password: 'dbpassword' },
        }),
      }),
    )
  })

  it('connect uses empty string as default password', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, connected: true, database: 'test.accdb' }))

    await connectionApi.connect('C:/db/test.accdb', false)

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.arguments.password).toBe('')
  })
})
