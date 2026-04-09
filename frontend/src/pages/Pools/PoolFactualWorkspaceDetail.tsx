import { useEffect, useState } from 'react'
import { Alert, Button, Descriptions, Space, Typography } from 'antd'

import {
  applyPoolFactualReviewAction as applyPoolFactualReviewActionRequest,
  getPoolFactualWorkspace,
  type OrganizationPool,
  type PoolBatch,
  type PoolFactualEdgeBalance,
  type PoolFactualRefreshCheckpoint,
  type PoolFactualRefreshResponse,
  type PoolFactualReviewQueue,
  type PoolFactualReviewQueueItem,
  type PoolFactualSummary,
  type PoolFactualWorkspace,
  refreshPoolFactualWorkspace,
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

type PoolFactualRefreshCardState = {
  requestedAt: string | null
  status: string
  checkpointsPending: number
  checkpointsRunning: number
  checkpointsFailed: number
  checkpointsReady: number
  activity: string
  pollingTier: string
  pollIntervalSeconds: number
  freshnessTargetSeconds: number
}

const FACTUAL_WORKSPACE_POLL_INTERVAL_MS = 120_000
const FACTUAL_REFRESH_STATE_POLL_INTERVAL_MS = 5_000

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

const formatQuarterWindow = (quarterStart: string | null | undefined, quarterEnd: string | null | undefined) => {
  if (quarterStart && quarterEnd) {
    return `${quarterStart} -> ${quarterEnd}`
  }
  return quarterStart ?? quarterEnd ?? '-'
}

const buildRefreshStateFromResponse = (
  response: PoolFactualRefreshResponse
): PoolFactualRefreshCardState => ({
  requestedAt: response.requested_at,
  status: response.status,
  checkpointsPending: response.checkpoints_pending,
  checkpointsRunning: response.checkpoints_running,
  checkpointsFailed: response.checkpoints_failed,
  checkpointsReady: response.checkpoints_ready,
  activity: response.activity,
  pollingTier: response.polling_tier,
  pollIntervalSeconds: response.poll_interval_seconds,
  freshnessTargetSeconds: response.freshness_target_seconds,
})

const buildRefreshStateFromSummary = (
  summary: PoolFactualSummary,
  requestedAt: string | null
): PoolFactualRefreshCardState | null => {
  if (summary.checkpoint_total <= 0) {
    return null
  }
  return {
    requestedAt,
    status: summary.sync_status,
    checkpointsPending: summary.checkpoints_pending,
    checkpointsRunning: summary.checkpoints_running,
    checkpointsFailed: summary.checkpoints_failed,
    checkpointsReady: summary.checkpoints_ready,
    activity: summary.activity,
    pollingTier: summary.polling_tier,
    pollIntervalSeconds: summary.poll_interval_seconds,
    freshnessTargetSeconds: summary.freshness_target_seconds,
  }
}

const isRefreshStateInFlight = (refreshState: PoolFactualRefreshCardState | null) => (
  refreshState?.status === 'pending' || refreshState?.status === 'running'
)

const getRefreshTone = (refreshState: PoolFactualRefreshCardState | null) => {
  switch (refreshState?.status) {
    case 'running':
      return 'warning'
    case 'pending':
      return 'warning'
    case 'failed':
      return 'error'
    case 'success':
      return 'active'
    default:
      return 'unknown'
  }
}

const getRefreshCopy = (refreshState: PoolFactualRefreshCardState | null) => {
  if (!refreshState) {
    return 'Use the shipped refresh control when the operator needs an immediate bounded sync for this pool and quarter.'
  }
  return `${refreshState.checkpointsRunning} running, ${refreshState.checkpointsPending} pending, ${refreshState.checkpointsFailed} failed, ${refreshState.checkpointsReady} ready checkpoint(s).`
}

const getSyncCheckpointTone = (checkpoint: PoolFactualRefreshCheckpoint) => {
  switch (checkpoint.workflow_status) {
    case 'running':
    case 'pending':
      return 'warning'
    case 'failed':
      return 'error'
    case '':
      return 'active'
    default:
      return 'unknown'
  }
}

const getSyncCheckpointStatusLabel = (checkpoint: PoolFactualRefreshCheckpoint) => (
  checkpoint.workflow_status.trim() || 'ready'
)

const getSyncCheckpointDatabaseLabel = (checkpoint: PoolFactualRefreshCheckpoint) => (
  checkpoint.database_name?.trim() || `Database ${formatShortId(checkpoint.database_id)}`
)

const buildWorkflowExecutionDetailsHref = (executionId: string) => (
  `/workflows/executions?execution=${encodeURIComponent(executionId)}&detail=1`
)

const buildOperationMonitorHref = (operationId: string) => (
  `/operations?operation=${encodeURIComponent(operationId)}&tab=monitor`
)

const getCarryForwardSummary = (row: PoolBatch) => {
  const carryForward = row.settlement?.summary?.carry_forward
  if (!carryForward || typeof carryForward !== 'object') {
    return null
  }
  const summary = carryForward as Record<string, unknown>
  return {
    sourceSnapshotId: typeof summary.source_snapshot_id === 'string' ? summary.source_snapshot_id : null,
    targetSnapshotId: typeof summary.target_snapshot_id === 'string' ? summary.target_snapshot_id : null,
    targetQuarterStart: typeof summary.target_quarter_start === 'string' ? summary.target_quarter_start : null,
    targetQuarterEnd: typeof summary.target_quarter_end === 'string' ? summary.target_quarter_end : null,
    appliedAt: typeof summary.applied_at === 'string' ? summary.applied_at : null,
  }
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
  if (summary.backlog_total > 0) {
    return 'warning'
  }
  if (summary.freshness_state === 'stale') {
    return 'warning'
  }
  return summary.last_synced_at ? 'active' : 'unknown'
}

const getBacklogCopy = (summary: PoolFactualSummary | null) => {
  if (!summary) {
    return 'This card surfaces source availability, read backlog, and the latest factual sync timestamp.'
  }
  if (summary.backlog_total > 0) {
    return `Read backlog has ${summary.backlog_total} overdue checkpoint(s) on the default sync lane.`
  }
  return 'Read backlog is clear on the default sync lane.'
}

const getScopeLineageTone = (summary: PoolFactualSummary | null) => {
  if (!summary) {
    return 'unknown'
  }
  if (summary.scope_contract?.resolved_bindings?.length) {
    return 'active'
  }
  if (summary.scope_fingerprint) {
    return 'warning'
  }
  return 'unknown'
}

const countAttentionRequiredSettlements = (workspace: PoolFactualWorkspace | null | undefined) => (
  workspace?.settlements.filter((row) => row.settlement?.status === 'attention_required').length ?? 0
)

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
  const [refreshingWorkspace, setRefreshingWorkspace] = useState(false)
  const [refreshState, setRefreshState] = useState<PoolFactualRefreshCardState | null>(null)
  const [syncCheckpoints, setSyncCheckpoints] = useState<PoolFactualRefreshCheckpoint[]>([])
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [reviewActionError, setReviewActionError] = useState<string | null>(null)
  const [pendingReviewItemId, setPendingReviewItemId] = useState<string | null>(null)
  const [attributeReviewRow, setAttributeReviewRow] = useState<ReviewRowWithTargets | null>(null)

  useEffect(() => {
    setRefreshState(null)
    setSyncCheckpoints([])
    setRefreshError(null)
  }, [quarterStart, selectedPool.id])

  useEffect(() => {
    let cancelled = false

    const loadWorkspace = async ({ background = false }: { background?: boolean } = {}) => {
      if (!background) {
        setLoadingWorkspace(true)
        setWorkspaceError(null)
      }
      if (!background) {
        setRefreshError(null)
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
        setSyncCheckpoints(data.checkpoints ?? [])
        setRefreshState((current) => {
          const next = buildRefreshStateFromSummary(
            data.summary,
            current?.requestedAt ?? null,
          )
          return next ?? current
        })
      } catch (error) {
        if (cancelled) {
          return
        }
        const resolved = resolveApiError(error, 'Failed to load factual workspace data.')
        setWorkspaceError(resolved.message)
        if (!background) {
          setSyncCheckpoints([])
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

  useEffect(() => {
    if (!isRefreshStateInFlight(refreshState)) {
      return
    }

    let cancelled = false
    const pollId = window.setInterval(() => {
      void (async () => {
        try {
          const data = await getPoolFactualWorkspace({
            poolId: selectedPool.id,
            quarterStart: quarterStart ?? undefined,
          })
          if (cancelled) {
            return
          }
          setWorkspace(data)
          setSyncCheckpoints(data.checkpoints ?? [])
          setRefreshState((current) => {
            const next = buildRefreshStateFromSummary(
              data.summary,
              current?.requestedAt ?? refreshState?.requestedAt ?? null,
            )
            return next ?? current
          })
        } catch {
          // Keep the last known state and let the regular workspace polling recover.
        }
      })()
    }, FACTUAL_REFRESH_STATE_POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(pollId)
    }
  }, [quarterStart, refreshState, selectedPool.id])

  const handleRefreshWorkspace = async () => {
    setRefreshingWorkspace(true)
    setRefreshError(null)

    try {
      const response = await refreshPoolFactualWorkspace({
        pool_id: selectedPool.id,
        quarter_start: quarterStart ?? undefined,
      })
      setSyncCheckpoints(response.checkpoints ?? [])
      setRefreshState(buildRefreshStateFromResponse(response))
    } catch (error) {
      const resolved = resolveApiError(error, 'Failed to refresh factual workspace sync.')
      setRefreshError(resolved.message)
    } finally {
      setRefreshingWorkspace(false)
    }
  }

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
              attention_required_total: Math.max(
                countAttentionRequiredSettlements(current),
                response.review_queue.summary.attention_required_total,
              ),
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

      {refreshError ? (
        <Alert
          type="error"
          showIcon
          message="Factual refresh request failed"
          description={refreshError}
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
          <Text strong>Sync control</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <Space wrap>
                <StatusBadge
                  status={getRefreshTone(refreshState)}
                  label={refreshState?.status ?? 'idle'}
                />
                <Button
                  type="primary"
                  loading={refreshingWorkspace}
                  aria-label="Refresh factual sync"
                  onClick={() => {
                    void handleRefreshWorkspace()
                  }}
                >
                  Refresh factual sync
                </Button>
              </Space>
              <Text type="secondary">{getRefreshCopy(refreshState)}</Text>
              {refreshState ? (
                <Text type="secondary">
                  {refreshState.requestedAt
                    ? `Requested ${formatTimestamp(refreshState.requestedAt)} on ${refreshState.pollingTier || 'unknown'} tier (${refreshState.pollIntervalSeconds}s).`
                    : `Current ${refreshState.pollingTier || 'unknown'} tier (${refreshState.pollIntervalSeconds}s) for this workspace context.`}
                </Text>
              ) : null}
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
                <Space direction="vertical" size={4}>
                  <Text type="secondary">
                    Source {workspace.summary.source_availability}; last sync {formatTimestamp(workspace.summary.last_synced_at)}.
                  </Text>
                  <Text type="secondary">{getBacklogCopy(workspace.summary)}</Text>
                </Space>
              ) : (
                <Text type="secondary">
                  {getBacklogCopy(null)}
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
          <Text strong>Pinned scope lineage</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={getScopeLineageTone(workspace?.summary ?? null)}
                label={workspace?.summary.scope_contract_version || 'legacy scope only'}
              />
              {workspace?.summary.scope_contract ? (
                <Space direction="vertical" size={4}>
                  <Text type="secondary">
                    Fingerprint {workspace.summary.scope_fingerprint}; revision {workspace.summary.gl_account_set_revision_id}.
                  </Text>
                  <Text type="secondary">
                    Selector {workspace.summary.scope_contract.selector_key}.
                  </Text>
                  <Text type="secondary">
                    {workspace.summary.scope_contract.effective_members.length} effective member(s),
                    {' '}
                    {workspace.summary.scope_contract.resolved_bindings.length} pinned binding(s).
                  </Text>
                </Space>
              ) : (
                <Text type="secondary">
                  Pinned selector lineage and resolved bindings appear here once the workspace is backed by
                  factual_scope_contract.v2 metadata.
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

      {syncCheckpoints.length > 0 ? (
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space direction="vertical" size={4}>
              <Text strong>Sync diagnostics</Text>
              <Text type="secondary">
                Secondary workflow and operations handoff for factual sync checkpoints stays local to this workspace.
              </Text>
            </Space>

            {syncCheckpoints.map((checkpoint) => (
              <div
                key={checkpoint.checkpoint_id}
                style={{
                  border: '1px solid #f0f0f0',
                  borderRadius: 12,
                  padding: 12,
                  background: '#fafafa',
                }}
              >
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space wrap>
                    <Text strong>{getSyncCheckpointDatabaseLabel(checkpoint)}</Text>
                    <StatusBadge
                      status={getSyncCheckpointTone(checkpoint)}
                      label={getSyncCheckpointStatusLabel(checkpoint)}
                    />
                    <Text code>{formatShortId(checkpoint.checkpoint_id)}</Text>
                  </Space>

                  <Text type="secondary">
                    {checkpoint.last_error_code
                      ? `Error ${checkpoint.last_error_code}${checkpoint.last_error ? ` · ${checkpoint.last_error}` : ''}`
                      : checkpoint.last_synced_at
                        ? `Last sync ${formatTimestamp(checkpoint.last_synced_at)}`
                        : 'No sync error recorded for this checkpoint.'}
                  </Text>

                  <Space wrap>
                    {checkpoint.execution_id ? (
                      <RouteButton
                        size="small"
                        aria-label={`Open workflow execution ${checkpoint.execution_id}`}
                        to={buildWorkflowExecutionDetailsHref(checkpoint.execution_id)}
                      >
                        Workflow execution {formatShortId(checkpoint.execution_id)}
                      </RouteButton>
                    ) : (
                      <Text type="secondary">No workflow execution linked.</Text>
                    )}

                    {checkpoint.operation_id ? (
                      <RouteButton
                        size="small"
                        aria-label={`Open operation monitor ${checkpoint.operation_id}`}
                        to={buildOperationMonitorHref(checkpoint.operation_id)}
                      >
                        Operation {formatShortId(checkpoint.operation_id)}
                      </RouteButton>
                    ) : (
                      <Text type="secondary">No operation projection linked.</Text>
                    )}
                  </Space>
                </Space>
              </div>
            ))}
          </Space>
        </div>
      ) : null}

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
            title: 'Amounts',
            key: 'amounts',
            render: (_: unknown, row: PoolBatch) => (
              <Space direction="vertical" size={4}>
                <Text>Incoming {row.settlement?.incoming_amount ?? '-'}</Text>
                <Text>Outgoing {row.settlement?.outgoing_amount ?? '-'}</Text>
                <Text>Open balance {row.settlement?.open_balance ?? '-'}</Text>
              </Space>
            ),
          },
          {
            title: 'Carry-forward',
            key: 'carry_forward',
            render: (_: unknown, row: PoolBatch) => {
              const carryForward = getCarryForwardSummary(row)
              if (!carryForward) {
                return <Text type="secondary">-</Text>
              }
              return (
                <Space direction="vertical" size={4}>
                  <Text>{`Target quarter ${formatQuarterWindow(carryForward.targetQuarterStart, carryForward.targetQuarterEnd)}`}</Text>
                  <Text type="secondary">
                    {`source ${formatShortId(carryForward.sourceSnapshotId)} -> target ${formatShortId(carryForward.targetSnapshotId)}`}
                  </Text>
                  {carryForward.appliedAt ? <Text type="secondary">Applied {formatTimestamp(carryForward.appliedAt)}</Text> : null}
                </Space>
              )
            },
          },
          {
            title: 'Freshness',
            key: 'freshness',
            render: (_: unknown, row: PoolBatch) => (
              <Text type="secondary">{formatTimestamp(row.settlement?.freshness_at)}</Text>
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
            title: 'Amounts',
            key: 'amounts',
            render: (_: unknown, row: PoolFactualEdgeBalance) => (
              <Space direction="vertical" size={4}>
                <Text>Incoming {row.incoming_amount}</Text>
                <Text>Outgoing {row.outgoing_amount}</Text>
                <Text>Open balance {row.open_balance}</Text>
              </Space>
            ),
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
