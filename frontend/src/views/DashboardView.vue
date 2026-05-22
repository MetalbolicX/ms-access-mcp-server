<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { connectionApi, schemaApi } from '../api/client'
import type { TablesResponse, RelationshipsResponse } from '../api/types'

// Connection state
const databasePath = ref('')
const useCom = ref(false)

const { data: connectionStatus, refetch: checkConnection } = useQuery({
  queryKey: ['connection'],
  queryFn: connectionApi.isConnected,
  refetchInterval: 10000,
})

const { data: tablesData, isLoading: tablesLoading } = useQuery<TablesResponse>({
  queryKey: ['tables'],
  queryFn: schemaApi.getTables,
  enabled: computed(() => connectionStatus.value?.connected === true),
})

const { data: relationshipsData } = useQuery<RelationshipsResponse>({
  queryKey: ['relationships'],
  queryFn: schemaApi.getRelationships,
  enabled: computed(() => connectionStatus.value?.connected === true),
})

const isConnected = computed(() => connectionStatus.value?.connected === true)
const tableCount = computed(() => tablesData.value?.count ?? 0)
const relationshipCount = computed(() => relationshipsData.value?.count ?? 0)

async function handleConnect() {
  if (!databasePath.value) return
  await connectionApi.connect(databasePath.value, useCom.value)
  checkConnection()
}

async function handleDisconnect() {
  await connectionApi.disconnect()
  checkConnection()
}
</script>

<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h1>Dashboard</h1>
    </div>

    <!-- Connection Card -->
    <div class="data-card connection-card">
      <div class="card-header">
        <span class="card-title">Database Connection</span>
        <span :class="['status-badge', isConnected ? 'connected' : 'disconnected']">
          {{ isConnected ? 'Connected' : 'Disconnected' }}
        </span>
      </div>

      <div v-if="!isConnected" class="connect-form">
        <el-input
          v-model="databasePath"
          placeholder="C:\path\to\database.accdb"
          size="large"
          class="path-input"
        />
        <div class="connect-options">
          <el-checkbox v-model="useCom">Use COM Automation</el-checkbox>
          <el-button type="primary" size="large" @click="handleConnect">
            Connect
          </el-button>
        </div>
      </div>

      <div v-else class="connection-info">
        <div class="info-row">
          <span class="info-label">Database:</span>
          <span class="info-value">{{ connectionStatus?.database }}</span>
        </div>
        <el-button type="danger" @click="handleDisconnect">Disconnect</el-button>
      </div>
    </div>

    <!-- Stats Cards -->
    <div v-if="isConnected" class="stats-grid">
      <div class="data-card stat-card">
        <div class="stat-value">{{ tableCount }}</div>
        <div class="stat-label">Tables</div>
      </div>

      <div class="data-card stat-card">
        <div class="stat-value">{{ relationshipCount }}</div>
        <div class="stat-label">Relationships</div>
      </div>
    </div>

    <!-- Recent Tables -->
    <div v-if="isConnected && tablesData?.tables?.length" class="data-card">
      <div class="card-header">
        <span class="card-title">Recent Tables</span>
        <el-button text @click="$router.push('/schema')">View All</el-button>
      </div>
      <el-table :data="tablesData.tables.slice(0, 5)" stripe style="width: 100%">
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="record_count" label="Records" width="100" />
      </el-table>
    </div>

    <!-- Loading State -->
    <div v-if="tablesLoading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>Loading schema...</span>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.dashboard-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0;
}

.connection-card {
  max-width: 600px;
}

.connect-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.path-input {
  width: 100%;
}

.connect-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.connection-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.info-row {
  display: flex;
  gap: var(--space-2);
}

.info-label {
  color: var(--color-text-muted);
}

.info-value {
  color: var(--color-text-primary);
  word-break: break-all;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
  max-width: 400px;
}

.stat-card {
  text-align: center;
  padding: var(--space-6);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text-muted);
}
</style>