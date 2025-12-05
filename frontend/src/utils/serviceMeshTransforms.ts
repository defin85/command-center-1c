/**
 * Service Mesh Transforms - Convert generated API types to UI types.
 *
 * The generated API uses snake_case (e.g., display_name, ops_per_minute)
 * while the UI types use camelCase (e.g., displayName, opsPerMinute).
 *
 * This module provides transformation functions to bridge the gap.
 *
 * @module utils/serviceMeshTransforms
 */

import type {
  ServiceHistoryResponse,
  HistoryDataPoint as GeneratedHistoryDataPoint,
  OperationListResponse,
  BatchOperation,
} from '../api/generated'
import type {
  HistoricalMetricsResponse,
  HistoricalDataPoint,
  OperationsListResponse,
  ServiceOperation,
} from '../types/serviceMesh'

// ============================================================================
// History Transforms
// ============================================================================

/**
 * Transform a single historical data point from snake_case to camelCase.
 */
export function transformHistoricalDataPoint(
  data: GeneratedHistoryDataPoint
): HistoricalDataPoint {
  return {
    timestamp: data.timestamp,
    opsPerMinute: data.ops_per_minute ?? 0,
    p95LatencyMs: data.p95_latency_ms ?? 0,
    errorRate: data.error_rate ?? 0,
  }
}

/**
 * Transform ServiceHistoryResponse from generated API to UI type.
 */
export function transformServiceHistoryResponse(
  response: ServiceHistoryResponse
): HistoricalMetricsResponse {
  return {
    service: response.service,
    displayName: response.display_name,
    minutes: response.minutes,
    dataPoints: response.data_points.map(transformHistoricalDataPoint),
  }
}

// ============================================================================
// Operations Transforms
// ============================================================================

/**
 * Transform BatchOperation from generated API to ServiceOperation UI type.
 *
 * Note: The generated BatchOperation has a different structure than ServiceOperation.
 * We map the available fields and provide defaults for missing ones.
 */
export function transformBatchOperationToServiceOperation(
  data: BatchOperation
): ServiceOperation {
  return {
    id: data.id,
    name: data.name,
    operationType: data.operation_type,
    status: data.status,
    // BatchOperation doesn't have a 'service' field, derive from operation_type or use default
    service: deriveServiceFromOperation(data),
    durationSeconds: parseDurationSeconds(data.duration_seconds),
    createdAt: data.created_at,
    completedAt: data.completed_at ?? null,
    totalTasks: data.total_tasks,
    completedTasks: data.completed_tasks,
    failedTasks: data.failed_tasks,
    progress: data.progress,
  }
}

/**
 * Derive service name from operation type or metadata.
 * BatchOperation doesn't have explicit 'service' field.
 */
function deriveServiceFromOperation(data: BatchOperation): string {
  // Try to get from metadata if available
  if (data.metadata && typeof data.metadata === 'object') {
    const metadata = data.metadata as Record<string, unknown>
    if (typeof metadata.service === 'string') {
      return metadata.service
    }
  }

  // Map operation types to services
  const operationTypeToService: Record<string, string> = {
    'extension_install': 'worker',
    'health_check': 'orchestrator',
    'data_sync': 'worker',
    'backup': 'worker',
    'restore': 'worker',
  }

  return operationTypeToService[data.operation_type] || 'orchestrator'
}

/**
 * Parse duration_seconds string to number.
 * Generated API returns duration as string (e.g., "123.45").
 */
function parseDurationSeconds(duration: string): number | null {
  if (!duration) return null
  const parsed = parseFloat(duration)
  return isNaN(parsed) ? null : parsed
}

/**
 * Transform OperationListResponse from generated API to UI type.
 */
export function transformOperationListResponse(
  response: OperationListResponse
): OperationsListResponse {
  return {
    operations: response.operations.map(transformBatchOperationToServiceOperation),
    total: response.total,
  }
}
