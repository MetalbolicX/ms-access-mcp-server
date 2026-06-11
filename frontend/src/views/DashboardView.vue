<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { connectionApi, schemaApi } from '../api/client'
import type {
  DatabaseStatistics,
  TablesResponse,
  QueriesResponse,
  ObjectListResponse,
  RelationshipsResponse,
} from '../api/types'

// Connection state
const databasePath = ref('')
const useCom = ref(false)
const dbPassword = ref('')
const connectError = ref('')

// Connection status (polled)
const { data: connectionStatus, refetch: checkConnection } = useQuery({
  queryKey: ['connection'],
  queryFn: connectionApi.isConnected,
  refetchInterval: 10000,
  enabled: false,
})

const isConnected = computed(() => connectionStatus.value?.connected === true)

// Aggregate statistics — drives the 4x2 grid
const { data: statsData, isLoading: statsLoading } = useQuery<DatabaseStatistics>({
  queryKey: ['database-stats'],
  queryFn: schemaApi.getDatabaseStatistics,
  enabled: isConnected,
})

// Relationships (separate from the 8-card grid; shown in its own panel)
const { data: relationshipsData } = useQuery<RelationshipsResponse>({
  queryKey: ['relationships'],
  queryFn: schemaApi.getRelationships,
  enabled: isConnected,
})

const relationshipCount = computed(() => relationshipsData.value?.count ?? 0)

// Lazy-loaded object lists — enabled only when their card is active
const activeListType = ref<string | null>(null)

const { data: tablesData, isLoading: tablesLoading } = useQuery<TablesResponse>({
  queryKey: ['tables'],
  queryFn: schemaApi.getTables,
  enabled: computed(() => activeListType.value === 'tables'),
})

const { data: queriesData, isLoading: queriesLoading } = useQuery<QueriesResponse>({
  queryKey: ['queries'],
  queryFn: schemaApi.getQueries,
  enabled: computed(() => activeListType.value === 'queries'),
})

const { data: formsData, isLoading: formsLoading } = useQuery<ObjectListResponse>({
  queryKey: ['forms'],
  queryFn: schemaApi.listForms,
  enabled: computed(() => activeListType.value === 'forms'),
})

const { data: reportsData, isLoading: reportsLoading } = useQuery<ObjectListResponse>({
  queryKey: ['reports'],
  queryFn: schemaApi.listReports,
  enabled: computed(() => activeListType.value === 'reports'),
})

const { data: macrosData, isLoading: macrosLoading } = useQuery<ObjectListResponse>({
  queryKey: ['macros'],
  queryFn: schemaApi.listMacros,
  enabled: computed(() => activeListType.value === 'macros'),
})

const { data: modulesData, isLoading: modulesLoading } = useQuery<ObjectListResponse>({
  queryKey: ['modules'],
  queryFn: schemaApi.listModules,
  enabled: computed(() => activeListType.value === 'modules'),
})

// Toggle detail panel — clicking the same card again closes it
function toggleList(type: string) {
  activeListType.value = activeListType.value === type ? null : type
}

function getListCount(): number {
  switch (activeListType.value) {
    case 'tables':
      return tablesData.value?.tables.length ?? 0
    case 'queries':
      return queriesData.value?.queries.length ?? 0
    case 'forms':
      return formsData.value?.count ?? 0
    case 'reports':
      return reportsData.value?.count ?? 0
    case 'macros':
      return macrosData.value?.count ?? 0
    case 'modules':
      return modulesData.value?.count ?? 0
    default:
      return 0
  }
}

function getListItems(): string[] {
  switch (activeListType.value) {
    case 'forms':
      return formsData.value?.items ?? []
    case 'reports':
      return reportsData.value?.items ?? []
    case 'macros':
      return macrosData.value?.items ?? []
    case 'modules':
      return modulesData.value?.items ?? []
    default:
      return []
  }
}

