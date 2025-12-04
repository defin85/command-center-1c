/**
 * Service Mesh API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides the same function signatures as endpoints/serviceMesh.ts
 * 3. Maps parameters to the v2 action-based endpoints
 * 4. Preserves type transformations between snake_case API and camelCase UI types
 *
 * Note: Generated types for service-mesh endpoints return void, so we keep
 * using legacy types from types/serviceMesh.ts for proper typing.
 */

import { customInstance } from '../mutator'
import type {
  ServiceMeshState,
  HistoricalMetricsResponse,
  OperationsListResponse,
  ServiceMetrics,
  ServiceConnection,
  HistoricalDataPoint,
  ServiceOperation,
} from '../../types/serviceMesh'

// Re-export all types and constants from serviceMesh types for convenience
export type {
  ServiceMeshState,
  HistoricalMetricsResponse,
  OperationsListResponse,
  ServiceMetrics,
  ServiceConnection,
  HistoricalDataPoint,
  ServiceOperation,
  ServiceStatus,
  ServiceMeshMessageType,
  ServiceMeshWSMessage,
  ServiceMeshWSAction,
  ServiceMeshWSRequest,
  ServiceNodePosition,
  ServiceNodeData,
  ServiceLayoutConfig,
  ServiceDisplayConfig,
} from '../../types/serviceMesh'

// Re-export constants for UI components
export {
  DEFAULT_SERVICE_POSITIONS,
  SERVICE_DISPLAY_CONFIG,
  STATUS_COLORS,
  STATUS_TEXT,
} from '../../types/serviceMesh'

// ============================================================================
// API Response Types (snake_case from backend)
// ============================================================================

interface ServiceMetricsResponse {
  name: string
  display_name: string
  status: 'healthy' | 'degraded' | 'critical'
  ops_per_minute: number
  active_operations: number
  p95_latency_ms: number
  error_rate: number
  last_updated: string
}

interface ServiceConnectionResponse {
  source: string
  target: string
  requests_per_minute: number
  avg_latency_ms: number
}

interface MeshMetricsAPIResponse {
  services: ServiceMetricsResponse[]
  connections: ServiceConnectionResponse[]
  overall_health: 'healthy' | 'degraded' | 'critical'
  timestamp: string
  error?: string
}

interface HistoricalDataPointResponse {
  timestamp: string
  ops_per_minute: number
  p95_latency_ms: number
  error_rate: number
}

interface HistoricalAPIResponse {
  service: string
  display_name: string
  minutes: number
  data_points: HistoricalDataPointResponse[]
  error?: string
}

interface ServiceOperationResponse {
  id: string
  name: string
  operation_type: string
  status: string
  service: string
  duration_seconds: number | null
  created_at: string | null
  completed_at: string | null
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  progress: number
}

/**
 * Response from /operations/list-operations/ endpoint
 * Has 'count' instead of just 'total'
 */
interface ListOperationsAPIResponse {
  operations: ServiceOperationResponse[]
  count: number
  total: number
}

// ============================================================================
// Type Transformations (snake_case API -> camelCase UI)
// ============================================================================

/**
 * Transform snake_case API response to camelCase ServiceMetrics
 */
function transformServiceMetrics(data: ServiceMetricsResponse): ServiceMetrics {
  return {
    name: data.name,
    displayName: data.display_name,
    status: data.status,
    opsPerMinute: data.ops_per_minute,
    activeOperations: data.active_operations,
    p95LatencyMs: data.p95_latency_ms,
    errorRate: data.error_rate,
    lastUpdated: data.last_updated,
  }
}

/**
 * Transform snake_case API response to camelCase ServiceConnection
 */
function transformServiceConnection(data: ServiceConnectionResponse): ServiceConnection {
  return {
    source: data.source,
    target: data.target,
    requestsPerMinute: data.requests_per_minute,
    avgLatencyMs: data.avg_latency_ms,
  }
}

/**
 * Transform snake_case API response to camelCase HistoricalDataPoint
 */
function transformHistoricalDataPoint(data: HistoricalDataPointResponse): HistoricalDataPoint {
  return {
    timestamp: data.timestamp,
    opsPerMinute: data.ops_per_minute,
    p95LatencyMs: data.p95_latency_ms,
    errorRate: data.error_rate,
  }
}

/**
 * Transform snake_case API response to camelCase ServiceOperation
 */
function transformOperation(data: ServiceOperationResponse): ServiceOperation {
  return {
    id: data.id,
    name: data.name,
    operationType: data.operation_type,
    status: data.status,
    service: data.service,
    durationSeconds: data.duration_seconds,
    createdAt: data.created_at,
    completedAt: data.completed_at,
    totalTasks: data.total_tasks,
    completedTasks: data.completed_tasks,
    failedTasks: data.failed_tasks,
    progress: data.progress,
  }
}

// ============================================================================
// Service Mesh API Functions
// ============================================================================

/**
 * Get current service mesh metrics for all services.
 *
 * Maps to: GET /api/v2/service-mesh/get-metrics/
 */
export const getServiceMeshMetrics = async (): Promise<ServiceMeshState> => {
  const response = await customInstance<MeshMetricsAPIResponse>({
    url: '/api/v2/service-mesh/get-metrics/',
    method: 'GET',
  })

  return {
    services: response.services.map(transformServiceMetrics),
    connections: response.connections.map(transformServiceConnection),
    overallHealth: response.overall_health,
    timestamp: response.timestamp,
    error: response.error,
  }
}

/**
 * Get historical metrics for a specific service.
 *
 * Maps to: GET /api/v2/service-mesh/get-history/
 *
 * @param service - Service name (e.g., 'api-gateway', 'worker')
 * @param minutes - Number of minutes of history (default: 30)
 */
export const getServiceHistory = async (
  service: string,
  minutes: number = 30
): Promise<HistoricalMetricsResponse> => {
  const response = await customInstance<HistoricalAPIResponse>({
    url: '/api/v2/service-mesh/get-history/',
    method: 'GET',
    params: { service, minutes },
  })

  return {
    service: response.service,
    displayName: response.display_name,
    minutes: response.minutes,
    dataPoints: response.data_points.map(transformHistoricalDataPoint),
    error: response.error,
  }
}

/**
 * Get recent operations, optionally filtered by status.
 *
 * Maps to: GET /api/v2/operations/list-operations/
 *
 * @param limit - Maximum number of operations to return (default: 50)
 * @param status - Optional status filter
 */
export const getServiceOperations = async (
  limit: number = 50,
  status?: string
): Promise<OperationsListResponse> => {
  const params: Record<string, string | number> = { limit }

  if (status) {
    params.status = status
  }

  const response = await customInstance<ListOperationsAPIResponse>({
    url: '/api/v2/operations/list-operations/',
    method: 'GET',
    params,
  })

  return {
    operations: response.operations.map(transformOperation),
    total: response.total,
  }
}

// ============================================================================
// Service Mesh API Object (for convenient imports)
// ============================================================================

/**
 * Service Mesh API object for convenient imports.
 *
 * Usage:
 *   import { serviceMeshApi } from '../api/adapters/serviceMesh'
 *   const metrics = await serviceMeshApi.getMetrics()
 */
export const serviceMeshApi = {
  getMetrics: getServiceMeshMetrics,
  getHistory: getServiceHistory,
  getOperations: getServiceOperations,
}

export default serviceMeshApi
