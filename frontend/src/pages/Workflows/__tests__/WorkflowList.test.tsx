import { StrictMode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { changeLanguage, ensureNamespaces } from '@/i18n/runtime'

import WorkflowList from '../WorkflowList'

const mockGetWorkflowsListWorkflows = vi.fn()
const mockGetWorkflowsGetWorkflow = vi.fn()
const mockNavigate = vi.fn()
const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../../../api/generated', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/generated')>()
  return {
    ...actual,
    getV2: () => ({
      getWorkflowsListWorkflows: (...args: unknown[]) => mockGetWorkflowsListWorkflows(...args),
      getWorkflowsGetWorkflow: (...args: unknown[]) => mockGetWorkflowsGetWorkflow(...args),
      postWorkflowsDeleteWorkflow: vi.fn(),
      postWorkflowsCloneWorkflow: vi.fn(),
    }),
  }
})

function renderPage(initialEntry = '/workflows') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  const content = (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]} future={ROUTER_FUTURE}>
        <AntApp>
          <WorkflowList />
          <WorkflowListLocationProbe />
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )

  return {
    renderStrict: () => render(<StrictMode>{content}</StrictMode>),
    renderDefault: () => render(content),
  }
}

function WorkflowListLocationProbe() {
  const location = useLocation()
  return <output data-testid="workflow-list-route-search">{location.search}</output>
}

