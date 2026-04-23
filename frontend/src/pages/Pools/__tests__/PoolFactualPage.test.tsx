import { StrictMode, type ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp, ConfigProvider } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import type {
  PoolFactualOverviewItem,
  PoolFactualRefreshResponse,
  PoolFactualReviewActionResponse,
  PoolFactualReviewQueue,
  PoolFactualReviewQueueItem,
  PoolFactualWorkspace,
} from '../../../api/intercompanyPools'
import { createLocaleFormatters } from '../../../i18n'
import { changeLanguage, ensureNamespaces, i18n } from '../../../i18n/runtime'
import { resetQueryClient } from '../../../lib/queryClient'
import { PoolFactualPage } from '../PoolFactualPage'
import { buildPoolFactualRoute } from '../routes'


const mockListPoolFactualOverview = vi.fn()
const mockGetPoolFactualWorkspace = vi.fn()
const mockRefreshPoolFactualWorkspace = vi.fn()
const mockApplyPoolFactualReviewAction = vi.fn()
let consoleErrorSpy: ReturnType<typeof vi.spyOn> | null = null
const englishFormatters = createLocaleFormatters('en')

const translatePoolFactual = (key: string, options?: Record<string, unknown>) => (
  (i18n.t as unknown as (fullKey: string, values?: Record<string, unknown>) => string)(`poolFactual:${key}`, options)
)

const formatPoolFactualTimestamp = (value: string | null | undefined) => (
  englishFormatters.dateTime(value, {
    fallback: '—',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC',
    timeZoneName: 'short',
  })
)

const formatPoolFactualDate = (value: string | null | undefined) => (
  englishFormatters.date(value, {
    fallback: '—',
  })
)

vi.mock('../../../api/intercompanyPools', async () => {
  const actual = await vi.importActual<typeof import('../../../api/intercompanyPools')>(
    '../../../api/intercompanyPools'
  )
  return {
    ...actual,
    listPoolFactualOverview: (...args: unknown[]) => mockListPoolFactualOverview(...args),
    getPoolFactualWorkspace: (...args: unknown[]) => mockGetPoolFactualWorkspace(...args),
    refreshPoolFactualWorkspace: (...args: unknown[]) => mockRefreshPoolFactualWorkspace(...args),
    applyPoolFactualReviewAction: (...args: unknown[]) => mockApplyPoolFactualReviewAction(...args),
  }
})

