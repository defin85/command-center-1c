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
} from '../types/serviceMesh'

// Reconnection settings
const RECONNECT_INITIAL_DELAY = 1000 // 1 second
const RECONNECT_MAX_DELAY = 30000 // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10

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

  // Refs
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef<number>(0) // Ref to avoid stale closure

  // Get WebSocket URL
  const getWebSocketUrl = useCallback((): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // WebSocket directly to Orchestrator (Django Channels)
    // Port 8200 - Django/Orchestrator service
    const host = import.meta.env.VITE_WS_HOST || 'localhost:8200'
    return `${protocol}//${host}/ws/service-mesh/`
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

      case 'interval_updated':
        // Interval change confirmed
        console.log('Update interval changed to:', message.interval, 'seconds')
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

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const url = getWebSocketUrl()
    console.log('Service mesh WebSocket connecting to:', url)

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
        console.error('Service mesh WebSocket error:', event)
        setConnectionError('WebSocket connection error')
      }

      ws.onclose = (event) => {
        console.log('Service mesh WebSocket closed:', event.code, event.reason)
        setIsConnected(false)
        wsRef.current = null

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
  }, [getWebSocketUrl, handleMessage]) // Removed reconnectAttempts - using ref instead

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
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
  }, [])

  // Connect on mount
  useEffect(() => {
    connect()

    return () => {
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
  }
}

export default useServiceMesh
