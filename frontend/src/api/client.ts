// Native fetch API client — no axios, web standard only
const API_BASE = 'http://localhost:8000'

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(error.error || `HTTP ${response.status}`)
  }

  return response.json()
}

// Connection API
export const connectionApi = {
  connect: (databasePath: string, useCom = false) =>
    apiRequest<{ success: boolean; connected: boolean; database: string }>('/mcp/tools/call', {
      method: 'POST',
      body: {
        name: 'connect_access',
        arguments: { database_path: databasePath, use_com: useCom },
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