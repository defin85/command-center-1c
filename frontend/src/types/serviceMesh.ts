/**
 * Types for Service Mesh monitoring.
 *
 * These types mirror the backend data structures from:
 * - orchestrator/apps/operations/services/prometheus_client.py
 * - orchestrator/apps/operations/views/service_mesh.py
 */

/**
 * Service health status
 */
export type ServiceStatus = 'healthy' | 'degraded' | 'critical'

/**
 * Metrics for a single service in the mesh
 */
export interface ServiceMetrics {
  name: string
  displayName: string
  status: ServiceStatus
  opsPerMinute: number
  activeOperations: number
  p95LatencyMs: number
  errorRate: number // 0.0 - 1.0
  lastUpdated: string // ISO timestamp
}

/**
 * Connection between two services with traffic metrics
 */
export interface ServiceConnection {
  source: string
  target: string
  requestsPerMinute: number
  avgLatencyMs: number
}

/**
 * Complete state of the service mesh
 */
export interface ServiceMeshState {
  services: ServiceMetrics[]
  connections: ServiceConnection[]
  overallHealth: ServiceStatus
  timestamp: string
  error?: string
}

/**
 * Historical data point for charts
 */
export interface HistoricalDataPoint {
  timestamp: string
  opsPerMinute: number
  p95LatencyMs: number
  errorRate: number
}

/**
 * Historical metrics response from API
 */
export interface HistoricalMetricsResponse {
  service: string
  displayName: string
  minutes: number
  dataPoints: HistoricalDataPoint[]
  error?: string
}

/**
 * Operation summary for recent operations table
 */
export interface ServiceOperation {
  id: string
  name: string
  operationType: string
  status: string
  service: string
  durationSeconds: number | null
  createdAt: string | null
  completedAt: string | null
  totalTasks: number
  completedTasks: number
  failedTasks: number
  progress: number
}

/**
 * Operations list response from API
 */
export interface OperationsListResponse {
  operations: ServiceOperation[]
  total: number
}

/**
 * WebSocket message types
 */
export type ServiceMeshMessageType =
  | 'metrics_update'
  | 'interval_updated'
  | 'error'
  | 'pong'

/**
 * WebSocket message from server
 */
export interface ServiceMeshWSMessage {
  type: ServiceMeshMessageType
  services?: ServiceMetrics[]
  connections?: ServiceConnection[]
  overallHealth?: ServiceStatus
  timestamp?: string
  error?: string
  interval?: number
  code?: string
  message?: string
}

/**
 * WebSocket actions that can be sent to server
 */
export type ServiceMeshWSAction = 'get_metrics' | 'ping' | 'set_interval'

/**
 * WebSocket message to server
 */
export interface ServiceMeshWSRequest {
  action: ServiceMeshWSAction
  interval?: number
}

/**
 * Node position in the flow diagram
 */
export interface ServiceNodePosition {
  x: number
  y: number
}

/**
 * Service node data for react-flow
 */
export interface ServiceNodeData {
  metrics: ServiceMetrics
  onSelect: (service: string) => void
  isSelected: boolean
}

/**
 * Configuration for service layout in diagram
 */
export interface ServiceLayoutConfig {
  [serviceName: string]: ServiceNodePosition
}

/**
 * Default service positions for the flow diagram
 */
export const DEFAULT_SERVICE_POSITIONS: ServiceLayoutConfig = {
  frontend: { x: 350, y: 50 },
  'api-gateway': { x: 350, y: 150 },
  orchestrator: { x: 150, y: 300 },
  worker: { x: 350, y: 300 },
  'ras-adapter': { x: 550, y: 300 },
}

/**
 * Service display configuration
 */
export interface ServiceDisplayConfig {
  name: string
  displayName: string
  icon: string
  description: string
}

/**
 * All service display configurations
 */
export const SERVICE_DISPLAY_CONFIG: Record<string, ServiceDisplayConfig> = {
  frontend: {
    name: 'frontend',
    displayName: 'Frontend',
    icon: 'desktop',
    description: 'React web application',
  },
  'api-gateway': {
    name: 'api-gateway',
    displayName: 'API Gateway',
    icon: 'gateway',
    description: 'HTTP routing and authentication',
  },
  orchestrator: {
    name: 'orchestrator',
    displayName: 'Orchestrator',
    icon: 'apartment',
    description: 'Django task coordination',
  },
  worker: {
    name: 'worker',
    displayName: 'Worker',
    icon: 'thunderbolt',
    description: 'Go parallel task executor',
  },
  'ras-adapter': {
    name: 'ras-adapter',
    displayName: 'RAS Adapter',
    icon: 'api',
    description: '1C cluster management',
  },
}

/**
 * Status color mapping
 */
export const STATUS_COLORS: Record<ServiceStatus, string> = {
  healthy: '#52c41a',
  degraded: '#faad14',
  critical: '#ff4d4f',
}

/**
 * Status text mapping
 */
export const STATUS_TEXT: Record<ServiceStatus, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  critical: 'Critical',
}
