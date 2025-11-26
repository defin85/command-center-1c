/**
 * Tracing Types for workflow execution monitoring.
 *
 * These types are used for displaying trace information in the UI,
 * abstracting away Jaeger-specific details.
 */

// ============================================================================
// Span Context Types
// ============================================================================

/**
 * Context for linking spans across services.
 */
export interface SpanContext {
  traceId: string
  spanId: string
  parentSpanId?: string
}

/**
 * Status of a trace span.
 */
export type SpanStatus = 'ok' | 'error' | 'unset'

/**
 * Represents a single span in a trace.
 */
export interface TraceSpan {
  spanId: string
  parentSpanId?: string
  operationName: string
  serviceName: string
  startTime: Date
  duration: number  // milliseconds
  status: SpanStatus
  tags: Record<string, string | number | boolean>
  logs: TraceEvent[]
  children: TraceSpan[]
}

/**
 * Log/event within a span.
 */
export interface TraceEvent {
  timestamp: Date
  name: string
  attributes: Record<string, string | number | boolean>
}

/**
 * Complete trace data structure.
 */
export interface TraceData {
  traceId: string
  rootSpan: TraceSpan | null
  spans: TraceSpan[]
  services: string[]
  startTime: Date
  duration: number  // milliseconds
  spanCount: number
  errorCount: number
}

// ============================================================================
// Timeline Types
// ============================================================================

/**
 * Timeline item for display in trace viewer.
 */
export interface TimelineItem {
  spanId: string
  operationName: string
  serviceName: string
  startOffset: number  // ms from trace start
  duration: number     // ms
  depth: number        // nesting level
  status: SpanStatus
  hasError: boolean
}

/**
 * Service summary in a trace.
 */
export interface ServiceSummary {
  serviceName: string
  spanCount: number
  totalDuration: number  // ms
  errorCount: number
  operations: string[]
}

// ============================================================================
// Conversion Utilities
// ============================================================================

import type { JaegerTrace, JaegerSpan } from '../api/endpoints/jaeger'

/**
 * Convert Jaeger span status from tags.
 */
const getSpanStatus = (span: JaegerSpan): SpanStatus => {
  const errorTag = span.tags.find(t => t.key === 'error')
  if (errorTag && errorTag.value === true) {
    return 'error'
  }

  const statusCodeTag = span.tags.find(t => t.key === 'otel.status_code')
  if (statusCodeTag) {
    if (statusCodeTag.value === 'ERROR') return 'error'
    if (statusCodeTag.value === 'OK') return 'ok'
  }

  const httpStatusTag = span.tags.find(t => t.key === 'http.status_code')
  if (httpStatusTag && typeof httpStatusTag.value === 'number') {
    if (httpStatusTag.value >= 400) return 'error'
    return 'ok'
  }

  return 'unset'
}

/**
 * Convert Jaeger trace to our TraceData format.
 */
