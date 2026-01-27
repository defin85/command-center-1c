import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import OperationTimelineDrawer from '../OperationTimelineDrawer'
import { apiClient } from '../../../api/client'
import type { OperationTimelineResponse } from '../../../types/operationTimeline'

vi.mock('../../../api/client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}))

vi.mock('../WaterfallTimeline', () => ({
  default: ({ items }: { items: unknown[] }) => (
    <div data-testid="waterfall-timeline">
      {items.length} items
    </div>
  ),
}))

describe('OperationTimelineDrawer (integration)', () => {
  const mockOperationId = 'op-123456789012345'
  const mockOnClose = vi.fn()
  const apiOptions = { skipGlobalError: true }

  const mockTimelineResponse: OperationTimelineResponse = {
    operation_id: mockOperationId,
    timeline: [
      {
        timestamp: 1000,
        event: 'orchestrator.created',
        service: 'orchestrator',
        metadata: { user_id: '123' },
      },
      {
        timestamp: 1500,
        event: 'worker.command.received',
        service: 'worker',
        metadata: {},
      },
      {
        timestamp: 2500,
        event: 'worker.command.completed',
        service: 'worker',
        metadata: { result: 'success' },
      },
      {
        timestamp: 2600,
        event: 'orchestrator.completed',
        service: 'orchestrator',
        metadata: {},
      },
    ],
    total_events: 4,
    duration_ms: 1600,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('complete flow: open → load → display → close', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

    const { rerender } = render(
      <OperationTimelineDrawer
        operationId={mockOperationId}
        visible={false}
        onClose={mockOnClose}
      />
    )

    expect(screen.queryByText('Operation Timeline')).not.toBeInTheDocument()

    rerender(
      <OperationTimelineDrawer
        operationId={mockOperationId}
        visible={true}
        onClose={mockOnClose}
      />
    )

    const spinElement = document.querySelector('.ant-spin')
    expect(spinElement).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Total Duration')).toBeInTheDocument()
      expect(screen.getByText('1.6s')).toBeInTheDocument()
    })

    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v2/operations/get-operation-timeline/',
      { operation_id: mockOperationId },
      apiOptions
    )

    rerender(
      <OperationTimelineDrawer
        operationId={mockOperationId}
        visible={false}
        onClose={mockOnClose}
      />
    )

    expect(screen.queryByText('Total Duration')).not.toBeInTheDocument()
  })

  it('handles rapid open/close without race conditions', async () => {
    vi.mocked(apiClient.post).mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ data: mockTimelineResponse }), 100)
        })
    )

    const { rerender } = render(
      <OperationTimelineDrawer
        operationId={mockOperationId}
        visible={true}
        onClose={mockOnClose}
      />
    )

    rerender(
      <OperationTimelineDrawer
        operationId={mockOperationId}
        visible={false}
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.queryByText('Total Duration')).not.toBeInTheDocument()
    })
  })
})

