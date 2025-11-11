import { apiClient } from '../client'

export interface Task {
  id: string
  database: string
  database_name: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'retry' | 'cancelled'
  result: any
  error_message: string
  error_code: string
  retry_count: number
  max_retries: number
  worker_id: string
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  created_at: string
  updated_at: string
}

export interface BatchOperation {
  id: string
  name: string
  description: string
  operation_type: 'create' | 'update' | 'delete' | 'query' | 'install_extension'
  target_entity: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  payload: any
  config: any
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  success_rate: number | null
  created_by: string
  metadata: any
  created_at: string
  updated_at: string
  database_names: string[]
  tasks: Task[]
}

// Legacy interface for backward compatibility
export interface Operation {
  id: string
  type: string
  status: string
  database: string
  payload: Record<string, any>
  result?: Record<string, any>
  error?: string
  created_at: string
  updated_at: string
}

export const operationsApi = {
  list: async (params?: Record<string, any>): Promise<BatchOperation[]> => {
    const response = await apiClient.get<BatchOperation[]>('/operations/', { params })
    return response.data
  },

  get: async (id: string): Promise<BatchOperation> => {
    const response = await apiClient.get<BatchOperation>(`/operations/${id}/`)
    return response.data
  },

  cancel: async (id: string): Promise<{ status: string }> => {
    const response = await apiClient.post<{ status: string }>(`/operations/${id}/cancel/`)
    return response.data
  }
}
