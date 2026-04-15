import type { AppStringTranslator } from '../../i18n'

export type PoolFactualReviewReason = 'unattributed' | 'late_correction'
export type PoolFactualReviewStatus = 'pending' | 'attributed' | 'reconciled' | 'resolved_without_change'
export type PoolFactualReviewAction = 'attribute' | 'reconcile' | 'resolve_without_change'

export type PoolFactualReviewRow = {
  id: string
  reason: PoolFactualReviewReason
  status: PoolFactualReviewStatus
  quarter: string
  sourceDocumentRef: string
  summary: string
  attentionRequired: boolean
  allowedActions: PoolFactualReviewAction[]
}

export function getPoolFactualReviewStatusTone(row: PoolFactualReviewRow): string {
  if (row.status === 'pending') {
    return row.reason === 'late_correction' ? 'error' : 'warning'
  }
  return 'active'
}

export function getPoolFactualReviewReasonLabel(
  t: AppStringTranslator,
  reason: PoolFactualReviewReason,
): string {
  return reason === 'late_correction'
    ? t('review.reasons.lateCorrection')
    : t('review.reasons.unattributed')
}

export function getPoolFactualReviewStatusLabel(
  t: AppStringTranslator,
  status: PoolFactualReviewStatus,
): string {
  switch (status) {
    case 'attributed':
      return t('statuses.attributed')
    case 'reconciled':
      return t('statuses.reconciled')
    case 'resolved_without_change':
      return t('statuses.resolvedWithoutChange')
    default:
      return t('statuses.pending')
  }
}

export function getPoolFactualReviewActionLabel(
  t: AppStringTranslator,
  action: PoolFactualReviewAction,
): string {
  switch (action) {
    case 'attribute':
      return t('review.actions.attribute')
    case 'reconcile':
      return t('review.actions.reconcile')
    case 'resolve_without_change':
      return t('review.actions.resolveWithoutChange')
  }
}
