/**
 * Installation API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides the same function signatures as endpoints/installation.ts
 * 3. Maps parameters to the v2 action-based endpoints
 * 4. Provides type transformations between generated and legacy types
 */

import { customInstance } from '../mutator'
// Import generated types
import type {
  ExtensionInstallation as GeneratedExtensionInstallation,
  ExtensionInstallationStatusEnum,
} from '../generated/model'

// Re-export generated types for direct use
export type { ExtensionInstallationStatusEnum }
export { ExtensionInstallationStatusEnum as InstallationStatusEnum } from '../generated/model'

// Import and re-export legacy types for UI component compatibility
export type {
  BatchInstallRequest,
  BatchInstallResponse,
  InstallationProgress,
  ExtensionInstallation,
  InstallSingleResponse,
} from '../../types/installation'

// Import legacy types for internal use
import type {
  BatchInstallRequest,
  BatchInstallResponse,
  InstallationProgress,
  ExtensionInstallation as LegacyExtensionInstallation,
  InstallSingleResponse,
} from '../../types/installation'

// ============================================================================
// Type Transformations (Generated <-> Legacy)
// ============================================================================

/**
 * Convert generated ExtensionInstallation to legacy format.
 * Handles differences in id type (number vs string) and status enum.
 */
function convertInstallationToLegacy(
  installation: GeneratedExtensionInstallation
): LegacyExtensionInstallation {
  return {
    id: String(installation.id),
    database_id: installation.database_id,
    database_name: installation.database_name,
    extension_name: installation.extension_name ?? 'ODataAutoConfig',
    status: (installation.status ?? 'pending') as LegacyExtensionInstallation['status'],
    started_at: installation.started_at,
    completed_at: installation.completed_at,
    error_message: installation.error_message ?? null,
    duration_seconds: installation.duration_seconds ?? null,
    retry_count: installation.retry_count ?? 0,
    created_at: installation.created_at,
    updated_at: installation.updated_at,
  }
}

// ============================================================================
// Installation API Response Types
// ============================================================================

interface BatchInstallApiResponse {
  task_id: string
  total: number
  queued: number
  installations: Array<{
    database_id: string
    installation_id: string
    status: string
  }>
}

interface InstallProgressApiResponse {
  task_id: string
  progress: InstallationProgress
  installations: Array<{
    database_id: string
    database_name: string
    status: string
    error_message?: string
  }>
}

interface InstallStatusApiResponse {
  database_id: string
  database_name: string
  installation: GeneratedExtensionInstallation | null
  history: GeneratedExtensionInstallation[]
}

interface ListExtensionsApiResponse {
  extensions: GeneratedExtensionInstallation[]
  count: number
  total: number
  summary: {
    pending: number
    in_progress: number
    completed: number
    failed: number
  }
}

interface RetryInstallationApiResponse {
  database_id: string
  installation_id: string
  status: string
  celery_task_id?: string
  message: string
}

interface InstallSingleApiResponse {
  task_id: string
  operation_id: string
  message: string
  status: string
  queued_count?: number
}

// ============================================================================
// Installation Endpoints
// ============================================================================

/**
 * Batch install extension to multiple databases.
 * POST /api/v2/extensions/batch-install/
 */
export const batchInstall = async (
  request: BatchInstallRequest
): Promise<BatchInstallResponse> => {
  const response = await customInstance<BatchInstallApiResponse>({
    url: '/api/v2/extensions/batch-install/',
    method: 'POST',
    data: {
      database_ids: request.database_ids,
      extension_name: request.extension_config.name,
      extension_path: request.extension_config.path,
    },
  })

  return {
    task_id: response.task_id,
    total_databases: response.total,
    status: 'queued',
  }
}

/**
 * Get progress of extension installations.
 * GET /api/v2/extensions/get-install-progress/?task_id={taskId}
 */
export const getProgress = async (taskId: string): Promise<InstallationProgress> => {
  const response = await customInstance<InstallProgressApiResponse>({
    url: '/api/v2/extensions/get-install-progress/',
    method: 'GET',
    params: { task_id: taskId },
  })

  return response.progress
}

/**
 * Get extension installation status for a specific database.
 * GET /api/v2/extensions/get-install-status/?database_id={databaseId}
 */
export const getDatabaseStatus = async (
  databaseId: string
): Promise<LegacyExtensionInstallation | null> => {
  try {
    const response = await customInstance<InstallStatusApiResponse>({
      url: '/api/v2/extensions/get-install-status/',
      method: 'GET',
      params: { database_id: databaseId },
    })

    if (!response.installation) {
      return null
    }

    return convertInstallationToLegacy(response.installation)
  } catch (error: unknown) {
    // If installation not found, return null
    if (
      error &&
      typeof error === 'object' &&
      'response' in error &&
      (error as { response?: { status?: number } }).response?.status === 404
    ) {
      return null
    }
    throw error
  }
}

/**
 * Retry extension installation for a specific database.
 * POST /api/v2/extensions/retry-installation/
 */
export const retryInstallation = async (
  databaseId: string
): Promise<RetryInstallationApiResponse> => {
  return customInstance<RetryInstallationApiResponse>({
    url: '/api/v2/extensions/retry-installation/',
    method: 'POST',
    data: { database_id: databaseId },
  })
}

/**
 * Install extension to a single database.
 * POST /api/v2/extensions/install-single/
 */
export const installSingle = async (
  databaseId: string,
  extensionConfig: { name: string; path: string }
): Promise<InstallSingleResponse> => {
  return customInstance<InstallSingleApiResponse>({
    url: '/api/v2/extensions/install-single/',
    method: 'POST',
    data: {
      database_id: databaseId,
      extension_name: extensionConfig.name,
      extension_path: extensionConfig.path,
    },
  })
}

/**
 * Get all extension installations.
 * GET /api/v2/extensions/list-extensions/
 */
export const getAllInstallations = async (): Promise<LegacyExtensionInstallation[]> => {
  const response = await customInstance<ListExtensionsApiResponse>({
    url: '/api/v2/extensions/list-extensions/',
    method: 'GET',
  })

  return response.extensions.map(convertInstallationToLegacy)
}

// ============================================================================
// Legacy API Object (for backward compatibility)
// ============================================================================

/**
 * Installation API object for backward compatibility with endpoints/installation.ts
 * @deprecated Use individual exported functions instead
 */
export const installationApi = {
  batchInstall,
  getProgress,
  getDatabaseStatus,
  retryInstallation,
  installSingle,
  getAllInstallations,
}

export default installationApi
