import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import WorkflowList from '../WorkflowList'

const mockGetWorkflowsListWorkflows = vi.fn()
const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

vi.mock('../../../api/generated', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/generated')>()
  return {
    ...actual,
    getV2: () => ({
      getWorkflowsListWorkflows: (...args: unknown[]) => mockGetWorkflowsListWorkflows(...args),
      postWorkflowsDeleteWorkflow: vi.fn(),
      postWorkflowsCloneWorkflow: vi.fn(),
    }),
  }
})

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={ROUTER_FUTURE}>
        <AntApp>
          <WorkflowList />
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('WorkflowList', () => {
  beforeEach(() => {
    mockGetWorkflowsListWorkflows.mockReset()
    mockGetWorkflowsListWorkflows.mockResolvedValue({
      workflows: [],
      count: 0,
      total: 0,
      authoring_phase: {
        phase: 'workflow_centric_prerequisite',
        label: 'Workflow-centric prerequisite phase',
        description: 'Workflows are becoming the primary analyst-facing scheme library for pools.',
        is_prerequisite_platform_phase: true,
        analyst_surface: '/workflows',
        rollout_scope: ['pool_distribution', 'pool_publication'],
        deferred_scope: ['extensions.*', 'database.ib_user.*'],
        follow_up_changes: ['add-13-service-workflow-automation'],
        construct_visibility: {
          contract_version: 'workflow_construct_visibility.v1',
          public_constructs: ['operation_task'],
          internal_runtime_only_constructs: ['generated_runtime_projection'],
          compatibility_constructs: ['workflow_executor_kind_template'],
        },
        source: 'default',
      },
    })
  })

  it('renders workflow authoring phase rollout banner', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Workflow-centric prerequisite phase')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Workflows are becoming the primary analyst-facing scheme library for pools.')
    ).toBeInTheDocument()
    expect(screen.getByText('Workflow Scheme Library')).toBeInTheDocument()
    expect(
      screen.getByText('Reusable analyst-authored workflow definitions for pool distribution and publication.')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New Scheme/ })).toBeInTheDocument()
    expect(screen.getByText('Primary analyst surface: /workflows')).toBeInTheDocument()
    expect(screen.getByText('pool_distribution')).toBeInTheDocument()
    expect(screen.getByText('pool_publication')).toBeInTheDocument()
    expect(screen.getByText('Deferred: extensions.*')).toBeInTheDocument()
    expect(screen.getByText('Deferred: database.ib_user.*')).toBeInTheDocument()
    expect(screen.getByText('Follow-up: add-13-service-workflow-automation')).toBeInTheDocument()
  })
})
