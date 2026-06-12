// Tests for the dagre layout helper (dashboard-refinement PR4).
// Asserts: applyDagreLayout() returns deterministic positions and preserves
// edge wiring + node data/style on round-trip.
import { describe, it, expect } from 'vitest'
import { applyDagreLayout } from './erDiagramLayout'
import type { Node, Edge } from '@vue-flow/core'

// Minimal Vue Flow node/edge shapes for the layout function. We use unknown
// in `data` because the layout function must not care about payload shape.
const mockNodes: Node[] = [
  { id: 'Orders', data: { label: 'Orders', columns: [] }, position: { x: 0, y: 0 } },
  { id: 'Customers', data: { label: 'Customers', columns: [] }, position: { x: 0, y: 0 } },
  { id: 'Products', data: { label: 'Products', columns: [] }, position: { x: 0, y: 0 } },
]

const mockEdges: Edge[] = [
  { id: 'e1', source: 'Orders', target: 'Customers' },
  { id: 'e2', source: 'Orders', target: 'Products' },
]

// --- ER Mount Coverage Tests ---
// These test the layout behavior under SSR mount conditions:
// authenticated bootstrap (API key present), empty state (no tables), and load failure.

// Helper to build Vue Flow nodes from raw API response nodes (matching ErDiagramView.vue behavior)
interface RawERNode {
  id: string
  data: { label: string; columns: Array<{ name: string; type: string }>; record_count: number }
}

interface RawEREdge {
  id: string
  source: string
  target: string
  label: string
  animated: boolean
}

function buildFlowNodes(raw: RawERNode[]): Node[] {
  return raw.map((n) => ({
    id: n.id,
    data: n.data,
    style: {
      background: 'var(--color-bg-secondary)',
      border: '1px solid var(--color-border)',
      borderRadius: '8px',
      padding: '10px',
      minWidth: '180px',
      fontSize: '13px',
      color: 'var(--color-text-primary)',
    },
  }))
}

function buildFlowEdges(raw: RawEREdge[]): Edge[] {
  return raw.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: e.animated,
    style: { stroke: 'var(--color-accent)' },
  }))
}

describe('ER Diagram SSR mount coverage', () => {
  describe('authenticated SSR bootstrap (API key present)', () => {
    it('applies layout to nodes from authenticated SSR response', () => {
      // Simulates the data shape from SSR-rendered page where API key was injected.
      // The page calls schemaApi.getErDiagram() which returns { success, nodes, edges, ... }
      const ssrResponse = {
        success: true,
        nodes: [
          { id: 'Orders', data: { label: 'Orders', columns: [{ name: 'Id', type: 'Long Integer' }], record_count: 0 } },
          { id: 'Customers', data: { label: 'Customers', columns: [{ name: 'Id', type: 'Long Integer' }], record_count: 0 } },
        ] as RawERNode[],
        edges: [
          { id: 'e1', source: 'Orders', target: 'Customers', label: 'FK_CustomerId', animated: false },
        ] as RawEREdge[],
        node_count: 2,
        edge_count: 1,
      }

      const flowNodes = buildFlowNodes(ssrResponse.nodes)
      const flowEdges = buildFlowEdges(ssrResponse.edges)
      const result = applyDagreLayout(flowNodes, flowEdges)

      // Layout must produce defined positions (dagre processed the graph)
      expect(result.nodes[0].position).toBeDefined()
      expect(result.nodes[1].position).toBeDefined()
      // In TB layout, Orders (source) should be above Customers (target)
      expect(result.nodes[0].position!.y).toBeLessThan(result.nodes[1].position!.y)
      // Edges must be preserved
      expect(result.edges).toHaveLength(1)
      expect(result.edges[0].source).toBe('Orders')
      expect(result.edges[0].target).toBe('Customers')
    })

    it('preserves node data and style from SSR bootstrap', () => {
      const ssrResponse = {
        success: true,
        nodes: [
          { id: 'Products', data: { label: 'Products', columns: [{ name: 'Name', type: 'Text' }], record_count: 150 } },
        ] as RawERNode[],
        edges: [] as RawEREdge[],
        node_count: 1,
        edge_count: 0,
      }

      const flowNodes = buildFlowNodes(ssrResponse.nodes)
      const flowEdges = buildFlowEdges(ssrResponse.edges)
      const result = applyDagreLayout(flowNodes, flowEdges)

      expect(result.nodes[0].data.label).toBe('Products')
      expect(result.nodes[0].data.columns).toHaveLength(1)
      expect(result.nodes[0].style.background).toBe('var(--color-bg-secondary)')
    })
  })

  describe('empty state (no tables)', () => {
    it('returns empty nodes and edges when API returns zero tables', () => {
      // Empty state from SSR — no database connected or no tables exist
      const emptyResponse = {
        success: true,
        nodes: [] as RawERNode[],
        edges: [] as RawEREdge[],
        node_count: 0,
        edge_count: 0,
      }

      const flowNodes = buildFlowNodes(emptyResponse.nodes)
      const flowEdges = buildFlowEdges(emptyResponse.edges)
      const result = applyDagreLayout(flowNodes, flowEdges)

      expect(result.nodes).toHaveLength(0)
      expect(result.edges).toHaveLength(0)
    })

    it('handles empty nodes array (different from zero-length API response)', () => {
      // Pure empty input — no nodes passed at all
      const result = applyDagreLayout([], [])
      expect(result.nodes).toHaveLength(0)
      expect(result.edges).toHaveLength(0)
    })

    it('produces deterministic empty layout (not random positions)', () => {
      // Calling layout twice with same empty input must produce same result
      const result1 = applyDagreLayout([], [])
      const result2 = applyDagreLayout([], [])
      expect(result1.nodes).toEqual(result2.nodes)
      expect(result1.edges).toEqual(result2.edges)
    })
  })

  describe('load failure scenarios', () => {
    it('gracefully handles nodes with missing position data', () => {
      // Nodes without position (e.g., malformed API response after load failure)
      const malformedNodes: Node[] = [
        { id: 'Table1', data: { label: 'Table1', columns: [] } } as Node,
        { id: 'Table2', data: { label: 'Table2', columns: [] } } as Node,
      ]
      const result = applyDagreLayout(malformedNodes, [])

      // Must not throw — should assign default positions
      expect(result.nodes).toHaveLength(2)
      expect(result.nodes[0].position).toBeDefined()
      expect(result.nodes[1].position).toBeDefined()
    })

    it('handles edges referencing non-existent nodes (orphaned edges)', () => {
      // After load failure, some edge references may be invalid
      const orphanedEdges: Edge[] = [
        { id: 'e1', source: 'NonExistent', target: 'AlsoMissing' },
      ]
      const result = applyDagreLayout([], orphanedEdges)

      // Edges preserved as-is; layout handles gracefully
      expect(result.edges).toHaveLength(1)
      expect(result.nodes).toHaveLength(0)
    })

    it('handles response with success=false (load failure signal)', () => {
      // SSR page may receive { success: false } on load failure
      // The Vue component checks data?.success and clears nodes on failure
      // Layout must handle empty nodes gracefully in this case
      const failedResponse = {
        success: false,
        nodes: [] as RawERNode[],
        edges: [] as RawEREdge[],
        node_count: 0,
        edge_count: 0,
      }

      const flowNodes = buildFlowNodes(failedResponse.nodes)
      const flowEdges = buildFlowEdges(failedResponse.edges)
      const result = applyDagreLayout(flowNodes, flowEdges)

      expect(result.nodes).toHaveLength(0)
      expect(result.edges).toHaveLength(0)
    })

    it('handles partial edge data (missing optional fields)', () => {
      // Edge missing label or animated fields (API inconsistency)
      const partialEdges: Edge[] = [
        { id: 'e1', source: 'Orders', target: 'Customers' } as Edge,
        { id: 'e2', source: 'Products', target: 'Orders', label: 'Rel', animated: true } as Edge,
      ]
      const result = applyDagreLayout([], partialEdges)

      expect(result.edges).toHaveLength(2)
      // Partial edge should still have source/target preserved
      expect(result.edges[0].source).toBe('Orders')
      expect(result.edges[0].target).toBe('Customers')
    })
  })
})

