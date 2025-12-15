/**
 * React hook for real-time workflow execution updates via WebSocket.
 *
 * Features:
 * - Real-time workflow status updates
 * - Node execution progress tracking
 * - Automatic reconnection with exponential backoff
 * - Connection state management
 *
 * Usage:
 * ```tsx
 * const { status, progress, nodeStatuses, isConnected, error } = useWorkflowExecution(executionId);
 * ```
 */
import { useCallback, useEffect, useRef, useState } from 'react'

// WebSocket message types (match server-side consumers.py)
export type WorkflowStatusType = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type NodeStatusType = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface NodeStatus {
  nodeId: string
  status: NodeStatusType
  output?: Record<string, any>
  error?: string
  durationMs?: number
  spanId?: string
  startedAt?: string
  completedAt?: string
}

export interface WorkflowStatus {
  executionId: string
  status: WorkflowStatusType
  progress: number // 0.0 - 1.0
  currentNodeId?: string
  traceId?: string
  errorMessage?: string
  nodeStatuses: Record<string, NodeStatus>
  createdAt?: string
  updatedAt?: string
  completedAt?: string
}

export interface WorkflowCompletedEvent {
  executionId: string
  status: WorkflowStatusType
  result?: Record<string, any>
  errorMessage?: string
  durationMs?: number
  completedAt?: string
}

export interface UseWorkflowExecutionResult {
  // Workflow status
  status: WorkflowStatusType
  progress: number
  currentNodeId?: string
  traceId?: string
  errorMessage?: string
  result?: Record<string, any>

  // Node statuses (nodeId -> status)
  nodeStatuses: Record<string, NodeStatus>

  // Connection state
  isConnected: boolean
  connectionError: string | null
  reconnectAttempts: number

  // Actions
  requestStatus: () => void
  subscribeToNodes: (nodeIds: string[]) => void
  disconnect: () => void
}

interface WebSocketMessage {
  type: string
  execution_id?: string
  status?: string
  progress?: number
  current_node_id?: string
  trace_id?: string
  error_message?: string
  node_statuses?: Record<string, any>
  node_id?: string
  output?: Record<string, any>
  error?: string
  duration_ms?: number
  span_id?: string
  started_at?: string
  completed_at?: string
  result?: Record<string, any>
  code?: string
  message?: string
  created_at?: string
  updated_at?: string
}

// Reconnection settings
const RECONNECT_INITIAL_DELAY = 1000 // 1 second
const RECONNECT_MAX_DELAY = 30000 // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10

