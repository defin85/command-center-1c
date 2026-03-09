import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import type { Organization } from '../../../api/intercompanyPools'
import { PoolCatalogPage } from '../PoolCatalogPage'

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
const mockListMasterDataParties = vi.fn()
const mockListMasterDataItems = vi.fn()
const mockListMasterDataContracts = vi.fn()
const mockListMasterDataTaxProfiles = vi.fn()
const mockUseMe = vi.fn()
const mockUseDatabases = vi.fn()
const mockUseMyTenants = vi.fn()

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
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
  listMasterDataParties: (...args: unknown[]) => mockListMasterDataParties(...args),
  listMasterDataItems: (...args: unknown[]) => mockListMasterDataItems(...args),
  listMasterDataContracts: (...args: unknown[]) => mockListMasterDataContracts(...args),
  listMasterDataTaxProfiles: (...args: unknown[]) => mockListMasterDataTaxProfiles(...args),
}))

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

async function waitForInitialCatalogLoad() {
  await waitFor(() => expect(mockListOrganizations).toHaveBeenCalled())
  await waitFor(() => expect(mockGetOrganization).toHaveBeenCalled())
  await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalled())
  await waitFor(() => expect(mockGetPoolGraph).toHaveBeenCalled())
  await waitFor(() => expect(mockListPoolTopologySnapshots).toHaveBeenCalled())
}

