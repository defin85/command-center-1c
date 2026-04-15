import type { PoolWorkflowBinding } from '../../api/intercompanyPools'
import { translateNamespace } from '../../i18n'
import {
  resolvePoolWorkflowBindingDecisionRefs,
  resolvePoolWorkflowBindingWorkflow,
} from './poolWorkflowBindingPresentation'

export type TopologyCoverageContext = {
  status: 'resolved' | 'ambiguous' | 'unavailable'
  bindingLabel: string | null
  detail: string
  source: 'selected' | 'auto' | null
  slotRefs: Array<{
    slotKey: string
    refLabel: string
  }>
}

export type TopologySlotCoverage = {
  code?: string | null
  status: 'resolved' | 'missing_selector' | 'missing_slot' | 'ambiguous_slot' | 'ambiguous_context' | 'unavailable_context'
  label: string
  detail: string
}

export type TopologyEdgeSelector = {
  edgeId: string
  edgeLabel: string
  slotKey?: string
}

export type TopologyCoverageSummary = {
  totalEdges: number
  counts: Record<TopologySlotCoverage['status'], number>
  items: Array<{
    edgeId: string
    edgeLabel: string
    slotKey: string
    coverage: TopologySlotCoverage
  }>
}

export const describePoolWorkflowBindingCoverage = (binding: PoolWorkflowBinding): string => {
  const bindingId = String(binding.binding_id || '').trim()
  const workflowName = String(resolvePoolWorkflowBindingWorkflow(binding)?.workflow_name || '').trim()
  const selectorParts = [
    String(binding.selector?.direction || '').trim(),
    String(binding.selector?.mode || '').trim(),
  ].filter((item) => item)
  const scope = selectorParts.join(' · ')
  return [
    bindingId || workflowName || translateNamespace('pools', 'common.topologyCoverage.bindingFallback'),
    workflowName && workflowName !== bindingId ? workflowName : '',
    scope,
  ]
    .filter((item) => item)
    .join(' · ')
}

export const buildTopologyCoverageContext = ({
  bindingLabel,
  detail,
  slotRefs,
  source,
}: {
  bindingLabel: string
  detail: string
  slotRefs: Array<{ slotKey: string; refLabel: string }>
  source: 'selected' | 'auto'
}): TopologyCoverageContext => ({
  status: 'resolved',
  bindingLabel,
  detail,
  source,
  slotRefs,
})

const buildSlotRefsFromBinding = (
  binding: PoolWorkflowBinding
): Array<{ slotKey: string; refLabel: string }> => (
  resolvePoolWorkflowBindingDecisionRefs(binding)
    .map((decision) => ({
      slotKey: String(decision.slot_key || decision.decision_key || '').trim(),
      refLabel: `${decision.decision_table_id} (${decision.decision_key}) r${decision.decision_revision}`,
    }))
    .filter((slotRef) => slotRef.slotKey && slotRef.refLabel)
)

export const resolveTopologyCoverageContext = (
  bindings: PoolWorkflowBinding[],
  selectedBindingId: string | undefined
): TopologyCoverageContext => {
  const normalizedSelection = String(selectedBindingId || '').trim()
  const activeBindings = bindings.filter((binding) => binding.status === 'active')
  if (normalizedSelection) {
    const selectedBinding = activeBindings.find((binding) => binding.binding_id === normalizedSelection)
    if (selectedBinding) {
      const bindingLabel = describePoolWorkflowBindingCoverage(selectedBinding)
      return buildTopologyCoverageContext({
        bindingLabel,
        detail: translateNamespace('pools', 'common.topologyCoverage.selectedBinding', { bindingLabel }),
        slotRefs: buildSlotRefsFromBinding(selectedBinding),
        source: 'selected',
      })
    }
    return {
      status: 'unavailable',
      bindingLabel: null,
      detail: translateNamespace('pools', 'common.topologyCoverage.selectedBindingUnavailable'),
      source: null,
      slotRefs: [],
    }
  }
  if (activeBindings.length === 1) {
    const activeBinding = activeBindings[0]
    const bindingLabel = describePoolWorkflowBindingCoverage(activeBinding)
    return buildTopologyCoverageContext({
      bindingLabel,
      detail: translateNamespace('pools', 'common.topologyCoverage.autoResolved', { bindingLabel }),
      slotRefs: buildSlotRefsFromBinding(activeBinding),
      source: 'auto',
    })
  }
  if (activeBindings.length === 0) {
    return {
      status: 'unavailable',
      bindingLabel: null,
      detail: translateNamespace('pools', 'common.topologyCoverage.noActiveBindings'),
      source: null,
      slotRefs: [],
    }
  }
  return {
    status: 'ambiguous',
    bindingLabel: null,
    detail: translateNamespace('pools', 'common.topologyCoverage.ambiguousContext'),
    source: null,
    slotRefs: [],
  }
}

