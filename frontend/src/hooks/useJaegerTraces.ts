/**
 * React hook for loading and managing Jaeger traces.
 *
 * Provides state management for fetching traces from Jaeger
 * and converting them to our internal format.
 *
 * Usage:
 * ```tsx
 * const { trace, isLoading, error, fetchTrace, findSpan } = useJaegerTraces(traceId);
 * ```
 */

import { useState, useEffect, useCallback } from 'react'
import { getTraceById, type JaegerTrace } from '../api/endpoints/jaeger'
import {
  convertJaegerTrace,
  findSpanInTrace,
  type TraceData,
  type TraceSpan
} from '../types/tracing'

export interface UseJaegerTracesResult {
  // Trace data
  trace: TraceData | null
  rawTrace: JaegerTrace | null

  // Loading state
  isLoading: boolean
  error: string | null

  // Actions
  fetchTrace: (traceId: string) => Promise<void>
  refresh: () => Promise<void>
  findSpan: (spanId: string) => TraceSpan | null
  clear: () => void
}

/**
 * Hook for loading and managing Jaeger traces.
 *
 * @param initialTraceId - Optional trace ID to load on mount
 */
export const useJaegerTraces = (initialTraceId?: string | null): UseJaegerTracesResult => {
  // State
  const [trace, setTrace] = useState<TraceData | null>(null)
  const [rawTrace, setRawTrace] = useState<JaegerTrace | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [currentTraceId, setCurrentTraceId] = useState<string | null>(initialTraceId || null)

  /**
   * Fetch a trace from Jaeger.
   */
  const fetchTrace = useCallback(async (traceId: string): Promise<void> => {
    if (!traceId) {
      setError('Trace ID is required')
      return
    }

    setIsLoading(true)
    setError(null)
    setCurrentTraceId(traceId)

    try {
      const jaegerTrace = await getTraceById(traceId)

      if (!jaegerTrace) {
        setError(`Trace not found: ${traceId}`)
        setTrace(null)
        setRawTrace(null)
        return
      }

      setRawTrace(jaegerTrace)
      const convertedTrace = convertJaegerTrace(jaegerTrace)
      setTrace(convertedTrace)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load trace'
      setError(message)
      setTrace(null)
      setRawTrace(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  /**
   * Refresh the current trace.
   */
  const refresh = useCallback(async (): Promise<void> => {
    if (currentTraceId) {
      await fetchTrace(currentTraceId)
    }
  }, [currentTraceId, fetchTrace])

  /**
   * Find a span by ID in the current trace.
   */
  const findSpan = useCallback((spanId: string): TraceSpan | null => {
    if (!trace) return null
    return findSpanInTrace(trace, spanId)
  }, [trace])

  /**
   * Clear the trace data.
   */
  const clear = useCallback(() => {
    setTrace(null)
    setRawTrace(null)
    setError(null)
    setCurrentTraceId(null)
  }, [])

  // Load initial trace if provided
  useEffect(() => {
    if (initialTraceId && initialTraceId !== currentTraceId) {
      fetchTrace(initialTraceId)
    }
  }, [initialTraceId, currentTraceId, fetchTrace])

  return {
    trace,
    rawTrace,
    isLoading,
    error,
    fetchTrace,
    refresh,
    findSpan,
    clear
  }
}

export default useJaegerTraces