describe('WorkflowList', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'workflows')
    mockGetWorkflowsListWorkflows.mockReset()
    mockGetWorkflowsGetWorkflow.mockReset()
    mockNavigate.mockReset()
    mockGetWorkflowsListWorkflows.mockResolvedValue({
      workflows: [],
      count: 0,
      total: 0,
      authoring_phase: {
        phase: 'workflow_centric_active',
        label: 'Workflow-centric active phase',
        description: 'Workflow-centric analyst modeling is active for pools and drives runtime projection for new scheme authoring.',
        is_prerequisite_platform_phase: false,
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
    mockGetWorkflowsGetWorkflow.mockResolvedValue({
      workflow: {
        id: 'workflow-1',
        name: 'Decision-aware Workflow',
        description: 'authoring',
        workflow_type: 'complex',
        category: 'custom',
        dag_structure: { nodes: [], edges: [] },
        config: {},
        is_valid: true,
        is_active: true,
        is_system_managed: false,
        management_mode: 'user_authored',
        visibility_surface: 'workflow_library',
        read_only_reason: null,
        version_number: 1,
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
        success_rate: 0,
        avg_duration: 0,
      },
      executions: [],
    })
  })

  afterEach(async () => {
    await ensureNamespaces('ru', 'workflows')
    await changeLanguage('ru')
  })

  it('renders workflow authoring phase rollout banner', async () => {
    renderPage().renderDefault()

    await waitFor(() => {
      expect(screen.getByText('Workflow-centric active phase')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Workflow-centric analyst modeling is active for pools and drives runtime projection for new scheme authoring.')
    ).toBeInTheDocument()
    expect(screen.getByText('Workflow Scheme Library')).toBeInTheDocument()
    expect(
      screen.getByText('Reusable analyst-authored workflow definitions for pool distribution and publication.')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New Scheme/ })).toBeInTheDocument()
    expect(screen.getByText('Primary analyst surface: /workflows')).toBeInTheDocument()
    expect(
      screen.getByText('Compose analyst-authored schemes in /workflows. Use /templates for atomic operations and /decisions for versioned decision resources.')
    ).toBeInTheDocument()
    expect(screen.getByText('pool_distribution')).toBeInTheDocument()
    expect(screen.getByText('pool_publication')).toBeInTheDocument()
    expect(screen.getByText('Deferred: extensions.*')).toBeInTheDocument()
    expect(screen.getByText('Deferred: database.ib_user.*')).toBeInTheDocument()
    expect(screen.getByText('Follow-up: add-13-service-workflow-automation')).toBeInTheDocument()
  })

  it('preserves database_id in workflow links when compatibility context is provided', async () => {
    mockGetWorkflowsListWorkflows.mockResolvedValueOnce({
      workflows: [
        {
          id: 'workflow-1',
          name: 'Decision-aware Workflow',
          description: 'authoring',
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
      ],
      count: 1,
      total: 1,
      authoring_phase: null,
    })

    renderPage('/workflows?database_id=22222222-2222-2222-2222-222222222222').renderDefault()

    fireEvent.click(await screen.findByTestId('workflow-list-detail-open'))

    expect(mockNavigate).toHaveBeenCalledWith(
      '/workflows/workflow-1?database_id=22222222-2222-2222-2222-222222222222&returnTo=%2Fworkflows%3Fdatabase_id%3D22222222-2222-2222-2222-222222222222%26workflow%3Dworkflow-1%26detail%3D1'
    )
  })

  it('hydrates search, filters, and sort from URL-backed workspace state', async () => {
    mockGetWorkflowsListWorkflows.mockResolvedValue({
      workflows: [
        {
          id: 'workflow-1',
          name: 'Decision-aware Workflow',
          description: 'authoring',
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
      ],
      count: 1,
      total: 1,
      authoring_phase: null,
    })

    const params = new URLSearchParams()
    params.set('q', 'Decision')
    params.set('filters', JSON.stringify({ workflow_type: 'complex' }))
    params.set('sort', JSON.stringify({ key: 'updated_at', order: 'desc' }))
    params.set('workflow', 'workflow-1')
    params.set('detail', '1')

    renderPage(`/workflows?${params.toString()}`).renderDefault()

    await waitFor(() => {
      expect(mockGetWorkflowsListWorkflows).toHaveBeenCalledWith(expect.objectContaining({
        search: 'Decision',
        filters: JSON.stringify({
          workflow_type: {
            op: 'contains',
            value: 'complex',
          },
        }),
        sort: JSON.stringify({
          key: 'updated_at',
          order: 'desc',
        }),
      }))
    })

    expect(await screen.findByTestId('workflow-list-catalog-item-workflow-1')).toBeInTheDocument()
  })

  it('restores selected workflow detail from the route state', async () => {
    mockGetWorkflowsListWorkflows.mockResolvedValueOnce({
      workflows: [
        {
          id: 'workflow-1',
          name: 'Decision-aware Workflow',
          description: 'authoring',
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
      ],
      count: 1,
      total: 1,
      authoring_phase: null,
    })

    renderPage('/workflows?workflow=workflow-1&detail=1').renderDefault()

    expect(await screen.findByTestId('workflow-list-selected-id')).toHaveTextContent('workflow-1')
    expect(await screen.findByTestId('workflow-list-selected-dag')).toHaveTextContent('"nodes"')
  })

  it('preserves filters and sort in designer handoff before table hydration settles', async () => {
    mockGetWorkflowsListWorkflows.mockResolvedValue({
      workflows: [
        {
          id: 'workflow-1',
          name: 'Decision-aware Workflow',
          description: 'authoring',
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
      ],
      count: 1,
      total: 1,
      authoring_phase: null,
    })

    const params = new URLSearchParams()
    params.set('q', 'Decision')
    params.set('filters', JSON.stringify({ workflow_type: 'complex' }))
    params.set('sort', JSON.stringify({ key: 'updated_at', order: 'desc' }))
    params.set('workflow', 'workflow-1')
    params.set('detail', '1')

    renderPage(`/workflows?${params.toString()}`).renderDefault()

    fireEvent.click(await screen.findByTestId('workflow-list-detail-open'))

    expect(mockNavigate).toHaveBeenCalledWith(
      `/workflows/workflow-1?returnTo=${encodeURIComponent(`/workflows?${params.toString()}`)}`
    )
  })

  it('does not strip route-backed filters and sort during strict-mode mount', async () => {
    mockGetWorkflowsListWorkflows.mockResolvedValue({
      workflows: [
        {
          id: 'workflow-1',
          name: 'Decision-aware Workflow',
          description: 'authoring',
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
      ],
      count: 1,
      total: 1,
      authoring_phase: null,
    })

    const params = new URLSearchParams()
    params.set('q', 'Services')
    params.set('filters', JSON.stringify({ workflow_type: 'complex' }))
    params.set('sort', JSON.stringify({ key: 'updated_at', order: 'desc' }))
    params.set('workflow', 'workflow-1')
    params.set('detail', '1')

    renderPage(`/workflows?${params.toString()}`).renderStrict()

    await waitFor(() => {
      expect(screen.getByTestId('workflow-list-route-search')).toHaveTextContent(`?${params.toString()}`)
    })

    expect(mockGetWorkflowsListWorkflows).toHaveBeenCalledWith(expect.objectContaining({
      search: 'Services',
      filters: JSON.stringify({
        workflow_type: {
          op: 'contains',
          value: 'complex',
        },
      }),
      sort: JSON.stringify({
        key: 'updated_at',
        order: 'desc',
      }),
    }))
  })
})
