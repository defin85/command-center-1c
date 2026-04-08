type PrimitiveValue = string | number | boolean | null

type RouteLocationInput = {
  pathname?: string
  search?: string
  hash?: string
}

type RouteSnapshot = {
  path: string
  search: string
  hash: string
  context: Record<string, PrimitiveValue>
}

type ActionSource = 'explicit' | 'navigation' | 'synthetic_request'
type ActionKind = 'route.navigate' | 'modal.submit' | 'modal.confirm' | 'request.boundary'
type WebSocketChannelKind = 'shared' | 'dedicated'
type WebSocketLifecycleOutcome = 'connect' | 'reuse' | 'close' | 'reconnect'

type ActionEvent = {
  event_id: string
  event_type: 'ui.action'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  ui_action_id: string
  action_kind: ActionKind
  action_name: string
  action_source: ActionSource
}

type RouteEvent = {
  event_id: string
  event_type: 'route.transition'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  outcome: 'navigated'
}

type HttpFailureEvent = {
  event_id: string
  event_type: 'http.request.failure' | 'http.request.slow'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  request_id: string
  ui_action_id: string
  outcome: 'failure' | 'slow'
  method: string
  path: string
  status?: number
  latency_ms: number
  error_code?: string
  error_title?: string
}

type UiErrorEvent = {
  event_id: string
  event_type: 'ui.error.boundary' | 'ui.error.global' | 'ui.error.unhandled_rejection'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  ui_action_id?: string
  outcome: 'error'
  error_name?: string
  error_message?: string
  error_source?: string
  component_stack?: string
}

type WebSocketEvent = {
  event_id: string
  event_type: 'websocket.lifecycle' | 'websocket.churn_warning'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  outcome: WebSocketLifecycleOutcome | 'churn_warning'
  owner: string
  reuse_key: string
  channel_kind: WebSocketChannelKind
  socket_instance_id: string
  active_connections_for_reuse_key: number
  close_code?: number
  close_reason?: string
  reconnect_attempt?: number
}

type UiJournalEvent = RouteEvent | ActionEvent | HttpFailureEvent | UiErrorEvent | WebSocketEvent

type ActiveActionContext = {
  ui_action_id: string
  action_kind: ActionKind
  action_name: string
  action_source: ActionSource
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  timeout_id: ReturnType<typeof setTimeout> | null
}

type ActiveHttpRequest = {
  request_id: string
  ui_action_id: string
  method: string
  path: string
  started_at: string
  started_at_ms: number
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
}

type ActiveWebSocket = {
  owner: string
  reuse_key: string
  channel_kind: WebSocketChannelKind
  socket_instance_id: string
  active: boolean
  last_event_at: string
}

type RequestProblemDetails = {
  code?: string
  title?: string
  request_id?: string
  ui_action_id?: string
}

type UiActionMeta = {
  actionKind: ActionKind
  actionName?: string
  actionSource?: ActionSource
  context?: Record<string, unknown>
}

type StartHttpRequestInput = {
  method?: string
  path?: string
  context?: Record<string, unknown>
}

type CompleteHttpRequestInput = {
  requestId?: string
  uiActionId?: string
  method?: string
  path?: string
  status?: number
  failed?: boolean
  problem?: RequestProblemDetails
}

type WebSocketLifecycleInput = {
  owner: string
  reuseKey: string
  channelKind: WebSocketChannelKind
  socketInstanceId: string
  outcome: WebSocketLifecycleOutcome
  closeCode?: number
  closeReason?: string
  reconnectAttempt?: number
}

type WindowGlobalJournalApi = {
  clear: () => void
  exportBundle: () => UiJournalBundle
  isEnabled: () => boolean
}

export type UiJournalBundle = {
  session_id: string | null
  captured_at: string
  release: {
    app: string
    fingerprint: string
    mode: string
    origin: string
  }
  route: RouteSnapshot
  events: UiJournalEvent[]
  active_http_requests: ActiveHttpRequest[]
  active_websockets_by_owner: Record<string, {
    active_connection_count: number
    channel_kinds: WebSocketChannelKind[]
    reuse_keys: string[]
    socket_instance_ids: string[]
  }>
  active_websockets_by_reuse_key: Record<string, {
    active_connection_count: number
    channel_kind: WebSocketChannelKind
    owner: string
    socket_instance_ids: string[]
  }>
  recent_churn_anomalies: WebSocketEvent[]
}

