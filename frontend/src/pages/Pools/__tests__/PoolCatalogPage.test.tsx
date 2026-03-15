import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter } from 'react-router-dom'

import type {
  Organization,
  PoolWorkflowBinding,
  PoolWorkflowBindingCollection,
} from '../../../api/intercompanyPools'
import { PoolCatalogPage } from '../PoolCatalogPage'

const mockGetDecisionsCollection = vi.fn()
const mockListOrganizations = vi.fn()
const mockGetOrganization = vi.fn()
const mockListOrganizationPools = vi.fn()
const mockGetPoolGraph = vi.fn()
const mockUpsertOrganization = vi.fn()
const mockUpsertOrganizationPool = vi.fn()
const mockUpsertPoolTopologySnapshot = vi.fn()
const mockListPoolTopologySnapshots = vi.fn()
const mockSyncOrganizationsCatalog = vi.fn()
const mockGetPoolODataMetadataCatalog = vi.fn()
const mockRefreshPoolODataMetadataCatalog = vi.fn()
const mockListPoolWorkflowBindings = vi.fn()
const mockUpsertPoolWorkflowBinding = vi.fn()
const mockDeletePoolWorkflowBinding = vi.fn()
const mockMigratePoolEdgeDocumentPolicy = vi.fn()
const mockListMasterDataParties = vi.fn()
const mockListMasterDataItems = vi.fn()
const mockListMasterDataContracts = vi.fn()
const mockListMasterDataTaxProfiles = vi.fn()
const mockUseMe = vi.fn()
const mockUseDatabases = vi.fn()
const mockUseMyTenants = vi.fn()
const mockSyncPoolWorkflowBindings = vi.fn()

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../api/generated/v2/v2', () => ({
  getV2: () => ({
    getDecisionsCollection: (...args: unknown[]) => mockGetDecisionsCollection(...args),
    getPoolsOdataMetadataCatalogGet: (...args: unknown[]) => mockGetPoolODataMetadataCatalog(...args),
    postPoolsOdataMetadataCatalogRefresh: (...args: unknown[]) => mockRefreshPoolODataMetadataCatalog(...args),
  }),
}))

vi.mock('../../../api/queries/me', () => ({
  useMe: (...args: unknown[]) => mockUseMe(...args),
}))

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: (...args: unknown[]) => mockUseDatabases(...args),
}))

vi.mock('../../../api/queries/tenants', () => ({
  useMyTenants: (...args: unknown[]) => mockUseMyTenants(...args),
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizations: (...args: unknown[]) => mockListOrganizations(...args),
  getOrganization: (...args: unknown[]) => mockGetOrganization(...args),
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
  getPoolGraph: (...args: unknown[]) => mockGetPoolGraph(...args),
  upsertOrganization: (...args: unknown[]) => mockUpsertOrganization(...args),
  upsertOrganizationPool: (...args: unknown[]) => mockUpsertOrganizationPool(...args),
  upsertPoolTopologySnapshot: (...args: unknown[]) => mockUpsertPoolTopologySnapshot(...args),
  listPoolTopologySnapshots: (...args: unknown[]) => mockListPoolTopologySnapshots(...args),
  syncOrganizationsCatalog: (...args: unknown[]) => mockSyncOrganizationsCatalog(...args),
  getPoolODataMetadataCatalog: (...args: unknown[]) => mockGetPoolODataMetadataCatalog(...args),
  refreshPoolODataMetadataCatalog: (...args: unknown[]) => mockRefreshPoolODataMetadataCatalog(...args),
  listPoolWorkflowBindings: (...args: unknown[]) => mockListPoolWorkflowBindings(...args),
  upsertPoolWorkflowBinding: (...args: unknown[]) => mockUpsertPoolWorkflowBinding(...args),
  deletePoolWorkflowBinding: (...args: unknown[]) => mockDeletePoolWorkflowBinding(...args),
  migratePoolEdgeDocumentPolicy: (...args: unknown[]) => mockMigratePoolEdgeDocumentPolicy(...args),
  listMasterDataParties: (...args: unknown[]) => mockListMasterDataParties(...args),
  listMasterDataItems: (...args: unknown[]) => mockListMasterDataItems(...args),
  listMasterDataContracts: (...args: unknown[]) => mockListMasterDataContracts(...args),
  listMasterDataTaxProfiles: (...args: unknown[]) => mockListMasterDataTaxProfiles(...args),
}))

vi.mock('../poolWorkflowBindingsSync', async () => {
  const actual = await vi.importActual<typeof import('../poolWorkflowBindingsSync')>('../poolWorkflowBindingsSync')
  return {
    ...actual,
    syncPoolWorkflowBindings: (...args: unknown[]) => mockSyncPoolWorkflowBindings(...args),
  }
})

const baseOrganization: Organization = {
  id: '11111111-1111-1111-1111-111111111111',
  tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  database_id: '22222222-2222-2222-2222-222222222222',
  name: 'Org One',
  full_name: 'Org One LLC',
  inn: '730000000001',
  kpp: '123456789',
  status: 'active',
  external_ref: '',
  metadata: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:01Z',
}

const secondOrganization: Organization = {
  ...baseOrganization,
  id: '77777777-7777-7777-7777-777777777777',
  database_id: '88888888-8888-8888-8888-888888888888',
  name: 'Org Two',
  full_name: 'Org Two LLC',
  inn: '730000000002',
}

let initialCatalogLoadPromise: Promise<void> | null = null

function buildPoolWorkflowBinding(overrides: Partial<PoolWorkflowBinding> = {}): PoolWorkflowBinding {
  return {
    binding_id: 'binding-top-down',
    pool_id: 'pool-1',
    revision: 1,
    workflow: {
      workflow_definition_key: 'services-publication',
      workflow_revision_id: '11111111-1111-1111-1111-111111111111',
      workflow_revision: 3,
      workflow_name: 'services_publication',
    },
    selector: {
      direction: 'top_down',
      mode: 'safe',
      tags: ['baseline'],
    },
    effective_from: '2026-01-01',
    effective_to: null,
    status: 'active',
    ...overrides,
  }
}

function buildPoolWorkflowBindingCollection(
  workflowBindings: PoolWorkflowBinding[] = [],
  overrides: Partial<PoolWorkflowBindingCollection> = {}
): PoolWorkflowBindingCollection {
  return {
    pool_id: '44444444-4444-4444-4444-444444444444',
    workflow_bindings: workflowBindings,
    collection_etag: 'sha256:test-etag',
    blocking_remediation: null,
    ...overrides,
  }
}

