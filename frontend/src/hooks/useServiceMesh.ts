/**
 * React hook for real-time service mesh monitoring via WebSocket.
 *
 * Features:
 * - Real-time metrics updates every 2 seconds
 * - Automatic reconnection with exponential backoff
 * - Connection state management
 * - Manual refresh capability
 *
 * Usage:
 * ```tsx
 * const { services, connections, overallHealth, isConnected } = useServiceMesh();
 * ```
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  ServiceMetrics,
  ServiceConnection,
  ServiceStatus,
  ServiceMeshWSMessage,
  OperationFlowEvent,
  OperationFlowStatus,
  InvalidationScope,
} from '../types/serviceMesh'

// Reconnection settings
const RECONNECT_INITIAL_DELAY = 1000 // 1 second
const RECONNECT_MAX_DELAY = 30000 // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10

/**
 * Last invalidation event data
 */
export interface InvalidationEvent {
  scope: InvalidationScope
  timestamp: string
  entityId?: string
}

export interface UseServiceMeshResult {
  // Metrics data
  services: ServiceMetrics[]
  connections: ServiceConnection[]
  overallHealth: ServiceStatus
  timestamp: string | null

  // Connection state
  isConnected: boolean
  connectionError: string | null
  reconnectAttempts: number

  // Actions
  refresh: () => void
  setUpdateInterval: (seconds: number) => void
  disconnect: () => void

  // Operation flow
  activeOperation: OperationFlowEvent | null
  operationHistory: OperationFlowEvent[]

  // Cache invalidation
  lastInvalidation: InvalidationEvent | null
}

/**
 * Transform snake_case WebSocket data to camelCase
 */
function transformServiceMetrics(data: Record<string, unknown>): ServiceMetrics {
  return {
    name: data.name as string,
    displayName: (data.display_name || data.displayName) as string,
    status: data.status as ServiceStatus,
    opsPerMinute: (data.ops_per_minute ?? data.opsPerMinute ?? 0) as number,
    activeOperations: (data.active_operations ?? data.activeOperations ?? 0) as number,
    p95LatencyMs: (data.p95_latency_ms ?? data.p95LatencyMs ?? 0) as number,
    errorRate: (data.error_rate ?? data.errorRate ?? 0) as number,
    lastUpdated: (data.last_updated || data.lastUpdated) as string,
  }
}

function transformServiceConnection(data: Record<string, unknown>): ServiceConnection {
  return {
    source: data.source as string,
    target: data.target as string,
    requestsPerMinute: (data.requests_per_minute ?? data.requestsPerMinute ?? 0) as number,
    avgLatencyMs: (data.avg_latency_ms ?? data.avgLatencyMs ?? 0) as number,
  }
}

function transformOperationFlow(data: Record<string, unknown>): OperationFlowEvent {
  const flow = data.flow as Record<string, unknown>
  const operation = data.operation as Record<string, unknown>

  return {
    version: (data.version || '1.0') as string,
    type: 'operation_flow_update',
    operation_id: data.operation_id as string,
    timestamp: data.timestamp as string,
    flow: {
      currentService: (flow.current_service || flow.currentService) as string,
      path: ((flow.path || []) as Array<Record<string, unknown>>).map((p) => ({
        service: p.service as string,
        status: p.status as OperationFlowStatus,
        timestamp: p.timestamp as string,
      })),
      edges: ((flow.edges || []) as Array<Record<string, unknown>>).map((e) => ({
        from: e.from as string,
        to: e.to as string,
        status: e.status as OperationFlowStatus,
      })),
    },
    operation: {
      type: (operation.type || '') as string,
      name: (operation.name || '') as string,
      status: operation.status as 'pending' | 'processing' | 'completed' | 'failed',
      message: (operation.message || '') as string,
      metadata: operation.metadata as Record<string, unknown> | undefined,
    },
  }
}

