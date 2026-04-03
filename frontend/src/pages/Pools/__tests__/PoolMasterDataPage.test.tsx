import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import { HEAVY_ROUTE_TEST_TIMEOUT_MS } from '../../../test/timeouts'
import { PoolMasterDataPage } from '../PoolMasterDataPage'

const mockListMasterDataParties = vi.fn()
const mockUpsertMasterDataParty = vi.fn()
const mockListMasterDataItems = vi.fn()
const mockUpsertMasterDataItem = vi.fn()
const mockListMasterDataContracts = vi.fn()
const mockUpsertMasterDataContract = vi.fn()
const mockListMasterDataTaxProfiles = vi.fn()
const mockUpsertMasterDataTaxProfile = vi.fn()
const mockListMasterDataBindings = vi.fn()
const mockUpsertMasterDataBinding = vi.fn()
const mockGetPoolMasterDataRegistry = vi.fn()
const mockListPoolTargetDatabases = vi.fn()
const mockListMasterDataSyncStatus = vi.fn()
const mockListMasterDataSyncConflicts = vi.fn()
const mockRetryMasterDataSyncConflict = vi.fn()
const mockReconcileMasterDataSyncConflict = vi.fn()
const mockResolveMasterDataSyncConflict = vi.fn()
const mockRunPoolMasterDataBootstrapImportPreflight = vi.fn()
const mockCreatePoolMasterDataBootstrapImportJob = vi.fn()
const mockListPoolMasterDataBootstrapImportJobs = vi.fn()
const mockGetPoolMasterDataBootstrapImportJob = vi.fn()
const mockCancelPoolMasterDataBootstrapImportJob = vi.fn()
const mockRetryFailedPoolMasterDataBootstrapImportChunks = vi.fn()

const buildBootstrapJob = (overrides: Record<string, unknown> = {}) => ({
  id: 'job-1',
  tenant_id: 'tenant-1',
  database_id: 'db-1',
  entity_scope: ['party', 'item'],
  status: 'finalized',
  started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:02:00Z',
  last_error_code: '',
  last_error: '',
  preflight_result: { ok: true },
  dry_run_summary: { rows_total: 2, chunks_total: 1 },
  progress: {
    total_chunks: 1,
    processed_chunks: 1,
    pending_chunks: 0,
    running_chunks: 0,
    succeeded_chunks: 1,
    failed_chunks: 0,
    deferred_chunks: 0,
    canceled_chunks: 0,
    completion_ratio: 1,
  },
  audit_trail: [],
  report: {
    created_count: 1,
    updated_count: 1,
    skipped_count: 0,
    failed_count: 0,
    deferred_count: 0,
    diagnostics: {},
  },
  chunks: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:02:00Z',
  ...overrides,
})

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listMasterDataParties: (...args: unknown[]) => mockListMasterDataParties(...args),
  upsertMasterDataParty: (...args: unknown[]) => mockUpsertMasterDataParty(...args),
  listMasterDataItems: (...args: unknown[]) => mockListMasterDataItems(...args),
  upsertMasterDataItem: (...args: unknown[]) => mockUpsertMasterDataItem(...args),
  listMasterDataContracts: (...args: unknown[]) => mockListMasterDataContracts(...args),
  upsertMasterDataContract: (...args: unknown[]) => mockUpsertMasterDataContract(...args),
  listMasterDataTaxProfiles: (...args: unknown[]) => mockListMasterDataTaxProfiles(...args),
  upsertMasterDataTaxProfile: (...args: unknown[]) => mockUpsertMasterDataTaxProfile(...args),
  listMasterDataBindings: (...args: unknown[]) => mockListMasterDataBindings(...args),
  upsertMasterDataBinding: (...args: unknown[]) => mockUpsertMasterDataBinding(...args),
  getPoolMasterDataRegistry: (...args: unknown[]) => mockGetPoolMasterDataRegistry(...args),
  listPoolTargetDatabases: (...args: unknown[]) => mockListPoolTargetDatabases(...args),
  listMasterDataSyncStatus: (...args: unknown[]) => mockListMasterDataSyncStatus(...args),
  listMasterDataSyncConflicts: (...args: unknown[]) => mockListMasterDataSyncConflicts(...args),
  retryMasterDataSyncConflict: (...args: unknown[]) => mockRetryMasterDataSyncConflict(...args),
  reconcileMasterDataSyncConflict: (...args: unknown[]) => mockReconcileMasterDataSyncConflict(...args),
  resolveMasterDataSyncConflict: (...args: unknown[]) => mockResolveMasterDataSyncConflict(...args),
  runPoolMasterDataBootstrapImportPreflight: (...args: unknown[]) => mockRunPoolMasterDataBootstrapImportPreflight(...args),
  createPoolMasterDataBootstrapImportJob: (...args: unknown[]) => mockCreatePoolMasterDataBootstrapImportJob(...args),
  listPoolMasterDataBootstrapImportJobs: (...args: unknown[]) => mockListPoolMasterDataBootstrapImportJobs(...args),
  getPoolMasterDataBootstrapImportJob: (...args: unknown[]) => mockGetPoolMasterDataBootstrapImportJob(...args),
  cancelPoolMasterDataBootstrapImportJob: (...args: unknown[]) => mockCancelPoolMasterDataBootstrapImportJob(...args),
  retryFailedPoolMasterDataBootstrapImportChunks: (...args: unknown[]) =>
    mockRetryFailedPoolMasterDataBootstrapImportChunks(...args),
}))