function buildMinimalDocumentPolicy() {
  return {
    version: 'document_policy.v1',
    chains: [
      {
        chain_id: 'sale_chain',
        documents: [
          {
            document_id: 'sale',
            entity_name: 'Document_Sales',
            document_role: 'sale',
          },
        ],
      },
    ],
  }
}

async function waitForInitialCatalogLoad() {
  await waitFor(() => expect(mockListOrganizations).toHaveBeenCalled())
  await waitFor(() => expect(mockGetOrganization).toHaveBeenCalled())
  await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalled())
  await waitFor(() => expect(mockGetPoolGraph).toHaveBeenCalled())
  await waitFor(() => expect(mockListPoolTopologySnapshots).toHaveBeenCalled())
}

function renderPage() {
  const result = render(
    <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <AntApp>
        <PoolCatalogPage />
      </AntApp>
    </MemoryRouter>
  )
  initialCatalogLoadPromise = waitForInitialCatalogLoad()
  return result
}

function openSelectByTestId(testId: string) {
  const select = screen.getByTestId(testId)
  const trigger = select.querySelector('.ant-select-selector') as HTMLElement | null
  fireEvent.mouseDown(trigger ?? select)
}

async function selectDropdownOption(label: string | RegExp) {
  const matcher = typeof label === 'string' ? label : (content: string) => label.test(content)
  const matches = await screen.findAllByText(matcher)
  const option = [...matches]
    .reverse()
    .find((node) => node.closest('.ant-select-item-option'))
  expect(option).toBeTruthy()
  fireEvent.click(option as Element)
}

async function openWorkspaceTab(
  user: ReturnType<typeof userEvent.setup>,
  tabLabel: 'Pools' | 'Bindings' | 'Topology Editor'
) {
  await initialCatalogLoadPromise
  await user.click(screen.getByRole('tab', { name: tabLabel }))
  if (tabLabel === 'Pools') {
    await screen.findByText('Pools management')
    return
  }
  if (tabLabel === 'Bindings') {
    await screen.findByText('Workflow bindings workspace')
    return
  }
  await screen.findByText('Topology snapshots by date')
  await waitFor(() => {
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeInTheDocument()
  })
}

async function expandFirstEdgeAdvanced(user: ReturnType<typeof userEvent.setup>) {
  const toggle = await screen.findAllByText('Advanced edge metadata')
  await user.click(toggle[0] as HTMLElement)
}

const EXTENDED_UI_TEST_TIMEOUT_MS = 30000
const TOPOLOGY_EDITOR_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS
const SYNC_MODAL_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS

