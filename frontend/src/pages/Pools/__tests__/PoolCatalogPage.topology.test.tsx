import { StrictMode, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  await waitFor(() => expect(mockListOrganizations).toHaveBeenCalled())
  await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalled())
  await waitFor(() => expect(mockGetPoolGraph).toHaveBeenCalled())
  await waitFor(() => expect(mockListPoolTopologySnapshots).toHaveBeenCalled())
}

function renderPage(initialEntry = '/pools/catalog?tab=topology&date=2026-01-01', options?: { strict?: boolean }) {
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

async function chooseDropdownOption(testId: string, label: string | RegExp) {
  openSelectByTestId(testId)
  await waitFor(() => {
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })
  await selectDropdownOption(label)
  await waitFor(() => {
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
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

async function expandFirstEdgeAdvanced(user: ReturnType<typeof userEvent.setup>) {
  const toggle = await screen.findAllByText('Advanced edge metadata')
  await user.click(toggle[0] as HTMLElement)
}

const EXTENDED_UI_TEST_TIMEOUT_MS = 60000
const TOPOLOGY_EDITOR_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS
const SYNC_MODAL_TIMEOUT_MS = EXTENDED_UI_TEST_TIMEOUT_MS
// Cold serial validation runs can push this end-to-end template instantiation flow
// past the generic 60s UI budget because it hydrates the template catalog and
// drives seven Select interactions before submit.
const TEMPLATE_INSTANTIATION_TIMEOUT_MS = 90000

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

  it('deactivates selected pool via toggle action', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage('/pools/catalog?tab=topology&date=2026-02-24')
    await initialCatalogLoadPromise

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

    renderPage('/pools/catalog?tab=topology&date=2026-02-24')
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    openSelectByTestId('pool-catalog-topology-authoring-mode')
    await selectDropdownOption('Manual snapshot editor')
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    openSelectByTestId('pool-catalog-topology-authoring-mode')
    await selectDropdownOption('Manual snapshot editor')

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
    await initialCatalogLoadPromise

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
    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByText('Topology snapshots by date')).toBeInTheDocument()
    expect(await screen.findByText('2026-02-24')).toBeInTheDocument()
    expect(await screen.findByText('2026-01-01')).toBeInTheDocument()

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

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-0')).toHaveTextContent('sale')
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

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 4,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_internal',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_leaf',
              decision_revision: 5,
            },
          ],
        }),
      ])
    )
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    openSelectByTestId('pool-catalog-topology-edge-slot-0')
    await selectDropdownOption('sale · decision-1 (document_policy) r4')
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

  it('submits template-based topology instantiation payload from /pools/catalog', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 4,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_internal',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_leaf',
              decision_revision: 5,
            },
          ],
        }),
      ])
    )

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    await chooseDropdownOption('pool-catalog-topology-authoring-mode', 'Template-based instantiation')
    await chooseDropdownOption('pool-catalog-topology-template-revision', 'Top Down Template · r3')
    await screen.findByTestId('pool-catalog-topology-template-slot-key-0', {}, { timeout: TOPOLOGY_EDITOR_TIMEOUT_MS })
    await chooseDropdownOption('pool-catalog-topology-template-slot-org-0', /Org One/)
    await chooseDropdownOption('pool-catalog-topology-template-slot-org-1', /Org Two/)
    await chooseDropdownOption('pool-catalog-topology-template-slot-org-2', /Org Three/)
    await chooseDropdownOption('pool-catalog-topology-template-slot-org-3', /Org Four/)
    await chooseDropdownOption('pool-catalog-topology-template-slot-org-4', /Org Five/)
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-initial',
        topology_template_revision_id: 'template-revision-r3',
        slot_assignments: [
          {
            slot_key: 'root',
            organization_id: '11111111-1111-1111-1111-111111111111',
          },
          {
            slot_key: 'organization_1',
            organization_id: '77777777-7777-7777-7777-777777777777',
          },
          {
            slot_key: 'organization_2',
            organization_id: '99999999-9999-9999-9999-999999999999',
          },
          {
            slot_key: 'organization_3',
            organization_id: '12121212-1212-1212-1212-121212121212',
          },
          {
            slot_key: 'organization_4',
            organization_id: '34343434-3434-3434-3434-343434343434',
          },
        ],
        edge_selector_overrides: [],
        nodes: [],
        edges: [],
      })
    )
  }, TEMPLATE_INSTANTIATION_TIMEOUT_MS)

  it('defaults fresh pool topology editor to template-based instantiation when graph is empty', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-authoring-mode')).toHaveTextContent(
        'Template-based instantiation'
      )
    })
    expect(screen.getByTestId('pool-catalog-topology-template-revision')).toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('keeps existing concrete manual pool in manual mode without auto-converting to template', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:manual-topology',
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-authoring-mode')).toHaveTextContent(
        'Manual snapshot editor'
      )
    })
    expect(screen.queryByTestId('pool-catalog-topology-template-revision')).not.toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('restores topology template instantiation from pool metadata without switching to manual mode', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_internal',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_leaf',
              decision_revision: 5,
            },
          ],
        }),
      ])
    )
    mockListOrganizationPools.mockResolvedValue([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {
          topology_template_instantiation: {
            topology_template_id: 'template-1',
            topology_template_code: 'top-down-template',
            topology_template_name: 'Top Down Template',
            topology_template_revision_id: 'template-revision-r3',
            topology_template_revision_number: 3,
            slot_assignments: [
              {
                slot_key: 'root',
                organization_id: '11111111-1111-1111-1111-111111111111',
              },
              {
                slot_key: 'organization_1',
                organization_id: '77777777-7777-7777-7777-777777777777',
              },
              {
                slot_key: 'organization_2',
                organization_id: '99999999-9999-9999-9999-999999999999',
              },
              {
                slot_key: 'organization_3',
                organization_id: '12121212-1212-1212-1212-121212121212',
              },
              {
                slot_key: 'organization_4',
                organization_id: '34343434-3434-3434-3434-343434343434',
              },
            ],
            edge_selector_overrides: [],
          },
        },
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:templated-topology',
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
          organization_id: '99999999-9999-9999-9999-999999999999',
          inn: '730000000003',
          name: 'Org Three',
          is_root: false,
          metadata: {},
        },
        {
          node_version_id: 'node-v4',
          organization_id: '12121212-1212-1212-1212-121212121212',
          inn: '730000000004',
          name: 'Org Four',
          is_root: false,
          metadata: {},
        },
        {
          node_version_id: 'node-v5',
          organization_id: '34343434-3434-3434-3434-343434343434',
          inn: '730000000005',
          name: 'Org Five',
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
          parent_node_version_id: 'node-v2',
          child_node_version_id: 'node-v3',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'receipt_internal',
          },
        },
        {
          edge_version_id: 'edge-v3',
          parent_node_version_id: 'node-v3',
          child_node_version_id: 'node-v4',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'receipt_leaf',
          },
        },
        {
          edge_version_id: 'edge-v4',
          parent_node_version_id: 'node-v3',
          child_node_version_id: 'node-v5',
          weight: '1',
          min_amount: null,
          max_amount: null,
          metadata: {
            document_policy_key: 'receipt_leaf',
          },
        },
      ],
    })

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-authoring-mode')).toHaveTextContent('Template-based instantiation')
    })
    expect(screen.getByTestId('pool-catalog-topology-template-revision')).toHaveTextContent('Top Down Template · r3')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-key-0')).toHaveValue('root')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-key-1')).toHaveValue('organization_1')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-key-4')).toHaveValue('organization_4')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-org-0')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-topology-template-slot-org-4')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-topology-template-edge-slot-status-0')).toBeInTheDocument()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('shows template instantiation from pool metadata before graph loading completes', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_internal',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_leaf',
              decision_revision: 5,
            },
          ],
        }),
      ])
    )
    mockListOrganizationPools.mockResolvedValue([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {
          topology_template_instantiation: {
            topology_template_id: 'template-1',
            topology_template_code: 'top-down-template',
            topology_template_name: 'Top Down Template',
            topology_template_revision_id: 'template-revision-r3',
            topology_template_revision_number: 3,
            slot_assignments: [
              {
                slot_key: 'root',
                organization_id: '11111111-1111-1111-1111-111111111111',
              },
              {
                slot_key: 'organization_1',
                organization_id: '77777777-7777-7777-7777-777777777777',
              },
              {
                slot_key: 'organization_2',
                organization_id: '99999999-9999-9999-9999-999999999999',
              },
              {
                slot_key: 'organization_3',
                organization_id: '12121212-1212-1212-1212-121212121212',
              },
              {
                slot_key: 'organization_4',
                organization_id: '34343434-3434-3434-3434-343434343434',
              },
            ],
            edge_selector_overrides: [],
          },
        },
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    let resolveGraph:
      | ((value: Awaited<ReturnType<typeof mockGetPoolGraph>>) => void)
      | undefined
    mockGetPoolGraph.mockImplementation(() => new Promise((resolve) => {
      resolveGraph = resolve as (value: Awaited<ReturnType<typeof mockGetPoolGraph>>) => void
    }))

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=topology&date=2026-01-01')
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-authoring-mode')).toHaveTextContent('Template-based instantiation')
    })
    expect(screen.getByTestId('pool-catalog-topology-template-revision')).toHaveTextContent('Top Down Template · r3')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-key-0')).toHaveValue('root')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-key-1')).toHaveValue('organization_1')
    expect(screen.getByTestId('pool-catalog-topology-template-slot-org-0')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-topology-template-edge-slot-status-0')).toBeInTheDocument()

    await act(async () => {
      resolveGraph?.({
        pool_id: '44444444-4444-4444-4444-444444444444',
        date: '2026-01-01',
        version: 'v1:templated-topology',
        nodes: [],
        edges: [],
      })
    })
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('renders template slot assignment labels after organizations finish loading on first open', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    let resolveOrganizations: ((value: Organization[]) => void) | undefined
    mockListOrganizations.mockImplementation(() => new Promise<Organization[]>((resolve) => {
      resolveOrganizations = resolve
    }))
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_internal',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_leaf',
              decision_revision: 5,
            },
          ],
        }),
      ])
    )
    mockListOrganizationPools.mockResolvedValue([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {
          topology_template_instantiation: {
            topology_template_id: 'template-1',
            topology_template_code: 'top-down-template',
            topology_template_name: 'Top Down Template',
            topology_template_revision_id: 'template-revision-r3',
            topology_template_revision_number: 3,
            slot_assignments: [
              {
                slot_key: 'root',
                organization_id: '11111111-1111-1111-1111-111111111111',
              },
              {
                slot_key: 'organization_1',
                organization_id: '77777777-7777-7777-7777-777777777777',
              },
              {
                slot_key: 'organization_2',
                organization_id: '99999999-9999-9999-9999-999999999999',
              },
              {
                slot_key: 'organization_3',
                organization_id: '12121212-1212-1212-1212-121212121212',
              },
              {
                slot_key: 'organization_4',
                organization_id: '34343434-3434-3434-3434-343434343434',
              },
            ],
            edge_selector_overrides: [],
          },
        },
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=topology&date=2026-01-01')
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-context-pool')).toHaveTextContent('pool-1 - Pool One')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-authoring-mode')).toHaveTextContent('Template-based instantiation')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-template-slot-key-0')).toHaveValue('root')
    })
    expect(screen.getByTestId('pool-catalog-topology-template-slot-org-0')).not.toHaveTextContent('Org One')

    await act(async () => {
      resolveOrganizations?.([
        baseOrganization,
        secondOrganization,
        thirdOrganization,
        fourthOrganization,
        fifthOrganization,
      ])
    })

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-template-slot-org-0')).toHaveTextContent('Org One')
      expect(screen.getByTestId('pool-catalog-topology-template-slot-org-4')).toHaveTextContent('Org Five')
    })
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('keeps template edge selectors materialized after refreshing topology data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([
      baseOrganization,
      secondOrganization,
      thirdOrganization,
      fourthOrganization,
      fifthOrganization,
    ])
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_internal',
              decision_revision: 5,
            },
            {
              decision_table_id: 'decision-2',
              decision_key: 'document_policy',
              slot_key: 'receipt_leaf',
              decision_revision: 5,
            },
          ],
        }),
      ])
    )
    mockListOrganizationPools.mockResolvedValue([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {
          topology_template_instantiation: {
            topology_template_id: 'template-1',
            topology_template_code: 'top-down-template',
            topology_template_name: 'Top Down Template',
            topology_template_revision_id: 'template-revision-r3',
            topology_template_revision_number: 3,
            slot_assignments: [
              {
                slot_key: 'root',
                organization_id: '11111111-1111-1111-1111-111111111111',
              },
              {
                slot_key: 'organization_1',
                organization_id: '77777777-7777-7777-7777-777777777777',
              },
              {
                slot_key: 'organization_2',
                organization_id: '99999999-9999-9999-9999-999999999999',
              },
              {
                slot_key: 'organization_3',
                organization_id: '12121212-1212-1212-1212-121212121212',
              },
              {
                slot_key: 'organization_4',
                organization_id: '34343434-3434-3434-3434-343434343434',
              },
            ],
            edge_selector_overrides: [],
          },
        },
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    expect(await screen.findByTestId('pool-catalog-topology-template-edge-slot-status-0')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Refresh data' }))

    await waitFor(() => {
      expect(mockGetPoolGraph.mock.calls.length).toBeGreaterThanOrEqual(2)
    })
    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-topology-template-edge-slot-status-0')).toBeInTheDocument()
      expect(screen.getByTestId('pool-catalog-topology-template-edge-slot-status-1')).toBeInTheDocument()
    })
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('hands off reusable topology authoring to the dedicated workspace when the template catalog is empty', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListPoolTopologyTemplates.mockResolvedValue([])

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')

    expect(screen.getByText('Topology template catalog is empty.')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('pool-catalog-open-topology-template-workspace'))

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('/pools/topology-templates')
    })
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('compose=create')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_pool_id=44444444-4444-4444-4444-444444444444')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_tab=topology')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_date=2026-01-01')
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('hands off selected reusable topology template revision to the dedicated revise workspace with preserved context', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    openSelectByTestId('pool-catalog-topology-template-revision')
    await selectDropdownOption('Top Down Template · r3')
    await screen.findByTestId('pool-catalog-revise-topology-template', {}, { timeout: TOPOLOGY_EDITOR_TIMEOUT_MS })

    fireEvent.click(screen.getByTestId('pool-catalog-revise-topology-template'))

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('/pools/topology-templates')
    })
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('compose=revise')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('template=template-1')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('detail=1')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_pool_id=44444444-4444-4444-4444-444444444444')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_tab=topology')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_date=2026-01-01')
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('hands off the generic Open topology templates CTA with preserved topology return context', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage('/pools/catalog?pool_id=44444444-4444-4444-4444-444444444444&tab=topology&date=2026-01-01')
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    await user.click(screen.getByRole('button', { name: 'Open topology templates' }))

    await waitFor(() => {
      expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('/pools/topology-templates')
    })
    expect(screen.getByTestId('pool-catalog-location')).not.toHaveTextContent('compose=')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_pool_id=44444444-4444-4444-4444-444444444444')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_tab=topology')
    expect(screen.getByTestId('pool-catalog-location')).toHaveTextContent('return_date=2026-01-01')
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)

  it('supports edge metadata builder mode and preserves custom metadata keys with slot selector', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 4,
            },
          ],
        }),
      ])
    )
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
    await initialCatalogLoadPromise
    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-0')).toHaveTextContent('sale')
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
    mockListPoolWorkflowBindings.mockResolvedValue(
      buildPoolWorkflowBindingCollection([
        buildPoolWorkflowBinding({
          decisions: [
            {
              decision_table_id: 'decision-1',
              decision_key: 'document_policy',
              slot_key: 'sale',
              decision_revision: 4,
            },
          ],
        }),
      ])
    )
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
          },
        },
      ],
    })

    renderPage()
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')
    openSelectByTestId('pool-catalog-topology-edge-slot-0')
    await selectDropdownOption('sale · decision-1 (document_policy) r4')
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
            decision_key: 'document_policy',
            slot_key: 'sale',
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByTestId('pool-catalog-topology-coverage-status')).toHaveTextContent('Auto-resolved binding')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-status-0')).toHaveTextContent('Resolved')
    expect(
      await screen.findByText(/binding-top-down .*sale-policy \(document_policy\) r7/i)
    ).toBeInTheDocument()
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
            decision_key: 'document_policy',
            slot_key: 'sale',
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
            decision_key: 'document_policy',
            slot_key: 'purchase',
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
    await initialCatalogLoadPromise

    await openWorkspaceTab(user, 'Topology Editor')

    expect(await screen.findByTestId('pool-catalog-topology-coverage-status')).toHaveTextContent('Ambiguous context')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-status-0')).toHaveTextContent('Coverage unavailable')
    expect(screen.getByText('Topology remediation required')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeDisabled()

    openSelectByTestId('pool-catalog-topology-coverage-binding')
    await selectDropdownOption(/binding-sale/i)

    expect(await screen.findByTestId('pool-catalog-topology-coverage-status')).toHaveTextContent('Selected binding')
    expect(await screen.findByTestId('pool-catalog-topology-edge-slot-status-0')).toHaveTextContent('Resolved')
    expect(
      await screen.findByText(/binding-sale .*sale-policy \(document_policy\) r2/i)
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByText('Topology remediation required')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeEnabled()
  }, TOPOLOGY_EDITOR_TIMEOUT_MS)
})
