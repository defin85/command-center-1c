import type { PoolFactualSummary } from '../../api/intercompanyPools'

export type PoolFactualVerdict = 'critical' | 'warning' | 'healthy' | 'unknown'

export const resolvePoolFactualVerdict = (
  summary: PoolFactualSummary | null | undefined
): PoolFactualVerdict => {
  if (!summary) {
    return 'unknown'
  }
  if (
    summary.source_availability !== 'available'
    || summary.sync_status === 'failed'
    || summary.checkpoints_failed > 0
  ) {
    return 'critical'
  }
  if (
    summary.freshness_state === 'stale'
    || summary.backlog_total > 0
    || summary.attention_required_total > 0
    || summary.pending_review_total > 0
  ) {
    return 'warning'
  }
  if (summary.last_synced_at) {
    return 'healthy'
  }
  return 'unknown'
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
  if (!summary) {
    return 'Factual state will appear after the workspace payload loads.'
  }
  if (summary.source_availability !== 'available') {
    return summary.source_availability_detail || `Source availability is ${summary.source_availability}.`
  }
  if (summary.checkpoints_failed > 0 || summary.sync_status === 'failed') {
    return `${summary.checkpoints_failed} failed checkpoint(s) are blocking a healthy factual projection.`
  }
  if (summary.attention_required_total > 0) {
    return `${summary.attention_required_total} settlement or review item(s) require manual intervention.`
  }
  if (summary.pending_review_total > 0) {
    return `${summary.pending_review_total} review item(s) are still waiting in the queue.`
  }
  if (summary.backlog_total > 0) {
    return `${summary.backlog_total} overdue checkpoint(s) are keeping the read model behind.`
  }
  if (summary.freshness_state === 'stale') {
    return 'The factual read model is stale for the selected quarter.'
  }
  if (summary.last_synced_at) {
    return 'Data is fresh and no manual intervention is currently required.'
  }
  return 'No successful sync has been recorded for this workspace yet.'
}

export const getPoolFactualCompactSummary = (
  summary: PoolFactualSummary | null | undefined
): string => {
  const verdict = resolvePoolFactualVerdict(summary)
  if (!summary) {
    return 'Awaiting factual data'
  }
  if (verdict === 'critical') {
    if (summary.source_availability !== 'available') {
      return 'Source unavailable'
    }
    return `${summary.checkpoints_failed} failed sync checkpoint(s)`
  }
  if (verdict === 'warning') {
    if (summary.attention_required_total > 0) {
      return `${summary.attention_required_total} attention required`
    }
    if (summary.pending_review_total > 0) {
      return `${summary.pending_review_total} pending review item(s)`
    }
    if (summary.backlog_total > 0) {
      return `${summary.backlog_total} overdue checkpoint(s)`
    }
    return 'Data is stale'
  }
  if (verdict === 'healthy') {
    return 'Data is fresh'
  }
  return 'Awaiting factual data'
}

export const getPoolFactualPrimaryActionLabel = (
  summary: PoolFactualSummary | null | undefined
): string => {
  if (!summary) {
    return 'Wait for factual data'
  }
  if (summary.source_availability !== 'available' || summary.checkpoints_failed > 0 || summary.sync_status === 'failed') {
    return 'Open sync diagnostics'
  }
  if (summary.attention_required_total > 0 || summary.pending_review_total > 0) {
    return 'Open manual review queue'
  }
  if (summary.backlog_total > 0 || summary.freshness_state === 'stale') {
    return 'Open freshness details'
  }
  return 'Open settlement handoff'
}
