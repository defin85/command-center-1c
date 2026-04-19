import { StrictMode, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import type {
  Organization,
  PoolTopologyTemplate,
  PoolWorkflowBinding,
  PoolWorkflowBindingCollection,
} from '../../../api/intercompanyPools'
import { poolMasterDataRegistryResponse } from './poolMasterDataRegistryFixture'
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
const mockListPoolTopologyTemplates = vi.fn()
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
const mockGetPoolMasterDataRegistry = vi.fn()
const mockUseAuthz = vi.fn()
const mockUseDatabases = vi.fn()
const mockUseBindingProfiles = vi.fn()
const mockSyncPoolWorkflowBindings = vi.fn()
const mockGetBindingProfileDetail = vi.fn()

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const { createPoolCatalogAntdTestDouble } = await import('./poolCatalogAntdTestDouble')
  return createPoolCatalogAntdTestDouble(actual)
})

vi.mock('../../../components/platform', () => import('./poolCatalogPlatformTestDouble'))

vi.mock('../../../api/generated/v2/v2', () => ({
  getV2: () => ({
    getDecisionsCollection: (...args: unknown[]) => mockGetDecisionsCollection(...args),
    getPoolsOdataMetadataCatalogGet: (...args: unknown[]) => mockGetPoolODataMetadataCatalog(...args),
    postPoolsOdataMetadataCatalogRefresh: (...args: unknown[]) => mockRefreshPoolODataMetadataCatalog(...args),
  }),
}))

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: (...args: unknown[]) => mockUseDatabases(...args),
}))

vi.mock('../../../api/queries/poolBindingProfiles', () => ({
  useBindingProfiles: (...args: unknown[]) => mockUseBindingProfiles(...args),
}))