const JOURNAL_MAX_EVENTS = 240
const ACTION_TTL_MS = 15_000
const SLOW_REQUEST_THRESHOLD_MS = 2_000
const WEBSOCKET_CHURN_WINDOW_MS = 60_000
const WEBSOCKET_CHURN_THRESHOLD = 3
const ROUTE_CONTEXT_ALLOWLIST = new Set([
  'artifact',
  'batch',
  'binding',
  'cluster',
  'context',
  'database',
  'detail',
  'direction',
  'edge',
  'execution',
  'execution_id',
  'focus',
  'mode',
  'operation',
  'organization',
  'period_end',
  'period_start',
  'pool',
  'quarter_start',
  'run',
  'service',
  'stage',
  'tab',
  'template',
  'tenant',
  'user',
  'view',
  'workflow',
])
const SENSITIVE_KEY_PATTERN = /(auth|authorization|cookie|csrf|passwd|password|secret|session|token)/i
const SECRET_VALUE_PATTERN = /\b(password|passwd|pwd|token|authorization|secret|cookie)\b[:=]\s*([^\s,;]+)/gi

const nowIso = () => new Date().toISOString()

const toActionName = (actionKind: ActionKind, actionName?: string) => (
  sanitizeString(actionName, 80) ?? actionKind
)

const normalizeRequestPath = (rawPath?: string): string => {
  const fallback = '/unknown'
  if (!rawPath) {
    return fallback
  }

  try {
    const resolved = rawPath.startsWith('http://') || rawPath.startsWith('https://')
      ? new URL(rawPath)
      : new URL(rawPath, 'http://localhost')
    return resolved.pathname || fallback
  } catch {
    const [pathname] = rawPath.split('?')
    return pathname || fallback
  }
}

const generateRuntimeId = (prefix: string): string => {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return `${prefix}-${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`
}

const sanitizeString = (value: unknown, maxLength = 240): string | undefined => {
  if (typeof value !== 'string' && typeof value !== 'number' && typeof value !== 'boolean') {
    return undefined
  }

  const normalized = String(value).trim()
  if (!normalized) {
    return undefined
  }

  const redacted = normalized
    .replace(SECRET_VALUE_PATTERN, '$1=[redacted]')
    .slice(0, maxLength)
  return redacted || undefined
}

const isPrimitiveValue = (value: unknown): value is PrimitiveValue => (
  value === null
    || typeof value === 'string'
    || typeof value === 'number'
    || typeof value === 'boolean'
)

const isRouteContextKeyAllowed = (key: string): boolean => {
  const normalized = key.trim().toLowerCase()
  if (!normalized || SENSITIVE_KEY_PATTERN.test(normalized)) {
    return false
  }
  if (ROUTE_CONTEXT_ALLOWLIST.has(normalized)) {
    return true
  }
  return normalized.endsWith('_id') || normalized.endsWith('_uuid')
}

const sanitizeContextRecord = (value: Record<string, unknown> | undefined): Record<string, PrimitiveValue> => {
  if (!value) {
    return {}
  }

  const normalized: Record<string, PrimitiveValue> = {}
  for (const [rawKey, rawValue] of Object.entries(value)) {
    const key = rawKey.trim()
    if (!key || SENSITIVE_KEY_PATTERN.test(key)) {
      continue
    }
    if (!isPrimitiveValue(rawValue)) {
      continue
    }
    if (typeof rawValue === 'string') {
      const safeValue = sanitizeString(rawValue)
      if (safeValue !== undefined) {
        normalized[key] = safeValue
      }
      continue
    }
    normalized[key] = rawValue
  }
  return normalized
}

