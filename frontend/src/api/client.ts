// Native fetch API client — no axios, web standard only
import type { DatabaseStatistics, ObjectListResponse } from './types'

const API_BASE = ''

// --- API Key State ---
let apiKey: string = localStorage.getItem('mcp_api_key') ?? ''

export function getApiKey(): string {
  return apiKey
}

export function setApiKey(key: string): void {
  apiKey = key
  localStorage.setItem('mcp_api_key', key)
}

export function clearApiKey(): void {
  apiKey = ''
  localStorage.removeItem('mcp_api_key')
}

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options

  const headers: Record<string, string> = {}
  if (body) {
    headers['Content-Type'] = 'application/json'
  }
  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers: Object.keys(headers).length > 0 ? headers : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  })

  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:required'))
      throw new Error('Authentication required')
    }
    const error = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(error.error || `HTTP ${response.status}`)
  }

  return response.json()
}

// Connection API
export const connectionApi = {
  connect: (databasePath: string, useCom = false, password = '') =>
    apiRequest<{ success: boolean; connected: boolean; database: string }>('/mcp/tools/call', {
      method: 'POST',
      body: {
        name: 'connect_access',
        arguments: { database_path: databasePath, use_com: useCom, password },
      },
    }),

  disconnect: () =>
    apiRequest<{ success: boolean; message: string }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'disconnect_access', arguments: {} },
    }),

  isConnected: () =>
    apiRequest<{ connected: boolean; database?: string }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'is_connected', arguments: {} },
    }),
}

// Schema API
export const schemaApi = {
  getTables: () =>
    apiRequest<{ success: boolean; tables: any[]; count: number }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_tables', arguments: {} },
    }),

  getTableSchema: (tableName: string) =>
    apiRequest<{ success: boolean; table?: any; error?: string }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_table_schema', arguments: { table_name: tableName } },
    }),

  getQueries: () =>
    apiRequest<{ success: boolean; queries: any[]; count: number }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_queries', arguments: {} },
    }),

  getRelationships: () =>
    apiRequest<{ success: boolean; relationships: any[]; count: number }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_relationships', arguments: {} },
    }),

  getErDiagram: () =>
    apiRequest<{ success: boolean; nodes: any[]; edges: any[]; node_count: number; edge_count: number }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_er_diagram', arguments: {} },
    }),

  // dashboard-refinement PR2: aggregate statistics + per-object list endpoints
  getDatabaseStatistics: () =>
    apiRequest<DatabaseStatistics>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_database_statistics', arguments: {} },
    }),

  listForms: () =>
    apiRequest<ObjectListResponse>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_forms', arguments: {} },
    }),

  listReports: () =>
    apiRequest<ObjectListResponse>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_reports', arguments: {} },
    }),

  listMacros: () =>
    apiRequest<ObjectListResponse>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_macros', arguments: {} },
    }),

  listModules: () =>
    apiRequest<ObjectListResponse>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_modules', arguments: {} },
    }),
}

// Jobs API
export const jobsApi = {
  getJobs: () =>
    apiRequest<{ success: boolean; jobs: any[] }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'list_jobs', arguments: {} },
    }),

  getJobStatus: (jobId: string) =>
    apiRequest<{ success: boolean; job?: any }>('/mcp/tools/call', {
      method: 'POST',
      body: { name: 'get_migration_status', arguments: { job_id: jobId } },
    }),
}