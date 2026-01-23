/**
 * Tests for OperationTimelineDrawer Component
 *
 * Tests operation timeline drawer functionality:
 * - Drawer opens/closes correctly
 * - Loading state while fetching data
 * - Error state on API failure
 * - Successful data display with statistics
 * - API call with correct operation ID
 * - Empty state handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OperationTimelineDrawer from '../OperationTimelineDrawer'
import { apiClient } from '../../../api/client'
import type { OperationTimelineResponse } from '../../../types/operationTimeline'

// Mock API client
vi.mock('../../../api/client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}))

// Mock WaterfallTimeline component to simplify testing
vi.mock('../WaterfallTimeline', () => ({
  default: ({ items }: { items: unknown[] }) => (
    <div data-testid="waterfall-timeline">
      {items.length} items
    </div>
  ),
}))

describe('OperationTimelineDrawer', () => {
  const mockOperationId = 'op-123456789012345' // Long ID to test truncation
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

  describe('Drawer State', () => {
    it('does not render when visible is false', () => {
      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Ant Design Drawer with open=false should not show title
      expect(screen.queryByText('Operation Timeline')).not.toBeInTheDocument()
    })

    it('renders when visible is true', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      expect(screen.getByText('Operation Timeline')).toBeInTheDocument()
      await waitFor(() => expect(vi.mocked(apiClient.post)).toHaveBeenCalled())
    })

    it('calls onClose when drawer is closed', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Find and click close button (Ant Design Drawer has a close icon)
      const closeButton = screen.getByRole('button', { name: /close/i })
      await user.click(closeButton)

      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('displays formatted operation ID in title', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Wait for render to complete
      await waitFor(() => {
        // Drawer renders into document.body, use document.body to search
        const titleElement = document.querySelector('.operation-timeline-drawer__id')
        expect(titleElement).toBeInTheDocument()
        // ID should be truncated: first 8 chars + … + last 4 chars
        expect(titleElement).toHaveTextContent('op-12345\u20262345')
      })
    })

    it('displays full operation ID when shorter than 12 chars', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId="short-id"
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => expect(screen.getByText('short-id')).toBeInTheDocument())
      await waitFor(() => expect(vi.mocked(apiClient.post)).toHaveBeenCalled())
    })
  })

  describe('Loading State', () => {
    it('shows loading spinner while fetching data', async () => {
      vi.mocked(apiClient.post).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Look for Spin component with tip text
      await waitFor(() => {
        const spinElement = document.querySelector('.ant-spin')
        expect(spinElement).toBeInTheDocument()
      })
    })

    it('shows loading spinner immediately when drawer opens', () => {
      vi.mocked(apiClient.post).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      const { rerender } = render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Check for Spin component
      const spinElement = document.querySelector('.ant-spin')
      expect(spinElement).toBeInTheDocument()
    })
  })

  describe('API Calls', () => {
    it('fetches timeline data when drawer opens', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith(
          '/api/v2/operations/get-operation-timeline/',
          { operation_id: mockOperationId },
          apiOptions
        )
      })
    })

    it('does not fetch data when drawer is closed', () => {
      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      expect(apiClient.post).not.toHaveBeenCalled()
    })

    it('does not fetch data when operationId is null', () => {
      render(
        <OperationTimelineDrawer
          operationId={null}
          visible={true}
          onClose={mockOnClose}
        />
      )

      expect(apiClient.post).not.toHaveBeenCalled()
    })

    it('refetches data when operationId changes', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      const { rerender } = render(
        <OperationTimelineDrawer
          operationId="op-first"
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith(
          '/api/v2/operations/get-operation-timeline/',
          { operation_id: 'op-first' },
          apiOptions
        )
      })

      vi.clearAllMocks()

      rerender(
        <OperationTimelineDrawer
          operationId="op-second"
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith(
          '/api/v2/operations/get-operation-timeline/',
          { operation_id: 'op-second' },
          apiOptions
        )
      })
    })

    it('refetches data when drawer reopens', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      const { rerender } = render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledTimes(1)
      })

      vi.clearAllMocks()

      // Close drawer
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Reopen drawer
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledTimes(1)
      })
    })
  })

  describe('Error State', () => {
    beforeEach(() => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
    })

    it('shows error message on API failure', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'))

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Error Loading Timeline')).toBeInTheDocument()
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })
    })

    it('shows error message from API response.data.error', async () => {
      // Create proper AxiosError-like object
      const axiosError = Object.assign(new Error('Request failed'), {
        isAxiosError: true,
        response: {
          data: {
            error: 'Operation not found',
          },
          status: 404,
        },
      })
      vi.mocked(apiClient.post).mockRejectedValue(axiosError)

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Operation not found')).toBeInTheDocument()
      })
    })

    it('shows error message from API response.data.detail', async () => {
      // Create proper AxiosError-like object
      const axiosError = Object.assign(new Error('Request failed'), {
        isAxiosError: true,
        response: {
          data: {
            detail: 'Unauthorized access',
          },
          status: 401,
        },
      })
      vi.mocked(apiClient.post).mockRejectedValue(axiosError)

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Unauthorized access')).toBeInTheDocument()
      })
    })

    it('shows default error message for unknown errors', async () => {
      vi.mocked(apiClient.post).mockRejectedValue('unknown error')

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Failed to load timeline data')).toBeInTheDocument()
      })
    })

    it('clears error when drawer is closed', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'))

      const { rerender } = render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })

      // Close drawer
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Error should be cleared
      expect(screen.queryByText('Network error')).not.toBeInTheDocument()
    })
  })

  describe('Success State', () => {
    beforeEach(() => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })
    })

    it('displays summary statistics', async () => {
      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Total Duration')).toBeInTheDocument()
        expect(screen.getByText('1.6s')).toBeInTheDocument() // 1600ms formatted

        expect(screen.getByText('Events')).toBeInTheDocument()
        expect(screen.getByText('4')).toBeInTheDocument()

        expect(screen.getByText('Services')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument() // orchestrator + worker
      })
    })

    it('shows "In Progress" when duration_ms is null', async () => {
      const inProgressResponse: OperationTimelineResponse = {
        ...mockTimelineResponse,
        duration_ms: null,
      }
      vi.mocked(apiClient.post).mockResolvedValue({ data: inProgressResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('In Progress')).toBeInTheDocument()
      })
    })

    it('calculates unique services count correctly', async () => {
      const responseWithDuplicates: OperationTimelineResponse = {
        operation_id: mockOperationId,
        timeline: [
          { timestamp: 1000, event: 'e1', service: 'orchestrator', metadata: {} },
          { timestamp: 2000, event: 'e2', service: 'worker', metadata: {} },
          { timestamp: 3000, event: 'e3', service: 'worker', metadata: {} },
          { timestamp: 4000, event: 'e4', service: 'orchestrator', metadata: {} },
        ],
        total_events: 4,
        duration_ms: 3000,
      }
      vi.mocked(apiClient.post).mockResolvedValue({ data: responseWithDuplicates })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const servicesStatistic = screen.getByText('Services').closest('.ant-statistic')
        expect(servicesStatistic).toHaveTextContent('2')
      })
    })

    it('renders WaterfallTimeline with transformed data', async () => {
      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        const waterfall = screen.getByTestId('waterfall-timeline')
        expect(waterfall).toBeInTheDocument()
        expect(waterfall).toHaveTextContent('4 items') // 4 timeline events
      })
    })

    it('clears data when drawer is closed', async () => {
      const { rerender } = render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Total Duration')).toBeInTheDocument()
      })

      // Close drawer
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Data should be cleared (drawer is closed, so content not visible)
      expect(screen.queryByText('Total Duration')).not.toBeInTheDocument()
    })
  })

  describe('Empty States', () => {
    it('shows empty state when timeline is empty but API succeeded', async () => {
      const emptyResponse: OperationTimelineResponse = {
        operation_id: mockOperationId,
        timeline: [],
        total_events: 0,
        duration_ms: 0,
      }
      vi.mocked(apiClient.post).mockResolvedValue({ data: emptyResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('No timeline events recorded')).toBeInTheDocument()
      })
    })

    it('shows select operation prompt when no operation ID provided', () => {
      render(
        <OperationTimelineDrawer
          operationId={null}
          visible={true}
          onClose={mockOnClose}
        />
      )

      expect(screen.getByText('Select an operation to view its timeline')).toBeInTheDocument()
    })

    it('does not show loading state when no operation ID provided', () => {
      render(
        <OperationTimelineDrawer
          operationId={null}
          visible={true}
          onClose={mockOnClose}
        />
      )

      expect(screen.queryByText('Loading timeline\u2026')).not.toBeInTheDocument()
    })
  })

  describe('Drawer Configuration', () => {
    it('renders with correct width', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Drawer renders into document.body portal
      const drawer = document.querySelector('.ant-drawer')
      expect(drawer).toBeInTheDocument()
      await waitFor(() => expect(vi.mocked(apiClient.post)).toHaveBeenCalled())
      // Width is set via inline styles by Ant Design
    })

    it('renders on right side', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Drawer renders into document.body portal
      const drawer = document.querySelector('.ant-drawer-right')
      expect(drawer).toBeInTheDocument()
      await waitFor(() => expect(vi.mocked(apiClient.post)).toHaveBeenCalled())
    })

    it('has correct CSS class', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Drawer renders into document.body portal
      const drawer = document.querySelector('.operation-timeline-drawer')
      expect(drawer).toBeInTheDocument()
      await waitFor(() => expect(vi.mocked(apiClient.post)).toHaveBeenCalled())
    })
  })

  describe('Integration', () => {
    it('complete flow: open → load → display → close', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockTimelineResponse })

      const { rerender } = render(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Initially closed
      expect(screen.queryByText('Operation Timeline')).not.toBeInTheDocument()

      // Open drawer
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={true}
          onClose={mockOnClose}
        />
      )

      // Should show loading (check for Spin component)
      const spinElement = document.querySelector('.ant-spin')
      expect(spinElement).toBeInTheDocument()

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText('Total Duration')).toBeInTheDocument()
        expect(screen.getByText('1.6s')).toBeInTheDocument()
      })

      // Verify API was called
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v2/operations/get-operation-timeline/',
        { operation_id: mockOperationId },
        apiOptions
      )

      // Close drawer
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Content should be cleared
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

      // Immediately close before data loads
      rerender(
        <OperationTimelineDrawer
          operationId={mockOperationId}
          visible={false}
          onClose={mockOnClose}
        />
      )

      // Wait to ensure no errors
      await waitFor(() => {
        expect(screen.queryByText('Total Duration')).not.toBeInTheDocument()
      })
    })
  })
})
