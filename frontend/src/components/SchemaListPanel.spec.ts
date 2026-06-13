// Tests for SchemaListPanel.vue — the left pane of the unified explorer.
// Strict TDD: RED first. The component does not exist yet.
//
// Contract (from sdd/unified-schema-explorer/spec + design):
// - Shows a header, a search input, the table list, and the selected-table
//   detail area. All four are present on first render (spec: "First load
//   shows both panes" / "Loading state preserves layout").
// - Typing in the search input filters the list case-insensitively.
// - The count summary updates as the filter changes.
// - If the filter matches nothing, a no-match state echoes the query.
// - Clicking a table calls useSchemaExplorer().select(name).
// - When a table is selected, its fields render in the detail area.
// - When the detail fetch fails, an error state names the table.
// - The panel is read-only — no create/edit/delete affordances are rendered.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'

// Mock the apiClient module BEFORE importing the component so the component
// captures the mocked module's exports at script-setup time.
vi.mock('../api/apiClient', () => ({
  schemaApi: {
    getTables: vi.fn(),
    getTableSchema: vi.fn(),
  },
}))

// Mock the composable BEFORE importing the component. We expose a
// controllable Vue ref + setter so we can assert that clicking a table
// updates the shared selection. Vue's template auto-unwrap only works
// against a real ref, so the mock returns one (not a plain object).
const selectionSpy = vi.fn()
let selectedTableRef = ref<string | null>(null)
vi.mock('../composables/useSchemaExplorer', () => ({
  useSchemaExplorer: () => ({
    selectedTable: selectedTableRef,
    select: selectionSpy,
  }),
}))

import SchemaListPanel from './SchemaListPanel.vue'
import { schemaApi } from '../api/apiClient'

// --- Test data helpers ---

const tableA = { name: 'A', fields: [], record_count: 0 }
const tableB = { name: 'B', fields: [], record_count: 0 }
const tableCustomers = {
  name: 'Customers',
  fields: [
    { name: 'Id', type: 'Long Integer', size: 4, required: true, allow_zero_length: false },
    { name: 'Name', type: 'Text', size: 255, required: false, allow_zero_length: true },
  ],
  record_count: 42,
}

function tablesResponse(tables: Array<{ name: string }>) {
  return { success: true, tables, count: tables.length }
}

function tableSchemaResponse(table: unknown) {
  return { success: true, table }
}

function tableSchemaError(message: string) {
  return { success: false, error: message }
}

beforeEach(() => {
  // Use a fresh Vue ref per test so reactivity is real and the
  // component's template auto-unwrap works.
  selectedTableRef = ref<string | null>(null)
  selectionSpy.mockClear()
  vi.mocked(schemaApi.getTables).mockReset()
  vi.mocked(schemaApi.getTableSchema).mockReset()
  // Default the detail mock to a benign empty schema so tests that
  // don't care about the detail (e.g. aria-selected) don't trip the
  // "Query data cannot be undefined" warning.
  vi.mocked(schemaApi.getTableSchema).mockResolvedValue(
    tableSchemaResponse({ name: '', fields: [] }) as any,
  )
})

afterEach(() => {
  vi.restoreAllMocks()
})

// Helper: a tiny stand-in component that satisfies the Element-Plus
// el-input / el-button / el-tag surface used in the panel template. The
// panel uses these as plain presentational wrappers, so a real
// Element Plus mount would add noise. The el-input stub renders an actual
// <input> element so wrapper.find('input') and setValue() work. Other
// stubs return their slot content and forward attrs.
function makeStub(tag: string) {
  return defineComponent({
    name: tag,
    setup(_, { slots, attrs }) {
      return () => h(tag, attrs, slots.default ? slots.default() : [])
    },
  })
}

// Real <input> stub for el-input. Element Plus el-input normally wraps a
// real input element, so the stub mirrors that — exposing the underlying
// input for setValue and DOM queries. v-model is implemented by listening
// to the input event and emitting `update:modelValue`.
const ElInputStub = defineComponent({
  name: 'el-input',
  emits: ['update:modelValue'],
  props: ['modelValue', 'placeholder', 'clearable', 'ariaLabel'],
  setup(props, { emit, attrs }) {
    return () =>
      h('input', {
        type: 'text',
        placeholder: props.placeholder,
        value: props.modelValue,
        'aria-label': attrs['aria-label'] ?? props.ariaLabel,
        onInput: (e: Event) => {
          const target = e.target as HTMLInputElement
          emit('update:modelValue', target.value)
        },
      })
  },
})