const buildRouteSnapshot = (location?: RouteLocationInput): RouteSnapshot => {
  const pathname = location?.pathname ?? (typeof window !== 'undefined' ? window.location.pathname : '/')
  const rawSearch = location?.search ?? (typeof window !== 'undefined' ? window.location.search : '')
  const hash = location?.hash ?? (typeof window !== 'undefined' ? window.location.hash : '')
  const context: Record<string, PrimitiveValue> = {}
  const sanitizedSearchParams = new URLSearchParams()

  const params = new URLSearchParams(rawSearch.startsWith('?') ? rawSearch.slice(1) : rawSearch)
  params.forEach((value, key) => {
    if (!isRouteContextKeyAllowed(key)) {
      return
    }
    const safeValue = sanitizeString(value, 120)
    if (safeValue !== undefined) {
      context[key] = safeValue
      sanitizedSearchParams.set(key, safeValue)
    }
  })

  const search = sanitizedSearchParams.size > 0
    ? `?${sanitizedSearchParams.toString()}`
    : ''

  return {
    path: pathname || '/',
    search: search || '',
    hash: hash || '',
    context,
  }
}

const buildCorrelationFingerprint = (mode: string, origin: string): string => `${mode}:${origin}`

class UiActionJournal {
  private enabled = false
  private sessionId: string | null = null
  private readonly events: UiJournalEvent[] = []
  private readonly activeRequests = new Map<string, ActiveHttpRequest>()
  private readonly activeWebSockets = new Map<string, ActiveWebSocket>()
  private readonly websocketChurnHistory = new Map<string, number[]>()
  private readonly recentChurnAnomalies: WebSocketEvent[] = []
  private currentRoute: RouteSnapshot = buildRouteSnapshot()
  private lastRouteSignature = ''
  private activeAction: ActiveActionContext | null = null

  constructor() {
    this.installWindowApi()
  }

  setEnabled(enabled: boolean) {
    if (this.enabled === enabled) {
      return
    }

    this.enabled = enabled
    if (!enabled) {
      this.reset()
      this.installWindowApi()
      return
    }

    this.startSession()
  }

  clear() {
    if (!this.enabled) {
      this.reset()
      this.installWindowApi()
      return
    }

    this.reset()
    this.startSession()
  }