function renderPage(path = '/pools/master-data') {
  window.history.pushState({}, '', path)
  return render(
    <AntApp>
      <PoolMasterDataPage />
    </AntApp>
  )
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

describe('PoolMasterDataPage', () => {
  beforeEach(() => {
    mockListMasterDataParties.mockReset()
    mockUpsertMasterDataParty.mockReset()
    mockListMasterDataItems.mockReset()
    mockUpsertMasterDataItem.mockReset()
    mockListMasterDataContracts.mockReset()
    mockUpsertMasterDataContract.mockReset()
    mockListMasterDataTaxProfiles.mockReset()
    mockUpsertMasterDataTaxProfile.mockReset()
    mockListMasterDataBindings.mockReset()
    mockUpsertMasterDataBinding.mockReset()
    mockGetPoolMasterDataRegistry.mockReset()
    mockListPoolTargetDatabases.mockReset()
    mockListMasterDataSyncStatus.mockReset()
    mockListMasterDataSyncConflicts.mockReset()
    mockRetryMasterDataSyncConflict.mockReset()
    mockReconcileMasterDataSyncConflict.mockReset()
    mockResolveMasterDataSyncConflict.mockReset()
    mockRunPoolMasterDataBootstrapImportPreflight.mockReset()
    mockCreatePoolMasterDataBootstrapImportJob.mockReset()
    mockListPoolMasterDataBootstrapImportJobs.mockReset()
    mockGetPoolMasterDataBootstrapImportJob.mockReset()
    mockCancelPoolMasterDataBootstrapImportJob.mockReset()
    mockRetryFailedPoolMasterDataBootstrapImportChunks.mockReset()

    mockListMasterDataParties.mockResolvedValue({
      parties: [
        {
          id: 'party-1',
          tenant_id: 'tenant-1',
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
      meta: { limit: 100, offset: 0, total: 1 },
    })
    mockListMasterDataItems.mockResolvedValue({
      items: [],
      meta: { limit: 100, offset: 0, total: 0 },
    })
    mockListMasterDataContracts.mockResolvedValue({
      contracts: [],
      meta: { limit: 100, offset: 0, total: 0 },
    })
    mockListMasterDataTaxProfiles.mockResolvedValue({
      tax_profiles: [],
      meta: { limit: 100, offset: 0, total: 0 },
    })
    mockListMasterDataBindings.mockResolvedValue({
      bindings: [],
      meta: { limit: 200, offset: 0, total: 0 },
    })
    mockGetPoolMasterDataRegistry.mockResolvedValue({
      contract_version: 'pool_master_data_registry.v1',
      count: 5,
      entries: [
        {
          entity_type: 'party',
          label: 'Party',
          kind: 'canonical',
          display_order: 10,
          binding_scope_fields: ['canonical_id', 'database_id', 'ib_catalog_kind'],
          capabilities: {
            direct_binding: true,
            token_exposure: true,
            bootstrap_import: true,
            outbox_fanout: true,
            sync_outbound: true,
            sync_inbound: true,
            sync_reconcile: true,
          },
          token_contract: {
            enabled: true,
            qualifier_kind: 'ib_catalog_kind',
            qualifier_required: true,
            qualifier_options: ['organization', 'counterparty'],
          },
          bootstrap_contract: { enabled: true, dependency_order: 10 },
          runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
        },
        {
          entity_type: 'item',
          label: 'Item',
          kind: 'canonical',
          display_order: 20,
          binding_scope_fields: ['canonical_id', 'database_id'],
          capabilities: {
            direct_binding: true,
            token_exposure: true,
            bootstrap_import: true,
            outbox_fanout: true,
            sync_outbound: true,
            sync_inbound: true,
            sync_reconcile: true,
          },
          token_contract: {
            enabled: true,
            qualifier_kind: 'none',
            qualifier_required: false,
            qualifier_options: [],
          },
          bootstrap_contract: { enabled: true, dependency_order: 20 },
          runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
        },
        {
          entity_type: 'contract',
          label: 'Contract',
          kind: 'canonical',
          display_order: 30,
          binding_scope_fields: ['canonical_id', 'database_id', 'owner_counterparty_canonical_id'],
          capabilities: {
            direct_binding: true,
            token_exposure: true,
            bootstrap_import: true,
            outbox_fanout: true,
            sync_outbound: true,
            sync_inbound: true,
            sync_reconcile: true,
          },
          token_contract: {
            enabled: true,
            qualifier_kind: 'owner_counterparty_canonical_id',
            qualifier_required: true,
            qualifier_options: [],
          },
          bootstrap_contract: { enabled: true, dependency_order: 40 },
          runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
        },
        {
          entity_type: 'tax_profile',
          label: 'Tax Profile',
          kind: 'canonical',
          display_order: 40,
          binding_scope_fields: ['canonical_id', 'database_id'],
          capabilities: {
            direct_binding: true,
            token_exposure: true,
            bootstrap_import: true,
            outbox_fanout: true,
            sync_outbound: true,
            sync_inbound: true,
            sync_reconcile: true,
          },
          token_contract: {
            enabled: true,
            qualifier_kind: 'none',
            qualifier_required: false,
            qualifier_options: [],
          },
          bootstrap_contract: { enabled: true, dependency_order: 30 },
          runtime_consumers: ['bindings', 'bootstrap_import', 'sync', 'token_catalog', 'token_parser'],
        },
        {
          entity_type: 'binding',
          label: 'Binding',
          kind: 'bootstrap_helper',
          display_order: 50,
          binding_scope_fields: [],
          capabilities: {
            direct_binding: false,
            token_exposure: false,
            bootstrap_import: true,
            outbox_fanout: false,
            sync_outbound: false,
            sync_inbound: false,
            sync_reconcile: false,
          },
          token_contract: {
            enabled: false,
            qualifier_kind: 'none',
            qualifier_required: false,
            qualifier_options: [],
          },
          bootstrap_contract: { enabled: true, dependency_order: 50 },
          runtime_consumers: ['bootstrap_import'],
        },
      ],
    })
    mockListPoolTargetDatabases.mockResolvedValue([
      { id: 'db-1', name: 'Main DB' },
    ])
    mockListMasterDataSyncStatus.mockResolvedValue({
      statuses: [],
      count: 0,
    })
    mockListMasterDataSyncConflicts.mockResolvedValue({
      conflicts: [],
      count: 0,
    })
    mockRetryMasterDataSyncConflict.mockResolvedValue({ conflict: {} })
    mockReconcileMasterDataSyncConflict.mockResolvedValue({ conflict: {} })
    mockResolveMasterDataSyncConflict.mockResolvedValue({ conflict: {} })
    mockRunPoolMasterDataBootstrapImportPreflight.mockResolvedValue({
      preflight: {
        ok: true,
        source_kind: 'ib_odata',
        coverage: {
          party: true,
          item: true,
        },
        credential_strategy: 'service',
        errors: [],
        diagnostics: {},
      },
    })
    mockCreatePoolMasterDataBootstrapImportJob.mockResolvedValue({
      job: buildBootstrapJob(),
    })
    mockListPoolMasterDataBootstrapImportJobs.mockResolvedValue({
      count: 0,
      limit: 20,
      offset: 0,
      jobs: [],
    })
    mockGetPoolMasterDataBootstrapImportJob.mockResolvedValue({
      job: buildBootstrapJob(),
    })
    mockCancelPoolMasterDataBootstrapImportJob.mockResolvedValue({
      job: buildBootstrapJob({ status: 'canceled' }),
    })
    mockRetryFailedPoolMasterDataBootstrapImportChunks.mockResolvedValue({
      job: buildBootstrapJob(),
    })
  })

  it('renders workspace tabs and loads default Party tab list', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Pool Master Data')).toBeInTheDocument()
    expect(await screen.findByText('Party One')).toBeInTheDocument()
    expect(mockListMasterDataParties).toHaveBeenCalledWith({
      query: undefined,
      role: undefined,
      limit: 100,
      offset: 0,
    })

    await user.click(screen.getByRole('tab', { name: 'Item' }))
    await waitFor(() => expect(mockListMasterDataItems).toHaveBeenCalled())

    await user.click(screen.getByRole('tab', { name: 'Sync' }))
    await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
    await waitFor(() => expect(mockListMasterDataSyncConflicts).toHaveBeenCalled())
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('opens remediation target tab from query params and shows remediation context', async () => {
    renderPage('/pools/master-data?tab=bindings&entityType=organization&canonicalId=party-1&databaseId=db-1&role=organization')

    expect(await screen.findByText('Pool Master Data')).toBeInTheDocument()
    await waitFor(() => expect(mockListMasterDataBindings).toHaveBeenCalled())
    expect(screen.getByTestId('pool-master-data-remediation-context')).toHaveTextContent(
      'entity_type=organization canonical_id=party-1 database_id=db-1'
    )
    expect(screen.getByTestId('pool-master-data-remediation-context')).toHaveTextContent(
      'role=organization'
    )
  })

  it('blocks Party save when no role is selected', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Party One')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add Party' }))
    await user.type(screen.getByLabelText('Canonical ID'), 'party-002')
    await user.type(screen.getByLabelText('Name'), 'Party Two')
    await user.click(screen.getByRole('checkbox', { name: 'Role: counterparty' }))
    await user.click(screen.getByRole('button', { name: 'OK' }))

    expect(
      await screen.findByText('Party должен иметь минимум одну роль: organization или counterparty.')
    ).toBeInTheDocument()
    expect(mockUpsertMasterDataParty).not.toHaveBeenCalled()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('renders Sync tab and runs conflict actions', async () => {
    const user = userEvent.setup()
    mockListMasterDataSyncStatus.mockResolvedValue({
      statuses: [
        {
          tenant_id: 'tenant-1',
          database_id: 'db-1',
          entity_type: 'item',
          checkpoint_token: 'cp-001',
          pending_checkpoint_token: 'cp-002',
          checkpoint_status: 'active',
          pending_count: 1,
          retry_count: 0,
          conflict_pending_count: 1,
          conflict_retrying_count: 0,
          lag_seconds: 120,
          last_success_at: '2026-01-01T00:00:00Z',
          last_applied_at: '2026-01-01T00:00:00Z',
          last_error_code: '',
          last_error_reason: '',
          priority: 'p1',
          role: 'reconcile',
          server_affinity: 'srv:main',
          deadline_at: '2026-01-01T00:01:00Z',
          deadline_state: 'pending',
          queue_states: {
            queued: 1,
            processing: 0,
            retrying: 0,
            failed: 0,
            completed: 0,
          },
        },
      ],
      count: 1,
    })
    mockListMasterDataSyncConflicts.mockResolvedValue({
      conflicts: [
        {
          id: 'conflict-1',
          tenant_id: 'tenant-1',
          database_id: 'db-1',
          entity_type: 'item',
          status: 'pending',
          conflict_code: 'POLICY_VIOLATION',
          canonical_id: 'item-001',
          origin_system: 'ib',
          origin_event_id: 'evt-001',
          diagnostics: {},
          metadata: {},
          resolved_at: null,
          resolved_by_id: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      count: 1,
    })

    renderPage('/pools/master-data?tab=sync')

    expect(await screen.findByText('Sync Status')).toBeInTheDocument()
    expect(await screen.findByText('Conflict Queue')).toBeInTheDocument()
    expect(await screen.findByText('POLICY_VIOLATION')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() =>
      expect(mockRetryMasterDataSyncConflict).toHaveBeenCalledWith('conflict-1', {
        note: 'Manual retry from Pool Master Data Sync UI',
      })
    )

    await user.click(screen.getByRole('button', { name: 'Reconcile' }))
    await waitFor(() =>
      expect(mockReconcileMasterDataSyncConflict).toHaveBeenCalledWith('conflict-1', {
        note: 'Manual reconcile from Pool Master Data Sync UI',
        reconcile_payload: { strategy: 'manual_reconcile' },
      })
    )

    await user.click(screen.getByRole('button', { name: 'Resolve' }))
    await waitFor(() =>
      expect(mockResolveMasterDataSyncConflict).toHaveBeenCalledWith('conflict-1', {
        resolution_code: 'MANUAL_RECONCILE',
        note: 'Manual resolve from Pool Master Data Sync UI',
        metadata: { source: 'ui' },
      })
    )
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('hides retry and reconcile actions when registry disables the required sync direction', async () => {
    mockGetPoolMasterDataRegistry.mockResolvedValue({
      contract_version: 'pool_master_data_registry.v1',
      count: 1,
      entries: [
        {
          entity_type: 'item',
          label: 'Item',
          kind: 'canonical',
          display_order: 20,
          binding_scope_fields: ['canonical_id', 'database_id'],
          capabilities: {
            direct_binding: true,
            token_exposure: true,
            bootstrap_import: true,
            outbox_fanout: true,
            sync_outbound: false,
            sync_inbound: false,
            sync_reconcile: false,
          },
          token_contract: {
            enabled: true,
            qualifier_kind: 'none',
            qualifier_required: false,
            qualifier_options: [],
          },
          bootstrap_contract: { enabled: true, dependency_order: 20 },
          runtime_consumers: ['bindings', 'bootstrap_import', 'token_catalog', 'token_parser'],
        },
      ],
    })
    mockListMasterDataSyncStatus.mockResolvedValue({
      statuses: [
        {
          tenant_id: 'tenant-1',
          database_id: 'db-1',
          entity_type: 'item',
          checkpoint_token: 'cp-disabled-001',
          pending_checkpoint_token: '',
          checkpoint_status: 'active',
          pending_count: 0,
          retry_count: 0,
          conflict_pending_count: 1,
          conflict_retrying_count: 0,
          lag_seconds: 0,
          last_success_at: null,
          last_applied_at: null,
          last_error_code: '',
          last_error_reason: '',
          priority: '',
          role: '',
          server_affinity: '',
          deadline_at: '',
          deadline_state: 'none',
          queue_states: {
            queued: 0,
            processing: 0,
            retrying: 0,
            failed: 0,
            completed: 0,
          },
        },
      ],
      count: 1,
    })
    mockListMasterDataSyncConflicts.mockResolvedValue({
      conflicts: [
        {
          id: 'conflict-disabled-1',
          tenant_id: 'tenant-1',
          database_id: 'db-1',
          entity_type: 'item',
          status: 'pending',
          conflict_code: 'POLICY_VIOLATION',
          canonical_id: 'item-disabled-001',
          origin_system: 'ib',
          origin_event_id: 'evt-disabled-001',
          diagnostics: {},
          metadata: {},
          resolved_at: null,
          resolved_by_id: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      count: 1,
    })

    renderPage('/pools/master-data?tab=sync')

    expect(await screen.findByText('Conflict Queue')).toBeInTheDocument()
    await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
    expect(screen.queryByText('cp-disabled-001')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reconcile' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resolve' })).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('applies scheduling filters for sync status operator view', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Sync' }))

    await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
    mockListMasterDataSyncStatus.mockClear()

    openSelectByTestId('sync-status-filter-priority')
    await selectDropdownOption(/^p1$/)
    openSelectByTestId('sync-status-filter-role')
    await selectDropdownOption(/^reconcile$/)
    await user.type(screen.getByTestId('sync-status-filter-server-affinity'), 'srv:main')
    openSelectByTestId('sync-status-filter-deadline-state')
    await selectDropdownOption(/^missed$/)

    await user.click(screen.getByTestId('sync-status-refresh'))

    await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
    expect(mockListMasterDataSyncStatus).toHaveBeenLastCalledWith({
      database_id: undefined,
      entity_type: undefined,
      priority: 'p1',
      role: 'reconcile',
      server_affinity: 'srv:main',
      deadline_state: 'missed',
    })
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('runs bootstrap wizard flow preflight -> dry-run -> execute', async () => {
    const user = userEvent.setup()
    const dryRunJob = buildBootstrapJob({
      id: 'job-dry-run',
      status: 'execute_pending',
      dry_run_summary: { rows_total: 2, chunks_total: 1 },
      report: {
        created_count: 0,
        updated_count: 0,
        skipped_count: 0,
        failed_count: 0,
        deferred_count: 0,
        diagnostics: {},
      },
    })
    const executeJob = buildBootstrapJob({
      id: 'job-execute',
      status: 'finalized',
      report: {
        created_count: 1,
        updated_count: 1,
        skipped_count: 0,
        failed_count: 0,
        deferred_count: 0,
        diagnostics: {},
      },
      chunks: [
        {
          id: 'chunk-1',
          job_id: 'job-execute',
          entity_type: 'party',
          chunk_index: 0,
          status: 'succeeded',
          attempt_count: 1,
          idempotency_key: 'idem-1',
          records_total: 2,
          records_created: 1,
          records_updated: 1,
          records_skipped: 0,
          records_failed: 0,
          last_error_code: '',
          last_error: '',
          diagnostics: {},
          metadata: {},
          started_at: '2026-01-01T00:00:00Z',
          finished_at: '2026-01-01T00:01:00Z',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:01:00Z',
        },
      ],
    })
    mockCreatePoolMasterDataBootstrapImportJob
      .mockResolvedValueOnce({ job: dryRunJob })
      .mockResolvedValueOnce({ job: executeJob })
    mockGetPoolMasterDataBootstrapImportJob
      .mockResolvedValueOnce({ job: dryRunJob })
      .mockResolvedValueOnce({ job: executeJob })
    mockListPoolMasterDataBootstrapImportJobs.mockResolvedValue({
      count: 2,
      limit: 20,
      offset: 0,
      jobs: [executeJob, dryRunJob],
    })

    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Bootstrap Import' }))

    openSelectByTestId('bootstrap-import-database-select')
    await selectDropdownOption(/^Main DB$/)

    await user.click(screen.getByTestId('bootstrap-import-run-preflight'))
    await waitFor(() =>
      expect(mockRunPoolMasterDataBootstrapImportPreflight).toHaveBeenCalledWith({
        database_id: 'db-1',
        entity_scope: ['party', 'item'],
      })
    )

    await user.click(screen.getByTestId('bootstrap-import-run-dry-run'))
    await waitFor(() =>
      expect(mockCreatePoolMasterDataBootstrapImportJob).toHaveBeenNthCalledWith(1, {
        database_id: 'db-1',
        entity_scope: ['party', 'item'],
        mode: 'dry_run',
      })
    )

    await user.click(screen.getByTestId('bootstrap-import-run-execute'))
    await waitFor(() =>
      expect(mockCreatePoolMasterDataBootstrapImportJob).toHaveBeenNthCalledWith(2, {
        database_id: 'db-1',
        entity_scope: ['party', 'item'],
        mode: 'execute',
      })
    )

    expect(await screen.findByText('Current Job')).toBeInTheDocument()
    expect(await screen.findByText('Rows (dry-run)')).toBeInTheDocument()
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('keeps bootstrap form values after preflight error', async () => {
    const user = userEvent.setup()
    mockRunPoolMasterDataBootstrapImportPreflight.mockRejectedValueOnce({
      response: {
        data: {
          title: 'Validation Error',
          detail: 'Preflight failed in source adapter.',
          errors: {
            database_id: ['Database is not available'],
          },
        },
      },
    })

    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Bootstrap Import' }))

    openSelectByTestId('bootstrap-import-database-select')
    await selectDropdownOption(/^Main DB$/)

    await user.click(screen.getByTestId('bootstrap-import-run-preflight'))

    expect((await screen.findAllByText('Preflight failed in source adapter.')).length).toBeGreaterThan(0)
    expect(screen.getByTestId('bootstrap-import-database-select')).toHaveTextContent('Main DB')
    expect(screen.getByTestId('bootstrap-import-entity-scope-select')).toHaveTextContent('party')
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

  it('runs retry failed chunks action for bootstrap job', async () => {
    const user = userEvent.setup()
    const failedJob = buildBootstrapJob({
      id: 'job-failed',
      status: 'finalized',
      report: {
        created_count: 1,
        updated_count: 0,
        skipped_count: 0,
        failed_count: 1,
        deferred_count: 0,
        diagnostics: {},
      },
    })
    mockListPoolMasterDataBootstrapImportJobs.mockResolvedValue({
      count: 1,
      limit: 20,
      offset: 0,
      jobs: [failedJob],
    })
    mockGetPoolMasterDataBootstrapImportJob.mockResolvedValue({
      job: failedJob,
    })
    mockRetryFailedPoolMasterDataBootstrapImportChunks.mockResolvedValue({
      job: buildBootstrapJob({
        id: 'job-failed',
        status: 'finalized',
      }),
    })

    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Bootstrap Import' }))
    expect(await screen.findByText('Current Job')).toBeInTheDocument()

    await user.click(screen.getByTestId('bootstrap-import-retry-failed'))
    await waitFor(() =>
      expect(mockRetryFailedPoolMasterDataBootstrapImportChunks).toHaveBeenCalledWith('job-failed')
    )
  }, HEAVY_ROUTE_TEST_TIMEOUT_MS)

})
