// Tests for the split-layout branch of ErDiagramView.vue introduced by
// the unified-schema-explorer change (PR2 + PR3).
//
// What this slice lands (PR2):
//   - The view now renders a two-pane shell: left = <SchemaListPanel>,
//     right = <VueFlow>. The diagram-side selection sync is PR3.
//   - The view's data path is apiClient (cookie auth) — schemaApi is
//     imported from '../api/apiClient', not '../api/client'.
//
// What this slice lands (PR3):
//   - Wiring @node-click on VueFlow → useSchemaExplorer().select(node.id).
//   - Watching selectedTable to (a) highlight the corresponding Vue Flow
//     node with the `is-selected` class and (b) call fitView({ nodes: [id] })
//     to auto-pan the diagram to the selection.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'

// --- Module mocks (declared before any component imports) ---

// Mock apiClient so the view can render without a network.
vi.mock('../api/apiClient', () => ({
  schemaApi: {
    getErDiagram: vi.fn(),
    getTables: vi.fn(),
  },
}))

// Spy on fitView so the PR3 watch assertion can check it was called.
const fitViewSpy = vi.fn()
vi.mock('@vue-flow/core', () => ({
  VueFlow: () => null,
  useVueFlow: () => ({
    fitView: fitViewSpy,
    setNodes: vi.fn(),
    setEdges: vi.fn(),
    fitViewOnInit: vi.fn(),
  }),
}))

// Mock the composable so the view does not import a real one in tests.
// We expose a controllable Vue ref + setter so the test can mutate
// selectedTable and observe the view's watch response. Vue's template
// auto-unwrap only works against a real ref, so the mock returns one
// (not a plain object).
const selectionSpy = vi.fn()
let selectedTableRef = ref<string | null>(null)
vi.mock('../composables/useSchemaExplorer', () => ({
  useSchemaExplorer: () => ({
    selectedTable: selectedTableRef,
    select: selectionSpy,
  }),
}))

// --- Stubs for child components ---

// Stub the SchemaListPanel — we test the shell, not the panel again here.
const SchemaListPanelStub = defineComponent({
  name: 'SchemaListPanel',
  setup() {
    return () => h('aside', { 'data-test': 'schema-list-panel-stub' }, 'SchemaListPanel stub')
  },
})

// Stub VueFlow as a div so we can assert it renders in the right pane
// without pulling in the @vue-flow runtime. The stub forwards any
// emitted events from a test-only button so PR3's @node-click handler
// can be exercised in isolation.
const VueFlowStub = defineComponent({
  name: 'VueFlow',
  emits: ['nodeClick', 'node-click'],
  setup(_, { slots, emit }) {
    return () =>
      h(
        'div',
        { 'data-test': 'vue-flow-stub' },
        [
          // Test handle: a button that emits a nodeClick for table "A".
          // The test can call this.trigger('click') to simulate a user
          // clicking a diagram node.
          h(
            'button',
            {
              'data-test': 'emit-node-click-A',
              onClick: () =>
                emit('nodeClick', { node: { id: 'A' }, event: new MouseEvent('click') }),
            },
            'emit-node-click-A',
          ),
          h(
            'button',
            {
              'data-test': 'emit-node-click-B',
              onClick: () =>
                emit('nodeClick', { node: { id: 'B' }, event: new MouseEvent('click') }),
            },
            'emit-node-click-B',
          ),
          slots.default ? slots.default() : [],
        ],
      )
  },
})

const MiniMapStub = defineComponent({
  name: 'MiniMap',
  setup() {
    return () => h('div', { 'data-test': 'mini-map-stub' })
  },
})

const ControlsStub = defineComponent({
  name: 'Controls',
  setup() {
    return () => h('div', { 'data-test': 'controls-stub' })
  },
})

import ErDiagramView from './ErDiagramView.vue'
import { schemaApi } from '../api/apiClient'