  captureRoute(location?: RouteLocationInput) {
    if (!this.enabled) {
      return
    }

    this.ensureSession()
    const route = buildRouteSnapshot(location)
    const signature = `${route.path}${route.search}${route.hash}`
    if (signature === this.lastRouteSignature) {
      return
    }

    this.lastRouteSignature = signature
    this.currentRoute = route
    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: 'route.transition',
      occurred_at: nowIso(),
      route,
      context: route.context,
      outcome: 'navigated',
    })
  }

  trackAction<T>(meta: UiActionMeta, handler?: () => T): T | undefined {
    if (!this.enabled) {
      return handler?.()
    }

    const action = this.activateAction(meta)

    try {
      const result = handler?.()
      if (isPromiseLike(result)) {
        return Promise.resolve(result)
          .finally(() => {
            this.resolveAction(action.ui_action_id)
          }) as T
      }
      return result
    } catch (error) {
      this.recordUiError('ui.error.global', error, {
        error_source: 'ui_action_handler',
      })
      this.resolveAction(action.ui_action_id)
      throw error
    }
  }

  startHttpRequest(input: StartHttpRequestInput) {
    if (!this.enabled) {
      return {
        requestId: generateRuntimeId('req'),
        uiActionId: this.activeAction?.ui_action_id ?? generateRuntimeId('uia'),
      }
    }

    this.ensureSession()

    const route = this.currentRoute
    const method = sanitizeString(input.method?.toUpperCase(), 16) ?? 'GET'
    const path = normalizeRequestPath(input.path)
    const requestId = generateRuntimeId('req')
    const action = this.activeAction ?? this.createSyntheticRequestAction(method, path)
    const startedAt = nowIso()
    const activeRequest: ActiveHttpRequest = {
      request_id: requestId,
      ui_action_id: action.ui_action_id,
      method,
      path,
      started_at: startedAt,
      started_at_ms: Date.now(),
      route,
      context: {
        ...route.context,
        ...sanitizeContextRecord(input.context),
      },
    }

    this.activeRequests.set(requestId, activeRequest)
    return {
      requestId,
      uiActionId: activeRequest.ui_action_id,
    }
  }

  completeHttpRequest(input: CompleteHttpRequestInput) {
    if (!input.requestId) {
      return
    }

    const activeRequest = this.activeRequests.get(input.requestId)
    if (!activeRequest) {
      return
    }

    this.activeRequests.delete(input.requestId)
    const latencyMs = Math.max(0, Date.now() - activeRequest.started_at_ms)
    const status = input.status
    const problem = input.problem
    const correlatedRequestId = sanitizeString(problem?.request_id, 160) ?? activeRequest.request_id
    const correlatedActionId = sanitizeString(problem?.ui_action_id, 160) ?? input.uiActionId ?? activeRequest.ui_action_id

    if (input.failed || (status ?? 0) >= 400) {
      this.pushEvent({
        event_id: generateRuntimeId('evt'),
        event_type: 'http.request.failure',
        occurred_at: nowIso(),
        route: activeRequest.route,
        context: activeRequest.context,
        request_id: correlatedRequestId,
        ui_action_id: correlatedActionId,
        outcome: 'failure',
        method: sanitizeString(input.method?.toUpperCase(), 16) ?? activeRequest.method,
        path: normalizeRequestPath(input.path) || activeRequest.path,
        status,
        latency_ms: latencyMs,
        error_code: sanitizeString(problem?.code, 80),
        error_title: sanitizeString(problem?.title, 160),
      })
      return
    }

    if (latencyMs >= SLOW_REQUEST_THRESHOLD_MS) {
      this.pushEvent({
        event_id: generateRuntimeId('evt'),
        event_type: 'http.request.slow',
        occurred_at: nowIso(),
        route: activeRequest.route,
        context: activeRequest.context,
        request_id: correlatedRequestId,
        ui_action_id: correlatedActionId,
        outcome: 'slow',
        method: sanitizeString(input.method?.toUpperCase(), 16) ?? activeRequest.method,
        path: normalizeRequestPath(input.path) || activeRequest.path,
        status,
        latency_ms: latencyMs,
      })
    }
  }

  recordErrorBoundary(error: Error, componentStack?: string | null) {
    this.recordUiError('ui.error.boundary', error, {
      component_stack: sanitizeString(componentStack, 500),
      error_source: 'ErrorBoundary',
    })
  }

  recordWindowError(error: unknown, details?: {
    error_source?: string
  }) {
    this.recordUiError('ui.error.global', error, {
      error_source: sanitizeString(details?.error_source, 80),
    })
  }

  recordUnhandledRejection(reason: unknown) {
    this.recordUiError('ui.error.unhandled_rejection', reason, {
      error_source: 'unhandledrejection',
    })
  }

  recordWebSocketLifecycle(input: WebSocketLifecycleInput) {
    if (!this.enabled) {
      return
    }

    this.ensureSession()
    const route = this.currentRoute
    const owner = sanitizeString(input.owner, 80)
    const reuseKey = sanitizeString(input.reuseKey, 160)
    const socketInstanceId = sanitizeString(input.socketInstanceId, 160)
    if (!owner || !reuseKey || !socketInstanceId) {
      return
    }

    const mapKey = `${owner}:${reuseKey}:${socketInstanceId}`
    const occurredAt = nowIso()
    if (input.outcome === 'close') {
      this.activeWebSockets.delete(mapKey)
    } else {
      this.activeWebSockets.set(mapKey, {
        owner,
        reuse_key: reuseKey,
        channel_kind: input.channelKind,
        socket_instance_id: socketInstanceId,
        active: true,
        last_event_at: occurredAt,
      })
    }

    const activeConnections = this.countActiveWebSocketsForReuseKey(reuseKey)
    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: 'websocket.lifecycle',
      occurred_at: occurredAt,
      route,
      context: route.context,
      outcome: input.outcome,
      owner,
      reuse_key: reuseKey,
      channel_kind: input.channelKind,
      socket_instance_id: socketInstanceId,
      active_connections_for_reuse_key: activeConnections,
      close_code: input.closeCode,
      close_reason: sanitizeString(input.closeReason, 120),
      reconnect_attempt: input.reconnectAttempt,
    })

    this.trackWebSocketChurn({
      ...input,
      owner,
      reuseKey,
      socketInstanceId,
      activeConnections,
      occurredAt,
    })
  }

  exportBundle(): UiJournalBundle {
    const mode = import.meta.env.MODE || 'unknown'
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'

    return {
      session_id: this.sessionId,
      captured_at: nowIso(),
      release: {
        app: 'commandcenter1c-frontend',
        fingerprint: buildCorrelationFingerprint(mode, origin),
        mode,
        origin,
      },
      route: this.currentRoute,
      events: [...this.events],
      active_http_requests: Array.from(this.activeRequests.values()).map((request) => ({ ...request })),
      active_websockets_by_owner: this.buildActiveWebSocketsByOwner(),
      active_websockets_by_reuse_key: this.buildActiveWebSocketsByReuseKey(),
      recent_churn_anomalies: [...this.recentChurnAnomalies],
    }
  }

  private startSession() {
    this.reset()
    this.sessionId = generateRuntimeId('session')
    this.currentRoute = buildRouteSnapshot()
    this.lastRouteSignature = ''
    this.installWindowApi()
  }

  private ensureSession() {
    if (!this.enabled) {
      return
    }

    if (!this.sessionId) {
      this.startSession()
    }
  }

  private activateAction(meta: UiActionMeta): ActiveActionContext {
    this.ensureSession()
    const route = this.currentRoute
    const action: ActiveActionContext = {
      ui_action_id: generateRuntimeId('uia'),
      action_kind: meta.actionKind,
      action_name: toActionName(meta.actionKind, meta.actionName),
      action_source: meta.actionSource ?? 'explicit',
      route,
      context: {
        ...route.context,
        ...sanitizeContextRecord(meta.context),
      },
      timeout_id: null,
    }

    if (this.activeAction?.timeout_id) {
      clearTimeout(this.activeAction.timeout_id)
    }

    action.timeout_id = setTimeout(() => {
      if (this.activeAction?.ui_action_id === action.ui_action_id) {
        this.activeAction = null
      }
    }, ACTION_TTL_MS)

    this.activeAction = action
    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: 'ui.action',
      occurred_at: nowIso(),
      route,
      context: action.context,
      ui_action_id: action.ui_action_id,
      action_kind: action.action_kind,
      action_name: action.action_name,
      action_source: action.action_source,
    })
    return action
  }

  private resolveAction(uiActionId: string) {
    if (this.activeAction?.ui_action_id !== uiActionId) {
      return
    }
    if (this.activeAction.timeout_id) {
      clearTimeout(this.activeAction.timeout_id)
    }
    this.activeAction = null
  }

  private createSyntheticRequestAction(method: string, path: string): ActiveActionContext {
    const route = this.currentRoute
    const action: ActiveActionContext = {
      ui_action_id: generateRuntimeId('uia'),
      action_kind: 'request.boundary',
      action_name: `${method} ${path}`,
      action_source: 'synthetic_request',
      route,
      context: route.context,
      timeout_id: null,
    }

    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: 'ui.action',
      occurred_at: nowIso(),
      route,
      context: action.context,
      ui_action_id: action.ui_action_id,
      action_kind: action.action_kind,
      action_name: action.action_name,
      action_source: action.action_source,
    })
    return action
  }

  private recordUiError(
    eventType: UiErrorEvent['event_type'],
    error: unknown,
    details?: {
      component_stack?: string
      error_source?: string
    },
  ) {
    if (!this.enabled) {
      return
    }

    this.ensureSession()
    const normalized = normalizeErrorLike(error)
    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: eventType,
      occurred_at: nowIso(),
      route: this.currentRoute,
      context: this.currentRoute.context,
      ui_action_id: this.activeAction?.ui_action_id,
      outcome: 'error',
      error_name: normalized.name,
      error_message: normalized.message,
      error_source: sanitizeString(details?.error_source, 80),
      component_stack: details?.component_stack,
    })
  }

  private trackWebSocketChurn(input: WebSocketLifecycleInput & {
    owner: string
    reuseKey: string
    socketInstanceId: string
    activeConnections: number
    occurredAt: string
  }) {
    const historyKey = `${input.owner}:${input.reuseKey}`
    const now = Date.now()
    const history = this.websocketChurnHistory.get(historyKey) ?? []
    const shouldTrackTimestamp = input.outcome === 'connect' || input.outcome === 'reconnect'
    const nextHistory = shouldTrackTimestamp
      ? [...history, now].filter((timestamp) => now - timestamp <= WEBSOCKET_CHURN_WINDOW_MS)
      : history.filter((timestamp) => now - timestamp <= WEBSOCKET_CHURN_WINDOW_MS)
    this.websocketChurnHistory.set(historyKey, nextHistory)

    const isSharedLeak = input.channelKind === 'shared' && input.activeConnections > 1
    const isReconnectChurn = nextHistory.length >= WEBSOCKET_CHURN_THRESHOLD
    if (!isSharedLeak && !isReconnectChurn) {
      return
    }

    const churnEvent: WebSocketEvent = {
      event_id: generateRuntimeId('evt'),
      event_type: 'websocket.churn_warning',
      occurred_at: input.occurredAt,
      route: this.currentRoute,
      context: this.currentRoute.context,
      outcome: 'churn_warning',
      owner: input.owner,
      reuse_key: input.reuseKey,
      channel_kind: input.channelKind,
      socket_instance_id: input.socketInstanceId,
      active_connections_for_reuse_key: input.activeConnections,
      reconnect_attempt: input.reconnectAttempt,
    }

    this.pushEvent(churnEvent)
    this.recentChurnAnomalies.push(churnEvent)
    if (this.recentChurnAnomalies.length > 20) {
      this.recentChurnAnomalies.shift()
    }
  }

  private countActiveWebSocketsForReuseKey(reuseKey: string): number {
    let count = 0
    for (const socket of this.activeWebSockets.values()) {
      if (socket.active && socket.reuse_key === reuseKey) {
        count += 1
      }
    }
    return count
  }

  private buildActiveWebSocketsByOwner() {
    const summary: UiJournalBundle['active_websockets_by_owner'] = {}

    for (const socket of this.activeWebSockets.values()) {
      if (!socket.active) {
        continue
      }
      const existing = summary[socket.owner] ?? {
        active_connection_count: 0,
        channel_kinds: [] as WebSocketChannelKind[],
        reuse_keys: [] as string[],
        socket_instance_ids: [] as string[],
      }
      existing.active_connection_count += 1
      if (!existing.channel_kinds.includes(socket.channel_kind)) {
        existing.channel_kinds.push(socket.channel_kind)
      }
      if (!existing.reuse_keys.includes(socket.reuse_key)) {
        existing.reuse_keys.push(socket.reuse_key)
      }
      if (!existing.socket_instance_ids.includes(socket.socket_instance_id)) {
        existing.socket_instance_ids.push(socket.socket_instance_id)
      }
      summary[socket.owner] = existing
    }

    return summary
  }

  private buildActiveWebSocketsByReuseKey() {
    const summary: UiJournalBundle['active_websockets_by_reuse_key'] = {}

    for (const socket of this.activeWebSockets.values()) {
      if (!socket.active) {
        continue
      }
      const existing = summary[socket.reuse_key] ?? {
        active_connection_count: 0,
        channel_kind: socket.channel_kind,
        owner: socket.owner,
        socket_instance_ids: [] as string[],
      }
      existing.active_connection_count += 1
      if (!existing.socket_instance_ids.includes(socket.socket_instance_id)) {
        existing.socket_instance_ids.push(socket.socket_instance_id)
      }
      summary[socket.reuse_key] = existing
    }

    return summary
  }

  private pushEvent(event: UiJournalEvent) {
    this.events.push(event)
    if (this.events.length > JOURNAL_MAX_EVENTS) {
      this.events.splice(0, this.events.length - JOURNAL_MAX_EVENTS)
    }
  }

  private reset() {
    if (this.activeAction?.timeout_id) {
      clearTimeout(this.activeAction.timeout_id)
    }
    this.activeAction = null
    this.events.splice(0, this.events.length)
    this.activeRequests.clear()
    this.activeWebSockets.clear()
    this.websocketChurnHistory.clear()
    this.recentChurnAnomalies.splice(0, this.recentChurnAnomalies.length)
    this.sessionId = null
    this.currentRoute = buildRouteSnapshot()
    this.lastRouteSignature = ''
  }

  private installWindowApi() {
    if (typeof window === 'undefined') {
      return
    }

    const api: WindowGlobalJournalApi = {
      clear: () => this.clear(),
      exportBundle: () => this.exportBundle(),
      isEnabled: () => this.enabled,
    }

    window.__CC1C_UI_JOURNAL__ = api
  }
}

