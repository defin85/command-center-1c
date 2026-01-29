import { getWsHost } from '../api/baseUrl'
import type {
  ServiceMetrics,
  ServiceConnection,
  ServiceStatus,
  ServiceMeshWSMessage,
  OperationFlowEvent,
  OperationFlowStatus,
  InvalidationScope,
} from '../types/serviceMesh'

const RECONNECT_INITIAL_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
const RECONNECT_MAX_ATTEMPTS = 10
const PING_INTERVAL = 30000
const DISCONNECT_GRACE_MS = 250
const LONG_RUNNING_OPERATION_TYPES = new Set(['sync_cluster', 'designer_cli', 'execute_workflow'])

export interface InvalidationEvent {
  scope: InvalidationScope
  timestamp: string
  entityId?: string
}

export interface ServiceMeshState {
  services: ServiceMetrics[]
  connections: ServiceConnection[]
  overallHealth: ServiceStatus
  timestamp: string | null
  isConnected: boolean
  connectionError: string | null
  reconnectAttempts: number
  activeOperation: OperationFlowEvent | null
  operationHistory: OperationFlowEvent[]
  lastInvalidation: InvalidationEvent | null
}

type StateListener = (state: ServiceMeshState) => void
type InvalidationListener = (event: InvalidationEvent) => void

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
    trace_id: (data.trace_id as string | undefined) || undefined,
    workflow_execution_id: (data.workflow_execution_id as string | undefined) || undefined,
    node_id: (data.node_id as string | undefined) || undefined,
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

class ServiceMeshManager {
  private state: ServiceMeshState = {
    services: [],
    connections: [],
    overallHealth: 'degraded',
    timestamp: null,
    isConnected: false,
    connectionError: null,
    reconnectAttempts: 0,
    activeOperation: null,
    operationHistory: [],
    lastInvalidation: null,
  }
  private listeners = new Set<StateListener>()
  private invalidationListeners = new Set<InvalidationListener>()
  private refCount = 0
  private stopTimer: ReturnType<typeof setTimeout> | null = null
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private operationTimeout: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private isConnecting = false
  private isManualClose = false

  getState() {
    return this.state
  }

  subscribe(listener: StateListener) {
    this.listeners.add(listener)
    listener(this.state)
    return () => {
      this.listeners.delete(listener)
    }
  }

  subscribeInvalidation(listener: InvalidationListener) {
    this.invalidationListeners.add(listener)
    return () => {
      this.invalidationListeners.delete(listener)
    }
  }

  start() {
    this.refCount += 1
    if (this.stopTimer) {
      clearTimeout(this.stopTimer)
      this.stopTimer = null
    }
    if (this.refCount === 1) {
      this.connect()
    }
  }

  stop() {
    this.refCount = Math.max(0, this.refCount - 1)
    if (this.refCount === 0) {
      this.stopTimer = setTimeout(() => {
        if (this.refCount === 0) {
          this.disconnect(true)
        }
      }, DISCONNECT_GRACE_MS)
    }
  }

