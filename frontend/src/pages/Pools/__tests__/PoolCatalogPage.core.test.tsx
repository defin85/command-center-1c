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

async function waitForInitialCatalogLoad() {
  await waitFor(() => expect(mockListOrganizations).toHaveBeenCalled())
  await waitFor(() => expect(mockGetOrganization).toHaveBeenCalled())
  await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalled())
  await waitFor(() => expect(mockGetPoolGraph).toHaveBeenCalled())
  await waitFor(() => expect(mockListPoolTopologySnapshots).toHaveBeenCalled())
}

function renderPage(initialEntry = '/pools/catalog', options?: { strict?: boolean }) {
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

async function findDialogByName(name: string | RegExp) {
  return screen.findByRole('dialog', { name })
}

const EXTENDED_UI_TEST_TIMEOUT_MS = 60000
const TOPOLOGY_EDITOR_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS

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

  it('disables mutating controls for staff without active tenant', async () => {
    mockUseAuthz.mockReturnValue(createAuthzValue({ isStaff: true }))
    const user = userEvent.setup()

    renderPage()

    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Organizations')
    expect(screen.getAllByText('Mutating actions are disabled').length).toBeGreaterThan(0)
    expect(screen.getByTestId('pool-catalog-add-org')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-edit-org')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeDisabled()
  })

  it('keeps mutating controls enabled for non-staff without active tenant', async () => {
    mockUseAuthz.mockReturnValue(createAuthzValue({ isStaff: false }))
    const user = userEvent.setup()

    renderPage()

    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Organizations')
    expect(screen.getByTestId('pool-catalog-add-org')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeEnabled()
  })

  it('keeps mutating controls enabled for staff with tenant from shell local storage', async () => {
    mockUseAuthz.mockReturnValue(createAuthzValue({ isStaff: true }))
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()

    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Organizations')
    expect(screen.getByTestId('pool-catalog-add-org')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeEnabled()
  })

  it('deduplicates initial catalog reads in StrictMode and resolves the default graph date before the first graph fetch', async () => {
    renderPage('/pools/catalog', { strict: true })

    await initialCatalogLoadPromise

    await waitFor(() => {
      expect(mockListOrganizations).toHaveBeenCalledTimes(1)
      expect(mockGetOrganization).toHaveBeenCalledTimes(1)
      expect(mockListOrganizationPools).toHaveBeenCalledTimes(1)
      expect(mockListPoolTopologySnapshots).toHaveBeenCalledTimes(1)
      expect(mockGetPoolGraph).toHaveBeenCalledTimes(1)
    })

    expect(mockGetPoolGraph).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      '2026-01-01',
    )
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

    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Organizations')
    await user.click(screen.getByTestId('pool-catalog-add-org'))
    const drawer = await findDialogByName('Add organization')
    const drawerQueries = within(drawer)

    await user.clear(drawerQueries.getByLabelText('INN'))
    await user.type(drawerQueries.getByLabelText('INN'), '730000000999')
    await user.clear(drawerQueries.getByLabelText('Name'))
    await user.type(drawerQueries.getByLabelText('Name'), 'Created Org')

    await user.click(drawerQueries.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(mockUpsertOrganization).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganization).toHaveBeenCalledWith(
      expect.objectContaining({
        inn: '730000000999',
        name: 'Created Org',
      })
    )
    await waitFor(() => expect(mockListOrganizations).toHaveBeenCalledTimes(2))
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

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

    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Organizations')
    expect(await screen.findByText(baseOrganization.database_id as string)).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-edit-org'))
    const drawer = await findDialogByName('Edit organization')
    await user.click(within(drawer).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(mockUpsertOrganization).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(nextDatabaseId)).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-add-pool'))
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-pool-drawer')).toBeVisible()
    })
    const drawer = screen.getByTestId('pool-catalog-pool-drawer')
    const drawerQueries = within(drawer)
    const codeInput = drawerQueries.getByPlaceholderText('pool-main')
    const nameInput = drawerQueries.getByPlaceholderText('Main intercompany pool')
    const descriptionInput = drawerQueries.getByPlaceholderText('Optional')
    await user.clear(codeInput)
    await user.type(codeInput, 'pool-2')
    await user.clear(nameInput)
    await user.type(nameInput, 'Pool Two')
    await user.clear(descriptionInput)
    await user.type(descriptionInput, 'Second pool')
    await user.click(drawerQueries.getByTestId('pool-catalog-save-pool'))

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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-pool-drawer')).toBeVisible()
    })
    const drawer = screen.getByTestId('pool-catalog-pool-drawer')
    const drawerQueries = within(drawer)
    const nameInput = drawerQueries.getByPlaceholderText('Main intercompany pool')
    await user.clear(nameInput)
    await user.type(nameInput, 'Pool One Updated')
    await user.click(drawerQueries.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One Updated',
      })
    )
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('restores selected pool and attachment workspace from query params', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=bindings')
    await initialCatalogLoadPromise
    expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')

    await waitFor(() => {
      expect(mockListPoolWorkflowBindings).toHaveBeenCalledWith('44444444-4444-4444-4444-444444444444')
    })

    expect(await screen.findByTestId('pool-catalog-bindings-drawer')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('pool_id=44444444-4444-4444-4444-444444444444')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('tab=bindings')
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('keeps selected pool and active workspace tab in the URL when the operator switches tasks', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    await initialCatalogLoadPromise
    expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')

    await openWorkspaceTab(user, 'Bindings')
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('pool_id=44444444-4444-4444-4444-444444444444')
    })
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('tab=bindings')

    await openWorkspaceTab(user, 'Topology Editor')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('tab=topology')
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('keeps the newly selected pool stable instead of bouncing back to the previous route pool', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    mockListOrganizationPools.mockResolvedValueOnce([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: '55555555-5555-5555-5555-555555555555',
        code: 'pool-2',
        name: 'Pool Two',
        description: 'Secondary pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-02T00:00:00Z',
      },
    ])
    mockGetPoolGraph.mockImplementation(async (poolId: string) => ({
      pool_id: poolId,
      date: '2026-01-01',
      version: `v1:${poolId}`,
      nodes: [],
      edges: [],
    }))
    mockListPoolTopologySnapshots.mockImplementation(async (poolId: string) => ({
      pool_id: poolId,
      count: 1,
      snapshots: [
        {
          effective_from: '2026-01-01',
          effective_to: null,
          nodes_count: 0,
          edges_count: 0,
        },
      ],
    }))

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=pools')
    await initialCatalogLoadPromise

    expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')

    openSelectByTestId('pool-catalog-context-pool')
    await selectDropdownOption('pool-2 - Pool Two')

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-2 - Pool Two')
      expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent(
        'pool_id=55555555-5555-5555-5555-555555555555'
      )
    })

    await waitFor(() => {
      expect(mockGetPoolGraph).toHaveBeenLastCalledWith('55555555-5555-5555-5555-555555555555', '2026-01-01')
    })
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)
})
