/**
 * Service Mesh Types - Frontend-specific types for service mesh visualization.
 *
 * IMPORTANT: These types are NOT generated from OpenAPI because the service mesh
 * monitoring uses Prometheus metrics and WebSocket streams, not REST API.
 *
 * This file contains:
 * - Prometheus metrics types (ServiceMetrics, ServiceConnection)
 * - WebSocket message types (ServiceMeshWSMessage, ServiceMeshWSRequest)
 * - React Flow diagram types (ServiceNodeData, ServiceLayoutConfig)
 * - UI constants (STATUS_COLORS, DEFAULT_SERVICE_POSITIONS)
 *
 * Related backend:
 * - orchestrator/apps/operations/services/prometheus_client.py
 * - orchestrator/apps/operations/views/service_mesh.py
 *
 * @module types/serviceMesh
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
  | 'operation_flow_update'
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

  // Operation flow fields (for operation_flow_update)
  operation_id?: string
  flow?: {
    current_service: string
    path: Array<{ service: string; status: string; timestamp: string }>
    edges: Array<{ from: string; to: string; status: string }>
  }
  operation?: {
    type: string
    name: string
    status: string
    message: string
    metadata?: Record<string, unknown>
  }
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
 * Operation flow path node status
 */
export type OperationFlowStatus = 'pending' | 'active' | 'completed' | 'failed'

/**
 * Single node in operation flow path
 */
export interface OperationFlowPath {
  service: string
  status: OperationFlowStatus
  timestamp: string
}

/**
 * Edge in operation flow (connection between services)
 */
export interface OperationFlowEdge {
  from: string
  to: string
  status: OperationFlowStatus
}

/**
 * Complete flow data for an operation
 */
export interface OperationFlowData {
  currentService: string
  path: OperationFlowPath[]
  edges: OperationFlowEdge[]
}

/**
 * Operation details in flow event
 */
export interface OperationFlowOperation {
  type: string
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message: string
  metadata?: Record<string, unknown>
}

/**
 * WebSocket message for operation flow update
 */
export interface OperationFlowEvent {
  version: string
  type: 'operation_flow_update'
  operation_id: string
  timestamp: string
  flow: OperationFlowData
  operation: OperationFlowOperation
}

/**
 * Service node data for react-flow
 */
export interface ServiceNodeData {
  metrics: ServiceMetrics
  onSelect: (service: string) => void
  isSelected: boolean
  operationStatus?: OperationFlowStatus | null
  onMouseEnter?: () => void
  onMouseLeave?: () => void
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
  // Level 0: Client (top center)
  frontend: { x: 400, y: 50 },

  // Level 1: Entry Point
  'api-gateway': { x: 400, y: 150 },

  // Level 2: Orchestrator (center - main hub)
  orchestrator: { x: 400, y: 280 },

  // Level 3: Infrastructure + Worker (horizontal)
  postgresql: { x: 200, y: 410 },
  redis: { x: 400, y: 410 },
  worker: { x: 600, y: 410 },

  // Level 4: Worker children (bottom)
  'ras-adapter': { x: 500, y: 540 },
  'batch-service': { x: 700, y: 540 },
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
  'batch-service': {
    name: 'batch-service',
    displayName: 'Batch Service',
    icon: 'build',
    description: 'Extension installation via 1cv8.exe',
  },
  postgresql: {
    name: 'postgresql',
    displayName: 'PostgreSQL',
    icon: 'database',
    description: 'Primary database (port 5432)',
  },
  redis: {
    name: 'redis',
    displayName: 'Redis',
    icon: 'cloud-server',
    description: 'Queue and cache (port 6379)',
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

/**
 * Connection type between services
 */
export type ConnectionType = 'http' | 'queue' | 'database' | 'pubsub'

/**
 * Color mapping for connection types
 */
export const CONNECTION_TYPE_COLORS: Record<ConnectionType, string> = {
  http: '#1890ff',      // Blue - REST API
  queue: '#722ed1',     // Purple - queues (Redis queue)
  database: '#13c2c2',  // Cyan - DB connections
  pubsub: '#eb2f96',    // Magenta - Redis Pub/Sub
}

/**
 * Human-readable labels for connection types
 */
export const CONNECTION_TYPE_LABELS: Record<ConnectionType, string> = {
  http: 'HTTP/REST',
  queue: 'Queue',
  database: 'Database',
  pubsub: 'Pub/Sub',
}

/**
 * Mapping of service connections to their types
 */
export const CONNECTION_TYPES: Record<string, ConnectionType> = {
  'frontend->api-gateway': 'http',
  'api-gateway->orchestrator': 'http',
  'orchestrator->postgresql': 'database',
  'orchestrator->redis': 'queue',
  'redis->worker': 'queue',
  'worker->ras-adapter': 'http',
  'worker->batch-service': 'http',
  'batch-service->postgresql': 'database',
  'ras-adapter->orchestrator': 'http',
}
