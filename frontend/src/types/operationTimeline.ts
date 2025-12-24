/**
 * Operation Timeline Types - Types for waterfall timeline visualization.
 *
 * Used by OperationTimelineDrawer and WaterfallTimeline components
 * to display operation execution flow across services.
 *
 * API Endpoint: GET /api/v2/internal/operations/{operation_id}/timeline
 *
 * @module types/operationTimeline
 */

/**
 * Timeline event from API response
 */
export interface TimelineEvent {
  timestamp: number
  event: string
  service: string
  trace_id?: string | null
  workflow_execution_id?: string | null
  node_id?: string | null
  metadata: Record<string, unknown>
}

/**
 * API response for operation timeline
 */
export interface OperationTimelineResponse {
  operation_id: string
  timeline: TimelineEvent[]
  total_events: number
  duration_ms: number | null
}

/**
 * Transformed timeline item for waterfall visualization
 */
export interface WaterfallItem {
  id: string
  event: string
  eventLabel: string
  service: string
  startOffset: number  // ms from timeline start
  duration: number     // ms to next event
  timestamp: Date
  metadata: Record<string, unknown>
}

/**
 * Event status derived from event name
 *
 * - received: Initial event (e.g., .received, .created)
 * - processing: In-progress event (e.g., .started, .processing)
 * - completed: Successfully finished (e.g., .completed)
 * - failed: Error occurred (e.g., .failed)
 * - unknown: Unrecognized event suffix
 */
export type EventStatus = 'received' | 'processing' | 'completed' | 'failed' | 'unknown'
