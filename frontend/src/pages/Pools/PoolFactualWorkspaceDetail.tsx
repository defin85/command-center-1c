import { useEffect, useState } from 'react'
import { Alert, Button, Collapse, Progress, Space, Typography } from 'antd'

import {
  applyPoolFactualReviewAction as applyPoolFactualReviewActionRequest,
  getPoolFactualWorkspace,
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
import { usePoolFactualTranslation, type AppStringTranslator } from '../../i18n'
import { useLocaleFormatters } from '../../i18n/formatters'
import {
  getPoolFactualReviewActionLabel,
  getPoolFactualReviewReasonLabel,
  getPoolFactualReviewStatusLabel,
  getPoolFactualReviewStatusTone,
  type PoolFactualReviewAction,
  type PoolFactualReviewRow,
} from './poolFactualReviewQueue'
import {
  getPoolFactualAvailabilityLabel,
  getPoolFactualFreshnessStatusLabel,
  getPoolFactualPrimaryActionLabel,
  getPoolFactualPrimaryReason,
  getPoolFactualSettlementStatusLabel,
  getPoolFactualSyncStatusLabel,
  resolvePoolFactualPrioritySignal,
  getPoolFactualVerdictLabel,
  getPoolFactualVerdictTone,
  resolvePoolFactualVerdict,
} from './poolFactualHealth'
import {
  PoolFactualReviewAttributeModal,
  type PoolFactualReviewAttributeValues,
} from './PoolFactualReviewAttributeModal'
import { resolveApiError } from './masterData/errorUtils'


const { Text } = Typography

type PoolFactualWorkspaceSelection = {
  id: string
  code: string
  name: string
}

type PoolFactualWorkspaceDetailProps = {
  selectedPool: PoolFactualWorkspaceSelection
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

type PoolFactualTranslation = AppStringTranslator
type PoolFactualFormatters = {
  dateTime: (
    value: string | Date | null | undefined,
    options?: Intl.DateTimeFormatOptions & { fallback?: string }
  ) => string
  date: (
    value: string | Date | null | undefined,
    options?: Intl.DateTimeFormatOptions & { fallback?: string }
  ) => string
  number: (
    value: number | null | undefined,
    options?: Intl.NumberFormatOptions & { fallback?: string }
  ) => string
}

const formatShortId = (value: string | null | undefined) => {
  if (!value) {
    return '—'
  }
  return value.slice(0, 8)
}

const parseAmount = (value: string | null | undefined) => {
  const parsed = Number(value ?? '0')
  return Number.isFinite(parsed) ? parsed : 0
}

const formatTimestamp = (
  formatters: PoolFactualFormatters,
  value: string | null | undefined,
) => (
  formatters.dateTime(value, {
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

const formatQuarterWindow = (
  formatters: PoolFactualFormatters,
  quarterStart: string | null | undefined,
  quarterEnd: string | null | undefined,
) => {
  if (quarterStart && quarterEnd) {
    return `${formatters.date(quarterStart)} -> ${formatters.date(quarterEnd)}`
  }
  if (quarterStart) {
    return formatters.date(quarterStart)
  }
  if (quarterEnd) {
    return formatters.date(quarterEnd)
  }
  return '—'
}

const formatAmount = (
  formatters: PoolFactualFormatters,
  value: string | null | undefined,
) => (
  value == null || value === ''
    ? '—'
    : formatters.number(parseAmount(value), {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      fallback: '—',
    })
)

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

const getRefreshCopy = (
  t: PoolFactualTranslation,
  refreshState: PoolFactualRefreshCardState | null,
) => {
  if (!refreshState) {
    return t('detail.refresh.emptyDescription')
  }
  return t('detail.refresh.summary', {
    running: refreshState.checkpointsRunning,
    pending: refreshState.checkpointsPending,
    failed: refreshState.checkpointsFailed,
    ready: refreshState.checkpointsReady,
  })
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

const getSyncCheckpointStatusLabel = (
  t: PoolFactualTranslation,
  checkpoint: PoolFactualRefreshCheckpoint,
) => (
  getPoolFactualSyncStatusLabel(t, checkpoint.workflow_status)
)

const getSyncCheckpointDatabaseLabel = (
  t: PoolFactualTranslation,
  checkpoint: PoolFactualRefreshCheckpoint,
) => (
  checkpoint.database_name?.trim() || t('detail.diagnostics.databaseFallback', {
    value: formatShortId(checkpoint.database_id),
  })
)

const buildWorkflowExecutionDetailsHref = (executionId: string) => (
  `/workflows/executions?execution=${encodeURIComponent(executionId)}&detail=1`
)

const buildOperationMonitorHref = (operationId: string) => (
  `/operations?operation=${encodeURIComponent(operationId)}&tab=monitor`
)

const FACTUAL_GL_ACCOUNT_BINDING_REMEDIATION_CODES = new Set([
  'POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_MISSING',
  'POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_AMBIGUOUS',
  'POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_STALE',
])

const buildMasterDataBindingsHref = ({
  entityType,
  databaseId,
}: {
  entityType: string
  databaseId: string
}) => {
  const params = new URLSearchParams()
  params.set('tab', 'bindings')
  params.set('entityType', entityType)
  params.set('databaseId', databaseId)
  return `/pools/master-data?${params.toString()}`
}

const resolveSyncCheckpointBindingsRemediationHref = (
  checkpoint: PoolFactualRefreshCheckpoint,
): string | null => {
  const lastErrorCode = String(checkpoint.last_error_code || '').trim()
  if (!FACTUAL_GL_ACCOUNT_BINDING_REMEDIATION_CODES.has(lastErrorCode)) {
    return null
  }
  const databaseId = String(checkpoint.database_id || '').trim()
  if (!databaseId) {
    return null
  }
  return buildMasterDataBindingsHref({
    entityType: 'gl_account',
    databaseId,
  })
}

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

const buildReviewSummary = (
  t: PoolFactualTranslation,
  item: PoolFactualReviewQueueItem,
) => {
  if (item.reason === 'late_correction') {
    return t('review.summaries.lateCorrection')
  }
  return t('review.summaries.unattributed')
}

const mapReviewRows = (
  t: PoolFactualTranslation,
  queue: PoolFactualReviewQueue | null | undefined,
): ReviewRowWithTargets[] => (
  queue?.items.map((item) => ({
    id: item.id,
    reason: item.reason,
    status: item.status,
    quarter: item.quarter,
    sourceDocumentRef: item.source_document_ref,
    summary: buildReviewSummary(t, item),
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

const getBacklogCopy = (
  t: PoolFactualTranslation,
  summary: PoolFactualSummary | null,
) => {
  if (!summary) {
    return t('detail.freshness.emptyDescription')
  }
  if (summary.backlog_total > 0) {
    return t('detail.freshness.backlogOverdue', {
      count: summary.backlog_total,
    })
  }
  return t('detail.freshness.backlogClear')
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

const getOverallStateAlertType = (workspaceError: string | null, summary: PoolFactualSummary | null | undefined) => {
  if (workspaceError) {
    return 'error' as const
  }
  switch (resolvePoolFactualVerdict(summary)) {
    case 'critical':
      return 'error' as const
    case 'warning':
      return 'warning' as const
    case 'healthy':
      return 'success' as const
    default:
      return 'info' as const
  }
}

const resolvePrimaryAction = (
  t: PoolFactualTranslation,
  summary: PoolFactualSummary | null | undefined,
) => {
  const label = getPoolFactualPrimaryActionLabel(t, summary)
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'source_unavailable':
    case 'sync_failed':
    case 'checkpoint_failed':
      return {
        label,
        targetId: 'pool-factual-sync-diagnostics',
      }
    case 'stale':
    case 'backlog':
      return {
        label,
        targetId: 'pool-factual-freshness',
      }
    case 'attention_required':
    case 'pending_review':
      return {
        label,
        targetId: 'pool-factual-review-queue',
      }
    case 'healthy':
    case 'unsynced':
      return {
        label,
        targetId: 'pool-factual-settlement-handoff',
      }
    default:
      return {
        label,
        targetId: null,
      }
  }
}

export function PoolFactualWorkspaceDetail({
  selectedPool,
  focus,
  runId,
  quarterStart,
  poolCatalogHref,
  runWorkspaceHref,
}: PoolFactualWorkspaceDetailProps) {
  const { t } = usePoolFactualTranslation()
  const formatters = useLocaleFormatters()
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
  const [detailPanels, setDetailPanels] = useState<string[]>([])

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
        const resolved = resolveApiError(error, t('messages.failedLoadWorkspace'))
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
  }, [quarterStart, selectedPool.id, t])

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
      const resolved = resolveApiError(error, t('messages.failedRefreshWorkspace'))
      setRefreshError(resolved.message)
    } finally {
      setRefreshingWorkspace(false)
    }
  }

  const reviewRows = mapReviewRows(t, workspace?.review_queue)
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
        note: t('messages.reviewActionNote'),
      })
      try {
        const refreshedWorkspace = await getPoolFactualWorkspace({
          poolId: selectedPool.id,
          quarterStart: quarterStart ?? undefined,
        })
        setWorkspace(refreshedWorkspace)
      } catch (error) {
        const resolved = resolveApiError(error, t('messages.workspaceRefreshFailedAfterReview'))
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
      const resolved = resolveApiError(error, t('messages.failedApplyReviewAction'))
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
      title: t('detail.reviewTable.columns.reason'),
      dataIndex: 'reason',
      key: 'reason',
      render: (_: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <StatusBadge
            status={getPoolFactualReviewStatusTone(row)}
            label={getPoolFactualReviewReasonLabel(t, row.reason)}
          />
          <Text type="secondary">{row.quarter}</Text>
        </Space>
      ),
    },
    {
      title: t('detail.reviewTable.columns.document'),
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
      title: t('detail.reviewTable.columns.status'),
      dataIndex: 'status',
      key: 'status',
      render: (_: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <StatusBadge
            status={getPoolFactualReviewStatusTone(row)}
            label={getPoolFactualReviewStatusLabel(t, row.status)}
          />
          {row.attentionRequired ? <Text type="secondary">{t('detail.reviewTable.attentionRequired')}</Text> : null}
        </Space>
      ),
    },
    {
      title: t('detail.reviewTable.columns.action'),
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
                aria-label={t('detail.reviewTable.actionAria', {
                  action: getPoolFactualReviewActionLabel(t, action),
                  id: row.id,
                })}
                onClick={() => {
                  if (action === 'attribute') {
                    handleOpenAttributeReview(row as ReviewRowWithTargets)
                    return
                  }
                  void handleReviewAction(row as ReviewRowWithTargets, action)
                }}
              >
                {getPoolFactualReviewActionLabel(t, action)}
              </Button>
            ))}
          </Space>
        ) : (
          <Text type="secondary">{t('detail.reviewTable.closed')}</Text>
        )
      ),
    },
  ]

  const summary = workspace?.summary ?? null
  const overallVerdict = workspaceError ? 'critical' : resolvePoolFactualVerdict(summary)
  const overallTone = getPoolFactualVerdictTone(overallVerdict)
  const overallLabel = getPoolFactualVerdictLabel(t, overallVerdict)
  const overallReason = workspaceError ?? getPoolFactualPrimaryReason(t, summary)
  const primaryAction = resolvePrimaryAction(t, summary)
  const showRunLinkedSettlementHandoff = Boolean(runId && focus === 'settlement')
  const incomingAmount = parseAmount(summary?.incoming_amount)
  const outgoingAmount = parseAmount(summary?.outgoing_amount)
  const openBalanceAmount = parseAmount(summary?.open_balance)
  const outgoingPercent = incomingAmount > 0
    ? Math.min(100, Math.max(0, Number(((outgoingAmount / incomingAmount) * 100).toFixed(2))))
    : 0
  const openBalancePercent = incomingAmount > 0
    ? Math.min(100, Math.max(0, Number(((openBalanceAmount / incomingAmount) * 100).toFixed(2))))
    : 0
  const vatWithAmount = parseAmount(summary?.amount_with_vat)
  const vatWithoutAmount = parseAmount(summary?.amount_without_vat)
  const vatAmount = parseAmount(summary?.vat_amount)

  const jumpToSection = (targetId: string | null) => {
    if (!targetId) {
      return
    }
    document.getElementById(targetId)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  }

  const reloadWorkspace = async () => {
    setLoadingWorkspace(true)
    setWorkspaceError(null)
    setRefreshError(null)
    setReviewActionError(null)

    try {
      const data = await getPoolFactualWorkspace({
        poolId: selectedPool.id,
        quarterStart: quarterStart ?? undefined,
      })
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
      const resolved = resolveApiError(error, t('messages.failedLoadWorkspace'))
      setWorkspaceError(resolved.message)
      setSyncCheckpoints([])
      setWorkspace(null)
    } finally {
      setLoadingWorkspace(false)
    }
  }

  const handlePrimaryAction = () => {
    if (workspaceError) {
      void reloadWorkspace()
      return
    }
    jumpToSection(primaryAction.targetId)
  }

  useEffect(() => {
    if (overallVerdict !== 'critical') {
      return
    }
    setDetailPanels((current) => (
      current.includes('diagnostics') ? current : [...current, 'diagnostics']
    ))
  }, [overallVerdict])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div
        style={{
          border: '1px solid #f0f0f0',
          borderRadius: 12,
          padding: 16,
          background: '#fff',
        }}
      >
        <Space wrap>
          <Text strong>{selectedPool.name}</Text>
          <Text code>{selectedPool.code}</Text>
          <StatusBadge status={overallTone} label={overallLabel} />
          {summary ? <Text type="secondary">{summary.quarter}</Text> : null}
          {runId ? <Text type="secondary">{t('common.linkedRun', { value: formatShortId(runId) })}</Text> : null}
          <Text type="secondary">{t('common.focus', { value: focus })}</Text>
        </Space>
      </div>

      <Alert
        type={getOverallStateAlertType(workspaceError, summary)}
        showIcon
        message={t('detail.overallState.title')}
        description={(
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space wrap>
              <StatusBadge status={overallTone} label={overallLabel} />
              {summary ? (
                <Text type="secondary">
                  {t('detail.overallState.resolvedQuarter', {
                    quarter: summary.quarter,
                    window: formatQuarterWindow(formatters, summary.quarter_start, summary.quarter_end),
                  })}
                </Text>
              ) : null}
            </Space>
            <Text>{overallReason}</Text>
            <Space wrap>
              {summary?.last_synced_at ? (
                <Text type="secondary">
                  {t('detail.overallState.lastSuccessfulSync', {
                    value: formatTimestamp(formatters, summary.last_synced_at),
                  })}
                </Text>
              ) : (
                <Text type="secondary">{t('detail.overallState.noSuccessfulSync')}</Text>
              )}
              <Button
                type="primary"
                disabled={!workspaceError && !primaryAction.targetId}
                onClick={handlePrimaryAction}
              >
                {workspaceError ? t('detail.overallState.retryWorkspaceLoad') : primaryAction.label}
              </Button>
            </Space>
          </Space>
        )}
      />

      <div
        style={{
          border: '1px solid #f0f0f0',
          borderRadius: 12,
          padding: 16,
          background: '#fff',
        }}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Space wrap>
            <Text strong>{t('detail.movement.title')}</Text>
            <StatusBadge
              status={openBalanceAmount > 0 ? 'warning' : 'active'}
              label={summary ? summary.quarter : (loadingWorkspace ? t('common.loading') : t('health.compactSummary.unknown'))}
            />
          </Space>
          <div
            style={{
              display: 'grid',
              gap: 12,
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            }}
          >
            <div
              style={{
                border: '1px solid #f0f0f0',
                borderRadius: 12,
                padding: 16,
                background: '#fafafa',
              }}
            >
              <Text type="secondary">{t('detail.movement.incoming')}</Text>
              <div style={{ marginTop: 8 }}>
                <Text strong style={{ fontSize: 24 }}>
                  {formatters.number(incomingAmount, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </Text>
              </div>
            </div>
            <div
              style={{
                border: '1px solid #f0f0f0',
                borderRadius: 12,
                padding: 16,
                background: '#fafafa',
              }}
            >
              <Text type="secondary">{t('detail.movement.outgoing')}</Text>
              <div style={{ marginTop: 8 }}>
                <Text strong style={{ fontSize: 24 }}>
                  {formatters.number(outgoingAmount, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </Text>
              </div>
            </div>
            <div
              style={{
                border: '1px solid #f0f0f0',
                borderRadius: 12,
                padding: 16,
                background: '#fafafa',
              }}
            >
              <Text type="secondary">{t('detail.movement.openBalance')}</Text>
              <div style={{ marginTop: 8 }}>
                <Text strong style={{ fontSize: 24 }}>
                  {formatters.number(openBalanceAmount, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </Text>
              </div>
            </div>
          </div>
          {summary ? (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {incomingAmount > 0 ? (
                <Text type="secondary">
                  {t('detail.movement.outgoingShare', {
                    outgoingPercent: formatters.number(outgoingPercent, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }),
                    openBalancePercent: formatters.number(openBalancePercent, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }),
                  })}
                </Text>
              ) : (
                <Text type="secondary">{t('detail.movement.noIncoming')}</Text>
              )}
              <Progress
                percent={outgoingPercent}
                showInfo={false}
                strokeColor="#389e0d"
                trailColor={openBalanceAmount > 0 ? '#faad14' : '#f0f0f0'}
              />
              <Text type="secondary">
                {t('detail.movement.vatSummary', {
                  withVat: formatters.number(vatWithAmount, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  }),
                  withoutVat: formatters.number(vatWithoutAmount, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  }),
                  vat: formatters.number(vatAmount, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  }),
                })}
              </Text>
            </Space>
          ) : (
            <Text type="secondary">{t('detail.movement.emptyDescription')}</Text>
          )}
        </Space>
      </div>

      {refreshError ? (
        <Alert
          type="error"
          showIcon
          message={t('detail.refresh.failedTitle')}
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
        {showRunLinkedSettlementHandoff ? (
          <div
            style={{
              border: '1px solid #d9f7be',
              borderRadius: 12,
              padding: 16,
              background: '#f6ffed',
            }}
          >
            <Text strong>{t('detail.runLinkedSettlement.title')}</Text>
            <div style={{ marginTop: 12 }}>
              <Space direction="vertical" size={8}>
                <Space wrap>
                  <StatusBadge status="active" label={t('common.focusBadge', { value: 'settlement' })} />
                  {linkedSettlement?.settlement?.status ? (
                    <StatusBadge
                      status={getSettlementStatusTone(linkedSettlement.settlement.status)}
                      label={getPoolFactualSettlementStatusLabel(t, linkedSettlement.settlement.status)}
                    />
                  ) : null}
                </Space>
                <Text type="secondary">
                  {linkedSettlement
                    ? t('detail.runLinkedSettlement.matchedSettlement', {
                      settlement: linkedSettlement.source_reference || formatShortId(linkedSettlement.id),
                      status: getPoolFactualSettlementStatusLabel(t, linkedSettlement.settlement?.status),
                      openBalance: formatAmount(formatters, linkedSettlement.settlement?.open_balance),
                    })
                    : t('detail.runLinkedSettlement.emptyDescription')}
                </Text>
              </Space>
            </div>
          </div>
        ) : null}
        <div
          id="pool-factual-freshness"
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>{t('detail.freshness.title')}</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={getFreshnessTone(summary)}
                label={summary ? getPoolFactualFreshnessStatusLabel(t, summary.freshness_state) : t('common.notConnected')}
              />
              {summary ? (
                <Space direction="vertical" size={4}>
                  <Text type="secondary">
                    {t('detail.freshness.sourceSummary', {
                      availability: getPoolFactualAvailabilityLabel(t, summary.source_availability),
                      value: formatTimestamp(formatters, summary.last_synced_at),
                    })}
                  </Text>
                  <Text type="secondary">{getBacklogCopy(t, summary)}</Text>
                </Space>
              ) : (
                <Text type="secondary">{getBacklogCopy(t, null)}</Text>
              )}
            </Space>
          </div>
        </div>
        <div
          id="pool-factual-review-summary"
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>{t('detail.reviewSummary.title')}</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={reviewSummary.attentionRequiredTotal > 0 ? 'warning' : 'active'}
                label={t('detail.reviewSummary.pending', { count: reviewSummary.pendingTotal })}
              />
              <Text type="secondary">
                {reviewSummary.attentionRequiredTotal > 0
                  ? t('detail.reviewSummary.attentionRequired', {
                    count: reviewSummary.attentionRequiredTotal,
                  })
                  : t('detail.reviewSummary.clear')}
              </Text>
              {summary ? (
                <Text type="secondary">
                  {t('detail.reviewSummary.scoped', { quarter: summary.quarter })}
                </Text>
              ) : null}
            </Space>
          </div>
        </div>
        <div
          id="pool-factual-sync-control"
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>{t('detail.refresh.title')}</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <Space wrap>
                <StatusBadge
                  status={getRefreshTone(refreshState)}
                  label={getPoolFactualSyncStatusLabel(t, refreshState?.status ?? 'idle')}
                />
                <Button
                  type="primary"
                  loading={refreshingWorkspace}
                  aria-label={t('detail.refresh.button')}
                  onClick={() => {
                    void handleRefreshWorkspace()
                  }}
                >
                  {t('detail.refresh.button')}
                </Button>
              </Space>
              <Text type="secondary">{getRefreshCopy(t, refreshState)}</Text>
              {refreshState ? (
                <Text type="secondary">
                  {refreshState.requestedAt
                    ? t('common.requestedTier', {
                      value: formatTimestamp(formatters, refreshState.requestedAt),
                      tier: refreshState.pollingTier || t('common.unknown'),
                      seconds: refreshState.pollIntervalSeconds,
                    })
                    : t('common.currentTier', {
                      tier: refreshState.pollingTier || t('common.unknown'),
                      seconds: refreshState.pollIntervalSeconds,
                    })}
                </Text>
              ) : null}
            </Space>
          </div>
        </div>
        <div
          id="pool-factual-settlement-handoff"
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>{t('detail.settlementHandoff.title')}</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={getSettlementHandoffTone(workspace)}
                label={summary
                  ? t('detail.settlementHandoff.attentionRequiredLabel', {
                    count: summary.attention_required_total,
                  })
                  : t('detail.settlementHandoff.pendingLabel')}
              />
              {summary ? (
                <>
                  <Text type="secondary">
                    {t('detail.settlementHandoff.activeBatches', {
                      count: workspace?.settlements.length ?? 0,
                      quarter: summary.quarter,
                    })}
                  </Text>
                  <Text type="secondary">
                    {t('detail.settlementHandoff.openBalance', {
                      value: formatters.number(openBalanceAmount, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      }),
                    })}
                  </Text>
                </>
              ) : (
                <Text type="secondary">{t('detail.settlementHandoff.emptyDescription')}</Text>
              )}
            </Space>
          </div>
        </div>
      </div>

      <Collapse
        activeKey={detailPanels}
        onChange={(keys) => {
          if (Array.isArray(keys)) {
            setDetailPanels(keys.map(String))
            return
          }
          setDetailPanels(keys ? [String(keys)] : [])
        }}
        items={[
          {
            key: 'scope',
            label: t('detail.scope.title'),
            children: (
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Space wrap>
                  <StatusBadge
                    status={getScopeLineageTone(summary)}
                    label={summary?.scope_contract_version || t('detail.scope.legacyScopeOnly')}
                  />
                </Space>
                {summary?.scope_contract ? (
                  <>
                    <Text type="secondary">
                      {t('detail.scope.fingerprint', {
                        fingerprint: summary.scope_fingerprint,
                        revision: summary.gl_account_set_revision_id,
                      })}
                    </Text>
                    <Text type="secondary">
                      {t('detail.scope.selector', {
                        value: summary.scope_contract.selector_key,
                      })}
                    </Text>
                    <Text type="secondary">
                      {t('detail.scope.counts', {
                        members: summary.scope_contract.effective_members.length,
                        bindings: summary.scope_contract.resolved_bindings.length,
                      })}
                    </Text>
                  </>
                ) : (
                  <Text type="secondary">{t('detail.scope.emptyDescription')}</Text>
                )}
              </Space>
            ),
          },
          {
            key: 'diagnostics',
            label: t('detail.diagnostics.title'),
            children: (
              <div id="pool-factual-sync-diagnostics">
                {syncCheckpoints.length > 0 ? (
                  <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <Text type="secondary">{t('detail.diagnostics.summary')}</Text>
                    {syncCheckpoints.map((checkpoint) => {
                      const bindingsRemediationHref = resolveSyncCheckpointBindingsRemediationHref(checkpoint)
                      return (
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
                            {bindingsRemediationHref ? (
                              <Alert
                                type="warning"
                                showIcon
                                message={t('detail.diagnostics.bindingRemediation.title')}
                                description={t('detail.diagnostics.bindingRemediation.description')}
                                action={(
                                  <RouteButton
                                    size="small"
                                    to={bindingsRemediationHref}
                                  >
                                    {t('detail.diagnostics.bindingRemediation.openBindingsWorkspace')}
                                  </RouteButton>
                                )}
                              />
                            ) : null}

                            <Space wrap>
                              <Text strong>{getSyncCheckpointDatabaseLabel(t, checkpoint)}</Text>
                              <StatusBadge
                                status={getSyncCheckpointTone(checkpoint)}
                                label={getSyncCheckpointStatusLabel(t, checkpoint)}
                              />
                              <Text code>{formatShortId(checkpoint.checkpoint_id)}</Text>
                            </Space>

                            <Text type="secondary">
                              {checkpoint.last_error_code
                                ? t('detail.diagnostics.error', {
                                  code: checkpoint.last_error_code,
                                  suffix: checkpoint.last_error ? ` · ${checkpoint.last_error}` : '',
                                })
                                : checkpoint.last_synced_at
                                  ? t('detail.diagnostics.lastSync', {
                                    value: formatTimestamp(formatters, checkpoint.last_synced_at),
                                  })
                                  : t('detail.diagnostics.noSyncError')}
                            </Text>

                            <Space wrap>
                              {checkpoint.execution_id ? (
                                <RouteButton
                                  size="small"
                                  aria-label={t('detail.diagnostics.openWorkflowExecutionAria', {
                                    value: checkpoint.execution_id,
                                  })}
                                  to={buildWorkflowExecutionDetailsHref(checkpoint.execution_id)}
                                >
                                  {t('detail.diagnostics.openWorkflowExecution', {
                                    value: formatShortId(checkpoint.execution_id),
                                  })}
                                </RouteButton>
                              ) : (
                                <Text type="secondary">{t('detail.diagnostics.noWorkflowExecution')}</Text>
                              )}

                              {checkpoint.operation_id ? (
                                <RouteButton
                                  size="small"
                                  aria-label={t('detail.diagnostics.openOperationAria', {
                                    value: checkpoint.operation_id,
                                  })}
                                  to={buildOperationMonitorHref(checkpoint.operation_id)}
                                >
                                  {t('detail.diagnostics.openOperation', {
                                    value: formatShortId(checkpoint.operation_id),
                                  })}
                                </RouteButton>
                              ) : (
                                <Text type="secondary">{t('detail.diagnostics.noOperationProjection')}</Text>
                              )}
                            </Space>
                          </Space>
                        </div>
                      )
                    })}
                  </Space>
                ) : (
                  <Text type="secondary">{t('detail.diagnostics.emptyDescription')}</Text>
                )}
              </div>
            ),
          },
        ]}
      />

      <EntityTable
        title={t('detail.tables.settlements.title')}
        extra={(
          <Space wrap>
            {focus === 'settlement' ? <StatusBadge status="active" label={t('common.runLinkedFocus')} /> : null}
            <RouteButton to={runWorkspaceHref}>{t('detail.tables.settlements.openLinkedRunContext')}</RouteButton>
          </Space>
        )}
        loading={loadingWorkspace}
        dataSource={settlements}
        columns={[
          {
            title: t('detail.tables.settlements.columns.batch'),
            dataIndex: 'id',
            key: 'id',
            render: (_: string, row: PoolBatch) => (
              <Space direction="vertical" size={4}>
                <Text>{row.source_reference || formatShortId(row.id)}</Text>
                <Text type="secondary">
                  {t('detail.tables.settlements.batchMeta', {
                    kind: row.batch_kind,
                    periodStart: formatters.date(row.period_start),
                  })}
                </Text>
                {row.run_id ? <Text type="secondary">{t('detail.tables.settlements.run', { value: formatShortId(row.run_id) })}</Text> : null}
                {runId && row.run_id === runId ? <Text type="secondary">{t('detail.tables.settlements.linkedFromRunReport')}</Text> : null}
              </Space>
            ),
          },
          {
            title: t('detail.tables.settlements.columns.status'),
            key: 'status',
            render: (_: unknown, row: PoolBatch) => (
              <StatusBadge
                status={getSettlementStatusTone(row.settlement?.status)}
                label={getPoolFactualSettlementStatusLabel(t, row.settlement?.status)}
              />
            ),
          },
          {
            title: t('detail.tables.settlements.columns.amounts'),
            key: 'amounts',
            render: (_: unknown, row: PoolBatch) => (
              <Space direction="vertical" size={4}>
                <Text>{t('page.list.compactMoneyLine', {
                  incoming: formatAmount(formatters, row.settlement?.incoming_amount),
                  outgoing: formatAmount(formatters, row.settlement?.outgoing_amount),
                  open: formatAmount(formatters, row.settlement?.open_balance),
                })}</Text>
              </Space>
            ),
          },
          {
            title: t('detail.tables.settlements.columns.carryForward'),
            key: 'carry_forward',
            render: (_: unknown, row: PoolBatch) => {
              const carryForward = getCarryForwardSummary(row)
              if (!carryForward) {
                return <Text type="secondary">{t('common.noValue')}</Text>
              }
              return (
                <Space direction="vertical" size={4}>
                  <Text>{t('common.targetQuarter', {
                    value: formatQuarterWindow(formatters, carryForward.targetQuarterStart, carryForward.targetQuarterEnd),
                  })}</Text>
                  <Text type="secondary">
                    {t('common.sourceTarget', {
                      source: formatShortId(carryForward.sourceSnapshotId),
                      target: formatShortId(carryForward.targetSnapshotId),
                    })}
                  </Text>
                  {carryForward.appliedAt ? (
                    <Text type="secondary">
                      {t('detail.tables.settlements.applied', {
                        value: formatTimestamp(formatters, carryForward.appliedAt),
                      })}
                    </Text>
                  ) : null}
                </Space>
              )
            },
          },
          {
            title: t('detail.tables.settlements.columns.freshness'),
            key: 'freshness',
            render: (_: unknown, row: PoolBatch) => (
              <Text type="secondary">{formatTimestamp(formatters, row.settlement?.freshness_at)}</Text>
            ),
          },
        ]}
        rowKey="id"
        emptyDescription={t('detail.tables.settlements.emptyDescription')}
      />

      <EntityTable
        title={t('detail.tables.edgeBalances.title')}
        extra={<RouteButton to={poolCatalogHref}>{t('detail.tables.edgeBalances.openTopologyContext')}</RouteButton>}
        loading={loadingWorkspace}
        dataSource={workspace?.edge_balances ?? []}
        columns={[
          {
            title: t('detail.tables.edgeBalances.columns.edge'),
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
            title: t('detail.tables.edgeBalances.columns.amounts'),
            key: 'amounts',
            render: (_: unknown, row: PoolFactualEdgeBalance) => (
              <Space direction="vertical" size={4}>
                <Text>{t('page.list.compactMoneyLine', {
                  incoming: formatAmount(formatters, row.incoming_amount),
                  outgoing: formatAmount(formatters, row.outgoing_amount),
                  open: formatAmount(formatters, row.open_balance),
                })}</Text>
              </Space>
            ),
          },
        ]}
        rowKey="id"
        emptyDescription={t('detail.tables.edgeBalances.emptyDescription')}
      />

      {reviewActionError ? (
        <Alert
          type="error"
          showIcon
          message={t('detail.reviewTable.failedTitle')}
          description={reviewActionError}
        />
      ) : null}

      <div id="pool-factual-review-queue">
        <EntityTable
          title={t('detail.reviewTable.title')}
          extra={focus === 'review' ? <StatusBadge status="active" label={t('common.reviewFocus')} /> : null}
          loading={loadingWorkspace}
          dataSource={reviewRows}
          columns={reviewColumns}
          rowKey="id"
          emptyDescription={t('detail.reviewTable.emptyDescription')}
        />
      </div>

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
