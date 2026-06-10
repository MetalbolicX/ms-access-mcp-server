// Dagre-based layout helper for the ER diagram view.
// dashboard-refinement PR4: replaces Math.random() positions with a
// deterministic layered graph layout so the diagram renders stably and
// looks the same on every load.
import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@vue-flow/core'

export interface LayoutOptions {
  rankdir?: 'TB' | 'LR' | 'BT' | 'RL'
  nodesep?: number
  ranksep?: number
  edgesep?: number
  // Node size used by dagre to compute ranks/positions.
  nodeWidth?: number
  nodeHeight?: number
}

const DEFAULT_OPTIONS: Required<LayoutOptions> = {
  rankdir: 'TB',
  nodesep: 50,
  ranksep: 80,
  edgesep: 20,
  nodeWidth: 180,
  nodeHeight: 100,
}

/**
 * Compute deterministic (x, y) positions for Vue Flow nodes using dagre.
 * Preserves node `data` and `style` and returns edges untouched. The
 * resulting `position` is the TOP-LEFT corner of the node (Vue Flow's
 * contract) — dagre returns the CENTER, so we shift by half the node size.
 */
export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): { nodes: Node[]; edges: Edge[] } {
  const opts = { ...DEFAULT_OPTIONS, ...options }

  // Empty input fast path: dagre.graphlib.Graph() does not like being
  // asked to layout nothing, and the tests assert a clean empty result.
  if (nodes.length === 0) {
    return { nodes: [], edges: [...edges] }
  }

  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: opts.rankdir,
    nodesep: opts.nodesep,
    ranksep: opts.ranksep,
    edgesep: opts.edgesep,
  })
  g.setDefaultEdgeLabel(() => ({}))

  // Register every node with explicit dimensions so dagre can compute
  // collision-free positions.
  for (const node of nodes) {
    g.setNode(node.id, { width: opts.nodeWidth, height: opts.nodeHeight })
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target)
  }

  dagre.layout(g)

  // Apply positions back onto the original node objects (preserving
  // data/style and any other fields the consumer attached).
  const layoutedNodes = nodes.map((node) => {
    const positioned = g.node(node.id) as { x: number; y: number } | undefined
    // Dagre centers each node; Vue Flow expects top-left, so subtract
    // half the node size. Falls back to (0, 0) if dagre dropped the node.
    const x = positioned ? positioned.x - opts.nodeWidth / 2 : 0
    const y = positioned ? positioned.y - opts.nodeHeight / 2 : 0
    return {
      ...node,
      position: { x, y },
    }
  })

  return { nodes: layoutedNodes, edges: [...edges] }
}
