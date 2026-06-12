// Tests for apiClient — replaces client.ts with cookie-based auth (no localStorage).
// Strict TDD: RED first — these tests describe the cookie-auth behavior that does not exist yet.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

type FetchMock = ReturnType<typeof vi.fn>

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return {
    ok: init?.status === undefined || init!.status >= 200 && init!.status < 300,
    status: init?.status ?? 200,
    statusText: init?.statusText ?? 'OK',
    json: () => Promise.resolve(body),
    headers: new Headers(init?.headers ?? {}),
  } as unknown as Response
}

describe('apiClient cookie-based auth', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // --- Login flow ---

  it('login POSTs api_key to /api/login with credentials: include', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    // Dynamically import so module-level state is fresh per test
    const { loginApi } = await import('./apiClient')
    await loginApi.login('test-api-key')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/login',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: 'test-api-key' }),
        credentials: 'include',
      }),
    )
  })

  it('login returns { success: true } on valid key', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const { loginApi } = await import('./apiClient')
    const result = await loginApi.login('valid-key')
    expect(result).toEqual({ success: true })
  })

  it('login throws error with message on invalid key (401)', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Invalid API key' }), {
        status: 401,
        statusText: 'Unauthorized',
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const { loginApi } = await import('./apiClient')
    await expect(loginApi.login('bad-key')).rejects.toThrow('Invalid API key')
  })

  it('login throws error on rate-limited request (429)', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Too many requests' }), {
        status: 429,
        statusText: 'Too Many Requests',
        headers: { 'Content-Type': 'application/json', 'Retry-After': '60' },
      }),
    )

    const { loginApi } = await import('./apiClient')
    await expect(loginApi.login('any-key')).rejects.toThrow('Too many requests')
  })

  it('login throws generic error on network failure', async () => {
    fetchMock.mockRejectedValueOnce(new Error('Network failure'))

    const { loginApi } = await import('./apiClient')
    await expect(loginApi.login('any-key')).rejects.toThrow('Network failure')
  })

  // --- Logout flow ---

  it('logout POSTs to /api/logout with credentials: include', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const { loginApi } = await import('./apiClient')
    await loginApi.logout()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/logout',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
      }),
    )
  })

  it('logout returns { success: true } on success', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), { status: 200 }),
    )

    const { loginApi } = await import('./apiClient')
    const result = await loginApi.logout()
    expect(result).toEqual({ success: true })
  })

  // --- Tool call proxy (cookie-auth, no Bearer needed) ---

  it('toolsApi.call proxies to /api/tools/call with credentials: include', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, result: {} }), { status: 200 }),
    )

    const { toolsApi } = await import('./apiClient')
    await toolsApi.call('get_tables', {})

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'get_tables', arguments: {} }),
        credentials: 'include',
      }),
    )
  })

  it('toolsApi.call does NOT inject Authorization header (cookie auth only)', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), { status: 200 }),
    )

    const { toolsApi } = await import('./apiClient')
    await toolsApi.call('get_tables', {})

    const callArgs = fetchMock.mock.calls[0]
    const headers = callArgs[1].headers as Record<string, string>
    expect(headers).not.toHaveProperty('Authorization')
  })

  it('toolsApi.call returns parsed JSON response', async () => {
    const payload = { success: true, tables: [{ name: 'Customers' }], count: 1 }
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const { toolsApi } = await import('./apiClient')
    const result = await toolsApi.call('get_tables', {})
    expect(result).toEqual(payload)
  })

  it('toolsApi.call throws on 401 and redirects to /login', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 }),
    )

    const { toolsApi } = await import('./apiClient')
    // Spy on window.location.href
    const locationSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({ href: 'http://localhost/dashboard' } as Location)

    await expect(toolsApi.call('get_tables', {})).rejects.toThrow('Unauthorized')
    expect(window.location.href).toBe('/login')
    locationSpy.mockRestore()
  })

  it('toolsApi.call throws on 403 read-only mode', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Server is in read-only mode' }), { status: 403 }),
    )

    const { toolsApi } = await import('./apiClient')
    await expect(toolsApi.call('delete_table', {})).rejects.toThrow('Server is in read-only mode')
  })

  it('toolsApi.call throws on non-OK response with error message', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Internal server error' }), { status: 500 }),
    )

    const { toolsApi } = await import('./apiClient')
    await expect(toolsApi.call('get_tables', {})).rejects.toThrow('Internal server error')
  })
})

