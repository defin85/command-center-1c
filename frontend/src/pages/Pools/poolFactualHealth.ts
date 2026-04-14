import type { TFunction } from 'i18next'

import type { PoolFactualSummary } from '../../api/intercompanyPools'

export type PoolFactualVerdict = 'critical' | 'warning' | 'healthy' | 'unknown'
export type PoolFactualPrioritySignal =
  | 'source_unavailable'
  | 'sync_failed'
  | 'checkpoint_failed'
  | 'stale'
  | 'backlog'
  | 'attention_required'
  | 'pending_review'
  | 'healthy'
  | 'unsynced'
  | 'unknown'

export const resolvePoolFactualPrioritySignal = (
  summary: PoolFactualSummary | null | undefined
): PoolFactualPrioritySignal => {
  if (!summary) {
    return 'unknown'
  }
  if (summary.source_availability !== 'available') {
    return 'source_unavailable'
  }
  if (summary.sync_status === 'failed') {
    return 'sync_failed'
  }
  if (summary.checkpoints_failed > 0) {
    return 'checkpoint_failed'
  }
  if (summary.freshness_state === 'stale') {
    return 'stale'
  }
  if (summary.backlog_total > 0) {
    return 'backlog'
  }
  if (summary.attention_required_total > 0) {
    return 'attention_required'
  }
  if (summary.pending_review_total > 0) {
    return 'pending_review'
  }
  if (summary.last_synced_at) {
    return 'healthy'
  }
  return 'unsynced'
}

export const resolvePoolFactualVerdict = (
  summary: PoolFactualSummary | null | undefined
): PoolFactualVerdict => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'source_unavailable':
    case 'sync_failed':
    case 'checkpoint_failed':
      return 'critical'
    case 'stale':
    case 'backlog':
    case 'attention_required':
    case 'pending_review':
      return 'warning'
    case 'healthy':
      return 'healthy'
    default:
      return 'unknown'
  }
}

export const getPoolFactualVerdictPriority = (
  verdict: PoolFactualVerdict
): number => {
  switch (verdict) {
    case 'critical':
      return 0
    case 'warning':
      return 1
    case 'healthy':
      return 2
    default:
      return 3
  }
}

export const getPoolFactualVerdictTone = (verdict: PoolFactualVerdict) => {
  switch (verdict) {
    case 'critical':
      return 'error'
    case 'warning':
      return 'warning'
    case 'healthy':
      return 'active'
    default:
      return 'unknown'
  }
}

export const getPoolFactualVerdictLabel = (
  t: TFunction<'poolFactual', undefined>,
  verdict: PoolFactualVerdict,
) => {
  switch (verdict) {
    case 'critical':
      return t('health.verdicts.critical')
    case 'warning':
      return t('health.verdicts.warning')
    case 'healthy':
      return t('health.verdicts.healthy')
    default:
      return t('health.verdicts.unknown')
  }
}

export const getPoolFactualPrimaryReason = (
  t: TFunction<'poolFactual', undefined>,
  summary: PoolFactualSummary | null | undefined
): string => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'unknown':
      return t('health.primaryReasons.unknown')
    case 'source_unavailable':
      return summary?.source_availability_detail || t('health.primaryReasons.sourceUnavailable', {
        value: summary?.source_availability || t('common.unknown'),
      })
    case 'sync_failed':
      return t('health.primaryReasons.syncFailed')
    case 'checkpoint_failed':
      return t('health.primaryReasons.checkpointFailed', {
        count: summary?.checkpoints_failed ?? 0,
      })
    case 'stale':
      return t('health.primaryReasons.stale')
    case 'backlog':
      return t('health.primaryReasons.backlog', {
        count: summary?.backlog_total ?? 0,
      })
    case 'attention_required':
      return t('health.primaryReasons.attentionRequired', {
        count: summary?.attention_required_total ?? 0,
      })
    case 'pending_review':
      return t('health.primaryReasons.pendingReview', {
        count: summary?.pending_review_total ?? 0,
      })
    case 'healthy':
      return t('health.primaryReasons.healthy')
    default:
      return t('health.primaryReasons.unsynced')
  }
}

export const getPoolFactualCompactSummary = (
  t: TFunction<'poolFactual', undefined>,
  summary: PoolFactualSummary | null | undefined
): string => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'source_unavailable':
      return t('health.compactSummary.sourceUnavailable')
    case 'sync_failed':
      return t('health.compactSummary.syncFailed')
    case 'checkpoint_failed':
      return t('health.compactSummary.checkpointFailed', {
        count: summary?.checkpoints_failed ?? 0,
      })
    case 'stale':
      return t('health.compactSummary.stale')
    case 'backlog':
      return t('health.compactSummary.backlog', {
        count: summary?.backlog_total ?? 0,
      })
    case 'attention_required':
      return t('health.compactSummary.attentionRequired', {
        count: summary?.attention_required_total ?? 0,
      })
    case 'pending_review':
      return t('health.compactSummary.pendingReview', {
        count: summary?.pending_review_total ?? 0,
      })
    case 'healthy':
      return t('health.compactSummary.healthy')
    default:
      return t('health.compactSummary.unknown')
  }
}

export const getPoolFactualPrimaryActionLabel = (
  t: TFunction<'poolFactual', undefined>,
  summary: PoolFactualSummary | null | undefined
): string => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'source_unavailable':
    case 'sync_failed':
    case 'checkpoint_failed':
      return t('health.primaryActions.diagnostics')
    case 'stale':
    case 'backlog':
      return t('health.primaryActions.freshness')
    case 'attention_required':
    case 'pending_review':
      return t('health.primaryActions.review')
    case 'healthy':
    case 'unsynced':
      return t('health.primaryActions.settlement')
    default:
      return t('health.primaryActions.wait')
  }
}

export const getPoolFactualSyncStatusLabel = (
  t: TFunction<'poolFactual', undefined>,
  status: string | null | undefined,
): string => {
  switch (status?.trim()) {
    case 'running':
      return t('statuses.running')
    case 'pending':
      return t('statuses.pending')
    case 'failed':
      return t('statuses.failed')
    case 'success':
      return t('statuses.success')
    case '':
    case undefined:
    case null:
      return t('statuses.ready')
    default:
      return status?.trim() || t('common.unknown')
  }
}

export const getPoolFactualFreshnessStatusLabel = (
  t: TFunction<'poolFactual', undefined>,
  status: string | null | undefined,
): string => {
  switch (status?.trim()) {
    case 'fresh':
      return t('statuses.fresh')
    case 'stale':
      return t('statuses.stale')
    default:
      return status?.trim() || t('common.notConnected')
  }
}

export const getPoolFactualAvailabilityLabel = (
  t: TFunction<'poolFactual', undefined>,
  status: string | null | undefined,
): string => {
  switch (status?.trim()) {
    case 'available':
      return t('statuses.available')
    case 'unavailable':
      return t('statuses.unavailable')
    default:
      return status?.trim() || t('common.unknown')
  }
}

export const getPoolFactualSettlementStatusLabel = (
  t: TFunction<'poolFactual', undefined>,
  status: string | null | undefined,
): string => {
  switch (status?.trim()) {
    case 'closed':
      return t('statuses.closed')
    case 'attention_required':
      return t('statuses.attentionRequired')
    case 'partially_closed':
      return t('statuses.partiallyClosed')
    case 'carried_forward':
      return t('statuses.carriedForward')
    case 'distributed':
      return t('statuses.distributed')
    case 'pending':
      return t('statuses.pending')
    default:
      return status?.trim() || t('common.unknown')
  }
}
