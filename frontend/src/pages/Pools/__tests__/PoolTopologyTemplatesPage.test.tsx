import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
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

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const { createPoolReusableAuthoringAntdTestDouble } = await import('./poolReusableAuthoringAntdTestDouble')
  return createPoolReusableAuthoringAntdTestDouble(actual)
})

vi.mock('../../../components/platform', async () => {
  const actual = await vi.importActual<typeof import('../../../components/platform')>(
    '../../../components/platform'
  )

  const formatStatus = (value: ReactNode) => {
    if (typeof value !== 'string') {
      return value
    }
    return value
      .split('_')
      .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1)}` : part))
      .join(' ')
  }

  return {
    ...actual,
    WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
      <div>
        {header}
        {children}
      </div>
    ),
    PageHeader: ({
      title,
      subtitle,
      actions,
    }: {
      title: ReactNode
      subtitle?: ReactNode
      actions?: ReactNode
    }) => (
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
        {actions}
      </div>
    ),
    MasterDetailShell: ({
      list,
      detail,
      detailOpen,
      detailDrawerTitle,
      onCloseDetail,
    }: {
      list: ReactNode
      detail: ReactNode
      detailOpen?: boolean
      detailDrawerTitle?: ReactNode
      onCloseDetail?: () => void
    }) => (
      <div>
        <section>{list}</section>
        <section data-detail-open={detailOpen ? 'true' : 'false'}>
          {detailDrawerTitle ? <h2>{detailDrawerTitle}</h2> : null}
          {detailOpen && onCloseDetail ? (
            <button type="button" onClick={onCloseDetail}>
              Close detail
            </button>
          ) : null}
          {detail}
        </section>
      </div>
    ),
    EntityList: ({
      title,
      extra,
      toolbar,
      error,
      loading,
      emptyDescription,
      dataSource,
      renderItem,
    }: {
      title?: ReactNode
      extra?: ReactNode
      toolbar?: ReactNode
      error?: ReactNode
      loading?: boolean
      emptyDescription?: ReactNode
      dataSource?: Array<Record<string, unknown>>
      renderItem: (item: Record<string, unknown>) => ReactNode
    }) => (
      <section>
        {title ? <h3>{title}</h3> : null}
        {extra}
        {toolbar}
        {error ? error : loading ? <div>Loading</div> : (dataSource?.length ?? 0) === 0 ? <div>{emptyDescription}</div> : (
          (dataSource ?? []).map((item, index) => (
            <div key={String(item.key ?? item.id ?? index)}>
              {renderItem(item)}
            </div>
          ))
        )}
      </section>
    ),
    EntityDetails: ({
      title,
      extra,
      error,
      loading,
      empty,
      emptyDescription,
      children,
    }: {
      title?: ReactNode
      extra?: ReactNode
      error?: ReactNode
      loading?: boolean
      empty?: boolean
      emptyDescription?: ReactNode
      children?: ReactNode
    }) => (
      <section>
        {title ? <h3>{title}</h3> : null}
        {extra}
        {error ? error : loading ? <div>Loading</div> : empty ? emptyDescription : children}
      </section>
    ),
    StatusBadge: ({
      status,
      label,
    }: {
      status?: ReactNode
      label?: ReactNode
    }) => <span>{label ?? formatStatus(status ?? '')}</span>,
    JsonBlock: ({ title, value }: { title?: ReactNode; value: unknown }) => (
      <section>
        {title ? <h4>{title}</h4> : null}
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </section>
    ),
    DrawerFormShell: ({
      open,
      onSubmit,
      title,
      subtitle,
      onClose,
      submitText,
      confirmLoading,
      submitDisabled,
      extra,
      submitButtonTestId,
      drawerTestId,
      children,
    }: {
      open: boolean
      onSubmit?: () => void | Promise<void>
      title?: ReactNode
      subtitle?: ReactNode
      onClose?: () => void
      submitText?: ReactNode
      confirmLoading?: boolean
      submitDisabled?: boolean
      extra?: ReactNode
      submitButtonTestId?: string
      drawerTestId?: string
      children?: ReactNode
    }) => (
      open ? (
        <section data-testid={drawerTestId}>
          {title ? <h2>{title}</h2> : null}
          {subtitle ? <p>{subtitle}</p> : null}
          {extra}
          {onSubmit ? (
            <button
              type="button"
              onClick={() => {
                void onSubmit()
              }}
              disabled={Boolean(confirmLoading) || Boolean(submitDisabled)}
              data-testid={submitButtonTestId}
            >
              {submitText ?? 'Save'}
            </button>
          ) : null}
          {onClose ? (
            <button type="button" onClick={onClose}>
              Close
            </button>
          ) : null}
          {children}
        </section>
      ) : null
    ),
  }
})

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

function buildTopologyTemplate(overrides: Partial<PoolTopologyTemplate> = {}): PoolTopologyTemplate {
  const latestRevision = {
    topology_template_revision_id: 'template-revision-r3',
    topology_template_id: 'template-1',
    revision_number: 3,
    nodes: [
      {
        slot_key: 'root',
        label: 'Root',
        is_root: true,
        metadata: {},
      },
      {
        slot_key: 'organization_1',
        label: 'Organization 1',
        is_root: false,
        metadata: {},
      },
      {
        slot_key: 'organization_2',
        label: 'Organization 2',
        is_root: false,
        metadata: {},
      },
      {
        slot_key: 'organization_3',
        label: 'Organization 3',
        is_root: false,
        metadata: {},
      },
      {
        slot_key: 'organization_4',
        label: 'Organization 4',
        is_root: false,
        metadata: {},
      },
    ],
    edges: [
      {
        parent_slot_key: 'root',
        child_slot_key: 'organization_1',
        weight: '1',
        min_amount: null,
        max_amount: null,
        document_policy_key: 'sale',
        metadata: {},
      },
      {
        parent_slot_key: 'organization_1',
        child_slot_key: 'organization_2',
        weight: '1',
        min_amount: null,
        max_amount: null,
        document_policy_key: 'receipt_internal',
        metadata: {},
      },
      {
        parent_slot_key: 'organization_2',
        child_slot_key: 'organization_3',
        weight: '1',
        min_amount: null,
        max_amount: null,
        document_policy_key: 'receipt_leaf',
        metadata: {},
      },
      {
        parent_slot_key: 'organization_2',
        child_slot_key: 'organization_4',
        weight: '1',
        min_amount: null,
        max_amount: null,
        document_policy_key: 'receipt_leaf',
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
    latest_revision_number: 3,
    latest_revision: latestRevision,
    revisions: [
      latestRevision,
      {
        ...latestRevision,
        topology_template_revision_id: 'template-revision-r2',
        revision_number: 2,
        edges: latestRevision.edges.map((edge) => ({
          ...edge,
          document_policy_key: 'receipt',
        })),
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
        <ConfigProvider theme={{ token: { motion: false } }} wave={{ disabled: true }}>
          <AntApp>
            <PoolTopologyTemplatesPage />
          </AntApp>
        </ConfigProvider>
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
        <ConfigProvider theme={{ token: { motion: false } }} wave={{ disabled: true }}>
          <AntApp>
            <Routes>
              <Route path="/pools/topology-templates" element={<PoolTopologyTemplatesPage />} />
              <Route path="/pools/catalog" element={<LocationProbe />} />
            </Routes>
          </AntApp>
        </ConfigProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PoolTopologyTemplatesPage', () => {
  beforeAll(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'pools')
  })

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

  afterAll(async () => {
    await ensureNamespaces('ru', 'pools')
    await changeLanguage('ru')
  })

  it('renders a dedicated reusable topology template catalog with return handoff context', async () => {
    renderPage('/pools/topology-templates?template=template-1&detail=1&return_pool_id=pool-1&return_tab=topology&return_date=2026-03-23')

    expect(await screen.findByRole('heading', { name: 'Topology Templates' })).toBeInTheDocument()
    expect(screen.getByText(/Reusable producer workspace for authoring topology templates and publishing immutable revisions./i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Return to pool topology' })).toBeInTheDocument()
    expect(screen.getByTestId('pool-topology-templates-selected-code')).toHaveTextContent('top-down-template')
    expect(screen.getByTestId('pool-topology-templates-status')).toHaveTextContent('Active')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeEnabled()
    expect(screen.getByText('Branching Template')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Revision' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Nodes' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Edges' })).toBeInTheDocument()
    const revisionsTable = screen.getAllByRole('table').find((table) => (
      within(table).queryByRole('columnheader', { name: 'Created at' }) !== null
    ))
    expect(revisionsTable).toBeDefined()
    expect(within(revisionsTable as HTMLElement).getByRole('cell', { name: 'r3' })).toBeInTheDocument()
    expect(within(revisionsTable as HTMLElement).getByRole('cell', { name: 'r2' })).toBeInTheDocument()
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

  it('shows empty-state guidance when no topology templates are available', async () => {
    mockUsePoolTopologyTemplates.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    })

    renderPage()

    expect(await screen.findByText('No topology templates found.')).toBeInTheDocument()
    expect(screen.getByText('Select a reusable topology template from the catalog.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create template' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Return to pool topology' })).not.toBeInTheDocument()
  })

  it('surfaces catalog load errors on the dedicated page without collapsing into an empty state', async () => {
    mockUsePoolTopologyTemplates.mockReturnValue({
      data: [],
      isLoading: false,
      isError: true,
      error: {
        response: {
          data: {
            detail: 'Topology catalog unavailable.',
          },
        },
      },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getAllByText('Topology catalog unavailable.').length).toBeGreaterThanOrEqual(2)
    })
    expect(screen.queryByText('No topology templates found.')).not.toBeInTheDocument()
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
    const latestRevision = buildTopologyTemplate().latest_revision
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
            nodes: latestRevision.nodes.map((node) => (
              node.slot_key === 'root'
                ? {
                  ...node,
                  label: 'Updated Root',
                }
                : node
            )),
            edges: latestRevision.edges.map((edge, index) => (
              index === 0
                ? {
                  ...edge,
                  document_policy_key: 'receipt',
                }
                : edge
            )),
            metadata: {},
          },
        },
      })
    })
  })

  it('keeps the revise drawer open and surfaces mutation errors when publishing a revision fails', async () => {
    const mutateAsync = vi.fn().mockRejectedValue({
      response: {
        data: {
          detail: 'Topology revision failed.',
        },
      },
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
    fireEvent.click(screen.getByTestId('pool-topology-templates-revise-submit'))

    await waitFor(() => {
      expect(screen.getByText('Topology revision failed.')).toBeInTheDocument()
    })

    expect(screen.getByTestId('pool-topology-templates-revise-node-label-0')).toHaveValue('Updated Root')
    expect(mutateAsync).toHaveBeenCalledTimes(1)
  })

  it('returns to the originating pool topology context without losing the selected pool', async () => {
    renderPageWithRoutes('/pools/topology-templates?template=template-1&detail=1&return_pool_id=pool-1&return_tab=topology&return_date=2026-03-23')

    fireEvent.click(await screen.findByRole('button', { name: 'Return to pool topology' }))

    expect(await screen.findByTestId('location-probe')).toHaveTextContent(
      '/pools/catalog?pool_id=pool-1&tab=topology&date=2026-03-23'
    )
  })
})
