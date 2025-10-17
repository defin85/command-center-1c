export type OperationStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
export type OperationType = 'create' | 'update' | 'delete' | 'query'
export type DatabaseStatus = 'active' | 'inactive' | 'error'

export interface ApiError {
  message: string
  code?: string
  details?: Record<string, any>
}

export interface PaginatedResponse<T> {
  count: number
  next?: string
  previous?: string
  results: T[]
}
