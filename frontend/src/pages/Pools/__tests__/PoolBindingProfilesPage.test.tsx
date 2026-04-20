import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import type { BindingProfileDetail } from '../../../api/generated/model/bindingProfileDetail'
import type { BindingProfileRevision } from '../../../api/generated/model/bindingProfileRevision'
import type { BindingProfileSummary } from '../../../api/generated/model/bindingProfileSummary'
import type { BindingProfileUsageSummary } from '../../../api/generated/model/bindingProfileUsageSummary'
import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import { HEAVY_ROUTE_TEST_TIMEOUT_MS } from '../../../test/timeouts'
import type { AvailableDecisionRevision, AvailableWorkflowRevision } from '../../../types/workflow'
import { PoolBindingProfilesPage } from '../PoolBindingProfilesPage'

const mockUseBindingProfiles = vi.fn()
const mockUseBindingProfileDetail = vi.fn()
const mockUseCreateBindingProfile = vi.fn()
const mockUseReviseBindingProfile = vi.fn()
const mockUseDeactivateBindingProfile = vi.fn()
const mockUseAuthoringReferences = vi.fn()

vi.mock('../../../api/queries/poolBindingProfiles', () => ({
  useBindingProfiles: (...args: unknown[]) => mockUseBindingProfiles(...args),
  useBindingProfileDetail: (...args: unknown[]) => mockUseBindingProfileDetail(...args),
  useCreateBindingProfile: (...args: unknown[]) => mockUseCreateBindingProfile(...args),
  useReviseBindingProfile: (...args: unknown[]) => mockUseReviseBindingProfile(...args),
  useDeactivateBindingProfile: (...args: unknown[]) => mockUseDeactivateBindingProfile(...args),
}))