export const convertJaegerTrace = (jaegerTrace: JaegerTrace): TraceData => {
  const spanMap = new Map<string, TraceSpan>()

  // First pass: create all spans
  for (const jSpan of jaegerTrace.spans) {
    const process = jaegerTrace.processes[jSpan.processID]

    const span: TraceSpan = {
      spanId: jSpan.spanID,
      parentSpanId: jSpan.parentSpanID ||
        jSpan.references.find(r => r.refType === 'CHILD_OF')?.spanID,
      operationName: jSpan.operationName,
      serviceName: process?.serviceName || 'unknown',
      startTime: new Date(jSpan.startTime / 1000),  // us to ms
      duration: jSpan.duration / 1000,  // us to ms
      status: getSpanStatus(jSpan),
      tags: Object.fromEntries(jSpan.tags.map(t => [t.key, t.value])),
      logs: jSpan.logs.map(log => ({
        timestamp: new Date(log.timestamp / 1000),
        name: log.fields.find(f => f.key === 'event')?.value as string || 'log',
        attributes: Object.fromEntries(log.fields.map(f => [f.key, f.value]))
      })),
      children: []
    }

    spanMap.set(jSpan.spanID, span)
  }

  // Second pass: build tree structure
  let rootSpan: TraceSpan | null = null
  const allSpans: TraceSpan[] = []

  for (const span of spanMap.values()) {
    allSpans.push(span)

    if (span.parentSpanId) {
      const parent = spanMap.get(span.parentSpanId)
      if (parent) {
        parent.children.push(span)
      }
    } else {
      rootSpan = span
    }
  }

  // Sort children by start time
  const sortChildren = (span: TraceSpan) => {
    span.children.sort((a, b) => a.startTime.getTime() - b.startTime.getTime())
    span.children.forEach(sortChildren)
  }
  if (rootSpan) {
    sortChildren(rootSpan)
  }

  // Get unique services
  const services = [...new Set(allSpans.map(s => s.serviceName))].sort()

  // Calculate trace duration (handle empty spans array)
  let traceStart = Date.now()
  let traceEnd = traceStart

  if (allSpans.length > 0) {
    const startTimes = allSpans.map(s => s.startTime.getTime())
    const endTimes = allSpans.map(s => s.startTime.getTime() + s.duration)
    traceStart = Math.min(...startTimes)
    traceEnd = Math.max(...endTimes)
  }

  // Count errors
  const errorCount = allSpans.filter(s => s.status === 'error').length

  return {
    traceId: jaegerTrace.traceID,
    rootSpan,
    spans: allSpans,
    services,
    startTime: new Date(traceStart),
    duration: allSpans.length > 0 ? traceEnd - traceStart : 0,
    spanCount: allSpans.length,
    errorCount
  }
}

/**
 * Convert trace spans to timeline items.
 */
export const getTimelineItems = (trace: TraceData): TimelineItem[] => {
  const items: TimelineItem[] = []
  const traceStart = trace.startTime.getTime()

  const addSpanToTimeline = (span: TraceSpan, depth: number) => {
    items.push({
      spanId: span.spanId,
      operationName: span.operationName,
      serviceName: span.serviceName,
      startOffset: span.startTime.getTime() - traceStart,
      duration: span.duration,
      depth,
      status: span.status,
      hasError: span.status === 'error'
    })

    for (const child of span.children) {
      addSpanToTimeline(child, depth + 1)
    }
  }

  if (trace.rootSpan) {
    addSpanToTimeline(trace.rootSpan, 0)
  }

  return items
}

/**
 * Get service summaries from trace.
 */
export const getServiceSummaries = (trace: TraceData): ServiceSummary[] => {
  const summaryMap = new Map<string, ServiceSummary>()

  for (const span of trace.spans) {
    let summary = summaryMap.get(span.serviceName)
    if (!summary) {
      summary = {
        serviceName: span.serviceName,
        spanCount: 0,
        totalDuration: 0,
        errorCount: 0,
        operations: []
      }
      summaryMap.set(span.serviceName, summary)
    }

    summary.spanCount++
    summary.totalDuration += span.duration
    if (span.status === 'error') {
      summary.errorCount++
    }
    if (!summary.operations.includes(span.operationName)) {
      summary.operations.push(span.operationName)
    }
  }

  return Array.from(summaryMap.values()).sort((a, b) =>
    a.serviceName.localeCompare(b.serviceName)
  )
}

/**
 * Find a span by ID in trace data.
 */
export const findSpanInTrace = (trace: TraceData, spanId: string): TraceSpan | null => {
  return trace.spans.find(s => s.spanId === spanId) || null
}

/**
 * Format duration for display.
 */
export const formatTraceDuration = (ms: number): string => {
  if (ms < 1) {
    return `${(ms * 1000).toFixed(0)}us`
  }
  if (ms < 1000) {
    return `${ms.toFixed(2)}ms`
  }
  return `${(ms / 1000).toFixed(2)}s`
}
