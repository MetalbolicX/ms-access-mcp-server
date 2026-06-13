<script setup lang="ts">
// ErDiagramView.vue — the unified schema explorer view.
//
// PR2 brought in the split layout: <SchemaListPanel> on the left and
// <VueFlow> on the right, with the data path switched from
// `../api/client` (localStorage) to `../api/apiClient` (cookie auth) so
// every fetch in the unified view uses the same session-cookie auth as
// the rest of the app.
//
// PR3 (this slice) wires the bidirectional selection sync between the
// two panes:
//   - @node-click on VueFlow → useSchemaExplorer().select(node.id),
//     so clicking a diagram node selects the matching table in the list.
//   - A watch on selectedTable that (a) applies the `is-selected` class
//     to the corresponding Vue Flow node and (b) calls
//     fitView({ nodes: [id], padding }) to auto-pan the diagram to the
//     selection. Selection is the single source of truth — the list
//     drives the diagram highlight, and the diagram drives the list via
//     the @node-click handler above.
import { ref, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useQuery } from '@tanstack/vue-query'
import { schemaApi } from '../api/apiClient'
import type { ERDiagramResponse } from '../api/types'
import { applyDagreLayout } from './erDiagramLayout'
import { useSchemaExplorer } from '../composables/useSchemaExplorer'
import SchemaListPanel from '../components/SchemaListPanel.vue'

const { data, isLoading, error } = useQuery<ERDiagramResponse>({
  queryKey: ['er-diagram'],
  queryFn: schemaApi.getErDiagram,
  refetchOnWindowFocus: false,
})

const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const { fitView } = useVueFlow()

// Shared selection state. PR3 reads selectedTable to drive the
// diagram-side highlight + fitView, and writes via select() from the
// @node-click handler below.
const { selectedTable, select } = useSchemaExplorer()

// Build vue-flow nodes/edges from the API response and run them through
// the dagre layout helper. Using `watch(immediate: true)` so that the
// diagram refreshes when the query refetches (e.g. after connecting to
// a different database), not just on first mount.
watch(
  data,
  (newData) => {
    if (!newData?.success) {
      nodes.value = []
      edges.value = []
      return
    }

    const rawNodes = newData.nodes.map((n) => ({
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

    const rawEdges = newData.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: e.animated,
      style: { stroke: 'var(--color-accent)' },
    }))

    // Deterministic layered layout — replaces the previous Math.random()
    // positions and makes the diagram render the same way on every load.
    const layouted = applyDagreLayout(rawNodes, rawEdges)
    // PR3: apply the current selection highlight so a table selected
    // before the diagram query resolves is reflected on first render.
    nodes.value = applySelectionHighlight(layouted.nodes, selectedTable.value)
    edges.value = layouted.edges

    // Wait one tick for Vue Flow to mount before fitting the viewport.
    setTimeout(() => fitView({ padding: 0.2 }), 200)
  },
  { immediate: true },
)

// --- Selection sync (PR3) ---

// Mark a single node as selected. Pure helper so both the data
// watcher (initial render) and the selectedTable watcher (runtime
// changes) share the same transformation. Returning a new array keeps
// Vue's reactivity happy and ensures Vue Flow re-renders the class.
function applySelectionHighlight<T extends { id: string; class?: unknown }>(
  nodeList: T[],
  selectedId: string | null,
): T[] {
  return nodeList.map((n) => ({
    ...n,
    class: n.id === selectedId ? 'is-selected' : '',
  }))
}

// Re-apply the highlight whenever selectedTable changes at runtime.
// We intentionally do NOT use `{ immediate: true }` here — the data
// watcher above already applies the initial highlight when the query
// resolves, and using immediate here too would cause a no-op map
// against an empty nodes array on the very first synchronous tick.
watch(selectedTable, (id) => {
  nodes.value = applySelectionHighlight(nodes.value, id)
  // Auto-pan to the selection so the user does not have to hunt for
  // the node in a large graph. The setTimeout gives Vue Flow a chance
  // to re-render the class change first.
  if (id) {
    setTimeout(() => fitView({ nodes: [id], padding: 0.2 }), 50)
  }
})

