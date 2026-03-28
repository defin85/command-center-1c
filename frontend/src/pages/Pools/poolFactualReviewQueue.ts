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

export function getPoolFactualReviewReasonLabel(reason: PoolFactualReviewReason): string {
  return reason === 'late_correction' ? 'late correction' : 'unattributed'
}

export function getPoolFactualReviewActionLabel(action: PoolFactualReviewAction): string {
  switch (action) {
    case 'attribute':
      return 'Attribute'
    case 'reconcile':
      return 'Reconcile'
    case 'resolve_without_change':
      return 'Resolve w/o change'
  }
}
