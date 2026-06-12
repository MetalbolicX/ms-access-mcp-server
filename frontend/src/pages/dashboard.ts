// Alpine.js dashboard page — cookie-based auth, no localStorage.
// Mounted by the SSR template at dashboard.html via<script src="/dist/assets/dashboard.js">
import { connectionApi, schemaApi } from '../api/apiClient'
import type { DatabaseStatistics, TablesResponse, RelationshipsResponse } from '../api/types'

/**
 * Load current connection status.
 * @throws Error on 401 (redirects to /login via apiClient).
 */
export async function loadConnectionStatus(): Promise<{ connected: boolean; database?: string }> {
  return connectionApi.isConnected()
}

/**
 * Load database aggregate statistics.
 * @throws Error on 401 (redirects to /login via apiClient).
 */
export async function loadStats(): Promise<DatabaseStatistics> {
  return schemaApi.getDatabaseStatistics()
}

/**
 * Connect to a database.
 */
export async function connectDatabase(
  databasePath: string,
  useCom = false,
  password = '',
): Promise<{ success: boolean; connected: boolean; database: string }> {
  return connectionApi.connect(databasePath, useCom, password)
}

/**
 * Disconnect from the current database.
 */
export async function disconnectDatabase(): Promise<{ success: boolean; message: string }> {
  return connectionApi.disconnect()
}

/**
 * Load relationships for the relationships panel.
 */
export async function loadRelationships(): Promise<RelationshipsResponse> {
  return schemaApi.getRelationships()
}

/**
 * Load all tables (for lazy-loaded object list).
 */
export async function loadTables(): Promise<TablesResponse> {
  return schemaApi.getTables()
}

/**
 * Load all queries (for lazy-loaded object list).
 */
export async function loadQueries(): Promise<{ success: boolean; queries: any[]; count: number }> {
  return schemaApi.getQueries()
}

/**
 * Format bytes to human-readable size string.
 */
export function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// Expose globally for Alpine.js inline templates
declare global {
  interface Window {
    loadConnectionStatus: typeof loadConnectionStatus
    loadStats: typeof loadStats
    connectDatabase: typeof connectDatabase
    disconnectDatabase: typeof disconnectDatabase
    loadRelationships: typeof loadRelationships
    loadTables: typeof loadTables
    loadQueries: typeof loadQueries
    formatSize: typeof formatSize
  }
}

if (typeof window !== 'undefined') {
  window.loadConnectionStatus = loadConnectionStatus
  window.loadStats = loadStats
  window.connectDatabase = connectDatabase
  window.disconnectDatabase = disconnectDatabase
  window.loadRelationships = loadRelationships
  window.loadTables = loadTables
  window.loadQueries = loadQueries
  window.formatSize = formatSize
}