const globalStubs = {
  'el-input': ElInputStub,
  'el-button': makeStub('el-button'),
  'el-tag': makeStub('el-tag'),
  'el-icon': makeStub('el-icon'),
}

async function mountPanel() {
  // Fresh QueryClient per mount so query state does not leak between tests.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const wrapper = mount(SchemaListPanel, {
    global: {
      stubs: globalStubs,
      plugins: [[VueQueryPlugin, { queryClient }]],
    },
  })
  await flushPromises()
  return wrapper
}

describe('SchemaListPanel.vue', () => {
  describe('first render layout', () => {
    it('renders the schema panel container', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(tablesResponse([tableA, tableB]) as any)
      const wrapper = await mountPanel()
      expect(wrapper.find('.schema-panel').exists()).toBe(true)
    })

    it('shows a search input that is present before data loads', async () => {
      // getTables is pending — flushPromises will not resolve until we mock
      // a value. We render without awaiting getTables resolution by
      // mocking a never-resolving promise; the layout should still render.
      vi.mocked(schemaApi.getTables).mockImplementation(
        () => new Promise(() => {}) as any,
      )
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      })
      const wrapper = mount(SchemaListPanel, {
        global: {
          stubs: globalStubs,
          plugins: [[VueQueryPlugin, { queryClient }]],
        },
      })
      // The search input must be in the DOM during loading (spec:
      // "Loading state preserves layout").
      expect(wrapper.find('input[type="text"], input:not([type])').exists()).toBe(true)
      // Header is present.
      expect(wrapper.text()).toContain('Schema')
    })

    it('does not render mutation controls (read-only contract)', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(tablesResponse([tableA]) as any)
      const wrapper = await mountPanel()
      // No element should advertise create / edit / delete / insert / remove
      const text = wrapper.text().toLowerCase()
      for (const forbidden of ['add table', 'create table', 'delete table', 'edit table', 'drop table']) {
        expect(text).not.toContain(forbidden)
      }
    })
  })

  describe('table list and search', () => {
    it('renders every table name returned by the API', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB, { name: 'Customers' }]) as any,
      )
      const wrapper = await mountPanel()
      const text = wrapper.text()
      expect(text).toContain('A')
      expect(text).toContain('B')
      expect(text).toContain('Customers')
    })

    it('shows the count summary reflecting the unfiltered list', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB, { name: 'Customers' }]) as any,
      )
      const wrapper = await mountPanel()
      // Format is "Showing N of M tables" — assert the M total and N shown
      expect(wrapper.text()).toMatch(/3\s*of\s*3/i)
    })

    it('filters the list as the user types (case-insensitive substring)', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB, { name: 'Customers' }, { name: 'Orders' }]) as any,
      )
      const wrapper = await mountPanel()
      const input = wrapper.find('input[type="text"], input:not([type])')
      await input.setValue('cus')
      const text = wrapper.text()
      expect(text).toContain('Customers')
      expect(text).not.toContain('Orders')
      // Count summary should now show 1 of 4
      expect(wrapper.text()).toMatch(/1\s*of\s*4/i)
    })

    it('is case-insensitive (uppercase query matches lowercase names)', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([{ name: 'customers' }, { name: 'orders' }]) as any,
      )
      const wrapper = await mountPanel()
      const input = wrapper.find('input[type="text"], input:not([type])')
      await input.setValue('CUSTOM')
      expect(wrapper.text()).toContain('customers')
      expect(wrapper.text()).not.toContain('orders')
    })

    it('shows a no-match state echoing the query when the filter is empty', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB]) as any,
      )
      const wrapper = await mountPanel()
      const input = wrapper.find('input[type="text"], input:not([type])')
      await input.setValue('zzz-no-such-table')
      const text = wrapper.text()
      expect(text.toLowerCase()).toContain('no')
      // Echo the query (spec: "echoing the query")
      expect(text).toContain('zzz-no-such-table')
    })

    it('clearing the search restores the full list', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB, { name: 'Customers' }]) as any,
      )
      const wrapper = await mountPanel()
      const input = wrapper.find('input[type="text"], input:not([type])')
      await input.setValue('Customers')
      expect(wrapper.text()).toMatch(/1\s*of\s*3/i)
      await input.setValue('')
      expect(wrapper.text()).toMatch(/3\s*of\s*3/i)
    })
  })

  describe('selection', () => {
    it('clicking a table calls useSchemaExplorer().select(name)', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB]) as any,
      )
      const wrapper = await mountPanel()
      // The panel renders each table as a clickable item. The first such
      // item is the first table (A). We click it.
      const items = wrapper.findAll('[data-test="table-item"]')
      expect(items.length).toBeGreaterThan(0)
      await items[0].trigger('click')
      expect(selectionSpy).toHaveBeenCalledWith('A')
    })

    it('clicking a different table updates the call to that table', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, { name: 'Customers' }]) as any,
      )
      const wrapper = await mountPanel()
      const items = wrapper.findAll('[data-test="table-item"]')
      await items[1].trigger('click')
      expect(selectionSpy).toHaveBeenCalledWith('Customers')
    })

    it('marks the selected table in the DOM via aria-selected', async () => {
      selectedTableRef = ref<string | null>('B')
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA, tableB]) as any,
      )
      const wrapper = await mountPanel()
      const items = wrapper.findAll('[data-test="table-item"]')
      // Item for B should be marked as the current selection.
      const b = items.find((i) => i.text().trim() === 'B')!
      expect(b.attributes('aria-selected')).toBe('true')
      const a = items.find((i) => i.text().trim() === 'A')!
      expect(a.attributes('aria-selected')).toBe('false')
    })
  })

  describe('detail area', () => {
    it('does not fetch detail until a table is selected', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([tableA]) as any,
      )
      vi.mocked(schemaApi.getTableSchema).mockResolvedValue(
        tableSchemaResponse(tableCustomers) as any,
      )
      await mountPanel()
      // Selection is null by default; detail fetch should not have fired.
      expect(vi.mocked(schemaApi.getTableSchema)).not.toHaveBeenCalled()
    })

    it('fetches detail when a table is selected and renders the field list', async () => {
      selectedTableRef = ref<string | null>('Customers')
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([{ name: 'Customers' }]) as any,
      )
      vi.mocked(schemaApi.getTableSchema).mockResolvedValue(
        tableSchemaResponse(tableCustomers) as any,
      )
      const wrapper = await mountPanel()
      // Wait for the detail query to resolve.
      await flushPromises()
      await flushPromises()
      expect(vi.mocked(schemaApi.getTableSchema)).toHaveBeenCalledWith('Customers')
      // Field names from the mock must be visible.
      const text = wrapper.text()
      expect(text).toContain('Id')
      expect(text).toContain('Name')
    })

    it('renders an error state naming the table on detail fetch failure', async () => {
      selectedTableRef = ref<string | null>('Customers')
      vi.mocked(schemaApi.getTables).mockResolvedValue(
        tablesResponse([{ name: 'Customers' }]) as any,
      )
      vi.mocked(schemaApi.getTableSchema).mockResolvedValue(
        tableSchemaError('boom') as any,
      )
      const wrapper = await mountPanel()
      await flushPromises()
      await flushPromises()
      const text = wrapper.text()
      // Spec: "the detail area MUST show an error state naming the table"
      expect(text).toContain('Customers')
      expect(text.toLowerCase()).toMatch(/error|failed|boom/)
    })

    it('does not render the detail area when no table is selected', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(tablesResponse([tableA]) as any)
      const wrapper = await mountPanel()
      // The detail area (fields list) should not be present.
      expect(wrapper.find('[data-test="detail-area"]').exists()).toBe(false)
    })
  })

  describe('empty state', () => {
    it('shows an empty state when the database has no tables', async () => {
      vi.mocked(schemaApi.getTables).mockResolvedValue(tablesResponse([]) as any)
      const wrapper = await mountPanel()
      const text = wrapper.text().toLowerCase()
      expect(text).toMatch(/no tables|empty/)
    })
  })
})
