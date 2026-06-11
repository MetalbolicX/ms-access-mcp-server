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
