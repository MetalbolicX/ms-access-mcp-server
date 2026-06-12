// Tests for Alpine dashboard page behavior.
// Verifies connection status loading, stats display, and 401 logout redirects.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const ORIGINAL_LOCATION = window.location

function mockLocation(href: string) {
  Object.defineProperty(window, 'location', {
    value: { href },
    writable: true,
    configurable: true,
  })
}

function restoreLocation() {
  Object.defineProperty(window, 'location', {
    value: ORIGINAL_LOCATION,
    writable: true,
    configurable: true,
  })
}

describe('dashboard page Alpine behavior', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockLocation('http://localhost/dashboard')
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    restoreLocation()
    vi.unstubAllGlobals()
  })

  it('loadConnectionStatus() calls /api/tools/call with is_connected', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ connected: true, database: 'test.accdb' }), { status: 200 }),
    )

    const { loadConnectionStatus } = await import('../pages/dashboard')
    const result = await loadConnectionStatus()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'is_connected', arguments: {} }),
        credentials: 'include',
      }),
    )
    expect(result.connected).toBe(true)
  })

  it('loadConnectionStatus() redirects to /login on 401', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 }),
    )

    const { loadConnectionStatus } = await import('../pages/dashboard')
    await expect(loadConnectionStatus()).rejects.toThrow('Unauthorized')
    expect(window.location.href).toBe('/login')
  })

  it('loadStats() calls /api/tools/call with get_database_statistics', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({
        success: true,
        objects: { tables: 4, queries: 7, forms: 2, reports: 1, macros: 0, modules: 3 },
        file: { name: 'demo.accdb', size_bytes: 524288, modified: '2026-06-10' },
        system: { access_version: '16.0', com_available: true },
      }), { status: 200 }),
    )

    const { loadStats } = await import('../pages/dashboard')
    const result = await loadStats()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_database_statistics', arguments: {} }),
      }),
    )
    expect(result.objects.tables).toBe(4)
  })

 it('loadStats() redirects to /login on 401', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 }),
    )

    const { loadStats } = await import('../pages/dashboard')
    await expect(loadStats()).rejects.toThrow('Unauthorized')
    expect(window.location.href).toBe('/login')
  })

  it('connectDatabase() calls /api/tools/call with connect_access', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, connected: true, database: 'test.accdb' }), { status: 200 }),
    )

    const { connectDatabase } = await import('../pages/dashboard')
    const result = await connectDatabase('C:/db/test.accdb', false, '')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({
          name: 'connect_access',
          arguments: { database_path: 'C:/db/test.accdb', use_com: false, password: '' },
        }),
      }),
    )
    expect(result.connected).toBe(true)
  })

  it('disconnectDatabase() calls /api/tools/call with disconnect_access', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, message: 'Disconnected' }), { status: 200 }),
    )

    const { disconnectDatabase } = await import('../pages/dashboard')
    await disconnectDatabase()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'disconnect_access', arguments: {} }),
      }),
    )
  })

  it('loadRelationships() calls /api/tools/call with get_relationships', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, relationships: [], count: 0 }), { status: 200 }),
    )

    const { loadRelationships } = await import('../pages/dashboard')
    await loadRelationships()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_relationships', arguments: {} }),
      }),
    )
  })

  it('loadTables() calls /api/tools/call with get_tables', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, tables: [], count: 0 }), { status: 200 }),
    )

    const { loadTables } = await import('../pages/dashboard')
    await loadTables()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_tables', arguments: {} }),
      }),
    )
  })

  it('loadQueries() calls /api/tools/call with get_queries', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true, queries: [], count: 0 }), { status: 200 }),
    )

    const { loadQueries } = await import('../pages/dashboard')
    await loadQueries()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        body: JSON.stringify({ name: 'get_queries', arguments: {} }),
      }),
    )
  })
})
