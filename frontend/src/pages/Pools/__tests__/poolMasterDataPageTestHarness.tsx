import { useEffect, type ReactNode } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp, ConfigProvider } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import {
  captureUiRouteTransition,
  clearUiActionJournal,
  exportUiActionJournalBundle,
  setUiActionJournalEnabled,
} from '../../../observability/uiActionJournal'
import { HEAVY_ROUTE_TEST_TIMEOUT_MS } from '../../../test/timeouts'
import { PoolMasterDataPage } from '../PoolMasterDataPage'

const { mockNavigate } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const mockListMasterDataParties = vi.fn()
const mockUpsertMasterDataParty = vi.fn()
const mockListMasterDataItems = vi.fn()
const mockUpsertMasterDataItem = vi.fn()
const mockListMasterDataContracts = vi.fn()
const mockUpsertMasterDataContract = vi.fn()
const mockListMasterDataTaxProfiles = vi.fn()
const mockUpsertMasterDataTaxProfile = vi.fn()
const mockListMasterDataGlAccounts = vi.fn()
const mockGetMasterDataGlAccount = vi.fn()
const mockUpsertMasterDataGlAccount = vi.fn()
const mockListMasterDataGlAccountSets = vi.fn()
const mockGetMasterDataGlAccountSet = vi.fn()
const mockUpsertMasterDataGlAccountSet = vi.fn()
const mockPublishMasterDataGlAccountSet = vi.fn()
const mockListMasterDataBindings = vi.fn()
const mockUpsertMasterDataBinding = vi.fn()
const mockGetPoolMasterDataRegistry = vi.fn()
const mockListPoolTargetClusters = vi.fn()
const mockListPoolTargetDatabases = vi.fn()
const mockUpsertPoolMasterDataChartSource = vi.fn()
const mockListPoolMasterDataChartSources = vi.fn()
const mockCreatePoolMasterDataChartJob = vi.fn()
const mockListPoolMasterDataChartJobs = vi.fn()
const mockGetPoolMasterDataChartJob = vi.fn()
const mockListMasterDataSyncStatus = vi.fn()
const mockListMasterDataSyncConflicts = vi.fn()
const mockRetryMasterDataSyncConflict = vi.fn()
const mockReconcileMasterDataSyncConflict = vi.fn()
const mockResolveMasterDataSyncConflict = vi.fn()
const mockListPoolMasterDataSyncLaunches = vi.fn()
const mockGetPoolMasterDataSyncLaunch = vi.fn()
const mockCreatePoolMasterDataSyncLaunch = vi.fn()
const mockRunPoolMasterDataBootstrapCollectionPreflight = vi.fn()
const mockCreatePoolMasterDataBootstrapCollection = vi.fn()
const mockListPoolMasterDataBootstrapCollections = vi.fn()
const mockGetPoolMasterDataBootstrapCollection = vi.fn()
const mockRunPoolMasterDataBootstrapImportPreflight = vi.fn()
const mockCreatePoolMasterDataBootstrapImportJob = vi.fn()
const mockListPoolMasterDataBootstrapImportJobs = vi.fn()
const mockGetPoolMasterDataBootstrapImportJob = vi.fn()
const mockCancelPoolMasterDataBootstrapImportJob = vi.fn()
const mockRetryFailedPoolMasterDataBootstrapImportChunks = vi.fn()
const mockListPoolMasterDataDedupeReviewItems = vi.fn()
const mockGetPoolMasterDataDedupeReviewItem = vi.fn()
const mockApplyPoolMasterDataDedupeReviewAction = vi.fn()
let consoleErrorSpy: ReturnType<typeof vi.spyOn> | null = null
let setIntervalSpy: ReturnType<typeof vi.spyOn> | null = null

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

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