export const resolveTopologySlotCoverage = (
  slotKey: string | undefined,
  context: TopologyCoverageContext
): TopologySlotCoverage => {
  const normalizedSlotKey = String(slotKey || '').trim()
  if (!normalizedSlotKey) {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING',
      status: 'missing_selector',
      label: translateNamespace('pools', 'common.topologyCoverage.slotRequired'),
      detail: translateNamespace('pools', 'common.topologyCoverage.slotRequiredDetail'),
    }
  }
  if (context.status === 'ambiguous') {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS',
      status: 'ambiguous_context',
      label: translateNamespace('pools', 'common.topologyCoverage.coverageUnavailable'),
      detail: context.detail,
    }
  }
  if (context.status === 'unavailable' || !context.bindingLabel) {
    return {
      code: null,
      status: 'unavailable_context',
      label: translateNamespace('pools', 'common.topologyCoverage.coverageUnavailable'),
      detail: context.detail,
    }
  }
  const matches = context.slotRefs.filter((slotRef) => slotRef.slotKey === normalizedSlotKey)
  if (matches.length === 0) {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND',
      status: 'missing_slot',
      label: translateNamespace('pools', 'common.topologyCoverage.slotMissing'),
      detail: translateNamespace('pools', 'common.topologyCoverage.slotMissingDetail', {
        bindingLabel: context.bindingLabel,
        slotKey: normalizedSlotKey,
      }),
    }
  }
  if (matches.length > 1) {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS',
      status: 'ambiguous_slot',
      label: translateNamespace('pools', 'common.topologyCoverage.ambiguousSlot'),
      detail: translateNamespace('pools', 'common.topologyCoverage.ambiguousSlotDetail', {
        bindingLabel: context.bindingLabel,
        count: matches.length,
        slotKey: normalizedSlotKey,
      }),
    }
  }
  return {
    code: null,
    status: 'resolved',
    label: translateNamespace('pools', 'common.topologyCoverage.resolved'),
    detail: translateNamespace('pools', 'common.topologyCoverage.resolvedDetail', {
      bindingLabel: context.bindingLabel,
      refLabel: matches[0]?.refLabel || normalizedSlotKey,
    }),
  }
}

export const summarizeTopologySlotCoverage = (
  selectors: TopologyEdgeSelector[],
  context: TopologyCoverageContext
): TopologyCoverageSummary => {
  const counts: TopologyCoverageSummary['counts'] = {
    resolved: 0,
    missing_selector: 0,
    missing_slot: 0,
    ambiguous_slot: 0,
    ambiguous_context: 0,
    unavailable_context: 0,
  }
  const items = selectors.map((selector) => {
    const slotKey = String(selector.slotKey || '').trim()
    const coverage = resolveTopologySlotCoverage(slotKey, context)
    counts[coverage.status] += 1
    return {
      edgeId: selector.edgeId,
      edgeLabel: selector.edgeLabel,
      slotKey,
      coverage,
    }
  })
  return {
    totalEdges: selectors.length,
    counts,
    items,
  }
}
