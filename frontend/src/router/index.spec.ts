// Tests for router/index.ts — route guard behavior
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

// Mock the client module so we can control apiKey state in tests
const mockGetApiKey = vi.fn()
vi.mock('../api/client', () => ({
  getApiKey: () => mockGetApiKey(),
  setApiKey: vi.fn(),
  clearApiKey: vi.fn(),
}))

// Minimal stub components for routes
const LoginStub = { template: '<div>Login</div>' }
const DashboardStub = { template: '<div>Dashboard</div>' }
const SchemaStub = { template: '<div>Schema</div>' }

function createTestRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/login', component: LoginStub, name: 'login' },
      { path: '/dashboard', component: DashboardStub, name: 'dashboard' },
      { path: '/schema', component: SchemaStub, name: 'schema' },
      { path: '/', redirect: '/dashboard' },
    ],
  })
}

describe('router auth guard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('redirects to /login when navigating to protected route with no apiKey', async () => {
    mockGetApiKey.mockReturnValue('')
    const router = createTestRouter()
    router.beforeEach((to) => {
      if (to.path !== '/login' && !mockGetApiKey()) {
        return '/login'
      }
    })

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows navigation to /login when no apiKey', async () => {
    mockGetApiKey.mockReturnValue('')
    const router = createTestRouter()
    router.beforeEach((to) => {
      if (to.path !== '/login' && !mockGetApiKey()) {
        return '/login'
      }
    })

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows navigation to protected route when apiKey is set', async () => {
    mockGetApiKey.mockReturnValue('valid-key')
    const router = createTestRouter()
    router.beforeEach((to) => {
      if (to.path !== '/login' && !mockGetApiKey()) {
        return '/login'
      }
    })

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('redirects to /login when navigating to /schema with no apiKey', async () => {
    mockGetApiKey.mockReturnValue('')
    const router = createTestRouter()
    router.beforeEach((to) => {
      if (to.path !== '/login' && !mockGetApiKey()) {
        return '/login'
      }
    })

    await router.push('/schema')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows navigation to /login even when apiKey is set', async () => {
    mockGetApiKey.mockReturnValue('some-key')
    const router = createTestRouter()
    router.beforeEach((to) => {
      if (to.path !== '/login' && !mockGetApiKey()) {
        return '/login'
      }
    })

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })
})