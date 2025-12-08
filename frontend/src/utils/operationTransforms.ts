/**
 * Utility functions for transforming operation data from generated API types.
 *
 * The API returns some fields as strings that need to be parsed for UI usage:
 * - database_names: JSON string -> string[]
 * - duration_seconds: string -> number | null
 * - success_rate: string -> number | null
 */

import type {
  BatchOperation as GeneratedBatchOperation,
  Task as GeneratedTask,
} from '../api/generated/model'

// ============================================================================
// UI Types (with transformed fields)
// ============================================================================

/**
 * Task type for UI components.
 * Matches the format expected by Operations.tsx
 */
export interface UITask {
  id: string
  database: string
  database_name: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'retry' | 'cancelled'
  result: unknown
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

/**
 * BatchOperation type for UI components.
 * Matches the format expected by Operations.tsx
 */
export interface UIBatchOperation {
  id: string
  name: string
  description: string
  operation_type: 'create' | 'update' | 'delete' | 'query' | 'install_extension' | 'lock_scheduled_jobs' | 'unlock_scheduled_jobs' | 'terminate_sessions' | 'block_sessions' | 'unblock_sessions'
  target_entity: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  payload: unknown
  config: unknown
  task_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  success_rate: number | null
  created_by: string
  metadata: unknown
  created_at: string
  updated_at: string
  database_names: string[]
  tasks: UITask[]
}

// ============================================================================
// Transform Functions
// ============================================================================

/**
 * Parse database_names from API (string | string[]) to string[].
 * API may return JSON string or already parsed array.
 */
export function parseDatabaseNames(value: string | string[] | undefined): string[] {
  if (!value) return []
  if (Array.isArray(value)) return value
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : [value]
  } catch {
    return value ? [value] : []
  }
}

/**
 * Parse numeric field from string to number | null.
 * API returns duration_seconds and success_rate as strings.
 */
export function parseNumericField(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const num = typeof value === 'string' ? parseFloat(value) : value
  return Number.isNaN(num) ? null : num
}

/**
 * Convert generated Task to UI Task format.
 */
export function transformTask(task: GeneratedTask): UITask {
  return {
    id: task.id,
    database: task.database,
    database_name: task.database_name,
    status: task.status as UITask['status'],
    result: task.result,
    error_message: task.error_message ?? '',
    error_code: task.error_code ?? '',
    retry_count: task.retry_count ?? 0,
    max_retries: task.max_retries ?? 3,
    worker_id: task.worker_id ?? '',
    started_at: task.started_at ?? null,
    completed_at: task.completed_at ?? null,
    duration_seconds: task.duration_seconds ?? null,
    created_at: task.created_at,
    updated_at: task.updated_at,
  }
}

/**
 * Convert generated BatchOperation to UI BatchOperation format.
 */
export function transformBatchOperation(op: GeneratedBatchOperation): UIBatchOperation {
  return {
    id: op.id,
    name: op.name,
    description: op.description ?? '',
    operation_type: op.operation_type as UIBatchOperation['operation_type'],
    target_entity: op.target_entity,
    status: op.status as UIBatchOperation['status'],
    progress: op.progress,
    total_tasks: op.total_tasks,
    completed_tasks: op.completed_tasks,
    failed_tasks: op.failed_tasks,
    payload: op.payload,
    config: op.config,
    task_id: op.task_id ?? null,
    started_at: op.started_at ?? null,
    completed_at: op.completed_at ?? null,
    duration_seconds: parseNumericField(op.duration_seconds),
    success_rate: parseNumericField(op.success_rate),
    created_by: op.created_by ?? '',
    metadata: op.metadata,
    created_at: op.created_at,
    updated_at: op.updated_at,
    database_names: parseDatabaseNames(op.database_names),
    tasks: op.tasks ? op.tasks.map(transformTask) : [],
  }
}