describe('PoolCatalogPage', () => {
  beforeEach(() => {
    initialCatalogLoadPromise = null
    localStorage.clear()

    mockListOrganizations.mockReset()
    mockGetOrganization.mockReset()
    mockGetDecisionsCollection.mockReset()
    mockListOrganizationPools.mockReset()
    mockGetPoolGraph.mockReset()
    mockUpsertOrganization.mockReset()
    mockUpsertOrganizationPool.mockReset()
    mockUpsertPoolTopologySnapshot.mockReset()
    mockListPoolTopologySnapshots.mockReset()
    mockSyncOrganizationsCatalog.mockReset()
    mockGetPoolODataMetadataCatalog.mockReset()
    mockRefreshPoolODataMetadataCatalog.mockReset()
    mockListPoolWorkflowBindings.mockReset()
    mockUpsertPoolWorkflowBinding.mockReset()
    mockDeletePoolWorkflowBinding.mockReset()
    mockMigratePoolEdgeDocumentPolicy.mockReset()
    mockListMasterDataParties.mockReset()
    mockListMasterDataItems.mockReset()
    mockListMasterDataContracts.mockReset()
    mockListMasterDataTaxProfiles.mockReset()
    mockUseMe.mockReset()
    mockUseDatabases.mockReset()
    mockUseMyTenants.mockReset()
    mockSyncPoolWorkflowBindings.mockReset()

    mockUseMe.mockReturnValue({ data: { is_staff: false } })
    mockUseMyTenants.mockReturnValue({
      data: { active_tenant_id: null, tenants: [] },
    })
    mockUseDatabases.mockReturnValue({
      data: {
        databases: [
          { id: '22222222-2222-2222-2222-222222222222', name: 'db1' },
          { id: '33333333-3333-3333-3333-333333333333', name: 'db2' },
        ],
      },
      isLoading: false,
    })

    mockListOrganizations.mockResolvedValue([baseOrganization])
    mockGetOrganization.mockResolvedValue({
      organization: baseOrganization,
      pool_bindings: [],
    })
    mockListOrganizationPools.mockResolvedValue([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [],
      edges: [],
    })
    mockUpsertOrganization.mockResolvedValue({
      organization: baseOrganization,
      created: false,
    })
    mockUpsertOrganizationPool.mockResolvedValue({
      pool: {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
      created: false,
    })
    mockUpsertPoolTopologySnapshot.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      version: 'v1:topology-updated',
      effective_from: '2026-01-01',
      effective_to: null,
      nodes_count: 0,
      edges_count: 0,
    })
    mockListPoolTopologySnapshots.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      count: 1,
      snapshots: [
        {
          effective_from: '2026-01-01',
          effective_to: null,
          nodes_count: 0,
          edges_count: 0,
        },
      ],
    })
    mockSyncOrganizationsCatalog.mockResolvedValue({
      stats: { created: 1, updated: 0, skipped: 0 },
      total_rows: 1,
    })
    mockGetPoolODataMetadataCatalog.mockResolvedValue({
      database_id: '88888888-8888-8888-8888-888888888888',
      source: 'db',
      fetched_at: '2026-01-01T00:00:00Z',
      catalog_version: 'v1:test',
      config_name: 'test',
      config_version: '',
      metadata_hash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      documents: [
        {
          entity_name: 'Document_Sales',
          display_name: 'Sales',
          fields: [{ name: 'Amount', type: 'Edm.Decimal', nullable: false }],
          table_parts: [],
        },
      ],
    })
    mockRefreshPoolODataMetadataCatalog.mockResolvedValue({
      database_id: '88888888-8888-8888-8888-888888888888',
      source: 'live_refresh',
      fetched_at: '2026-01-01T00:00:00Z',
      catalog_version: 'v1:test',
      config_name: 'test',
      config_version: '',
      metadata_hash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      documents: [
        {
          entity_name: 'Document_Sales',
          display_name: 'Sales',
          fields: [{ name: 'Amount', type: 'Edm.Decimal', nullable: false }],
          table_parts: [],
        },
      ],
    })
    mockListPoolWorkflowBindings.mockResolvedValue(buildPoolWorkflowBindingCollection())
    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [
        {
          id: 'decision-version-4',
          decision_table_id: 'decision-1',
          decision_key: 'route_documents',
          decision_revision: 4,
          name: 'Route Documents',
          is_active: true,
        },
      ],
      count: 1,
    })
    mockUpsertPoolWorkflowBinding.mockImplementation(async ({ pool_id, workflow_binding }) => ({
      pool_id,
      workflow_binding: {
        ...workflow_binding,
        binding_id: workflow_binding.binding_id || 'generated-binding-id',
      },
      created: !workflow_binding.binding_id,
    }))
    mockDeletePoolWorkflowBinding.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      workflow_binding: buildPoolWorkflowBinding(),
      deleted: true,
    })
    mockMigratePoolEdgeDocumentPolicy.mockResolvedValue({
      decision: {
        id: 'decision-version-2',
        decision_table_id: 'services-publication-policy',
        decision_key: 'document_policy',
        decision_revision: 2,
        name: 'Services publication policy',
      },
      metadata_context: {
        snapshot_id: 'snapshot-1',
        config_name: 'shared-profile',
        config_version: '8.3.24',
      },
      migration: {
        created: true,
        reused_existing_revision: false,
        binding_update_required: false,
        source: {
          pool_id: '44444444-4444-4444-4444-444444444444',
          edge_version_id: 'edge-v1',
          source_path: 'edge.metadata.document_policy',
        },
        decision_ref: {
          decision_id: 'decision-version-2',
          decision_table_id: 'services-publication-policy',
          decision_revision: 2,
        },
      },
    })
    mockSyncPoolWorkflowBindings.mockResolvedValue(undefined)
    mockListMasterDataParties.mockResolvedValue({
      parties: [
        {
          id: 'party-1',
          tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          canonical_id: 'party-001',
          name: 'Party One',
          full_name: 'Party One LLC',
          inn: '730000000001',
          kpp: '',
          is_our_organization: true,
          is_counterparty: true,
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 500, offset: 0, total: 1 },
    })
    mockListMasterDataItems.mockResolvedValue({
      items: [
        {
          id: 'item-1',
          tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          canonical_id: 'item-001',
          name: 'Item One',
          sku: 'SKU-1',
          unit: 'pcs',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 500, offset: 0, total: 1 },
    })
    mockListMasterDataContracts.mockResolvedValue({
      contracts: [
        {
          id: 'contract-1',
          tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          canonical_id: 'contract-001',
          name: 'Contract One',
          owner_counterparty_id: 'party-1',
          owner_counterparty_canonical_id: 'party-001',
          number: 'C-1',
          date: '2026-01-01',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 500, offset: 0, total: 1 },
    })
    mockListMasterDataTaxProfiles.mockResolvedValue({
      tax_profiles: [
        {
          id: 'tax-1',
          tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          canonical_id: 'vat-20',
          vat_rate: 20,
          vat_included: true,
          vat_code: 'VAT20',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 500, offset: 0, total: 1 },
    })
  })

  it('disables mutating controls for staff without active tenant', async () => {
    mockUseMe.mockReturnValue({ data: { is_staff: true } })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(screen.getAllByText('Mutating actions are disabled').length).toBeGreaterThan(0)
    expect(screen.getByTestId('pool-catalog-add-org')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-edit-org')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeDisabled()
  })

  it('keeps mutating controls enabled for non-staff without active tenant', async () => {
    mockUseMe.mockReturnValue({ data: { is_staff: false } })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-add-org')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeEnabled()
  })

  it('keeps mutating controls enabled for staff with tenant from server context', async () => {
    mockUseMe.mockReturnValue({ data: { is_staff: true } })
    mockUseMyTenants.mockReturnValue({
      data: {
        active_tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        tenants: [{ id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', slug: 'default', name: 'Default', role: 'owner' }],
      },
    })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-add-org')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeEnabled()
  })

  it('creates organization via drawer and reloads catalog', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockResolvedValueOnce({
      organization: {
        ...baseOrganization,
        id: '55555555-5555-5555-5555-555555555555',
        inn: '730000000999',
        name: 'Created Org',
      },
      created: true,
    })
    mockListOrganizations
      .mockResolvedValueOnce([baseOrganization])
      .mockResolvedValueOnce([
        baseOrganization,
        {
          ...baseOrganization,
          id: '55555555-5555-5555-5555-555555555555',
          inn: '730000000999',
          name: 'Created Org',
        },
      ])

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await user.click(screen.getByTestId('pool-catalog-add-org'))

    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000999')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Created Org')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(mockUpsertOrganization).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganization).toHaveBeenCalledWith(
      expect.objectContaining({
        inn: '730000000999',
        name: 'Created Org',
      })
    )
    await waitFor(() => expect(mockListOrganizations).toHaveBeenCalledTimes(2))
  }, 30000)

  it('updates organization details after editing without page reload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()
    const nextDatabaseId = '33333333-3333-3333-3333-333333333333'
    const updatedOrganization = {
      ...baseOrganization,
      database_id: nextDatabaseId,
      updated_at: '2026-01-01T00:00:02Z',
    }

    mockListOrganizations
      .mockResolvedValueOnce([baseOrganization])
      .mockResolvedValueOnce([updatedOrganization])
    mockGetOrganization
      .mockResolvedValueOnce({
        organization: baseOrganization,
        pool_bindings: [],
      })
      .mockResolvedValueOnce({
        organization: updatedOrganization,
        pool_bindings: [],
      })
    mockUpsertOrganization.mockResolvedValueOnce({
      organization: updatedOrganization,
      created: false,
    })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(await screen.findByText(baseOrganization.database_id as string)).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-edit-org'))
    const drawer = await screen.findByRole('dialog', { name: 'Edit organization' })
    await user.click(within(drawer).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(mockUpsertOrganization).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(nextDatabaseId)).toBeInTheDocument()
  }, 30000)

  it('creates pool via drawer and reloads pools list', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()
    const initialPools = [
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]
    const updatedPools = [
      ...initialPools,
      {
        id: '66666666-6666-6666-6666-666666666666',
        code: 'pool-2',
        name: 'Pool Two',
        description: 'Second pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]

    mockUpsertOrganizationPool.mockResolvedValueOnce({
      pool: {
        id: '66666666-6666-6666-6666-666666666666',
        code: 'pool-2',
        name: 'Pool Two',
        description: 'Second pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
      created: true,
    })
    mockListOrganizationPools.mockResolvedValue(updatedPools)
    mockListOrganizationPools.mockResolvedValueOnce(initialPools)

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-add-pool'))
    fireEvent.change(screen.getByLabelText('Code'), { target: { value: 'pool-2' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Pool Two' } })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Second pool' } })
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'pool-2',
        name: 'Pool Two',
      })
    )
    expect(await screen.findByText('Pool Two')).toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('edits selected pool via drawer and sends pool_id in upsert payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Pool One Updated')
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One Updated',
      })
    )
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('renders existing workflow bindings in isolated workspace and keeps pool drawer focused on pool fields', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [
          buildPoolWorkflowBinding(),
          buildPoolWorkflowBinding({
            binding_id: 'binding-bottom-up',
            workflow: {
              workflow_definition_key: 'bottom-up-import',
              workflow_revision_id: '22222222-2222-2222-2222-222222222222',
              workflow_revision: 5,
              workflow_name: 'bottom_up_import',
            },
            selector: {
              direction: 'bottom_up',
              mode: 'safe',
              tags: ['cutover', 'monthly'],
            },
          }),
        ],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(buildPoolWorkflowBindingCollection([
      buildPoolWorkflowBinding(),
      buildPoolWorkflowBinding({
        binding_id: 'binding-bottom-up',
        workflow: {
          workflow_definition_key: 'bottom-up-import',
          workflow_revision_id: '22222222-2222-2222-2222-222222222222',
          workflow_revision: 5,
          workflow_name: 'bottom_up_import',
        },
        selector: {
          direction: 'bottom_up',
          mode: 'safe',
          tags: ['cutover', 'monthly'],
        },
      }),
    ]))

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')

    expect(screen.queryByLabelText('Workflow bindings JSON')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(mockListPoolWorkflowBindings).toHaveBeenCalledWith('44444444-4444-4444-4444-444444444444')
    })
    expect(screen.getByText('Workflow bindings workspace')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-workflow-binding-card-0')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-workflow-binding-card-1')).toBeInTheDocument()
    expect(screen.getByDisplayValue('services-publication')).toBeInTheDocument()
    expect(screen.getByDisplayValue('bottom-up-import')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-workflow-binding-summary-0')).toHaveTextContent(
      'direction=top_down'
    )
    expect(screen.getByTestId('pool-catalog-workflow-binding-summary-1')).toHaveTextContent(
      'tags=cutover, monthly'
    )

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))

    const dialog = await screen.findByRole('dialog', { name: 'Edit pool' })
    expect(within(dialog).queryByTestId('pool-catalog-workflow-binding-card-0')).not.toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('removes deleted workflow bindings through first-class binding API', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [buildPoolWorkflowBinding()],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(
      buildPoolWorkflowBindingCollection([buildPoolWorkflowBinding()])
    )

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-remove-0'))
    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    expect(mockUpsertOrganizationPool).not.toHaveBeenCalled()
    await waitFor(() => expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledTimes(1))
    expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledWith({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:test-etag',
      nextBindings: [],
    })
    expect(mockUpsertPoolWorkflowBinding).not.toHaveBeenCalled()
    expect(mockDeletePoolWorkflowBinding).not.toHaveBeenCalled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('does not sync workflow bindings when saving only pool fields', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    const existingBinding = buildPoolWorkflowBinding({
      binding_id: 'binding-existing',
      revision: 3,
    })
    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [existingBinding],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(
      buildPoolWorkflowBindingCollection([existingBinding], {
        collection_etag: 'sha256:existing-binding-etag',
      })
    )

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockSyncPoolWorkflowBindings).not.toHaveBeenCalled()
    expect(mockUpsertPoolWorkflowBinding).not.toHaveBeenCalled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('shows stale binding revision conflict without clearing edited workflow binding form', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    const existingBinding = buildPoolWorkflowBinding({
      binding_id: 'binding-existing',
      revision: 3,
    })
    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [existingBinding],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(
      buildPoolWorkflowBindingCollection([existingBinding], {
        collection_etag: 'sha256:existing-binding-etag',
      })
    )
    mockSyncPoolWorkflowBindings.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Workflow Binding Collection Conflict',
          status: 409,
          detail: 'Workflow binding collection was updated by another operator. Reload bindings and retry.',
          code: 'POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT',
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    await waitFor(() => {
      expect(mockListPoolWorkflowBindings).toHaveBeenCalledWith('44444444-4444-4444-4444-444444444444')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-workflow-binding-workflow-name-0')).toHaveValue('services_publication')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-save-bindings')).toBeEnabled()
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-name-0'), {
      target: { value: 'services_publication_conflicted' },
    })

    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    expect(mockUpsertOrganizationPool).not.toHaveBeenCalled()
    await waitFor(() => expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledTimes(1), { timeout: 2000 })
    expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledWith({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:existing-binding-etag',
      nextBindings: [
        expect.objectContaining({
          binding_id: 'binding-existing',
          revision: 3,
          workflow: expect.objectContaining({
            workflow_name: 'services_publication_conflicted',
          }),
        }),
      ],
    })
    expect(
      screen.getByTestId('pool-catalog-workflow-binding-workflow-name-0')
    ).toHaveValue('services_publication_conflicted')
    expect(screen.getByText('Workflow bindings workspace')).toBeInTheDocument()
  }, 30000)

  it('submits workflow bindings from isolated workspace via structured editor', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-key-0'), {
      target: { value: 'services-publication' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-revision-id-0'), {
      target: { value: '11111111-1111-1111-1111-111111111111' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-revision-0'), {
      target: { value: '3' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-name-0'), {
      target: { value: 'services_publication' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-effective-from-0'), {
      target: { value: '2026-01-01' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-effective-to-0'), {
      target: { value: '2026-12-31' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-selector-direction-0'), {
      target: { value: 'top_down' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-selector-mode-0'), {
      target: { value: 'safe' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-selector-tags-0'), {
      target: { value: 'baseline, monthly' },
    })
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add-decision-0'))
    openSelectByTestId('pool-catalog-workflow-binding-decision-select-0-0')
    await selectDropdownOption('Route Documents (route_documents) · r4')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add-role-0'))
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-role-source-0-0'), {
      target: { value: 'owner' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-role-target-0-0'), {
      target: { value: 'publisher' },
    })
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add-parameter-0'))
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-parameter-key-0-0'), {
      target: { value: 'strategy' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-parameter-value-0-0'), {
      target: { value: '"strict"' },
    })
    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    expect(mockUpsertOrganizationPool).not.toHaveBeenCalled()
    await waitFor(() => expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledTimes(1))
    expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledWith({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:test-etag',
      nextBindings: [
        expect.objectContaining({
          workflow: expect.objectContaining({
            workflow_definition_key: 'services-publication',
            workflow_revision: 3,
        }),
        decisions: [
          expect.objectContaining({
            decision_table_id: 'decision-1',
            decision_key: 'route_documents',
            decision_revision: 4,
          }),
        ],
        role_mapping: {
          owner: 'publisher',
        },
        parameters: {
          strategy: 'strict',
        },
        selector: {
          direction: 'top_down',
          mode: 'safe',
          tags: ['baseline', 'monthly'],
        },
        effective_to: '2026-12-31',
        status: 'draft',
      }),
      ],
    })
    expect(mockDeletePoolWorkflowBinding).not.toHaveBeenCalled()
  }, 30000)

  it('uses active /decisions revisions in pool binding editor and hides inactive revisions by default', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockGetDecisionsCollection.mockResolvedValueOnce({
      decisions: [
        {
          id: 'decision-version-4',
          decision_table_id: 'decision-1',
          decision_key: 'route_documents',
          decision_revision: 4,
          name: 'Route Documents',
          is_active: true,
          metadata_context: {
            config_name: 'shared-profile',
            config_version: '8.3.24',
          },
          metadata_compatibility: {
            status: 'compatible',
            reason: null,
            is_compatible: true,
          },
        },
        {
          id: 'decision-version-5',
          decision_table_id: 'decision-2',
          decision_key: 'route_documents_drift',
          decision_revision: 5,
          name: 'Route Documents Drift',
          is_active: true,
          metadata_context: {
            config_name: 'shared-profile',
            config_version: '8.3.24',
            publication_drift: true,
          },
          metadata_compatibility: {
            status: 'compatible',
            reason: 'metadata_surface_diverged',
            is_compatible: true,
          },
        },
        {
          id: 'decision-version-6',
          decision_table_id: 'decision-3',
          decision_key: 'route_documents_incompatible',
          decision_revision: 6,
          name: 'Incompatible Route',
          is_active: true,
          metadata_context: {
            config_name: 'other-profile',
            config_version: '1.0.0',
          },
          metadata_compatibility: {
            status: 'incompatible',
            reason: 'configuration_scope_mismatch',
            is_compatible: false,
          },
        },
        {
          id: 'decision-version-3',
          decision_table_id: 'decision-legacy',
          decision_key: 'legacy_route',
          decision_revision: 3,
          name: 'Legacy Route',
          is_active: false,
        },
      ],
      count: 2,
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add-decision-0'))

    openSelectByTestId('pool-catalog-workflow-binding-decision-select-0-0')
    expect(mockGetDecisionsCollection).toHaveBeenCalledWith({ database_id: baseOrganization.database_id })
    const activeOption = await screen.findByText('Route Documents (route_documents) · r4 · shared-profile 8.3.24')
    expect(activeOption).toBeInTheDocument()
    expect(screen.getByText('Route Documents Drift (route_documents_drift) · r5 · shared-profile 8.3.24 · drift')).toBeInTheDocument()
    expect(screen.queryByText('Incompatible Route (route_documents_incompatible) · r6')).not.toBeInTheDocument()
    expect(screen.queryByText('Legacy Route (legacy_route) · r3')).not.toBeInTheDocument()

    await user.click(activeOption)
    expect(await screen.findByTestId('pool-catalog-workflow-binding-slot-key-0-0')).toHaveTextContent('route_documents')
  }, 30000)

  it('keeps inactive pinned decision refs visible for existing workflow bindings', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    const existingBinding = buildPoolWorkflowBinding({
      decisions: [
        {
          decision_table_id: 'decision-legacy',
          decision_key: 'legacy_route',
          decision_revision: 3,
        },
      ],
    })
    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [existingBinding],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(
      buildPoolWorkflowBindingCollection([existingBinding], {
        collection_etag: 'sha256:inactive-binding-etag',
      })
    )
    mockGetDecisionsCollection.mockResolvedValueOnce({
      decisions: [
        {
          id: 'decision-version-4',
          decision_table_id: 'decision-1',
          decision_key: 'route_documents',
          decision_revision: 4,
          name: 'Route Documents',
          is_active: true,
        },
      ],
      count: 1,
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-workflow-binding-decision-select-0-0')).toBeInTheDocument()
    })
    expect(screen.getByTestId('pool-catalog-workflow-binding-slot-key-0-0')).toHaveTextContent('legacy_route')

    openSelectByTestId('pool-catalog-workflow-binding-decision-select-0-0')
    expect(
      await screen.findAllByText('decision-legacy (legacy_route) · r3 [inactive]')
    ).not.toHaveLength(0)
    expect(screen.getByText('Route Documents (route_documents) · r4')).toBeInTheDocument()
  }, 30000)

  it('shows topology slot coverage summary in bindings workspace', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListPoolWorkflowBindings.mockResolvedValueOnce(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'sale-policy',
              decision_key: 'sale',
              decision_revision: 7,
            },
          ],
        }),
      ])
    )
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-with-slots',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {},
        },
        {
          node_version_id: 'node-v3',
          organization_id: '88888888-8888-8888-8888-888888888888',
          inn: '730000000003',
          name: 'Org Three',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'sale',
          },
        },
        {
          edge_version_id: 'edge-v2',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v3',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'purchase',
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    expect(await screen.findByTestId('pool-catalog-workflow-binding-coverage-0')).toHaveTextContent('edges: 2')
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-0')).toHaveTextContent('resolved: 1')
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-0')).toHaveTextContent('missing slot: 1')
    expect(screen.getByText('Binding remediation required')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-save-bindings')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-workflow-binding-slot-coverage-0-0')).toHaveTextContent('edges: 1')
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-item-0')).toHaveTextContent(
      'Org One -> Org Three · purchase · Slot missing'
    )
  }, 30000)

  it('fails closed when first-class workflow bindings load fails', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [buildPoolWorkflowBinding()],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockRejectedValueOnce(new Error('binding read failed'))

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')

    expect(await screen.findByText('binding read failed')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-save-bindings')).toBeDisabled()
    expect(screen.queryByDisplayValue('services-publication')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Workflow bindings JSON')).not.toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('enters blocking remediation state when canonical collection is empty but legacy metadata is present', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        workflow_bindings: [],
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(buildPoolWorkflowBindingCollection([], {
      collection_etag: 'sha256:legacy-remediation',
      blocking_remediation: {
        code: 'LEGACY_METADATA_WORKFLOW_BINDINGS_PRESENT',
        title: 'Legacy workflow bindings remediation required',
        detail: 'Canonical binding collection is empty while legacy metadata payload is still present.',
      },
    }))

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')

    expect(await screen.findByText('Legacy workflow bindings remediation required')).toBeInTheDocument()
    expect(
      screen.getByText('Canonical binding collection is empty while legacy metadata payload is still present.')
    ).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-save-bindings')).toBeDisabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('blocks save when structured workflow binding contains invalid parameter JSON', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-key-0'), {
      target: { value: 'services-publication' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-revision-id-0'), {
      target: { value: '11111111-1111-1111-1111-111111111111' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-revision-0'), {
      target: { value: '3' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-workflow-name-0'), {
      target: { value: 'services_publication' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-effective-from-0'), {
      target: { value: '2026-01-01' },
    })
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add-parameter-0'))
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-parameter-key-0-0'), {
      target: { value: 'strategy' },
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-parameter-value-0-0'), {
      target: { value: '{bad json}' },
    })

    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    expect(
      await screen.findByText('Binding #1: parameters.strategy должен быть валидным JSON.')
    ).toBeInTheDocument()
    expect(mockUpsertOrganizationPool).not.toHaveBeenCalled()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('deactivates selected pool via toggle action', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-toggle-pool-active'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: '44444444-4444-4444-4444-444444444444',
        is_active: false,
      })
    )
  }, SYNC_MODAL_TIMEOUT_MS)

  it('blocks topology save when preflight validation fails and keeps form input', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    expect(await screen.findByText('Preflight validation failed')).toBeInTheDocument()
    expect(await screen.findByText('Добавьте хотя бы один topology node.')).toBeInTheDocument()
    expect(mockUpsertPoolTopologySnapshot).not.toHaveBeenCalled()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('renders move arrows for topology nodes and edges', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')

    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    expect(screen.getByTestId('pool-catalog-topology-node-move-up-0')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-topology-node-move-down-0')).toBeDisabled()

    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    expect(screen.getByTestId('pool-catalog-topology-node-move-up-1')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-topology-node-move-down-0')).toBeEnabled()

    await user.click(screen.getByTestId('pool-catalog-topology-add-edge'))
    expect(screen.getByTestId('pool-catalog-topology-edge-move-up-0')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-topology-edge-move-down-0')).toBeDisabled()

    await user.click(screen.getByTestId('pool-catalog-topology-add-edge'))
    expect(screen.getByTestId('pool-catalog-topology-edge-move-up-1')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-topology-edge-move-down-0')).toBeEnabled()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('loads master-data token catalogs with backend-compatible limit in topology mode', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')

    await waitFor(() => {
      expect(mockListMasterDataParties).toHaveBeenCalledWith({ limit: 200, offset: 0 })
      expect(mockListMasterDataItems).toHaveBeenCalledWith({ limit: 200, offset: 0 })
      expect(mockListMasterDataContracts).toHaveBeenCalledWith({ limit: 200, offset: 0 })
      expect(mockListMasterDataTaxProfiles).toHaveBeenCalledWith({ limit: 200, offset: 0 })
    })
  }, SYNC_MODAL_TIMEOUT_MS)

  it('loads topology snapshots list and switches graph date from snapshot row', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListPoolTopologySnapshots.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      count: 2,
      snapshots: [
        {
          effective_from: '2026-02-24',
          effective_to: null,
          nodes_count: 4,
          edges_count: 3,
        },
        {
          effective_from: '2026-01-01',
          effective_to: '2026-02-23',
          nodes_count: 3,
          edges_count: 2,
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByText('Topology snapshots by date')).toBeInTheDocument()
    expect(await screen.findByText('2026-02-24')).toBeInTheDocument()
    expect(await screen.findByText('2026-01-01')).toBeInTheDocument()
    await waitFor(() => {
      expect(
        mockGetPoolGraph.mock.calls.some(
          (call) =>
            call[0] === '44444444-4444-4444-4444-444444444444'
            && call[1] === '2026-02-24'
        )
      ).toBe(true)
    })

    await user.click(screen.getByTestId('pool-catalog-topology-snapshot-open-2026-01-01'))

    await waitFor(() => {
      expect(mockGetPoolGraph).toHaveBeenCalledWith(
        '44444444-4444-4444-4444-444444444444',
        '2026-01-01'
      )
    })
  }, SYNC_MODAL_TIMEOUT_MS)

  it('shows publication slot selector and hides legacy document_policy controls', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {
            document_policy: buildMinimalDocumentPolicy(),
          },
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'sale',
            document_policy: buildMinimalDocumentPolicy(),
            custom_edge_key: 'preserve-this',
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-0')).toHaveValue('sale')
    expect(screen.queryByText('Legacy edge document_policy compatibility')).not.toBeInTheDocument()
    expect(screen.queryByTestId('pool-catalog-topology-edge-open-legacy-policy-editor-0')).not.toBeInTheDocument()
    expect(screen.queryByTestId('pool-catalog-topology-edge-migrate-legacy-policy-0')).not.toBeInTheDocument()

    await expandFirstEdgeAdvanced(user)
    expect(await screen.findByTestId('pool-catalog-topology-edge-metadata-0')).toBeInTheDocument()
    expect(screen.queryByTestId('pool-catalog-topology-edge-policy-mode-0')).not.toBeInTheDocument()
    expect(screen.queryByTestId('pool-catalog-topology-edge-policy-0')).not.toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('includes edge document_policy_key in topology upsert payload after preflight', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            custom_edge_key: 'preserve-this',
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    const slotInput = screen.getByTestId('pool-catalog-topology-edge-slot-0')
    await user.clear(slotInput)
    await user.paste('sale')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-initial',
        edges: [
          expect.objectContaining({
            parent_organization_id: '11111111-1111-1111-1111-111111111111',
            child_organization_id: '77777777-7777-7777-7777-777777777777',
            metadata: expect.objectContaining({
              custom_edge_key: 'preserve-this',
              document_policy_key: 'sale',
            }),
          }),
        ],
      })
    )
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('supports edge metadata builder mode and preserves custom metadata keys with slot selector', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'sale',
            custom_edge_key: 'preserve-this',
            custom_nested: { level: 2 },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByDisplayValue('sale')).toBeInTheDocument()
    await expandFirstEdgeAdvanced(user)

    openSelectByTestId('pool-catalog-topology-edge-metadata-mode-0')
    await selectDropdownOption(/builder/i)

    expect(await screen.findByTestId('pool-catalog-topology-edge-metadata-add-field-0')).toBeInTheDocument()
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        edges: [
          expect.objectContaining({
            metadata: expect.objectContaining({
              document_policy_key: 'sale',
              custom_edge_key: 'preserve-this',
              custom_nested: expect.objectContaining({ level: 2 }),
            }),
          }),
        ],
      })
    )
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('preserves existing node and edge metadata when editing edge slot selector', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-with-metadata',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: { node_hint: 'keep-me' },
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: { node_priority: 2 },
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: '10.00',
          max_amount: '20.00',
          metadata: {
            document_policy_key: 'legacy-sale',
            custom_edge_key: 'preserve-this',
            document_policy: buildMinimalDocumentPolicy(),
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(await screen.findByText('Org Two')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    const slotInput = screen.getByTestId('pool-catalog-topology-edge-slot-0')
    await user.clear(slotInput)
    await user.paste('sale')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-with-metadata',
        nodes: expect.arrayContaining([
          expect.objectContaining({
            organization_id: '11111111-1111-1111-1111-111111111111',
            metadata: expect.objectContaining({
              node_hint: 'keep-me',
            }),
          }),
          expect.objectContaining({
            organization_id: '77777777-7777-7777-7777-777777777777',
            metadata: expect.objectContaining({
              node_priority: 2,
            }),
          }),
        ]),
        edges: [
          expect.objectContaining({
            parent_organization_id: '11111111-1111-1111-1111-111111111111',
            child_organization_id: '77777777-7777-7777-7777-777777777777',
            metadata: expect.objectContaining({
              custom_edge_key: 'preserve-this',
              document_policy_key: 'sale',
              document_policy: expect.objectContaining({
                version: 'document_policy.v1',
              }),
            }),
          }),
        ],
      })
    )
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('auto-resolves topology slot coverage when exactly one active binding is available', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(buildPoolWorkflowBindingCollection([
      buildPoolWorkflowBinding({
        decisions: [
          {
            decision_table_id: 'sale-policy',
            decision_key: 'sale',
            decision_revision: 7,
          },
        ],
      }),
    ]))
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'sale',
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByTestId('pool-catalog-topology-coverage-status')).toHaveTextContent('Auto-resolved binding')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-status-0')).toHaveTextContent('Resolved')
    expect(await screen.findByText(/sale-policy r7/i)).toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('shows ambiguous coverage context until operator selects an active binding', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockListPoolWorkflowBindings.mockResolvedValueOnce(buildPoolWorkflowBindingCollection([
      buildPoolWorkflowBinding({
        binding_id: 'binding-sale',
        decisions: [
          {
            decision_table_id: 'sale-policy',
            decision_key: 'sale',
            decision_revision: 2,
          },
        ],
      }),
      buildPoolWorkflowBinding({
        binding_id: 'binding-purchase',
        workflow: {
          workflow_definition_key: 'purchase-publication',
          workflow_revision_id: '22222222-2222-2222-2222-222222222222',
          workflow_revision: 4,
          workflow_name: 'purchase_publication',
        },
        decisions: [
          {
            decision_table_id: 'purchase-policy',
            decision_key: 'purchase',
            decision_revision: 5,
          },
        ],
      }),
    ]))
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'sale',
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByTestId('pool-catalog-topology-coverage-status')).toHaveTextContent('Ambiguous context')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-status-0')).toHaveTextContent('Coverage unavailable')
    expect(screen.getByText('Topology remediation required')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeDisabled()

    openSelectByTestId('pool-catalog-topology-coverage-binding')
    await selectDropdownOption(/binding-sale/i)

    expect(await screen.findByTestId('pool-catalog-topology-coverage-status')).toHaveTextContent('Selected binding')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-status-0')).toHaveTextContent('Resolved')
    expect(await screen.findByText(/sale-policy r2/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByText('Topology remediation required')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeEnabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('enters topology blocking remediation state when graph still contains legacy document_policy payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-legacy',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
        {
          node_version_id: 'node-v2',
          organization_id: '77777777-7777-7777-7777-777777777777',
          inn: '730000000002',
          name: 'Org Two',
          is_root: false,
          metadata: {},
        },
      ],
      edges: [
        {
          edge_version_id: 'edge-v1',
          parent_node_version_id: 'node-v1',
          child_node_version_id: 'node-v2',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'sale',
            document_policy: buildMinimalDocumentPolicy(),
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')

    expect((await screen.findAllByText('Legacy topology remediation required')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/legacy document_policy payload/i).length).toBeGreaterThan(0)
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeDisabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('sends topology version token and shows conflict error without clearing form data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertPoolTopologySnapshot.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Topology Version Conflict',
          status: 409,
          detail: 'stale version token',
          code: 'TOPOLOGY_VERSION_CONFLICT',
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))

    const topologyCard = screen.getByText('Topology snapshot editor').closest('.ant-card')
    expect(topologyCard).toBeTruthy()

    const nodeSelector = topologyCard?.querySelector('.ant-select .ant-select-selector')
    expect(nodeSelector).toBeTruthy()
    fireEvent.mouseDown(nodeSelector as Element)
    fireEvent.click(await screen.findByText('Org One (730000000001)'))

    const rootSwitch = topologyCard?.querySelector('button[role="switch"]')
    expect(rootSwitch).toBeTruthy()
    fireEvent.click(rootSwitch as Element)

    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-initial',
      })
    )
    expect(
      await screen.findByText(
        'Топология уже была изменена другим оператором. Обновите граф и повторите сохранение.'
      )
    ).toBeInTheDocument()
    expect(screen.getAllByText('Org One (730000000001)').length).toBeGreaterThan(0)
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('shows mapped backend domain error for organization upsert and keeps form data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockRejectedValueOnce({
      response: {
        data: {
          success: false,
          error: {
            code: 'DATABASE_ALREADY_LINKED',
            message: 'Database is already linked',
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-org'))
    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000111')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Mapped Error Org')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Выбранная база уже привязана к другой организации.')).toBeInTheDocument()
    expect(screen.getByLabelText('INN')).toHaveValue('730000000111')
    expect(screen.getByLabelText('Name')).toHaveValue('Mapped Error Org')
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('shows problem detail for topology validation error without field-level payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
      ],
      edges: [],
    })
    mockUpsertPoolTopologySnapshot.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          detail: 'Pool graph must have exactly one root node, got 2.',
          code: 'VALIDATION_ERROR',
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText('Pool graph must have exactly one root node, got 2.')
    ).toBeInTheDocument()
    expect(screen.queryByText('Проверьте корректность данных.')).not.toBeInTheDocument()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('shows problem items for topology metadata reference errors', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
      ],
      edges: [],
    })
    mockUpsertPoolTopologySnapshot.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Metadata Reference Validation Error',
          status: 400,
          detail: 'Field mapping validation failed.',
          code: 'POOL_METADATA_REFERENCE_INVALID',
          errors: [
            {
              code: 'POOL_METADATA_REFERENCE_INVALID',
              path: 'edges[0].metadata.document_policy.chains[0].documents[0].field_mapping.Amount',
              detail: "Field 'Amount' is not available for entity 'Document_РеализацияТоваровУслуг'.",
            },
            {
              code: 'POOL_METADATA_REFERENCE_INVALID',
              path: 'edges[1].metadata.document_policy.chains[0].documents[1].field_mapping.BaseDocument',
              detail: "Field 'BaseDocument' is not available for entity 'Document_ПоступлениеТоваровУслуг'.",
            },
          ],
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(/Document policy содержит ссылки на отсутствующие metadata поля\./)
    ).toBeInTheDocument()
    expect(
      await screen.findByText(
        /edges\[0\]\.metadata\.document_policy\.chains\[0\]\.documents\[0\]\.field_mapping\.Amount: Field 'Amount' is not available for entity 'Document_РеализацияТоваровУслуг'/
      )
    ).toBeInTheDocument()
    expect(
      await screen.findByText(
        /edges\[1\]\.metadata\.document_policy\.chains\[0\]\.documents\[1\]\.field_mapping\.BaseDocument: Field 'BaseDocument' is not available for entity 'Document_ПоступлениеТоваровУслуг'/
      )
    ).toBeInTheDocument()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('adds /databases remediation when topology save is blocked by missing metadata context', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [
        {
          node_version_id: 'node-v1',
          organization_id: '11111111-1111-1111-1111-111111111111',
          inn: '730000000001',
          name: 'Org One',
          is_root: true,
          metadata: {},
        },
      ],
      edges: [],
    })
    mockUpsertPoolTopologySnapshot.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Metadata Snapshot Unavailable',
          status: 400,
          detail: 'Current metadata snapshot is missing for selected database scope.',
          code: 'POOL_METADATA_SNAPSHOT_UNAVAILABLE',
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(
        /Metadata context недоступен для topology editor\. Откройте \/databases, перепроверьте configuration identity или обновите metadata snapshot и повторите\./
      )
    ).toBeInTheDocument()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('applies field-level serializer errors to form fields on upsert', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockRejectedValueOnce({
      response: {
        data: {
          success: false,
          error: {
            inn: ['ИНН уже существует'],
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-org'))
    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000001')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Duplicate Org')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Проверьте корректность заполнения полей.')).toBeInTheDocument()
    expect(await screen.findByText('ИНН уже существует')).toBeInTheDocument()
    expect(screen.getByLabelText('INN')).toHaveValue('730000000001')
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('applies field-level validation errors from problem+json payload on upsert', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          detail: 'Organization payload validation failed.',
          code: 'VALIDATION_ERROR',
          errors: {
            inn: ['ИНН уже существует'],
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-org'))
    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000001')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Duplicate Org')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Проверьте корректность данных.')).toBeInTheDocument()
    expect(await screen.findByText('ИНН уже существует')).toBeInTheDocument()
    expect(screen.getByLabelText('INN')).toHaveValue('730000000001')
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('blocks sync submit when preflight validation fails', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"name":"No inn"}]}' },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Строка 1: поле inn обязательно.')).toBeInTheDocument()
    expect(mockSyncOrganizationsCatalog).not.toHaveBeenCalled()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('blocks sync submit when payload exceeds 1000 rows', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    const payload = JSON.stringify({
      rows: Array.from({ length: 1001 }, (_, index) => ({
        inn: `7300${String(index).padStart(8, '0')}`.slice(0, 12),
        name: `Org ${index + 1}`,
      })),
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: payload },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Превышен лимит batch: максимум 1000 строк.')).toBeInTheDocument()
    expect(mockSyncOrganizationsCatalog).not.toHaveBeenCalled()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('shows field-level backend validation errors in sync modal', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockSyncOrganizationsCatalog.mockRejectedValueOnce({
      response: {
        data: {
          success: false,
          error: {
            rows: ['Некорректный формат строки'],
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"inn":"730000000123","name":"Org"}]}' },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Проверьте корректность заполнения полей.')).toBeInTheDocument()
    expect(await screen.findByText('rows: Некорректный формат строки')).toBeInTheDocument()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('runs sync with valid payload and shows stats', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"inn":"730000000123","name":"Synced Org","status":"ACTIVE"}]}' },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    await waitFor(() => expect(mockSyncOrganizationsCatalog).toHaveBeenCalledTimes(1))
    expect(mockSyncOrganizationsCatalog).toHaveBeenCalledWith({
      rows: [
        {
          inn: '730000000123',
          name: 'Synced Org',
          status: 'active',
        },
      ],
    })
    expect(await screen.findByText('Sync completed')).toBeInTheDocument()
    expect(screen.getByText('total_rows:')).toBeInTheDocument()
  }, SYNC_MODAL_TIMEOUT_MS)
})
