import { StrictMode, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp, ConfigProvider } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import type {
  Organization,
  PoolTopologyTemplate,
  PoolWorkflowBinding,
  PoolWorkflowBindingCollection,
} from '../../../api/intercompanyPools'
import { HEAVY_ROUTE_TEST_TIMEOUT_MS } from '../../../test/timeouts'
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
      topology_template_compatibility: {
        status: 'compatible',
        topology_aware_ready: true,
        covered_slot_keys: ['document_policy'],
        diagnostics: [],
      },
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
      topology_template_compatibility: {
        status: 'compatible',
        topology_aware_ready: true,
        covered_slot_keys: ['document_policy'],
        diagnostics: [],
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

async function waitForInitialCatalogLoad() {
  await waitFor(() => expect(mockListOrganizations).toHaveBeenCalled())
  await waitFor(() => expect(mockGetOrganization).toHaveBeenCalled())
  await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalled())
  await waitFor(() => expect(mockGetPoolGraph).toHaveBeenCalled())
  await waitFor(() => expect(mockListPoolTopologySnapshots).toHaveBeenCalled())
}

function renderPage(initialEntry = '/pools/catalog?tab=bindings', options?: { strict?: boolean }) {
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

async function openWorkspaceTab(
  user: ReturnType<typeof userEvent.setup>,
  tabLabel: 'Organizations' | 'Pools' | 'Bindings' | 'Topology Editor'
) {
  await initialCatalogLoadPromise
  await waitFor(() => {
    expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')
  })
  const tab = screen.getByRole('tab', { name: tabLabel })
  if (tab.getAttribute('aria-selected') !== 'true') {
    await user.click(tab)
  }
  if (tabLabel === 'Organizations') {
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-add-org')).toBeInTheDocument()
    })
    return
  }
  if (tabLabel === 'Pools') {
    await screen.findByText('Pools management')
    return
  }
  if (tabLabel === 'Bindings') {
    await screen.findByText('Workflow attachment workspace')
    if (!screen.queryByTestId('pool-catalog-bindings-drawer')) {
      await waitFor(() => {
        expect(screen.getByTestId('pool-catalog-open-bindings-workspace')).toBeEnabled()
      })
      fireEvent.click(screen.getByTestId('pool-catalog-open-bindings-workspace'))
      await waitFor(() => {
        expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('tab=bindings')
      })
      await screen.findByTestId('pool-catalog-bindings-drawer', undefined, { timeout: 5000 })
    }
    return
  }
  await screen.findByText('Topology snapshots by date')
  await waitFor(() => {
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeInTheDocument()
  })
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

  it('renders existing workflow attachments in isolated workspace and keeps pool drawer focused on pool fields', async () => {
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')

    expect(screen.queryByLabelText('Workflow bindings JSON')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(mockListPoolWorkflowBindings).toHaveBeenCalledWith('44444444-4444-4444-4444-444444444444')
    })
    expect(screen.getByText('Workflow attachment workspace')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-workflow-binding-card-0')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-workflow-binding-card-1')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-workflow-binding-profile-summary-0')).toHaveTextContent(
      'services-publication-profile'
    )
    expect(screen.getByTestId('pool-catalog-workflow-binding-workflow-key-0')).toHaveTextContent(
      'services-publication'
    )
    expect(screen.getByTestId('pool-catalog-workflow-binding-workflow-key-1')).toHaveTextContent(
      'bottom-up-import'
    )
    expect(screen.getByTestId('pool-catalog-workflow-binding-summary-0')).toHaveTextContent(
      'direction=top_down'
    )
    expect(screen.getByTestId('pool-catalog-workflow-binding-summary-1')).toHaveTextContent(
      'tags=cutover, monthly'
    )

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-pool-drawer')).toBeVisible()
    })
    const dialog = screen.getByTestId('pool-catalog-pool-drawer')
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
    await initialCatalogLoadPromise

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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockSyncPoolWorkflowBindings).not.toHaveBeenCalled()
    expect(mockUpsertPoolWorkflowBinding).not.toHaveBeenCalled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('shows stale collection conflict without clearing edited workflow attachment form', async () => {
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    await waitFor(() => {
      expect(mockListPoolWorkflowBindings).toHaveBeenCalledWith('44444444-4444-4444-4444-444444444444')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-workflow-binding-selector-tags-0')).toHaveValue('baseline')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-save-bindings')).toBeEnabled()
    })
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-selector-tags-0'), {
      target: { value: 'baseline, conflicted' },
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
          binding_profile_revision_id: 'bp-rev-services-r2',
          selector: expect.objectContaining({
            direction: 'top_down',
            mode: 'safe',
            tags: ['baseline', 'conflicted'],
          }),
        }),
      ],
    })
    expect(
      screen.getByTestId('pool-catalog-workflow-binding-selector-tags-0')
    ).toHaveValue('baseline, conflicted')
    expect(screen.getByText('Workflow attachment workspace')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('submits workflow attachments from isolated workspace via profile revision selection', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    openSelectByTestId('pool-catalog-workflow-binding-profile-revision-0')
    await selectDropdownOption('services-publication-profile · Services Publication Profile · r2 · active')
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
    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    expect(mockUpsertOrganizationPool).not.toHaveBeenCalled()
    await waitFor(() => expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledTimes(1))
    expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledWith({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:test-etag',
      nextBindings: [
        expect.objectContaining({
          binding_profile_revision_id: 'bp-rev-services-r2',
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
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('lists reusable profile revisions from dedicated catalog and offers handoff for reusable logic edits', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    try {
      mockUseBindingProfiles.mockReturnValue({
        data: {
          binding_profiles: [
            buildBindingProfileSummary(),
            buildBindingProfileSummary({
              binding_profile_id: 'bp-legacy',
              code: 'legacy-archive-profile',
              name: 'Legacy Archive Profile',
              status: 'deactivated',
              latest_revision_number: 1,
              latest_revision: {
                binding_profile_revision_id: 'bp-rev-legacy-r1',
                binding_profile_id: 'bp-legacy',
                revision_number: 1,
                workflow: {
                  workflow_definition_key: 'legacy-publication',
                  workflow_revision_id: 'wf-legacy-r1',
                  workflow_revision: 1,
                  workflow_name: 'legacy_publication',
                },
                decisions: [],
                parameters: {},
                role_mapping: {},
                metadata: { source: 'manual' },
                topology_template_compatibility: {
                  status: 'compatible',
                  topology_aware_ready: true,
                  covered_slot_keys: ['document_policy'],
                  diagnostics: [],
                },
                created_at: '2026-01-01T00:00:00Z',
              },
            }),
          ],
          count: 2,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderPage()
      await initialCatalogLoadPromise

      await openWorkspaceTab(user, 'Bindings')
      await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
      openSelectByTestId('pool-catalog-workflow-binding-profile-revision-0')
      expect(await screen.findByText('services-publication-profile · Services Publication Profile · r2 · active')).toBeInTheDocument()
      expect(screen.getByText('legacy-archive-profile · Legacy Archive Profile · r1 · deactivated')).toBeInTheDocument()

      await selectDropdownOption('services-publication-profile · Services Publication Profile · r2 · active')
      expect(await screen.findByTestId('pool-catalog-workflow-binding-profile-summary-0')).toHaveTextContent(
        'services-publication-profile'
      )
      expect(screen.getByTestId('pool-catalog-workflow-binding-handoff-0').tagName).toBe('BUTTON')
      expect(
        consoleErrorSpy.mock.calls.some((call) => (
          call.some((argument) => typeof argument === 'string' && argument.includes('Encountered two children with the same key'))
        )),
      ).toBe(false)
    } finally {
      consoleErrorSpy.mockRestore()
    }
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('does not prefetch every binding profile detail before the operator opens a revision selector', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUseBindingProfiles.mockReturnValue({
      data: {
        binding_profiles: [
          buildBindingProfileSummary(),
          buildBindingProfileSummary({
            binding_profile_id: 'bp-legacy',
            code: 'legacy-archive-profile',
            name: 'Legacy Archive Profile',
          }),
        ],
        count: 2,
      },
      isLoading: false,
      isError: false,
      error: null,
    })

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    expect(mockGetBindingProfileDetail).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    openSelectByTestId('pool-catalog-workflow-binding-profile-revision-0')

    await waitFor(() => expect(mockGetBindingProfileDetail).toHaveBeenCalledTimes(2))
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('allows attaching an explicit non-latest profile revision from catalog detail', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUseBindingProfiles.mockReturnValue({
      data: {
        binding_profiles: [buildBindingProfileSummary()],
        count: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    mockGetBindingProfileDetail.mockImplementation(async () => ({
      binding_profile: {
        ...buildBindingProfileDetail(),
        revisions: [
          {
            binding_profile_revision_id: 'bp-rev-services-r2',
            binding_profile_id: 'bp-services',
            revision_number: 2,
            workflow: {
              workflow_definition_key: 'services-publication',
              workflow_revision_id: 'wf-services-r2',
              workflow_revision: 4,
              workflow_name: 'services_publication',
            },
            decisions: [],
            parameters: {},
            role_mapping: {},
            metadata: { source: 'manual' },
            created_at: '2026-01-02T00:00:00Z',
          },
          {
            binding_profile_revision_id: 'bp-rev-services-r1',
            binding_profile_id: 'bp-services',
            revision_number: 1,
            workflow: {
              workflow_definition_key: 'services-publication',
              workflow_revision_id: 'wf-services-r1',
              workflow_revision: 3,
              workflow_name: 'services_publication',
            },
            decisions: [],
            parameters: {},
            role_mapping: {},
            metadata: { source: 'manual' },
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
      },
    }))

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    openSelectByTestId('pool-catalog-workflow-binding-profile-revision-0')
    expect(await screen.findByText('services-publication-profile · Services Publication Profile · r1 · active')).toBeInTheDocument()

    await selectDropdownOption('services-publication-profile · Services Publication Profile · r1 · active')
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-effective-from-0'), {
      target: { value: '2026-01-01' },
    })
    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    await waitFor(() => expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledTimes(1))
    expect(mockSyncPoolWorkflowBindings).toHaveBeenCalledWith({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:test-etag',
      nextBindings: [
        expect.objectContaining({
          binding_profile_revision_id: 'bp-rev-services-r1',
        }),
      ],
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('keeps pinned reusable profile visible even when it is no longer the catalog latest revision', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    const existingBinding = buildPoolWorkflowBinding({
      binding_profile_id: 'bp-legacy',
      binding_profile_revision_id: 'bp-rev-legacy-r1',
      binding_profile_revision_number: 1,
      resolved_profile: {
        binding_profile_id: 'bp-legacy',
        code: 'legacy-archive-profile',
        name: 'Legacy Archive Profile',
        status: 'deactivated',
        binding_profile_revision_id: 'bp-rev-legacy-r1',
        binding_profile_revision_number: 1,
        workflow: {
          workflow_definition_key: 'legacy-publication',
          workflow_revision_id: 'wf-legacy-r1',
          workflow_revision: 1,
          workflow_name: 'legacy_publication',
        },
        decisions: [],
        parameters: {},
        role_mapping: {},
      },
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
    mockUseBindingProfiles.mockReturnValue({
      data: {
        binding_profiles: [buildBindingProfileSummary()],
        count: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    })

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    expect(await screen.findByTestId('pool-catalog-workflow-binding-profile-summary-0')).toHaveTextContent(
      'legacy-archive-profile'
    )
    expect(screen.getByTestId('pool-catalog-workflow-binding-profile-status-0')).toHaveTextContent('deactivated')
    openSelectByTestId('pool-catalog-workflow-binding-profile-revision-0')
    expect(await screen.findAllByText('legacy-archive-profile · Legacy Archive Profile · r1 · current')).not.toHaveLength(0)
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('shows topology slot coverage summary in bindings workspace', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListPoolWorkflowBindings.mockResolvedValueOnce(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'sale-policy',
              decision_key: 'document_policy',
              slot_key: 'sale',
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-workflow-binding-profile-summary-0')).toBeInTheDocument()
    }, { timeout: 3000 })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-0')).toBeInTheDocument()
    }, { timeout: 3000 })
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-0')).toHaveTextContent('edges: 2')
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-0')).toHaveTextContent('resolved: 1')
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-0')).toHaveTextContent('missing slot: 1')
    expect(screen.getByText('Binding remediation required')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-save-bindings')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-workflow-binding-slot-coverage-0-0')).toHaveTextContent('edges: 1')
    expect(screen.getByTestId('pool-catalog-workflow-binding-coverage-item-0-0')).toHaveTextContent(
      'Org One -> Org Three · purchase · Slot missing'
    )
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

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
    await initialCatalogLoadPromise

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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')

    expect(await screen.findByText('Legacy workflow bindings remediation required')).toBeInTheDocument()
    expect(
      screen.getByText('Canonical binding collection is empty while legacy metadata payload is still present.')
    ).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-save-bindings')).toBeDisabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('surfaces execution-pack topology remediation with diagnostics and canonical handoff', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListPoolWorkflowBindings.mockResolvedValueOnce(buildPoolWorkflowBindingCollection([], {
      collection_etag: 'sha256:template-remediation',
      blocking_remediation: {
        code: 'EXECUTION_PACK_TEMPLATE_INCOMPATIBLE',
        title: 'Execution pack remediation required',
        detail: 'Pinned execution pack still uses concrete participant refs.',
        errors: [
          {
            code: 'EXECUTION_PACK_TEMPLATE_INCOMPATIBLE',
            slot_key: 'document_policy',
            decision_table_id: 'decision-1',
            decision_revision: 4,
            field_or_table_path: 'documents[0].field_mappings.counterparty',
            detail: 'Use topology-aware aliases instead of concrete refs.',
          },
        ],
      },
    }))

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')

    expect(await screen.findByText('Execution pack remediation required')).toBeInTheDocument()
    expect(screen.getByText('Pinned execution pack still uses concrete participant refs.')).toBeInTheDocument()
    expect(screen.getByText(/slot document_policy/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Open execution packs' }).length).toBeGreaterThan(0)
    expect(screen.getByTestId('pool-catalog-save-bindings')).toBeDisabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('blocks save when workflow attachment is missing binding_profile_revision_id', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Bindings')
    await user.click(screen.getByTestId('pool-catalog-workflow-binding-add'))
    fireEvent.change(screen.getByTestId('pool-catalog-workflow-binding-effective-from-0'), {
      target: { value: '2026-01-01' },
    })

    await user.click(screen.getByTestId('pool-catalog-save-bindings'))

    expect(
      await screen.findByText('Attachment #1: binding_profile_revision_id is required.')
    ).toBeInTheDocument()
    expect(mockUpsertOrganizationPool).not.toHaveBeenCalled()
  }, SYNC_MODAL_TIMEOUT_MS)
})
