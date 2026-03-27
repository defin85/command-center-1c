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

const PENDING_ACTIONS_BY_REASON: Record<PoolFactualReviewReason, PoolFactualReviewAction[]> = {
  unattributed: ['attribute', 'resolve_without_change'],
  late_correction: ['reconcile', 'resolve_without_change'],
}

const STATUS_BY_ACTION: Record<PoolFactualReviewAction, PoolFactualReviewStatus> = {
  attribute: 'attributed',
  reconcile: 'reconciled',
  resolve_without_change: 'resolved_without_change',
}

export function buildDemoPoolFactualReviewQueue(poolCode: string): PoolFactualReviewRow[] {
  const normalizedPoolCode = poolCode.trim() || 'pool'
  return [
    {
      id: `unattributed-${normalizedPoolCode}`,
      reason: 'unattributed',
      status: 'pending',
      quarter: '2026Q1',
      sourceDocumentRef: `Document_РеализацияТоваровУслуг(guid'${normalizedPoolCode}-sale')`,
      summary: 'Manual sale without CCPOOL marker; operator must attribute it before edge-level settlement closes.',
      attentionRequired: false,
      allowedActions: [...PENDING_ACTIONS_BY_REASON.unattributed],
    },
    {
      id: `late-correction-${normalizedPoolCode}`,
      reason: 'late_correction',
      status: 'pending',
      quarter: '2026Q1',
      sourceDocumentRef: `Document_КорректировкаРеализации(guid'${normalizedPoolCode}-late')`,
      summary: 'Frozen quarter delta detected after carry-forward; operator must reconcile the historical correction manually.',
      attentionRequired: true,
      allowedActions: [...PENDING_ACTIONS_BY_REASON.late_correction],
    },
  ]
}

export function applyPoolFactualReviewAction(
  rows: PoolFactualReviewRow[],
  itemId: string,
  action: PoolFactualReviewAction
): PoolFactualReviewRow[] {
  return rows.map((row) => {
    if (row.id !== itemId) {
      return row
    }
    if (!row.allowedActions.includes(action)) {
      return row
    }
    return {
      ...row,
      status: STATUS_BY_ACTION[action],
      allowedActions: [],
      attentionRequired: false,
    }
  })
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
