import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import type { PoolTopologyTemplate } from '../../../api/intercompanyPools'
import { PoolTopologyTemplatesPage } from '../PoolTopologyTemplatesPage'

const mockUsePoolTopologyTemplates = vi.fn()
const mockUseCreatePoolTopologyTemplate = vi.fn()
const mockUseRevisePoolTopologyTemplate = vi.fn()

vi.mock('../../../api/queries/poolTopologyTemplates', () => ({
  usePoolTopologyTemplates: (...args: unknown[]) => mockUsePoolTopologyTemplates(...args),
  useCreatePoolTopologyTemplate: (...args: unknown[]) => mockUseCreatePoolTopologyTemplate(...args),
  useRevisePoolTopologyTemplate: (...args: unknown[]) => mockUseRevisePoolTopologyTemplate(...args),
}))

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

function buildTopologyTemplate(overrides: Partial<PoolTopologyTemplate> = {}): PoolTopologyTemplate {
  const latestRevision = {
    topology_template_revision_id: 'template-revision-r2',
    topology_template_id: 'template-1',
    revision_number: 2,
    nodes: [
      {
        slot_key: 'root',
        label: 'Root',
        is_root: true,
        metadata: {},
      },
      {
        slot_key: 'leaf',
        label: 'Leaf',
        is_root: false,
        metadata: {},
      },
    ],
    edges: [
      {
        parent_slot_key: 'root',
        child_slot_key: 'leaf',
        weight: '1',
        min_amount: null,
        max_amount: null,
        document_policy_key: 'sale',
        metadata: {},
      },
    ],
    metadata: {},
    created_at: '2026-03-23T10:00:00Z',
  }

  return {
    topology_template_id: 'template-1',
    code: 'top-down-template',
    name: 'Top Down Template',
    description: 'Reusable topology for top-down flows.',
    status: 'active',
    metadata: {},
    latest_revision_number: 2,
    latest_revision: latestRevision,
    revisions: [
      latestRevision,
      {
        ...latestRevision,
        topology_template_revision_id: 'template-revision-r1',
        revision_number: 1,
        created_at: '2026-03-22T10:00:00Z',
      },
    ],
    created_at: '2026-03-22T09:00:00Z',
    updated_at: '2026-03-23T10:00:00Z',
    ...overrides,
  }
}

const topologyTemplates = [
  buildTopologyTemplate(),
  buildTopologyTemplate({
    topology_template_id: 'template-2',
    code: 'branching-template',
    name: 'Branching Template',
    description: 'Reusable topology for branching flows.',
  }),
]

function renderPage(path = '/pools/topology-templates') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
        <AntApp>
          <PoolTopologyTemplatesPage />
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-probe">{`${location.pathname}${location.search}`}</div>
}

