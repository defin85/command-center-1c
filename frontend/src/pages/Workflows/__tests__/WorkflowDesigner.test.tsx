import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockGetWorkflowsGetWorkflow = vi.fn()
const mockGetWorkflowsListWorkflows = vi.fn()
const mockGetDecisionsCollection = vi.fn()
const mockListOperationCatalogExposures = vi.fn()
const mockPropertyEditor = vi.fn()
const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

vi.mock('../../../api/generated/v2/v2', () => ({
  getV2: () => ({
    getWorkflowsGetWorkflow: (...args: unknown[]) => mockGetWorkflowsGetWorkflow(...args),
    getWorkflowsListWorkflows: (...args: unknown[]) => mockGetWorkflowsListWorkflows(...args),
    getDecisionsCollection: (...args: unknown[]) => mockGetDecisionsCollection(...args),
    postWorkflowsCreateWorkflow: vi.fn(),
    postWorkflowsUpdateWorkflow: vi.fn(),
    postWorkflowsValidateWorkflow: vi.fn(),
    postWorkflowsExecuteWorkflow: vi.fn(),
  }),
}))

vi.mock('../../../api/operationCatalog', () => ({
  listOperationCatalogExposures: (...args: unknown[]) => mockListOperationCatalogExposures(...args),
}))

vi.mock('../../../components/workflow', () => ({
  WorkflowCanvas: ({ mode }: { mode: string }) => (
    <div data-testid="workflow-canvas">{mode}</div>
  ),
  NodePalette: () => <div data-testid="node-palette">palette</div>,
  PropertyEditor: (props: { readOnly?: boolean }) => {
    mockPropertyEditor(props)
    return <div data-testid="property-editor">{props.readOnly ? 'read-only' : 'editable'}</div>
  },
}))

vi.mock('../../../components/code/LazyJsonCodeEditor', () => ({
  LazyJsonCodeEditor: () => <div data-testid="json-editor">json-editor</div>,
}))

const { default: WorkflowDesigner } = await import('../WorkflowDesigner')

