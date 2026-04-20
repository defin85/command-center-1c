import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { changeLanguage, ensureNamespaces } from '@/i18n/runtime'

import WorkflowExecutions from '../WorkflowExecutions'

const mockGetWorkflowsListExecutions = vi.fn()
const mockGetWorkflowsGetExecution = vi.fn()
const mockPostWorkflowsCancelExecution = vi.fn()

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

vi.mock('../../../api/generated', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/generated')>()
  return {
    ...actual,
    getV2: () => ({
      getWorkflowsListExecutions: (...args: unknown[]) => mockGetWorkflowsListExecutions(...args),
      getWorkflowsGetExecution: (...args: unknown[]) => mockGetWorkflowsGetExecution(...args),
      postWorkflowsCancelExecution: (...args: unknown[]) => mockPostWorkflowsCancelExecution(...args),
    }),
  }
})

vi.mock('../../../components/platform', () => ({
  WorkspacePage: ({
    header,
    children,
  }: {
    header?: ReactNode
    children?: ReactNode
  }) => (
    <div data-testid="workflow-executions-workspace">
      {header}
      {children}
    </div>
  ),
  PageHeader: ({
    title,
    subtitle,
    actions,
  }: {
    title?: ReactNode
    subtitle?: ReactNode
    actions?: ReactNode
  }) => (
    <header data-testid="workflow-executions-header">
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
      <div>{actions}</div>
    </header>
  ),
  MasterDetailShell: ({
    list,
    detail,
  }: {
    list?: ReactNode
    detail?: ReactNode
  }) => (
    <div data-testid="workflow-executions-shell">
      <section>{list}</section>
      <aside>{detail}</aside>
    </div>
  ),
  EntityList: ({
    title,
    toolbar,
    dataSource,
    renderItem,
    empty,
    emptyDescription,
  }: {
    title?: ReactNode
    toolbar?: ReactNode
    dataSource?: Array<unknown>
    renderItem?: (item: never) => ReactNode
    empty?: boolean
    emptyDescription?: ReactNode
  }) => (
    <div data-testid="workflow-executions-entity-list">
      {title ? <h3>{title}</h3> : null}
      {toolbar}
      {empty ? <div>{emptyDescription}</div> : dataSource?.map((item, index) => (
        <div key={index}>{renderItem ? renderItem(item as never) : null}</div>
      ))}
    </div>
  ),
  EntityDetails: ({
    title,
    extra,
    empty,
    emptyDescription,
    children,
  }: {
    title?: ReactNode
    extra?: ReactNode
    empty?: boolean
    emptyDescription?: ReactNode
    children?: ReactNode
  }) => (
    <div data-testid="workflow-executions-entity-details">
      {title ? <h3>{title}</h3> : null}
      {extra}
      {empty ? <div>{emptyDescription}</div> : children}
    </div>
  ),
  JsonBlock: ({
    value,
    dataTestId,
  }: {
    value: unknown
    dataTestId?: string
  }) => (
    <pre data-testid={dataTestId}>{JSON.stringify(value, null, 2)}</pre>
  ),
  StatusBadge: ({
    label,
  }: {
    label?: ReactNode
  }) => <span>{label}</span>,
}))

function renderPage(initialEntry = '/workflows/executions') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]} future={ROUTER_FUTURE}>
        <AntApp>
          <WorkflowExecutions />
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('WorkflowExecutions', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'workflows')
    mockGetWorkflowsListExecutions.mockReset()
    mockGetWorkflowsGetExecution.mockReset()
    mockPostWorkflowsCancelExecution.mockReset()

    mockGetWorkflowsListExecutions.mockResolvedValue({
      executions: [
        {
          id: 'exec-1',
          workflow_template: 'workflow-1',
          template_name: 'Workflow 1',
          template_version: 3,
          status: 'running',
          progress_percent: '45.0',
          current_node_id: 'node-2',
          error_message: '',
          error_node_id: '',
          trace_id: 'trace-1',
          started_at: '2026-03-08T12:00:00Z',
          completed_at: null,
          duration: 12,
        },
      ],
      count: 1,
      total: 1,
    })
    mockGetWorkflowsGetExecution.mockResolvedValue({
      execution: {
        id: 'exec-1',
        workflow_template: 'workflow-1',
        template_name: 'Workflow 1',
        template_version: 3,
        status: 'running',
        input_context: { pool_id: 'pool-1' },
        final_result: null,
        current_node_id: 'node-2',
        completed_nodes: ['node-1'],
        failed_nodes: [],
        node_statuses: { 'node-1': 'completed', 'node-2': 'running' },
        progress_percent: '45.0',
        error_message: '',
        error_node_id: '',
        trace_id: 'trace-1',
        started_at: '2026-03-08T12:00:00Z',
        completed_at: null,
        duration: 12,
        step_results: [],
      },
      execution_plan: undefined,
      bindings: [],
      steps: [],
    })
    mockPostWorkflowsCancelExecution.mockResolvedValue({ success: true })
  })

  afterEach(async () => {
    await ensureNamespaces('ru', 'workflows')
    await changeLanguage('ru')
  })

  it('applies route-backed filters to the list query', async () => {
    renderPage('/workflows/executions?status=running&workflow_id=11111111-1111-4111-8111-111111111111')

    await waitFor(() => {
      expect(mockGetWorkflowsListExecutions).toHaveBeenCalledWith(expect.objectContaining({
        status: 'running',
        workflow_id: '11111111-1111-4111-8111-111111111111',
      }))
    })
  })

  it('restores selected execution detail from route state', async () => {
    renderPage('/workflows/executions?status=running&execution=exec-1&detail=1')

    expect(await screen.findByTestId('workflow-executions-selected-id')).toHaveTextContent('exec-1')
    expect(await screen.findByTestId('workflow-executions-selected-node-statuses')).toHaveTextContent('"node-2"')
    expect(await screen.findByTestId('workflow-executions-selected-input-context')).toHaveTextContent('"pool_id"')
  })
})
