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

export const getPoolFactualVerdictLabel = (verdict: PoolFactualVerdict) => {
  switch (verdict) {
    case 'critical':
      return 'Critical issue'
    case 'warning':
      return 'Needs attention'
    case 'healthy':
      return 'Healthy'
    default:
      return 'Awaiting data'
  }
}

export const getPoolFactualPrimaryReason = (
  summary: PoolFactualSummary | null | undefined
): string => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'unknown':
      return 'Factual state will appear after the workspace payload loads.'
    case 'source_unavailable':
      return summary?.source_availability_detail || `Source availability is ${summary?.source_availability}.`
    case 'sync_failed':
      return 'The factual sync lane failed for the selected quarter.'
    case 'checkpoint_failed':
      return `${summary?.checkpoints_failed ?? 0} failed checkpoint(s) are blocking a healthy factual projection.`
    case 'stale':
      return 'The factual read model is stale for the selected quarter.'
    case 'backlog':
      return `${summary?.backlog_total ?? 0} overdue checkpoint(s) are keeping the read model behind.`
    case 'attention_required':
      return `${summary?.attention_required_total ?? 0} settlement or review item(s) require manual intervention.`
    case 'pending_review':
      return `${summary?.pending_review_total ?? 0} review item(s) are still waiting in the queue.`
    case 'healthy':
      return 'Data is fresh and no manual intervention is currently required.'
    default:
      return 'No successful sync has been recorded for this workspace yet.'
  }
}

export const getPoolFactualCompactSummary = (
  summary: PoolFactualSummary | null | undefined
): string => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'source_unavailable':
      return 'Source unavailable'
    case 'sync_failed':
      return 'Sync failed'
    case 'checkpoint_failed':
      return `${summary?.checkpoints_failed ?? 0} failed sync checkpoint(s)`
    case 'stale':
      return 'Data is stale'
    case 'backlog':
      return `${summary?.backlog_total ?? 0} overdue checkpoint(s)`
    case 'attention_required':
      return `${summary?.attention_required_total ?? 0} attention required`
    case 'pending_review':
      return `${summary?.pending_review_total ?? 0} pending review item(s)`
    case 'healthy':
      return 'Data is fresh'
    default:
      return 'Awaiting factual data'
  }
}

export const getPoolFactualPrimaryActionLabel = (
  summary: PoolFactualSummary | null | undefined
): string => {
  switch (resolvePoolFactualPrioritySignal(summary)) {
    case 'source_unavailable':
    case 'sync_failed':
    case 'checkpoint_failed':
      return 'Open sync diagnostics'
    case 'stale':
    case 'backlog':
      return 'Open freshness details'
    case 'attention_required':
    case 'pending_review':
      return 'Open manual review queue'
    case 'healthy':
    case 'unsynced':
      return 'Open settlement handoff'
    default:
      return 'Wait for factual data'
  }
}
