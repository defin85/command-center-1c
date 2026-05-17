import type { PoolWorkflowBinding } from '../../../api/intercompanyPools'

export const SCHEMA_TEMPLATE_UPLOAD_SOURCE_TYPE = 'schema_template_upload'
export const KVO17_GENERATED_PURCHASE_SOURCE_TYPE = 'kvo17_generated_purchase'

export type PoolBatchIntakeSourceMode =
  | typeof SCHEMA_TEMPLATE_UPLOAD_SOURCE_TYPE
  | typeof KVO17_GENERATED_PURCHASE_SOURCE_TYPE

export type SchemeIntakeBindingDiagnosticCode =
  | 'bindingMissing'
  | 'capabilityMissing'
  | 'sourceTypeMismatch'
  | 'slotMissing'
  | 'topologyNotReady'

export type SchemeIntakeBindingCapability = {
  available: boolean
  diagnostics: SchemeIntakeBindingDiagnosticCode[]
}

const KVO17_GENERATED_PURCHASE_REQUIRED_SLOTS = new Set([
  'kvo17_generated_purchase_pair',
])

export function resolveKvo17GeneratedPurchaseBindingCapability(
  binding: PoolWorkflowBinding | null | undefined,
): SchemeIntakeBindingCapability {
  const diagnostics: SchemeIntakeBindingDiagnosticCode[] = []

  if (!binding?.resolved_profile) {
    diagnostics.push('bindingMissing')
    return { available: false, diagnostics }
  }

  const parameters = binding.resolved_profile.parameters ?? {}
  if (parameters.generated_purchase_supported !== true) {
    diagnostics.push('capabilityMissing')
  }
  if (parameters.generated_purchase_source_type !== KVO17_GENERATED_PURCHASE_SOURCE_TYPE) {
    diagnostics.push('sourceTypeMismatch')
  }

  const slotKeys = new Set(
    (binding.resolved_profile.decisions ?? [])
      .map((decision) => String(decision.slot_key ?? '').trim())
      .filter(Boolean),
  )
  const missingSlot = Array.from(KVO17_GENERATED_PURCHASE_REQUIRED_SLOTS)
    .some((slotKey) => !slotKeys.has(slotKey))
  if (missingSlot) {
    diagnostics.push('slotMissing')
  }

  const topologyCompatibility = binding.resolved_profile.topology_template_compatibility
  if (
    topologyCompatibility
    && topologyCompatibility.topology_aware_ready !== true
  ) {
    diagnostics.push('topologyNotReady')
  }

  return {
    available: diagnostics.length === 0,
    diagnostics,
  }
}
