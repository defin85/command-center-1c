export interface OperationFilters {
  status?: string
  operation_type?: string
  operation_id?: string
  workflow_execution_id?: string
  node_id?: string
  limit?: number
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