function renderPage(initialEntry = '/workflows/runtime-1?surface=runtime_diagnostics') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]} future={ROUTER_FUTURE}>
      <Routes>
        <Route
          path="/workflows/:id"
          element={(
            <AntApp>
              <WorkflowDesigner />
            </AntApp>
          )}
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('WorkflowDesigner', () => {
  beforeEach(() => {
    mockGetWorkflowsGetWorkflow.mockReset()
    mockGetWorkflowsListWorkflows.mockReset()
    mockGetDecisionsCollection.mockReset()
    mockListOperationCatalogExposures.mockReset()
    mockPropertyEditor.mockReset()

    mockGetWorkflowsGetWorkflow.mockResolvedValue({
      workflow: {
        id: 'runtime-1',
        name: 'Runtime Projection',
        description: 'system-managed',
        workflow_type: 'complex',
        category: 'system',
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
        is_system_managed: true,
        management_mode: 'system_managed',
        visibility_surface: 'runtime_diagnostics',
        read_only_reason: 'System-managed runtime workflow projections are read-only.',
        version_number: 1,
        parent_version: null,
        parent_version_name: null,
        created_by: null,
        created_by_username: 'system',
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
    mockGetWorkflowsListWorkflows.mockResolvedValue({
      workflows: [
        {
          id: 'workflow-root',
          name: 'Services Publication',
          description: 'root revision',
          workflow_type: 'complex',
          category: 'custom',
          is_valid: true,
          is_active: true,
          is_system_managed: false,
          management_mode: 'user_authored',
          visibility_surface: 'workflow_library',
          read_only_reason: null,
          version_number: 1,
          parent_version: null,
          created_by: null,
          created_by_username: 'analyst',
          node_count: 2,
          execution_count: 0,
          created_at: '2026-03-08T12:00:00Z',
          updated_at: '2026-03-08T12:00:00Z',
        },
        {
          id: 'workflow-revision-3',
          name: 'Services Publication',
          description: 'latest revision',
          workflow_type: 'complex',
          category: 'custom',
          is_valid: true,
          is_active: true,
          is_system_managed: false,
          management_mode: 'user_authored',
          visibility_surface: 'workflow_library',
          read_only_reason: null,
          version_number: 3,
          parent_version: 'workflow-root',
          created_by: null,
          created_by_username: 'analyst',
          node_count: 5,
          execution_count: 0,
          created_at: '2026-03-08T12:00:00Z',
          updated_at: '2026-03-08T12:00:00Z',
        },
      ],
      authoring_phase: {
        key: 'workflow_centric_prerequisite',
        is_active: false,
        summary: 'prerequisite',
      },
      count: 2,
      total: 2,
    })
    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [
        {
          id: 'decision-version-2',
          decision_table_id: 'decision-root',
          decision_key: 'invoice_mode',
          decision_revision: 2,
          name: 'Invoice Mode',
          description: 'fail-closed routing',
          inputs: [],
          outputs: [],
          rules: [],
          hit_policy: 'first_match',
          validation_mode: 'fail_closed',
          is_active: true,
          parent_version: null,
          created_at: '2026-03-08T12:00:00Z',
          updated_at: '2026-03-08T12:00:00Z',
        },
      ],
      count: 1,
    })
    mockListOperationCatalogExposures.mockResolvedValue({ exposures: [] })
  })

  it('renders runtime projections as read-only diagnostics surface', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Runtime Projection')).toBeInTheDocument()
    })

    expect(screen.getByText('Runtime diagnostics surface')).toBeInTheDocument()
    expect(screen.getByText('System-managed runtime workflow projections are read-only.')).toBeInTheDocument()
    expect(screen.queryByTestId('node-palette')).not.toBeInTheDocument()
    expect(screen.getByTestId('workflow-canvas')).toHaveTextContent('monitor')
    expect(screen.getByTestId('property-editor')).toHaveTextContent('read-only')
    expect(screen.getByRole('button', { name: /Validate/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Save/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Execute/ })).toBeDisabled()
  })

  it('renders authored workflows as analyst-facing scheme editor', async () => {
    mockGetWorkflowsGetWorkflow.mockResolvedValueOnce({
      workflow: {
        id: 'analyst-1',
        name: 'Services Publication',
        description: 'analyst-authored',
        workflow_type: 'complex',
        category: 'custom',
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
        is_system_managed: false,
        management_mode: 'user_authored',
        visibility_surface: 'workflow_library',
        read_only_reason: null,
        version_number: 3,
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

    renderPage('/workflows/analyst-1')

    await waitFor(() => {
      expect(screen.getByText('Services Publication')).toBeInTheDocument()
    })

    expect(screen.getByText('Workflow scheme library')).toBeInTheDocument()
    expect(
      screen.getByText('This editor authors reusable workflow definitions for pools. Templates stay atomic, pool bindings decide where the scheme is active, and runtime projections are compiled into diagnostics-only artifacts.')
    ).toBeInTheDocument()
    expect(screen.getByTestId('node-palette')).toBeInTheDocument()
    expect(screen.getByTestId('workflow-canvas')).toHaveTextContent('design')
    expect(screen.getByTestId('property-editor')).toHaveTextContent('editable')
    expect(screen.queryByText('Runtime diagnostics surface')).not.toBeInTheDocument()
    await waitFor(() => expect(mockGetWorkflowsListWorkflows).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(mockGetDecisionsCollection).toHaveBeenCalledTimes(1))

    const lastPropertyEditorProps = mockPropertyEditor.mock.calls[mockPropertyEditor.mock.calls.length - 1]?.[0]
    expect(lastPropertyEditorProps).toEqual(
      expect.objectContaining({
        availableWorkflows: expect.arrayContaining([
          expect.objectContaining({
            workflowDefinitionKey: 'workflow-root',
            workflowRevisionId: 'workflow-revision-3',
            workflowRevision: 3,
          }),
        ]),
        availableDecisions: [
          {
            id: 'decision-version-2',
            name: 'Invoice Mode',
            decisionTableId: 'decision-root',
            decisionKey: 'invoice_mode',
            decisionRevision: 2,
          },
        ],
      })
    )
  })
})