function isListLoading(): boolean {
  switch (activeListType.value) {
    case 'tables':
      return tablesLoading.value
    case 'queries':
      return queriesLoading.value
    case 'forms':
      return formsLoading.value
    case 'reports':
      return reportsLoading.value
    case 'macros':
      return macrosLoading.value
    case 'modules':
      return modulesLoading.value
    default:
      return false
  }
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// Connect / disconnect (preserved from prior dashboard)
async function handleConnect() {
  if (!databasePath.value) return
  connectError.value = ''
  try {
    await connectionApi.connect(databasePath.value, useCom.value, dbPassword.value)
    checkConnection()
  } catch (err) {
    connectError.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleDisconnect() {
  try {
    await connectionApi.disconnect()
    checkConnection()
  } catch (err) {
    connectError.value = err instanceof Error ? err.message : String(err)
  }
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
        <el-input
          v-model="dbPassword"
          type="password"
          placeholder="Database password (optional)"
          size="large"
          show-password
          class="password-input"
        />
        <el-alert
          v-if="connectError"
          :title="connectError"
          type="error"
          show-icon
          closable
          class="connect-error"
          @close="connectError = ''"
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

    <!-- 4x2 Stats Grid -->
    <div v-if="isConnected" class="stats-grid">
      <!-- Row 1 -->
      <div class="data-card stat-card" data-testid="stat-tables" @click="toggleList('tables')">
        <div class="stat-icon">📊</div>
        <div class="stat-value">{{ statsData?.objects.tables ?? 0 }}</div>
        <div class="stat-label">Tables</div>
      </div>
      <div class="data-card stat-card" data-testid="stat-queries" @click="toggleList('queries')">
        <div class="stat-icon">🔍</div>
        <div class="stat-value">{{ statsData?.objects.queries ?? 0 }}</div>
        <div class="stat-label">Queries</div>
      </div>
      <div class="data-card stat-card" data-testid="stat-forms" @click="toggleList('forms')">
        <div class="stat-icon">📝</div>
        <div class="stat-value">{{ statsData?.objects.forms ?? 0 }}</div>
        <div class="stat-label">Forms</div>
      </div>
      <div class="data-card stat-card" data-testid="stat-reports" @click="toggleList('reports')">
        <div class="stat-icon">📋</div>
        <div class="stat-value">{{ statsData?.objects.reports ?? 0 }}</div>
        <div class="stat-label">Reports</div>
      </div>
      <!-- Row 2 -->
      <div class="data-card stat-card" data-testid="stat-macros" @click="toggleList('macros')">
        <div class="stat-icon">⚙️</div>
        <div class="stat-value">{{ statsData?.objects.macros ?? 0 }}</div>
        <div class="stat-label">Macros</div>
      </div>
      <div class="data-card stat-card" data-testid="stat-modules" @click="toggleList('modules')">
        <div class="stat-icon">📦</div>
        <div class="stat-value">{{ statsData?.objects.modules ?? 0 }}</div>
        <div class="stat-label">Modules</div>
      </div>
      <div class="data-card stat-card stat-info">
        <div class="stat-icon">💾</div>
        <div class="stat-value">{{ formatSize(statsData?.file.size_bytes ?? 0) }}</div>
        <div class="stat-label">DB Size</div>
      </div>
      <div class="data-card stat-card stat-info">
        <div class="stat-icon">🔧</div>
        <div class="stat-value">{{ statsData?.system.access_version ?? 'N/A' }}</div>
        <div class="stat-label">Access Version</div>
      </div>
    </div>

    <!-- Lazy-loaded Object List Panel -->
    <div v-if="activeListType" class="data-card object-list-panel">
      <div class="card-header">
        <span class="card-title">{{ activeListType }} ({{ getListCount() }})</span>
        <el-button text @click="activeListType = null">Close</el-button>
      </div>
      <div v-if="isListLoading()" class="loading-state">Loading...</div>
      <template v-else>
        <el-table v-if="activeListType === 'tables' && tablesData" :data="tablesData.tables" stripe>
          <el-table-column prop="name" label="Name" />
          <el-table-column prop="record_count" label="Records" width="100" />
        </el-table>
        <el-table v-else-if="activeListType === 'queries' && queriesData" :data="queriesData.queries" stripe>
          <el-table-column prop="name" label="Name" />
          <el-table-column prop="sql" label="SQL" show-overflow-tooltip />
        </el-table>
        <el-empty v-else-if="getListItems().length === 0" description="No items found" />
        <div v-else class="simple-list">
          <div v-for="item in getListItems()" :key="item" class="list-item">{{ item }}</div>
        </div>
      </template>
    </div>

    <!-- Loading State for stats -->
    <div v-if="isConnected && statsLoading" class="loading-state">Loading schema...</div>

    <!-- Relationships Section -->
    <div v-if="isConnected" class="data-card relationships-card">
      <div class="card-header">
        <span class="card-title">Relationships</span>
        <el-button text @click="$router.push('/er-diagram')">Open ER Diagram</el-button>
      </div>
      <div class="stat-value">{{ relationshipCount }}</div>
      <div class="stat-label">relationships defined</div>
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

.password-input {
  width: 100%;
}

.connect-error {
  margin-top: var(--space-2);
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
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  text-align: center;
  padding: var(--space-5);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.stat-card:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-accent);
}

.stat-card.stat-info {
  cursor: default;
}

.stat-icon {
  font-size: 24px;
  margin-bottom: var(--space-2);
}

.object-list-panel {
  max-height: 400px;
  overflow-y: auto;
}

.simple-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.list-item {
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text-muted);
}
</style>
