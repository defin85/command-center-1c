/**
 * Jaeger API client for trace visualization.
 *
 * Provides methods to fetch and parse Jaeger traces for workflow execution monitoring.
 */

// Jaeger через API Gateway proxy (contract-driven)
import { getCommandCenter1CAPIGateway } from '../generated-gateway'

const JAEGER_URL = import.meta.env.VITE_JAEGER_URL || 'http://localhost:16686'
const apiGateway = getCommandCenter1CAPIGateway()

// ============================================================================
// Jaeger API Types
// ============================================================================

export interface JaegerReference {
  refType: 'CHILD_OF' | 'FOLLOWS_FROM'
  traceID: string
  spanID: string
}

export interface JaegerTag {
  key: string
  type: string
  value: string | number | boolean
}

export interface JaegerLog {
  timestamp: number
  fields: JaegerTag[]
}

export interface JaegerSpan {
  traceID: string
  spanID: string
  parentSpanID?: string
  operationName: string
  references: JaegerReference[]
  startTime: number  // microseconds
  duration: number   // microseconds
  tags: JaegerTag[]
  logs: JaegerLog[]
  processID: string
  warnings: string[] | null
}

export interface JaegerProcess {
  serviceName: string
  tags: JaegerTag[]
}

export interface JaegerTrace {
  traceID: string
  spans: JaegerSpan[]
  processes: Record<string, JaegerProcess>
  warnings: string[] | null
}

export interface JaegerResponse {
  data: JaegerTrace[]
  total: number
  limit: number
  offset: number
  errors: string[] | null
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get a trace by its ID from Jaeger.
 * Includes timeout to prevent hanging when Jaeger is unavailable.
 */
export const getTraceById = async (traceId: string, timeoutMs: number = 10000): Promise<JaegerTrace | null> => {
  // Standard Jaeger API: GET /tracing/traces/{traceId}
  try {
    const response = await apiGateway.getTracingGetTrace(traceId, { timeout: timeoutMs })

    if (response?.data && response.data.length > 0) {
      return response.data[0] as unknown as JaegerTrace
    }

    return null
  } catch (error: any) {
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error(`Jaeger request timed out after ${timeoutMs}ms`)
      throw new Error(`Jaeger request timed out after ${timeoutMs}ms`)
    }
    if (error.response?.status === 404) {
      return null
    }
    console.error('Failed to fetch trace from Jaeger:', error)
    throw error
  }
}

/**
 * Find a span by ID within a trace.
 */
export const findSpanById = (trace: JaegerTrace, spanId: string): JaegerSpan | null => {
  return trace.spans.find(span => span.spanID === spanId) || null
}

/**
 * Get child spans of a parent span.
 */
export const getChildSpans = (trace: JaegerTrace, parentSpanId: string): JaegerSpan[] => {
  return trace.spans.filter(span =>
    span.references.some(ref =>
      ref.refType === 'CHILD_OF' && ref.spanID === parentSpanId
    ) || span.parentSpanID === parentSpanId
  )
}

/**
 * Get the root span of a trace (span without parent).
 */
export const getRootSpan = (trace: JaegerTrace): JaegerSpan | null => {
  return trace.spans.find(span =>
    !span.parentSpanID &&
    span.references.filter(ref => ref.refType === 'CHILD_OF').length === 0
  ) || null
}

/**
 * Get spans sorted by start time.
 */
export const getSpansSortedByTime = (trace: JaegerTrace): JaegerSpan[] => {
  return [...trace.spans].sort((a, b) => a.startTime - b.startTime)
}

/**
 * Get the URL to view a trace in Jaeger UI.
 */
export const getJaegerTraceUrl = (traceId: string): string => {
  return `${JAEGER_URL}/trace/${traceId}`
}

/**
 * Get the URL to view a specific span in Jaeger UI.
 */
export const getJaegerSpanUrl = (traceId: string, spanId: string): string => {
  return `${JAEGER_URL}/trace/${traceId}?uiFind=${spanId}`
}

/**
 * Get tag value from a span by key.
 */
export const getSpanTag = (span: JaegerSpan, key: string): string | number | boolean | undefined => {
  const tag = span.tags.find(t => t.key === key)
  return tag?.value
}

/**
 * Get process/service name for a span.
 */
export const getSpanServiceName = (trace: JaegerTrace, span: JaegerSpan): string => {
  const process = trace.processes[span.processID]
  return process?.serviceName || 'unknown'
}

/**
 * Format duration from microseconds to human-readable string.
 */
export const formatDuration = (microseconds: number): string => {
  if (microseconds < 1000) {
    return `${microseconds}us`
  }
  if (microseconds < 1000000) {
    return `${(microseconds / 1000).toFixed(2)}ms`
  }
  return `${(microseconds / 1000000).toFixed(2)}s`
}

/**
 * Calculate relative timestamp within a trace.
 */
export const getRelativeTime = (trace: JaegerTrace, span: JaegerSpan): number => {
  const rootSpan = getRootSpan(trace)
  if (!rootSpan) return 0
  return span.startTime - rootSpan.startTime
}

/**
 * Get unique services from a trace.
 */
export const getTraceServices = (trace: JaegerTrace): string[] => {
  const services = new Set<string>()
  for (const processId in trace.processes) {
    services.add(trace.processes[processId].serviceName)
  }
  return Array.from(services).sort()
}

/**
 * Search traces by service and operation.
 * Includes timeout to prevent hanging when Jaeger is unavailable.
 */
export const searchTraces = async (
  service: string,
  operation?: string,
  limit: number = 20,
  lookback: string = '1h',
  timeoutMs: number = 15000
): Promise<JaegerTrace[]> => {
  // Standard Jaeger API: GET /tracing/traces?service=...
  try {
    const response = await apiGateway.getTracingGetTraces(
      {
        service,
        limit,
        lookback,
        operation,
      },
      { timeout: timeoutMs }
    )

    return (response?.data || []) as unknown as JaegerTrace[]
  } catch (error: any) {
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      console.error(`Jaeger search timed out after ${timeoutMs}ms`)
      throw new Error(`Jaeger search timed out after ${timeoutMs}ms`)
    }
    console.error('Failed to search traces in Jaeger:', error)
    throw error
  }
}

export default {
  getTraceById,
  findSpanById,
  getChildSpans,
  getRootSpan,
  getSpansSortedByTime,
  getJaegerTraceUrl,
  getJaegerSpanUrl,
  getSpanTag,
  getSpanServiceName,
  formatDuration,
  getRelativeTime,
  getTraceServices,
  searchTraces
}