export const useWorkflowExecution = (
  executionId: string | null
): UseWorkflowExecutionResult => {
  // Workflow state
  const [status, setStatus] = useState<WorkflowStatusType>('pending')
  const [progress, setProgress] = useState<number>(0)
  const [currentNodeId, setCurrentNodeId] = useState<string | undefined>()
  const [traceId, setTraceId] = useState<string | undefined>()
  const [errorMessage, setErrorMessage] = useState<string | undefined>()
  const [result, setResult] = useState<Record<string, any> | undefined>()
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, NodeStatus>>({})

  // Connection state
  const [isConnected, setIsConnected] = useState<boolean>(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0)

  // WebSocket ref
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Get WebSocket URL
  const getWebSocketUrl = useCallback((execId: string): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // Connect through API Gateway for production, direct for development
    const rawHost = import.meta.env.VITE_WS_HOST || window.location.host
    // Prefer IPv4 localhost to avoid WSL/Chromium attempting ::1 while backend listens on 0.0.0.0
    const host = rawHost.startsWith('localhost') ? `127.0.0.1${rawHost.slice('localhost'.length)}` : rawHost
    return `${protocol}//${host}/ws/workflow/${execId}/`
  }, [])

  // Handle incoming WebSocket message
  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'workflow_status':
        // Full workflow status update
        if (message.status) {
          setStatus(message.status as WorkflowStatusType)
        }
        if (message.progress !== undefined) {
          setProgress(message.progress)
        }
        if (message.current_node_id !== undefined) {
          setCurrentNodeId(message.current_node_id || undefined)
        }
        if (message.trace_id !== undefined) {
          setTraceId(message.trace_id || undefined)
        }
        if (message.error_message !== undefined) {
          setErrorMessage(message.error_message || undefined)
        }
        if (message.node_statuses) {
          // Convert snake_case to camelCase
          const converted: Record<string, NodeStatus> = {}
          for (const [nodeId, nodeData] of Object.entries(message.node_statuses)) {
            if (typeof nodeData === 'object' && nodeData !== null) {
              converted[nodeId] = {
                nodeId,
                status: (nodeData as any).status || 'pending',
                output: (nodeData as any).output,
                error: (nodeData as any).error,
                durationMs: (nodeData as any).duration_ms,
                spanId: (nodeData as any).span_id,
                startedAt: (nodeData as any).started_at,
                completedAt: (nodeData as any).completed_at,
              }
            }
          }
          setNodeStatuses(converted)
        }
        break

      case 'node_status':
        // Individual node update
        if (message.node_id) {
          setNodeStatuses((prev) => ({
            ...prev,
            [message.node_id!]: {
              nodeId: message.node_id!,
              status: (message.status as NodeStatusType) || 'pending',
              output: message.output,
              error: message.error,
              durationMs: message.duration_ms,
              spanId: message.span_id,
              startedAt: message.started_at,
              completedAt: message.completed_at,
            },
          }))
        }
        // Update workflow progress and current node
        if (message.status === 'running') {
          setCurrentNodeId(message.node_id || undefined)
        }
        break

      case 'execution_completed':
        // Workflow finished
        if (message.status) {
          setStatus(message.status as WorkflowStatusType)
        }
        if (message.result) {
          setResult(message.result)
        }
        if (message.error_message) {
          setErrorMessage(message.error_message)
        }
        setProgress(1.0) // 100% complete
        break

      case 'error':
        // Server-side error
        setConnectionError(message.message || 'Unknown server error')
        break

      case 'pong':
        // Heartbeat response - ignore
        break

      case 'subscription_update':
        // Node subscription confirmed - ignore
        break

      default:
        console.warn('Unknown WebSocket message type:', message.type)
    }
  }, [])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!executionId) {
      return
    }

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

    const url = getWebSocketUrl(executionId)
    console.log('WebSocket connecting to:', url)

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setConnectionError(null)
        setReconnectAttempts(0)
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          handleMessage(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        setConnectionError('WebSocket connection error')
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        setIsConnected(false)
        wsRef.current = null

        // Check if we should reconnect
        const isTerminalStatus = ['completed', 'failed', 'cancelled'].includes(status)

        if (!isTerminalStatus && reconnectAttempts < RECONNECT_MAX_ATTEMPTS) {
          // Schedule reconnection with exponential backoff
          const delay = Math.min(
            RECONNECT_INITIAL_DELAY * Math.pow(2, reconnectAttempts),
            RECONNECT_MAX_DELAY
          )

          console.log(`WebSocket reconnecting in ${delay}ms (attempt ${reconnectAttempts + 1})`)
          setConnectionError(`Connection lost. Reconnecting in ${Math.round(delay / 1000)}s...`)

          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts((prev) => prev + 1)
            connect()
          }, delay)
        } else if (reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
          setConnectionError('Max reconnection attempts reached. Please refresh the page.')
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.error('WebSocket connection failed:', err)
      setConnectionError('Failed to establish WebSocket connection')
    }
  }, [executionId, getWebSocketUrl, handleMessage, reconnectAttempts, status])

  // Request current status from server
  const requestStatus = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'get_status' }))
    }
  }, [])

  // Subscribe to specific node updates
  const subscribeToNodes = useCallback((nodeIds: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe_nodes',
        node_ids: nodeIds,
      }))
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

  // Connect when executionId changes
  useEffect(() => {
    if (executionId) {
      // Reset state for new execution
      setStatus('pending')
      setProgress(0)
      setCurrentNodeId(undefined)
      setTraceId(undefined)
      setErrorMessage(undefined)
      setResult(undefined)
      setNodeStatuses({})
      setReconnectAttempts(0)

      connect()
    }

    return () => {
      disconnect()
    }
  }, [executionId, connect, disconnect])

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
    // Workflow status
    status,
    progress,
    currentNodeId,
    traceId,
    errorMessage,
    result,

    // Node statuses
    nodeStatuses,

    // Connection state
    isConnected,
    connectionError,
    reconnectAttempts,

    // Actions
    requestStatus,
    subscribeToNodes,
    disconnect,
  }
}

export default useWorkflowExecution
