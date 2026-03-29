import { useEffect, useState } from 'react'
import { Alert, Button, Descriptions, Space, Typography } from 'antd'

import {
  applyPoolFactualReviewAction as applyPoolFactualReviewActionRequest,
  getPoolFactualWorkspace,
  type OrganizationPool,
  type PoolBatch,
  type PoolFactualEdgeBalance,
  type PoolFactualReviewQueue,
  type PoolFactualReviewQueueItem,
  type PoolFactualSummary,
  type PoolFactualWorkspace,
} from '../../api/intercompanyPools'
import { EntityTable, RouteButton, StatusBadge } from '../../components/platform'
import {
  getPoolFactualReviewActionLabel,
  getPoolFactualReviewReasonLabel,
  getPoolFactualReviewStatusTone,
  type PoolFactualReviewAction,
  type PoolFactualReviewRow,
} from './poolFactualReviewQueue'
import {
  PoolFactualReviewAttributeModal,
  type PoolFactualReviewAttributeValues,
} from './PoolFactualReviewAttributeModal'
import { resolveApiError } from './masterData/errorUtils'


const { Text } = Typography

type PoolFactualWorkspaceDetailProps = {
  selectedPool: OrganizationPool
  focus: 'summary' | 'settlement' | 'drilldown' | 'review'
  runId: string | null
  quarterStart: string | null
  poolCatalogHref: string
  runWorkspaceHref: string
}

type ReviewRowWithTargets = PoolFactualReviewRow & {
  batchId: string | null
  edgeId: string | null
  organizationId: string | null
}

const FACTUAL_WORKSPACE_POLL_INTERVAL_MS = 120_000

const formatShortId = (value: string | null | undefined) => {
  if (!value) {
    return '-'
  }
  return value.slice(0, 8)
}

const formatTimestamp = (value: string | null | undefined) => {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').replace('Z', ' UTC')
}

const buildReviewSummary = (item: PoolFactualReviewQueueItem) => {
  if (item.reason === 'late_correction') {
    return 'Frozen-quarter correction requires manual reconcile before close.'
  }
  return 'Operator must confirm attribution before settlement can close on the default path.'
}

const mapReviewRows = (queue: PoolFactualReviewQueue | null | undefined): ReviewRowWithTargets[] => (
  queue?.items.map((item) => ({
    id: item.id,
    reason: item.reason,
    status: item.status,
    quarter: item.quarter,
    sourceDocumentRef: item.source_document_ref,
    summary: buildReviewSummary(item),
    attentionRequired: item.attention_required,
    allowedActions: item.allowed_actions,
    batchId: item.batch_id,
    edgeId: item.edge_id,
    organizationId: item.organization_id,
  })) ?? []
)

const getFreshnessTone = (summary: PoolFactualSummary | null) => {
  if (!summary) {
    return 'unknown'
  }
  if (summary.source_availability !== 'available') {
    return 'error'
  }
  if (summary.freshness_state === 'stale') {
    return 'warning'
  }
  return summary.last_synced_at ? 'active' : 'unknown'
}

const getSettlementHandoffTone = (workspace: PoolFactualWorkspace | null) => {
  if (!workspace || workspace.settlements.length === 0) {
    return 'unknown'
  }
  if (workspace.summary.attention_required_total > 0) {
    return 'warning'
  }
  return 'active'
}

const getSettlementStatusTone = (status: string | null | undefined) => {
  switch (status) {
    case 'closed':
      return 'active'
    case 'attention_required':
    case 'partially_closed':
    case 'carried_forward':
      return 'warning'
    case 'distributed':
      return 'active'
    default:
      return 'unknown'
  }
}

const buildEdgeLabel = (row: PoolFactualEdgeBalance) => (
  row.edge_id ? `${row.organization_name} · ${formatShortId(row.edge_id)}` : row.organization_name
)

