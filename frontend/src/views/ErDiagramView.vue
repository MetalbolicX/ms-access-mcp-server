<script setup lang="ts">
import { ref, watch } from 'vue'
import { VueFlow, useVueFlow, MiniMap, Controls } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useQuery } from '@tanstack/vue-query'
import { schemaApi } from '../api/client'
import type { ERDiagramResponse } from '../api/types'
import { applyDagreLayout } from './erDiagramLayout'

const { data, isLoading, error } = useQuery<ERDiagramResponse>({
  queryKey: ['er-diagram'],
  queryFn: schemaApi.getErDiagram,
  refetchOnWindowFocus: false,
})

const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const { fitView } = useVueFlow()

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
    nodes.value = layouted.nodes
    edges.value = layouted.edges

    // Wait one tick for Vue Flow to mount before fitting the viewport.
    setTimeout(() => fitView({ padding: 0.2 }), 200)
  },
  { immediate: true },
)
</script>

<template>
  <div class="er-diagram-view">
    <div class="diagram-header">
      <h1>ER Diagram</h1>
      <div class="diagram-stats">
        <el-tag type="info">{{ data?.node_count ?? 0 }} tables</el-tag>
        <el-tag type="info">{{ data?.edge_count ?? 0 }} relationships</el-tag>
      </div>
    </div>

    <div class="diagram-container">
      <div v-if="isLoading" class="loading">Loading schema...</div>
      <div v-else-if="error" class="error">Failed to load ER diagram: {{ error.message }}</div>
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
  </div>
</template>

<style scoped>
.er-diagram-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: var(--space-4);
}

.diagram-header {
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
</style>
