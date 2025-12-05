/**
 * Installation Types - Frontend-specific types for extension installation UI.
 *
 * ExtensionInstallation is a UI-specific type that differs from the generated API type:
 * - `id` is `string` (generated uses `number`) for compatibility with UI components
 * - `retry_count`, `extension_name` are non-optional with defaults
 *
 * The adapter in `api/adapters/installation.ts` converts between generated and legacy types.
 *
 * @module types/installation
 */

// Re-export status enum from generated API types (compatible)
export type { ExtensionInstallationStatusEnum } from '@/api/generated/model/extensionInstallationStatusEnum'

// ============================================================================
// UI-specific ExtensionInstallation Type
// ============================================================================

/**
 * UI-specific extension installation type.
 *
 * NOTE: This differs from the generated `ExtensionInstallation` type:
 * - `id`: string (generated has number) - for Table rowKey compatibility
 * - `retry_count`: number (generated has number | undefined)
 * - `extension_name`: string (generated has string | undefined)
 *
 * The adapter `convertInstallationToLegacy()` handles the conversion.
 */
export interface ExtensionInstallation {
  id: string
  database_id: string
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

// ============================================================================
// Frontend-only Types (not in backend API)
// ============================================================================

/**
 * Progress summary for batch installation operations.
 * Calculated on frontend from individual ExtensionInstallation records.
 */
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
  database_ids: string[] | 'all'
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
