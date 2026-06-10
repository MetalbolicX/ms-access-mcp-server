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

// Database statistics (dashboard-refinement PR1 response shape)
export interface DatabaseStatistics {
  success: boolean
  objects: {
    tables: number
    queries: number
    forms: number
    reports: number
    macros: number
    modules: number
  }
  file: {
    name: string
    size_bytes: number
    modified: string
  }
  system: {
    access_version: string | null
    com_available: boolean
  }
}

// Generic object-name list (forms, reports, macros, modules)
export interface ObjectListResponse {
  success: boolean
  items: string[]
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

// ER Diagram types
export interface ERNode {
  id: string
  type: 'table'
  data: {
    label: string
    columns: TableField[]
    record_count: number
  }
}

export interface EREdge {
  id: string
  source: string
  target: string
  label: string
  animated: boolean
}

export interface ERDiagramResponse {
  success: boolean
  nodes: ERNode[]
  edges: EREdge[]
  node_count: number
  edge_count: number
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