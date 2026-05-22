// TypeScript interfaces for API responses
export interface ConnectionResponse {
  connected: boolean
  database?: string
}

export interface TableField {
  name: string
  type: string
  size: number
  required: boolean
  allow_zero_length: boolean
}

export interface TableInfo {
  name: string
  fields: TableField[]
  record_count: number
}

export interface TablesResponse {
  success: boolean
  tables: TableInfo[]
  count: number
}

export interface TableSchemaResponse {
  success: boolean
  table?: TableInfo
  error?: string
}

export interface QueryInfo {
  name: string
  sql: string
  type: string
}

export interface QueriesResponse {
  success: boolean
  queries: QueryInfo[]
  count: number
}

export interface RelationshipInfo {
  name: string
  table: string
  foreign_table: string
  attributes: string
}

export interface RelationshipsResponse {
  success: boolean
  relationships: RelationshipInfo[]
  count: number
}

export interface Job {
  id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  created_at: string
  completed_at?: string
  error?: string
}

export interface JobsResponse {
  success: boolean
  jobs: Job[]
}