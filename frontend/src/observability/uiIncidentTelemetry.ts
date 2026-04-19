import type { SystemBootstrapResponse } from '../api/generated/model/systemBootstrapResponse'
import { queryKeys } from '../api/queries/queryKeys'
import { getApiBaseUrl } from '../api/baseUrl'
import { LOCALE_REQUEST_HEADER } from '../i18n/constants'
import { getCurrentAppLocale } from '../i18n/localeStore'
import { getAuthToken } from '../lib/authState'
import { queryClient } from '../lib/queryClient'

import {
  createUiRuntimeId,
  exportUiActionJournalBundle,
  subscribeToUiActionJournal,
  type RouteSnapshot,
  type UiJournalBundle,
  type UiJournalEvent,
} from './uiActionJournal'

type FlushReason = 'size_threshold' | 'time_threshold' | 'pagehide' | 'shutdown' | 'manual'
type SendOutcome = 'success' | 'retry' | 'drop'
type TelemetryActor = {
  user_id: number
  username: string
  is_staff: boolean
}
type UiIncidentTelemetryEnvelope = {
  batch_id: string
  flush_reason: FlushReason
  session_id: string | null
  tenant_id: string | null
  actor: TelemetryActor | null
  release: UiJournalBundle['release']
  route: RouteSnapshot
  dropped_events_count: number
  events: UiJournalEvent[]
}

const INGEST_URL = `${getApiBaseUrl()}/api/v2/ui/incident-telemetry/ingest/`
const FLUSH_INTERVAL_MS = 5_000
const RETRY_DELAY_MS = 15_000
const MAX_BATCH_EVENTS = 24
const MAX_BUFFERED_EVENTS = 120
const MAX_QUEUED_BATCHES = 4

const getEventPriority = (event: UiJournalEvent): number => {
  switch (event.event_type) {
    case 'route.transition':
    case 'websocket.lifecycle':
      return 0
    case 'ui.action':
      return 1
    case 'http.request.slow':
    case 'websocket.churn_warning':
      return 2
    case 'http.request.failure':
    case 'ui.error.boundary':
    case 'ui.error.global':
    case 'ui.error.unhandled_rejection':
      return 3
    default:
      return 1
  }
}

const shouldPersistEvent = (event: UiJournalEvent): boolean => {
  switch (event.event_type) {
    case 'route.transition':
    case 'ui.action':
    case 'http.request.failure':
    case 'http.request.slow':
    case 'ui.error.boundary':
    case 'ui.error.global':
    case 'ui.error.unhandled_rejection':
    case 'websocket.churn_warning':
      return true
    case 'websocket.lifecycle':
      return event.outcome === 'reconnect'
        || (event.outcome === 'close' && (event.close_code ?? 1000) >= 1011)
    default:
      return false
  }
}

const resolveTelemetryContext = (): {
  tenantId: string | null
  actor: TelemetryActor | null
} => {
  const bootstrap = queryClient.getQueryData<SystemBootstrapResponse>(queryKeys.shell.bootstrap())
  const tenantId = localStorage.getItem('active_tenant_id')
    ?? bootstrap?.tenant_context.active_tenant_id
    ?? null

  if (!bootstrap?.me) {
    return { tenantId, actor: null }
  }

  return {
    tenantId,
    actor: {
      user_id: bootstrap.me.id,
      username: bootstrap.me.username,
      is_staff: bootstrap.me.is_staff,
    },
  }
}

class UiIncidentTelemetryUploader {
  private enabled = false
  private unsubscribe: (() => void) | null = null
  private flushTimer: number | null = null
  private retryTimer: number | null = null
  private inflight = false
  private readonly bufferedEvents: UiJournalEvent[] = []
  private readonly queuedBatches: UiIncidentTelemetryEnvelope[] = []
  private droppedEventsCount = 0

  setEnabled(enabled: boolean) {
    if (this.enabled === enabled) {
      return
    }

    this.enabled = enabled
    if (!enabled) {
      this.stop()
      return
    }

    this.start()
  }

  private start() {
    this.unsubscribe = subscribeToUiActionJournal((event) => {
      this.handleJournalEvent(event)
    })
    window.addEventListener('pagehide', this.handlePageHide)
  }

  private stop() {
    this.unsubscribe?.()
    this.unsubscribe = null
    window.removeEventListener('pagehide', this.handlePageHide)
    this.clearTimers()
    this.bufferedEvents.splice(0, this.bufferedEvents.length)
    this.queuedBatches.splice(0, this.queuedBatches.length)
    this.droppedEventsCount = 0
    this.inflight = false
  }

  private handleJournalEvent(event: UiJournalEvent) {
    if (!this.enabled || !shouldPersistEvent(event)) {
      return
    }

    this.bufferedEvents.push(event)
    this.trimBufferedEvents()

    if (this.bufferedEvents.length >= MAX_BATCH_EVENTS) {
      this.enqueueBuffered('size_threshold')
      return
    }

    this.armFlushTimer()
  }

