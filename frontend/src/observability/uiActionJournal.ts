type PrimitiveValue = string | number | boolean | null

type RouteLocationInput = {
  pathname?: string
  search?: string
  hash?: string
}

export type RouteSnapshot = {
  path: string
  search: string
  hash: string
  context: Record<string, PrimitiveValue>
}

type ActionSource = 'explicit' | 'navigation' | 'synthetic_request'
type ActionKind =
  | 'route.change'
  | 'route.navigate'
  | 'modal.submit'
  | 'modal.confirm'
  | 'drawer.submit'
  | 'operator.action'
  | 'request.boundary'
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
  surface_id?: string
  control_id?: string
}

export type UiRouteParamDiffEntry = {
  from: PrimitiveValue | null
  to: PrimitiveValue | null
}

type UiRouteParamDiff = Record<string, UiRouteParamDiffEntry>

type RouteNavigationMode = 'push' | 'replace'

type RouteWriteAttribution = {
  surface_id?: string
  route_writer_owner?: string
  write_reason?: string
  navigation_mode?: RouteNavigationMode
  param_diff?: UiRouteParamDiff
  caused_by_ui_action_id?: string
}

type RouteEvent = {
  event_id: string
  event_type: 'route.transition'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  ui_action_id?: string
  outcome: 'navigated'
} & RouteWriteAttribution

