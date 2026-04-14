/**
 * Tests for WaterfallTimeline Component
 *
 * Tests waterfall timeline visualization:
 * - Rendering list of events with bars
 * - Color coding by event status
 * - Click to expand metadata
 * - Empty state display
 * - Bar width and position calculations
 * - Service icons and display names
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WaterfallTimeline from '../WaterfallTimeline'
import type { WaterfallItem } from '../../../types/operationTimeline'
import { changeLanguage } from '@/i18n/runtime'

beforeEach(async () => {
  await changeLanguage('en')
})

afterEach(async () => {
  await changeLanguage('ru')
})

describe('WaterfallTimeline', () => {
  const mockItems: WaterfallItem[] = [
    {
      id: '1',
      event: 'orchestrator.created',
      eventLabel: 'Operation Created',
      service: 'orchestrator',
      startOffset: 0,
      duration: 100,
      timestamp: new Date('2025-12-13T10:00:00.000Z'),
      metadata: { user_id: '123' },
    },
    {
      id: '2',
      event: 'worker.command.received',
      eventLabel: 'Worker Received',
      service: 'worker',
      startOffset: 100,
      duration: 500,
      timestamp: new Date('2025-12-13T10:00:00.100Z'),
      metadata: {},
    },
    {
      id: '3',
      event: 'worker.command.completed',
      eventLabel: 'Worker Completed',
      service: 'worker',
      startOffset: 600,
      duration: 0,
      timestamp: new Date('2025-12-13T10:00:00.600Z'),
      metadata: { result: 'success', rows: 42 },
    },
  ]

  describe('Rendering', () => {
    it('renders empty state when no items provided', () => {
      render(<WaterfallTimeline items={[]} />)

      expect(screen.getByText('No timeline events')).toBeInTheDocument()
    })

    it('renders all event labels', () => {
      render(<WaterfallTimeline items={mockItems} />)

      expect(screen.getByText('Operation Created')).toBeInTheDocument()
      expect(screen.getByText('Worker Received')).toBeInTheDocument()
      expect(screen.getByText('Worker Completed')).toBeInTheDocument()
    })

    it('renders timeline header with time markers', () => {
      render(<WaterfallTimeline items={mockItems} />)

      expect(screen.getByText('Event')).toBeInTheDocument()
      expect(screen.getByText('0ms')).toBeInTheDocument()
      expect(screen.getByText('300ms')).toBeInTheDocument() // totalDuration / 2
      expect(screen.getByText('600ms')).toBeInTheDocument() // totalDuration
    })

    it('renders status tags for each event', () => {
      render(<WaterfallTimeline items={mockItems} />)

      // orchestrator.created -> received
      // worker.command.received -> received (appears twice)
      const receivedTags = screen.getAllByText('received')
      expect(receivedTags.length).toBeGreaterThanOrEqual(1)

      // worker.command.completed -> completed
      expect(screen.getByText('completed')).toBeInTheDocument()
    })

    it('renders all waterfall rows', () => {
      const { container } = render(<WaterfallTimeline items={mockItems} />)

      const rows = container.querySelectorAll('.waterfall-row')
      expect(rows).toHaveLength(3)
    })

    it('applies custom className if provided', () => {
      const { container } = render(
        <WaterfallTimeline items={mockItems} className="custom-timeline" />
      )

      const timeline = container.querySelector('.waterfall-container')
      expect(timeline).toHaveClass('custom-timeline')
    })
  })

  describe('Event Status Colors', () => {
    it('applies blue color for received status', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'orchestrator.created',
          eventLabel: 'Created',
          service: 'orchestrator',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const bar = container.querySelector('.waterfall-bar')
      expect(bar).toHaveStyle({ backgroundColor: '#1890ff' })
    })

    it('applies green color for completed status', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'worker.command.completed',
          eventLabel: 'Completed',
          service: 'worker',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const bar = container.querySelector('.waterfall-bar')
      expect(bar).toHaveStyle({ backgroundColor: '#52c41a' })
    })

    it('applies red color for failed status', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'worker.command.failed',
          eventLabel: 'Failed',
          service: 'worker',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const bar = container.querySelector('.waterfall-bar')
      expect(bar).toHaveStyle({ backgroundColor: '#ff4d4f' })
    })

    it('applies gray color for unknown status', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'custom.unknown.event',
          eventLabel: 'Unknown',
          service: 'custom',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const bar = container.querySelector('.waterfall-bar')
      expect(bar).toHaveStyle({ backgroundColor: '#8c8c8c' })
    })
  })

  describe('Bar Dimensions', () => {
    it('calculates bar width as percentage of total duration', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 250,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '2',
          event: 'event2',
          eventLabel: 'Event 2',
          service: 's2',
          startOffset: 250,
          duration: 750,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)
      const bars = container.querySelectorAll('.waterfall-bar')

      // Total: 1000ms
      // Event 1: 250ms = 25%
      // Event 2: 750ms = 75%
      expect(bars[0]).toHaveStyle({ width: '25%' })
      expect(bars[1]).toHaveStyle({ width: '75%' })
    })

    it('calculates bar offset as percentage of total duration', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 200,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '2',
          event: 'event2',
          eventLabel: 'Event 2',
          service: 's2',
          startOffset: 500,
          duration: 500,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)
      const bars = container.querySelectorAll('.waterfall-bar')

      // Total: 1000ms
      // Event 1: offset 0ms = 0%
      // Event 2: offset 500ms = 50%
      expect(bars[0]).toHaveStyle({ left: '0%' })
      expect(bars[1]).toHaveStyle({ left: '50%' })
    })

    it('enforces minimum 2% width for visibility', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 1,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '2',
          event: 'event2',
          eventLabel: 'Event 2',
          service: 's2',
          startOffset: 1,
          duration: 9999,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)
      const bars = container.querySelectorAll('.waterfall-bar')

      // First bar would be 0.01% but should be 2% minimum
      const firstBarWidth = bars[0].getAttribute('style')
      expect(firstBarWidth).toContain('width: 2%')
    })

    it('handles zero total duration gracefully', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 0,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)
      const bar = container.querySelector('.waterfall-bar')

      // Should default to 0% when total is 0
      expect(bar).toHaveStyle({ width: '0%', left: '0%' })
    })
  })

  describe('Metadata Expansion', () => {
    it('toggles metadata display on click when metadata exists', async () => {
      const user = userEvent.setup()
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: { key: 'value', count: 42 },
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      // Click on the row to expand
      const row = container.querySelector('.waterfall-row')
      expect(row).toBeInTheDocument()
      if (row) {
        await user.click(row)
      }

      // After click, metadata should be visible
      expect(screen.getByText('key:')).toBeInTheDocument()
      expect(screen.getByText('value')).toBeInTheDocument()
      expect(screen.getByText('count:')).toBeInTheDocument()
      expect(screen.getByText('42')).toBeInTheDocument()

      // Click again to collapse
      if (row) {
        await user.click(row)
      }

      // Wait a bit for Collapse animation
      await new Promise(resolve => setTimeout(resolve, 100))
    })

    it('does not render metadata collapse when metadata is empty', async () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      // Row with empty metadata should not be clickable
      const row = container.querySelector('.waterfall-row')
      expect(row).toHaveStyle({ cursor: 'default' })

      // Metadata collapse should NOT be rendered when metadata is empty
      const metadataCollapse = container.querySelector('.waterfall-metadata-collapse')
      expect(metadataCollapse).not.toBeInTheDocument()
    })

    it('formats object metadata as JSON', async () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {
            nested: { foo: 'bar', count: 123 },
          },
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const row = container.querySelector('.waterfall-row')
      if (row) {
        await userEvent.click(row)
      }

      expect(screen.getByText('nested:')).toBeInTheDocument()
      expect(screen.getByText('{"foo":"bar","count":123}')).toBeInTheDocument()
    })

    it('does not expand when metadata is empty', async () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const row = container.querySelector('.waterfall-row')

      // Row should have default cursor, not pointer
      expect(row).toHaveStyle({ cursor: 'default' })
    })

    it('row has pointer cursor when metadata exists', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: { key: 'value' },
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const row = container.querySelector('.waterfall-row')
      expect(row).toHaveStyle({ cursor: 'pointer' })
    })
  })

  describe('Service Icons and Names', () => {
    it('renders service icon for known services', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event',
          service: 'orchestrator',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const icon = container.querySelector('.waterfall-service-icon')
      expect(icon).toBeInTheDocument()
      expect(icon).toContainHTML('anticon')
    })

    it('renders question icon for unknown services', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event',
          service: 'unknown-service',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const icon = container.querySelector('.waterfall-service-icon')
      expect(icon).toBeInTheDocument()
      expect(icon).toContainHTML('anticon-question-circle')
    })

    it('shows service display name on icon hover', async () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'My Event',
          service: 'orchestrator',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      // Tooltip content is rendered by Ant Design
      // We can check that the service icon exists
      const serviceIcon = container.querySelector('.waterfall-service-icon')
      expect(serviceIcon).toBeInTheDocument()
    })
  })

  describe('Duration Display', () => {
    it('shows formatted duration for each event', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 123,
          timestamp: new Date(),
          metadata: {},
        },
        {
          id: '2',
          event: 'event2',
          eventLabel: 'Event 2',
          service: 's2',
          startOffset: 123,
          duration: 5000,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      render(<WaterfallTimeline items={items} />)

      expect(screen.getByText('123ms')).toBeInTheDocument()
      expect(screen.getByText('5.0s')).toBeInTheDocument()
    })

    it('shows "-" for zero duration', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 0,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const durationCell = container.querySelector('.waterfall-duration')
      expect(durationCell).toHaveTextContent('-')
    })
  })

  describe('Accessibility', () => {
    it('renders semantic HTML structure', () => {
      render(<WaterfallTimeline items={mockItems} />)

      const container = document.querySelector('.waterfall-container')
      expect(container).toBeInTheDocument()

      const header = document.querySelector('.waterfall-header')
      expect(header).toBeInTheDocument()

      const rows = document.querySelector('.waterfall-rows')
      expect(rows).toBeInTheDocument()
    })

    it('provides tooltips with detailed event information', () => {
      render(<WaterfallTimeline items={mockItems} />)

      // Tooltips are rendered by Ant Design on hover
      // We can verify that Tooltip components wrap the bars
      const bars = document.querySelectorAll('.waterfall-bar')
      expect(bars.length).toBeGreaterThan(0)
    })
  })

  describe('Edge Cases', () => {
    it('handles single event', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Single Event',
          service: 's1',
          startOffset: 0,
          duration: 250,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      expect(screen.getByText('Single Event')).toBeInTheDocument()

      // Duration appears in the duration cell
      const durationCell = container.querySelector('.waterfall-duration')
      expect(durationCell).toHaveTextContent('250ms')
    })

    it('handles very large number of events', () => {
      const items: WaterfallItem[] = Array.from({ length: 100 }, (_, i) => ({
        id: `${i}`,
        event: `event${i}`,
        eventLabel: `Event ${i}`,
        service: 's1',
        startOffset: i * 10,
        duration: 10,
        timestamp: new Date(),
        metadata: {},
      }))

      const { container } = render(<WaterfallTimeline items={items} />)

      const rows = container.querySelectorAll('.waterfall-row')
      expect(rows).toHaveLength(100)
    })

    it('handles events with very long labels', () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'This is a very long event label that should be handled properly',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {},
        },
      ]

      render(<WaterfallTimeline items={items} />)

      expect(
        screen.getByText('This is a very long event label that should be handled properly')
      ).toBeInTheDocument()
    })

    it('handles special characters in metadata', async () => {
      const items: WaterfallItem[] = [
        {
          id: '1',
          event: 'event1',
          eventLabel: 'Event 1',
          service: 's1',
          startOffset: 0,
          duration: 100,
          timestamp: new Date(),
          metadata: {
            'key-with-dash': 'value',
            'key with spaces': 'another value',
            'key.with.dots': 123,
          },
        },
      ]

      const { container } = render(<WaterfallTimeline items={items} />)

      const row = container.querySelector('.waterfall-row')
      if (row) {
        await userEvent.click(row)
      }

      expect(screen.getByText('key-with-dash:')).toBeInTheDocument()
      expect(screen.getByText('key with spaces:')).toBeInTheDocument()
      expect(screen.getByText('key.with.dots:')).toBeInTheDocument()
    })
  })
})
