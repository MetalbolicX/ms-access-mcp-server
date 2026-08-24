// Alpine.js dashboard page — cookie-based auth, no localStorage.
// Mounted by the SSR template at dashboard.html via<script src="/dist/assets/dashboard.js">
import { connectionApi, schemaApi } from '../api/apiClient'
import type { DatabaseStatistics, TablesResponse, RelationshipsResponse } from '../api/types'

export const loadConnectionStatus = async (): Promise<{ connected: boolean; database?: string }> => {
  return connectionApi.isConnected()
}

export const loadStats = async (): Promise<DatabaseStatistics> => {
  return schemaApi.getDatabaseStatistics()
}

export const connectDatabase = async (
  databasePath: string,
  useCom = false,
  password = '',
): Promise<{ success: boolean; connected: boolean; database: string }> => {
  return connectionApi.connect(databasePath, useCom, password)
}

export const disconnectDatabase = async (): Promise<{ success: boolean; message: string }> => {
  return connectionApi.disconnect()
}

export const loadRelationships = async (): Promise<RelationshipsResponse> => {
  return schemaApi.getRelationships()
}

export const loadTables = async (): Promise<TablesResponse> => {
  return schemaApi.getTables()
}

export const loadQueries = async (): Promise<{ success: boolean; queries: any[]; count: number }> => {
  return schemaApi.getQueries()
}

export const formatSize = (bytes: number): string => {
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