const isPromiseLike = <T>(value: unknown): value is PromiseLike<T> => (
  typeof value === 'object'
    && value !== null
    && 'then' in value
    && typeof (value as PromiseLike<T>).then === 'function'
)

const normalizeErrorLike = (error: unknown): {
  name?: string
  message?: string
} => {
  if (error instanceof Error) {
    return {
      name: sanitizeString(error.name, 80),
      message: sanitizeString(error.message, 240),
    }
  }

  if (typeof error === 'string') {
    return {
      message: sanitizeString(error, 240),
    }
  }

  if (error && typeof error === 'object') {
    const raw = error as { name?: unknown; message?: unknown; detail?: unknown }
    return {
      name: sanitizeString(raw.name, 80),
      message: sanitizeString(raw.message ?? raw.detail, 240),
    }
  }

  return {
    message: sanitizeString(String(error), 240),
  }
}

export const uiActionJournal = new UiActionJournal()

export const createUiRuntimeId = (prefix: string) => generateRuntimeId(prefix)

export const setUiActionJournalEnabled = (enabled: boolean) => {
  uiActionJournal.setEnabled(enabled)
}

export const clearUiActionJournal = () => {
  uiActionJournal.clear()
}

export const exportUiActionJournalBundle = () => uiActionJournal.exportBundle()