// @node-click on VueFlow fires with { node, event } — extract the
// node id and push it to the shared selection. The list pane (and
// the watch above) react automatically.
function onNodeClick(params: { node: { id: string } }) {
  select(params.node.id)
}
</script>

<template>
  <div class="unified-explorer">
    <header class="unified-header">
      <h1>Schema Explorer</h1>
      <div class="diagram-stats">
        <el-tag type="info">{{ data?.node_count ?? 0 }} tables</el-tag>
        <el-tag type="info">{{ data?.edge_count ?? 0 }} relationships</el-tag>
      </div>
    </header>

    <div class="unified-body">
      <SchemaListPanel class="unified-left-pane" />

      <section class="unified-right-pane" aria-label="ER diagram">
        <div class="diagram-container">
          <div v-if="isLoading" class="loading">Loading schema...</div>
          <div v-else-if="error" class="error">
            Failed to load ER diagram: {{ error.message }}
          </div>
          <div v-else-if="nodes.length === 0" class="empty">
            No tables found. Connect to a database first.
          </div>
          <VueFlow
            v-else
            v-model:nodes="nodes"
            v-model:edges="edges"
            :fit-view-on-init="true"
            :default-viewport="{ zoom: 0.8 }"
            class="vue-flow"
            @node-click="onNodeClick"
          >
            <MiniMap
              pannable
              zoomable
              :node-color="'var(--color-accent)'"
              :mask-color="'rgba(15, 15, 15, 0.7)'"
            />
            <Controls />

            <template #node="{ data: nodeData }">
              <div class="table-node">
                <div class="table-node-header">{{ nodeData.label }}</div>
                <div class="table-node-body">
                  <div
                    v-for="col in nodeData.columns"
                    :key="col.name"
                    class="column-row"
                  >
                    <span class="col-name">{{ col.name }}</span>
                    <span class="col-type">{{ col.type }}</span>
                  </div>
                </div>
              </div>
            </template>

            <template #edge-label="{ label }">
              <div class="edge-label">{{ label }}</div>
            </template>
          </VueFlow>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.unified-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: var(--space-4);
}

.unified-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  & h1 {
    font-size: 24px;
    font-weight: 700;
    margin: 0;
    color: var(--color-text-primary);
  }
}

.diagram-stats {
  display: flex;
  gap: var(--space-2);
}

.unified-body {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: var(--space-3);
}

.unified-left-pane {
  /* The panel itself sets its own background / border; the view just
     gives it a fixed flex basis so the diagram gets the rest. */
  flex: 0 0 320px;
  min-height: 0;
}

.unified-right-pane {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
}

.diagram-container {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-bg-primary);
}

.vue-flow {
  width: 100%;
  height: 100%;
  background: var(--color-bg-primary);
}

.loading,
.error,
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-text-muted);
  font-size: 16px;
}

.error {
  color: var(--color-error);
}

.table-node {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  min-width: 160px;
  font-size: 12px;
  box-shadow: var(--shadow-md);

  &-header {
    background: var(--color-accent);
    color: #fff;
    padding: 6px 10px;
    font-weight: 600;
    border-radius: 5px 5px 0 0;
  }

  &-body {
    padding: 4px 0;
  }
}

.column-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 8px;
  gap: 12px;

  &:hover {
    background: var(--color-bg-hover);
  }
}

.col-name {
  color: var(--color-text-primary);
  font-weight: 500;
}

.col-type {
  color: var(--color-text-muted);
  font-size: 11px;
}

.edge-label {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-accent);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 10px;
  color: var(--color-accent);
}

/* PR3 — selection sync. When the user selects a table in the list pane,
   the watch in <script setup> tags the corresponding Vue Flow node with
   the `is-selected` class. Vue Flow propagates that class onto the
   node's outer wrapper, so we use a descendant selector to highlight
   the inner `.table-node`. The outline is in addition to the
   per-node border set inline in <script setup>, so the highlighted
   state reads as a clear outline ring on top of the existing card. */
.vue-flow :deep(.is-selected) .table-node {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--color-accent-soft, rgba(231, 76, 60, 0.18));
}
</style>