describe('apiClient connectionApi (cookie-auth proxy)', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('connect calls /api/tools/call with connect_access via toolsApi', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, connected: true, database: 'test.accdb' }), { status: 200 }),
    )

    const { connectionApi } = await import('./apiClient')
    const result = await connectionApi.connect('C:/db/test.accdb', false, 'pw')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          name: 'connect_access',
          arguments: { database_path: 'C:/db/test.accdb', use_com: false, password: 'pw' },
        }),
        credentials: 'include',
      }),
    )
    expect(result.connected).toBe(true)
  })

  it('isConnected calls /api/tools/call with is_connected', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ connected: true, database: 'test.accdb' }), { status: 200 }),
    )

    const { connectionApi } = await import('./apiClient')
    const result = await connectionApi.isConnected()
    expect(result.connected).toBe(true)
  })

  it('disconnect calls /api/tools/call with disconnect_access', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, message: 'Disconnected' }), { status: 200 }),
    )

    const { connectionApi } = await import('./apiClient')
    await connectionApi.disconnect()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'disconnect_access', arguments: {} }),
      }),
    )
  })
})

describe('apiClient schemaApi (cookie-auth proxy)', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getTables calls get_tables via /api/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, tables: [], count: 0 }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    const result = await schemaApi.getTables()
    expect(result.success).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_tables', arguments: {} }),
      }),
    )
  })

  it('getTableSchema calls get_table_schema with table_name', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, table: { name: 'Customers', fields: [] } }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.getTableSchema('Customers')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_table_schema', arguments: { table_name: 'Customers' } }),
      }),
    )
  })

  it('getRelationships calls get_relationships', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, relationships: [], count: 0 }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.getRelationships()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_relationships', arguments: {} }),
      }),
    )
  })

  it('getDatabaseStatistics calls get_database_statistics', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, objects: {}, file: {}, system: {} }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.getDatabaseStatistics()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_database_statistics', arguments: {} }),
      }),
    )
  })

  it('listForms calls get_forms', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, items: [], count: 0 }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.listForms()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_forms', arguments: {} }),
      }),
    )
  })

  it('listReports calls get_reports', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, items: [], count: 0 }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.listReports()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_reports', arguments: {} }),
      }),
    )
  })

  it('listMacros calls get_macros', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, items: [], count: 0 }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.listMacros()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_macros', arguments: {} }),
      }),
    )
  })

  it('listModules calls get_modules', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, items: [], count: 0 }), { status: 200 }),
    )

    const { schemaApi } = await import('./apiClient')
    await schemaApi.listModules()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_modules', arguments: {} }),
      }),
    )
  })
})

describe('apiClient jobsApi (cookie-auth proxy)', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getJobs calls list_jobs via /api/tools/call', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, jobs: [] }), { status: 200 }),
    )

    const { jobsApi } = await import('./apiClient')
    const result = await jobsApi.getJobs()
    expect(result.success).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'list_jobs', arguments: {} }),
      }),
    )
  })

  it('getJobStatus calls get_migration_status with job_id', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, job: { id: 'job-1', status: 'running' } }), { status: 200 }),
    )

    const { jobsApi } = await import('./apiClient')
    await jobsApi.getJobStatus('job-1')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_migration_status', arguments: { job_id: 'job-1' } }),
      }),
    )
  })
})
