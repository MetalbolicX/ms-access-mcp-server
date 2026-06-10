// Tests for DashboardView (dashboard-refinement PR3).
// Asserts: 4x2 stat grid render, failed-stats fallback, lazy detail fetch
// triggered by card click, and empty state for zero-count objects.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import ElementPlus from 'element-plus'
import DashboardView from './DashboardView.vue'
import { connectionApi, schemaApi } from '../api/client'

// Mock the API client module so useQuery resolves synchronously with our fixtures.
vi.mock('../api/client', () => ({
  connectionApi: {
    isConnected: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
  schemaApi: {
    getDatabaseStatistics: vi.fn(),
    getTables: vi.fn(),
    getQueries: vi.fn(),
    getRelationships: vi.fn(),
    listForms: vi.fn(),
    listReports: vi.fn(),
    listMacros: vi.fn(),
    listModules: vi.fn(),
  },
}))

const STATS_FIXTURE = {
  success: true,
  objects: {
    tables: 5,
    queries: 3,
    forms: 2,
    reports: 1,
    macros: 0,
    modules: 4,
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

function mountDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/er-diagram', component: { template: '<div />' } },
    ],
  })
  return mount(DashboardView, {
    global: {
      plugins: [
        [VueQueryPlugin, { queryClient }],
        router,
        ElementPlus,
      ],
    },
  })
}

function findStatCardByLabel(wrapper: ReturnType<typeof mountDashboard>, label: string) {
  const card = wrapper
    .findAll('.stat-card')
    .find((c) => c.text().includes(label))
  if (!card) throw new Error(`No stat card with label "${label}" found`)
  return card
}

describe('DashboardView — dashboard-refinement PR3', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(connectionApi.isConnected).mockResolvedValue({
      connected: true,
      database: 'demo.accdb',
    })
    vi.mocked(schemaApi.getDatabaseStatistics).mockResolvedValue(STATS_FIXTURE)
    vi.mocked(schemaApi.getRelationships).mockResolvedValue({
      success: true,
      relationships: [],
      count: 0,
    })
    vi.mocked(schemaApi.getTables).mockResolvedValue({
      success: true,
      tables: [],
      count: 0,
    })
    vi.mocked(schemaApi.getQueries).mockResolvedValue({
      success: true,
      queries: [],
      count: 0,
    })
    vi.mocked(schemaApi.listForms).mockResolvedValue({
      success: true,
      items: [],
      count: 0,
    })
    vi.mocked(schemaApi.listReports).mockResolvedValue({
      success: true,
      items: [],
      count: 0,
    })
    vi.mocked(schemaApi.listMacros).mockResolvedValue({
      success: true,
      items: [],
      count: 0,
    })
    vi.mocked(schemaApi.listModules).mockResolvedValue({
      success: true,
      items: [],
      count: 0,
    })
  })

  describe('4x2 stat grid', () => {
    it('renders exactly 8 stat cards when connected and stats load', async () => {
      const wrapper = mountDashboard()
      await flushPromises()

      const cards = wrapper.findAll('.stat-card')
      expect(cards).toHaveLength(8)
    })

    it('shows fallback zeros for the 6 clickable stat cards when stats fail', async () => {
      vi.mocked(schemaApi.getDatabaseStatistics).mockRejectedValue(
        new Error('boom'),
      )
      const wrapper = mountDashboard()
      await flushPromises()

      const statGrid = wrapper.find('.stats-grid')
      const statCards = statGrid.findAll('.stat-card')
      // Grid is still 4x2 even when stats fail
      expect(statCards).toHaveLength(8)
      // The 6 clickable object-count cards should each fall back to 0.
      // The 2 info cards (DB Size / Access Version) use the same ??0 default,
      // but the clickable ones are the first 6 by design.
      for (let i = 0; i < 6; i++) {
        expect(statCards[i].find('.stat-value').text()).toBe('0')
      }
    })
  })

  describe('toggleDetail lazy fetch', () => {
    it('does not call getTables until the tables card is clicked', async () => {
      const wrapper = mountDashboard()
      await flushPromises()

      // Lazy: enabled only when activeListType === 'tables'
      expect(schemaApi.getTables).not.toHaveBeenCalled()

      const tablesCard = findStatCardByLabel(wrapper, 'Tables')
      await tablesCard.trigger('click')
      await flushPromises()

      expect(schemaApi.getTables).toHaveBeenCalledTimes(1)
    })

    it('opens and closes the detail panel on repeated card clicks', async () => {
      const wrapper = mountDashboard()
      await flushPromises()

      const tablesCard = findStatCardByLabel(wrapper, 'Tables')
      // First click: open
      await tablesCard.trigger('click')
      await flushPromises()
      expect(wrapper.find('.object-list-panel').exists()).toBe(true)

      // Second click: close
      await tablesCard.trigger('click')
      await flushPromises()
      expect(wrapper.find('.object-list-panel').exists()).toBe(false)
    })

    it('renders el-empty for an object type with zero items', async () => {
      // macros is 0 in the fixture
      const wrapper = mountDashboard()
      await flushPromises()

      const macrosCard = findStatCardByLabel(wrapper, 'Macros')
      await macrosCard.trigger('click')
      await flushPromises()

      expect(wrapper.find('.el-empty').exists()).toBe(true)
    })
  })
})
