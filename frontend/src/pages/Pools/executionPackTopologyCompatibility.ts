export type ExecutionPackTopologyCompatibilityDiagnosticLike = {
  code?: string | null
  slot_key?: string | null
  decision_table_id?: string | null
  decision_revision?: number | null
  field_or_table_path?: string | null
  detail?: string | null
}

export type ExecutionPackTopologyCompatibilitySummaryLike = {
  status?: string | null
  topology_aware_ready?: boolean | null
  covered_slot_keys?: string[] | null
  diagnostics?: ExecutionPackTopologyCompatibilityDiagnosticLike[] | null
}

const joinNonEmpty = (values: Array<string | null | undefined>, separator: string) => (
  values
    .map((value) => String(value ?? '').trim())
    .filter(Boolean)
    .join(separator)
)

export const formatExecutionPackTopologyDiagnostic = (
  diagnostic: ExecutionPackTopologyCompatibilityDiagnosticLike,
): string => {
  const location = joinNonEmpty(
    [
      diagnostic.slot_key ? `slot ${diagnostic.slot_key}` : null,
      diagnostic.decision_table_id
        ? `${diagnostic.decision_table_id}${diagnostic.decision_revision ? ` r${diagnostic.decision_revision}` : ''}`
        : null,
      diagnostic.field_or_table_path,
    ],
    ' · ',
  )
  return joinNonEmpty([location || null, diagnostic.detail || null], ' — ')
}

export const describeExecutionPackTopologyCompatibility = (
  summary: ExecutionPackTopologyCompatibilitySummaryLike | null | undefined,
): {
  statusText: string
  alertType: 'success' | 'warning' | 'info'
  message: string
  coveredSlotsText: string
  diagnostics: string[]
} => {
  const coveredSlots = Array.isArray(summary?.covered_slot_keys) ? summary.covered_slot_keys.filter(Boolean) : []
  const diagnostics = Array.isArray(summary?.diagnostics)
    ? summary.diagnostics.map(formatExecutionPackTopologyDiagnostic).filter(Boolean)
    : []

  if (!summary) {
    return {
      statusText: 'not available',
      alertType: 'info',
      message: 'Template topology compatibility is not available for this execution pack.',
      coveredSlotsText: '-',
      diagnostics: [],
    }
  }

  if (String(summary.status).trim() === 'compatible' && summary.topology_aware_ready) {
    return {
      statusText: 'compatible',
      alertType: 'success',
      message: 'Template topology compatibility is ready.',
      coveredSlotsText: coveredSlots.length > 0 ? coveredSlots.join(', ') : '-',
      diagnostics: [],
    }
  }

  return {
    statusText: 'incompatible',
    alertType: 'warning',
    message: 'Template topology compatibility is blocked until reusable decisions use topology-aware aliases.',
    coveredSlotsText: coveredSlots.length > 0 ? coveredSlots.join(', ') : '-',
    diagnostics,
  }
}