export function PoolFactualWorkspaceDetail({
  selectedPool,
  focus,
  runId,
  quarterStart,
  poolCatalogHref,
  runWorkspaceHref,
}: PoolFactualWorkspaceDetailProps) {
  const [workspace, setWorkspace] = useState<PoolFactualWorkspace | null>(null)
  const [loadingWorkspace, setLoadingWorkspace] = useState(true)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [reviewActionError, setReviewActionError] = useState<string | null>(null)
  const [pendingReviewItemId, setPendingReviewItemId] = useState<string | null>(null)
  const [attributeReviewRow, setAttributeReviewRow] = useState<ReviewRowWithTargets | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadWorkspace = async ({ background = false }: { background?: boolean } = {}) => {
      if (!background) {
        setLoadingWorkspace(true)
        setWorkspaceError(null)
      }
      setReviewActionError(null)

      try {
        const data = await getPoolFactualWorkspace({
          poolId: selectedPool.id,
          quarterStart: quarterStart ?? undefined,
        })
        if (cancelled) {
          return
        }
        setWorkspace(data)
      } catch (error) {
        if (cancelled) {
          return
        }
        const resolved = resolveApiError(error, 'Failed to load factual workspace data.')
        setWorkspaceError(resolved.message)
        if (!background) {
          setWorkspace(null)
        }
      } finally {
        if (!cancelled && !background) {
          setLoadingWorkspace(false)
        }
      }
    }

    void loadWorkspace()
    const pollId = window.setInterval(() => {
      void loadWorkspace({ background: true })
    }, FACTUAL_WORKSPACE_POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(pollId)
    }
  }, [quarterStart, selectedPool.id])

  const reviewRows = mapReviewRows(workspace?.review_queue)
  const linkedSettlement = runId
    ? (workspace?.settlements.find((row) => row.run_id === runId) ?? null)
    : null
  const settlements = linkedSettlement && workspace
    ? [linkedSettlement, ...workspace.settlements.filter((row) => row.id !== linkedSettlement.id)]
    : (workspace?.settlements ?? [])

  const reviewSummary = {
    pendingTotal: workspace?.review_queue.summary.pending_total ?? 0,
    attentionRequiredTotal: workspace?.review_queue.summary.attention_required_total ?? 0,
  }

  const submitReviewAction = async (
    row: ReviewRowWithTargets,
    action: PoolFactualReviewAction,
    targets?: PoolFactualReviewAttributeValues,
  ) => {
    setPendingReviewItemId(row.id)
    setReviewActionError(null)

    try {
      const response = await applyPoolFactualReviewActionRequest({
        review_item_id: row.id,
        action,
        batch_id: targets ? targets.batch_id ?? undefined : row.batchId ?? undefined,
        edge_id: targets ? targets.edge_id ?? undefined : row.edgeId ?? undefined,
        organization_id: targets ? targets.organization_id ?? undefined : row.organizationId ?? undefined,
        note: 'Triggered from factual workspace',
      })
      try {
        const refreshedWorkspace = await getPoolFactualWorkspace({
          poolId: selectedPool.id,
          quarterStart: quarterStart ?? undefined,
        })
        setWorkspace(refreshedWorkspace)
      } catch (error) {
        const resolved = resolveApiError(error, 'Factual review action succeeded but workspace refresh failed.')
        setReviewActionError(resolved.message)
        setWorkspace((current) => {
          if (!current) {
            return current
          }
          return {
            ...current,
            review_queue: response.review_queue,
            summary: {
              ...current.summary,
              pending_review_total: response.review_queue.summary.pending_total,
            },
          }
        })
      }
      if (action === 'attribute') {
        setAttributeReviewRow(null)
      }
    } catch (error) {
      const resolved = resolveApiError(error, 'Failed to apply factual review action.')
      setReviewActionError(resolved.message)
    } finally {
      setPendingReviewItemId(null)
    }
  }

  const handleReviewAction = async (row: ReviewRowWithTargets, action: PoolFactualReviewAction) => {
    await submitReviewAction(row, action)
  }

  const handleOpenAttributeReview = (row: ReviewRowWithTargets) => {
    setReviewActionError(null)
    setAttributeReviewRow(row)
  }

  const handleConfirmAttributeReview = async (values: PoolFactualReviewAttributeValues) => {
    if (!attributeReviewRow) {
      return
    }

    await submitReviewAction(attributeReviewRow, 'attribute', values)
  }

  const reviewColumns = [
    {
      title: 'Reason',
      dataIndex: 'reason',
      key: 'reason',
      render: (_: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <StatusBadge status={getPoolFactualReviewStatusTone(row)} label={getPoolFactualReviewReasonLabel(row.reason)} />
          <Text type="secondary">{row.quarter}</Text>
        </Space>
      ),
    },
    {
      title: 'Document',
      dataIndex: 'sourceDocumentRef',
      key: 'sourceDocumentRef',
      render: (value: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <Text>{value}</Text>
          <Text type="secondary">{row.summary}</Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (_: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <StatusBadge status={getPoolFactualReviewStatusTone(row)} label={row.status} />
          {row.attentionRequired ? <Text type="secondary">attention required</Text> : null}
        </Space>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: unknown, row: PoolFactualReviewRow) => (
        row.allowedActions.length > 0 ? (
          <Space wrap>
            {row.allowedActions.map((action) => (
              <Button
                key={action}
                size="small"
                type={action === 'resolve_without_change' ? 'default' : 'primary'}
                loading={pendingReviewItemId === row.id}
                aria-label={`${getPoolFactualReviewActionLabel(action)} review item ${row.id}`}
                onClick={() => {
                  if (action === 'attribute') {
                    handleOpenAttributeReview(row as ReviewRowWithTargets)
                    return
                  }
                  void handleReviewAction(row as ReviewRowWithTargets, action)
                }}
              >
                {getPoolFactualReviewActionLabel(action)}
              </Button>
            ))}
          </Space>
        ) : (
          <Text type="secondary">Closed in factual workspace</Text>
        )
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Descriptions bordered size="small" column={2}>
        <Descriptions.Item label="Pool" span={1}>
          <Text>{selectedPool.name}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Code" span={1}>
          <Text code>{selectedPool.code}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Linked run" span={1}>
          <Text code>{runId ?? '-'}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Workspace contract" span={1}>
          <Text>factual summary / settlement / review</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Focused section" span={1}>
          <Text>{focus}</Text>
        </Descriptions.Item>
      </Descriptions>

      {runId && focus === 'settlement' ? (
        <div
          style={{
            border: '1px solid #d9f7be',
            borderRadius: 12,
            padding: 16,
            background: '#f6ffed',
          }}
        >
          <Space direction="vertical" size={8}>
            <Space wrap>
              <Text strong>Run-linked settlement handoff</Text>
              <StatusBadge status="active" label="focus=settlement" />
            </Space>
            <Text type="secondary">
              {linkedSettlement
                ? `Matched run-linked settlement ${linkedSettlement.source_reference || formatShortId(linkedSettlement.id)} is ${linkedSettlement.settlement?.status ?? 'pending'} with open balance ${linkedSettlement.settlement?.open_balance ?? '-'}.`
                : 'This deep link keeps the operator in factual dashboard context while starting from the linked run report and its batch settlement handoff.'}
            </Text>
          </Space>
        </div>
      ) : null}

      {workspaceError ? (
        <Alert
          type="error"
          showIcon
          message="Factual workspace data is unavailable"
          description={workspaceError}
        />
      ) : null}

      <div
        style={{
          display: 'grid',
          gap: 16,
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        }}
      >
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Quarter summary</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={workspace ? 'active' : 'unknown'}
                label={workspace ? workspace.summary.quarter : (loadingWorkspace ? 'loading' : 'awaiting data')}
              />
              {workspace ? (
                <Space direction="vertical" size={4}>
                  <Text type="secondary">
                    Incoming {workspace.summary.incoming_amount}, outgoing {workspace.summary.outgoing_amount}, open balance {workspace.summary.open_balance}.
                  </Text>
                  <Text type="secondary">
                    With VAT {workspace.summary.amount_with_vat}, without VAT {workspace.summary.amount_without_vat}, VAT {workspace.summary.vat_amount}.
                  </Text>
                </Space>
              ) : (
                <Text type="secondary">
                  Incoming, outgoing, and open-balance totals appear here after the factual workspace payload loads.
                </Text>
              )}
            </Space>
          </div>
        </div>
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Freshness</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={getFreshnessTone(workspace?.summary ?? null)}
                label={workspace ? workspace.summary.freshness_state : 'not connected'}
              />
              {workspace ? (
                <Text type="secondary">
                  Source {workspace.summary.source_availability}; last sync {formatTimestamp(workspace.summary.last_synced_at)}.
                </Text>
              ) : (
                <Text type="secondary">
                  This card surfaces source availability and the latest factual sync timestamp.
                </Text>
              )}
            </Space>
          </div>
        </div>
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Settlement handoff</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={getSettlementHandoffTone(workspace)}
                label={workspace ? `${workspace.summary.attention_required_total} attention required` : 'batch queue pending'}
              />
              {workspace ? (
                <Text type="secondary">
                  {workspace.settlements.length} batch settlement row(s) are active for {workspace.summary.quarter}.
                </Text>
              ) : (
                <Text type="secondary">
                  Receipt distribution and closing sale handoff stays visible here without mixing execution diagnostics.
                </Text>
              )}
            </Space>
          </div>
        </div>
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Review queue</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={reviewSummary.attentionRequiredTotal > 0 ? 'warning' : 'active'}
                label={`${reviewSummary.pendingTotal} pending`}
              />
              <Text type="secondary">
                Unattributed documents and late corrections stay in this route instead of the run-local canvas.
                {` ${reviewSummary.attentionRequiredTotal} item(s) currently require manual reconcile.`}
              </Text>
            </Space>
          </div>
        </div>
      </div>

      <EntityTable
        title="Batch settlement"
        extra={(
          <Space wrap>
            {focus === 'settlement' ? <StatusBadge status="active" label="run-linked focus" /> : null}
            <RouteButton to={runWorkspaceHref}>Open linked run context</RouteButton>
          </Space>
        )}
        loading={loadingWorkspace}
        dataSource={settlements}
        columns={[
          {
            title: 'Batch',
            dataIndex: 'id',
            key: 'id',
            render: (_: string, row: PoolBatch) => (
              <Space direction="vertical" size={4}>
                <Text>{row.source_reference || formatShortId(row.id)}</Text>
                <Text type="secondary">{row.batch_kind} · {row.period_start}</Text>
                {row.run_id ? <Text type="secondary">run {formatShortId(row.run_id)}</Text> : null}
                {runId && row.run_id === runId ? <Text type="secondary">linked from run report</Text> : null}
              </Space>
            ),
          },
          {
            title: 'Status',
            key: 'status',
            render: (_: unknown, row: PoolBatch) => (
              <StatusBadge
                status={getSettlementStatusTone(row.settlement?.status)}
                label={row.settlement?.status ?? 'pending'}
              />
            ),
          },
          {
            title: 'Open balance',
            key: 'open_balance',
            render: (_: unknown, row: PoolBatch) => (
              <Text>{row.settlement?.open_balance ?? '-'}</Text>
            ),
          },
        ]}
        rowKey="id"
        emptyDescription="No batch settlements were recorded for this quarter."
      />

      <EntityTable
        title="Edge drill-down"
        extra={<RouteButton to={poolCatalogHref}>Open pool topology context</RouteButton>}
        loading={loadingWorkspace}
        dataSource={workspace?.edge_balances ?? []}
        columns={[
          {
            title: 'Edge',
            dataIndex: 'id',
            key: 'id',
            render: (_: string, row: PoolFactualEdgeBalance) => (
              <Space direction="vertical" size={4}>
                <Text>{buildEdgeLabel(row)}</Text>
                <Text type="secondary">{row.quarter}</Text>
              </Space>
            ),
          },
          {
            title: 'Incoming',
            key: 'incoming',
            render: (_: unknown, row: PoolFactualEdgeBalance) => <Text>{row.incoming_amount}</Text>,
          },
          {
            title: 'Open balance',
            key: 'open_balance',
            render: (_: unknown, row: PoolFactualEdgeBalance) => <Text>{row.open_balance}</Text>,
          },
        ]}
        rowKey="id"
        emptyDescription="No edge-level factual balances were projected for this quarter."
      />

      {reviewActionError ? (
        <Alert
          type="error"
          showIcon
          message="Manual review action failed"
          description={reviewActionError}
        />
      ) : null}

      <EntityTable
        title="Manual review queue"
        extra={focus === 'review' ? <StatusBadge status="active" label="review focus" /> : null}
        loading={loadingWorkspace}
        dataSource={reviewRows}
        columns={reviewColumns}
        rowKey="id"
        emptyDescription="No pending factual review items were recorded for this quarter."
      />

      <PoolFactualReviewAttributeModal
        open={Boolean(attributeReviewRow)}
        reviewRow={attributeReviewRow}
        workspace={workspace}
        saving={pendingReviewItemId === attributeReviewRow?.id}
        onCancel={() => {
          setAttributeReviewRow(null)
          setReviewActionError(null)
        }}
        onSubmit={handleConfirmAttributeReview}
      />
    </Space>
  )
}
