// Tests for Alpine schema explorer page behavior.
// Verifies table loading, table selection, and 401 logout redirects.
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

describe('schema page Alpine behavior', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockLocation('http://localhost/schema')
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    restoreLocation()
    vi.unstubAllGlobals()
  })

  it('loadTables() calls /api/tools/call with get_tables', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({
        success: true,
        tables: [
          { name: 'Customers', fields: [], record_count: 150 },
          { name: 'Orders', fields: [], record_count: 430 },
        ],
        count: 2,
      }), { status: 200 }),
    )

    const { loadTables } = await import('../pages/schema')
    const result = await loadTables()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'get_tables', arguments: {} }),
        credentials: 'include',
      }),
    )
    expect(result.tables).toHaveLength(2)
    expect(result.tables[0].name).toBe('Customers')
  })

  it('loadTables() redirects to /login on 401', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 }),
    )

    const { loadTables } = await import('../pages/schema')
    await expect(loadTables()).rejects.toThrow('Unauthorized')
    expect(window.location.href).toBe('/login')
  })

  it('loadTableSchema() calls /api/tools/call with get_table_schema and table_name', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({
        success: true,
        table: {
          name: 'Customers',
          fields: [
            { name: 'ID', type: 'LongInteger', size: 4, required: true, allow_zero_length: false },
            { name: 'Name', type: 'Text', size: 100, required: false, allow_zero_length: true },
          ],
          record_count: 150,
        },
      }), { status: 200 }),
    )

    const { loadTableSchema } = await import('../pages/schema')
    const result = await loadTableSchema('Customers')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/tools/call',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'get_table_schema', arguments: { table_name: 'Customers' } }),
 }),
    )
    expect(result.table?.name).toBe('Customers')
    expect(result.table?.fields).toHaveLength(2)
  })

  it('loadTableSchema() redirects to /login on 401', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 }),
    )

    const { loadTableSchema } = await import('../pages/schema')
    await expect(loadTableSchema('Customers')).rejects.toThrow('Unauthorized')
    expect(window.location.href).toBe('/login')
  })

  it('loadTableSchema() throws on non-OK response', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: false, error: 'Table not found' }), { status: 400 }),
    )

    const { loadTableSchema } = await import('../pages/schema')
    await expect(loadTableSchema('NonExistent')).rejects.toThrow('Table not found')
  })
})