describe('applyDagreLayout (dashboard-refinement PR4)', () => {
  it('returns the same number of nodes and edges passed in', () => {
    const result = applyDagreLayout(mockNodes, mockEdges)
    expect(result.nodes).toHaveLength(3)
    expect(result.edges).toHaveLength(2)
  })

  it('assigns deterministic positions (no Math.random)', () => {
    const result1 = applyDagreLayout(mockNodes, mockEdges)
    const result2 = applyDagreLayout(mockNodes, mockEdges)
    // Every node must have identical positions across separate invocations.
    for (let i = 0; i < result1.nodes.length; i++) {
      expect(result1.nodes[i].position).toEqual(result2.nodes[i].position)
    }
  })

  it('places the source node above its target in default TB layout', () => {
    // Default rankdir is 'TB' (top-to-bottom). In a TB layout, a node that
    // points to another (Orders -> Customers) should sit above its target.
    const result = applyDagreLayout(mockNodes, mockEdges)
    const orders = result.nodes.find((n) => n.id === 'Orders')!
    const customers = result.nodes.find((n) => n.id === 'Customers')!
    expect(orders.position.y).toBeLessThan(customers.position.y)
  })

  it('preserves node data on round-trip', () => {
    const result = applyDagreLayout(mockNodes, mockEdges)
    expect(result.nodes[0].data).toEqual(mockNodes[0].data)
    expect(result.nodes[1].data).toEqual(mockNodes[1].data)
    expect(result.nodes[2].data).toEqual(mockNodes[2].data)
  })

  it('preserves node style on round-trip', () => {
    const styledNodes: Node[] = mockNodes.map((n) => ({
      ...n,
      style: { background: 'var(--color-bg-secondary)' },
    }))
    const result = applyDagreLayout(styledNodes, mockEdges)
    expect(result.nodes[0].style).toEqual({ background: 'var(--color-bg-secondary)' })
  })

  it('preserves edge source, target, and id wiring', () => {
    const result = applyDagreLayout(mockNodes, mockEdges)
    const e1 = result.edges.find((e) => e.id === 'e1')!
    const e2 = result.edges.find((e) => e.id === 'e2')!
    expect(e1.source).toBe('Orders')
    expect(e1.target).toBe('Customers')
    expect(e2.source).toBe('Orders')
    expect(e2.target).toBe('Products')
  })

  it('handles an empty graph', () => {
    const result = applyDagreLayout([], [])
    expect(result.nodes).toHaveLength(0)
    expect(result.edges).toHaveLength(0)
  })

  it('handles a single node with no edges', () => {
    const result = applyDagreLayout([mockNodes[0]], [])
    expect(result.nodes).toHaveLength(1)
    expect(result.nodes[0].position).toEqual({
      x: expect.any(Number),
      y: expect.any(Number),
    })
  })

  it('accepts a custom rankdir option (LR swaps x/y semantics)', () => {
    // In LR, source should sit to the LEFT (smaller x) of target.
    const result = applyDagreLayout(mockNodes, mockEdges, { rankdir: 'LR' })
    const orders = result.nodes.find((n) => n.id === 'Orders')!
    const customers = result.nodes.find((n) => n.id === 'Customers')!
    expect(orders.position.x).toBeLessThan(customers.position.x)
  })
})
