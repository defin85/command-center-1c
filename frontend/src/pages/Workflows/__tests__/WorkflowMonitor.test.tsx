import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockGetWorkflowsGetExecution = vi.fn()
const mockGetWorkflowsGetWorkflow = vi.fn()
const mockUseWorkflowExecution = vi.fn()

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

vi.mock('../../../api/generated', () => ({
  getV2: () => ({
    getWorkflowsGetExecution: (...args: unknown[]) => mockGetWorkflowsGetExecution(...args),
    getWorkflowsGetWorkflow: (...args: unknown[]) => mockGetWorkflowsGetWorkflow(...args),
    postWorkflowsCancelExecution: vi.fn(),
  }),
}))

vi.mock('../../../hooks/useWorkflowExecution', () => ({
  useWorkflowExecution: (...args: unknown[]) => mockUseWorkflowExecution(...args),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => ({ isStaff: true }),
}))

vi.mock('../../../components/workflow', () => ({
  WorkflowCanvas: () => <div data-testid="workflow-monitor-canvas">monitor</div>,
}))

vi.mock('../../../components/workflow/TraceViewerModal', () => ({
  TraceViewerModal: () => null,
}))

vi.mock('../components/NodeDetailsDrawer', () => ({
  NodeDetailsDrawer: ({
    open,
    selectedNode,
  }: {
    open: boolean
    selectedNode: { nodeId: string; nodeName: string } | null
  }) => (
    open
      ? <div data-testid="workflow-monitor-node-drawer">{`${selectedNode?.nodeName}:${selectedNode?.nodeId}`}</div>
      : null
  ),
}))

const { default: WorkflowMonitor } = await import('../WorkflowMonitor')

function renderPage(initialEntry = '/workflows/executions/exec-1?node=start') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]} future={ROUTER_FUTURE}>
      <Routes>
        <Route
          path="/workflows/executions/:executionId"
          element={(
            <AntApp>
              <WorkflowMonitor />
            </AntApp>
          )}
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('WorkflowMonitor', () => {
  beforeEach(() => {
    mockGetWorkflowsGetExecution.mockReset()
    mockGetWorkflowsGetWorkflow.mockReset()
    mockUseWorkflowExecution.mockReset()

    mockGetWorkflowsGetExecution.mockResolvedValue({
      execution: {
        id: 'exec-1',
        workflow_template: 'workflow-1',
        template_name: 'Services Publication',
        template_version: 4,
        status: 'pending',
        input_context: { pool_id: 'pool-1' },
        final_result: null,
        current_node_id: '',
        completed_nodes: {},
        failed_nodes: {},
        node_statuses: {
          start: {
            status: 'pending',
          },
        },
        progress_percent: '0.00',
        error_message: '',
        error_node_id: '',
        trace_id: '',
        started_at: '2026-03-08T12:00:00Z',
        completed_at: null,
        duration: 0,
        step_results: [],
      },
      execution_plan: {
        kind: 'workflow',
        workflow_id: 'workflow-1',
      },
      bindings: [],
      steps: [],
    })

    mockGetWorkflowsGetWorkflow.mockResolvedValue({
      workflow: {
        id: 'workflow-1',
        name: 'Services Publication',
        description: '',
        workflow_type: 'complex',
        dag_structure: {
          nodes: [
            {
              id: 'start',
              name: 'Start',
              type: 'operation',
              template_id: 'noop',
            },
          ],
          edges: [],
        },
        config: {},
        is_valid: true,
        is_active: true,
        version_number: 4,
        parent_version: null,
        parent_version_name: null,
        created_by: null,
        created_by_username: 'analyst',
        execution_count: 0,
        created_at: '2026-03-08T12:00:00Z',
        updated_at: '2026-03-08T12:00:00Z',
      },
      statistics: {
        total_executions: 0,
        successful: 0,
        failed: 0,
        cancelled: 0,
        running: 0,
        average_duration: null,
      },
      executions: [],
    })

    mockUseWorkflowExecution.mockReturnValue({
      status: 'pending',
      progress: 0,
      currentNodeId: undefined,
      traceId: undefined,
      errorMessage: undefined,
      result: undefined,
      nodeStatuses: {},
      isConnected: false,
      connectionError: null,
      reconnectAttempts: 0,
      requestStatus: vi.fn(),
      subscribeToNodes: vi.fn(),
      disconnect: vi.fn(),
    })
  })

  it('restores selected node inspection from node query parameter', async () => {
    renderPage()

    await waitFor(() => {
      expect(mockGetWorkflowsGetExecution).toHaveBeenCalledWith({ execution_id: 'exec-1' })
    })

    expect(screen.getByText('Workflow Execution')).toBeInTheDocument()
    expect(screen.getByText('Execution Info')).toBeInTheDocument()
    expect(screen.getByTestId('workflow-monitor-node-drawer')).toHaveTextContent('Start:start')
    expect(screen.getByTestId('workflow-monitor-selected-node')).toHaveTextContent('Selected node: Start')
  })

  it('renders final result from execution payload when websocket result is unavailable', async () => {
    mockGetWorkflowsGetExecution.mockResolvedValueOnce({
      execution: {
        id: 'exec-1',
        workflow_template: 'workflow-1',
        template_name: 'Services Publication',
        template_version: 4,
        status: 'completed',
        input_context: { pool_id: 'pool-1' },
        final_result: { document_id: 'doc-42', status: 'published' },
        current_node_id: '',
        completed_nodes: {},
        failed_nodes: {},
        node_statuses: {
          start: {
            status: 'completed',
          },
        },
        progress_percent: '100.00',
        error_message: '',
        error_node_id: '',
        trace_id: '',
        started_at: '2026-03-08T12:00:00Z',
        completed_at: '2026-03-08T12:00:30Z',
        duration: 30,
        step_results: [],
      },
      execution_plan: {
        kind: 'workflow',
        workflow_id: 'workflow-1',
      },
      bindings: [],
      steps: [],
    })

    renderPage('/workflows/executions/exec-1')

    await waitFor(() => {
      expect(screen.getByText('Workflow Execution')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Execution Completed'))
    expect(await screen.findByTestId('workflow-monitor-final-result')).toHaveTextContent('doc-42')
  })
})
