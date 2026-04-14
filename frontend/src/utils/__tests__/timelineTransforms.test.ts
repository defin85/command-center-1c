/**
 * Unit Tests for Timeline Transform Utilities
 *
 * Tests transformation functions for waterfall timeline visualization:
 * - Event label mapping and fallback
 * - Event status extraction
 * - Timeline events to waterfall items transformation
 * - Duration and timestamp formatting
 * - Total duration calculation
 */

import { describe, it, expect } from 'vitest'
import {
  getEventLabel,
  getEventStatus,
  transformToWaterfallItems,
  formatDuration,
  formatTimestamp,
  calculateTotalDuration,
  EVENT_LABELS,
} from '../timelineTransforms'
import type { TimelineEvent, WaterfallItem } from '../../types/operationTimeline'

describe('timelineTransforms', () => {
  describe('getEventLabel', () => {
    it('returns human-readable label for known orchestrator events', () => {
      expect(getEventLabel('orchestrator.created')).toBe('Operation Created')
      expect(getEventLabel('orchestrator.completed')).toBe('Operation Completed')
      expect(getEventLabel('orchestrator.failed')).toBe('Operation Failed')
    })

    it('returns human-readable label for known worker events', () => {
      expect(getEventLabel('worker.command.received')).toBe('Worker Received')
      expect(getEventLabel('worker.command.completed')).toBe('Worker Completed')
      expect(getEventLabel('worker.command.failed')).toBe('Worker Failed')
    })

    it('returns human-readable label for known RAS adapter events', () => {
      expect(getEventLabel('ras.command.received')).toBe('RAS Command Received')
      expect(getEventLabel('ras.command.completed')).toBe('RAS Command Completed')
      expect(getEventLabel('ras.command.failed')).toBe('RAS Command Failed')
    })

    it('returns human-readable label for known OData adapter events', () => {
      expect(getEventLabel('odata.command.received')).toBe('OData Request Received')
      expect(getEventLabel('odata.command.completed')).toBe('OData Request Completed')
      expect(getEventLabel('odata.command.failed')).toBe('OData Request Failed')
    })

    it('returns human-readable label for known Designer agent events', () => {
      expect(getEventLabel('designer.command.received')).toBe('Designer Command Received')
      expect(getEventLabel('designer.command.completed')).toBe('Designer Command Completed')
      expect(getEventLabel('designer.command.failed')).toBe('Designer Command Failed')
    })

    it('returns human-readable label for known Batch service events', () => {
      expect(getEventLabel('batch.command.received')).toBe('Batch Request Received')
      expect(getEventLabel('batch.command.completed')).toBe('Batch Completed')
      expect(getEventLabel('batch.command.failed')).toBe('Batch Failed')
    })

    it('returns human-readable label for known cluster.sync events', () => {
      expect(getEventLabel('cluster.sync.started')).toBe('Cluster Sync Started')
      expect(getEventLabel('cluster.sync.resolving.started')).toBe('Resolving Cluster UUID')
      expect(getEventLabel('cluster.sync.resolving.finished')).toBe('Cluster UUID Resolved')
      expect(getEventLabel('cluster.sync.fetching.started')).toBe('Fetching Infobases')
      expect(getEventLabel('cluster.sync.fetching.finished')).toBe('Infobases Fetched')
      expect(getEventLabel('cluster.sync.publish_result.started')).toBe('Publishing Sync Result')
      expect(getEventLabel('cluster.sync.publish_result.finished')).toBe('Sync Result Published')
      expect(getEventLabel('cluster.sync.publish_result.failed')).toBe('Sync Result Publish Failed')
      expect(getEventLabel('cluster.sync.completed')).toBe('Cluster Sync Completed')
      expect(getEventLabel('cluster.sync.failed')).toBe('Cluster Sync Failed')
    })

    it('falls back to Title Case conversion for unknown events', () => {
      expect(getEventLabel('custom.event.triggered')).toBe('Custom Event Triggered')
      expect(getEventLabel('database.query.executed')).toBe('Database Query Executed')
      expect(getEventLabel('singleword')).toBe('Singleword')
    })

    it('handles empty string', () => {
      expect(getEventLabel('')).toBe('')
    })

    it('handles event names with multiple dots', () => {
      expect(getEventLabel('a.b.c.d.e')).toBe('A B C D E')
    })

    it('preserves all EVENT_LABELS mapping keys', () => {
      Object.keys(EVENT_LABELS).forEach((event) => {
        expect(getEventLabel(event)).toBe(EVENT_LABELS[event])
      })
    })
  })

  describe('getEventStatus', () => {
    it('returns "received" for events ending with .received', () => {
      expect(getEventStatus('worker.command.received')).toBe('received')
      expect(getEventStatus('ras.command.received')).toBe('received')
      expect(getEventStatus('odata.command.received')).toBe('received')
    })

    it('returns "received" for events ending with .created', () => {
      expect(getEventStatus('orchestrator.created')).toBe('received')
      expect(getEventStatus('database.created')).toBe('received')
    })

    it('returns "completed" for events ending with .completed', () => {
      expect(getEventStatus('worker.command.completed')).toBe('completed')
      expect(getEventStatus('ras.command.completed')).toBe('completed')
      expect(getEventStatus('orchestrator.completed')).toBe('completed')
    })

    it('returns "completed" for events ending with .finished', () => {
      expect(getEventStatus('cluster.sync.fetching.finished')).toBe('completed')
      expect(getEventStatus('cluster.sync.resolving.finished')).toBe('completed')
      expect(getEventStatus('cluster.sync.publish_result.finished')).toBe('completed')
    })

    it('returns "failed" for events ending with .failed', () => {
      expect(getEventStatus('worker.command.failed')).toBe('failed')
      expect(getEventStatus('ras.command.failed')).toBe('failed')
      expect(getEventStatus('orchestrator.failed')).toBe('failed')
    })

    it('returns "processing" for events ending with .started', () => {
      expect(getEventStatus('operation.started')).toBe('processing')
      expect(getEventStatus('cluster.sync.started')).toBe('processing')
      expect(getEventStatus('saga.started')).toBe('processing')
      expect(getEventStatus('database.query.started')).toBe('processing')
    })

    it('returns "processing" for events ending with .processing', () => {
      expect(getEventStatus('database.processing')).toBe('processing')
      expect(getEventStatus('worker.processing')).toBe('processing')
    })

    it('returns "processing" for transition/step events', () => {
      expect(getEventStatus('saga.transition')).toBe('processing')
      expect(getEventStatus('saga.compensation.step')).toBe('processing')
    })

    it('returns "completed" for rehydrated events', () => {
      expect(getEventStatus('designer.credentials.rehydrated')).toBe('completed')
      expect(getEventStatus('clusterinfo.rehydrated')).toBe('completed')
    })

    it('returns "unknown" for events with unrecognized endings', () => {
      expect(getEventStatus('custom.event')).toBe('unknown')
      expect(getEventStatus('database.query.pending')).toBe('unknown')
      expect(getEventStatus('worker.waiting')).toBe('unknown')
    })

    it('handles empty string', () => {
      expect(getEventStatus('')).toBe('unknown')
    })

    it('handles events without dots', () => {
      // Events without dots: endsWith still works for exact suffix match
      expect(getEventStatus('received')).toBe('unknown')    // no dot prefix
      expect(getEventStatus('completed')).toBe('unknown')   // no dot prefix
      expect(getEventStatus('failed')).toBe('unknown')      // no dot prefix
      expect(getEventStatus('started')).toBe('unknown')     // no dot prefix
      expect(getEventStatus('processing')).toBe('unknown')  // no dot prefix
    })
  })

  describe('transformToWaterfallItems', () => {
    it('returns empty array for empty input', () => {
      expect(transformToWaterfallItems([])).toEqual([])
    })

    it('transforms single event correctly', () => {
      const events: TimelineEvent[] = [
        {
          timestamp: 1000,
          event: 'orchestrator.created',
          service: 'orchestrator',
          metadata: { user_id: '123' },
        },
      ]

      const result = transformToWaterfallItems(events)

      expect(result).toHaveLength(1)
      expect(result[0]).toMatchObject({
        event: 'orchestrator.created',
        eventLabel: 'Operation Created',
        service: 'orchestrator',
        startOffset: 0,
        duration: 0,
        metadata: { user_id: '123' },
      })
      expect(result[0].id).toBe('1000-0')
      expect(result[0].timestamp).toEqual(new Date(1000))
    })

    it('calculates duration as difference between events', () => {
      const events: TimelineEvent[] = [
        {
          timestamp: 1000,
          event: 'orchestrator.created',
          service: 'orchestrator',
          metadata: {},
        },
        {
          timestamp: 1500,
          event: 'worker.command.received',
          service: 'worker',
          metadata: {},
        },
        {
          timestamp: 2000,
          event: 'worker.command.completed',
          service: 'worker',
          metadata: {},
        },
      ]

      const result = transformToWaterfallItems(events)

      expect(result).toHaveLength(3)
      expect(result[0].duration).toBe(500) // 1500 - 1000
      expect(result[1].duration).toBe(500) // 2000 - 1500
      expect(result[2].duration).toBe(0)   // Last event has no next
    })

    it('calculates startOffset relative to first event', () => {
      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'event1', service: 's1', metadata: {} },
        { timestamp: 1500, event: 'event2', service: 's2', metadata: {} },
        { timestamp: 2500, event: 'event3', service: 's3', metadata: {} },
      ]

      const result = transformToWaterfallItems(events)

      expect(result[0].startOffset).toBe(0)    // 1000 - 1000
      expect(result[1].startOffset).toBe(500)  // 1500 - 1000
      expect(result[2].startOffset).toBe(1500) // 2500 - 1000
    })

    it('generates unique IDs for each item', () => {
      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'event1', service: 's1', metadata: {} },
        { timestamp: 1000, event: 'event2', service: 's2', metadata: {} }, // Same timestamp
        { timestamp: 2000, event: 'event3', service: 's3', metadata: {} },
      ]

      const result = transformToWaterfallItems(events)

      expect(result[0].id).toBe('1000-0')
      expect(result[1].id).toBe('1000-1')
      expect(result[2].id).toBe('2000-2')

      const ids = result.map((item) => item.id)
      const uniqueIds = new Set(ids)
      expect(uniqueIds.size).toBe(ids.length)
    })

    it('preserves all metadata', () => {
      const metadata = {
        user_id: '123',
        database: 'test_db',
        nested: { key: 'value' },
      }

      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'event1', service: 's1', metadata },
      ]

      const result = transformToWaterfallItems(events)

      expect(result[0].metadata).toEqual(metadata)
    })

    it('transforms complete operation flow', () => {
      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'orchestrator.created', service: 'orchestrator', metadata: {} },
        { timestamp: 1100, event: 'worker.command.received', service: 'worker', metadata: {} },
        { timestamp: 1200, event: 'ras.command.received', service: 'worker', metadata: {} },
        { timestamp: 1800, event: 'ras.command.completed', service: 'worker', metadata: {} },
        { timestamp: 1900, event: 'worker.command.completed', service: 'worker', metadata: {} },
        { timestamp: 2000, event: 'orchestrator.completed', service: 'orchestrator', metadata: {} },
      ]

      const result = transformToWaterfallItems(events)

      expect(result).toHaveLength(6)
      expect(result.map((item) => item.event)).toEqual([
        'orchestrator.created',
        'worker.command.received',
        'ras.command.received',
        'ras.command.completed',
        'worker.command.completed',
        'orchestrator.completed',
      ])
    })
  })

  describe('formatDuration', () => {
    it('formats negative values as 0ms', () => {
      expect(formatDuration(-100)).toBe('0ms')
      expect(formatDuration(-1)).toBe('0ms')
    })

    it('formats milliseconds (< 1000ms)', () => {
      expect(formatDuration(0)).toBe('0ms')
      expect(formatDuration(1)).toBe('1ms')
      expect(formatDuration(123)).toBe('123ms')
      expect(formatDuration(999)).toBe('999ms')
    })

    it('formats seconds (>= 1000ms, < 60000ms)', () => {
      expect(formatDuration(1000)).toBe('1.0s')
      expect(formatDuration(1500)).toBe('1.5s')
      expect(formatDuration(5234)).toBe('5.2s')
      expect(formatDuration(59999)).toBe('60.0s')
    })

    it('formats minutes (>= 60000ms)', () => {
      expect(formatDuration(60000)).toBe('1.0m')
      expect(formatDuration(90000)).toBe('1.5m')
      expect(formatDuration(120000)).toBe('2.0m')
      expect(formatDuration(185000)).toBe('3.1m')
    })

    it('rounds milliseconds to whole numbers', () => {
      expect(formatDuration(123.4)).toBe('123ms')
      expect(formatDuration(123.9)).toBe('124ms')
    })

    it('rounds seconds to 1 decimal place', () => {
      expect(formatDuration(1234)).toBe('1.2s')
      expect(formatDuration(1267)).toBe('1.3s')
    })

    it('rounds minutes to 1 decimal place', () => {
      expect(formatDuration(123456)).toBe('2.1m')
      expect(formatDuration(185000)).toBe('3.1m')
    })
  })

  describe('formatTimestamp', () => {
    it('formats date with HH:MM:SS.mmm format', () => {
      const date = new Date('2025-12-13T10:30:45.123Z')
      const result = formatTimestamp(date)

      // Result depends on locale, but should include hours, minutes, seconds, milliseconds
      expect(result).toMatch(/\d{2}:\d{2}:\d{2}/)
      expect(result).toMatch(/[.,]\d{3}(?:\s?[AP]M)?$/i)
    })

    it('handles midnight correctly', () => {
      const date = new Date('2025-12-13T00:00:00.000Z')
      const result = formatTimestamp(date)

      expect(result).toMatch(/\d{2}:\d{2}:\d{2}/)
    })

    it('formats milliseconds with 3 digits', () => {
      const date1 = new Date('2025-12-13T10:30:45.001Z')
      const date2 = new Date('2025-12-13T10:30:45.999Z')

      const result1 = formatTimestamp(date1)
      const result2 = formatTimestamp(date2)

      // Both should have 3-digit milliseconds regardless of locale decimal separator or AM/PM suffix
      expect(result1).toMatch(/\d{2}:\d{2}:\d{2}[.,]\d{3}(?:\s?[AP]M)?/i)
      expect(result2).toMatch(/\d{2}:\d{2}:\d{2}[.,]\d{3}(?:\s?[AP]M)?/i)
    })

    it('returns consistent format for same time', () => {
      const date1 = new Date('2025-12-13T14:20:30.500Z')
      const date2 = new Date('2025-12-13T14:20:30.500Z')

      expect(formatTimestamp(date1)).toBe(formatTimestamp(date2))
    })
  })

  describe('calculateTotalDuration', () => {
    it('returns 0 for empty array', () => {
      expect(calculateTotalDuration([])).toBe(0)
    })

    it('calculates total as last item offset + duration', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'e1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '2',
          event: 'e2',
          eventLabel: 'Event 2',
          service: 's2',
          startOffset: 100,
          duration: 200,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '3',
          event: 'e3',
          eventLabel: 'Event 3',
          service: 's3',
          startOffset: 300,
          duration: 50,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      // Last item: startOffset=300 + duration=50 = 350
      expect(calculateTotalDuration(items)).toBe(350)
    })

    it('handles single item', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'e1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 500,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      expect(calculateTotalDuration(items)).toBe(500)
    })

    it('handles zero duration for last item', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'e1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '2',
          event: 'e2',
          eventLabel: 'Event 2',
          service: 's2',
          startOffset: 100,
          duration: 0,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      expect(calculateTotalDuration(items)).toBe(100)
    })

    it('handles all items with zero offset and duration', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'e1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 0,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      expect(calculateTotalDuration(items)).toBe(0)
    })
  })

  describe('Edge cases and integration', () => {
    it('handles events with identical timestamps', () => {
      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'event1', service: 's1', metadata: {} },
        { timestamp: 1000, event: 'event2', service: 's2', metadata: {} },
        { timestamp: 1000, event: 'event3', service: 's3', metadata: {} },
      ]

      const items = transformToWaterfallItems(events)

      expect(items).toHaveLength(3)
      expect(items[0].startOffset).toBe(0)
      expect(items[1].startOffset).toBe(0)
      expect(items[2].startOffset).toBe(0)
      expect(items[0].duration).toBe(0)
      expect(items[1].duration).toBe(0)
    })

    it('transforms and calculates complete workflow', () => {
      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'orchestrator.created', service: 'orchestrator', metadata: {} },
        { timestamp: 1250, event: 'worker.command.received', service: 'worker', metadata: {} },
        { timestamp: 2000, event: 'worker.command.completed', service: 'worker', metadata: {} },
        { timestamp: 2100, event: 'orchestrator.completed', service: 'orchestrator', metadata: {} },
      ]

      const items = transformToWaterfallItems(events)
      const total = calculateTotalDuration(items)

      expect(items).toHaveLength(4)
      expect(total).toBe(1100) // 2100 - 1000
      expect(formatDuration(total)).toBe('1.1s')
    })

    it('preserves event status through transformation', () => {
      const events: TimelineEvent[] = [
        { timestamp: 1000, event: 'orchestrator.created', service: 'orchestrator', metadata: {} },
        { timestamp: 2000, event: 'orchestrator.completed', service: 'orchestrator', metadata: {} },
        { timestamp: 3000, event: 'orchestrator.failed', service: 'orchestrator', metadata: {} },
      ]

      const items = transformToWaterfallItems(events)

      expect(getEventStatus(items[0].event)).toBe('received')
      expect(getEventStatus(items[1].event)).toBe('completed')
      expect(getEventStatus(items[2].event)).toBe('failed')
    })
  })
})
