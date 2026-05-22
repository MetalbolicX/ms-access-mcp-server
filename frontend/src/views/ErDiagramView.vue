<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useQuery } from '@tanstack/vue-query'
import { schemaApi } from '../api/client'
import type { ERDiagramResponse } from '../api/types'

const { data, isLoading, error } = useQuery<ERDiagramResponse>({
  queryKey: ['er-diagram'],
  queryFn: schemaApi.getErDiagram,
  refetchOnWindowFocus: false,
})

const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const { fitView } = useVueFlow()

onMounted(() => {
  if (data.value?.success) {
    nodes.value = data.value.nodes.map((n) => ({
      id: n.id,
      position: { x: Math.random() * 400, y: Math.random() * 300 },
      data: n.data,
      style: {
        background: '#fff',
        border: '1px solid #409eff',
        borderRadius: '8px',
        padding: '10px',
        minWidth: '180px',
        fontSize: '13px',
      },
    }))

    edges.value = data.value.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: e.animated,
      style: { stroke: '#409eff' },
    }))

    setTimeout(() => fitView({ padding: 0.2 }), 200)
  }
})
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
  background: #fafafa;
}

.vue-flow {
  width: 100%;
  height: 100%;
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
  color: var(--color-danger);
}

.table-node {
  background: #fff;
  border: 1px solid var(--color-accent);
  border-radius: 6px;
  min-width: 160px;
  font-size: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

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
    background: #f0f7ff;
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
  background: #fff;
  border: 1px solid #409eff;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 10px;
  color: #409eff;
}
</style>