beforeEach(() => {
  fitViewSpy.mockReset()
  selectionSpy.mockReset()
  selectedTableRef = ref<string | null>(null)
  vi.mocked(schemaApi.getErDiagram).mockReset()
  vi.mocked(schemaApi.getTables).mockReset()
  // Default the diagram query to a graph with one node so the right
  // pane renders the VueFlow branch (not the empty branch).
  vi.mocked(schemaApi.getErDiagram).mockResolvedValue({
    success: true,
    nodes: [
      {
        id: 'A',
        type: 'table',
        data: { label: 'A', columns: [], record_count: 0 },
      },
    ],
    edges: [],
    node_count: 1,
    edge_count: 0,
  } as any)
  vi.mocked(schemaApi.getTables).mockResolvedValue({
    success: true,
    tables: [{ name: 'A', fields: [], record_count: 0 }],
    count: 1,
  } as any)
})

afterEach(() => {
  vi.restoreAllMocks()
})

function mountView() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return mount(ErDiagramView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      // Stubs replace child components resolved by name. Using
      // `global.stubs` (not `global.components`) is what allows us to
      // intercept the imports inside the view's <script setup>.
      stubs: {
        SchemaListPanel: SchemaListPanelStub,
        VueFlow: VueFlowStub,
        MiniMap: MiniMapStub,
        Controls: ControlsStub,
      },
    },
  })
}

describe('ErDiagramView split layout (PR2)', () => {
  it('renders the unified-explorer container', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.unified-explorer, .er-diagram-view').exists()).toBe(true)
  })

  it('renders the SchemaListPanel in the left pane', async () => {
    const wrapper = mountView()
    await flushPromises()
    // The stub renders <aside data-test="schema-list-panel-stub">; the
    // view should mount it.
    expect(wrapper.find('[data-test="schema-list-panel-stub"]').exists()).toBe(true)
  })

  it('renders the VueFlow diagram in the right pane', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-test="vue-flow-stub"]').exists()).toBe(true)
  })

  it('keeps the header visible alongside the panes', async () => {
    const wrapper = mountView()
    await flushPromises()
    // Header must contain the unified-explorer title.
    const headerText = wrapper.find('header, .diagram-header, .unified-header').text()
    expect(headerText.toLowerCase()).toMatch(/schema|er|explorer/)
  })

  it('imports the data path from apiClient (cookie auth) and not from client', async () => {
    // This is a static contract test: ErDiagramView.vue must import
    // schemaApi from '../api/apiClient' and never from '../api/client'.
    // We re-read the file at runtime to assert the import.
    const fs = await import('fs')
    const path = await import('path')
    const filePath = path.join(__dirname, 'ErDiagramView.vue')
    const source = fs.readFileSync(filePath, 'utf-8')
    // Must reference the apiClient module path
    expect(source).toContain("from '../api/apiClient'")
    // Must not import from the legacy client (which uses localStorage)
    expect(source).not.toContain("from '../api/client'")
  })

  it('uses the shared schemaApi.getErDiagram query (does not define a second one)', async () => {
    // Re-confirms the data-path contract: the view calls schemaApi
    // (imported from apiClient) to load the ER graph. If the view
    // bypassed apiClient, getErDiagram would never be invoked.
    const wrapper = mountView()
    await flushPromises()
    expect(vi.mocked(schemaApi.getErDiagram)).toHaveBeenCalled()
  })
})

