/**
 * Service Mesh API endpoints.
 *
 * Provides functions for fetching service mesh metrics, history, and operations.
 */
import { apiClient } from '../client'
import type {
  ServiceMeshState,
  HistoricalMetricsResponse,
  OperationsListResponse,
  ServiceMetrics,
  ServiceConnection,
  HistoricalDataPoint,
  ServiceOperation,
} from '../../types/serviceMesh'

/**
 * API response types (snake_case from backend)
 */
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

/**
 * Transform snake_case API response to camelCase
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

function transformServiceConnection(data: ServiceConnectionResponse): ServiceConnection {
  return {
    source: data.source,
    target: data.target,
    requestsPerMinute: data.requests_per_minute,
    avgLatencyMs: data.avg_latency_ms,
  }
}

function transformHistoricalDataPoint(data: HistoricalDataPointResponse): HistoricalDataPoint {
  return {
    timestamp: data.timestamp,
    opsPerMinute: data.ops_per_minute,
    p95LatencyMs: data.p95_latency_ms,
    errorRate: data.error_rate,
  }
}

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

/**
 * Get current service mesh metrics for all services
 */
export const getServiceMeshMetrics = async (): Promise<ServiceMeshState> => {
  const response = await apiClient.get<MeshMetricsAPIResponse>('/service-mesh/get-metrics/')

  return {
    services: response.data.services.map(transformServiceMetrics),
    connections: response.data.connections.map(transformServiceConnection),
    overallHealth: response.data.overall_health,
    timestamp: response.data.timestamp,
    error: response.data.error,
  }
}

/**
 * Get historical metrics for a specific service
 *
 * @param service - Service name (e.g., 'api-gateway', 'worker')
 * @param minutes - Number of minutes of history (default: 30)
 */
export const getServiceHistory = async (
  service: string,
  minutes: number = 30
): Promise<HistoricalMetricsResponse> => {
  const response = await apiClient.get<HistoricalAPIResponse>(
    '/service-mesh/get-history/',
    { params: { service, minutes } }
  )

  return {
    service: response.data.service,
    displayName: response.data.display_name,
    minutes: response.data.minutes,
    dataPoints: response.data.data_points.map(transformHistoricalDataPoint),
    error: response.data.error,
  }
}

/**
 * Get recent operations, optionally filtered by status
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

  const response = await apiClient.get<ListOperationsAPIResponse>(
    '/operations/list-operations/',
    { params }
  )

  return {
    operations: response.data.operations.map(transformOperation),
    total: response.data.total,
  }
}

/**
 * Service Mesh API object for convenient imports
 */
export const serviceMeshApi = {
  getMetrics: getServiceMeshMetrics,
  getHistory: getServiceHistory,
  getOperations: getServiceOperations,
}

export default serviceMeshApi
