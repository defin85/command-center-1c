import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import { OperationsPage } from '../OperationsPage'
import type { UIBatchOperation } from '../types'

const mockUseOperations = vi.fn()
const mockCancelMutate = vi.fn()
const mockRefetch = vi.fn()
const mockGetRuntimeSettings = vi.fn()
const mockSetFilter = vi.fn()

function buildOperation(overrides: Partial<UIBatchOperation> = {}): UIBatchOperation {
  return {
    id: 'operation-1',
    name: 'workflow root execute',
    description: '',
    operation_type: 'query',
    target_entity: 'Workflow',
    status: 'processing',
    progress: 50,
    total_tasks: 2,
    completed_tasks: 1,
    failed_tasks: 0,
    payload: {},
    config: {},
    task_id: null,
    started_at: null,
    completed_at: null,
    duration_seconds: 1,
    success_rate: 50,
    created_by: 'admin',
    metadata: {},
    workflow_execution_id: 'workflow-run-1',
    node_id: 'services-node-1',
    root_operation_id: 'operation-1',
    execution_consumer: 'workflows',
    lane: 'workflows',
    trace_id: 'trace-1',
    created_at: '2026-03-10T12:00:00Z',
    updated_at: '2026-03-10T12:00:00Z',
    database_names: [],
    tasks: [],
    ...overrides,
  }
}

const operations = [
  buildOperation(),
  buildOperation({
    id: 'manual-op-1',
    name: 'manual lock scheduled jobs',
    operation_type: 'lock_scheduled_jobs',
    target_entity: 'Infobase',
    status: 'completed',
    progress: 100,
    total_tasks: 1,
    completed_tasks: 1,
    workflow_execution_id: undefined,
    node_id: undefined,
    root_operation_id: 'manual-op-1',
    execution_consumer: 'operations',
    lane: 'operations',
    trace_id: undefined,
  }),
]

vi.mock('../../../api/queries/operations', () => ({
  useOperations: (...args: unknown[]) => mockUseOperations(...args),
  useCancelOperation: () => ({ mutate: mockCancelMutate }),
}))

vi.mock('../../../api/generated', () => ({
  getV2: () => ({
    postWorkflowsExecuteWorkflow: vi.fn(),
  }),
}))

vi.mock('../../../api/operations', () => ({
  executeOperation: vi.fn(),
}))

vi.mock('../../../api/client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}))

vi.mock('../../../api/runtimeSettings', () => ({
  getRuntimeSettings: (...args: unknown[]) => mockGetRuntimeSettings(...args),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => ({
    isStaff: true,
    canAnyDatabase: () => true,
  }),
}))

vi.mock('../../../hooks/useOperationsMuxStream', () => ({
  useOperationsMuxStream: () => ({
    lastEvent: null,
  }),
}))

vi.mock('../../../components/table/hooks/useTableToolkit', () => ({
  useTableToolkit: () => ({
    pagination: { page: 1, pageSize: 50 },
    search: '',
    filtersPayload: undefined,
    sortPayload: undefined,
    setFilter: mockSetFilter,
    totalColumnsWidth: 960,
  }),
}))

vi.mock('../components/OperationsTable', () => ({
  OperationsTable: ({
    operations: items,
    onViewDetails,
  }: {
    operations: UIBatchOperation[]
    onViewDetails: (operation: UIBatchOperation) => void
  }) => (
    <div data-testid="operations-table">
      {items.map((operation) => (
        <div key={operation.id}>
          <span>{operation.name}</span>
          <button type="button" onClick={() => onViewDetails(operation)}>
            Details {operation.id}
          </button>
        </div>
      ))}
    </div>
  ),
}))

vi.mock('../components/OperationDetailsModal', () => ({
  OperationInspectPanel: ({
    operationId,
    onTimeline,
  }: {
    operationId: string | null
    onTimeline: (operationId: string) => void
  }) => (
    <div data-testid="operation-inspect-panel">
      <div>Inspect {operationId}</div>
      <button
        type="button"
        onClick={() => {
          if (operationId) {
            onTimeline(operationId)
          }
        }}
      >
        Open timeline
      </button>
    </div>
  ),
  OperationDetailsModal: () => null,
}))

vi.mock('../../../components/service-mesh/OperationTimelineDrawer', () => ({
  default: ({
    visible,
    operationId,
    onClose,
  }: {
    visible: boolean
    operationId: string | null
    onClose: () => void
  }) => (
    visible ? (
      <div data-testid="operation-timeline-drawer">
        <div>Timeline {operationId}</div>
        <button type="button" onClick={onClose}>
          Close timeline
        </button>
      </div>
    ) : null
  ),
}))

vi.mock('../components/NewOperationWizard', () => ({
  NewOperationWizard: () => null,
}))

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="operations-location">{location.pathname}{location.search}</output>
}

function renderOperationsPage(initialEntry = '/operations') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AntApp>
        <Routes>
          <Route
            path="/operations"
            element={(
              <>
                <OperationsPage />
                <LocationProbe />
              </>
            )}
          />
        </Routes>
      </AntApp>
    </MemoryRouter>
  )
}

describe('OperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetRuntimeSettings.mockResolvedValue([])
    mockUseOperations.mockReturnValue({
      data: {
        operations,
        count: operations.length,
        total: operations.length,
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    })
  })

  it('restores selected operation and active view from query params', async () => {
    const user = userEvent.setup()

    renderOperationsPage('/operations?operation=operation-1&tab=monitor')

    expect(await screen.findByRole('heading', { name: 'Operations Monitor', level: 2 })).toBeVisible()
    expect(screen.getByTestId('operation-timeline-drawer')).toHaveTextContent('Timeline operation-1')
    expect(screen.getByTestId('operations-location')).toHaveTextContent('/operations?operation=operation-1&tab=monitor')

    await user.click(screen.getByRole('button', { name: 'Close timeline' }))

    await waitFor(() => {
      expect(screen.getByTestId('operations-location')).toHaveTextContent('/operations?operation=operation-1&tab=inspect')
    })
    expect(screen.getByTestId('operation-inspect-panel')).toHaveTextContent('Inspect operation-1')
  })

  it('keeps selected operation and active view in the URL when the operator switches timeline context', async () => {
    const user = userEvent.setup()

    renderOperationsPage('/operations')

    expect(await screen.findByRole('heading', { name: 'Operations Monitor', level: 2 })).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Details manual-op-1' }))

    await waitFor(() => {
      expect(screen.getByTestId('operations-location')).toHaveTextContent('/operations?operation=manual-op-1&tab=inspect')
    })
    expect(screen.getByTestId('operation-inspect-panel')).toHaveTextContent('Inspect manual-op-1')

    await user.click(screen.getByRole('button', { name: 'Open timeline' }))

    await waitFor(() => {
      expect(screen.getByTestId('operations-location')).toHaveTextContent('/operations?operation=manual-op-1&tab=monitor')
    })
    expect(screen.getByTestId('operation-timeline-drawer')).toHaveTextContent('Timeline manual-op-1')

    await user.click(screen.getByRole('button', { name: 'Close timeline' }))

    await waitFor(() => {
      expect(screen.getByTestId('operations-location')).toHaveTextContent('/operations?operation=manual-op-1&tab=inspect')
    })
    expect(screen.getByTestId('operation-inspect-panel')).toHaveTextContent('Inspect manual-op-1')
  })
})
