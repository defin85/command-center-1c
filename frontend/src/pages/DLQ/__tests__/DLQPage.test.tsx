import { App as AntApp } from 'antd'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import type { DLQMessage } from '../../../api/generated/model/dLQMessage'

const {
  mockUseDlqMessages,
  mockUseDlqMessage,
  mockRetryMutateAsync,
  mockTrackUiAction,
} = vi.hoisted(() => ({
  mockUseDlqMessages: vi.fn(),
  mockUseDlqMessage: vi.fn(),
  mockRetryMutateAsync: vi.fn(),
  mockTrackUiAction: vi.fn((_: unknown, handler?: () => unknown) => handler?.()),
}))

vi.mock('../../../api/queries/dlq', () => ({
  useDlqMessages: (...args: unknown[]) => mockUseDlqMessages(...args),
  useDlqMessage: (...args: unknown[]) => mockUseDlqMessage(...args),
  useRetryDlqMessage: () => ({
    mutateAsync: mockRetryMutateAsync,
    isPending: false,
  }),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => ({
    isStaff: true,
  }),
}))

vi.mock('../../../observability/confirmWithTracking', () => ({
  confirmWithTracking: vi.fn(),
}))

vi.mock('../../../observability/uiActionJournal', () => ({
  trackUiAction: mockTrackUiAction,
}))

vi.mock('../../../components/table/hooks/useTableToolkit', () => ({
  useTableToolkit: () => ({
    search: '',
    filters: {},
    filtersPayload: {},
    sort: {},
    sortPayload: undefined,
    pagination: {
      page: 1,
      pageSize: 50,
    },
    totalColumnsWidth: 960,
  }),
}))

vi.mock('../../../components/table/TableToolkit', () => ({
  TableToolkit: ({
    data,
    columns,
  }: {
    data: Array<Record<string, unknown>>
    columns: Array<{
      key?: string
      render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
    }>
  }) => {
    const actionsColumn = columns.find((column) => column.key === 'actions')

    return (
      <div data-testid="dlq-table">
        {data.map((entry, index) => (
          <div key={String(entry.dlq_message_id)} data-testid={`dlq-row-actions-${String(entry.dlq_message_id)}`}>
            {actionsColumn?.render?.(null, entry, index) ?? null}
          </div>
        ))}
      </div>
    )
  },
}))

vi.mock('../../../components/platform', () => ({
  WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
    <div>
      {header}
      {children}
    </div>
  ),
  PageHeader: ({ title, actions }: { title: ReactNode; actions?: ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {actions}
    </div>
  ),
  DrawerSurfaceShell: ({
    open,
    extra,
    children,
  }: {
    open: boolean
    extra?: ReactNode
    children: ReactNode
  }) => (
    open ? (
      <div>
        {extra}
        {children}
      </div>
    ) : null
  ),
  RouteButton: ({ children }: { children?: ReactNode }) => <button type="button">{children}</button>,
}))

import { DLQPage } from '../DLQPage'

const buildMessage = (overrides: Partial<DLQMessage> = {}): DLQMessage => ({
  dlq_message_id: 'dlq-1',
  operation_id: 'op-1',
  original_message_id: 'orig-1',
  error_code: 'WORKER_FAILED',
  error_message: 'Worker failed',
  worker_id: 'worker-1',
  failed_at: '2026-04-08T12:00:00Z',
  ...overrides,
})

describe('DLQPage observability', () => {
  beforeEach(() => {
    mockUseDlqMessages.mockReset()
    mockUseDlqMessage.mockReset()
    mockRetryMutateAsync.mockReset()
    mockTrackUiAction.mockClear()
    mockUseDlqMessage.mockReturnValue({
      data: null,
      isLoading: false,
    })
  })

  it('tracks single-message retry actions through trackUiAction', async () => {
    const user = userEvent.setup()
    const entry = buildMessage()

    mockUseDlqMessages.mockReturnValue({
      data: {
        messages: [entry],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
    mockRetryMutateAsync.mockResolvedValue({
      enqueued: true,
      operation_id: 'op-1',
      message: 'ok',
    })

    render(
      <MemoryRouter initialEntries={['/dlq']}>
        <AntApp>
          <Routes>
            <Route path="/dlq" element={<DLQPage />} />
          </Routes>
        </AntApp>
      </MemoryRouter>,
    )

    await user.click(
      within(screen.getByTestId('dlq-row-actions-dlq-1')).getByRole('button', { name: /Retry/ }),
    )

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Retry DLQ message',
        context: {
          dlq_message_id: 'dlq-1',
          operation_id: 'op-1',
          original_message_id: 'orig-1',
          manual_operation: 'dlq.retry_single',
        },
      }),
      expect.any(Function),
    )
    expect(mockRetryMutateAsync).toHaveBeenCalledWith({
      operation_id: 'op-1',
      original_message_id: undefined,
      reason: undefined,
    })
  })
})