vi.mock('../../../api/queries/authoringReferences', () => ({
  useAuthoringReferences: (...args: unknown[]) => mockUseAuthoringReferences(...args),
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
  const { useNavigate } = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')

  const readValue = (record: Record<string, unknown>, dataIndex: unknown) => {
    if (Array.isArray(dataIndex)) {
      return dataIndex.reduce<unknown>((current, key) => (
        current && typeof current === 'object' ? (current as Record<string, unknown>)[String(key)] : undefined
      ), record)
    }
    if (typeof dataIndex === 'string') {
      return record[dataIndex]
    }
    return undefined
  }

  const formatStatus = (value: ReactNode) => {
    if (typeof value !== 'string') {
      return value
    }
    return value
      .split('_')
      .map((part) => part ? `${part[0].toUpperCase()}${part.slice(1)}` : part)
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
        {error}
        {loading ? <div>Loading</div> : null}
        {empty ? emptyDescription : children}
      </section>
    ),
    EntityTable: ({
      title,
      extra,
      toolbar,
      error,
      loading,
      emptyDescription,
      dataSource,
      columns,
      rowKey,
      onRow,
      rowClassName,
    }: {
      title?: ReactNode
      extra?: ReactNode
      toolbar?: ReactNode
      error?: ReactNode
      loading?: boolean
      emptyDescription?: ReactNode
      dataSource?: Array<Record<string, unknown>>
      columns?: Array<{
        title?: ReactNode
        key?: string
        dataIndex?: unknown
        render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
      }>
      rowKey?: string | ((record: Record<string, unknown>) => string)
      onRow?: (record: Record<string, unknown>) => { onClick?: () => void; style?: Record<string, unknown> }
      rowClassName?: (record: Record<string, unknown>) => string
    }) => {
      const rows = dataSource ?? []
      return (
        <section>
          {title ? <h3>{title}</h3> : null}
          {extra}
          {toolbar}
          {error}
          {loading ? <div>Loading</div> : null}
          {!loading && rows.length === 0 ? <div>{emptyDescription}</div> : null}
          {rows.length > 0 ? (
            <table>
              <thead>
                <tr>
                  {(columns ?? []).map((column, columnIndex) => (
                    <th key={column.key ?? `header-${columnIndex}`}>{column.title}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((record, rowIndex) => {
                  const resolvedRowKey = typeof rowKey === 'function'
                    ? rowKey(record)
                    : typeof rowKey === 'string'
                      ? String(record[rowKey])
                      : String(record.id ?? rowIndex)
                  const rowProps = onRow?.(record) ?? {}
                  return (
                    <tr
                      key={resolvedRowKey}
                      data-testid={`entity-table-row-${resolvedRowKey}`}
                      className={rowClassName?.(record)}
                      onClick={rowProps.onClick}
                    >
                      {(columns ?? []).map((column, columnIndex) => {
                        const value = readValue(record, column.dataIndex)
                        const content = column.render
                          ? column.render(value, record, rowIndex)
                          : (
                            value == null
                              ? ''
                              : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
                                ? String(value)
                                : JSON.stringify(value)
                          )
                        return <td key={column.key ?? `${resolvedRowKey}-${columnIndex}`}>{content}</td>
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : null}
        </section>
      )
    },
    StatusBadge: ({
      status,
      label,
    }: {
      status?: ReactNode
      label?: ReactNode
    }) => <span>{label ?? formatStatus(status ?? '')}</span>,
    RouteButton: ({
      to,
      children,
      disabled,
    }: {
      to: string
      children: ReactNode
      disabled?: boolean
    }) => {
      const navigate = useNavigate()
      return (
        <button type="button" disabled={disabled} onClick={() => navigate(to)}>
          {children}
        </button>
      )
    },
    ModalFormShell: ({
      open,
      title,
      onClose,
      onSubmit,
      submitText,
      confirmLoading,
      submitButtonTestId,
      children,
    }: {
      open: boolean
      title?: ReactNode
      onClose?: () => void
      onSubmit?: () => void
      submitText?: ReactNode
      confirmLoading?: boolean
      submitButtonTestId?: string
      children?: ReactNode
    }) => (
      open ? (
        <section>
          {title ? <h2>{title}</h2> : null}
          {children}
          {onClose ? (
            <button type="button" onClick={onClose}>
              Close
            </button>
          ) : null}
          {onSubmit ? (
            <button
              type="button"
              data-testid={submitButtonTestId}
              disabled={confirmLoading}
              onClick={onSubmit}
            >
              {submitText}
            </button>
          ) : null}
        </section>
      ) : null
    ),
    JsonBlock: ({ title, value }: { title?: ReactNode; value: unknown }) => (
      <section>
        {title ? <h4>{title}</h4> : null}
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </section>
    ),
  }
})

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

function buildRevision(overrides: Partial<BindingProfileRevision> = {}): BindingProfileRevision {
  return {
    binding_profile_revision_id: 'bp-rev-services-r2',
    binding_profile_id: 'bp-services',
    revision_number: 2,
    workflow: {
      workflow_definition_key: 'services-publication',
      workflow_revision_id: 'wf-services-r2',
      workflow_revision: 4,
      workflow_name: 'services_publication',
    },
    decisions: [
      {
        decision_table_id: 'decision-1',
        decision_key: 'document_policy',
        slot_key: 'document_policy',
        decision_revision: 3,
      },
    ],
    parameters: {
      publication_variant: 'full',
    },
    role_mapping: {
      initiator: 'finance',
    },
    metadata: {
      source: 'manual',
    },
    topology_template_compatibility: {
      status: 'compatible',
      topology_aware_ready: true,
      covered_slot_keys: ['document_policy'],
      diagnostics: [],
    },
    created_by: 'analyst',
    created_at: '2026-03-16T12:00:00Z',
    ...overrides,
  }
}

function buildSummaryFromDetail(detail: BindingProfileDetail): BindingProfileSummary {
  return {
    binding_profile_id: detail.binding_profile_id,
    code: detail.code,
    name: detail.name,
    description: detail.description,
    status: detail.status,
    latest_revision_number: detail.latest_revision_number,
    latest_revision: detail.latest_revision,
    created_by: detail.created_by,
    updated_by: detail.updated_by,
    deactivated_by: detail.deactivated_by,
    deactivated_at: detail.deactivated_at,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  }
}

function buildUsageSummary(overrides: Partial<BindingProfileUsageSummary> = {}): BindingProfileUsageSummary {
  return {
    attachment_count: 0,
    revision_summary: [],
    attachments: [],
    ...overrides,
  }
}

const activeDetail: BindingProfileDetail = {
  binding_profile_id: 'bp-services',
  code: 'services-publication',
  name: 'Services Publication',
  description: 'Reusable scheme for top-down publication.',
  status: 'active',
  latest_revision_number: 2,
  latest_revision: buildRevision(),
  revisions: [
    buildRevision(),
    buildRevision({
      binding_profile_revision_id: 'bp-rev-services-r1',
      revision_number: 1,
      workflow: {
        workflow_definition_key: 'services-publication',
        workflow_revision_id: 'wf-services-r1',
        workflow_revision: 3,
        workflow_name: 'services_publication',
      },
      created_at: '2026-03-15T08:00:00Z',
    }),
  ],
  usage_summary: buildUsageSummary(),
  created_by: 'analyst',
  updated_by: 'analyst',
  deactivated_by: undefined,
  deactivated_at: null,
  created_at: '2026-03-15T08:00:00Z',
  updated_at: '2026-03-16T12:00:00Z',
}

const deactivatedDetail: BindingProfileDetail = {
  binding_profile_id: 'bp-legacy',
  code: 'legacy-archive',
  name: 'Legacy Archive',
  description: 'Old profile kept only for pinned attachments.',
  status: 'deactivated',
  latest_revision_number: 1,
  latest_revision: buildRevision({
    binding_profile_id: 'bp-legacy',
    binding_profile_revision_id: 'bp-rev-legacy-r1',
    revision_number: 1,
    workflow: {
      workflow_definition_key: 'legacy-publication',
      workflow_revision_id: 'wf-legacy-r1',
      workflow_revision: 1,
      workflow_name: 'legacy_publication',
    },
  }),
  revisions: [
    buildRevision({
      binding_profile_id: 'bp-legacy',
      binding_profile_revision_id: 'bp-rev-legacy-r1',
      revision_number: 1,
      workflow: {
        workflow_definition_key: 'legacy-publication',
        workflow_revision_id: 'wf-legacy-r1',
        workflow_revision: 1,
        workflow_name: 'legacy_publication',
      },
    }),
  ],
  usage_summary: buildUsageSummary(),
  created_by: 'analyst',
  updated_by: 'analyst',
  deactivated_by: 'staff',
  deactivated_at: '2026-03-16T16:00:00Z',
  created_at: '2026-03-10T08:00:00Z',
  updated_at: '2026-03-16T16:00:00Z',
}

const profileDetails: Record<string, BindingProfileDetail> = {
  [activeDetail.binding_profile_id]: activeDetail,
  [deactivatedDetail.binding_profile_id]: deactivatedDetail,
}

const bindingProfiles = [
  buildSummaryFromDetail(activeDetail),
  buildSummaryFromDetail(deactivatedDetail),
]

const availableWorkflows: AvailableWorkflowRevision[] = [
  {
    id: 'workflow-revision-4',
    name: 'Services Publication',
    workflowDefinitionKey: 'services-publication',
    workflowRevisionId: 'wf-services-r2',
    workflowRevision: 4,
  },
  {
    id: 'workflow-revision-5',
    name: 'Services Publication',
    workflowDefinitionKey: 'services-publication',
    workflowRevisionId: 'wf-services-r5',
    workflowRevision: 5,
  },
  {
    id: 'workflow-revision-6',
    name: 'New Services Publication',
    workflowDefinitionKey: 'services-publication',
    workflowRevisionId: 'wf-new-r1',
    workflowRevision: 6,
  },
]

const availableDecisions: AvailableDecisionRevision[] = [
  {
    id: 'decision-version-3',
    name: 'Services Policy',
    decisionTableId: 'decision-1',
    decisionKey: 'document_policy',
    decisionRevision: 3,
  },
  {
    id: 'decision-version-4',
    name: 'Fallback Policy',
    decisionTableId: 'decision-2',
    decisionKey: 'document_policy',
    decisionRevision: 4,
  },
]

function openSelect(testId: string) {
  const select = screen.getByTestId(testId)
  const selector = select.querySelector('.ant-select-selector')
  expect(selector).toBeTruthy()
  fireEvent.mouseDown(selector as Element)
}

function renderPage(path = '/pools/execution-packs') {
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
            <PoolBindingProfilesPage />
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

function renderPageWithRoutes(path = '/pools/execution-packs') {
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
              <Route path="/pools/execution-packs" element={<PoolBindingProfilesPage />} />
              <Route path="/pools/catalog" element={<LocationProbe />} />
            </Routes>
          </AntApp>
        </ConfigProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PoolBindingProfilesPage', () => {
  beforeAll(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'pools')
  })

  beforeEach(() => {
    mockUseBindingProfiles.mockReset()
    mockUseBindingProfileDetail.mockReset()
    mockUseCreateBindingProfile.mockReset()
    mockUseReviseBindingProfile.mockReset()
    mockUseDeactivateBindingProfile.mockReset()
    mockUseAuthoringReferences.mockReset()

    mockUseBindingProfiles.mockReturnValue({
      data: {
        binding_profiles: bindingProfiles,
        count: bindingProfiles.length,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    mockUseBindingProfileDetail.mockImplementation((bindingProfileId?: string) => ({
      data: bindingProfileId ? { binding_profile: profileDetails[bindingProfileId] } : undefined,
      isLoading: false,
      isError: false,
      error: null,
    }))
    mockUseCreateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ binding_profile: activeDetail }),
    })
    mockUseReviseBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ binding_profile: activeDetail }),
    })
    mockUseDeactivateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue({ binding_profile: deactivatedDetail }),
    })
    mockUseAuthoringReferences.mockReturnValue({
      data: {
        availableWorkflows,
        availableDecisions,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
  })

  afterAll(async () => {
    await ensureNamespaces('ru', 'pools')
    await changeLanguage('ru')
  })

  it('renders a dedicated reusable profile catalog with list and detail states on a separate authoring surface', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Execution Packs' })).toBeInTheDocument()
    expect(screen.getByText(/Reusable execution-pack workspace for selecting an execution pack, checking where it is used, and publishing the next revision./i)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Open attachment workspace' })).toHaveLength(2)
    expect(screen.getAllByText('services-publication').length).toBeGreaterThan(0)
    expect(screen.getByText('legacy-archive')).toBeInTheDocument()

    expect(screen.getByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('services-publication')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeEnabled()
    expect(screen.getByRole('heading', { name: 'Where this execution pack is used', level: 3 })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Opaque pin' })).not.toBeInTheDocument()
    expect(screen.queryByText('Latest immutable revision')).not.toBeInTheDocument()
    expect(screen.queryByText('Workflow definition key')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Advanced payload and immutable pins/i }))
    expect(await screen.findByText('Latest immutable revision')).toBeInTheDocument()
    expect(screen.getByTestId('pool-binding-profiles-latest-revision-id')).toHaveTextContent('bp-rev-services-r2')
    expect(screen.getByRole('columnheader', { name: 'Opaque pin' })).toBeInTheDocument()
    expect(await screen.findByText('Workflow definition key')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open execution pack legacy-archive' }))

    expect(await screen.findByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('legacy-archive')
    expect(screen.getByTestId('pool-binding-profiles-status')).toHaveTextContent('Deactivated')
    expect(screen.getByRole('button', { name: 'Publish new revision' })).toBeDisabled()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('restores search and selected profile from query params and labels the catalog search', async () => {
    renderPage('/pools/execution-packs?q=legacy&profile=bp-legacy&detail=1')

    expect(await screen.findByRole('heading', { name: 'Execution Packs' })).toBeInTheDocument()
    expect(screen.getByLabelText('Search execution packs')).toHaveValue('legacy')
    expect(screen.queryByText('services-publication')).not.toBeInTheDocument()
    expect(screen.getByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('legacy-archive')
  })

  it('keeps filtered catalog context coherent when the selected profile is outside the active search', async () => {
    renderPage('/pools/execution-packs?q=legacy&profile=bp-services&detail=1')

    expect(await screen.findByRole('heading', { name: 'Execution Packs' })).toBeInTheDocument()
    expect(screen.getByLabelText('Search execution packs')).toHaveValue('legacy')
    expect(screen.queryByText('services-publication')).not.toBeInTheDocument()
    expect(screen.getByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('legacy-archive')
  })

  it('provides semantic profile selection controls instead of row-click-only selection', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Execution Packs' })).toBeInTheDocument()

    const secondProfileButton = screen.getByRole('button', { name: 'Open execution pack legacy-archive' })
    expect(secondProfileButton.tagName).toBe('BUTTON')
    expect(secondProfileButton).toHaveStyle({ minHeight: '36px' })

    fireEvent.click(secondProfileButton)

    expect(await screen.findByTestId('pool-binding-profiles-selected-code')).toHaveTextContent('legacy-archive')
  })

  it('creates a reusable profile from the dedicated catalog form', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      binding_profile: {
        ...activeDetail,
        binding_profile_id: 'bp-new',
        code: 'new-profile',
        name: 'New Profile',
      },
    })
    mockUseCreateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync,
    })

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Create execution pack' }))
    expect(screen.getByRole('button', { name: 'Open /workflows' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open /decisions' })).toBeInTheDocument()

    fireEvent.change(await screen.findByTestId('pool-binding-profiles-create-code'), {
      target: { value: 'new-profile' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-name'), {
      target: { value: 'New Profile' },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-description'), {
      target: { value: 'Reusable authoring surface' },
    })
    expect(screen.queryByTestId('pool-binding-profiles-create-parameters-json')).not.toBeInTheDocument()
    openSelect('pool-binding-profiles-create-workflow-revision-select')
    fireEvent.click(await screen.findByText('New Services Publication · r6'))
    expect(await screen.findByText('wf-new-r1')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pool-binding-profiles-create-add-slot'))
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-slot-key-0'), {
      target: { value: 'document_policy' },
    })
    openSelect('pool-binding-profiles-create-decision-select-0')
    fireEvent.click(await screen.findByText('Services Policy · decision-1 · r3'))
    await waitFor(() => {
      expect(screen.getByTestId('pool-binding-profiles-create-slot-ref-0')).toHaveTextContent('decision-1')
    })
    fireEvent.click(screen.getByTestId('pool-binding-profiles-create-advanced-toggle'))
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-parameters-json'), {
      target: { value: JSON.stringify({ publication_variant: 'full' }, null, 2) },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-role-mapping-json'), {
      target: { value: JSON.stringify({ initiator: 'finance' }, null, 2) },
    })
    fireEvent.change(screen.getByTestId('pool-binding-profiles-create-metadata-json'), {
      target: { value: JSON.stringify({ source: 'manual' }, null, 2) },
    })

    fireEvent.click(screen.getByTestId('pool-binding-profiles-create-submit'))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        code: 'new-profile',
        name: 'New Profile',
        description: 'Reusable authoring surface',
        revision: {
          workflow: {
            workflow_definition_key: 'services-publication',
            workflow_revision_id: 'wf-new-r1',
            workflow_revision: 6,
            workflow_name: 'New Services Publication',
          },
          decisions: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'document_policy',
              slot_key: 'document_policy',
              decision_revision: 3,
            },
          ],
          parameters: {
            publication_variant: 'full',
          },
          role_mapping: {
            initiator: 'finance',
          },
          metadata: {
            source: 'manual',
          },
        },
      })
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('publishes a new immutable revision and deactivates the selected profile from the catalog', async () => {
    const reviseMutateAsync = vi.fn().mockResolvedValue({ binding_profile: activeDetail })
    const deactivateMutateAsync = vi.fn().mockResolvedValue({ binding_profile: deactivatedDetail })
    mockUseReviseBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: reviseMutateAsync,
    })
    mockUseDeactivateBindingProfile.mockReturnValue({
      isPending: false,
      mutateAsync: deactivateMutateAsync,
    })

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Publish new revision' }))

    openSelect('pool-binding-profiles-revise-workflow-revision-select')
    fireEvent.click(await screen.findByText('Services Publication · r5'))
    await waitFor(() => {
      expect(screen.getAllByText('wf-services-r5').length).toBeGreaterThan(0)
    })
    fireEvent.click(screen.getByTestId('pool-binding-profiles-revise-advanced-toggle'))
    fireEvent.change(screen.getByTestId('pool-binding-profiles-revise-metadata-json'), {
      target: { value: JSON.stringify({ source: 'catalog-update' }, null, 2) },
    })

    fireEvent.click(screen.getByTestId('pool-binding-profiles-revise-submit'))

    await waitFor(() => {
      expect(reviseMutateAsync).toHaveBeenCalledWith({
        bindingProfileId: activeDetail.binding_profile_id,
        request: {
          revision: {
            workflow: {
              workflow_definition_key: 'services-publication',
              workflow_revision_id: 'wf-services-r5',
              workflow_revision: 5,
              workflow_name: 'Services Publication',
            },
            decisions: [
              {
                decision_table_id: 'decision-1',
                decision_key: 'document_policy',
                slot_key: 'document_policy',
                decision_revision: 3,
              },
            ],
            parameters: {
              publication_variant: 'full',
            },
            role_mapping: {
              initiator: 'finance',
            },
            metadata: {
              source: 'catalog-update',
            },
          },
        },
      })
    })

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate execution pack' }))

    await waitFor(() => {
      expect(deactivateMutateAsync).toHaveBeenCalledWith(activeDetail.binding_profile_id)
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('renders publication slots as compact stacked rows in the publish revision modal', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Publish new revision' }))

    fireEvent.click(screen.getByTestId('pool-binding-profiles-revise-add-slot'))
    fireEvent.click(screen.getByTestId('pool-binding-profiles-revise-add-slot'))

    for (const slotIndex of [0, 1, 2]) {
      expect(screen.getByTestId(`pool-binding-profiles-revise-slot-row-${slotIndex}`)).toHaveStyle({
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      })
      expect(screen.getByTestId(`pool-binding-profiles-revise-slot-controls-${slotIndex}`)).toHaveStyle({
        alignItems: 'flex-start',
      })
    }

    const firstSlotControls = screen.getByTestId('pool-binding-profiles-revise-slot-controls-0')
    expect(
      within(firstSlotControls).queryByTestId('pool-binding-profiles-revise-slot-ref-0'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('pool-binding-profiles-revise-slot-ref-0')).toBeInTheDocument()
  })

  it('shows pool attachment usage for selected profile revisions', async () => {
    mockUseBindingProfileDetail.mockImplementation((bindingProfileId?: string) => ({
      data: bindingProfileId ? {
        binding_profile: {
          ...profileDetails[bindingProfileId],
          usage_summary: buildUsageSummary({
            attachment_count: 2,
            revision_summary: [
              {
                binding_profile_revision_id: 'bp-rev-services-r2',
                binding_profile_revision_number: 2,
                attachment_count: 1,
              },
              {
                binding_profile_revision_id: 'bp-rev-services-r1',
                binding_profile_revision_number: 1,
                attachment_count: 1,
              },
            ],
            attachments: [
              {
                pool_id: 'pool-1',
                pool_code: 'pool-main',
                pool_name: 'Pool Main',
                binding_id: 'binding-1',
                attachment_revision: 4,
                status: 'active',
                binding_profile_revision_id: 'bp-rev-services-r2',
                binding_profile_revision_number: 2,
                selector: { direction: 'top_down', mode: 'safe', tags: ['baseline'] },
                effective_from: '2026-01-01',
                effective_to: null,
              },
              {
                pool_id: 'pool-1',
                pool_code: 'pool-main',
                pool_name: 'Pool Main',
                binding_id: 'binding-2',
                attachment_revision: 2,
                status: 'draft',
                binding_profile_revision_id: 'bp-rev-services-r1',
                binding_profile_revision_number: 1,
                selector: { direction: 'bottom_up', mode: 'safe', tags: [] },
                effective_from: '2026-02-01',
                effective_to: null,
              },
            ],
          }),
        },
      } : undefined,
      isLoading: false,
      isError: false,
      error: null,
    }))

    renderPage()

    expect(await screen.findByText('Pool attachment usage')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Load attachment usage' }))

    expect(screen.getByTestId('pool-binding-profiles-usage-total')).toHaveTextContent('2')
    expect(screen.getByTestId('pool-binding-profiles-usage-revisions')).toHaveTextContent('2')
    expect(screen.getAllByText('pool-main')).toHaveLength(2)
    expect(screen.getByText('binding-1')).toBeInTheDocument()
    expect(screen.getByText('binding-2')).toBeInTheDocument()
  })

  it('navigates to the pool attachment workspace through the router when opening usage entries', async () => {
    mockUseBindingProfileDetail.mockImplementation((bindingProfileId?: string) => ({
      data: bindingProfileId ? {
        binding_profile: {
          ...profileDetails[bindingProfileId],
          usage_summary: buildUsageSummary({
            attachment_count: 1,
            revision_summary: [
              {
                binding_profile_revision_id: 'bp-rev-services-r2',
                binding_profile_revision_number: 2,
                attachment_count: 1,
              },
            ],
            attachments: [
              {
                pool_id: 'pool-1',
                pool_code: 'pool-main',
                pool_name: 'Pool Main',
                binding_id: 'binding-1',
                attachment_revision: 4,
                status: 'active',
                binding_profile_revision_id: 'bp-rev-services-r2',
                binding_profile_revision_number: 2,
                selector: { direction: 'top_down', mode: 'safe', tags: ['baseline'] },
                effective_from: '2026-01-01',
                effective_to: null,
              },
            ],
          }),
        },
      } : undefined,
      isLoading: false,
      isError: false,
      error: null,
    }))

    renderPageWithRoutes('/pools/execution-packs?profile=bp-services&detail=1')

    fireEvent.click(await screen.findByRole('button', { name: 'Load attachment usage' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Open pool attachment' }))

    expect(await screen.findByTestId('location-probe')).toHaveTextContent('/pools/catalog?pool_id=pool-1&tab=bindings')
  })

  it('surfaces topology compatibility diagnostics for incompatible execution packs', async () => {
    mockUseBindingProfileDetail.mockImplementation((bindingProfileId?: string) => ({
      data: bindingProfileId ? {
        binding_profile: {
          ...profileDetails[bindingProfileId],
          latest_revision: buildRevision({
            topology_template_compatibility: {
              status: 'incompatible',
              topology_aware_ready: false,
              covered_slot_keys: ['document_policy'],
              diagnostics: [
                {
                  code: 'EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED',
                  slot_key: 'document_policy',
                  decision_table_id: 'decision-1',
                  decision_revision: 3,
                  field_or_table_path: 'documents[0].field_mappings.counterparty',
                  detail: 'Concrete participant refs are not reusable for topology templates.',
                },
              ],
            },
          }),
        },
      } : undefined,
      isLoading: false,
      isError: false,
      error: null,
    }))

    renderPage('/pools/execution-packs?profile=bp-services&detail=1')

    expect(await screen.findByTestId('pool-binding-profiles-topology-compatibility-status')).toHaveTextContent(
      'incompatible',
    )
    expect(screen.getByTestId('pool-binding-profiles-topology-diagnostic-0')).toHaveTextContent(
      'slot document_policy',
    )
    expect(screen.getByText('Open /decisions')).toBeInTheDocument()
  })

  it('fails closed on primary catalog load errors without triggering usage reads', async () => {
    mockUseBindingProfiles.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: {
        response: {
          data: {
            detail: 'Backend refused to load execution packs.',
          },
        },
      },
    })
    mockUseBindingProfileDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    })

    renderPage()

    expect(await screen.findByText('Backend refused to load execution packs.')).toBeInTheDocument()
    expect(screen.getByText('Select an execution pack from the catalog.')).toBeInTheDocument()
  })
})
