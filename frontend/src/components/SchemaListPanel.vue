<script setup lang="ts">
// SchemaListPanel.vue — the left pane of the unified schema explorer.
// Spec: sdd/unified-schema-explorer/spec. Design: see sdd/unified-schema-explorer/design in Engram.
//
// Responsibilities (this PR / slice):
//   - Render header, search input, table list, and selected-table detail.
//   - Fetch the table list via schemaApi.getTables() (cookie auth).
//   - Fetch the selected table's schema via schemaApi.getTableSchema(name)
//     and show the field list, or an error state.
//   - Use the shared useSchemaExplorer() composable for selection state.
//
// Out of scope (PR3): wiring the diagram side — @node-click on the Vue
// Flow node to drive select(node.id), and the fitView() watcher.
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { schemaApi } from '../api/apiClient'
import { useSchemaExplorer } from '../composables/useSchemaExplorer'
import type { TableField } from '../api/types'

const { selectedTable, select } = useSchemaExplorer()

// --- Table list query (cookie-auth via apiClient) ---

const {
  data: tablesData,
  isLoading: tablesLoading,
  error: tablesError,
} = useQuery({
  queryKey: ['tables'],
  queryFn: schemaApi.getTables,
  refetchOnWindowFocus: false,
})

const allTableNames = computed<string[]>(() => {
  if (!tablesData.value?.success) return []
  return tablesData.value.tables.map((t) => t.name)
})

// --- Search filter ---

const searchQuery = ref('')

const filteredTableNames = computed<string[]>(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return allTableNames.value
  return allTableNames.value.filter((name) => name.toLowerCase().includes(q))
})

// --- Detail query for the selected table ---

const {
  data: detailData,
  isLoading: detailLoading,
  error: detailError,
} = useQuery({
  // Cache key includes the table name so switching selection refetches.
  queryKey: computed(() => ['table-schema', selectedTable.value]),
  queryFn: () => schemaApi.getTableSchema(selectedTable.value as string),
  enabled: computed(() => selectedTable.value !== null),
  refetchOnWindowFocus: false,
})

const detailFields = computed<TableField[]>(() => {
  return detailData.value?.table?.fields ?? []
})

const detailTableName = computed<string | null>(() => {
  if (!selectedTable.value) return null
  if (detailData.value?.table?.name) return detailData.value.table.name
  return selectedTable.value
})

function onTableClick(name: string) {
  select(name)
}
</script>

<template>
  <aside class="schema-panel" aria-label="Schema explorer sidebar">
    <header class="schema-panel-header">
      <h2>Schema</h2>
      <span class="schema-panel-count" data-test="count-summary">
        Showing {{ filteredTableNames.length }} of {{ allTableNames.length }} tables
      </span>
    </header>

    <div class="schema-panel-search">
      <el-input
        v-model="searchQuery"
        placeholder="Search tables..."
        clearable
        aria-label="Search tables"
      />
    </div>

    <div class="schema-panel-body">
      <div
        v-if="tablesLoading"
        class="schema-panel-loading"
        role="status"
        aria-live="polite"
      >
        Loading tables...
      </div>

      <div
        v-else-if="tablesError"
        class="schema-panel-error"
        role="alert"
      >
        Failed to load tables: {{ tablesError.message }}
      </div>

      <ul
        v-else-if="filteredTableNames.length > 0"
        class="schema-panel-list"
        role="listbox"
        aria-label="Tables"
      >
        <li
          v-for="name in filteredTableNames"
          :key="name"
          :data-test="'table-item'"
          :data-table-name="name"
          :aria-selected="selectedTable === name ? 'true' : 'false'"
          :class="['schema-panel-list-item', { 'is-selected': selectedTable === name }]"
          role="option"
          tabindex="0"
          @click="onTableClick(name)"
          @keydown.enter="onTableClick(name)"
          @keydown.space.prevent="onTableClick(name)"
        >
          {{ name }}
        </li>
      </ul>

      <div
        v-else-if="searchQuery.trim() !== ''"
        class="schema-panel-empty"
        role="status"
        data-test="no-match"
      >
        No tables match "{{ searchQuery }}".
      </div>

      <div
        v-else
        class="schema-panel-empty"
        role="status"
        data-test="empty-database"
      >
        No tables in this database.
      </div>
    </div>

    <section
      v-if="selectedTable"
      class="schema-panel-detail"
      :data-test="'detail-area'"
      :aria-label="`Details for ${selectedTable}`"
    >
      <header class="schema-panel-detail-header">
        <h3>{{ detailTableName ?? selectedTable }}</h3>
      </header>

      <div v-if="detailLoading" class="schema-panel-detail-loading" role="status">
        Loading fields...
      </div>

      <div
        v-else-if="detailError"
        class="schema-panel-detail-error"
        role="alert"
      >
        Failed to load fields for {{ selectedTable }}: {{ detailError.message }}
      </div>

      <div
        v-else-if="!detailData?.success"
        class="schema-panel-detail-error"
        role="alert"
      >
        Failed to load fields for {{ selectedTable }}: {{ detailData?.error ?? 'Unknown error' }}
      </div>

      <table v-else-if="detailFields.length > 0" class="schema-panel-fields">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Type</th>
            <th scope="col">Size</th>
            <th scope="col">Required</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="field in detailFields" :key="field.name">
            <td>{{ field.name }}</td>
            <td>{{ field.type }}</td>
            <td>{{ field.size }}</td>
            <td>{{ field.required ? 'yes' : 'no' }}</td>
          </tr>
        </tbody>
      </table>

      <div v-else class="schema-panel-detail-empty" role="status">
        No fields.
      </div>
    </section>
  </aside>
</template>

<style scoped>
.schema-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border);
  overflow: hidden;
}

.schema-panel-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);

  & h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--color-text-primary);
  }
}

.schema-panel-count {
  font-size: 12px;
  color: var(--color-text-muted);
}

.schema-panel-search {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.schema-panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.schema-panel-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.schema-panel-list-item {
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-primary);
  border-bottom: 1px solid var(--color-border);
  user-select: none;

  &:hover,
  &:focus {
    background: var(--color-bg-hover);
    outline: none;
  }

  &.is-selected {
    background: var(--color-accent);
    color: #fff;
    font-weight: 600;
  }
}

.schema-panel-loading,
.schema-panel-error,
.schema-panel-empty {
  padding: var(--space-3) var(--space-4);
  font-size: 13px;
  color: var(--color-text-muted);
}

.schema-panel-error {
  color: var(--color-error);
}

.schema-panel-detail {
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-primary);
  max-height: 40%;
  overflow-y: auto;
}

.schema-panel-detail-header {
  padding: var(--space-2) var(--space-4);

  & h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
  }
}

.schema-panel-detail-loading,
.schema-panel-detail-error,
.schema-panel-detail-empty {
  padding: var(--space-2) var(--space-4);
  font-size: 12px;
  color: var(--color-text-muted);
}

.schema-panel-detail-error {
  color: var(--color-error);
}

.schema-panel-fields {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;

  & th,
  & td {
    padding: var(--space-1) var(--space-3);
    text-align: left;
    border-bottom: 1px solid var(--color-border);
  }

  & th {
    font-weight: 600;
    color: var(--color-text-muted);
    background: var(--color-bg-secondary);
  }

  & td {
    color: var(--color-text-primary);
  }
}
</style>