type RouteLoopWarningEvent = {
  event_id: string
  event_type: 'route.loop_warning'
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  ui_action_id?: string
  outcome: 'loop_warning'
  route_path: string
  surface_id?: string
  oscillating_keys: string[]
  observed_states: Record<string, PrimitiveValue>[]
  writer_owners: string[]
  transition_count: number
  window_ms: number
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

export type UiJournalEvent =
  | RouteEvent
  | RouteLoopWarningEvent
  | ActionEvent
  | HttpFailureEvent
  | UiErrorEvent
  | WebSocketEvent
type UiJournalListener = (event: UiJournalEvent) => void

type ActiveActionContext = {
  ui_action_id: string
  action_kind: ActionKind
  action_name: string
  action_source: ActionSource
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  surface_id?: string
  control_id?: string
  timeout_id: ReturnType<typeof setTimeout> | null
  settle_token: { canceled: boolean } | null
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
  synthetic_action?: PendingSyntheticAction
}

type PendingSyntheticAction = {
  occurred_at: string
  route: RouteSnapshot
  context: Record<string, PrimitiveValue>
  ui_action_id: string
  action_kind: 'request.boundary'
  action_name: string
  action_source: 'synthetic_request'
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
  surfaceId?: string
  controlId?: string
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

type UiRouteWriteMeta = {
  surfaceId?: string
  routeWriterOwner: string
  writeReason: string
  navigationMode?: RouteNavigationMode
  paramDiff?: Record<string, { from?: unknown; to?: unknown }>
  causedByUiActionId?: string | null
}

type PendingRouteWrite = {
  queued_at_ms: number
  surface_id?: string
  route_writer_owner: string
  write_reason: string
  navigation_mode: RouteNavigationMode
  param_diff?: UiRouteParamDiff
  caused_by_ui_action_id?: string
}

type RecentRouteTransition = {
  occurred_at_ms: number
  route_path: string
  surface_id?: string
  route_state: Record<string, PrimitiveValue>
  route_state_signature: string
  writer_owner?: string
  ui_action_id?: string
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
const ROUTE_WRITE_TTL_MS = 5_000
const SLOW_REQUEST_THRESHOLD_MS = 2_000
const WEBSOCKET_CHURN_WINDOW_MS = 60_000
const WEBSOCKET_CHURN_THRESHOLD = 3
const ROUTE_LOOP_WINDOW_MS = 8_000
const ROUTE_LOOP_MIN_TRANSITIONS = 4
const ROUTE_LOOP_HISTORY_MAX = 32
const ACTION_CONTEXT_ALLOWLIST = new Set([
  'canonical_id',
  'cluster_id',
  'control_id',
  'database_id',
  'detail_after',
  'detail_before',
  'entity_type',
  'from_tab',
  'launch_id',
  'manual_operation',
  'next_is_active',
  'node_type',
  'review_item_id',
  'surface_id',
  'to_tab',
])
const ROUTE_CONTEXT_ALLOWLIST = new Set([
  'artifact',
  'batch',
  'binding',
  'cluster',
  'clusterid',
  'context',
  'control',
  'canonicalid',
  'database',
  'databaseid',
  'detail',
  'direction',
  'edge',
  'entitytype',
  'execution',
  'execution_id',
  'focus',
  'launchid',
  'mode',
  'operation',
  'organization',
  'period_end',
  'period_start',
  'pool',
  'quarter_start',
  'run',
  'service',
  'setting',
  'stage',
  'tab',
  'template',
  'tenant',
  'user',
  'view',
  'workflow',
  'reviewitemid',
])
const ROUTE_LOOP_KEY_ALLOWLIST = [
  'canonicalId',
  'clusterId',
  'databaseId',
  'detail',
  'entityType',
  'launchId',
  'reviewItemId',
  'tab',
] as const
const SENSITIVE_KEY_PATTERN = /(auth|authorization|cookie|csrf|passwd|password|secret|session|token)/i
const SECRET_VALUE_PATTERN = /\b(password|passwd|pwd|token|authorization|secret|cookie)\b[:=]\s*([^\s,;]+)/gi
const DEFAULT_RELEASE_FINGERPRINT = '0.0.0+unknown'

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

const sanitizePrimitiveValue = (value: unknown, maxLength = 160): PrimitiveValue | undefined => {
  if (value === null) {
    return null
  }
  if (typeof value === 'string') {
    return sanitizeString(value, maxLength)
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return value
  }
  return undefined
}

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

const isActionContextKeyAllowed = (key: string): boolean => {
  const normalized = key.trim().toLowerCase()
  if (!normalized || SENSITIVE_KEY_PATTERN.test(normalized)) {
    return false
  }
  return ACTION_CONTEXT_ALLOWLIST.has(normalized) || isRouteContextKeyAllowed(normalized)
}

const sanitizeContextRecord = (value: Record<string, unknown> | undefined): Record<string, PrimitiveValue> => {
  if (!value) {
    return {}
  }

  const normalized: Record<string, PrimitiveValue> = {}
  for (const [rawKey, rawValue] of Object.entries(value)) {
    const key = rawKey.trim()
    if (!key || !isActionContextKeyAllowed(key)) {
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

const normalizeSearchParamsInput = (
  value: URLSearchParams | string,
): URLSearchParams => (
  value instanceof URLSearchParams
    ? new URLSearchParams(value)
    : new URLSearchParams(value.startsWith('?') ? value.slice(1) : value)
)

const buildRouteParamDiff = (
  current: URLSearchParams | string,
  next: URLSearchParams | string,
): UiRouteParamDiff => {
  const currentParams = normalizeSearchParamsInput(current)
  const nextParams = normalizeSearchParamsInput(next)
  const keys = new Set<string>([...currentParams.keys(), ...nextParams.keys()])
  const diff: UiRouteParamDiff = {}

  for (const key of keys) {
    if (!isRouteContextKeyAllowed(key)) {
      continue
    }
    const from = sanitizePrimitiveValue(currentParams.get(key), 120) ?? null
    const to = sanitizePrimitiveValue(nextParams.get(key), 120) ?? null
    if (from === to) {
      continue
    }
    diff[key] = { from, to }
  }

  return diff
}

const sanitizeRouteParamDiff = (
  value: Record<string, { from?: unknown; to?: unknown }> | undefined,
): UiRouteParamDiff | undefined => {
  if (!value) {
    return undefined
  }

  const normalized: UiRouteParamDiff = {}
  for (const [key, rawEntry] of Object.entries(value)) {
    if (!isRouteContextKeyAllowed(key) || !rawEntry || typeof rawEntry !== 'object') {
      continue
    }
    const from = sanitizePrimitiveValue(rawEntry.from, 120) ?? null
    const to = sanitizePrimitiveValue(rawEntry.to, 120) ?? null
    if (from === to) {
      continue
    }
    normalized[key] = { from, to }
  }

  return Object.keys(normalized).length > 0 ? normalized : undefined
}

const sanitizeRouteWriteMeta = (
  meta: UiRouteWriteMeta,
  fallbackActionId: string | null,
): PendingRouteWrite | null => {
  const routeWriterOwner = sanitizeString(meta.routeWriterOwner, 120)
  const writeReason = sanitizeString(meta.writeReason, 120)
  if (!routeWriterOwner || !writeReason) {
    return null
  }

  return {
    queued_at_ms: Date.now(),
    surface_id: sanitizeString(meta.surfaceId, 120),
    route_writer_owner: routeWriterOwner,
    write_reason: writeReason,
    navigation_mode: meta.navigationMode === 'push' ? 'push' : 'replace',
    param_diff: sanitizeRouteParamDiff(meta.paramDiff),
    caused_by_ui_action_id: sanitizeString(meta.causedByUiActionId ?? fallbackActionId, 160),
  }
}

const pickRouteLoopState = (route: RouteSnapshot): Record<string, PrimitiveValue> => {
  const state: Record<string, PrimitiveValue> = {}
  for (const key of ROUTE_LOOP_KEY_ALLOWLIST) {
    const value = route.context[key]
    if (value !== undefined) {
      state[key] = value
    }
  }
  return state
}

const stableSerializePrimitiveRecord = (value: Record<string, PrimitiveValue>): string => (
  JSON.stringify(
    Object.keys(value)
      .sort()
      .reduce<Record<string, PrimitiveValue>>((acc, key) => {
        acc[key] = value[key]
        return acc
      }, {}),
  )
)

const collectRouteStateDiffKeys = (
  first: Record<string, PrimitiveValue>,
  second: Record<string, PrimitiveValue>,
): string[] => (
  Array.from(new Set([...Object.keys(first), ...Object.keys(second)]))
    .filter((key) => first[key] !== second[key])
    .sort()
)

const collectAllowedRouteParams = (
  rawValue: string,
  context: Record<string, PrimitiveValue>,
): URLSearchParams => {
  const sanitizedParams = new URLSearchParams()
  const params = new URLSearchParams(rawValue.startsWith('?') ? rawValue.slice(1) : rawValue)

  params.forEach((value, key) => {
    if (!isRouteContextKeyAllowed(key)) {
      return
    }
    const safeValue = sanitizeString(value, 120)
    if (safeValue !== undefined) {
      context[key] = safeValue
      sanitizedParams.set(key, safeValue)
    }
  })

  return sanitizedParams
}

const sanitizeRouteHash = (
  rawHash: string,
  context: Record<string, PrimitiveValue>,
): string => {
  const normalized = rawHash.trim()
  if (!normalized) {
    return ''
  }

  const fragment = normalized.startsWith('#') ? normalized.slice(1) : normalized
  if (!fragment || !/[=&]/.test(fragment)) {
    return ''
  }

  const sanitizedParams = collectAllowedRouteParams(fragment, context)
  if (sanitizedParams.size === 0) {
    return ''
  }

  return `#${sanitizedParams.toString()}`
}

const buildRouteSnapshot = (location?: RouteLocationInput): RouteSnapshot => {
  const pathname = location?.pathname ?? (typeof window !== 'undefined' ? window.location.pathname : '/')
  const rawSearch = location?.search ?? (typeof window !== 'undefined' ? window.location.search : '')
  const rawHash = location?.hash ?? (typeof window !== 'undefined' ? window.location.hash : '')
  const context: Record<string, PrimitiveValue> = {}
  const sanitizedSearchParams = collectAllowedRouteParams(rawSearch, context)
  const hash = sanitizeRouteHash(rawHash, context)

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

const buildReleaseFingerprint = (): string => {
  const version = sanitizeString(import.meta.env.VITE_CC1C_APP_VERSION, 80) ?? '0.0.0'
  const buildId = sanitizeString(import.meta.env.VITE_CC1C_BUILD_ID, 120) ?? 'unknown'
  const fingerprint = `${version}+${buildId}`

  return fingerprint === DEFAULT_RELEASE_FINGERPRINT
    ? DEFAULT_RELEASE_FINGERPRINT
    : fingerprint
}

class UiActionJournal {
  private enabled = false
  private sessionId: string | null = null
  private readonly events: UiJournalEvent[] = []
  private readonly listeners = new Set<UiJournalListener>()
  private readonly activeRequests = new Map<string, ActiveHttpRequest>()
  private readonly activeWebSockets = new Map<string, ActiveWebSocket>()
  private readonly websocketChurnHistory = new Map<string, number[]>()
  private readonly recentChurnAnomalies: WebSocketEvent[] = []
  private currentRoute: RouteSnapshot = buildRouteSnapshot()
  private lastRouteSignature = ''
  private readonly activeActions: ActiveActionContext[] = []
  private currentExecutionActionId: string | null = null
  private pendingRouteWrite: PendingRouteWrite | null = null
  private readonly recentRouteTransitions: RecentRouteTransition[] = []
  private readonly recentRouteLoopWarnings = new Map<string, number>()

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
    const occurredAt = nowIso()
    const pendingRouteWrite = this.consumePendingRouteWrite()
    const routeEvent: RouteEvent = {
      event_id: generateRuntimeId('evt'),
      event_type: 'route.transition',
      occurred_at: occurredAt,
      route,
      context: route.context,
      ui_action_id: pendingRouteWrite?.caused_by_ui_action_id,
      outcome: 'navigated',
      surface_id: pendingRouteWrite?.surface_id,
      route_writer_owner: pendingRouteWrite?.route_writer_owner,
      write_reason: pendingRouteWrite?.write_reason,
      navigation_mode: pendingRouteWrite?.navigation_mode,
      param_diff: pendingRouteWrite?.param_diff,
      caused_by_ui_action_id: pendingRouteWrite?.caused_by_ui_action_id,
    }
    this.pushEvent(routeEvent)
    this.trackRouteLoop(routeEvent)
  }

  trackAction<T>(meta: UiActionMeta, handler?: (action: { uiActionId: string }) => T): T | undefined {
    const fallbackActionId = this.getCurrentContextActionId() ?? generateRuntimeId('uia')
    if (!this.enabled) {
      return handler?.({ uiActionId: fallbackActionId })
    }

    const action = this.activateAction(meta)

    try {
      const result = this.runWithActionContext(action.ui_action_id, () => (
        handler?.({ uiActionId: action.ui_action_id })
      ))
      if (isPromiseLike(result)) {
        return Promise.resolve(result)
          .finally(() => {
            this.resolveAction(action.ui_action_id)
          }) as T
      }
      this.deferActionResolution(action.ui_action_id)
      return result
    } catch (error) {
      this.recordUiError('ui.error.global', error, {
        error_source: 'ui_action_handler',
      })
      this.resolveAction(action.ui_action_id)
      throw error
    }
  }

  queueRouteWrite(meta: UiRouteWriteMeta) {
    if (!this.enabled) {
      return
    }

    this.ensureSession()
    this.pendingRouteWrite = sanitizeRouteWriteMeta(meta, this.getCurrentContextActionId())
  }

  startHttpRequest(input: StartHttpRequestInput) {
    const currentActionId = this.getCurrentContextActionId()
    if (!this.enabled) {
      return {
        requestId: generateRuntimeId('req'),
        uiActionId: currentActionId ?? generateRuntimeId('uia'),
      }
    }

    this.ensureSession()

    const route = this.currentRoute
    const method = sanitizeString(input.method?.toUpperCase(), 16) ?? 'GET'
    const path = normalizeRequestPath(input.path)
    const requestId = generateRuntimeId('req')
    const startedAt = nowIso()
    const uiActionId = currentActionId ?? generateRuntimeId('uia')
    const requestContext = {
      ...route.context,
      ...sanitizeContextRecord(input.context),
    }
    const activeRequest: ActiveHttpRequest = {
      request_id: requestId,
      ui_action_id: uiActionId,
      method,
      path,
      started_at: startedAt,
      started_at_ms: Date.now(),
      route,
      context: requestContext,
    }
    if (!currentActionId) {
      activeRequest.synthetic_action = this.createSyntheticRequestAction({
        method,
        path,
        occurredAt: startedAt,
        route,
        context: requestContext,
        uiActionId,
      })
    }

    this.activeRequests.set(requestId, activeRequest)
    return {
      requestId,
      uiActionId,
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
      this.materializeSyntheticRequestAction(activeRequest)
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
      this.materializeSyntheticRequestAction(activeRequest)
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
        fingerprint: buildReleaseFingerprint(),
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

  subscribe(listener: UiJournalListener) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
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
      surface_id: sanitizeString(meta.surfaceId, 120),
      control_id: sanitizeString(meta.controlId, 120),
      timeout_id: null,
      settle_token: null,
    }

    action.timeout_id = setTimeout(() => {
      this.resolveAction(action.ui_action_id)
    }, ACTION_TTL_MS)

    this.activeActions.push(action)
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
      surface_id: action.surface_id,
      control_id: action.control_id,
    })
    return action
  }

  private resolveAction(uiActionId: string) {
    const index = this.activeActions.findIndex((action) => action.ui_action_id === uiActionId)
    if (index < 0) {
      return
    }
    const [action] = this.activeActions.splice(index, 1)
    this.clearActionTimers(action)
  }

  private deferActionResolution(uiActionId: string) {
    const action = this.findActiveAction(uiActionId)
    if (!action) {
      return
    }
    if (action.settle_token) {
      action.settle_token.canceled = true
    }
    const settleToken = { canceled: false }
    action.settle_token = settleToken
    queueMicrotask(() => {
      if (settleToken.canceled) {
        return
      }
      if (action.settle_token === settleToken) {
        action.settle_token = null
      }
      this.resolveAction(uiActionId)
    })
  }

  private createSyntheticRequestAction(input: {
    method: string
    path: string
    occurredAt: string
    route: RouteSnapshot
    context: Record<string, PrimitiveValue>
    uiActionId: string
  }): PendingSyntheticAction {
    return {
      occurred_at: input.occurredAt,
      route: input.route,
      context: input.context,
      ui_action_id: input.uiActionId,
      action_kind: 'request.boundary',
      action_name: `${input.method} ${input.path}`,
      action_source: 'synthetic_request',
    }
  }

  private materializeSyntheticRequestAction(activeRequest: ActiveHttpRequest) {
    const action = activeRequest.synthetic_action
    if (!action) {
      return
    }

    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: 'ui.action',
      occurred_at: action.occurred_at,
      route: action.route,
      context: action.context,
      ui_action_id: action.ui_action_id,
      action_kind: action.action_kind,
      action_name: action.action_name,
      action_source: action.action_source,
    })
    delete activeRequest.synthetic_action
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
      ui_action_id: this.getCurrentContextActionId() ?? undefined,
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

  private consumePendingRouteWrite(): PendingRouteWrite | null {
    const pendingRouteWrite = this.pendingRouteWrite
    this.pendingRouteWrite = null
    if (!pendingRouteWrite) {
      return null
    }
    if (Date.now() - pendingRouteWrite.queued_at_ms > ROUTE_WRITE_TTL_MS) {
      return null
    }
    return pendingRouteWrite
  }

  private trackRouteLoop(event: RouteEvent) {
    const routeState = pickRouteLoopState(event.route)
    if (Object.keys(routeState).length === 0) {
      return
    }

    const occurredAtMs = Date.now()
    const routeStateSignature = stableSerializePrimitiveRecord(routeState)
    this.recentRouteTransitions.push({
      occurred_at_ms: occurredAtMs,
      route_path: event.route.path,
      surface_id: event.surface_id,
      route_state: routeState,
      route_state_signature: routeStateSignature,
      writer_owner: event.route_writer_owner,
      ui_action_id: event.caused_by_ui_action_id ?? event.ui_action_id,
    })
    while (this.recentRouteTransitions.length > 0) {
      const first = this.recentRouteTransitions[0]
      if (!first || occurredAtMs - first.occurred_at_ms <= ROUTE_LOOP_WINDOW_MS) {
        break
      }
      this.recentRouteTransitions.shift()
    }
    while (this.recentRouteTransitions.length > ROUTE_LOOP_HISTORY_MAX) {
      this.recentRouteTransitions.shift()
    }

    const candidates = this.recentRouteTransitions.filter((entry) => entry.route_path === event.route.path)
    if (candidates.length < ROUTE_LOOP_MIN_TRANSITIONS) {
      return
    }

    const sequence = candidates.slice(-ROUTE_LOOP_MIN_TRANSITIONS)
    const [first, second, third, fourth] = sequence
    if (!first || !second || !third || !fourth) {
      return
    }

    const firstSignature = first.route_state_signature
    const secondSignature = second.route_state_signature
    if (
      firstSignature === secondSignature
      || firstSignature !== third.route_state_signature
      || secondSignature !== fourth.route_state_signature
    ) {
      return
    }

    const oscillatingKeys = collectRouteStateDiffKeys(first.route_state, second.route_state)
    if (oscillatingKeys.length === 0) {
      return
    }

    const warningSignature = `${event.route.path}|${oscillatingKeys.join(',')}|${firstSignature}|${secondSignature}`
    const lastWarningAtMs = this.recentRouteLoopWarnings.get(warningSignature) ?? 0
    if (occurredAtMs - lastWarningAtMs < ROUTE_LOOP_WINDOW_MS) {
      return
    }
    this.recentRouteLoopWarnings.set(warningSignature, occurredAtMs)
    for (const [signature, seenAt] of this.recentRouteLoopWarnings.entries()) {
      if (occurredAtMs - seenAt > ROUTE_LOOP_WINDOW_MS) {
        this.recentRouteLoopWarnings.delete(signature)
      }
    }

    const observedStates = Array.from(
      new Map(
        [first, second, third, fourth].map((entry) => [
          entry.route_state_signature,
          entry.route_state,
        ]),
      ).values(),
    )
    const writerOwners = Array.from(
      new Set(sequence.map((entry) => entry.writer_owner).filter((value): value is string => Boolean(value))),
    )
    const uiActionId = [...sequence]
      .reverse()
      .map((entry) => entry.ui_action_id)
      .find((value): value is string => Boolean(value))
    const transitionCount = candidates.filter((entry) => (
      entry.route_state_signature === firstSignature || entry.route_state_signature === secondSignature
    )).length

    this.pushEvent({
      event_id: generateRuntimeId('evt'),
      event_type: 'route.loop_warning',
      occurred_at: event.occurred_at,
      route: event.route,
      context: event.route.context,
      ui_action_id: uiActionId,
      outcome: 'loop_warning',
      route_path: event.route.path,
      surface_id: event.surface_id ?? fourth.surface_id,
      oscillating_keys: oscillatingKeys,
      observed_states: observedStates,
      writer_owners: writerOwners,
      transition_count: transitionCount,
      window_ms: Math.max(0, fourth.occurred_at_ms - first.occurred_at_ms),
    })
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
    for (const listener of this.listeners) {
      listener(event)
    }
  }

  private reset() {
    for (const action of this.activeActions) {
      this.clearActionTimers(action)
    }
    this.activeActions.splice(0, this.activeActions.length)
    this.events.splice(0, this.events.length)
    this.activeRequests.clear()
    this.activeWebSockets.clear()
    this.websocketChurnHistory.clear()
    this.recentChurnAnomalies.splice(0, this.recentChurnAnomalies.length)
    this.pendingRouteWrite = null
    this.recentRouteTransitions.splice(0, this.recentRouteTransitions.length)
    this.recentRouteLoopWarnings.clear()
    this.sessionId = null
    this.currentRoute = buildRouteSnapshot()
    this.lastRouteSignature = ''
    this.currentExecutionActionId = null
  }

  private getCurrentAction(): ActiveActionContext | null {
    if (this.activeActions.length === 0) {
      return null
    }
    return this.activeActions[this.activeActions.length - 1] ?? null
  }

  private findActiveAction(uiActionId: string): ActiveActionContext | undefined {
    return this.activeActions.find((action) => action.ui_action_id === uiActionId)
  }

  private getCurrentContextActionId(): string | null {
    return this.currentExecutionActionId ?? this.getCurrentAction()?.ui_action_id ?? null
  }

  private runWithActionContext<T>(uiActionId: string | null, handler: () => T): T {
    const previousActionId = this.currentExecutionActionId
    this.currentExecutionActionId = uiActionId
    try {
      return handler()
    } finally {
      this.currentExecutionActionId = previousActionId
    }
  }

  private clearActionTimers(action: ActiveActionContext) {
    if (action.timeout_id) {
      clearTimeout(action.timeout_id)
    }
    if (action.settle_token) {
      action.settle_token.canceled = true
      action.settle_token = null
    }
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

export const trackUiAction = <T>(meta: UiActionMeta, handler?: (action: { uiActionId: string }) => T) => (
  uiActionJournal.trackAction(meta, handler)
)

export const queueUiRouteWrite = (meta: UiRouteWriteMeta) => {
  uiActionJournal.queueRouteWrite(meta)
}

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

export const subscribeToUiActionJournal = (listener: UiJournalListener) => (
  uiActionJournal.subscribe(listener)
)

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
export const buildUiRouteParamDiff = (
  current: URLSearchParams | string,
  next: URLSearchParams | string,
) => buildRouteParamDiff(current, next)

declare global {
  interface Window {
    __CC1C_ENV__?: Partial<Record<'VITE_BASE_HOST' | 'VITE_API_URL' | 'VITE_WS_HOST', string>>
    __CC1C_UI_JOURNAL__?: WindowGlobalJournalApi
  }
}

export const __TESTING__ = {
  buildRouteSnapshot,
  buildRouteParamDiff,
  buildReleaseFingerprint,
  sanitizeContextRecord,
  sanitizeRouteHash,
  sanitizeString,
  normalizeRequestPath,
}