  private readonly handlePageHide = () => {
    if (!this.enabled) {
      return
    }
    this.enqueueBuffered('pagehide', { drain: false })
    void this.drainQueue({ keepalive: true })
  }

  private armFlushTimer() {
    if (this.flushTimer !== null || this.bufferedEvents.length === 0) {
      return
    }
    this.flushTimer = window.setTimeout(() => {
      this.flushTimer = null
      this.enqueueBuffered('time_threshold')
    }, FLUSH_INTERVAL_MS)
  }

  private clearTimers() {
    if (this.flushTimer !== null) {
      window.clearTimeout(this.flushTimer)
      this.flushTimer = null
    }
    if (this.retryTimer !== null) {
      window.clearTimeout(this.retryTimer)
      this.retryTimer = null
    }
  }

  private enqueueBuffered(reason: FlushReason, options?: { drain?: boolean }) {
    if (this.bufferedEvents.length === 0) {
      return
    }

    const bundle = exportUiActionJournalBundle()
    const { tenantId, actor } = resolveTelemetryContext()
    const events = this.bufferedEvents.splice(0, this.bufferedEvents.length)
    const batch: UiIncidentTelemetryEnvelope = {
      batch_id: createUiRuntimeId('uibatch'),
      flush_reason: reason,
      session_id: bundle.session_id,
      tenant_id: tenantId,
      actor,
      release: bundle.release,
      route: bundle.route,
      dropped_events_count: this.droppedEventsCount,
      events,
    }

    this.droppedEventsCount = 0
    this.queuedBatches.push(batch)
    this.clearTimers()
    this.trimQueuedBatches()
    if (options?.drain !== false) {
      void this.drainQueue()
    }
  }

  private trimBufferedEvents() {
    while (this.bufferedEvents.length > MAX_BUFFERED_EVENTS) {
      let dropIndex = 0
      let lowestPriority = Number.POSITIVE_INFINITY
      for (const [index, event] of this.bufferedEvents.entries()) {
        const priority = getEventPriority(event)
        if (priority < lowestPriority) {
          lowestPriority = priority
          dropIndex = index
        }
      }
      this.bufferedEvents.splice(dropIndex, 1)
      this.droppedEventsCount += 1
    }
  }

  private trimQueuedBatches() {
    while (this.queuedBatches.length > MAX_QUEUED_BATCHES) {
      const droppedBatch = this.queuedBatches.pop()
      if (!droppedBatch) {
        return
      }
      this.droppedEventsCount += droppedBatch.events.length + droppedBatch.dropped_events_count
    }
  }

  private scheduleRetry() {
    if (!this.enabled || this.retryTimer !== null) {
      return
    }
    this.retryTimer = window.setTimeout(() => {
      this.retryTimer = null
      void this.drainQueue()
    }, RETRY_DELAY_MS)
  }

  private async drainQueue(options: { keepalive?: boolean } = {}) {
    if (this.inflight || this.queuedBatches.length === 0) {
      return
    }

    this.inflight = true
    const batch = this.queuedBatches[0]
    const outcome = await this.sendBatch(batch, { keepalive: Boolean(options.keepalive) })

    if (outcome === 'success' || outcome === 'drop') {
      this.queuedBatches.shift()
    }
    if (outcome === 'retry') {
      this.scheduleRetry()
    }

    this.inflight = false
    if (outcome === 'success' && this.queuedBatches.length > 0) {
      void this.drainQueue()
    }
  }

  private async sendBatch(
    batch: UiIncidentTelemetryEnvelope,
    options: { keepalive: boolean },
  ): Promise<SendOutcome> {
    const token = getAuthToken()
    const tenantId = batch.tenant_id ?? resolveTelemetryContext().tenantId

    if (!token || !tenantId) {
      return 'retry'
    }

    const locale = getCurrentAppLocale()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      'X-CC1C-Tenant-ID': tenantId,
    }
    if (locale) {
      headers[LOCALE_REQUEST_HEADER] = locale
    }

    try {
      const response = await fetch(INGEST_URL, {
        method: 'POST',
        headers,
        credentials: 'include',
        keepalive: options.keepalive,
        body: JSON.stringify({
          ...batch,
          tenant_id: tenantId,
        }),
      })

      if (response.ok) {
        return 'success'
      }
      if (response.status >= 500 || response.status === 429) {
        return 'retry'
      }
      return 'drop'
    } catch {
      return 'retry'
    }
  }
}

const uploader = new UiIncidentTelemetryUploader()

export const setUiIncidentTelemetryEnabled = (enabled: boolean) => {
  uploader.setEnabled(enabled)
}

export const __TESTING__ = {
  FLUSH_INTERVAL_MS,
  RETRY_DELAY_MS,
}