export const captureUiRouteTransition = (location?: RouteLocationInput) => {
  uiActionJournal.captureRoute(location)
}

export const trackUiAction = <T>(meta: UiActionMeta, handler?: () => T) => (
  uiActionJournal.trackAction(meta, handler)
)

export const startUiHttpRequest = (input: StartHttpRequestInput) => (
  uiActionJournal.startHttpRequest(input)
)

export const completeUiHttpRequest = (input: CompleteHttpRequestInput) => {
  uiActionJournal.completeHttpRequest(input)
}

export const recordUiErrorBoundary = (error: Error, componentStack?: string | null) => {
  uiActionJournal.recordErrorBoundary(error, componentStack)
}

export const recordUiWindowError = (error: unknown, details?: { error_source?: string }) => {
  uiActionJournal.recordWindowError(error, details)
}

export const recordUiUnhandledRejection = (reason: unknown) => {
  uiActionJournal.recordUnhandledRejection(reason)
}

export const recordUiWebSocketLifecycle = (input: WebSocketLifecycleInput) => {
  uiActionJournal.recordWebSocketLifecycle(input)
}

export const buildUiProblemCorrelation = (value: unknown): RequestProblemDetails | undefined => {
  if (!value || typeof value !== 'object') {
    return undefined
  }

  const payload = value as {
    code?: unknown
    title?: unknown
    request_id?: unknown
    ui_action_id?: unknown
  }
  return {
    code: sanitizeString(payload.code, 80),
    title: sanitizeString(payload.title, 160),
    request_id: sanitizeString(payload.request_id, 160),
    ui_action_id: sanitizeString(payload.ui_action_id, 160),
  }
}

export const normalizeUiRequestPathForSummary = (rawPath?: string) => normalizeRequestPath(rawPath)

declare global {
  interface Window {
    __CC1C_ENV__?: Partial<Record<'VITE_BASE_HOST' | 'VITE_API_URL' | 'VITE_WS_HOST', string>>
    __CC1C_UI_JOURNAL__?: WindowGlobalJournalApi
  }
}

export const __TESTING__ = {
  buildRouteSnapshot,
  sanitizeContextRecord,
  sanitizeString,
  normalizeRequestPath,
}