function renderPage() {
  const result = render(
    <AntApp>
      <PoolCatalogPage />
    </AntApp>
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

async function openWorkspaceTab(user: ReturnType<typeof userEvent.setup>, tabLabel: 'Pools' | 'Topology Editor') {
  await initialCatalogLoadPromise
  await user.click(screen.getByRole('tab', { name: tabLabel }))
  if (tabLabel === 'Pools') {
    await screen.findByText('Pools management')
    return
  }
  await screen.findByText('Topology snapshots by date')
  await waitFor(() => {
    expect(screen.getByTestId('pool-catalog-topology-save')).toBeInTheDocument()
  })
}

async function expandFirstEdgeAdvanced(user: ReturnType<typeof userEvent.setup>) {
  const toggle = await screen.findAllByText('Advanced edge metadata / legacy document policy')
  await user.click(toggle[0] as HTMLElement)
}

async function openFirstEdgeLegacyDocumentPolicyEditor(user: ReturnType<typeof userEvent.setup>) {
  await expandFirstEdgeAdvanced(user)
  const openButton = await screen.findByTestId('pool-catalog-topology-edge-open-legacy-policy-editor-0')
  await user.click(openButton)
}

describe('PoolCatalogPage', () => {
  beforeEach(() => {
    initialCatalogLoadPromise = null
    localStorage.clear()

    mockListOrganizations.mockReset()
    mockGetOrganization.mockReset()
    mockListOrganizationPools.mockReset()
    mockGetPoolGraph.mockReset()
    mockUpsertOrganization.mockReset()
    mockUpsertOrganizationPool.mockReset()
    mockUpsertPoolTopologySnapshot.mockReset()
    mockListPoolTopologySnapshots.mockReset()
    mockSyncOrganizationsCatalog.mockReset()
    mockGetPoolODataMetadataCatalog.mockReset()
    mockRefreshPoolODataMetadataCatalog.mockReset()
    mockListMasterDataParties.mockReset()
    mockListMasterDataItems.mockReset()
    mockListMasterDataContracts.mockReset()
    mockListMasterDataTaxProfiles.mockReset()
    mockUseMe.mockReset()
    mockUseDatabases.mockReset()
    mockUseMyTenants.mockReset()

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
    expect(screen.getByText('Mutating actions are disabled')).toBeInTheDocument()
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
  }, 15000)

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
  }, 15000)

  it('submits workflow bindings from pool drawer as structured payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Pools')
    await user.click(screen.getByTestId('pool-catalog-edit-pool'))
    fireEvent.change(screen.getByLabelText('Workflow bindings JSON'), {
      target: {
        value: JSON.stringify(
          [
            {
              workflow: {
                workflow_definition_key: 'services-publication',
                workflow_revision_id: '11111111-1111-1111-1111-111111111111',
                workflow_revision: 3,
                workflow_name: 'services_publication',
              },
              selector: { direction: 'top_down', mode: 'safe', tags: ['baseline'] },
              effective_from: '2026-01-01',
              status: 'active',
            },
          ],
          null,
          2
        ),
      },
    })
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: '44444444-4444-4444-4444-444444444444',
        workflow_bindings: [
          expect.objectContaining({
            workflow: expect.objectContaining({
              workflow_definition_key: 'services-publication',
              workflow_revision: 3,
            }),
            status: 'active',
          }),
        ],
      })
    )
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

  it('hides legacy edge document_policy editor behind explicit compatibility action', async () => {
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
            document_policy: {
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
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await expandFirstEdgeAdvanced(user)

    expect(await screen.findByText('Legacy edge document_policy compatibility')).toBeInTheDocument()
    expect(await screen.findByTestId('pool-catalog-topology-edge-open-legacy-policy-editor-0')).toBeInTheDocument()
    expect(await screen.findByTestId('pool-catalog-topology-edge-policy-readonly-0')).toBeDisabled()
    expect(screen.queryByTestId('pool-catalog-topology-edge-policy-mode-0')).not.toBeInTheDocument()
  }, 15000)

  it('blocks topology save when edge document_policy JSON is invalid', async () => {
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
            document_policy: {
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
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)
    const edgePolicyInput = screen.getByTestId('pool-catalog-topology-edge-policy-0')
    await user.click(edgePolicyInput)
    await user.clear(edgePolicyInput)
    await user.paste('{invalid-json')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    expect(await screen.findByText('Preflight validation failed')).toBeInTheDocument()
    expect(
      await screen.findByText('Edge #1: document_policy должен быть валидным JSON.')
    ).toBeInTheDocument()
    expect(mockUpsertPoolTopologySnapshot).not.toHaveBeenCalled()
  }, 15000)

  it('includes edge document_policy in topology upsert payload after preflight', async () => {
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
          metadata: {},
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)
    const edgePolicyInput = screen.getByTestId('pool-catalog-topology-edge-policy-0')
    await user.click(edgePolicyInput)
    await user.clear(edgePolicyInput)
    await user.paste(
      '{"version":"document_policy.v1","chains":[{"chain_id":"sale_chain","documents":[{"document_id":"sale","entity_name":"Document_Sales","document_role":"sale"}]}]}'
    )
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
            metadata: {
              document_policy: expect.objectContaining({
                version: 'document_policy.v1',
              }),
            },
          }),
        ],
      })
    )
  }, 15000)

  it('builds document_policy in builder mode and preserves unknown edge metadata keys', async () => {
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
            document_policy: {
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
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    expect(await screen.findByText('Add chain')).toBeInTheDocument()
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        edges: [
          expect.objectContaining({
            metadata: expect.objectContaining({
              custom_edge_key: 'preserve-this',
              document_policy: expect.objectContaining({
                version: 'document_policy.v1',
                chains: [
                  expect.objectContaining({
                    chain_id: 'sale_chain',
                    documents: [
                      expect.objectContaining({
                        document_id: 'sale',
                        entity_name: 'Document_Sales',
                        document_role: 'sale',
                      }),
                    ],
                  }),
                ],
              }),
            }),
          }),
        ],
      })
    )
  }, 15000)

  it('loads and refreshes metadata catalog for edge builder mode', async () => {
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
          metadata: {},
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    await waitFor(() => {
      expect(mockGetPoolODataMetadataCatalog).toHaveBeenCalledWith('88888888-8888-8888-8888-888888888888')
    })

    await user.click(screen.getByTestId('pool-catalog-topology-edge-policy-refresh-metadata-0'))
    await waitFor(() => {
      expect(mockRefreshPoolODataMetadataCatalog).toHaveBeenCalledWith('88888888-8888-8888-8888-888888888888')
    })
  }, 15000)

  it('shows detailed problem+json error for metadata refresh failure', async () => {
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
          metadata: {},
        },
      ],
    })
    mockRefreshPoolODataMetadataCatalog.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Metadata Catalog Fetch Failed',
          status: 502,
          detail: 'OData endpoint returned HTTP 500 for $metadata.',
          code: 'POOL_METADATA_FETCH_FAILED',
          errors: [
            {
              code: 'POOL_METADATA_FETCH_FAILED',
              path: '$metadata',
              detail: 'На сервере 1С:Предприятия не найдена лицензия.',
            },
          ],
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    await waitFor(() => {
      expect(mockGetPoolODataMetadataCatalog).toHaveBeenCalledWith('88888888-8888-8888-8888-888888888888')
    })

    await user.click(screen.getByTestId('pool-catalog-topology-edge-policy-refresh-metadata-0'))

    expect(await screen.findByText(/OData endpoint returned HTTP 500 for \$metadata\./i)).toBeInTheDocument()
    expect(await screen.findByText(/\$metadata: На сервере 1С:Предприятия не найдена лицензия\./i)).toBeInTheDocument()
  }, 15000)

  it('shows warning when selected entity has no metadata fields in builder mode', async () => {
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
            document_policy: {
              version: 'document_policy.v1',
              chains: [
                {
                  chain_id: 'sale_chain',
                  documents: [
                    {
                      document_id: 'sale',
                      entity_name: 'Document_Sales',
                      document_role: 'sale',
                      field_mapping: {},
                      table_parts_mapping: {},
                      link_rules: {},
                    },
                  ],
                },
              ],
            },
          },
        },
      ],
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
          fields: [],
          table_parts: [],
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    expect(
      await screen.findByText('Для "Document_Sales" в metadata catalog нет fields.')
    ).toBeInTheDocument()
  }, 15000)

  it('preserves link_rules when saving document_policy from builder mode', async () => {
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
            document_policy: {
              version: 'document_policy.v1',
              chains: [
                {
                  chain_id: 'sale_chain',
                  documents: [
                    {
                      document_id: 'sale',
                      entity_name: 'Document_Sales',
                      document_role: 'sale',
                      field_mapping: { Amount: 'allocation.amount' },
                      table_parts_mapping: {},
                      invoice_mode: 'required',
                      link_rules: {},
                    },
                    {
                      document_id: 'invoice',
                      entity_name: 'Document_Invoice',
                      document_role: 'invoice',
                      field_mapping: { BaseDocument: 'sale.ref' },
                      table_parts_mapping: {},
                      link_to: 'sale',
                      link_rules: { depends_on: 'sale' },
                    },
                  ],
                },
              ],
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        edges: [
          expect.objectContaining({
            metadata: expect.objectContaining({
              document_policy: expect.objectContaining({
                chains: [
                  expect.objectContaining({
                    documents: expect.arrayContaining([
                      expect.objectContaining({
                        document_id: 'invoice',
                        link_rules: expect.objectContaining({
                          depends_on: 'sale',
                        }),
                      }),
                    ]),
                  }),
                ],
              }),
            }),
          }),
        ],
      })
    )
  }, 15000)

  it('preserves canonical master_data token in field_mapping from builder mode', async () => {
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
            document_policy: {
              version: 'document_policy.v1',
              chains: [
                {
                  chain_id: 'sale_chain',
                  documents: [
                    {
                      document_id: 'sale',
                      entity_name: 'Document_Sales',
                      document_role: 'sale',
                      field_mapping: { Amount: 'master_data.item.item-001.ref' },
                      table_parts_mapping: {},
                      link_rules: {},
                    },
                  ],
                },
              ],
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        edges: [
          expect.objectContaining({
            metadata: expect.objectContaining({
              document_policy: expect.objectContaining({
                chains: [
                  expect.objectContaining({
                    documents: expect.arrayContaining([
                      expect.objectContaining({
                        document_id: 'sale',
                        field_mapping: expect.objectContaining({
                          Amount: 'master_data.item.item-001.ref',
                        }),
                      }),
                    ]),
                  }),
                ],
              }),
            }),
          }),
        ],
      })
    )
  }, 15000)

  it('shows preflight validation error when expression source contains canonical master_data token', async () => {
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
            document_policy: {
              version: 'document_policy.v1',
              chains: [
                {
                  chain_id: 'sale_chain',
                  documents: [
                    {
                      document_id: 'sale',
                      entity_name: 'Document_Sales',
                      document_role: 'sale',
                      field_mapping: { Amount: 'allocation.amount' },
                      table_parts_mapping: {},
                      link_rules: {},
                    },
                  ],
                },
              ],
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    const expressionInput = await screen.findByPlaceholderText('allocation.amount')
    await user.click(expressionInput)
    await user.clear(expressionInput)
    await user.paste('master_data.item.item-001.ref')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    expect(await screen.findByText(/source_type=expression/)).toBeInTheDocument()
    expect(mockUpsertPoolTopologySnapshot).not.toHaveBeenCalled()
  }, 30000)

  it('supports edge metadata builder mode and preserves custom metadata keys', async () => {
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
            custom_nested: { level: 2 },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

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
              custom_edge_key: 'preserve-this',
              custom_nested: expect.objectContaining({ level: 2 }),
            }),
          }),
        ],
      })
    )
  }, 15000)

  it('does not auto-retry metadata catalog load after initial failure', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockGetPoolODataMetadataCatalog.mockRejectedValue(new Error('metadata load failed'))

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
          metadata: {},
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)

    openSelectByTestId('pool-catalog-topology-edge-policy-mode-0')
    await selectDropdownOption(/builder/i)

    await waitFor(() => {
      expect(mockGetPoolODataMetadataCatalog).toHaveBeenCalledTimes(1)
      expect(mockGetPoolODataMetadataCatalog).toHaveBeenCalledWith('88888888-8888-8888-8888-888888888888')
    })

    await waitFor(
      () => {
        expect(mockGetPoolODataMetadataCatalog).toHaveBeenCalledTimes(1)
      },
      { timeout: 1000 }
    )

    await user.click(screen.getByTestId('pool-catalog-topology-edge-policy-refresh-metadata-0'))
    await waitFor(() => {
      expect(mockRefreshPoolODataMetadataCatalog).toHaveBeenCalledWith('88888888-8888-8888-8888-888888888888')
    })
  }, 15000)

  it('preserves existing node and edge metadata when editing edge document_policy', async () => {
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
            custom_edge_key: 'preserve-this',
            document_policy: {
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
            },
          },
        },
      ],
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(await screen.findByText('Org Two')).toBeInTheDocument()

    await openWorkspaceTab(user, 'Topology Editor')
    await openFirstEdgeLegacyDocumentPolicyEditor(user)
    const edgePolicyInput = await screen.findByTestId('pool-catalog-topology-edge-policy-0')
    await user.click(edgePolicyInput)
    await user.clear(edgePolicyInput)
    await user.paste(
      '{"version":"document_policy.v1","chains":[{"chain_id":"sale_chain","documents":[{"document_id":"sale","entity_name":"Document_Sales","document_role":"sale","invoice_mode":"required"}]}]}'
    )
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
              document_policy: expect.objectContaining({
                version: 'document_policy.v1',
              }),
            }),
          }),
        ],
      })
    )
  }, 30000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)

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
  }, 15000)
})