describe('ErDiagramView selection sync (PR3)', () => {
  // --- Task 1.4: @node-click → useSchemaExplorer().select(node.id) ---

  it('calls useSchemaExplorer().select(node.id) when a VueFlow node is clicked', async () => {
    const wrapper = mountView()
    await flushPromises()
    // The stub exposes a button that emits nodeClick with { node: { id: 'A' } }.
    await wrapper.find('[data-test="emit-node-click-A"]').trigger('click')
    expect(selectionSpy).toHaveBeenCalledWith('A')
  })

  it('forwards the clicked node id (not the event payload) to select()', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('[data-test="emit-node-click-B"]').trigger('click')
    // The second call should carry the second node's id, not 'A' or a
    // payload object.
    expect(selectionSpy).toHaveBeenLastCalledWith('B')
  })

  // --- Task 2.4: watch(selectedTable) → fitView + node highlight ---

  it('calls fitView({ nodes: [id], padding }) when selectedTable becomes a non-null value', async () => {
    const wrapper = mountView()
    await flushPromises()
    // Reset the spy to clear the initial fitView-on-mount call (the
    // existing watch on `data` calls fitView({ padding: 0.2 }) once
    // after the diagram loads). We only care about the PR3 watch's
    // call here.
    fitViewSpy.mockClear()

    selectedTableRef.value = 'A'
    await flushPromises()
    // The PR3 watcher schedules fitView through setTimeout(..., 50)
    // to give Vue Flow a chance to re-render with the new class.
    await new Promise((r) => setTimeout(r, 80))
    await flushPromises()

    const calls = fitViewSpy.mock.calls
    const sawNodeFit = calls.some(
      (args) =>
        args[0] &&
        Array.isArray(args[0].nodes) &&
        args[0].nodes.includes('A') &&
        typeof args[0].padding === 'number',
    )
    expect(sawNodeFit).toBe(true)
  })

  it('applies the is-selected class to the matching Vue Flow node when selectedTable changes', async () => {
    // Use a graph with two nodes so the assertion is meaningful.
    vi.mocked(schemaApi.getErDiagram).mockResolvedValue({
      success: true,
      nodes: [
        { id: 'A', type: 'table', data: { label: 'A', columns: [], record_count: 0 } },
        { id: 'B', type: 'table', data: { label: 'B', columns: [], record_count: 0 } },
      ],
      edges: [],
      node_count: 2,
      edge_count: 0,
    } as any)

    const wrapper = mountView()
    await flushPromises()

    // Before selection: no node carries the is-selected class.
    let nodes = (wrapper.vm as any).nodes as Array<{ id: string; class?: string | string[] }>
    expect(nodes.every((n) => !nodeHasIsSelected(n))).toBe(true)

    // Select A.
    selectedTableRef.value = 'A'
    await flushPromises()

    nodes = (wrapper.vm as any).nodes as Array<{ id: string; class?: string | string[] }>
    const a = nodes.find((n) => n.id === 'A')!
    const b = nodes.find((n) => n.id === 'B')!
    expect(nodeHasIsSelected(a)).toBe(true)
    expect(nodeHasIsSelected(b)).toBe(false)
  })

  it('clears the is-selected class when selectedTable becomes null', async () => {
    vi.mocked(schemaApi.getErDiagram).mockResolvedValue({
      success: true,
      nodes: [
        { id: 'A', type: 'table', data: { label: 'A', columns: [], record_count: 0 } },
      ],
      edges: [],
      node_count: 1,
      edge_count: 0,
    } as any)

    selectedTableRef = ref<string | null>('A')
    const wrapper = mountView()
    await flushPromises()

    let nodes = (wrapper.vm as any).nodes as Array<{ id: string; class?: string | string[] }>
    expect(nodeHasIsSelected(nodes[0])).toBe(true)

    // Clear selection.
    selectedTableRef.value = null
    await flushPromises()

    nodes = (wrapper.vm as any).nodes as Array<{ id: string; class?: string | string[] }>
    expect(nodeHasIsSelected(nodes[0])).toBe(false)
  })
})

// Vue Flow nodes may carry their `class` as a string, a string[], or
// an object map. Accept all three shapes for the assertion.
function nodeHasIsSelected(n: { class?: string | string[] | Record<string, unknown> }): boolean {
  const c = n.class
  if (typeof c === 'string') return c.split(/\s+/).includes('is-selected')
  if (Array.isArray(c)) return c.includes('is-selected')
  if (c && typeof c === 'object') return Boolean((c as Record<string, unknown>)['is-selected'])
  return false
}
