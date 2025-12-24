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
  status?: string
}