vi.mock('../../../api/poolBindingProfiles', () => ({
  getBindingProfileDetail: (...args: unknown[]) => mockGetBindingProfileDetail(...args),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: (...args: unknown[]) => mockUseAuthz(...args),
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
  listPoolTopologyTemplates: (...args: unknown[]) => mockListPoolTopologyTemplates(...args),
  syncOrganizationsCatalog: (...args: unknown[]) => mockSyncOrganizationsCatalog(...args),
  getPoolODataMetadataCatalog: (...args: unknown[]) => mockGetPoolODataMetadataCatalog(...args),
  refreshPoolODataMetadataCatalog: (...args: unknown[]) => mockRefreshPoolODataMetadataCatalog(...args),
  listPoolWorkflowBindings: (...args: unknown[]) => mockListPoolWorkflowBindings(...args),
  upsertPoolWorkflowBinding: (...args: unknown[]) => mockUpsertPoolWorkflowBinding(...args),
  deletePoolWorkflowBinding: (...args: unknown[]) => mockDeletePoolWorkflowBinding(...args),
  migratePoolEdgeDocumentPolicy: (...args: unknown[]) => mockMigratePoolEdgeDocumentPolicy(...args),
  getPoolMasterDataRegistry: (...args: unknown[]) => mockGetPoolMasterDataRegistry(...args),
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

const thirdOrganization: Organization = {
  ...baseOrganization,
  id: '99999999-9999-9999-9999-999999999999',
  database_id: 'aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb',
  name: 'Org Three',
  full_name: 'Org Three LLC',
  inn: '730000000003',
}

const fourthOrganization: Organization = {
  ...baseOrganization,
  id: '12121212-1212-1212-1212-121212121212',
  database_id: 'cccccccc-1111-2222-3333-dddddddddddd',
  name: 'Org Four',
  full_name: 'Org Four LLC',
  inn: '730000000004',
}

const fifthOrganization: Organization = {
  ...baseOrganization,
  id: '34343434-3434-3434-3434-343434343434',
  database_id: 'eeeeeeee-1111-2222-3333-ffffffffffff',
  name: 'Org Five',
  full_name: 'Org Five LLC',
  inn: '730000000005',
}

let initialCatalogLoadPromise: Promise<void> | null = null

function buildPoolWorkflowBinding(overrides: Partial<PoolWorkflowBinding> = {}): PoolWorkflowBinding {
  const workflow = overrides.workflow ?? {
    workflow_definition_key: 'services-publication',
    workflow_revision_id: '11111111-1111-1111-1111-111111111111',
    workflow_revision: 3,
    workflow_name: 'services_publication',
  }
  const decisions = overrides.decisions ?? [
    {
      decision_table_id: 'decision-1',
      decision_key: 'document_policy',
      slot_key: 'document_policy',
      decision_revision: 4,
    },
  ]
  const parameters = overrides.parameters ?? { publication_variant: 'full' }
  const roleMapping = overrides.role_mapping ?? { initiator: 'finance' }

  return {
    binding_id: 'binding-top-down',
    pool_id: 'pool-1',
    revision: 1,
    workflow,
    decisions,
    parameters,
    role_mapping: roleMapping,
    binding_profile_id: 'bp-services',
    binding_profile_revision_id: 'bp-rev-services-r2',
    binding_profile_revision_number: 2,
    resolved_profile: {
      binding_profile_id: 'bp-services',
      code: 'services-publication-profile',
      name: 'Services Publication Profile',
      status: 'active',
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_revision_number: 2,
      workflow,
      decisions,
      parameters,
      role_mapping: roleMapping,
    },
    profile_lifecycle_warning: null,
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

function buildBindingProfileSummary(overrides: Record<string, unknown> = {}) {
  const workflow = {
    workflow_definition_key: 'services-publication',
    workflow_revision_id: 'wf-services-r2',
    workflow_revision: 4,
    workflow_name: 'services_publication',
  }

  return {
    binding_profile_id: 'bp-services',
    code: 'services-publication-profile',
    name: 'Services Publication Profile',
    description: 'Reusable publication scheme',
    status: 'active',
    latest_revision_number: 2,
    latest_revision: {
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_id: 'bp-services',
      revision_number: 2,
      workflow,
      decisions: [
        {
          decision_table_id: 'decision-1',
          decision_key: 'document_policy',
          slot_key: 'document_policy',
          decision_revision: 4,
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
      created_at: '2026-01-01T00:00:00Z',
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    ...overrides,
  }
}

function buildBindingProfileDetail(overrides: Record<string, unknown> = {}) {
  const summary = buildBindingProfileSummary(overrides)
  const latestRevision = summary.latest_revision as Record<string, unknown>
  const revisions = [
    latestRevision,
    {
      ...latestRevision,
      binding_profile_revision_id: 'bp-rev-services-r1',
      revision_number: 1,
      workflow: {
        ...(latestRevision.workflow as Record<string, unknown>),
        workflow_revision: 3,
        workflow_revision_id: 'wf-services-r1',
      },
    },
  ]
  return {
    ...summary,
    revisions,
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

function buildTopologyTemplate(overrides: Partial<PoolTopologyTemplate> = {}): PoolTopologyTemplate {
  const latestRevision = {
    topology_template_revision_id: 'template-revision-r3',
    topology_template_id: 'template-1',
    revision_number: 3,
    nodes: [
      {
        slot_key: 'root',
        label: 'Root slot',
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
    created_at: '2026-01-02T00:00:00Z',
  }

  return {
    topology_template_id: 'template-1',
    code: 'top-down-template',
    name: 'Top Down Template',
    description: 'Reusable multi-stage topology',
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
        created_at: '2026-01-01T00:00:00Z',
      },
    ],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
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
  await waitFor(() => {
    expect(mockListOrganizations).toHaveBeenCalled()
    expect(mockGetOrganization).toHaveBeenCalled()
    expect(mockListOrganizationPools).toHaveBeenCalled()
    expect(mockGetPoolGraph).toHaveBeenCalled()
    expect(mockListPoolTopologySnapshots).toHaveBeenCalled()
  })
}

async function waitForOrganizationsCatalogLoad() {
  await waitFor(() => {
    expect(mockListOrganizations).toHaveBeenCalled()
    expect(mockGetOrganization).toHaveBeenCalled()
    expect(mockListOrganizationPools).toHaveBeenCalled()
  })
}

function renderPage(initialEntry = '/pools/catalog?tab=organizations', options?: { strict?: boolean }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })

  const tree = (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[initialEntry]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <ConfigProvider
          theme={{ token: { motion: false } }}
          wave={{ disabled: true }}
        >
          <AntApp>
            <PoolCatalogPage />
            <LocationProbe />
          </AntApp>
        </ConfigProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )

  const result = render(options?.strict ? <StrictMode>{tree}</StrictMode> : tree)
  initialCatalogLoadPromise = waitForInitialCatalogLoad()
  return result
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="pool-catalog-location">{`${location.pathname}${location.search}`}</div>
}

function openSelectByTestId(testId: string) {
  const select = screen.getByTestId(testId)
  const trigger = select.querySelector('.ant-select-selector') as HTMLElement | null
  fireEvent.mouseDown(trigger ?? select)
}

async function selectDropdownOption(label: string | RegExp) {
  const options = Array.from(document.querySelectorAll('.ant-select-item-option'))
  const optionTexts = options.map((node) => node.textContent || '')
  const option = [...options]
    .reverse()
    .find((node) => {
      const textContent = node.textContent || ''
      return typeof label === 'string' ? textContent.includes(label) : label.test(textContent)
    })
  expect(
    option,
    `label=${String(label)} dropdownOptions=${JSON.stringify(optionTexts)}`
  ).toBeTruthy()
  fireEvent.click(option as Element)
}

async function openWorkspaceTab(tabLabel: 'Organizations' | 'Pools' | 'Bindings' | 'Topology Editor') {
  await initialCatalogLoadPromise
  expect(await screen.findByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')
  const tab = screen.getByRole('tab', { name: tabLabel })
  if (tab.getAttribute('aria-selected') !== 'true') {
    fireEvent.click(tab)
  }
  if (tabLabel === 'Organizations') {
    await screen.findByTestId('pool-catalog-add-org')
    return
  }
  if (tabLabel === 'Pools') {
    await screen.findByText('Pools management')
    return
  }
  if (tabLabel === 'Bindings') {
    await screen.findByText('Workflow attachment workspace')
    if (!screen.queryByTestId('pool-catalog-bindings-drawer')) {
      expect(await screen.findByTestId('pool-catalog-open-bindings-workspace')).toBeEnabled()
      fireEvent.click(screen.getByTestId('pool-catalog-open-bindings-workspace'))
      await screen.findByTestId('pool-catalog-bindings-drawer', undefined, { timeout: 5000 })
    }
    return
  }
  await screen.findByTestId('pool-catalog-topology-save')
}

async function openOrganizationsWorkspace() {
  await waitForOrganizationsCatalogLoad()
  const tab = screen.getByRole('tab', { name: 'Organizations' })
  if (tab.getAttribute('aria-selected') !== 'true') {
    fireEvent.click(tab)
  }
  await screen.findByTestId('pool-catalog-add-org')
}

async function findOrganizationDrawer() {
  return screen.findByTestId('pool-catalog-organization-drawer')
}

const EXTENDED_UI_TEST_TIMEOUT_MS = 60000
const TOPOLOGY_EDITOR_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS
const SYNC_MODAL_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS

function createAuthzValue(overrides: Partial<{ isStaff: boolean; isLoading: boolean }> = {}) {
  return {
    isStaff: false,
    isLoading: false,
    canDatabase: vi.fn(() => false),
    canCluster: vi.fn(() => false),
    canTemplate: vi.fn(() => false),
    canAnyDatabase: vi.fn(() => false),
    canAnyCluster: vi.fn(() => false),
    canAnyTemplate: vi.fn(() => false),
    getDatabaseLevel: vi.fn(() => null),
    getClusterLevel: vi.fn(() => null),
    getTemplateLevel: vi.fn(() => null),
    ...overrides,
  }
}

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
    mockListPoolTopologyTemplates.mockReset()
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
    mockGetPoolMasterDataRegistry.mockReset()
    mockUseAuthz.mockReset()
    mockUseDatabases.mockReset()
    mockUseBindingProfiles.mockReset()
    mockSyncPoolWorkflowBindings.mockReset()
    mockGetBindingProfileDetail.mockReset()

    mockUseAuthz.mockReturnValue(createAuthzValue())
    mockUseDatabases.mockReturnValue({
      data: {
        databases: [
          { id: '22222222-2222-2222-2222-222222222222', name: 'db1' },
          { id: '33333333-3333-3333-3333-333333333333', name: 'db2' },
          { id: 'aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb', name: 'db3' },
          { id: 'cccccccc-1111-2222-3333-dddddddddddd', name: 'db4' },
          { id: 'eeeeeeee-1111-2222-3333-ffffffffffff', name: 'db5' },
        ],
      },
      isLoading: false,
    })
    mockUseBindingProfiles.mockReturnValue({
      data: {
        binding_profiles: [buildBindingProfileSummary()],
        count: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    mockGetBindingProfileDetail.mockImplementation(async (bindingProfileId: string) => ({
      binding_profile: buildBindingProfileDetail({ binding_profile_id: bindingProfileId }),
    }))

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
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
    mockListPoolTopologyTemplates.mockResolvedValue([buildTopologyTemplate()])
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
    mockGetPoolMasterDataRegistry.mockResolvedValue(poolMasterDataRegistryResponse)
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

  it('enters topology blocking remediation state when graph still contains legacy document_policy payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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

    renderPage('/pools/catalog?tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab('Topology Editor')

    expect((await screen.findAllByText('Legacy topology remediation required')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/legacy document_policy payload/i).length).toBeGreaterThan(0)
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeDisabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('sends topology version token and shows conflict error without clearing form data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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

    renderPage('/pools/catalog?tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab('Topology Editor')
    openSelectByTestId('pool-catalog-topology-authoring-mode')
    await selectDropdownOption('Manual snapshot editor')
    fireEvent.click(screen.getByTestId('pool-catalog-topology-add-node'))

    const topologyCard = screen.getByText('Topology snapshot editor').closest('.ant-card')
    expect(topologyCard).toBeTruthy()

    const nodeSelectors = topologyCard?.querySelectorAll('.ant-select .ant-select-selector')
    const nodeSelector = nodeSelectors?.[nodeSelectors.length - 1] ?? null
    expect(nodeSelector).toBeTruthy()
    fireEvent.mouseDown(nodeSelector as Element)
    fireEvent.click(await screen.findByText('Org One (730000000001)'))

    const rootSwitch = topologyCard?.querySelector('button[role="switch"]')
    expect(rootSwitch).toBeTruthy()
    fireEvent.click(rootSwitch as Element)

    fireEvent.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-initial',
      })
    )
    expect(
      await screen.findByText(
        'Topology was changed by another operator. Refresh the graph and try saving again.'
      )
    ).toBeInTheDocument()
    expect(screen.getAllByText('Org One (730000000001)').length).toBeGreaterThan(0)
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('shows mapped backend domain error for organization upsert and keeps form data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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

    renderPage('/pools/catalog?tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-add-org'))
    const drawer = await findOrganizationDrawer()
    const drawerQueries = within(drawer)
    fireEvent.change(drawerQueries.getByLabelText('INN'), { target: { value: '730000000111' } })
    fireEvent.change(drawerQueries.getByLabelText('Name'), { target: { value: 'Mapped Error Org' } })

    fireEvent.click(drawerQueries.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('The selected database is already linked to another organization.')).toBeInTheDocument()
    expect(drawerQueries.getByLabelText('INN')).toHaveValue('730000000111')
    expect(drawerQueries.getByLabelText('Name')).toHaveValue('Mapped Error Org')
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('shows problem detail for topology validation error without field-level payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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

    renderPage('/pools/catalog?tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab('Topology Editor')
    fireEvent.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText('Pool graph must have exactly one root node, got 2.')
    ).toBeInTheDocument()
    expect(screen.queryByText('Check the entered data.')).not.toBeInTheDocument()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('shows problem items for topology metadata reference errors', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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

    renderPage('/pools/catalog?tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab('Topology Editor')
    fireEvent.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(/Document policy references metadata fields that do not exist\./)
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
    await initialCatalogLoadPromise

    await openWorkspaceTab('Topology Editor')
    fireEvent.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(
      await screen.findByText(
        /Metadata context недоступен для topology editor\. Откройте \/databases, перепроверьте configuration identity или обновите metadata snapshot и повторите\./
      )
    ).toBeInTheDocument()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('applies field-level serializer errors to form fields on upsert', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-add-org'))
    const drawer = await findOrganizationDrawer()
    const drawerQueries = within(drawer)
    fireEvent.change(drawerQueries.getByLabelText('INN'), { target: { value: '730000000001' } })
    fireEvent.change(drawerQueries.getByLabelText('Name'), { target: { value: 'Duplicate Org' } })
    fireEvent.click(drawerQueries.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Check the highlighted fields.')).toBeInTheDocument()
    expect(await screen.findByText('ИНН уже существует')).toBeInTheDocument()
    expect(drawerQueries.getByLabelText('INN')).toHaveValue('730000000001')
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('applies field-level validation errors from problem+json payload on upsert', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-add-org'))
    const drawer = await findOrganizationDrawer()
    const drawerQueries = within(drawer)
    fireEvent.change(drawerQueries.getByLabelText('INN'), { target: { value: '730000000001' } })
    fireEvent.change(drawerQueries.getByLabelText('Name'), { target: { value: 'Duplicate Org' } })
    fireEvent.click(drawerQueries.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Check the entered data.')).toBeInTheDocument()
    expect(await screen.findByText('ИНН уже существует')).toBeInTheDocument()
    expect(drawerQueries.getByLabelText('INN')).toHaveValue('730000000001')
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('blocks sync submit when preflight validation fails', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    renderPage()
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"name":"No inn"}]}' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Row 1: inn is required.')).toBeInTheDocument()
    expect(mockSyncOrganizationsCatalog).not.toHaveBeenCalled()
  }, EXTENDED_UI_TEST_TIMEOUT_MS)

  it('blocks sync submit when payload exceeds 1000 rows', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    const payload = JSON.stringify({
      rows: Array.from({ length: 1001 }, (_, index) => ({
        inn: `7300${String(index).padStart(8, '0')}`.slice(0, 12),
        name: `Org ${index + 1}`,
      })),
    })

    renderPage()
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: payload },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Batch limit exceeded: maximum 1000 rows.')).toBeInTheDocument()
    expect(mockSyncOrganizationsCatalog).not.toHaveBeenCalled()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('shows field-level backend validation errors in sync modal', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

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
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"inn":"730000000123","name":"Org"}]}' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Check the highlighted fields.')).toBeInTheDocument()
    expect(await screen.findByText('rows: Некорректный формат строки')).toBeInTheDocument()
  }, SYNC_MODAL_TIMEOUT_MS)

  it('runs sync with valid payload and shows stats', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    renderPage()
    await initialCatalogLoadPromise
    await openOrganizationsWorkspace()

    fireEvent.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"inn":"730000000123","name":"Synced Org","status":"ACTIVE"}]}' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Run sync' }))

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
