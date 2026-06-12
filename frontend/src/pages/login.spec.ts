// Tests for Alpine login page behavior.
// Verifies cookie auth, login error rendering, and 401 logout redirects.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock window.location for redirect tests
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

describe('login page Alpine behavior', () => {
  beforeEach(() => {
    mockLocation('http://localhost/login')
  })

  afterEach(() => {
    restoreLocation()
    vi.unstubAllGlobals()
  })

  it('login() POSTs to /api/login with credentials and redirects to /dashboard on success', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { login } = await import('../pages/login')
    await login('test-api-key')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/login',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: 'test-api-key' }),
        credentials: 'include',
      }),
    )
    expect(window.location.href).toBe('/dashboard')
  })

  it('login() sets error state on401 invalid key', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Invalid API key' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { login } = await import('../pages/login')
    const error = await login('bad-key')
    expect(error).toBe('Invalid API key')
  })

  it('login() sets error state on 429 rate limit', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Too many requests' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', 'Retry-After': '60' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { login } = await import('../pages/login')
    const error = await login('any-key')
    expect(error).toBe('Too many requests — please wait before trying again')
  })

  it('login() sets error state on network failure', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('Network failure'))
    vi.stubGlobal('fetch', fetchMock)

    const { login } = await import('../pages/login')
    const error = await login('any-key')
    expect(error).toBe('Connection error — could not reach the server')
  })

  it('login() sets error state on non-401 server error', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Server error' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { login } = await import('../pages/login')
    const error = await login('any-key')
    expect(error).toBe('Server error')
  })
})
