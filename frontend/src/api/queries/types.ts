export interface OperationFilters {
  search?: string
  filters?: Record<string, { op?: string; value?: unknown } | unknown>
  sort?: { key: string; order: 'asc' | 'desc' }
  status?: string
  created_by?: string
  operation_type?: string
  operation_id?: string
  workflow_execution_id?: string
  node_id?: string
  root_operation_id?: string
  execution_consumer?: string
  lane?: string
  limit?: number
  offset?: number
}

export interface DatabaseFilters {
  cluster_id?: string
  search?: string
  filters?: Record<string, { op?: string; value?: unknown } | unknown>
  sort?: { key: string; order: 'asc' | 'desc' }
  limit?: number
  offset?: number
}

export interface ClusterFilters {
  search?: string
  filters?: Record<string, { op?: string; value?: unknown } | unknown>
  sort?: { key: string; order: 'asc' | 'desc' }
  limit?: number
  offset?: number
}

export interface ArtifactFilters {
  kind?: string
  name?: string
  tag?: string
}