vi.mock('../../../components/platform', async () => {
  const actual = await vi.importActual<typeof import('../../../components/platform')>(
    '../../../components/platform'
  )
  const router = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')

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
    const value = Array.isArray(dataIndex)
      ? dataIndex.reduce<unknown>((current, key) => (
        current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined
      ), row)
      : typeof dataIndex === 'string'
        ? row[dataIndex]
        : undefined

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
    RouteButton: ({
      to,
      onClick,
      children,
      type,
      ...props
    }: {
      to?: string
      onClick?: (event: { preventDefault: () => void; defaultPrevented: boolean }) => void
      children?: ReactNode
      type?: string
      [key: string]: unknown
    }) => {
      const navigate = router.useNavigate()
      return (
        <button
          type="button"
          data-variant={type}
          onClick={() => {
            let defaultPrevented = false
            onClick?.({
              preventDefault: () => {
                defaultPrevented = true
              },
              get defaultPrevented() {
                return defaultPrevented
              },
            })
            if (!defaultPrevented && typeof to === 'string') {
              navigate(to)
            }
          }}
          {...props}
        >
          {children}
        </button>
      )
    },
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
      title: ReactNode
      extra?: ReactNode
      error?: ReactNode
      loading?: boolean
      empty?: boolean
      emptyDescription?: ReactNode
      children?: ReactNode
    }) => (
      <section>
        <h3>{title}</h3>
        {extra}
        {error ? error : loading ? <div>Loading</div> : empty ? emptyDescription : children}
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
        {error ? error : loading ? <div>Loading</div> : dataSource.length === 0 ? <div>{emptyDescription}</div> : (
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
                const resolvedRowKey = typeof rowKey === 'function'
                  ? rowKey(row)
                  : String(row[rowKey] ?? rowIndex)
                const rowProps = onRow?.(row, rowIndex)
                return (
                  <tr
                    key={resolvedRowKey}
                    className={rowClassName?.(row, rowIndex)}
                    onClick={rowProps?.onClick}
                  >
                    {columns.map((column, columnIndex) => (
                      <td key={String(column.key ?? column.dataIndex ?? columnIndex)}>
                        {renderTableCell(column, row, rowIndex)}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    ),
    StatusBadge: ({
      status,
      label,
    }: {
      status?: ReactNode
      label?: ReactNode
    }) => <span>{label ?? status}</span>,
    ModalFormShell: ({
      open,
      onClose,
      onSubmit,
      title,
      subtitle,
      submitText,
      cancelText,
      confirmLoading,
      submitDisabled,
      footerStart,
      children,
      submitButtonTestId,
    }: {
      open: boolean
      onClose: () => void
      onSubmit?: () => void | Promise<void>
      title?: ReactNode
      subtitle?: ReactNode
      submitText?: ReactNode
      cancelText?: ReactNode
      confirmLoading?: boolean
      submitDisabled?: boolean
      footerStart?: ReactNode
      children: ReactNode
      submitButtonTestId?: string
    }) => (
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
      ) : null
    ),
  }
})

function buildReviewItem(overrides: Partial<PoolFactualReviewQueueItem> = {}): PoolFactualReviewQueueItem {
  return {
    id: 'unattributed-pool-alpha',
    pool_id: '11111111-1111-1111-1111-111111111111',
    batch_id: 'batch-receipt-1',
    organization_id: 'organization-leaf-1',
    edge_id: 'edge-alpha-1',
    reason: 'unattributed',
    status: 'pending',
    quarter: '2026Q1',
    source_document_ref: "Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')",
    allowed_actions: ['attribute', 'resolve_without_change'],
    attention_required: false,
    resolved_at: null,
    ...overrides,
  }
}

function buildReviewQueue(items?: PoolFactualReviewQueueItem[]): PoolFactualReviewQueue {
  const resolvedItems = items ?? [
    buildReviewItem(),
    buildReviewItem({
      id: 'late-correction-pool-alpha',
      reason: 'late_correction',
      batch_id: null,
      source_document_ref: "Document_КорректировкаРеализации(guid'pool-alpha-late')",
      allowed_actions: ['reconcile', 'resolve_without_change'],
      attention_required: true,
    }),
  ]

  return {
    contract_version: 'pool_factual_review_queue.v1',
    subsystem: 'reconcile_review',
    summary: {
      pending_total: resolvedItems.filter((item) => item.status === 'pending').length,
      unattributed_total: resolvedItems.filter(
        (item) => item.status === 'pending' && item.reason === 'unattributed'
      ).length,
      late_correction_total: resolvedItems.filter(
        (item) => item.status === 'pending' && item.reason === 'late_correction'
      ).length,
      attention_required_total: resolvedItems.filter((item) => item.attention_required).length,
    },
    items: resolvedItems,
  }
}

function buildOverviewItem(overrides: Partial<PoolFactualOverviewItem> = {}): PoolFactualOverviewItem {
  const poolId = overrides.pool_id ?? '11111111-1111-1111-1111-111111111111'
  return {
    pool_id: poolId,
    pool_code: 'pool-alpha',
    pool_name: 'Pool Alpha',
    pool_description: 'Primary factual pool',
    pool_is_active: true,
    summary: buildWorkspace({ pool_id: poolId }).summary,
    ...overrides,
  }
}

function buildWorkspace(overrides: Partial<PoolFactualWorkspace> = {}): PoolFactualWorkspace {
  const poolId = overrides.pool_id ?? '11111111-1111-1111-1111-111111111111'
  const reviewQueue = overrides.review_queue ?? buildReviewQueue()
  const checkpoints = overrides.checkpoints ?? [
    {
      checkpoint_id: 'checkpoint-ready-1',
      database_id: 'database-1',
      database_name: 'Pool factual DB 1',
      workflow_status: '',
      freshness_state: 'fresh',
      last_synced_at: '2026-03-27T10:00:00Z',
      last_error_code: '',
      last_error: '',
      execution_id: null,
      operation_id: null,
      activity: 'active',
      polling_tier: 'active',
      poll_interval_seconds: 120,
      freshness_target_seconds: 120,
    },
  ]
  const settlements = overrides.settlements ?? [
    {
      id: 'batch-receipt-1',
      tenant_id: 'tenant-1',
      pool_id: poolId,
      batch_kind: 'receipt',
      source_type: 'manual',
      schema_template_id: null,
      start_organization_id: 'org-root-1',
      run_id: 'run-001',
      workflow_execution_id: null,
      operation_id: null,
      workflow_status: '',
      period_start: '2026-01-01',
      period_end: '2026-03-31',
      source_reference: 'receipt-q1',
      raw_payload_ref: '',
      content_hash: 'hash-1',
      source_metadata: {},
      normalization_summary: {},
      publication_summary: {},
      last_error_code: '',
      last_error: '',
      created_by_id: null,
      created_at: '2026-03-27T09:00:00Z',
      updated_at: '2026-03-27T09:30:00Z',
      settlement: {
        id: 'settlement-receipt-1',
        tenant_id: 'tenant-1',
        batch_id: 'batch-receipt-1',
        status: 'partially_closed',
        incoming_amount: '120.00',
        outgoing_amount: '80.00',
        open_balance: '40.00',
        summary: {},
        freshness_at: '2026-03-27T10:00:00Z',
        created_at: '2026-03-27T09:00:00Z',
        updated_at: '2026-03-27T09:30:00Z',
      },
    },
    {
      id: 'batch-sale-1',
      tenant_id: 'tenant-1',
      pool_id: poolId,
      batch_kind: 'sale',
      source_type: 'manual',
      schema_template_id: null,
      start_organization_id: null,
      run_id: null,
      workflow_execution_id: 'workflow-sale-1',
      operation_id: 'operation-sale-1',
      workflow_status: 'completed',
      period_start: '2026-01-01',
      period_end: '2026-03-31',
      source_reference: 'sale-q1',
      raw_payload_ref: '',
      content_hash: 'hash-2',
      source_metadata: {},
      normalization_summary: {},
      publication_summary: {},
      last_error_code: '',
      last_error: '',
      created_by_id: null,
      created_at: '2026-03-27T09:00:00Z',
      updated_at: '2026-03-27T09:30:00Z',
      settlement: {
        id: 'settlement-sale-1',
        tenant_id: 'tenant-1',
        batch_id: 'batch-sale-1',
        status: 'attention_required',
        incoming_amount: '50.00',
        outgoing_amount: '35.00',
        open_balance: '15.00',
        summary: {},
        freshness_at: '2026-03-27T10:00:00Z',
        created_at: '2026-03-27T09:00:00Z',
        updated_at: '2026-03-27T09:30:00Z',
      },
    },
  ]
  const settlementAttentionRequiredTotal = settlements.filter(
    (item) => item.settlement?.status === 'attention_required'
  ).length

  return {
    pool_id: poolId,
    summary: {
      quarter: '2026Q1',
      quarter_start: '2026-01-01',
      quarter_end: '2026-03-31',
      amount_with_vat: '120.00',
      amount_without_vat: '100.00',
      vat_amount: '20.00',
      incoming_amount: '170.00',
      outgoing_amount: '115.00',
      open_balance: '55.00',
      pending_review_total: reviewQueue.summary.pending_total,
      attention_required_total: Math.max(
        settlementAttentionRequiredTotal,
        reviewQueue.summary.attention_required_total
      ),
      backlog_total: 0,
      freshness_state: 'fresh',
      source_availability: 'available',
      source_availability_detail: '',
      last_synced_at: '2026-03-27T10:00:00Z',
      sync_status: 'success',
      checkpoints_pending: 0,
      checkpoints_running: 0,
      checkpoints_failed: 0,
      checkpoints_ready: 1,
      activity: 'active',
      polling_tier: 'active',
      poll_interval_seconds: 120,
      freshness_target_seconds: 120,
      scope_fingerprint: 'scope-fp-q1',
      scope_contract_version: 'factual_scope_contract.v2',
      gl_account_set_revision_id: 'gl_account_set_rev_q1',
      scope_contract: {
        contract_version: 'factual_scope_contract.v2',
        selector_key: `pool:${poolId}:sales_report_v1:2026-01-01`,
        gl_account_set_id: '33333333-3333-3333-3333-333333333333',
        gl_account_set_revision_id: 'gl_account_set_rev_q1',
        scope_fingerprint: 'scope-fp-q1',
        effective_members: [
          {
            canonical_id: 'factual_sales_report_62_01',
            code: '62.01',
            name: '62.01',
            chart_identity: 'ChartOfAccounts_Хозрасчетный',
            sort_order: 0,
          },
          {
            canonical_id: 'factual_sales_report_90_01',
            code: '90.01',
            name: '90.01',
            chart_identity: 'ChartOfAccounts_Хозрасчетный',
            sort_order: 1,
          },
        ],
        resolved_bindings: [
          {
            canonical_id: 'factual_sales_report_62_01',
            code: '62.01',
            name: '62.01',
            chart_identity: 'ChartOfAccounts_Хозрасчетный',
            sort_order: 0,
            target_ref_key: 'account-62',
            binding_source: 'binding_table',
          },
          {
            canonical_id: 'factual_sales_report_90_01',
            code: '90.01',
            name: '90.01',
            chart_identity: 'ChartOfAccounts_Хозрасчетный',
            sort_order: 1,
            target_ref_key: 'account-90',
            binding_source: 'binding_table',
          },
        ],
      },
      settlement_total: settlements.length,
      checkpoint_total: 1,
    },
    checkpoints,
    settlements,
    edge_balances: [
      {
        id: 'edge-balance-1',
        pool_id: poolId,
        batch_id: 'batch-receipt-1',
        organization_id: 'organization-leaf-1',
        organization_name: 'Leaf Alpha',
        edge_id: 'edge-alpha-1',
        parent_node_id: 'parent-node-1',
        child_node_id: 'child-node-1',
        quarter: '2026Q1',
        quarter_start: '2026-01-01',
        quarter_end: '2026-03-31',
        amount_with_vat: '120.00',
        amount_without_vat: '100.00',
        vat_amount: '20.00',
        incoming_amount: '120.00',
        outgoing_amount: '80.00',
        open_balance: '40.00',
        freshness_at: '2026-03-27T10:00:00Z',
        metadata: {},
      },
    ],
    review_queue: reviewQueue,
    ...overrides,
  }
}

function buildRefreshResponse(
  overrides: Partial<PoolFactualRefreshResponse> = {}
): PoolFactualRefreshResponse {
  return {
    pool_id: '11111111-1111-1111-1111-111111111111',
    quarter_start: '2026-01-01',
    requested_at: '2026-03-27T10:01:00Z',
    status: 'running',
    activity: 'active',
    polling_tier: 'active',
    poll_interval_seconds: 120,
    freshness_target_seconds: 120,
    checkpoint_total: 1,
    checkpoints_pending: 0,
    checkpoints_running: 1,
    checkpoints_failed: 0,
    checkpoints_ready: 0,
    checkpoints: [
      {
        checkpoint_id: 'checkpoint-1',
        database_id: 'database-1',
        database_name: 'Pool factual DB 1',
        workflow_status: 'running',
        freshness_state: 'stale',
        last_synced_at: '2026-03-27T10:00:00Z',
        last_error_code: '',
        last_error: '',
        execution_id: 'execution-1',
        operation_id: 'operation-1',
        activity: 'active',
        polling_tier: 'active',
        poll_interval_seconds: 120,
        freshness_target_seconds: 120,
      },
    ],
    ...overrides,
  }
}

function renderPage(initialEntry = '/pools/factual', options?: { strict?: boolean }) {
  const tree = (
    <MemoryRouter initialEntries={[initialEntry]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <ConfigProvider theme={{ token: { motion: false } }} wave={{ disabled: true }}>
        <AntApp>
          <PoolFactualPage />
          <LocationProbe />
        </AntApp>
      </ConfigProvider>
    </MemoryRouter>
  )

  return render(options?.strict ? <StrictMode>{tree}</StrictMode> : tree)
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

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="pool-factual-location">{`${location.pathname}${location.search}`}</div>
}

describe('PoolFactualPage', () => {
  beforeAll(async () => {
    await ensureNamespaces('en', 'poolFactual')
    await changeLanguage('en')
  })

  beforeEach(() => {
    resetQueryClient()
    mockListPoolFactualOverview.mockReset()
    mockGetPoolFactualWorkspace.mockReset()
    mockRefreshPoolFactualWorkspace.mockReset()
    mockApplyPoolFactualReviewAction.mockReset()
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      const [firstArg] = args
      if (typeof firstArg === 'string' && firstArg.includes('not wrapped in act')) {
        return
      }
    })
  })

  afterEach(() => {
    consoleErrorSpy?.mockRestore()
    consoleErrorSpy = null
  })

  afterAll(async () => {
    await changeLanguage('ru')
  })

  it('renders live factual summary, settlement, drill-down, and review sections for the selected pool', async () => {
    const user = userEvent.setup()
    const receiptSettlement = buildWorkspace().settlements[0].settlement
    if (!receiptSettlement) {
      throw new Error('Expected fixture settlement for batch-receipt-1')
    }
    mockListPoolFactualOverview.mockResolvedValue([
      buildOverviewItem(),
      buildOverviewItem({
        pool_id: '22222222-2222-2222-2222-222222222222',
        pool_code: 'pool-beta',
        pool_name: 'Pool Beta',
      }),
    ])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace({
      settlements: [
        ...buildWorkspace().settlements,
        {
          ...buildWorkspace().settlements[0],
          id: 'batch-receipt-carry',
          source_reference: 'receipt-carry-forward',
          settlement: {
            ...receiptSettlement,
            id: 'settlement-carry-forward',
            batch_id: 'batch-receipt-carry',
            status: 'carried_forward',
            incoming_amount: '120.00',
            outgoing_amount: '80.00',
            open_balance: '40.00',
            summary: {
              carry_forward: {
                source_snapshot_id: '11111111-aaaa-bbbb-cccc-111111111111',
                target_snapshot_id: '22222222-aaaa-bbbb-cccc-222222222222',
                target_quarter_start: '2026-04-01',
                target_quarter_end: '2026-06-30',
                applied_at: '2026-04-01T00:05:00Z',
              },
            },
            freshness_at: '2026-03-31T20:15:00Z',
            created_at: '2026-03-27T09:00:00Z',
            updated_at: '2026-03-27T09:30:00Z',
          },
        },
      ],
    }))

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&run=run-001&focus=settlement&detail=1&quarter_start=2026-01-01')

    await screen.findByText('Factual operator workspace')
    await screen.findByText('receipt-q1')

    expect(mockGetPoolFactualWorkspace).toHaveBeenLastCalledWith({
      poolId: '11111111-1111-1111-1111-111111111111',
      quarterStart: '2026-01-01',
    })
    expect(screen.getByText('Batch settlement')).toBeInTheDocument()
    expect(screen.getByText('Edge drill-down')).toBeInTheDocument()
    expect(screen.getByText('Manual review queue')).toBeInTheDocument()
    expect(screen.getByText('Linked run: run-001')).toBeInTheDocument()
    expect(screen.getByText('Overall state')).toBeInTheDocument()
    expect(screen.getByText('Pool movement')).toBeInTheDocument()
    expect(screen.getByText('Run-linked settlement handoff')).toBeInTheDocument()
    expect(
      screen.getByText('Overall state').compareDocumentPosition(screen.getByText('Pool movement')) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    expect(
      screen.getByText('Pool movement').compareDocumentPosition(screen.getByText('Run-linked settlement handoff')) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    expect(screen.getAllByText('Needs attention').length).toBeGreaterThan(0)
    expect(screen.getAllByText('170.00').length).toBeGreaterThan(0)
    expect(screen.getAllByText('115.00').length).toBeGreaterThan(0)
    expect(screen.getAllByText('55.00').length).toBeGreaterThan(0)
    expect(screen.getByText('With VAT 120.00, without VAT 100.00, VAT 20.00.')).toBeInTheDocument()
    expect(
      screen.getByText(translatePoolFactual('detail.runLinkedSettlement.matchedSettlement', {
        settlement: 'receipt-q1',
        status: 'partially closed',
        openBalance: '40.00',
      }))
    ).toBeInTheDocument()
    expect(screen.getByText(translatePoolFactual('detail.freshness.sourceSummary', {
      availability: 'available',
      value: formatPoolFactualTimestamp('2026-03-27T10:00:00Z'),
    }))).toBeInTheDocument()
    expect(screen.getByText('Read backlog is clear on the default sync lane.')).toBeInTheDocument()
    expect(screen.getByText('Scope lineage')).toBeInTheDocument()
    await user.click(screen.getByText('Scope lineage'))
    expect(screen.getByText('Fingerprint scope-fp-q1; revision gl_account_set_rev_q1.')).toBeInTheDocument()
    expect(
      screen.getByText('Selector pool:11111111-1111-1111-1111-111111111111:sales_report_v1:2026-01-01.')
    ).toBeInTheDocument()
    expect(screen.getByText('2 effective member(s), 2 pinned binding(s).')).toBeInTheDocument()
    expect(screen.getByText('sale-q1')).toBeInTheDocument()
    expect(screen.getByText('Leaf Alpha · edge-alp')).toBeInTheDocument()
    expect(screen.getAllByText('In 120.00 · Out 80.00 · Open 40.00').length).toBeGreaterThan(0)
    expect(screen.getByText(translatePoolFactual('common.targetQuarter', {
      value: `${englishFormatters.date('2026-04-01')} -> ${englishFormatters.date('2026-06-30')}`,
    }))).toBeInTheDocument()
    expect(screen.getByText('source 11111111 -> target 22222222')).toBeInTheDocument()
    expect(screen.getByText("Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')")).toBeInTheDocument()
    expect(screen.getByText("Document_КорректировкаРеализации(guid'pool-alpha-late')")).toBeInTheDocument()
  })

  it('surfaces explicit read backlog details in the factual freshness card', async () => {
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
    const workspace = buildWorkspace()
    workspace.summary.backlog_total = 2
    workspace.summary.freshness_state = 'stale'
    mockGetPoolFactualWorkspace.mockResolvedValue(workspace)

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText(translatePoolFactual('detail.freshness.sourceSummary', {
      availability: 'available',
      value: formatPoolFactualTimestamp('2026-03-27T10:00:00Z'),
    }))
    expect(
      screen.queryAllByText('Read backlog has 2 overdue checkpoint(s) on the default sync lane.').length
    ).toBeGreaterThan(0)
  })

  it('prioritizes freshness warnings over review counters in compact and detail verdict copy', async () => {
    const warningSummary = {
      ...buildWorkspace().summary,
      backlog_total: 3,
      freshness_state: 'stale',
      attention_required_total: 4,
      pending_review_total: 5,
    }
    mockListPoolFactualOverview.mockResolvedValue([
      buildOverviewItem({
        summary: warningSummary,
      }),
    ])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace({
      summary: warningSummary,
    }))

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    const overviewButton = await screen.findByRole('button', { name: 'Open factual workspace for Pool Alpha' })
    await screen.findByText('Overall state')

    expect(within(overviewButton).getByText('Data is stale')).toBeInTheDocument()
    expect(within(overviewButton).queryByText('4 attention required')).not.toBeInTheDocument()
    expect(screen.getByText('The factual read model is stale for the selected quarter.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open freshness details' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open manual review queue' })).not.toBeInTheDocument()
  })

  it('renders explicit zero-incoming copy instead of a completion ratio', async () => {
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem({
      summary: {
        ...buildWorkspace().summary,
        incoming_amount: '0.00',
        outgoing_amount: '0.00',
        open_balance: '0.00',
      },
    })])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace({
      summary: {
        ...buildWorkspace().summary,
        incoming_amount: '0.00',
        outgoing_amount: '0.00',
        open_balance: '0.00',
      },
    }))

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText('Pool movement')
    expect(screen.getByText(translatePoolFactual('detail.movement.noIncoming'))).toBeInTheDocument()
    expect(screen.queryByText(/Outgoing share /)).not.toBeInTheDocument()
  })

  it('treats workspace load failures as a critical state and offers a retry path', async () => {
    const user = userEvent.setup()
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
    mockGetPoolFactualWorkspace
      .mockRejectedValueOnce(new Error('workspace failed'))
      .mockResolvedValueOnce(buildWorkspace())

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await waitFor(() => {
      expect(screen.getAllByText('Critical issue').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('Failed to load factual workspace data.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry workspace load' }))

    await waitFor(() => {
      expect(mockGetPoolFactualWorkspace).toHaveBeenCalledTimes(2)
    })
    await screen.findByText('receipt-q1')
  })

  it('polls the factual workspace on the default 120-second interval', async () => {
    const pollHandlers: Array<() => void> = []
    const setIntervalSpy = vi.spyOn(window, 'setInterval').mockImplementation(((handler: TimerHandler, timeout?: number) => {
      if (typeof handler !== 'function') {
        throw new Error('Expected polling handler to be a function')
      }
      if (timeout === 120000) {
        pollHandlers.push(() => {
          handler()
        })
      }
      return 1 as unknown as number
    }) as typeof window.setInterval)
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined)

    try {
      mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
      mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace())

      renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111')

      await waitFor(() => expect(mockGetPoolFactualWorkspace).toHaveBeenCalledTimes(1))
      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 120000)
      const runPoll = pollHandlers[pollHandlers.length - 1]
      if (runPoll === undefined) {
        throw new Error('Expected polling handler to be a function')
      }

      await act(async () => {
        runPoll()
      })

      await waitFor(() => expect(mockGetPoolFactualWorkspace).toHaveBeenCalledTimes(2))
    } finally {
      setIntervalSpy.mockRestore()
      clearIntervalSpy.mockRestore()
    }
  })

  it('updates the factual route query when the operator selects a pool from the compact master pane', async () => {
    const user = userEvent.setup()
    mockListPoolFactualOverview.mockResolvedValue([
      buildOverviewItem(),
      buildOverviewItem({
        pool_id: '22222222-2222-2222-2222-222222222222',
        pool_code: 'pool-beta',
        pool_name: 'Pool Beta',
      }),
    ])
    mockGetPoolFactualWorkspace.mockImplementation(
      async ({ poolId }: { poolId: string }) => buildWorkspace({
        pool_id: poolId,
        settlements: [
          {
            ...buildWorkspace().settlements[0],
            pool_id: poolId,
            source_reference: poolId === '22222222-2222-2222-2222-222222222222' ? 'receipt-beta' : 'receipt-alpha',
          },
        ],
      })
    )

    renderPage('/pools/factual')

    await screen.findByText('Pool Alpha')
    await user.click(screen.getByRole('button', { name: 'Open factual workspace for Pool Beta' }))

    await waitFor(() => {
      expect(screen.getByTestId('pool-factual-location').textContent).toContain('/pools/factual?pool=22222222-2222-2222-2222-222222222222&detail=1')
    })
    await screen.findByText('receipt-beta')

    expect(mockGetPoolFactualWorkspace).toHaveBeenLastCalledWith({
      poolId: '22222222-2222-2222-2222-222222222222',
    })
  })

  it('keeps execution controls out of the factual workspace', async () => {
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace())

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText('receipt-q1')

    expect(screen.getByText('Pool movement')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Open Pool Runs' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Refresh factual sync' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create / Upsert Run' })).not.toBeInTheDocument()
    expect(screen.queryByText('Create Run')).not.toBeInTheDocument()
  })

  it('shows factual sync checkpoint diagnostics with workflow and operations handoff', async () => {
    const user = userEvent.setup()
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace({
      summary: {
        ...buildWorkspace().summary,
        sync_status: 'failed',
        checkpoints_failed: 1,
        checkpoints_ready: 0,
        checkpoint_total: 1,
        backlog_total: 1,
        freshness_state: 'stale',
      },
      checkpoints: [
        {
          checkpoint_id: 'checkpoint-failed-1',
          database_id: 'database-1',
          database_name: 'Pool factual DB 1',
          workflow_status: 'failed',
          freshness_state: 'stale',
          last_synced_at: null,
          last_error_code: 'POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_MISSING',
          last_error: '',
          execution_id: 'execution-failed-1',
          operation_id: 'operation-failed-1',
          activity: 'active',
          polling_tier: 'active',
          poll_interval_seconds: 120,
          freshness_target_seconds: 120,
        },
      ],
    }))

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText('Sync diagnostics')
    await screen.findByText('Pool factual DB 1')
    expect(screen.getByText('Error POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_MISSING')).toBeInTheDocument()
    expect(screen.getByText('Fix GL Account coverage in Bindings')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open workflow execution execution-failed-1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open operation monitor operation-failed-1' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open GL Account bindings' }))
    await waitFor(() => {
      expect(screen.getByTestId('pool-factual-location')).toHaveTextContent(
        '/pools/master-data?tab=bindings&entityType=gl_account&databaseId=database-1'
      )
    })
  })

  it('lets the operator trigger a shipped factual refresh path from the workspace', async () => {
    const user = userEvent.setup()
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace())
    mockRefreshPoolFactualWorkspace.mockResolvedValue(buildRefreshResponse())

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1&quarter_start=2026-01-01')

    await screen.findByText('Sync control')
    await user.click(screen.getByRole('button', { name: 'Refresh factual sync' }))

    await waitFor(() => {
      expect(mockRefreshPoolFactualWorkspace).toHaveBeenCalledWith({
        pool_id: '11111111-1111-1111-1111-111111111111',
        quarter_start: '2026-01-01',
      })
    })
    expect(screen.getByText('1 running, 0 pending, 0 failed, 0 ready checkpoint(s).')).toBeInTheDocument()
    expect(screen.getByText(translatePoolFactual('common.requestedTier', {
      value: formatPoolFactualTimestamp('2026-03-27T10:01:00Z'),
      tier: 'active',
      seconds: 120,
    }))).toBeInTheDocument()
  })

  it('converges refresh state to terminal workspace status without another manual click', async () => {
    const user = userEvent.setup()
    const intervalHandlers = new Map<number, Array<() => void>>()
    const setIntervalSpy = vi.spyOn(window, 'setInterval').mockImplementation(((handler: TimerHandler, timeout?: number) => {
      if (typeof handler === 'function' && typeof timeout === 'number') {
        const existing = intervalHandlers.get(timeout) ?? []
        existing.push(() => {
          handler()
        })
        intervalHandlers.set(timeout, existing)
      }
      return 1 as unknown as number
    }) as typeof window.setInterval)
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined)

    try {
      mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
      mockGetPoolFactualWorkspace
        .mockResolvedValueOnce(buildWorkspace({
          summary: {
            ...buildWorkspace().summary,
            checkpoint_total: 0,
            sync_status: 'idle',
            checkpoints_pending: 0,
            checkpoints_running: 0,
            checkpoints_failed: 0,
            checkpoints_ready: 0,
            activity: '',
            polling_tier: '',
            poll_interval_seconds: 0,
            freshness_target_seconds: 0,
          },
        }))
        .mockResolvedValue(buildWorkspace({
          summary: {
            ...buildWorkspace().summary,
            sync_status: 'success',
            checkpoints_pending: 0,
            checkpoints_running: 0,
            checkpoints_failed: 0,
            checkpoints_ready: 1,
            activity: 'active',
            polling_tier: 'active',
            poll_interval_seconds: 120,
            freshness_target_seconds: 120,
          },
        }))
      mockRefreshPoolFactualWorkspace.mockResolvedValue(buildRefreshResponse())

      renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1&quarter_start=2026-01-01')

      await screen.findByText('Sync control')
      await user.click(screen.getByRole('button', { name: 'Refresh factual sync' }))

      await waitFor(() => {
        expect(mockRefreshPoolFactualWorkspace).toHaveBeenCalledTimes(1)
      })
      expect(intervalHandlers.get(5000)?.length ?? 0).toBeGreaterThan(0)
      expect(screen.getByText('1 running, 0 pending, 0 failed, 0 ready checkpoint(s).')).toBeInTheDocument()

      const refreshPoll = intervalHandlers.get(5000)?.[0]
      if (!refreshPoll) {
        throw new Error('Expected short refresh polling handler to be registered')
      }

      await act(async () => {
        refreshPoll()
      })

      await waitFor(() => {
        expect(mockGetPoolFactualWorkspace).toHaveBeenCalledTimes(2)
      })
      expect(screen.getByText('0 running, 0 pending, 0 failed, 1 ready checkpoint(s).')).toBeInTheDocument()
      expect(screen.getByText(translatePoolFactual('common.requestedTier', {
        value: formatPoolFactualTimestamp('2026-03-27T10:01:00Z'),
        tier: 'active',
        seconds: 120,
      }))).toBeInTheDocument()
    } finally {
      setIntervalSpy.mockRestore()
      clearIntervalSpy.mockRestore()
    }
  })

  it('opens an attribution modal and updates queue state after choosing explicit targets', async () => {
    const user = userEvent.setup()
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])
    const baseWorkspace = buildWorkspace()
    const baseReceiptBatch = baseWorkspace.settlements[0]
    if (!baseReceiptBatch?.settlement) {
      throw new Error('Expected receipt settlement fixture to exist.')
    }
    const baseReceiptSettlement = baseReceiptBatch.settlement
    const initialReviewQueue = buildReviewQueue([
      buildReviewItem({
        batch_id: null,
        edge_id: null,
        organization_id: null,
      }),
      buildReviewItem({
        id: 'late-correction-pool-alpha',
        reason: 'late_correction',
        batch_id: null,
        source_document_ref: "Document_КорректировкаРеализации(guid'pool-alpha-late')",
        allowed_actions: ['reconcile', 'resolve_without_change'],
        attention_required: true,
      }),
    ])
    const afterAttributeQueue = buildReviewQueue([
      buildReviewItem({
        status: 'attributed',
        batch_id: 'batch-receipt-2',
        edge_id: 'edge-beta-1',
        organization_id: 'organization-leaf-2',
        allowed_actions: [],
        attention_required: false,
        resolved_at: '2026-03-27T10:05:00Z',
      }),
      buildReviewItem({
        id: 'late-correction-pool-alpha',
        reason: 'late_correction',
        batch_id: null,
        source_document_ref: "Document_КорректировкаРеализации(guid'pool-alpha-late')",
        allowed_actions: ['reconcile', 'resolve_without_change'],
        attention_required: true,
      }),
    ])
    const afterReconcileQueue = buildReviewQueue([
      buildReviewItem({
        status: 'attributed',
        batch_id: 'batch-receipt-2',
        edge_id: 'edge-beta-1',
        organization_id: 'organization-leaf-2',
        allowed_actions: [],
        attention_required: false,
        resolved_at: '2026-03-27T10:05:00Z',
      }),
      buildReviewItem({
        id: 'late-correction-pool-alpha',
        reason: 'late_correction',
        status: 'reconciled',
        batch_id: null,
        source_document_ref: "Document_КорректировкаРеализации(guid'pool-alpha-late')",
        allowed_actions: [],
        attention_required: false,
        resolved_at: '2026-03-27T10:10:00Z',
      }),
    ])
    const initialWorkspace = buildWorkspace({
      settlements: [
        ...baseWorkspace.settlements,
        {
          ...baseReceiptBatch,
          id: 'batch-receipt-2',
          tenant_id: baseReceiptBatch.tenant_id,
          source_reference: 'receipt-q2',
          period_start: '2026-04-01',
          period_end: '2026-06-30',
          settlement: {
            ...baseReceiptSettlement,
            id: 'settlement-receipt-2',
            tenant_id: baseReceiptSettlement.tenant_id,
            batch_id: 'batch-receipt-2',
            status: 'ingested',
            incoming_amount: '90.00',
            outgoing_amount: '0.00',
            open_balance: '90.00',
          },
        },
      ],
      edge_balances: [
        ...baseWorkspace.edge_balances,
        {
          ...baseWorkspace.edge_balances[0],
          id: 'edge-balance-2',
          batch_id: 'batch-receipt-2',
          organization_id: 'organization-leaf-2',
          organization_name: 'Leaf Beta',
          edge_id: 'edge-beta-1',
          parent_node_id: 'parent-node-2',
          child_node_id: 'child-node-2',
          open_balance: '25.00',
        },
      ],
      review_queue: initialReviewQueue,
    })
    const workspaceAfterAttribute = buildWorkspace({
      settlements: initialWorkspace.settlements,
      edge_balances: initialWorkspace.edge_balances,
      review_queue: afterAttributeQueue,
    })
    const workspaceAfterReconcile = buildWorkspace({
      settlements: initialWorkspace.settlements,
      edge_balances: initialWorkspace.edge_balances,
      review_queue: afterReconcileQueue,
    })

    mockGetPoolFactualWorkspace
      .mockResolvedValueOnce(initialWorkspace)
      .mockResolvedValueOnce(workspaceAfterAttribute)
      .mockResolvedValueOnce(workspaceAfterReconcile)

    mockApplyPoolFactualReviewAction
      .mockResolvedValueOnce({
        review_item: afterAttributeQueue.items[0],
        review_queue: afterAttributeQueue,
      } satisfies PoolFactualReviewActionResponse)
      .mockResolvedValueOnce({
        review_item: afterReconcileQueue.items[1],
        review_queue: afterReconcileQueue,
      } satisfies PoolFactualReviewActionResponse)

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&focus=review&detail=1')

    await screen.findByText('Manual review queue')
    await screen.findByText("Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')")

    const unattributedRow = screen
      .getByText("Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')")
      .closest('tr')
    expect(unattributedRow).not.toBeNull()
    expect(within(unattributedRow as HTMLElement).getByRole('button', { name: 'Attribute review item unattributed-pool-alpha' })).toBeInTheDocument()
    expect(within(unattributedRow as HTMLElement).queryByRole('button', { name: 'Reconcile review item unattributed-pool-alpha' })).not.toBeInTheDocument()

    const lateCorrectionRow = screen
      .getByText("Document_КорректировкаРеализации(guid'pool-alpha-late')")
      .closest('tr')
    expect(lateCorrectionRow).not.toBeNull()
    expect(within(lateCorrectionRow as HTMLElement).getByRole('button', { name: 'Reconcile review item late-correction-pool-alpha' })).toBeInTheDocument()
    expect(within(lateCorrectionRow as HTMLElement).queryByRole('button', { name: 'Attribute review item late-correction-pool-alpha' })).not.toBeInTheDocument()

    await user.click(within(unattributedRow as HTMLElement).getByRole('button', { name: 'Attribute review item unattributed-pool-alpha' }))
    const attributeDialog = await screen.findByRole('dialog')
    await within(attributeDialog).findByText(translatePoolFactual('modal.infoTitle'))
    openSelectByTestId('pool-factual-attribute-batch-select')
    await selectDropdownOption(`receipt-q2 · ${formatPoolFactualDate('2026-04-01')} · receipt`)
    openSelectByTestId('pool-factual-attribute-edge-select')
    await selectDropdownOption('Leaf Beta · edge-bet')
    openSelectByTestId('pool-factual-attribute-organization-select')
    await selectDropdownOption('Leaf Beta')
    await user.click(within(attributeDialog).getByRole('button', { name: translatePoolFactual('modal.submit') }))
    await waitFor(() => {
      expect(within(unattributedRow as HTMLElement).getByText('attributed')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('1 pending')).toBeInTheDocument()
    })

    await user.click(within(lateCorrectionRow as HTMLElement).getByRole('button', { name: 'Reconcile review item late-correction-pool-alpha' }))
    await waitFor(() => {
      expect(within(lateCorrectionRow as HTMLElement).getByText('reconciled')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('0 pending')).toBeInTheDocument()
    })

    expect(mockApplyPoolFactualReviewAction).toHaveBeenNthCalledWith(1, expect.objectContaining({
      review_item_id: 'unattributed-pool-alpha',
      action: 'attribute',
      batch_id: 'batch-receipt-2',
      edge_id: 'edge-beta-1',
      organization_id: 'organization-leaf-2',
    }))
    expect(mockApplyPoolFactualReviewAction).toHaveBeenNthCalledWith(2, expect.objectContaining({
      review_item_id: 'late-correction-pool-alpha',
      action: 'reconcile',
    }))
    expect(mockGetPoolFactualWorkspace).toHaveBeenNthCalledWith(2, { poolId: '11111111-1111-1111-1111-111111111111' })
    expect(mockGetPoolFactualWorkspace).toHaveBeenNthCalledWith(3, { poolId: '11111111-1111-1111-1111-111111111111' })
  })

  it('recomputes top-level attention summary when review action refresh fails', async () => {
    const user = userEvent.setup()
    mockListPoolFactualOverview.mockResolvedValue([buildOverviewItem()])

    const lateCorrectionDocumentRef = "Document_КорректировкаРеализации(guid'pool-alpha-late')"
    const initialReviewQueue = buildReviewQueue([
      buildReviewItem({
        id: 'late-correction-pool-alpha',
        reason: 'late_correction',
        batch_id: null,
        source_document_ref: lateCorrectionDocumentRef,
        allowed_actions: ['reconcile', 'resolve_without_change'],
        attention_required: true,
      }),
    ])
    const resolvedReviewQueue = buildReviewQueue([
      buildReviewItem({
        id: 'late-correction-pool-alpha',
        reason: 'late_correction',
        status: 'reconciled',
        batch_id: null,
        source_document_ref: lateCorrectionDocumentRef,
        allowed_actions: [],
        attention_required: false,
        resolved_at: '2026-03-27T10:10:00Z',
      }),
    ])
    const baseWorkspace = buildWorkspace()
    const initialWorkspace = buildWorkspace({
      settlements: [baseWorkspace.settlements[0]],
      review_queue: initialReviewQueue,
    })

    mockGetPoolFactualWorkspace
      .mockResolvedValueOnce(initialWorkspace)
      .mockRejectedValueOnce(new Error('refresh failed'))

    mockApplyPoolFactualReviewAction.mockResolvedValueOnce({
      review_item: resolvedReviewQueue.items[0],
      review_queue: resolvedReviewQueue,
    } satisfies PoolFactualReviewActionResponse)

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&focus=review&detail=1')

    await screen.findByText('Manual review queue')
    await screen.findByText(lateCorrectionDocumentRef)

    await user.click(screen.getByRole('button', { name: 'Reconcile review item late-correction-pool-alpha' }))

    await waitFor(() => {
      expect(screen.getByText('0 pending')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('0 attention required')).toBeInTheDocument()
    })
    expect(screen.getByText('Manual intervention is not currently required.')).toBeInTheDocument()
  })

  it('builds a focus-aware factual route for settlement handoff from run report', () => {
    expect(
      buildPoolFactualRoute({
        poolId: 'pool-1',
        runId: 'run-1',
        quarterStart: '2026-01-01',
        focus: 'settlement',
        detail: true,
      })
    ).toBe('/pools/factual?pool=pool-1&run=run-1&quarter_start=2026-01-01&focus=settlement&detail=1')
  })
})