export const useServiceMesh = (): UseServiceMeshResult => {
  // Metrics state
  const [services, setServices] = useState<ServiceMetrics[]>([])
  const [connections, setConnections] = useState<ServiceConnection[]>([])
  const [overallHealth, setOverallHealth] = useState<ServiceStatus>('degraded')
  const [timestamp, setTimestamp] = useState<string | null>(null)

  // Connection state
  const [isConnected, setIsConnected] = useState<boolean>(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0)

  // Operation flow state
  const [activeOperation, setActiveOperation] = useState<OperationFlowEvent | null>(null)
  const [operationHistory, setOperationHistory] = useState<OperationFlowEvent[]>([])

  // Cache invalidation state
  const [lastInvalidation, setLastInvalidation] = useState<InvalidationEvent | null>(null)

  // Refs
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null) // Delay for StrictMode
  const reconnectAttemptsRef = useRef<number>(0) // Ref to avoid stale closure
  const isMountedRef = useRef<boolean>(false) // Track mount state for StrictMode
  const isIntentionalCloseRef = useRef<boolean>(false) // Track intentional disconnect

  // Get WebSocket URL with auth token
  const getWebSocketUrl = useCallback((): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // WebSocket through API Gateway (which proxies to Orchestrator)
    // Port 8180 - API Gateway service
    const host = import.meta.env.VITE_WS_HOST || 'localhost:8180'
    const baseUrl = `${protocol}//${host}/ws/service-mesh/`

    // Add JWT token for authentication
    const token = localStorage.getItem('auth_token')
    if (token) {
      return `${baseUrl}?token=${token}`
    }
    return baseUrl
  }, [])

  // Handle incoming WebSocket message
  const handleMessage = useCallback((message: ServiceMeshWSMessage) => {
    switch (message.type) {
      case 'metrics_update':
        // Full metrics update
        if (message.services) {
          setServices(
            message.services.map((s) => transformServiceMetrics(s as unknown as Record<string, unknown>))
          )
        }
        if (message.connections) {
          setConnections(
            message.connections.map((c) => transformServiceConnection(c as unknown as Record<string, unknown>))
          )
        }
        if (message.overallHealth) {
          setOverallHealth(message.overallHealth)
        }
        if (message.timestamp) {
          setTimestamp(message.timestamp)
        }
        // Clear any previous error on successful update
        if (!message.error) {
          setConnectionError(null)
        }
        break

      case 'operation_flow_update': {
        const flowEvent = transformOperationFlow(message as unknown as Record<string, unknown>)

        if (flowEvent.operation.status === 'processing') {
          // Operation in progress - show it
          setActiveOperation(flowEvent)
        } else {
          // Operation completed - remove and add to history
          setActiveOperation(null)
          setOperationHistory((prev) => [flowEvent, ...prev].slice(0, 10)) // Last 10
        }
        break
      }

      case 'interval_updated':
        // Interval change confirmed
        console.log('Update interval changed to:', message.interval, 'seconds')
        break

      case 'dashboard_invalidate':
        // Dashboard cache invalidation event
        setLastInvalidation({
          scope: message.scope || 'all',
          timestamp: message.timestamp || new Date().toISOString(),
          entityId: message.entity_id,
        })
        break

      case 'error':
        // Server-side error
        setConnectionError(message.message || 'Unknown server error')
        break

      case 'pong':
        // Heartbeat response - ignore
        break

      default:
        console.warn('Unknown WebSocket message type:', message.type)
    }
  }, [])

  // Actually create WebSocket connection (called after delay)
  const createWebSocket = useCallback((url: string) => {
    // Final check before creating connection
    if (!isMountedRef.current) {
      return
    }

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('Service mesh WebSocket connected')
        setIsConnected(true)
        setConnectionError(null)
        setReconnectAttempts(0)
      }

      ws.onmessage = (event) => {
        try {
          const message: ServiceMeshWSMessage = JSON.parse(event.data)
          handleMessage(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = (event) => {
        // Skip error logging if unmounted (StrictMode cleanup)
        if (!isMountedRef.current) return

        console.error('Service mesh WebSocket error:', event)
        setConnectionError('WebSocket connection error')
      }

      ws.onclose = (event) => {
        // Skip logging for intentional closes (StrictMode unmount)
        if (!isIntentionalCloseRef.current) {
          console.log('Service mesh WebSocket closed:', event.code, event.reason || '')
        }

        setIsConnected(false)
        wsRef.current = null

        // Don't reconnect if intentionally closed or unmounted
        if (isIntentionalCloseRef.current || !isMountedRef.current) {
          return
        }

        // Attempt to reconnect - use ref to avoid stale closure
        const currentAttempts = reconnectAttemptsRef.current
        if (currentAttempts < RECONNECT_MAX_ATTEMPTS) {
          // Schedule reconnection with exponential backoff
          const delay = Math.min(
            RECONNECT_INITIAL_DELAY * Math.pow(2, currentAttempts),
            RECONNECT_MAX_DELAY
          )

          console.log(
            `Service mesh WebSocket reconnecting in ${delay}ms (attempt ${currentAttempts + 1})`
          )
          setConnectionError(`Connection lost. Reconnecting in ${Math.round(delay / 1000)}s...`)

          reconnectTimeoutRef.current = setTimeout(() => {
            // Double-check still mounted before reconnecting
            if (!isMountedRef.current) return

            reconnectAttemptsRef.current += 1
            setReconnectAttempts(reconnectAttemptsRef.current)
            connect()
          }, delay)
        } else {
          setConnectionError('Max reconnection attempts reached. Please refresh the page.')
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.error('Service mesh WebSocket connection failed:', err)
      setConnectionError('Failed to establish WebSocket connection')
    }
  }, [handleMessage])

  // Connect to WebSocket with delay (StrictMode protection)
  const connect = useCallback(() => {
    // Clear any existing timeouts
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current)
      connectTimeoutRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Close existing connection
    if (wsRef.current) {
      isIntentionalCloseRef.current = true
      wsRef.current.close()
      wsRef.current = null
    }

    // Don't connect if unmounted
    if (!isMountedRef.current) {
      return
    }

    isIntentionalCloseRef.current = false
    const url = getWebSocketUrl()

    // Delay connection to allow StrictMode cleanup to complete
    // This prevents "WebSocket is closed before connection established" errors
    connectTimeoutRef.current = setTimeout(() => {
      if (isMountedRef.current) {
        console.log('Service mesh WebSocket connecting to:', url)
        createWebSocket(url)
      }
    }, 0)
  }, [getWebSocketUrl, createWebSocket])

  // Request immediate refresh
  const refresh = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'get_metrics' }))
    }
  }, [])

  // Set update interval
  const setUpdateInterval = useCallback((seconds: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'set_interval', interval: seconds }))
    }
  }, [])

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    // Clear all pending timeouts
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current)
      connectTimeoutRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      isIntentionalCloseRef.current = true
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
  }, [])

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    isMountedRef.current = true
    reconnectAttemptsRef.current = 0
    connect()

    return () => {
      isMountedRef.current = false
      disconnect()
    }
  }, [connect, disconnect])

  // Send periodic ping to keep connection alive
  useEffect(() => {
    if (!isConnected) {
      return
    }

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: 'ping' }))
      }
    }, 30000) // Every 30 seconds

    return () => {
      clearInterval(pingInterval)
    }
  }, [isConnected])

  return {
    // Metrics data
    services,
    connections,
    overallHealth,
    timestamp,

    // Connection state
    isConnected,
    connectionError,
    reconnectAttempts,

    // Actions
    refresh,
    setUpdateInterval,
    disconnect,

    // Operation flow
    activeOperation,
    operationHistory,

    // Cache invalidation
    lastInvalidation,
  }
}

export default useServiceMesh
