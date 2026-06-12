// API client with cookie-based authentication (no localStorage).
// All requests use credentials: 'include' to send session cookies.
//401 responses redirect to /login instead of dispatching auth:required.
import type {
  DatabaseStatistics,
  ObjectListResponse,
  TablesResponse,
  TableSchemaResponse,
  RelationshipsResponse,
  JobsResponse,
  Job,
} from './types'

const API_BASE = ''

// --- Error handling ---

function isUnauthorized(response: Response): boolean {
  return response.status === 401
}

function isForbidden(response: Response): boolean {
  return response.status === 403
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json()
      message = body.error || message
    } catch {
      // ignore parse errors
    }

    if (isUnauthorized(response)) {
      // Redirect to login on 401 — guard with try/catch for jsdom test environment
      try {
        window.location.href = '/login'
      } catch {
        // Navigation not implemented in jsdom — ignore
      }
    }

    throw new Error(message)
  }
  return response.json() as Promise<T>
}

// --- Core request helper ---
// Does NOT read or write localStorage. Uses session cookie via credentials: include.

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  return handleResponse<T>(response)
}

// --- Login API ---

export const loginApi = {
  login: (apiKey: string): Promise<{ success: boolean }> =>
    apiRequest<{ success: boolean }>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey }),
    }),

  logout: (): Promise<{ success: boolean }> =>
    apiRequest<{ success: boolean }>('/api/logout', {
      method: 'POST',
    }),
}

// --- Tools API (cookie-auth proxy) ---

export const toolsApi = {
  call: <T = unknown>(name: string, arguments_: Record<string, unknown>): Promise<T> =>
    apiRequest<T>('/api/tools/call', {
      method: 'POST',
      body: JSON.stringify({ name, arguments: arguments_ }),
    }),
}

// --- Connection API ---

export const connectionApi = {
  connect: (databasePath: string, useCom = false, password = ''): Promise<{ success: boolean; connected: boolean; database: string }> =>
    toolsApi.call<{ success: boolean; connected: boolean; database: string }>('connect_access', {
      database_path: databasePath,
      use_com: useCom,
      password,
    }),

  disconnect: (): Promise<{ success: boolean; message: string }> =>
    toolsApi.call<{ success: boolean; message: string }>('disconnect_access', {}),

  isConnected: (): Promise<{ connected: boolean; database?: string }> =>
    toolsApi.call<{ connected: boolean; database?: string }>('is_connected', {}),
}

// --- Schema API ---

export const schemaApi = {
  getTables: (): Promise<TablesResponse> =>
    toolsApi.call<TablesResponse>('get_tables', {}),

  getTableSchema: (tableName: string): Promise<TableSchemaResponse> =>
    toolsApi.call<TableSchemaResponse>('get_table_schema', { table_name: tableName }),

  getQueries: (): Promise<{ success: boolean; queries: any[]; count: number }> =>
    toolsApi.call('get_queries', {}),

  getRelationships: (): Promise<RelationshipsResponse> =>
    toolsApi.call<RelationshipsResponse>('get_relationships', {}),

  getErDiagram: (): Promise<{ success: boolean; nodes: any[]; edges: any[]; node_count: number; edge_count: number }> =>
    toolsApi.call('get_er_diagram', {}),

  getDatabaseStatistics: (): Promise<DatabaseStatistics> =>
    toolsApi.call<DatabaseStatistics>('get_database_statistics', {}),

  listForms: (): Promise<ObjectListResponse> =>
    toolsApi.call<ObjectListResponse>('get_forms', {}),

  listReports: (): Promise<ObjectListResponse> =>
    toolsApi.call<ObjectListResponse>('get_reports', {}),

  listMacros: (): Promise<ObjectListResponse> =>
    toolsApi.call<ObjectListResponse>('get_macros', {}),

  listModules: (): Promise<ObjectListResponse> =>
    toolsApi.call<ObjectListResponse>('get_modules', {}),
}

// --- Jobs API ---

export const jobsApi = {
  getJobs: (): Promise<JobsResponse> =>
    toolsApi.call<JobsResponse>('list_jobs', {}),

  getJobStatus: (jobId: string): Promise<{ success: boolean; job?: Job }> =>
    toolsApi.call<{ success: boolean; job?: Job }>('get_migration_status', { job_id: jobId }),
}

// Expose on window for Alpine.js templates that call apiClient.listForms() etc.
// Only needed for IIFE build; the module export is used for testing.
declare global {
  interface Window {
    loginApi: typeof loginApi
    schemaApi: typeof schemaApi
    connectionApi: typeof connectionApi
    jobsApi: typeof jobsApi
    toolsApi: typeof toolsApi
  }
}

if (typeof window !== 'undefined') {
  window.loginApi = loginApi
  window.schemaApi = schemaApi
  window.connectionApi = connectionApi
  window.jobsApi = jobsApi
  window.toolsApi = toolsApi
}
