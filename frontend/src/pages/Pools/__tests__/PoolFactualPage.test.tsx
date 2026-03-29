import { StrictMode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import type {
  OrganizationPool,
  PoolFactualReviewActionResponse,
  PoolFactualReviewQueue,
  PoolFactualReviewQueueItem,
  PoolFactualWorkspace,
} from '../../../api/intercompanyPools'
import { resetQueryClient } from '../../../lib/queryClient'
import { PoolFactualPage } from '../PoolFactualPage'
import { buildPoolFactualRoute } from '../routes'


const mockListOrganizationPools = vi.fn()
const mockGetPoolFactualWorkspace = vi.fn()
const mockApplyPoolFactualReviewAction = vi.fn()

vi.mock('../../../api/intercompanyPools', async () => {
  const actual = await vi.importActual<typeof import('../../../api/intercompanyPools')>(
    '../../../api/intercompanyPools'
  )
  return {
    ...actual,
    listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
    getPoolFactualWorkspace: (...args: unknown[]) => mockGetPoolFactualWorkspace(...args),
    applyPoolFactualReviewAction: (...args: unknown[]) => mockApplyPoolFactualReviewAction(...args),
  }
})

function buildPool(overrides: Partial<OrganizationPool> = {}): OrganizationPool {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    code: 'pool-alpha',
    name: 'Pool Alpha',
    description: 'Primary factual pool',
    is_active: true,
    metadata: {},
    updated_at: '2026-03-27T00:00:00Z',
    ...overrides,
  }
}

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

function buildWorkspace(overrides: Partial<PoolFactualWorkspace> = {}): PoolFactualWorkspace {
  const poolId = overrides.pool_id ?? '11111111-1111-1111-1111-111111111111'
  const reviewQueue = overrides.review_queue ?? buildReviewQueue()

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
      attention_required_total: 1,
      backlog_total: 0,
      freshness_state: 'fresh',
      source_availability: 'available',
      source_availability_detail: '',
      last_synced_at: '2026-03-27T10:00:00Z',
      settlement_total: 2,
      checkpoint_total: 1,
    },
    settlements: [
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
    ],
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

function renderPage(initialEntry = '/pools/factual', options?: { strict?: boolean }) {
  const tree = (
    <MemoryRouter initialEntries={[initialEntry]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <AntApp>
        <PoolFactualPage />
        <LocationProbe />
      </AntApp>
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
  beforeEach(() => {
    resetQueryClient()
    mockListOrganizationPools.mockReset()
    mockGetPoolFactualWorkspace.mockReset()
    mockApplyPoolFactualReviewAction.mockReset()
  })

  it('renders live factual summary, settlement, drill-down, and review sections for the selected pool', async () => {
    mockListOrganizationPools.mockResolvedValue([
      buildPool(),
      buildPool({
        id: '22222222-2222-2222-2222-222222222222',
        code: 'pool-beta',
        name: 'Pool Beta',
      }),
    ])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace())

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
    expect(screen.getByText('Run-linked settlement handoff')).toBeInTheDocument()
    expect(screen.getByText('Incoming 170.00, outgoing 115.00, open balance 55.00.')).toBeInTheDocument()
    expect(screen.getByText('With VAT 120.00, without VAT 100.00, VAT 20.00.')).toBeInTheDocument()
    expect(
      screen.getByText('Matched run-linked settlement receipt-q1 is partially_closed with open balance 40.00.')
    ).toBeInTheDocument()
    expect(screen.getByText('Source available; last sync 2026-03-27 10:00:00 UTC.')).toBeInTheDocument()
    expect(screen.getByText('Read backlog is clear on the default sync lane.')).toBeInTheDocument()
    expect(screen.getByText('sale-q1')).toBeInTheDocument()
    expect(screen.getByText('Leaf Alpha · edge-alp')).toBeInTheDocument()
    expect(screen.getByText("Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')")).toBeInTheDocument()
    expect(screen.getByText("Document_КорректировкаРеализации(guid'pool-alpha-late')")).toBeInTheDocument()
  })

  it('surfaces explicit read backlog details in the factual freshness card', async () => {
    mockListOrganizationPools.mockResolvedValue([buildPool()])
    const workspace = buildWorkspace()
    workspace.summary.backlog_total = 2
    workspace.summary.freshness_state = 'stale'
    mockGetPoolFactualWorkspace.mockResolvedValue(workspace)

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText('Source available; last sync 2026-03-27 10:00:00 UTC.')
    expect(
      screen.queryAllByText('Read backlog has 2 overdue checkpoint(s) on the default sync lane.').length
    ).toBeGreaterThan(0)
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
      mockListOrganizationPools.mockResolvedValue([buildPool()])
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
    mockListOrganizationPools.mockResolvedValue([
      buildPool(),
      buildPool({
        id: '22222222-2222-2222-2222-222222222222',
        code: 'pool-beta',
        name: 'Pool Beta',
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
    mockListOrganizationPools.mockResolvedValue([buildPool()])
    mockGetPoolFactualWorkspace.mockResolvedValue(buildWorkspace())

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText('receipt-q1')

    expect(screen.getByText('Quarter summary')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open Pool Runs' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create / Upsert Run' })).not.toBeInTheDocument()
    expect(screen.queryByText('Create Run')).not.toBeInTheDocument()
  })

  it('opens an attribution modal and updates queue state after choosing explicit targets', async () => {
    const user = userEvent.setup()
    mockListOrganizationPools.mockResolvedValue([buildPool()])
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
    await screen.findByText('Choose or confirm attribution targets')
    const attributeDialog = screen.getByRole('dialog')
    openSelectByTestId('pool-factual-attribute-batch-select')
    await selectDropdownOption('receipt-q2 · 2026-04-01 · receipt')
    openSelectByTestId('pool-factual-attribute-edge-select')
    await selectDropdownOption('Leaf Beta · edge-bet')
    openSelectByTestId('pool-factual-attribute-organization-select')
    await selectDropdownOption('Leaf Beta')
    await user.click(within(attributeDialog).getByRole('button', { name: 'Confirm attribution' }))
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