  refresh() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'get_metrics' }))
    }
  }

  setUpdateInterval(seconds: number) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'set_interval', interval: seconds }))
    }
  }

  disconnect(force = false) {
    this.clearReconnect()
    this.clearPing()
    this.clearOperationTimeout()
    if (this.ws) {
      this.isManualClose = true
      this.ws.close()
      this.ws = null
    }
    this.isConnecting = false
    if (force) {
      this.reconnectAttempts = 0
      this.setState({ isConnected: false, reconnectAttempts: 0 })
    } else {
      this.setState({ isConnected: false })
    }
  }

  private setState(partial: Partial<ServiceMeshState>) {
    this.state = { ...this.state, ...partial }
    for (const listener of this.listeners) {
      listener(this.state)
    }
  }

  private emitInvalidation(event: InvalidationEvent) {
    for (const listener of this.invalidationListeners) {
      listener(event)
    }
  }

  private clearReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private clearPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private clearOperationTimeout() {
    if (this.operationTimeout) {
      clearTimeout(this.operationTimeout)
      this.operationTimeout = null
    }
  }

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const baseUrl = `${protocol}//${getWsHost()}/ws/service-mesh/`
    const token = localStorage.getItem('auth_token')
    if (token) {
      return `${baseUrl}?token=${token}`
    }
    return baseUrl
  }

  private connect() {
    if (this.refCount === 0) return
    if (this.isConnecting) return
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    this.clearReconnect()

    this.isConnecting = true
    this.isManualClose = false
    const url = this.getWebSocketUrl()

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.setState({
          isConnected: true,
          connectionError: null,
          reconnectAttempts: 0,
        })
        this.startPing()
      }

      ws.onmessage = (event) => {
        try {
          const message: ServiceMeshWSMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = () => {
        if (this.isManualClose) return
        this.setState({ connectionError: 'WebSocket connection error' })
        this.isConnecting = false
      }

      ws.onclose = (event) => {
        this.clearPing()
        this.isConnecting = false
        this.ws = null
        this.setState({ isConnected: false })

        if (this.isManualClose || this.refCount === 0) {
          return
        }

        if (!this.isManualClose) {
          console.log('Service mesh WebSocket closed:', event.code, event.reason || '')
        }
        this.scheduleReconnect()
      }

      this.ws = ws
    } catch (err) {
      console.error('Service mesh WebSocket connection failed:', err)
      this.setState({ connectionError: 'Failed to establish WebSocket connection' })
      this.isConnecting = false
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer || this.refCount === 0) return
    if (this.reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
      this.setState({ connectionError: 'Max reconnection attempts reached. Please refresh the page.' })
      return
    }

    const delay = Math.min(
      RECONNECT_INITIAL_DELAY * Math.pow(2, this.reconnectAttempts),
      RECONNECT_MAX_DELAY
    )

    this.setState({
      connectionError: `Connection lost. Reconnecting in ${Math.round(delay / 1000)}s...`,
    })

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectAttempts += 1
      this.setState({ reconnectAttempts: this.reconnectAttempts })
      this.connect()
    }, delay)
  }

  private startPing() {
    this.clearPing()
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'ping' }))
      }
    }, PING_INTERVAL)
  }

  private handleMessage(message: ServiceMeshWSMessage) {
    switch (message.type) {
      case 'metrics_update': {
        const partial: Partial<ServiceMeshState> = {}
        if (message.services) {
          partial.services = message.services.map((s) =>
            transformServiceMetrics(s as unknown as Record<string, unknown>)
          )
        }
        if (message.connections) {
          partial.connections = message.connections.map((c) =>
            transformServiceConnection(c as unknown as Record<string, unknown>)
          )
        }
        if (message.overallHealth) {
          partial.overallHealth = message.overallHealth
        }
        if (message.timestamp) {
          partial.timestamp = message.timestamp
        }
        if (!message.error) {
          partial.connectionError = null
        }
        if (Object.keys(partial).length > 0) {
          this.setState(partial)
        }
        break
      }

      case 'operation_flow_update': {
        const flowEvent = transformOperationFlow(message as unknown as Record<string, unknown>)
        this.clearOperationTimeout()

        if (flowEvent.operation.status === 'processing') {
          this.setState({ activeOperation: flowEvent })
          const opType = flowEvent.operation.type || ''
          const timeoutMs =
            LONG_RUNNING_OPERATION_TYPES.has(opType) ? 5 * 60_000 : 60_000
          this.operationTimeout = setTimeout(() => {
            console.warn('Operation timeout - clearing stuck operation:', flowEvent.operation_id)
            this.setState({ activeOperation: null })
          }, timeoutMs)
        } else {
          const exists = this.state.operationHistory.some(
            (op) => op.operation_id === flowEvent.operation_id
          )
          if (!exists) {
            const nextHistory = [flowEvent, ...this.state.operationHistory].slice(0, 50)
            this.setState({ activeOperation: null, operationHistory: nextHistory })
          } else {
            this.setState({ activeOperation: null })
          }
        }
        break
      }

      case 'interval_updated':
        console.log('Update interval changed to:', message.interval, 'seconds')
        break

      case 'dashboard_invalidate':
        {
          const event: InvalidationEvent = {
            scope: message.scope || 'all',
            timestamp: message.timestamp || new Date().toISOString(),
            entityId: message.entity_id,
          }
          this.emitInvalidation(event)
          this.setState({ lastInvalidation: event })
        }
        break

      case 'error':
        this.setState({ connectionError: message.message || 'Unknown server error' })
        break

      case 'pong':
        break

      default:
        console.warn('Unknown WebSocket message type:', message.type)
    }
  }
}

export const serviceMeshManager = new ServiceMeshManager()