function renderPageWithRoutes(path = '/pools/topology-templates') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
        <AntApp>
          <Routes>
            <Route path="/pools/topology-templates" element={<PoolTopologyTemplatesPage />} />
            <Route path="/pools/catalog" element={<LocationProbe />} />
          </Routes>
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PoolTopologyTemplatesPage', () => {
  beforeEach(() => {
    mockUsePoolTopologyTemplates.mockReset()
    mockUseCreatePoolTopologyTemplate.mockReset()
    mockUseRevisePoolTopologyTemplate.mockReset()

    mockUsePoolTopologyTemplates.mockReturnValue({
      data: topologyTemplates,
      isLoading: false,
      isError: false,
      error: null,
    })
    mockUseCreatePoolTopologyTemplate.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({
        topology_template: buildTopologyTemplate({
          topology_template_id: 'template-new',
          code: 'new-template',
          name: 'New Template',
        }),
      }),
    })
    mockUseRevisePoolTopologyTemplate.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({
        topology_template: buildTopologyTemplate(),
      }),
    })
  })

  it('renders a dedicated reusable topology template catalog with return handoff context', async () => {
    renderPage('/pools/topology-templates?template=template-1&detail=1&return_pool_id=pool-1&return_tab=topology&return_date=2026-03-23')

    expect(await screen.findByRole('heading', { name: 'Topology Templates' })).toBeInTheDocument()
    expect(screen.getByText(/Reusable producer workspace for authoring topology templates and publishing immutable revisions./i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Return to pool topology' })).toBeInTheDocument()
    expect(screen.getByTestId('pool-topology-templates-selected-code')).toHaveTextContent('top-down-template')
    expect(screen.getByTestId('pool-topology-templates-status')).toHaveTextContent('active')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeEnabled()
    expect(screen.getByText('Branching Template')).toBeInTheDocument()
  })

  it('creates a reusable topology template from the dedicated catalog drawer', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      topology_template: buildTopologyTemplate({
        topology_template_id: 'template-new',
        code: 'new-template',
        name: 'New Template',
      }),
    })
    mockUseCreatePoolTopologyTemplate.mockReturnValue({
      isPending: false,
      mutateAsync,
    })

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Create template' }))

    fireEvent.change(screen.getByTestId('pool-topology-templates-create-code'), {
      target: { value: 'new-template' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-name'), {
      target: { value: 'New Template' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-description'), {
      target: { value: 'Reusable topology authoring surface' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-node-slot-key-0'), {
      target: { value: 'root' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-node-label-0'), {
      target: { value: 'Root' },
    })
    fireEvent.click(screen.getByTestId('pool-topology-templates-create-node-root-0'))
    fireEvent.click(screen.getByTestId('pool-topology-templates-create-add-node'))
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-node-slot-key-1'), {
      target: { value: 'leaf' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-node-label-1'), {
      target: { value: 'Leaf' },
    })
    fireEvent.click(screen.getByTestId('pool-topology-templates-create-add-edge'))
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-edge-parent-slot-key-0'), {
      target: { value: 'root' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-edge-child-slot-key-0'), {
      target: { value: 'leaf' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-edge-weight-0'), {
      target: { value: '1' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-create-edge-document-policy-key-0'), {
      target: { value: 'sale' },
    })

    fireEvent.click(screen.getByTestId('pool-topology-templates-create-submit'))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        code: 'new-template',
        name: 'New Template',
        description: 'Reusable topology authoring surface',
        metadata: {},
        revision: {
          nodes: [
            {
              slot_key: 'root',
              label: 'Root',
              is_root: true,
              metadata: {},
            },
            {
              slot_key: 'leaf',
              label: 'Leaf',
              is_root: false,
              metadata: {},
            },
          ],
          edges: [
            {
              parent_slot_key: 'root',
              child_slot_key: 'leaf',
              weight: '1',
              min_amount: null,
              max_amount: null,
              document_policy_key: 'sale',
              metadata: {},
            },
          ],
          metadata: {},
        },
      })
    })
  })

  it('publishes a new immutable revision for the selected topology template', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      topology_template: buildTopologyTemplate(),
    })
    mockUseRevisePoolTopologyTemplate.mockReturnValue({
      isPending: false,
      mutateAsync,
    })

    renderPage('/pools/topology-templates?template=template-1&detail=1')

    fireEvent.click(await screen.findByRole('button', { name: 'Publish new revision' }))
    fireEvent.change(screen.getByTestId('pool-topology-templates-revise-node-label-0'), {
      target: { value: 'Updated Root' },
    })
    fireEvent.change(screen.getByTestId('pool-topology-templates-revise-edge-document-policy-key-0'), {
      target: { value: 'receipt' },
    })

    fireEvent.click(screen.getByTestId('pool-topology-templates-revise-submit'))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        topologyTemplateId: 'template-1',
        request: {
          revision: {
            nodes: [
              {
                slot_key: 'root',
                label: 'Updated Root',
                is_root: true,
                metadata: {},
              },
              {
                slot_key: 'leaf',
                label: 'Leaf',
                is_root: false,
                metadata: {},
              },
            ],
            edges: [
              {
                parent_slot_key: 'root',
                child_slot_key: 'leaf',
                weight: '1',
                min_amount: null,
                max_amount: null,
                document_policy_key: 'receipt',
                metadata: {},
              },
            ],
            metadata: {},
          },
        },
      })
    })
  })

  it('returns to the originating pool topology context without losing the selected pool', async () => {
    const user = userEvent.setup()
    renderPageWithRoutes('/pools/topology-templates?template=template-1&detail=1&return_pool_id=pool-1&return_tab=topology&return_date=2026-03-23')

    await user.click(await screen.findByRole('button', { name: 'Return to pool topology' }))

    expect(await screen.findByTestId('location-probe')).toHaveTextContent(
      '/pools/catalog?pool_id=pool-1&tab=topology&date=2026-03-23'
    )
  })
})
