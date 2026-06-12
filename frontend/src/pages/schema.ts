// Alpine.js schema explorer page — cookie-based auth, no localStorage.
// Mounted by the SSR template at schema.html via<script src="/dist/assets/schema.js">
import { schemaApi } from '../api/apiClient'
import type { TablesResponse, TableSchemaResponse } from '../api/types'

/**
 * Load all tables.
 * @throws Error on 401 (redirects to /login via apiClient).
 */
export async function loadTables(): Promise<TablesResponse> {
  return schemaApi.getTables()
}

/**
 * Load schema for a specific table.
 * @throws Error on 401 (redirects to /login via apiClient).
 */
export async function loadTableSchema(tableName: string): Promise<TableSchemaResponse> {
  return schemaApi.getTableSchema(tableName)
}

/**
 * Filter tables by search query (case-insensitive).
 */
export function filterTables(tables: any[], query: string): any[] {
  if (!query) return tables
  const lower = query.toLowerCase()
  return tables.filter((t) => t.name.toLowerCase().includes(lower))
}

// Expose globally for Alpine.js inline templates
declare global {
  interface Window {
    loadTables: typeof loadTables
    loadTableSchema: typeof loadTableSchema
    filterTables: typeof filterTables
  }
}

if (typeof window !== 'undefined') {
  window.loadTables = loadTables
  window.loadTableSchema = loadTableSchema
  window.filterTables = filterTables
}
