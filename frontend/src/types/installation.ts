export interface ExtensionInstallation {
  id: string
  database_id: number
  database_name: string
  extension_name: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  duration_seconds: number | null
  retry_count: number
  created_at: string
  updated_at: string
}

export interface InstallationProgress {
  total: number
  completed: number
  failed: number
  in_progress: number
  pending: number
  progress_percent: number
  estimated_time_remaining: number
}

export interface BatchInstallRequest {
  database_ids: number[] | 'all'
  extension_config: {
    name: string
    path: string
  }
}

export interface BatchInstallResponse {
  task_id: string
  total_databases: number
  status: string
}

export interface InstallSingleResponse {
  task_id: string
  operation_id: string
  message: string
  status: string
  queued_count?: number
}
