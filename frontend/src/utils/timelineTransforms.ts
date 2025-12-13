/**
 * Timeline Transform Utilities
 *
 * Functions for transforming API timeline events into
 * waterfall visualization data.
 *
 * @module utils/timelineTransforms
 */

import type { TimelineEvent, WaterfallItem, EventStatus } from '../types/operationTimeline'

/**
 * Duration constants (milliseconds)
 */
const MS_IN_SECOND = 1000
const MS_IN_MINUTE = 60000

/**
 * Human-readable labels for timeline events
 */
export const EVENT_LABELS: Record<string, string> = {
  // Orchestrator events
  'orchestrator.created': 'Operation Created',
  'orchestrator.completed': 'Operation Completed',
  'orchestrator.failed': 'Operation Failed',

  // Worker events
  'worker.command.received': 'Worker Received',
  'worker.command.completed': 'Worker Completed',
  'worker.command.failed': 'Worker Failed',

  // RAS Adapter events
  'ras.command.received': 'RAS Command Received',
  'ras.command.completed': 'RAS Command Completed',
  'ras.command.failed': 'RAS Command Failed',

  // OData Adapter events
  'odata.command.received': 'OData Request Received',
  'odata.command.completed': 'OData Request Completed',
  'odata.command.failed': 'OData Request Failed',

  // Designer Agent events
  'designer.command.received': 'Designer Command Received',
  'designer.command.completed': 'Designer Command Completed',
  'designer.command.failed': 'Designer Command Failed',

  // Batch Service events
  'batch.command.received': 'Batch Request Received',
  'batch.command.completed': 'Batch Completed',
  'batch.command.failed': 'Batch Failed',
}

/**
 * Get human-readable label for an event
 */
export function getEventLabel(event: string): string {
  if (EVENT_LABELS[event]) {
    return EVENT_LABELS[event]
  }

  // Fallback: convert dot notation to Title Case
  return event
    .split('.')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/**
 * Extract event status from event name
 */
export function getEventStatus(event: string): EventStatus {
  if (event.endsWith('.received') || event.endsWith('.created')) {
    return 'received'
  }
  if (event.endsWith('.completed')) {
    return 'completed'
  }
  if (event.endsWith('.failed')) {
    return 'failed'
  }
  return 'unknown'
}

/**
 * Transform API timeline events into waterfall items
 */
export function transformToWaterfallItems(events: TimelineEvent[]): WaterfallItem[] {
  if (events.length === 0) {
    return []
  }

  const startTime = events[0].timestamp

  return events.map((event, index) => {
    const nextEvent = events[index + 1]
    const duration = nextEvent ? nextEvent.timestamp - event.timestamp : 0

    return {
      id: `${event.timestamp}-${index}`,
      event: event.event,
      eventLabel: getEventLabel(event.event),
      service: event.service,
      startOffset: event.timestamp - startTime,
      duration,
      timestamp: new Date(event.timestamp),
      metadata: event.metadata,
    }
  })
}

/**
 * Format duration in milliseconds to human-readable string
 */
export function formatDuration(ms: number): string {
  if (ms < 0) {
    return '0ms'
  }
  if (ms < MS_IN_SECOND) {
    return `${Math.round(ms)}ms`
  }
  if (ms < MS_IN_MINUTE) {
    return `${(ms / MS_IN_SECOND).toFixed(1)}s`
  }
  return `${(ms / MS_IN_MINUTE).toFixed(1)}m`
}

/**
 * Format timestamp to time string (HH:MM:SS.mmm)
 */
export function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  } as Intl.DateTimeFormatOptions)
}

/**
 * Calculate total duration from waterfall items
 */
export function calculateTotalDuration(items: WaterfallItem[]): number {
  if (items.length === 0) {
    return 0
  }

  const lastItem = items[items.length - 1]
  return lastItem.startOffset + lastItem.duration
}
