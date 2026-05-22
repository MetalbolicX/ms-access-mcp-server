<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { schemaApi } from '../api/client'
import type { TablesResponse, TableSchemaResponse } from '../api/types'

const selectedTable = ref<string | null>(null)
const searchQuery = ref('')

const { data: tablesData } = useQuery<TablesResponse>({
  queryKey: ['tables'],
  queryFn: schemaApi.getTables,
})

const { data: tableSchema } = useQuery<TableSchemaResponse>({
  queryKey: ['table-schema', selectedTable],
  queryFn: () => schemaApi.getTableSchema(selectedTable.value!),
  enabled: computed(() => !!selectedTable.value),
})

const filteredTables = computed(() => {
  if (!tablesData.value?.tables) return []
  if (!searchQuery.value) return tablesData.value.tables
  const query = searchQuery.value.toLowerCase()
  return tablesData.value.tables.filter((t) => t.name.toLowerCase().includes(query))
})

function selectTable(name: string) {
  selectedTable.value = name
}
</script>

<template>
  <div class="schema-explorer">
    <div class="explorer-header">
      <h1>Schema Explorer</h1>
      <el-input
        v-model="searchQuery"
        placeholder="Search tables..."
        prefix-icon="Search"
        clearable
        class="search-input"
      />
    </div>

    <div class="explorer-layout">
      <!-- Tables List -->
      <div class="tables-panel data-card">
        <div class="panel-header">
          <span class="card-title">Tables ({{ tablesData?.count ?? 0 }})</span>
        </div>
        <div class="tables-list">
          <div
            v-for="table in filteredTables"
            :key="table.name"
            :class="['table-item', { active: selectedTable === table.name }]"
            @click="selectTable(table.name)"
          >
            <span class="table-name">{{ table.name }}</span>
            <span class="table-count">{{ table.record_count }}</span>
          </div>
        </div>
      </div>

      <!-- Table Details -->
      <div class="details-panel">
        <div v-if="!selectedTable" class="empty-state data-card">
          <span>Select a table to view its schema</span>
        </div>

        <div v-else-if="tableSchema" class="schema-details data-card">
          <div class="card-header">
            <span class="card-title">{{ tableSchema.table?.name }}</span>
          </div>

          <el-table :data="tableSchema.table?.fields" stripe style="width: 100%">
            <el-table-column prop="name" label="Column" />
            <el-table-column prop="type" label="Type" width="140" />
            <el-table-column prop="size" label="Size" width="80" />
            <el-table-column prop="required" label="Required" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.required" type="danger" size="small">Required</el-tag>
                <el-tag v-else type="info" size="small">Optional</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schema-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: var(--space-5);
}

.explorer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  & h1 {
    font-size: 24px;
    font-weight: 700;
    color: var(--color-text-primary);
    margin: 0;
  }
}

.search-input {
  width: 280px;
}

.explorer-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: var(--space-5);
  flex: 1;
  min-height: 0;
}

.tables-panel {
  overflow: hidden;
  display: flex;
  flex-direction: column;

  & .panel-header {
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--color-border);
  }
}

.tables-list {
  overflow-y: auto;
  flex: 1;
  margin-top: var(--space-2);
}

.table-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);

  &:hover {
    background: var(--color-bg-hover);
  }

  &.active {
    background: var(--color-accent-subtle);

    & .table-name {
      color: var(--color-accent);
    }
  }

  & .table-name {
    color: var(--color-text-primary);
    font-size: 14px;
  }

  & .table-count {
    color: var(--color-text-muted);
    font-size: 12px;
  }
}

.details-panel {
  min-width: 0;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--color-text-muted);
}

.schema-details {
  overflow: auto;
}
</style>