const buildBootstrapCollection = (overrides: Record<string, unknown> = {}) => ({
  id: 'collection-1',
  tenant_id: 'tenant-1',
  target_mode: 'database_set',
  mode: 'dry_run',
  cluster_id: null,
  database_ids: ['db-1'],
  entity_scope: ['party', 'item'],
  status: 'dry_run_completed',
  requested_by_id: 1,
  requested_by_username: 'admin',
  last_error_code: '',
  last_error: '',
  aggregate_counters: {
    total_items: 1,
    scheduled: 0,
    coalesced: 0,
    skipped: 0,
    failed: 0,
    completed: 1,
  },
  progress: {
    total_items: 1,
    scheduled: 0,
    coalesced: 0,
    skipped: 0,
    failed: 0,
    completed: 1,
    terminal_items: 1,
    completion_ratio: 1,
  },
  child_job_status_counts: {},
  aggregate_preflight_result: {
    ok: true,
    target_mode: 'database_set',
    cluster_id: null,
    database_ids: ['db-1'],
    database_count: 1,
    entity_scope: ['party', 'item'],
    databases: [],
    errors: [],
    generated_at: '2026-01-01T00:00:00Z',
  },
  aggregate_dry_run_summary: {
    rows_total: 2,
    chunks_total: 1,
    entities: [],
  },
  audit_trail: [],
  items: [
    {
      id: 'collection-item-1',
      database_id: 'db-1',
      database_name: 'Main DB',
      cluster_id: 'cluster-1',
      status: 'completed',
      reason_code: '',
      reason_detail: '',
      child_job_id: null,
      child_job_status: '',
      preflight_result: { ok: true },
      dry_run_summary: { rows_total: 2, chunks_total: 1 },
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:02:00Z',
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:02:00Z',
  ...overrides,
})

const buildChartSnapshot = (overrides: Record<string, unknown> = {}) => ({
  id: 'chart-snapshot-1',
  tenant_id: 'tenant-1',
  chart_source_id: 'chart-source-1',
  fingerprint: 'chart-fingerprint-1',
  row_count: 2,
  materialized_count: 1,
  updated_count: 1,
  unchanged_count: 0,
  retired_count: 0,
  metadata: {},
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

const buildChartJobSummary = (overrides: Record<string, unknown> = {}) => ({
  id: 'chart-job-summary-1',
  tenant_id: 'tenant-1',
  chart_source_id: 'chart-source-1',
  snapshot: buildChartSnapshot(),
  mode: 'materialize',
  status: 'succeeded',
  database_ids: [],
  requested_by_username: 'admin',
  last_error_code: '',
  last_error: '',
  counters: {},
  diagnostics: {},
  audit_trail: [],
  started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:01:00Z',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:01:00Z',
  ...overrides,
})

const buildChartSource = (overrides: Record<string, unknown> = {}) => ({
  id: 'chart-source-1',
  tenant_id: 'tenant-1',
  database_id: 'db-1',
  database_name: 'Main DB',
  cluster_id: 'cluster-1',
  chart_identity: 'ChartOfAccounts_Main',
  config_name: 'Accounting Enterprise',
  config_version: '3.0.1',
  status: 'active',
  last_success_at: '2026-01-01T00:01:00Z',
  last_error_code: '',
  last_error: '',
  metadata: {},
  latest_snapshot: buildChartSnapshot(),
  latest_job: buildChartJobSummary(),
  candidate_databases: [
    {
      database_id: 'db-2',
      database_name: 'Replica DB',
      cluster_id: 'cluster-1',
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:01:00Z',
  ...overrides,
})

const buildChartJob = (overrides: Record<string, unknown> = {}) => ({
  id: 'chart-job-1',
  tenant_id: 'tenant-1',
  chart_source_id: 'chart-source-1',
  chart_source: buildChartSource(),
  snapshot: buildChartSnapshot(),
  mode: 'materialize',
  status: 'succeeded',
  database_ids: [],
  requested_by_username: 'admin',
  last_error_code: '',
  last_error: '',
  counters: {
    rows_total: 2,
    created_count: 1,
    updated_count: 1,
    unchanged_count: 0,
    retired_count: 0,
  },
  diagnostics: {},
  audit_trail: [],
  follower_statuses: [],
  started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:01:00Z',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:01:00Z',
  ...overrides,
})

const buildSyncLaunch = (overrides: Record<string, unknown> = {}) => ({
  id: 'launch-1',
  tenant_id: 'tenant-1',
  mode: 'inbound',
  target_mode: 'database_set',
  cluster_id: null,
  database_ids: ['db-1'],
  entity_scope: ['party', 'item'],
  status: 'completed',
  workflow_execution_id: 'wf-launch-1',
  operation_id: 'op-launch-1',
  requested_by_id: 1,
  requested_by_username: 'admin',
  last_error_code: '',
  last_error: '',
  aggregate_counters: {
    total_items: 2,
    scheduled: 1,
    coalesced: 0,
    skipped: 0,
    failed: 0,
    completed: 1,
  },
  progress: {
    total_items: 2,
    scheduled: 1,
    coalesced: 0,
    skipped: 0,
    failed: 0,
    completed: 1,
    terminal_items: 1,
    completion_ratio: 0.5,
  },
  child_job_status_counts: {
    queued: 1,
  },
  audit_trail: [],
  items: [
    {
      id: 'launch-item-1',
      database_id: 'db-1',
      database_name: 'Main DB',
      cluster_id: 'cluster-1',
      entity_type: 'party',
      status: 'scheduled',
      reason_code: '',
      reason_detail: '',
      child_job_id: 'job-sync-1',
      child_job_status: 'queued',
      child_workflow_execution_id: 'wf-child-1',
      child_operation_id: 'op-child-1',
      metadata: {},
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:01:00Z',
  ...overrides,
})

const buildDedupeReviewItem = (overrides: Record<string, unknown> = {}) => ({
  id: 'review-1',
  tenant_id: 'tenant-1',
  cluster_id: 'cluster-review-1',
  entity_type: 'party',
  status: 'pending_review',
  reason_code: 'MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS',
  conflicting_fields: ['name'],
  source_snapshot: [],
  proposed_survivor_source_record_id: 'source-1',
  cluster: {
    id: 'cluster-review-1',
    entity_type: 'party',
    canonical_id: 'party-001',
    dedupe_key: 'party:7701001001:770101001',
    status: 'pending_review',
    rollout_eligible: false,
    reason_code: 'MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS',
    reason_detail: 'Source record conflicts with an existing canonical cluster and requires operator review.',
    normalized_signals: {
      dedupe_key: 'party:7701001001:770101001',
      inn: '7701001001',
      kpp: '770101001',
    },
    conflicting_fields: ['name'],
    resolved_at: null,
    resolved_by_id: null,
  },
  affected_bindings: [
    {
      id: 'binding-1',
      database_id: 'db-1',
      database_name: 'Main DB',
      ib_ref_key: 'ref-party-001',
      ib_catalog_kind: 'counterparty',
      owner_counterparty_canonical_id: '',
      chart_identity: '',
      sync_status: 'resolved',
    },
  ],
  runtime_blockers: [
    {
      code: 'publication',
      label: 'Publication',
      detail: 'Publication remains blocked until the review item is resolved.',
    },
    {
      code: 'manual_sync_launch',
      label: 'Manual Sync Launch',
      detail: 'Manual rollout remains blocked until the review item is resolved.',
    },
  ],
  source_records: [
    {
      id: 'source-1',
      tenant_id: 'tenant-1',
      entity_type: 'party',
      cluster_id: 'cluster-review-1',
      source_database_id: 'db-1',
      source_database_name: 'Main DB',
      source_ref: 'Ref_A',
      source_fingerprint: 'fp-a',
      source_canonical_id: 'party-a',
      canonical_id: 'party-001',
      origin_kind: 'bootstrap_import',
      origin_ref: 'job-a',
      resolution_status: 'pending_review',
      resolution_reason: 'MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS',
      normalized_signals: {
        dedupe_key: 'party:7701001001:770101001',
        name: 'ooo romashka',
      },
      payload_snapshot: {
        name: 'ООО Ромашка',
        inn: '7701001001',
      },
      metadata: {},
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'source-2',
      tenant_id: 'tenant-1',
      entity_type: 'party',
      cluster_id: 'cluster-review-1',
      source_database_id: 'db-2',
      source_database_name: 'Replica DB',
      source_ref: 'Ref_B',
      source_fingerprint: 'fp-b',
      source_canonical_id: 'party-b',
      canonical_id: 'party-001',
      origin_kind: 'bootstrap_import',
      origin_ref: 'job-b',
      resolution_status: 'pending_review',
      resolution_reason: 'MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS',
      normalized_signals: {
        dedupe_key: 'party:7701001001:770101001',
        name: 'ooo romashka kompaniya',
      },
      payload_snapshot: {
        name: 'ООО Ромашка Компания',
        inn: '7701001001',
      },
      metadata: {},
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  resolved_at: null,
  resolved_by_id: null,
  resolved_by_username: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  metadata: {
    detail: 'Source record conflicts with an existing canonical cluster and requires operator review.',
  },
  ...overrides,
})

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const { createPoolMasterDataAntdTestDouble } = await import('./poolMasterDataAntdTestDouble')
  return createPoolMasterDataAntdTestDouble(actual)
})

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../components/platform', async () => {
  const actual = await vi.importActual<typeof import('../../../components/platform')>('../../../components/platform')

  const renderTableCell = (
    column: {
      dataIndex?: string | string[]
      key?: string
      render?: (value: unknown, row: Record<string, unknown>, index: number) => ReactNode
      title?: ReactNode
    },
    row: Record<string, unknown>,
    index: number,
  ) => {
    const dataIndex = column.dataIndex
    const value = Array.isArray(dataIndex) ? dataIndex.reduce<unknown>((current, key) => (current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined), row) : typeof dataIndex === 'string' ? row[dataIndex] : undefined

    return column.render ? column.render(value, row, index) : (value as ReactNode)
  }

  return {
    ...actual,
    WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
      <div>
        {header}
        {children}
      </div>
    ),
    PageHeader: ({ title, subtitle }: { title: ReactNode; subtitle?: ReactNode }) => (
      <div>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    ),
    MasterDetailShell: ({ list, detail, detailOpen, detailDrawerTitle, onCloseDetail }: { list: ReactNode; detail: ReactNode; detailOpen?: boolean; detailDrawerTitle?: ReactNode; onCloseDetail?: () => void }) => (
      <div>
        <section>{list}</section>
        <section data-detail-open={detailOpen ? 'true' : 'false'}>
          {detailDrawerTitle ? <h3>{detailDrawerTitle}</h3> : null}
          {detailOpen && onCloseDetail ? (
            <button type="button" onClick={onCloseDetail}>
              Close detail
            </button>
          ) : null}
          {detail}
        </section>
      </div>
    ),
    EntityList: ({ title, extra, toolbar, error, loading, emptyDescription, dataSource, renderItem }: { title?: ReactNode; extra?: ReactNode; toolbar?: ReactNode; error?: ReactNode; loading?: boolean; emptyDescription?: ReactNode; dataSource?: Array<Record<string, unknown>>; renderItem: (item: Record<string, unknown>) => ReactNode }) => (
      <div>
        {title ? <h3>{title}</h3> : null}
        {extra}
        {toolbar}
        {error ? error : loading ? <div>Loading</div> : (dataSource?.length ?? 0) === 0 ? <div>{emptyDescription}</div> : (dataSource ?? []).map((item, index) => <div key={String(item.key ?? item.id ?? index)}>{renderItem(item)}</div>)}
      </div>
    ),
    EntityDetails: ({ title, extra, error, loading, empty, emptyDescription, children }: { title: ReactNode; extra?: ReactNode; error?: ReactNode; loading?: boolean; empty?: boolean; emptyDescription?: ReactNode; children?: ReactNode }) => (
      <div>
        <h3>{title}</h3>
        {extra}
        {error ? error : loading ? <div>Loading</div> : empty ? emptyDescription : children}
      </div>
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
      title: ReactNode
      extra?: ReactNode
      toolbar?: ReactNode
      error?: ReactNode
      loading?: boolean
      emptyDescription?: ReactNode
      dataSource: Array<Record<string, unknown>>
      columns: Array<{
        title?: ReactNode
        dataIndex?: string | string[]
        key?: string
        render?: (value: unknown, row: Record<string, unknown>, index: number) => ReactNode
      }>
      rowKey: string | ((row: Record<string, unknown>) => string)
      onRow?: (row: Record<string, unknown>, index?: number) => { onClick?: () => void }
      rowClassName?: (row: Record<string, unknown>, index?: number) => string
    }) => (
      <section>
        <div>
          <h3>{title}</h3>
          {extra}
        </div>
        {toolbar}
        {error ? (
          error
        ) : loading ? (
          <div>Loading</div>
        ) : dataSource.length === 0 ? (
          <div>{emptyDescription}</div>
        ) : (
          <table>
            <thead>
              <tr>
                {columns.map((column, index) => (
                  <th key={String(column.key ?? column.dataIndex ?? index)}>{column.title}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataSource.map((row, rowIndex) => {
                const resolvedRowKey = typeof rowKey === 'function' ? rowKey(row) : String(row[rowKey] ?? rowIndex)
                const rowProps = onRow?.(row, rowIndex)
                return (
                  <tr key={resolvedRowKey} className={rowClassName?.(row, rowIndex)} onClick={rowProps?.onClick}>
                    {columns.map((column, columnIndex) => (
                      <td key={String(column.key ?? column.dataIndex ?? columnIndex)}>{renderTableCell(column, row, rowIndex)}</td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    ),
    StatusBadge: ({ status, label }: { status?: ReactNode; label?: ReactNode }) => <span>{label ?? status}</span>,
    JsonBlock: ({ title, value, dataTestId }: { title?: ReactNode; value: unknown; dataTestId?: string }) => (
      <section>
        {title ? <h4>{title}</h4> : null}
        <pre data-testid={dataTestId}>{JSON.stringify(value ?? {}, null, 2)}</pre>
      </section>
    ),
    ModalFormShell: ({ open, onClose, onSubmit, title, subtitle, submitText, cancelText, confirmLoading, submitDisabled, footerStart, children, submitButtonTestId }: { open: boolean; onClose: () => void; onSubmit?: () => void | Promise<void>; title?: ReactNode; subtitle?: ReactNode; submitText?: ReactNode; cancelText?: ReactNode; confirmLoading?: boolean; submitDisabled?: boolean; footerStart?: ReactNode; children: ReactNode; submitButtonTestId?: string }) =>
      open ? (
        <section role="dialog">
          {title ? <h4>{title}</h4> : null}
          {subtitle ? <p>{subtitle}</p> : null}
          {children}
          {footerStart}
          <button type="button" onClick={onClose}>
            {cancelText ?? 'Cancel'}
          </button>
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
        </section>
      ) : null,
    DrawerFormShell: ({ open, onClose, onSubmit, title, subtitle, submitText, confirmLoading, submitDisabled, extra, children, submitButtonTestId, drawerTestId }: { open: boolean; onClose: () => void; onSubmit?: () => void | Promise<void>; title?: ReactNode; subtitle?: ReactNode; submitText?: ReactNode; confirmLoading?: boolean; submitDisabled?: boolean; extra?: ReactNode; children: ReactNode; submitButtonTestId?: string; drawerTestId?: string }) =>
      open ? (
        <section data-testid={drawerTestId}>
          {title ? <h4>{title}</h4> : null}
          {subtitle ? <p>{subtitle}</p> : null}
          {extra}
          {children}
          <button type="button" onClick={onClose}>
            Close
          </button>
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
        </section>
      ) : null,
  }
})

vi.mock('../../../api/intercompanyPools', () => ({
  listMasterDataParties: (...args: unknown[]) => mockListMasterDataParties(...args),
  upsertMasterDataParty: (...args: unknown[]) => mockUpsertMasterDataParty(...args),
  listMasterDataItems: (...args: unknown[]) => mockListMasterDataItems(...args),
  upsertMasterDataItem: (...args: unknown[]) => mockUpsertMasterDataItem(...args),
  listMasterDataContracts: (...args: unknown[]) => mockListMasterDataContracts(...args),
  upsertMasterDataContract: (...args: unknown[]) => mockUpsertMasterDataContract(...args),
  listMasterDataTaxProfiles: (...args: unknown[]) => mockListMasterDataTaxProfiles(...args),
  upsertMasterDataTaxProfile: (...args: unknown[]) => mockUpsertMasterDataTaxProfile(...args),
  listMasterDataGlAccounts: (...args: unknown[]) => mockListMasterDataGlAccounts(...args),
  getMasterDataGlAccount: (...args: unknown[]) => mockGetMasterDataGlAccount(...args),
  upsertMasterDataGlAccount: (...args: unknown[]) => mockUpsertMasterDataGlAccount(...args),
  listMasterDataGlAccountSets: (...args: unknown[]) => mockListMasterDataGlAccountSets(...args),
  getMasterDataGlAccountSet: (...args: unknown[]) => mockGetMasterDataGlAccountSet(...args),
  upsertMasterDataGlAccountSet: (...args: unknown[]) => mockUpsertMasterDataGlAccountSet(...args),
  publishMasterDataGlAccountSet: (...args: unknown[]) => mockPublishMasterDataGlAccountSet(...args),
  listMasterDataBindings: (...args: unknown[]) => mockListMasterDataBindings(...args),
  upsertMasterDataBinding: (...args: unknown[]) => mockUpsertMasterDataBinding(...args),
  getPoolMasterDataRegistry: (...args: unknown[]) => mockGetPoolMasterDataRegistry(...args),
  listPoolTargetClusters: (...args: unknown[]) => mockListPoolTargetClusters(...args),
  listPoolTargetDatabases: (...args: unknown[]) => mockListPoolTargetDatabases(...args),
  upsertPoolMasterDataChartSource: (...args: unknown[]) => mockUpsertPoolMasterDataChartSource(...args),
  listPoolMasterDataChartSources: (...args: unknown[]) => mockListPoolMasterDataChartSources(...args),
  createPoolMasterDataChartJob: (...args: unknown[]) => mockCreatePoolMasterDataChartJob(...args),
  listPoolMasterDataChartJobs: (...args: unknown[]) => mockListPoolMasterDataChartJobs(...args),
  getPoolMasterDataChartJob: (...args: unknown[]) => mockGetPoolMasterDataChartJob(...args),
  listMasterDataSyncStatus: (...args: unknown[]) => mockListMasterDataSyncStatus(...args),
  listMasterDataSyncConflicts: (...args: unknown[]) => mockListMasterDataSyncConflicts(...args),
  retryMasterDataSyncConflict: (...args: unknown[]) => mockRetryMasterDataSyncConflict(...args),
  reconcileMasterDataSyncConflict: (...args: unknown[]) => mockReconcileMasterDataSyncConflict(...args),
  resolveMasterDataSyncConflict: (...args: unknown[]) => mockResolveMasterDataSyncConflict(...args),
  listPoolMasterDataSyncLaunches: (...args: unknown[]) => mockListPoolMasterDataSyncLaunches(...args),
  getPoolMasterDataSyncLaunch: (...args: unknown[]) => mockGetPoolMasterDataSyncLaunch(...args),
  createPoolMasterDataSyncLaunch: (...args: unknown[]) => mockCreatePoolMasterDataSyncLaunch(...args),
  runPoolMasterDataBootstrapCollectionPreflight: (...args: unknown[]) => mockRunPoolMasterDataBootstrapCollectionPreflight(...args),
  createPoolMasterDataBootstrapCollection: (...args: unknown[]) => mockCreatePoolMasterDataBootstrapCollection(...args),
  listPoolMasterDataBootstrapCollections: (...args: unknown[]) => mockListPoolMasterDataBootstrapCollections(...args),
  getPoolMasterDataBootstrapCollection: (...args: unknown[]) => mockGetPoolMasterDataBootstrapCollection(...args),
  runPoolMasterDataBootstrapImportPreflight: (...args: unknown[]) => mockRunPoolMasterDataBootstrapImportPreflight(...args),
  createPoolMasterDataBootstrapImportJob: (...args: unknown[]) => mockCreatePoolMasterDataBootstrapImportJob(...args),
  listPoolMasterDataBootstrapImportJobs: (...args: unknown[]) => mockListPoolMasterDataBootstrapImportJobs(...args),
  getPoolMasterDataBootstrapImportJob: (...args: unknown[]) => mockGetPoolMasterDataBootstrapImportJob(...args),
  cancelPoolMasterDataBootstrapImportJob: (...args: unknown[]) => mockCancelPoolMasterDataBootstrapImportJob(...args),
  retryFailedPoolMasterDataBootstrapImportChunks: (...args: unknown[]) => mockRetryFailedPoolMasterDataBootstrapImportChunks(...args),
  listPoolMasterDataDedupeReviewItems: (...args: unknown[]) => mockListPoolMasterDataDedupeReviewItems(...args),
  getPoolMasterDataDedupeReviewItem: (...args: unknown[]) => mockGetPoolMasterDataDedupeReviewItem(...args),
  applyPoolMasterDataDedupeReviewAction: (...args: unknown[]) => mockApplyPoolMasterDataDedupeReviewAction(...args),
}))

function renderPage(path = '/pools/master-data') {
  function LocationProbe() {
    const location = useLocation()
    useEffect(() => {
      captureUiRouteTransition(location)
    }, [location])
    return <output data-testid="pool-master-data-route-location">{`${location.pathname}${location.search}`}</output>
  }

  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <ConfigProvider theme={{ token: { motion: false } }} wave={{ disabled: true }}>
        <AntApp>
          <PoolMasterDataPage />
          <LocationProbe />
        </AntApp>
      </ConfigProvider>
    </MemoryRouter>,
  )
}

function openSelectByTestId(testId: string) {
  const select = screen.getByTestId(testId)
  const trigger = select.querySelector('.ant-select-selector') as HTMLElement | null
  fireEvent.mouseDown(trigger ?? select)
}

function getOpenSelectDropdown() {
  const dropdowns = Array.from(document.querySelectorAll('.ant-select-dropdown')).filter((node) => !node.classList.contains('ant-select-dropdown-hidden'))
  expect(dropdowns.length).toBeGreaterThan(0)
  return dropdowns[dropdowns.length - 1] as HTMLElement
}

async function selectDropdownOption(label: string | RegExp) {
  const matcher = typeof label === 'string' ? label : (content: string) => label.test(content)
  const matches = await screen.findAllByText(matcher)
  const option = [...matches].reverse().find((node) => node.closest('.ant-select-item-option'))
  expect(option).toBeTruthy()
  fireEvent.click(option as Element)
}

export function setupPoolMasterDataPageTestSuite() {
  beforeEach(() => {
    setUiActionJournalEnabled(true)
    clearUiActionJournal()
    mockListMasterDataParties.mockReset()
    mockUpsertMasterDataParty.mockReset()
    mockListMasterDataItems.mockReset()
    mockUpsertMasterDataItem.mockReset()
    mockListMasterDataContracts.mockReset()
    mockUpsertMasterDataContract.mockReset()
    mockListMasterDataTaxProfiles.mockReset()
    mockUpsertMasterDataTaxProfile.mockReset()
    mockListMasterDataGlAccounts.mockReset()
    mockGetMasterDataGlAccount.mockReset()
    mockUpsertMasterDataGlAccount.mockReset()
    mockListMasterDataGlAccountSets.mockReset()
    mockGetMasterDataGlAccountSet.mockReset()
    mockUpsertMasterDataGlAccountSet.mockReset()
    mockPublishMasterDataGlAccountSet.mockReset()
    mockListMasterDataBindings.mockReset()
    mockUpsertMasterDataBinding.mockReset()
    mockGetPoolMasterDataRegistry.mockReset()
    mockListPoolTargetClusters.mockReset()
    mockListPoolTargetDatabases.mockReset()
    mockUpsertPoolMasterDataChartSource.mockReset()
    mockListPoolMasterDataChartSources.mockReset()
    mockCreatePoolMasterDataChartJob.mockReset()
    mockListPoolMasterDataChartJobs.mockReset()
    mockGetPoolMasterDataChartJob.mockReset()
    mockListMasterDataSyncStatus.mockReset()
    mockListMasterDataSyncConflicts.mockReset()
    mockRetryMasterDataSyncConflict.mockReset()
    mockReconcileMasterDataSyncConflict.mockReset()
    mockResolveMasterDataSyncConflict.mockReset()
    mockListPoolMasterDataSyncLaunches.mockReset()
    mockGetPoolMasterDataSyncLaunch.mockReset()
    mockCreatePoolMasterDataSyncLaunch.mockReset()
    mockRunPoolMasterDataBootstrapCollectionPreflight.mockReset()
    mockCreatePoolMasterDataBootstrapCollection.mockReset()
    mockListPoolMasterDataBootstrapCollections.mockReset()
    mockGetPoolMasterDataBootstrapCollection.mockReset()
    mockRunPoolMasterDataBootstrapImportPreflight.mockReset()
    mockCreatePoolMasterDataBootstrapImportJob.mockReset()
    mockListPoolMasterDataBootstrapImportJobs.mockReset()
    mockGetPoolMasterDataBootstrapImportJob.mockReset()
    mockCancelPoolMasterDataBootstrapImportJob.mockReset()
    mockRetryFailedPoolMasterDataBootstrapImportChunks.mockReset()
    mockListPoolMasterDataDedupeReviewItems.mockReset()
    mockGetPoolMasterDataDedupeReviewItem.mockReset()
    mockApplyPoolMasterDataDedupeReviewAction.mockReset()
    mockNavigate.mockReset()
    setIntervalSpy = vi.spyOn(window, 'setInterval').mockImplementation(() => 0 as unknown as ReturnType<typeof window.setInterval>)
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      const [firstArg] = args
      if (typeof firstArg === 'string' && firstArg.includes('not wrapped in act')) {
        return
      }
    })

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
    mockListMasterDataGlAccounts.mockResolvedValue({
      gl_accounts: [
        {
          id: 'gl-account-1',
          tenant_id: 'tenant-1',
          canonical_id: 'gl-account-001',
          code: '10.01',
          name: 'Main Account',
          chart_identity: 'ChartOfAccounts_Main',
          config_name: 'Accounting Enterprise',
          config_version: '3.0.1',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 100, offset: 0, total: 1 },
    })
    mockGetMasterDataGlAccount.mockResolvedValue({
      gl_account: {
        id: 'gl-account-1',
        tenant_id: 'tenant-1',
        canonical_id: 'gl-account-001',
        code: '10.01',
        name: 'Main Account',
        chart_identity: 'ChartOfAccounts_Main',
        config_name: 'Accounting Enterprise',
        config_version: '3.0.1',
        metadata: {},
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    })
    mockListMasterDataGlAccountSets.mockResolvedValue({
      gl_account_sets: [
        {
          gl_account_set_id: 'gl-set-1',
          canonical_id: 'gl-set-001',
          name: 'Quarter Scope',
          description: 'Draft for Q1',
          chart_identity: 'ChartOfAccounts_Main',
          config_name: 'Accounting Enterprise',
          config_version: '3.0.1',
          draft_members_count: 1,
          published_revision_number: 1,
          published_revision_id: 'gl-set-rev-1',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 100, offset: 0, total: 1 },
    })
    mockGetMasterDataGlAccountSet.mockResolvedValue({
      gl_account_set: {
        gl_account_set_id: 'gl-set-1',
        canonical_id: 'gl-set-001',
        name: 'Quarter Scope',
        description: 'Draft for Q1',
        chart_identity: 'ChartOfAccounts_Main',
        config_name: 'Accounting Enterprise',
        config_version: '3.0.1',
        draft_members_count: 1,
        published_revision_number: 1,
        published_revision_id: 'gl-set-rev-1',
        metadata: {},
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        draft_members: [
          {
            gl_account_id: 'gl-account-1',
            canonical_id: 'gl-account-001',
            code: '10.01',
            name: 'Main Account',
            chart_identity: 'ChartOfAccounts_Main',
            config_name: 'Accounting Enterprise',
            config_version: '3.0.1',
            sort_order: 0,
            metadata: {},
          },
        ],
        revisions: [
          {
            gl_account_set_revision_id: 'gl-set-rev-1',
            gl_account_set_id: 'gl-set-1',
            contract_version: 'pool_master_gl_account_set.v1',
            revision_number: 1,
            name: 'Quarter Scope',
            description: 'Draft for Q1',
            chart_identity: 'ChartOfAccounts_Main',
            config_name: 'Accounting Enterprise',
            config_version: '3.0.1',
            members: [
              {
                gl_account_id: 'gl-account-1',
                canonical_id: 'gl-account-001',
                code: '10.01',
                name: 'Main Account',
                chart_identity: 'ChartOfAccounts_Main',
                config_name: 'Accounting Enterprise',
                config_version: '3.0.1',
                sort_order: 0,
                metadata: {},
              },
            ],
            metadata: {},
            created_by: 'user-1',
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
        published_revision: {
          gl_account_set_revision_id: 'gl-set-rev-1',
          gl_account_set_id: 'gl-set-1',
          contract_version: 'pool_master_gl_account_set.v1',
          revision_number: 1,
          name: 'Quarter Scope',
          description: 'Draft for Q1',
          chart_identity: 'ChartOfAccounts_Main',
          config_name: 'Accounting Enterprise',
          config_version: '3.0.1',
          members: [
            {
              gl_account_id: 'gl-account-1',
              canonical_id: 'gl-account-001',
              code: '10.01',
              name: 'Main Account',
              chart_identity: 'ChartOfAccounts_Main',
              config_name: 'Accounting Enterprise',
              config_version: '3.0.1',
              sort_order: 0,
              metadata: {},
            },
          ],
          metadata: {},
          created_by: 'user-1',
          created_at: '2026-01-01T00:00:00Z',
        },
      },
    })
    mockListMasterDataBindings.mockResolvedValue({
      bindings: [],
      meta: { limit: 200, offset: 0, total: 0 },
    })
    mockGetPoolMasterDataRegistry.mockResolvedValue({
      contract_version: 'pool_master_data_registry.v1',
      count: 7,
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
          entity_type: 'gl_account',
          label: 'GL Account',
          kind: 'canonical',
          display_order: 45,
          binding_scope_fields: ['canonical_id', 'database_id', 'chart_identity'],
          capabilities: {
            direct_binding: true,
            token_exposure: true,
            bootstrap_import: true,
            outbox_fanout: false,
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
          bootstrap_contract: { enabled: true, dependency_order: 35 },
          runtime_consumers: ['bindings', 'bootstrap_import', 'token_catalog', 'token_parser'],
        },
        {
          entity_type: 'gl_account_set',
          label: 'GL Account Set',
          kind: 'profile',
          display_order: 50,
          binding_scope_fields: [],
          capabilities: {
            direct_binding: false,
            token_exposure: false,
            bootstrap_import: false,
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
          bootstrap_contract: { enabled: false, dependency_order: null },
          runtime_consumers: ['profiles'],
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
    mockListPoolTargetClusters.mockResolvedValue([{ id: 'cluster-1', name: 'Main Cluster' }])
    mockListPoolTargetDatabases.mockResolvedValue([
      {
        id: 'db-1',
        name: 'Main DB',
        cluster_id: 'cluster-1',
        cluster_all_eligibility_state: 'eligible',
      },
      {
        id: 'db-2',
        name: 'Replica DB',
        cluster_id: 'cluster-1',
        cluster_all_eligibility_state: 'eligible',
      },
    ])
    mockUpsertPoolMasterDataChartSource.mockResolvedValue({
      source: buildChartSource(),
    })
    mockListPoolMasterDataChartSources.mockResolvedValue({
      count: 1,
      limit: 20,
      offset: 0,
      sources: [buildChartSource()],
    })
    mockCreatePoolMasterDataChartJob.mockResolvedValue({
      job: buildChartJob(),
    })
    mockListPoolMasterDataChartJobs.mockResolvedValue({
      count: 0,
      limit: 20,
      offset: 0,
      jobs: [],
    })
    mockGetPoolMasterDataChartJob.mockResolvedValue({
      job: buildChartJob(),
    })
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
    mockListPoolMasterDataSyncLaunches.mockResolvedValue({
      launches: [],
      count: 0,
      limit: 20,
      offset: 0,
    })
    mockGetPoolMasterDataSyncLaunch.mockResolvedValue({
      launch: buildSyncLaunch(),
    })
    mockCreatePoolMasterDataSyncLaunch.mockResolvedValue({
      launch: buildSyncLaunch(),
    })
    mockRunPoolMasterDataBootstrapCollectionPreflight.mockResolvedValue({
      preflight: {
        ok: true,
        target_mode: 'database_set',
        cluster_id: null,
        database_ids: ['db-1'],
        database_count: 1,
        entity_scope: ['party', 'item'],
        databases: [
          {
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            ok: true,
            preflight_result: {
              ok: true,
              source_kind: 'ib_odata',
              coverage: { party: true, item: true },
              credential_strategy: 'service',
              errors: [],
              diagnostics: {},
            },
          },
        ],
        errors: [],
        generated_at: '2026-01-01T00:00:00Z',
      },
      collection: buildBootstrapCollection({
        id: 'collection-preflight',
        mode: 'preflight',
        status: 'preflight_completed',
        aggregate_dry_run_summary: {},
        items: [
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: {
              ok: true,
              source_kind: 'ib_odata',
              coverage: { party: true, item: true },
              credential_strategy: 'service',
              errors: [],
              diagnostics: {},
            },
            dry_run_summary: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
      }),
    })
    mockCreatePoolMasterDataBootstrapCollection.mockResolvedValue({
      collection: buildBootstrapCollection(),
    })
    mockListPoolMasterDataBootstrapCollections.mockResolvedValue({
      count: 0,
      limit: 20,
      offset: 0,
      collections: [],
    })
    mockGetPoolMasterDataBootstrapCollection.mockResolvedValue({
      collection: buildBootstrapCollection(),
    })
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
    mockListPoolMasterDataDedupeReviewItems.mockResolvedValue({
      items: [],
      count: 0,
      meta: { limit: 50, offset: 0, total: 0 },
    })
    mockGetPoolMasterDataDedupeReviewItem.mockResolvedValue({
      review_item: buildDedupeReviewItem(),
    })
    mockApplyPoolMasterDataDedupeReviewAction.mockResolvedValue({
      review_item: buildDedupeReviewItem({
        status: 'resolved_manual',
        resolved_at: '2026-01-01T00:03:00Z',
      }),
    })
  })

  afterEach(() => {
    setIntervalSpy?.mockRestore()
    setIntervalSpy = null
    consoleErrorSpy?.mockRestore()
    consoleErrorSpy = null
    setUiActionJournalEnabled(false)
    clearUiActionJournal()
  })
}

export function registerPoolMasterDataWorkspaceTests() {
  it(
    'renders workspace zones and loads default Party zone list',
    async () => {
      renderPage()

      expect(await screen.findByText('Pool Master Data')).toBeInTheDocument()
      expect(await screen.findByText('Party One')).toBeInTheDocument()
      expect(mockListMasterDataParties).toHaveBeenCalledWith({
        query: undefined,
        role: undefined,
        limit: 100,
        offset: 0,
      })

      fireEvent.click(screen.getByRole('button', { name: 'Open Item zone' }))
      await waitFor(() => expect(mockListMasterDataItems).toHaveBeenCalled())

      fireEvent.click(screen.getByRole('button', { name: 'Open Sync zone' }))
      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
      await waitFor(() => expect(mockListMasterDataSyncConflicts).toHaveBeenCalled())
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'captures explicit zone-switch intent and attributed route transitions in the UI journal',
    async () => {
      renderPage('/pools/master-data?tab=bindings')

      expect(await screen.findByText('Current zone: Bindings')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Open Sync zone' }))

      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())

      const bundle = exportUiActionJournalBundle()
      const routeIntent = [...bundle.events]
        .reverse()
        .find((event) => event.event_type === 'ui.action' && event.action_kind === 'route.change')
      const attributedTransition = [...bundle.events]
        .reverse()
        .find((event) => event.event_type === 'route.transition' && event.write_reason === 'zone_switch')

      expect(routeIntent).toMatchObject({
        action_kind: 'route.change',
        action_source: 'explicit',
        surface_id: 'pool_master_data',
        control_id: 'zone.sync',
        context: {
          from_tab: 'bindings',
          to_tab: 'sync',
          detail_before: false,
          detail_after: true,
        },
      })
      expect(attributedTransition).toMatchObject({
        surface_id: 'pool_master_data',
        route_writer_owner: 'pool_master_data_page',
        write_reason: 'zone_switch',
        navigation_mode: 'push',
        param_diff: {
          detail: { from: null, to: '1' },
          tab: { from: 'bindings', to: 'sync' },
        },
      })
      expect(attributedTransition).toMatchObject({
        ui_action_id: routeIntent && 'ui_action_id' in routeIntent ? routeIntent.ui_action_id : undefined,
        caused_by_ui_action_id: routeIntent && 'ui_action_id' in routeIntent ? routeIntent.ui_action_id : undefined,
      })
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'drops Sync launchId when switching to another workspace zone',
    async () => {
      renderPage('/pools/master-data?tab=sync&detail=1&databaseId=db-1&entityType=party&launchId=launch-1')

      expect(await screen.findByText('Launch Detail')).toBeInTheDocument()
      expect(screen.getByTestId('pool-master-data-route-location')).toHaveTextContent('/pools/master-data?tab=sync&detail=1&databaseId=db-1&entityType=party&launchId=launch-1')

      fireEvent.click(screen.getByRole('button', { name: 'Open Bindings zone' }))

      await waitFor(() => expect(mockListMasterDataBindings).toHaveBeenCalled())
      await waitFor(() => expect(screen.getByTestId('pool-master-data-route-location')).not.toHaveTextContent('launchId='))
      expect(screen.getByTestId('pool-master-data-route-location')).toHaveTextContent('/pools/master-data?tab=bindings&detail=1&databaseId=db-1&entityType=party')
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'emits a bounded route.loop_warning when workspace zones oscillate',
    async () => {
      renderPage('/pools/master-data?tab=bindings&detail=1')

      expect(await screen.findByText('Current zone: Bindings')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Open Sync zone' }))
      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())

      fireEvent.click(screen.getByRole('button', { name: 'Open Bindings zone' }))
      await waitFor(() => expect(mockListMasterDataBindings).toHaveBeenCalled())

      fireEvent.click(screen.getByRole('button', { name: 'Open Sync zone' }))
      await waitFor(() => expect(screen.getByTestId('pool-master-data-route-location')).toHaveTextContent('tab=sync'))

      const bundle = exportUiActionJournalBundle()
      const loopWarning = [...bundle.events]
        .reverse()
        .find((event) => event.event_type === 'route.loop_warning')

      expect(loopWarning).toMatchObject({
        route_path: '/pools/master-data',
        surface_id: 'pool_master_data',
        outcome: 'loop_warning',
        oscillating_keys: ['tab'],
        writer_owners: ['pool_master_data_page'],
        transition_count: 4,
      })
      expect(loopWarning).toMatchObject({
        observed_states: expect.arrayContaining([
          expect.objectContaining({ detail: '1', tab: 'bindings' }),
          expect.objectContaining({ detail: '1', tab: 'sync' }),
        ]),
      })
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'renders reusable account zones and loads GL Account / GL Account Set surfaces inside the same shell',
    async () => {
      renderPage()

      expect(await screen.findByText('Pool Master Data')).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Open GL Account zone' }))

      await waitFor(() =>
        expect(mockListMasterDataGlAccounts).toHaveBeenCalledWith({
          query: undefined,
          code: undefined,
          chart_identity: undefined,
          limit: 100,
          offset: 0,
        }),
      )
      expect(await screen.findByTestId('pool-master-data-gl-account-selected-id')).toHaveTextContent('gl-account-1')
      expect(screen.getAllByText('ChartOfAccounts_Main').length).toBeGreaterThan(0)

      fireEvent.click(screen.getByRole('button', { name: 'Open GL Account Set zone' }))

      await waitFor(() =>
        expect(mockListMasterDataGlAccountSets).toHaveBeenCalledWith({
          query: undefined,
          chart_identity: undefined,
          limit: 100,
          offset: 0,
        }),
      )
      expect(screen.getAllByText('Quarter Scope').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Published r1').length).toBeGreaterThan(0)
      expect(await screen.findByTestId('pool-master-data-gl-account-set-selected-id')).toHaveTextContent('gl-set-1')
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it('opens remediation target tab from query params and shows remediation context', async () => {
    renderPage('/pools/master-data?tab=bindings&entityType=organization&canonicalId=party-1&databaseId=db-1&role=organization')

    expect(await screen.findByText('Pool Master Data')).toBeInTheDocument()
    await waitFor(() => expect(mockListMasterDataBindings).toHaveBeenCalled())
    expect(screen.getByTestId('pool-master-data-remediation-context')).toHaveTextContent('entity_type=organization canonical_id=party-1 database_id=db-1')
    expect(screen.getByTestId('pool-master-data-remediation-context')).toHaveTextContent('role=organization')
  })

  it('applies chart remediation query context to the Bindings workspace default filters', async () => {
    mockListMasterDataBindings.mockResolvedValueOnce({
      bindings: [
        {
          id: 'binding-gl-account-db2',
          tenant_id: 'tenant-1',
          entity_type: 'gl_account',
          canonical_id: 'gl-account-001',
          database_id: 'db-2',
          ib_ref_key: 'ref-gl-db2',
          chart_identity: 'ChartOfAccounts_Main',
          sync_status: 'resolved',
          fingerprint: 'fp-db2',
          metadata: {},
          last_synced_at: '2026-01-01T00:00:00Z',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 200, offset: 0, total: 1 },
    })

    renderPage('/pools/master-data?tab=bindings&entityType=gl_account&canonicalId=gl-account-001&databaseId=db-2')

    await waitFor(() =>
      expect(mockListMasterDataBindings).toHaveBeenCalledWith({
        entity_type: 'gl_account',
        canonical_id: 'gl-account-001',
        database_id: 'db-2',
        limit: 200,
        offset: 0,
      }),
    )
    expect(await screen.findByText('gl-account-001')).toBeInTheDocument()
    expect(screen.getAllByText('Replica DB').length).toBeGreaterThan(0)
  })

  it(
    'renders Dedupe Review tab and applies choose survivor action',
    async () => {
      const user = userEvent.setup()
      const pendingReview = buildDedupeReviewItem()
      const resolvedReview = buildDedupeReviewItem({
        status: 'resolved_manual',
        resolved_at: '2026-01-01T00:03:00Z',
        resolved_by_username: 'admin',
      })
      mockListPoolMasterDataDedupeReviewItems.mockResolvedValue({
        items: [pendingReview],
        count: 1,
        meta: { limit: 50, offset: 0, total: 1 },
      })
      mockGetPoolMasterDataDedupeReviewItem.mockResolvedValue({
        review_item: pendingReview,
      })
      mockApplyPoolMasterDataDedupeReviewAction.mockResolvedValue({
        review_item: resolvedReview,
      })

      renderPage('/pools/master-data?tab=dedupe-review&reviewItemId=review-1&clusterId=cluster-review-1&entityType=party&databaseId=db-1')

      expect(await screen.findByText('Review Queue')).toBeInTheDocument()
      expect(await screen.findByText('Review Detail')).toBeInTheDocument()
      expect((await screen.findAllByText('MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS')).length).toBeGreaterThan(0)
      expect(screen.getByTestId('pool-master-data-remediation-context')).toHaveTextContent('cluster_id=cluster-review-1 review_item_id=review-1')

      await user.click(screen.getByLabelText('Use Ref_B as survivor'))
      await user.click(screen.getByRole('button', { name: 'Choose Survivor' }))

      await waitFor(() =>
        expect(mockApplyPoolMasterDataDedupeReviewAction).toHaveBeenCalledWith('review-1', {
          action: 'choose_survivor',
          source_record_id: 'source-2',
          note: 'Manual choose survivor from Dedupe Review UI',
          metadata: { source: 'ui' },
        }),
      )
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'keeps review detail context after choose survivor under pending_review filter',
    async () => {
      const user = userEvent.setup()
      const pendingReview = buildDedupeReviewItem()
      const resolvedReview = buildDedupeReviewItem({
        status: 'resolved_manual',
        resolved_at: '2026-01-01T00:03:00Z',
        resolved_by_username: 'admin',
        cluster: {
          ...buildDedupeReviewItem().cluster,
          status: 'resolved_manual',
        },
      })
      let pendingFilterLoads = 0
      mockListPoolMasterDataDedupeReviewItems.mockImplementation(async (params?: Record<string, unknown>) => {
        if (params?.status === 'pending_review') {
          pendingFilterLoads += 1
          return pendingFilterLoads > 1
            ? {
                items: [],
                count: 0,
                meta: { limit: 50, offset: 0, total: 0 },
              }
            : {
                items: [pendingReview],
                count: 1,
                meta: { limit: 50, offset: 0, total: 1 },
              }
        }
        return {
          items: [pendingReview],
          count: 1,
          meta: { limit: 50, offset: 0, total: 1 },
        }
      })
      mockGetPoolMasterDataDedupeReviewItem.mockResolvedValueOnce({ review_item: pendingReview }).mockResolvedValue({ review_item: resolvedReview })
      mockApplyPoolMasterDataDedupeReviewAction.mockResolvedValue({
        review_item: resolvedReview,
      })

      renderPage('/pools/master-data?tab=dedupe-review&reviewItemId=review-1')

      expect(await screen.findByText('Review Queue')).toBeInTheDocument()
      openSelectByTestId('dedupe-review-status-filter')
      await selectDropdownOption('pending_review')
      await waitFor(() =>
        expect(mockListPoolMasterDataDedupeReviewItems).toHaveBeenLastCalledWith({
          database_id: undefined,
          entity_type: undefined,
          status: 'pending_review',
          reason_code: undefined,
          cluster_id: 'cluster-review-1',
          limit: 50,
          offset: 0,
        }),
      )

      await user.click(screen.getByLabelText('Use Ref_B as survivor'))
      await user.click(screen.getByRole('button', { name: 'Choose Survivor' }))

      expect((await screen.findAllByText('resolved_manual')).length).toBeGreaterThan(0)
      expect(screen.queryByText('No dedupe review item selected.')).not.toBeInTheDocument()
      expect(mockGetPoolMasterDataDedupeReviewItem).toHaveBeenLastCalledWith('review-1')
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'renders dedupe blockers and affected bindings in review detail',
    async () => {
      const pendingReview = buildDedupeReviewItem()
      mockListPoolMasterDataDedupeReviewItems.mockResolvedValue({
        items: [pendingReview],
        count: 1,
        meta: { limit: 50, offset: 0, total: 1 },
      })
      mockGetPoolMasterDataDedupeReviewItem.mockResolvedValue({
        review_item: pendingReview,
      })

      renderPage('/pools/master-data?tab=dedupe-review&reviewItemId=review-1')

      expect(await screen.findByText('Review Detail')).toBeInTheDocument()
      expect(await screen.findByText('Affected Bindings')).toBeInTheDocument()
      expect(screen.getAllByText('Main DB').length).toBeGreaterThan(0)
      expect(screen.getByText('ref-party-001')).toBeInTheDocument()
      expect(screen.getByText('Runtime Blockers')).toBeInTheDocument()
      expect(screen.getByText('Publication')).toBeInTheDocument()
      expect(screen.getByText('Manual Sync Launch')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'blocks Party save when no role is selected',
    async () => {
      const user = userEvent.setup()
      renderPage()

      expect(await screen.findByText('Party One')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Add Party' }))
      await user.type(screen.getByLabelText('Canonical ID'), 'party-002')
      await user.type(screen.getByLabelText('Name'), 'Party Two')
      await user.click(screen.getByRole('checkbox', { name: 'Role: counterparty' }))
      await user.click(screen.getByRole('button', { name: 'OK' }))

      expect(await screen.findByText('Party must have at least one role: organization or counterparty.')).toBeInTheDocument()
      expect(mockUpsertMasterDataParty).not.toHaveBeenCalled()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'shows chart_identity in GLAccount binding scope and submits chart-scoped payload',
    async () => {
      const user = userEvent.setup()
      mockListMasterDataBindings.mockResolvedValueOnce({
        bindings: [
          {
            id: 'binding-gl-account-1',
            tenant_id: 'tenant-1',
            entity_type: 'gl_account',
            canonical_id: 'gl-account-001',
            database_id: 'db-1',
            ib_ref_key: 'ref-gl-1',
            chart_identity: 'ChartOfAccounts_Main',
            sync_status: 'resolved',
            fingerprint: 'fp-1',
            metadata: {},
            last_synced_at: '2026-01-01T00:00:00Z',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        meta: { limit: 200, offset: 0, total: 1 },
      })
      mockUpsertMasterDataBinding.mockResolvedValue({
        binding: {},
        created: false,
      })

      renderPage('/pools/master-data?tab=bindings')

      expect(await screen.findByText('Chart Identity: ChartOfAccounts_Main')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Edit' }))

      const chartIdentityField = await screen.findByLabelText('Chart Identity')
      await user.clear(chartIdentityField)
      await user.type(chartIdentityField, 'ChartOfAccounts_Secondary')
      await user.click(screen.getByRole('button', { name: 'OK' }))

      await waitFor(() =>
        expect(mockUpsertMasterDataBinding).toHaveBeenCalledWith({
          binding_id: 'binding-gl-account-1',
          entity_type: 'gl_account',
          canonical_id: 'gl-account-001',
          database_id: 'db-1',
          ib_ref_key: 'ref-gl-1',
          ib_catalog_kind: '',
          owner_counterparty_canonical_id: '',
          chart_identity: 'ChartOfAccounts_Secondary',
          sync_status: 'resolved',
          fingerprint: 'fp-1',
        }),
      )
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )
}

export function registerPoolMasterDataSyncTests() {
  it(
    'stages Sync secondary reads after primary workspace hydration',
    async () => {
      const clustersRequest = deferred<Array<{ id: string; name: string }>>()
      const databasesRequest = deferred<
        Array<{
          id: string
          name: string
          cluster_id: string | null
          cluster_all_eligibility_state: 'eligible' | 'excluded' | 'unconfigured'
        }>
      >()
      const launchesRequest = deferred<{
        launches: Array<Record<string, unknown>>
        count: number
        limit: number
        offset: number
      }>()
      const statusRequest = deferred<{
        statuses: Array<Record<string, unknown>>
        count: number
      }>()
      const conflictsRequest = deferred<{
        conflicts: Array<Record<string, unknown>>
        count: number
      }>()

      mockListPoolTargetClusters.mockImplementation(() => clustersRequest.promise)
      mockListPoolTargetDatabases.mockImplementation(() => databasesRequest.promise)
      mockListPoolMasterDataSyncLaunches.mockImplementation(() => launchesRequest.promise)
      mockListMasterDataSyncStatus.mockImplementation(() => statusRequest.promise)
      mockListMasterDataSyncConflicts.mockImplementation(() => conflictsRequest.promise)

      renderPage('/pools/master-data?tab=sync')

      await waitFor(() => expect(mockListPoolTargetClusters).toHaveBeenCalled())
      expect(mockListPoolMasterDataSyncLaunches).toHaveBeenCalled()
      expect(mockListMasterDataSyncStatus).not.toHaveBeenCalled()
      expect(mockListMasterDataSyncConflicts).not.toHaveBeenCalled()

      clustersRequest.resolve([{ id: 'cluster-1', name: 'Main Cluster' }])
      databasesRequest.resolve([
        {
          id: 'db-1',
          name: 'Main DB',
          cluster_id: 'cluster-1',
          cluster_all_eligibility_state: 'eligible',
        },
      ])
      launchesRequest.resolve({
        launches: [],
        count: 0,
        limit: 20,
        offset: 0,
      })

      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
      expect(mockListMasterDataSyncConflicts).not.toHaveBeenCalled()

      statusRequest.resolve({
        statuses: [],
        count: 0,
      })
      await statusRequest.promise
      await Promise.resolve()

      await waitFor(() => expect(mockListMasterDataSyncConflicts).toHaveBeenCalled())
      conflictsRequest.resolve({
        conflicts: [],
        count: 0,
      })

      expect(await screen.findByText('Sync Status')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'ignores late launch_autoselect after leaving the Sync zone',
    async () => {
      const launchesRequest = deferred<{
        launches: Array<Record<string, unknown>>
        count: number
        limit: number
        offset: number
      }>()

      mockListPoolMasterDataSyncLaunches.mockImplementation(() => launchesRequest.promise)

      renderPage('/pools/master-data?tab=sync&detail=1')

      expect(await screen.findByText('Sync Status')).toBeInTheDocument()
      await waitFor(() => expect(mockListPoolMasterDataSyncLaunches).toHaveBeenCalled())

      fireEvent.click(screen.getByRole('button', { name: 'Open Bindings zone' }))

      await waitFor(() => expect(mockListMasterDataBindings).toHaveBeenCalled())
      await waitFor(() => expect(screen.getByTestId('pool-master-data-route-location')).toHaveTextContent('/pools/master-data?tab=bindings&detail=1'))
      expect(screen.getByTestId('pool-master-data-route-location')).not.toHaveTextContent('launchId=')

      launchesRequest.resolve({
        launches: [buildSyncLaunch({ id: 'launch-late-1' })],
        count: 1,
        limit: 20,
        offset: 0,
      })
      await launchesRequest.promise
      await Promise.resolve()
      await Promise.resolve()

      expect(screen.getByTestId('pool-master-data-route-location')).toHaveTextContent('/pools/master-data?tab=bindings&detail=1')
      expect(screen.getByTestId('pool-master-data-route-location')).not.toHaveTextContent('launchId=')
      expect(mockGetPoolMasterDataSyncLaunch).not.toHaveBeenCalled()

      const bundle = exportUiActionJournalBundle()
      expect(bundle.events.some((event) => (
        event.event_type === 'route.transition'
          && event.write_reason === 'launch_autoselect'
      ))).toBe(false)
      expect(bundle.events.some((event) => event.event_type === 'route.loop_warning')).toBe(false)
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'shows class-aware 429 diagnostics for Sync load without replacing the workspace shell',
    async () => {
      mockListMasterDataSyncStatus.mockRejectedValue({
        response: {
          status: 429,
          data: {
            error: 'Rate limit exceeded',
            code: 'RATE_LIMIT_EXCEEDED',
            rate_limit_class: 'background_heavy',
            retry_after_seconds: 17,
            budget_scope: 'tenant=tenant-1;principal=user:1;class=background_heavy',
            request_id: 'req-sync-429',
          },
        },
      })

      renderPage('/pools/master-data?tab=sync')

      const alert = await screen.findByTestId('sync-rate-limit-alert')
      expect(alert).toHaveTextContent('Gateway rate-limited sync status/conflicts under a separate request budget.')
      expect(alert).toHaveTextContent('Retry in about 17s.')
      expect(alert).toHaveTextContent('Budget class: background_heavy.')
      expect(alert).toHaveTextContent('Budget scope: tenant=tenant-1;principal=user:1;class=background_heavy.')
      expect(alert).toHaveTextContent('Request ID: req-sync-429.')
      expect(screen.getByText('Sync Status')).toBeInTheDocument()
      expect(mockListMasterDataSyncConflicts).not.toHaveBeenCalled()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'renders Sync tab and runs conflict actions',
    async () => {
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
        }),
      )

      await user.click(screen.getByRole('button', { name: 'Reconcile' }))
      await waitFor(() =>
        expect(mockReconcileMasterDataSyncConflict).toHaveBeenCalledWith('conflict-1', {
          note: 'Manual reconcile from Pool Master Data Sync UI',
          reconcile_payload: { strategy: 'manual_reconcile' },
        }),
      )

      await user.click(screen.getByRole('button', { name: 'Resolve' }))
      await waitFor(() =>
        expect(mockResolveMasterDataSyncConflict).toHaveBeenCalledWith('conflict-1', {
          resolution_code: 'MANUAL_RECONCILE',
          note: 'Manual resolve from Pool Master Data Sync UI',
          metadata: { source: 'ui' },
        }),
      )
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'creates manual sync launch from the Sync tab and shows launch detail',
    async () => {
      const user = userEvent.setup()
      const createdLaunch = buildSyncLaunch({
        id: 'launch-created-1',
        mode: 'outbound',
        target_mode: 'cluster_all',
        cluster_id: 'cluster-1',
        database_ids: ['db-1', 'db-2'],
        entity_scope: ['party'],
        status: 'running',
        aggregate_counters: {
          total_items: 2,
          scheduled: 2,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 0,
        },
        progress: {
          total_items: 2,
          scheduled: 2,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 0,
          terminal_items: 0,
          completion_ratio: 0,
        },
        items: [
          {
            id: 'launch-item-created-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            entity_type: 'party',
            status: 'scheduled',
            reason_code: '',
            reason_detail: '',
            child_job_id: 'job-sync-created-1',
            child_job_status: 'queued',
            child_workflow_execution_id: 'wf-child-created-1',
            child_operation_id: 'op-child-created-1',
            metadata: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
      })
      mockListPoolMasterDataSyncLaunches
        .mockResolvedValueOnce({
          launches: [],
          count: 0,
          limit: 20,
          offset: 0,
        })
        .mockResolvedValueOnce({
          launches: [createdLaunch],
          count: 1,
          limit: 20,
          offset: 0,
        })
      mockCreatePoolMasterDataSyncLaunch.mockResolvedValue({
        launch: createdLaunch,
      })
      mockGetPoolMasterDataSyncLaunch.mockResolvedValue({
        launch: createdLaunch,
      })

      renderPage('/pools/master-data?tab=sync')

      expect(await screen.findByTestId('sync-launch-open-drawer')).toBeInTheDocument()
      await user.click(screen.getByTestId('sync-launch-open-drawer'))

      openSelectByTestId('sync-launch-mode')
      await selectDropdownOption(/^Outbound$/)
      openSelectByTestId('sync-launch-target-mode')
      await selectDropdownOption(/^Cluster All$/)
      openSelectByTestId('sync-launch-cluster')
      await selectDropdownOption(/^Main Cluster$/)

      openSelectByTestId('sync-launch-entity-scope')
      const launchScopeDropdown = getOpenSelectDropdown()
      expect(within(launchScopeDropdown).getByText('Party')).toBeInTheDocument()
      expect(within(launchScopeDropdown).getByText('Item')).toBeInTheDocument()
      expect(within(launchScopeDropdown).queryByText('GL Account')).not.toBeInTheDocument()
      expect(within(launchScopeDropdown).queryByText('GL Account Set')).not.toBeInTheDocument()
      fireEvent.click(document.body)

      await user.click(screen.getByTestId('sync-launch-submit'))

      await waitFor(() =>
        expect(mockCreatePoolMasterDataSyncLaunch).toHaveBeenCalledWith({
          mode: 'outbound',
          target_mode: 'cluster_all',
          cluster_id: 'cluster-1',
          database_ids: undefined,
          entity_scope: ['party', 'item'],
        }),
      )
      expect(await screen.findByText('Launch Detail')).toBeInTheDocument()
      expect(await screen.findByText('launch-created-1')).toBeInTheDocument()
      expect(await screen.findByText('job-sync-created-1')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'keeps manual sync launch form values after validation error',
    async () => {
      const user = userEvent.setup()
      renderPage('/pools/master-data?tab=sync')

      expect(await screen.findByTestId('sync-launch-open-drawer')).toBeInTheDocument()
      await user.click(screen.getByTestId('sync-launch-open-drawer'))

      openSelectByTestId('sync-launch-mode')
      await selectDropdownOption(/^Reconcile$/)
      openSelectByTestId('sync-launch-target-mode')
      await selectDropdownOption(/^Cluster All$/)

      await user.click(screen.getByTestId('sync-launch-submit'))

      await waitFor(() => expect(screen.getByText('Select cluster.')).toBeInTheDocument())
      const drawer = screen.getByTestId('sync-launch-drawer')
      expect(drawer).toBeInTheDocument()
      expect(screen.getByTestId('sync-launch-cluster')).toBeInTheDocument()
      expect(screen.getByTestId('sync-launch-mode')).toHaveTextContent('Reconcile')
      expect(mockCreatePoolMasterDataSyncLaunch).not.toHaveBeenCalled()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'keeps manual sync launch scope after server-side create error',
    async () => {
      const user = userEvent.setup()
      mockCreatePoolMasterDataSyncLaunch.mockRejectedValue({
        response: {
          data: {
            code: 'SYNC_LAUNCH_DATABASE_NOT_FOUND',
            title: 'Sync Launch Invalid',
            detail: 'Selected databases are no longer available.',
            errors: {
              database_ids: ['Refresh the selected databases.'],
            },
          },
        },
      })

      renderPage('/pools/master-data?tab=sync')

      expect(await screen.findByTestId('sync-launch-open-drawer')).toBeInTheDocument()
      await user.click(screen.getByTestId('sync-launch-open-drawer'))

      openSelectByTestId('sync-launch-mode')
      await selectDropdownOption(/^Outbound$/)
      openSelectByTestId('sync-launch-database-set')
      await selectDropdownOption(/Main DB/)

      await user.click(screen.getByTestId('sync-launch-submit'))

      await waitFor(() =>
        expect(mockCreatePoolMasterDataSyncLaunch).toHaveBeenCalledWith({
          mode: 'outbound',
          target_mode: 'database_set',
          cluster_id: undefined,
          database_ids: ['db-1'],
          entity_scope: ['party', 'item'],
        }),
      )
      expect(await screen.findByText('Selected databases are no longer available.')).toBeInTheDocument()
      expect(await screen.findByText('Refresh the selected databases.')).toBeInTheDocument()
      expect(screen.getByTestId('sync-launch-drawer')).toBeInTheDocument()
      expect(screen.getByTestId('sync-launch-mode')).toHaveTextContent('Outbound')
      expect(screen.getByTestId('sync-launch-database-set')).toHaveTextContent('Main DB')
      expect(screen.getByTestId('sync-launch-entity-scope')).toHaveTextContent('Party')
      expect(screen.getByTestId('sync-launch-entity-scope')).toHaveTextContent('Item')
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'blocks cluster_all launch when eligibility is unconfigured and offers handoff to /databases',
    async () => {
      const user = userEvent.setup()
      mockListPoolTargetDatabases.mockResolvedValue([
        {
          id: 'db-1',
          name: 'Main DB',
          cluster_id: 'cluster-1',
          cluster_all_eligibility_state: 'eligible',
        },
        {
          id: 'db-2',
          name: 'Replica DB',
          cluster_id: 'cluster-1',
          cluster_all_eligibility_state: 'unconfigured',
        },
        {
          id: 'db-3',
          name: 'Archive DB',
          cluster_id: 'cluster-1',
          cluster_all_eligibility_state: 'excluded',
        },
      ])

      renderPage('/pools/master-data?tab=sync')

      expect(await screen.findByTestId('sync-launch-open-drawer')).toBeInTheDocument()
      await user.click(screen.getByTestId('sync-launch-open-drawer'))

      openSelectByTestId('sync-launch-target-mode')
      await selectDropdownOption(/^Cluster All$/)
      openSelectByTestId('sync-launch-cluster')
      await selectDropdownOption(/^Main Cluster$/)

      expect(await screen.findByTestId('sync-launch-cluster-all-summary')).toBeInTheDocument()
      expect(screen.getByText('Cluster summary: 1 eligible, 1 excluded, 1 unconfigured.')).toBeInTheDocument()
      expect(screen.getByText('Excluded from cluster_all: Archive DB.')).toBeInTheDocument()
      expect(screen.getByText('Resolve eligibility in /databases before launch for: Replica DB.')).toBeInTheDocument()
      expect(screen.getByText('Use Database Set for one-off launches that must include excluded databases.')).toBeInTheDocument()
      expect(screen.getByTestId('sync-launch-submit')).toBeDisabled()

      await user.click(screen.getByTestId('sync-launch-open-eligibility-handoff'))

      expect(mockNavigate).toHaveBeenCalledWith('/databases?cluster=cluster-1&context=metadata&database=db-2')
      expect(mockCreatePoolMasterDataSyncLaunch).not.toHaveBeenCalled()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'filters sync launch entity scope by mode capabilities',
    async () => {
      const user = userEvent.setup()
      renderPage('/pools/master-data?tab=sync')

      expect(await screen.findByTestId('sync-launch-open-drawer')).toBeInTheDocument()
      await user.click(screen.getByTestId('sync-launch-open-drawer'))

      openSelectByTestId('sync-launch-mode')
      await selectDropdownOption(/^Outbound$/)
      openSelectByTestId('sync-launch-entity-scope')
      const outboundDropdown = getOpenSelectDropdown()
      expect(within(outboundDropdown).getByText('Party')).toBeInTheDocument()
      expect(within(outboundDropdown).getByText('Item')).toBeInTheDocument()
      expect(within(outboundDropdown).getByText('Contract')).toBeInTheDocument()
      expect(within(outboundDropdown).getByText('Tax Profile')).toBeInTheDocument()
      expect(within(outboundDropdown).queryByText('GL Account')).not.toBeInTheDocument()
      expect(within(outboundDropdown).queryByText('GL Account Set')).not.toBeInTheDocument()
      fireEvent.click(document.body)

      openSelectByTestId('sync-launch-mode')
      await selectDropdownOption(/^Inbound$/)
      openSelectByTestId('sync-launch-entity-scope')
      const inboundDropdown = getOpenSelectDropdown()
      expect(within(inboundDropdown).getByText('Party')).toBeInTheDocument()
      expect(within(inboundDropdown).getByText('Item')).toBeInTheDocument()
      expect(within(inboundDropdown).getByText('Contract')).toBeInTheDocument()
      expect(within(inboundDropdown).getByText('Tax Profile')).toBeInTheDocument()
      expect(within(inboundDropdown).queryByText('GL Account')).not.toBeInTheDocument()
      expect(within(inboundDropdown).queryByText('GL Account Set')).not.toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'shows cluster_all resolution detail for excluded databases',
    async () => {
      const launchWithResolution = buildSyncLaunch({
        id: 'launch-resolution-1',
        target_mode: 'cluster_all',
        cluster_id: 'cluster-1',
        database_ids: ['db-1'],
        target_resolution: {
          eligible_count: 1,
          excluded_count: 1,
          unconfigured_count: 0,
          eligible_database_ids: ['db-1'],
          excluded_databases: [
            {
              database_id: 'db-2',
              database_name: 'Replica DB',
              cluster_id: 'cluster-1',
              cluster_all_eligibility_state: 'excluded',
            },
          ],
          unconfigured_databases: [],
        },
      })
      mockListPoolMasterDataSyncLaunches.mockResolvedValue({
        launches: [launchWithResolution],
        count: 1,
        limit: 20,
        offset: 0,
      })
      mockGetPoolMasterDataSyncLaunch.mockResolvedValue({
        launch: launchWithResolution,
      })

      renderPage('/pools/master-data?tab=sync&launchId=launch-resolution-1')

      expect(await screen.findByText('Launch Detail')).toBeInTheDocument()
      expect(await screen.findByText('Cluster resolution: 1 eligible, 1 excluded, 0 unconfigured.')).toBeInTheDocument()
      expect(screen.getByText('Excluded from snapshot: Replica DB.')).toBeInTheDocument()
      expect(screen.getByText('Use Database Set for one-off launches that must include excluded databases.')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'hides retry and reconcile actions when registry disables the required sync direction',
    async () => {
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
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'applies scheduling filters for sync status operator view',
    async () => {
      const user = userEvent.setup()
      renderPage('/pools/master-data?tab=sync')

      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
      mockListMasterDataSyncStatus.mockClear()

      openSelectByTestId('sync-status-filter-priority')
      await selectDropdownOption(/^p1$/)
      openSelectByTestId('sync-status-filter-role')
      await selectDropdownOption(/^reconcile$/)
      await user.type(screen.getByTestId('sync-status-filter-server-affinity'), 'srv:main')
      openSelectByTestId('sync-status-filter-deadline-state')
      await selectDropdownOption(/^missed$/)

      fireEvent.click(screen.getByTestId('sync-status-refresh'))

      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
      expect(mockListMasterDataSyncStatus).toHaveBeenLastCalledWith({
        database_id: undefined,
        entity_type: undefined,
        priority: 'p1',
        role: 'reconcile',
        server_affinity: 'srv:main',
        deadline_state: 'missed',
      })
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'publishes immutable GL Account Set revision from the reusable profile surface',
    async () => {
      const user = userEvent.setup()
      mockPublishMasterDataGlAccountSet.mockResolvedValue({
        gl_account_set: {
          gl_account_set_id: 'gl-set-1',
          canonical_id: 'gl-set-001',
          name: 'Quarter Scope',
          description: 'Draft for Q1',
          chart_identity: 'ChartOfAccounts_Main',
          config_name: 'Accounting Enterprise',
          config_version: '3.0.1',
          draft_members_count: 1,
          published_revision_number: 2,
          published_revision_id: 'gl-set-rev-2',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-02T00:00:00Z',
          draft_members: [
            {
              gl_account_id: 'gl-account-1',
              canonical_id: 'gl-account-001',
              code: '10.01',
              name: 'Main Account',
              chart_identity: 'ChartOfAccounts_Main',
              config_name: 'Accounting Enterprise',
              config_version: '3.0.1',
              sort_order: 0,
              metadata: {},
            },
          ],
          revisions: [
            {
              gl_account_set_revision_id: 'gl-set-rev-1',
              gl_account_set_id: 'gl-set-1',
              contract_version: 'pool_master_gl_account_set.v1',
              revision_number: 1,
              name: 'Quarter Scope',
              description: 'Draft for Q1',
              chart_identity: 'ChartOfAccounts_Main',
              config_name: 'Accounting Enterprise',
              config_version: '3.0.1',
              members: [
                {
                  gl_account_id: 'gl-account-1',
                  canonical_id: 'gl-account-001',
                  code: '10.01',
                  name: 'Main Account',
                  chart_identity: 'ChartOfAccounts_Main',
                  config_name: 'Accounting Enterprise',
                  config_version: '3.0.1',
                  sort_order: 0,
                  metadata: {},
                },
              ],
              metadata: {},
              created_by: 'user-1',
              created_at: '2026-01-01T00:00:00Z',
            },
            {
              gl_account_set_revision_id: 'gl-set-rev-2',
              gl_account_set_id: 'gl-set-1',
              contract_version: 'pool_master_gl_account_set.v1',
              revision_number: 2,
              name: 'Quarter Scope',
              description: 'Draft for Q1',
              chart_identity: 'ChartOfAccounts_Main',
              config_name: 'Accounting Enterprise',
              config_version: '3.0.1',
              members: [
                {
                  gl_account_id: 'gl-account-1',
                  canonical_id: 'gl-account-001',
                  code: '10.01',
                  name: 'Main Account',
                  chart_identity: 'ChartOfAccounts_Main',
                  config_name: 'Accounting Enterprise',
                  config_version: '3.0.1',
                  sort_order: 0,
                  metadata: {},
                },
              ],
              metadata: {},
              created_by: 'user-1',
              created_at: '2026-01-02T00:00:00Z',
            },
          ],
          published_revision: {
            gl_account_set_revision_id: 'gl-set-rev-2',
            gl_account_set_id: 'gl-set-1',
            contract_version: 'pool_master_gl_account_set.v1',
            revision_number: 2,
            name: 'Quarter Scope',
            description: 'Draft for Q1',
            chart_identity: 'ChartOfAccounts_Main',
            config_name: 'Accounting Enterprise',
            config_version: '3.0.1',
            members: [
              {
                gl_account_id: 'gl-account-1',
                canonical_id: 'gl-account-001',
                code: '10.01',
                name: 'Main Account',
                chart_identity: 'ChartOfAccounts_Main',
                config_name: 'Accounting Enterprise',
                config_version: '3.0.1',
                sort_order: 0,
                metadata: {},
              },
            ],
            metadata: {},
            created_by: 'user-1',
            created_at: '2026-01-02T00:00:00Z',
          },
        },
      })

      renderPage('/pools/master-data?tab=gl-account-set')

      expect(await screen.findByText('Quarter Scope')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Publish revision' }))

      await waitFor(() => expect(mockPublishMasterDataGlAccountSet).toHaveBeenCalledWith('gl-set-1'))
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )
}

export function registerPoolMasterDataBootstrapTests() {
  it(
    'runs bootstrap wizard flow preflight -> dry-run -> execute',
    async () => {
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
      mockCreatePoolMasterDataBootstrapImportJob.mockResolvedValueOnce({ job: dryRunJob }).mockResolvedValueOnce({ job: executeJob })
      mockGetPoolMasterDataBootstrapImportJob.mockResolvedValueOnce({ job: dryRunJob }).mockResolvedValueOnce({ job: executeJob })
      mockListPoolMasterDataBootstrapImportJobs.mockResolvedValue({
        count: 2,
        limit: 20,
        offset: 0,
        jobs: [executeJob, dryRunJob],
      })

      renderPage('/pools/master-data?tab=bootstrap-import')
      await screen.findByTestId('bootstrap-import-database-select')

      openSelectByTestId('bootstrap-import-database-select')
      await selectDropdownOption(/^Main DB$/)

      fireEvent.click(screen.getByTestId('bootstrap-import-run-preflight'))
      await waitFor(() =>
        expect(mockRunPoolMasterDataBootstrapImportPreflight).toHaveBeenCalledWith({
          database_id: 'db-1',
          entity_scope: ['party', 'item'],
        }),
      )

      fireEvent.click(screen.getByTestId('bootstrap-import-run-dry-run'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataBootstrapImportJob).toHaveBeenNthCalledWith(1, {
          database_id: 'db-1',
          entity_scope: ['party', 'item'],
          mode: 'dry_run',
        }),
      )

      fireEvent.click(screen.getByTestId('bootstrap-import-run-execute'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataBootstrapImportJob).toHaveBeenNthCalledWith(2, {
          database_id: 'db-1',
          entity_scope: ['party', 'item'],
          mode: 'execute',
        }),
      )

      expect(await screen.findByText('Current Job')).toBeInTheDocument()
      expect(await screen.findByText('Rows (dry-run)')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'keeps bootstrap form values after preflight error',
    async () => {
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

      renderPage('/pools/master-data?tab=bootstrap-import')
      await screen.findByTestId('bootstrap-import-database-select')

      openSelectByTestId('bootstrap-import-database-select')
      await selectDropdownOption(/^Main DB$/)

      fireEvent.click(screen.getByTestId('bootstrap-import-run-preflight'))

      expect((await screen.findAllByText('Preflight failed in source adapter.')).length).toBeGreaterThan(0)
      expect(screen.getByTestId('bootstrap-import-database-select')).toHaveTextContent('Main DB')
      expect(screen.getByTestId('bootstrap-import-entity-scope-select')).toHaveTextContent('Party')
      expect(screen.getByTestId('bootstrap-import-entity-scope-select')).toHaveTextContent('Item')
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'runs batch bootstrap collection preflight, dry-run, and execute',
    async () => {
      const preflightCollection = buildBootstrapCollection({
        id: 'collection-batch',
        status: 'preflight_completed',
        mode: 'preflight',
        database_ids: ['db-1', 'db-2'],
        aggregate_dry_run_summary: {},
        aggregate_counters: {
          total_items: 2,
          scheduled: 0,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 2,
        },
        items: [
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
          {
            id: 'collection-item-2',
            database_id: 'db-2',
            database_name: 'Replica DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
        ],
      })
      const dryRunCollection = buildBootstrapCollection({
        id: 'collection-batch',
        status: 'dry_run_completed',
        mode: 'dry_run',
        database_ids: ['db-1', 'db-2'],
        aggregate_counters: {
          total_items: 2,
          scheduled: 0,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 2,
        },
        progress: {
          total_items: 2,
          scheduled: 0,
          coalesced: 0,
          skipped: 0,
          failed: 0,
          completed: 2,
          terminal_items: 2,
          completion_ratio: 1,
        },
        aggregate_dry_run_summary: {
          rows_total: 2,
          chunks_total: 2,
          entities: [],
        },
        items: [
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
          {
            id: 'collection-item-2',
            database_id: 'db-2',
            database_name: 'Replica DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
        ],
      })
      const executeCollection = buildBootstrapCollection({
        id: 'collection-batch',
        status: 'execute_running',
        mode: 'execute',
        database_ids: ['db-1', 'db-2'],
        aggregate_counters: {
          total_items: 2,
          scheduled: 1,
          coalesced: 1,
          skipped: 0,
          failed: 0,
          completed: 0,
        },
        progress: {
          total_items: 2,
          scheduled: 1,
          coalesced: 1,
          skipped: 0,
          failed: 0,
          completed: 0,
          terminal_items: 1,
          completion_ratio: 0.5,
        },
        items: [
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'coalesced',
            reason_code: 'BOOTSTRAP_CHILD_JOB_COALESCED',
            reason_detail: 'Compatible bootstrap import job is already active for this database.',
            child_job_id: 'job-1',
            child_job_status: 'execute_pending',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
          {
            id: 'collection-item-2',
            database_id: 'db-2',
            database_name: 'Replica DB',
            cluster_id: 'cluster-1',
            status: 'scheduled',
            reason_code: '',
            reason_detail: '',
            child_job_id: 'job-2',
            child_job_status: 'execute_pending',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
        ],
      })

      mockRunPoolMasterDataBootstrapCollectionPreflight.mockResolvedValueOnce({
        preflight: {
          ok: true,
          target_mode: 'database_set',
          cluster_id: null,
          database_ids: ['db-1', 'db-2'],
          database_count: 2,
          entity_scope: ['party', 'item'],
          databases: [
            {
              database_id: 'db-1',
              database_name: 'Main DB',
              cluster_id: 'cluster-1',
              ok: true,
              preflight_result: {
                ok: true,
                source_kind: 'ib_odata',
                coverage: {},
                credential_strategy: 'service',
                errors: [],
                diagnostics: {},
              },
            },
            {
              database_id: 'db-2',
              database_name: 'Replica DB',
              cluster_id: 'cluster-1',
              ok: true,
              preflight_result: {
                ok: true,
                source_kind: 'ib_odata',
                coverage: {},
                credential_strategy: 'service',
                errors: [],
                diagnostics: {},
              },
            },
          ],
          errors: [],
          generated_at: '2026-01-01T00:00:00Z',
        },
        collection: preflightCollection,
      })
      mockCreatePoolMasterDataBootstrapCollection.mockResolvedValueOnce({ collection: dryRunCollection }).mockResolvedValueOnce({ collection: executeCollection })
      mockListPoolMasterDataBootstrapCollections
        .mockResolvedValueOnce({
          count: 0,
          limit: 20,
          offset: 0,
          collections: [],
        })
        .mockResolvedValueOnce({
          count: 1,
          limit: 20,
          offset: 0,
          collections: [dryRunCollection],
        })
        .mockResolvedValue({
          count: 1,
          limit: 20,
          offset: 0,
          collections: [executeCollection],
        })
      mockGetPoolMasterDataBootstrapCollection.mockResolvedValueOnce({ collection: dryRunCollection }).mockResolvedValueOnce({ collection: executeCollection })

      renderPage('/pools/master-data?tab=bootstrap-import')
      fireEvent.click(await screen.findByText('Batch Collection'))

      openSelectByTestId('bootstrap-collection-databases-select')
      await selectDropdownOption(/Main DB/)
      openSelectByTestId('bootstrap-collection-databases-select')
      await selectDropdownOption(/Replica DB/)

      fireEvent.click(screen.getByTestId('bootstrap-collection-run-preflight'))
      await waitFor(() =>
        expect(mockRunPoolMasterDataBootstrapCollectionPreflight).toHaveBeenCalledWith({
          target_mode: 'database_set',
          database_ids: ['db-1', 'db-2'],
          entity_scope: ['party', 'item'],
        }),
      )

      fireEvent.click(screen.getByTestId('bootstrap-collection-run-dry-run'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataBootstrapCollection).toHaveBeenNthCalledWith(1, {
          collection_id: 'collection-batch',
          target_mode: 'database_set',
          database_ids: ['db-1', 'db-2'],
          entity_scope: ['party', 'item'],
          mode: 'dry_run',
        }),
      )

      fireEvent.click(screen.getByTestId('bootstrap-collection-run-execute'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataBootstrapCollection).toHaveBeenNthCalledWith(2, {
          collection_id: 'collection-batch',
          target_mode: 'database_set',
          database_ids: ['db-1', 'db-2'],
          entity_scope: ['party', 'item'],
          mode: 'execute',
        }),
      )

      expect(await screen.findByText('Current Collection')).toBeInTheDocument()
      expect(await screen.findByText('Recent Collections')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'blocks batch execute when dry-run collection has failed items',
    async () => {
      const preflightCollection = buildBootstrapCollection({
        id: 'collection-failed',
        status: 'preflight_completed',
        mode: 'preflight',
        database_ids: ['db-1', 'db-2'],
        aggregate_dry_run_summary: {},
        items: [
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
          {
            id: 'collection-item-2',
            database_id: 'db-2',
            database_name: 'Replica DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
        ],
      })
      const failedDryRunCollection = buildBootstrapCollection({
        id: 'collection-failed',
        status: 'failed',
        mode: 'dry_run',
        aggregate_counters: {
          total_items: 2,
          scheduled: 0,
          coalesced: 0,
          skipped: 0,
          failed: 1,
          completed: 1,
        },
        items: [
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
          {
            id: 'collection-item-2',
            database_id: 'db-2',
            database_name: 'Replica DB',
            cluster_id: 'cluster-1',
            status: 'failed',
            reason_code: 'BOOTSTRAP_SOURCE_AUTH_MAPPING_MISSING',
            reason_detail: 'Source auth mapping is missing.',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: false },
            dry_run_summary: {},
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
        ],
      })

      mockRunPoolMasterDataBootstrapCollectionPreflight.mockResolvedValueOnce({
        preflight: {
          ok: true,
          target_mode: 'database_set',
          cluster_id: null,
          database_ids: ['db-1', 'db-2'],
          database_count: 2,
          entity_scope: ['party', 'item'],
          databases: [],
          errors: [],
          generated_at: '2026-01-01T00:00:00Z',
        },
        collection: preflightCollection,
      })
      mockCreatePoolMasterDataBootstrapCollection.mockResolvedValueOnce({
        collection: failedDryRunCollection,
      })
      mockListPoolMasterDataBootstrapCollections.mockResolvedValue({
        count: 1,
        limit: 20,
        offset: 0,
        collections: [failedDryRunCollection],
      })
      mockGetPoolMasterDataBootstrapCollection.mockResolvedValueOnce({
        collection: failedDryRunCollection,
      })

      renderPage('/pools/master-data?tab=bootstrap-import')
      fireEvent.click(await screen.findByText('Batch Collection'))

      openSelectByTestId('bootstrap-collection-databases-select')
      await selectDropdownOption(/Main DB/)
      openSelectByTestId('bootstrap-collection-databases-select')
      await selectDropdownOption(/Replica DB/)

      fireEvent.click(screen.getByTestId('bootstrap-collection-run-preflight'))
      fireEvent.click(screen.getByTestId('bootstrap-collection-run-dry-run'))

      await waitFor(() =>
        expect(mockCreatePoolMasterDataBootstrapCollection).toHaveBeenCalledWith({
          collection_id: 'collection-failed',
          target_mode: 'database_set',
          database_ids: ['db-1', 'db-2'],
          entity_scope: ['party', 'item'],
          mode: 'dry_run',
        }),
      )

      await waitFor(() => expect(screen.getByTestId('bootstrap-collection-run-execute')).toBeDisabled())
      fireEvent.click(screen.getByTestId('bootstrap-collection-run-execute'))
      expect(mockCreatePoolMasterDataBootstrapCollection).toHaveBeenCalledTimes(1)
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'shows batch target mode and immutable target snapshot in collection detail',
    async () => {
      const batchCollection = buildBootstrapCollection({
        id: 'collection-targets',
        target_mode: 'database_set',
        database_ids: ['db-2', 'db-1'],
        items: [
          {
            id: 'collection-item-2',
            database_id: 'db-2',
            database_name: 'Replica DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
          {
            id: 'collection-item-1',
            database_id: 'db-1',
            database_name: 'Main DB',
            cluster_id: 'cluster-1',
            status: 'completed',
            reason_code: '',
            reason_detail: '',
            child_job_id: null,
            child_job_status: '',
            preflight_result: { ok: true },
            dry_run_summary: { rows_total: 1, chunks_total: 1 },
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:02:00Z',
          },
        ],
      })

      mockListPoolMasterDataBootstrapCollections.mockResolvedValue({
        count: 1,
        limit: 20,
        offset: 0,
        collections: [batchCollection],
      })
      mockGetPoolMasterDataBootstrapCollection.mockResolvedValue({
        collection: batchCollection,
      })

      renderPage('/pools/master-data?tab=bootstrap-import')
      fireEvent.click(await screen.findByText('Batch Collection'))

      const currentCollectionCard = (await screen.findByText('Current Collection')).closest('.ant-card')
      expect(currentCollectionCard).not.toBeNull()
      const detail = within(currentCollectionCard as HTMLElement)

      expect(await detail.findByText('Target Mode')).toBeInTheDocument()
      expect(detail.getByText('Selected databases')).toBeInTheDocument()
      expect(detail.getByText('Replica DB · Main Cluster, Main DB · Main Cluster')).toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'keeps batch bootstrap form values after preflight error',
    async () => {
      mockRunPoolMasterDataBootstrapCollectionPreflight.mockRejectedValueOnce({
        response: {
          data: {
            title: 'Validation Error',
            detail: 'Aggregate preflight failed.',
            errors: {
              database_ids: ['Choose databases'],
            },
          },
        },
      })

      renderPage('/pools/master-data?tab=bootstrap-import')
      fireEvent.click(await screen.findByText('Batch Collection'))

      openSelectByTestId('bootstrap-collection-databases-select')
      await selectDropdownOption(/Main DB/)
      openSelectByTestId('bootstrap-collection-databases-select')
      await selectDropdownOption(/Replica DB/)

      fireEvent.click(screen.getByTestId('bootstrap-collection-run-preflight'))

      expect((await screen.findAllByText('Aggregate preflight failed.')).length).toBeGreaterThan(0)
      expect(screen.getByTestId('bootstrap-collection-databases-select')).toHaveTextContent('Main DB')
      expect(screen.getByTestId('bootstrap-collection-databases-select')).toHaveTextContent('Replica DB')
      expect(screen.getByTestId('bootstrap-collection-entity-scope-select')).toHaveTextContent('Party')
      expect(screen.getByTestId('bootstrap-collection-entity-scope-select')).toHaveTextContent('Item')
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'allows GL Account in bootstrap scope without adding it to generic sync actions',
    async () => {
      renderPage('/pools/master-data?tab=bootstrap-import')
      await waitFor(() => expect(screen.getByTestId('bootstrap-import-entity-scope-select')).toHaveTextContent('Party'))

      openSelectByTestId('bootstrap-import-entity-scope-select')
      await selectDropdownOption(/^GL Account$/)
      expect(screen.getByTestId('bootstrap-import-entity-scope-select')).toHaveTextContent('GL Account')

      openSelectByTestId('bootstrap-import-database-select')
      await selectDropdownOption(/^Main DB$/)
      fireEvent.click(screen.getByTestId('bootstrap-import-run-preflight'))

      await waitFor(() =>
        expect(mockRunPoolMasterDataBootstrapImportPreflight).toHaveBeenCalledWith({
          database_id: 'db-1',
          entity_scope: ['party', 'item', 'gl_account'],
        }),
      )

      fireEvent.click(screen.getByRole('button', { name: 'Open Sync zone' }))
      await waitFor(() => expect(mockListMasterDataSyncStatus).toHaveBeenCalled())
      expect(screen.queryByText('gl_account')).not.toBeInTheDocument()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )

  it(
    'runs retry failed chunks action for bootstrap job',
    async () => {
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

      renderPage('/pools/master-data?tab=bootstrap-import')
      expect(await screen.findByText('Current Job')).toBeInTheDocument()

      fireEvent.click(screen.getByTestId('bootstrap-import-retry-failed'))
      await waitFor(() => expect(mockRetryFailedPoolMasterDataBootstrapImportChunks).toHaveBeenCalledWith('job-failed'))
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )
}

export function registerPoolMasterDataChartImportTests() {
  it(
    'keeps Chart Import separate and runs source -> preflight -> dry-run -> materialize -> verify -> backfill',
    async () => {
      const source = buildChartSource()
      const createdJobs: Array<Record<string, unknown>> = []

      mockListPoolMasterDataChartSources.mockImplementation(async () => ({
        count: 1,
        limit: 20,
        offset: 0,
        sources: [source],
      }))
      mockUpsertPoolMasterDataChartSource.mockImplementation(async (payload: Record<string, unknown>) => {
        source.database_id = String(payload.database_id)
        source.chart_identity = String(payload.chart_identity)
        return { source }
      })
      mockCreatePoolMasterDataChartJob.mockImplementation(async (payload: Record<string, unknown>) => {
        const mode = String(payload.mode)
        const snapshot =
          mode === 'materialize' || mode === 'verify_followers' || mode === 'backfill_bindings'
            ? buildChartSnapshot({
                id: `snapshot-${mode}`,
                chart_source_id: source.id,
              })
            : null
        const followerStatuses =
          mode === 'backfill_bindings'
            ? [
                {
                  id: 'follower-1',
                  tenant_id: 'tenant-1',
                  job_id: `job-${mode}`,
                  snapshot_id: snapshot?.id ?? null,
                  database_id: 'db-2',
                  database_name: 'Replica DB',
                  cluster_id: 'cluster-1',
                  verdict: 'stale',
                  detail: 'Binding points to stale Ref_Key.',
                  matched_accounts: 1,
                  missing_accounts: 0,
                  ambiguous_accounts: 0,
                  stale_bindings: 1,
                  backfilled_accounts: 0,
                  diagnostics: {},
                  bindings_remediation_href: '/pools/master-data?tab=bindings&entityType=gl_account&databaseId=db-2&canonicalId=gl-account-001',
                  last_verified_at: '2026-01-01T00:03:00Z',
                  created_at: '2026-01-01T00:03:00Z',
                  updated_at: '2026-01-01T00:03:00Z',
                },
              ]
            : mode === 'verify_followers'
              ? [
                  {
                    id: 'follower-verify-1',
                    tenant_id: 'tenant-1',
                    job_id: `job-${mode}`,
                    snapshot_id: snapshot?.id ?? null,
                    database_id: 'db-2',
                    database_name: 'Replica DB',
                    cluster_id: 'cluster-1',
                    verdict: 'missing',
                    detail: 'Follower coverage is incomplete.',
                    matched_accounts: 1,
                    missing_accounts: 1,
                    ambiguous_accounts: 0,
                    stale_bindings: 0,
                    backfilled_accounts: 0,
                    diagnostics: {},
                    bindings_remediation_href: '/pools/master-data?tab=bindings&entityType=gl_account&databaseId=db-2&canonicalId=gl-account-001',
                    last_verified_at: '2026-01-01T00:02:00Z',
                    created_at: '2026-01-01T00:02:00Z',
                    updated_at: '2026-01-01T00:02:00Z',
                  },
                ]
              : []

        const job = buildChartJob({
          id: `job-${mode}`,
          chart_source_id: source.id,
          chart_source: source,
          snapshot,
          mode,
          database_ids: Array.isArray(payload.database_ids) ? payload.database_ids : [],
          counters:
            mode === 'backfill_bindings'
              ? {
                  database_count: 1,
                  backfilled_count: 0,
                  stale_count: 1,
                  ambiguous_count: 0,
                  missing_count: 0,
                }
              : mode === 'verify_followers'
                ? {
                    database_count: 1,
                    ok_count: 0,
                    missing_count: 1,
                    ambiguous_count: 0,
                    stale_count: 0,
                    backfilled_count: 0,
                  }
                : mode === 'materialize'
                  ? {
                      rows_total: 2,
                      created_count: 1,
                      updated_count: 1,
                      unchanged_count: 0,
                      retired_count: 0,
                    }
                  : { source_ok: true },
          follower_statuses: followerStatuses,
        })
        createdJobs.unshift(job)
        source.latest_job = {
          id: String(job.id),
          tenant_id: String(job.tenant_id),
          chart_source_id: String(job.chart_source_id),
          snapshot: job.snapshot ?? null,
          mode,
          status: 'succeeded',
          database_ids: Array.isArray(job.database_ids) ? job.database_ids : [],
          requested_by_username: 'admin',
          last_error_code: '',
          last_error: '',
          counters: typeof job.counters === 'object' && job.counters ? job.counters : {},
          diagnostics: {},
          audit_trail: [],
          started_at: '2026-01-01T00:00:00Z',
          finished_at: '2026-01-01T00:01:00Z',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:01:00Z',
        }
        if (snapshot) {
          source.latest_snapshot = snapshot
        }
        return { job }
      })
      mockListPoolMasterDataChartJobs.mockImplementation(async () => ({
        count: createdJobs.length,
        limit: 20,
        offset: 0,
        jobs: [...createdJobs],
      }))
      mockGetPoolMasterDataChartJob.mockImplementation(async (jobId: string) => ({
        job: createdJobs.find((job) => job.id === jobId) ?? buildChartJob({ id: jobId }),
      }))

      renderPage('/pools/master-data?tab=chart-import')

      expect(await screen.findByText('Authoritative Source')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Open Chart Import zone' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Open Bootstrap Import zone' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Open Sync zone' })).toBeInTheDocument()
      expect(screen.getByText('No chart job is selected yet.')).toBeInTheDocument()
      expect(await screen.findByTestId('pool-master-data-chart-import-selected-source-id')).toHaveTextContent('chart-source-1')

      fireEvent.click(screen.getByTestId('chart-import-upsert-source'))
      await waitFor(() =>
        expect(mockUpsertPoolMasterDataChartSource).toHaveBeenCalledWith({
          database_id: 'db-1',
          chart_identity: 'ChartOfAccounts_Main',
        }),
      )

      fireEvent.click(screen.getByTestId('chart-import-run-preflight'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataChartJob).toHaveBeenNthCalledWith(1, {
          chart_source_id: 'chart-source-1',
          mode: 'preflight',
          database_ids: undefined,
        }),
      )

      await waitFor(() => expect(screen.getByTestId('chart-import-run-dry-run')).toBeEnabled())
      fireEvent.click(screen.getByTestId('chart-import-run-dry-run'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataChartJob).toHaveBeenNthCalledWith(2, {
          chart_source_id: 'chart-source-1',
          mode: 'dry_run',
          database_ids: undefined,
        }),
      )

      await waitFor(() => expect(screen.getByTestId('chart-import-run-materialize')).toBeEnabled())
      fireEvent.click(screen.getByTestId('chart-import-run-materialize'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataChartJob).toHaveBeenNthCalledWith(3, {
          chart_source_id: 'chart-source-1',
          mode: 'materialize',
          database_ids: undefined,
        }),
      )

      await waitFor(() => expect(screen.getByTestId('chart-import-run-verify')).toBeEnabled())
      fireEvent.click(screen.getByTestId('chart-import-run-verify'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataChartJob).toHaveBeenNthCalledWith(4, {
          chart_source_id: 'chart-source-1',
          mode: 'verify_followers',
          database_ids: ['db-2'],
        }),
      )

      await waitFor(() => expect(screen.getByTestId('chart-import-run-backfill')).toBeEnabled())
      fireEvent.click(screen.getByTestId('chart-import-run-backfill'))
      await waitFor(() =>
        expect(mockCreatePoolMasterDataChartJob).toHaveBeenNthCalledWith(5, {
          chart_source_id: 'chart-source-1',
          mode: 'backfill_bindings',
          database_ids: ['db-2'],
        }),
      )

      expect(await screen.findByTestId('pool-master-data-chart-import-selected-source-id')).toHaveTextContent('chart-source-1')
      expect(await screen.findByTestId('pool-master-data-chart-import-selected-job-id')).toHaveTextContent('job-backfill_bindings')
      expect(screen.getByText('Binding points to stale Ref_Key.')).toBeInTheDocument()
      expect(await screen.findByRole('link', { name: 'Open Bindings' })).toHaveAttribute('href', '/pools/master-data?tab=bindings&entityType=gl_account&databaseId=db-2&canonicalId=gl-account-001')

      expect(mockRunPoolMasterDataBootstrapImportPreflight).not.toHaveBeenCalled()
      expect(mockCreatePoolMasterDataBootstrapImportJob).not.toHaveBeenCalled()
      expect(mockCreatePoolMasterDataSyncLaunch).not.toHaveBeenCalled()
    },
    HEAVY_ROUTE_TEST_TIMEOUT_MS,
  )
}
