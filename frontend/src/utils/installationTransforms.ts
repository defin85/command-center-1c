/**
 * Installation API Transforms.
 *
 * Utility functions to transform between generated API types and legacy UI types.
 * These transforms maintain backward compatibility while migrating to generated API.
 *
 * @module utils/installationTransforms
 */

import type {
  ExtensionInstallation as GeneratedExtensionInstallation,
  InstallProgressStats,
  InstallStatusResponse,
  BatchInstallResponse as GeneratedBatchInstallResponse,
} from '@/api/generated/model'

import type {
  ExtensionInstallation as LegacyExtensionInstallation,
  InstallationProgress,
  BatchInstallResponse as LegacyBatchInstallResponse,
} from '@/types/installation'

// ============================================================================
// ID Normalization
// ============================================================================

/**
 * Normalize installation ID to string format.
 * Generated API uses number, legacy UI uses string.
 */
export function normalizeInstallationId(id: number | string): string {
  return String(id)
}

// ============================================================================
// ExtensionInstallation Transforms
// ============================================================================

/**
 * Convert generated ExtensionInstallation to legacy UI format.
 * Handles differences in id type (number vs string) and optional fields.
 */
export function convertInstallationToLegacy(
  installation: GeneratedExtensionInstallation
): LegacyExtensionInstallation {
  return {
    id: normalizeInstallationId(installation.id),
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

/**
 * Convert array of generated ExtensionInstallations to legacy format.
 */
export function convertInstallationsToLegacy(
  installations: GeneratedExtensionInstallation[]
): LegacyExtensionInstallation[] {
  return installations.map(convertInstallationToLegacy)
}

// ============================================================================
// Progress Transforms
// ============================================================================

/**
 * Convert generated InstallProgressStats to legacy InstallationProgress format.
 * Handles field name differences and adds estimated_time_remaining.
 */
export function convertProgressToLegacy(
  progress: InstallProgressStats
): InstallationProgress {
  return {
    total: progress.total,
    completed: progress.completed,
    failed: progress.failed,
    in_progress: progress.in_progress,
    pending: progress.pending,
    progress_percent: progress.percent_complete,
    // Estimate: 30 seconds per remaining database
    estimated_time_remaining: (progress.pending + progress.in_progress) * 30,
  }
}

// ============================================================================
// BatchInstallResponse Transforms
// ============================================================================

/**
 * Convert generated BatchInstallResponse to legacy format.
 * Maps batch_id to task_id and queued to total_databases.
 */
export function convertBatchResponseToLegacy(
  response: GeneratedBatchInstallResponse
): LegacyBatchInstallResponse {
  return {
    task_id: response.batch_id,
    total_databases: response.queued,
    status: 'queued',
  }
}

// ============================================================================
// InstallStatusResponse Transforms
// ============================================================================

/**
 * Extract legacy ExtensionInstallation from InstallStatusResponse.
 * Returns null if no installation exists.
 *
 * Note: InstallStatusResponseInstallation is ExtensionInstallation | null
 */
export function extractInstallationFromStatus(
  response: InstallStatusResponse
): LegacyExtensionInstallation | null {
  if (!response.installation) {
    return null
  }

  // response.installation is ExtensionInstallation when not null
  return convertInstallationToLegacy(response.installation)
}
