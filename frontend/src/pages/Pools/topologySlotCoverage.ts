import type { PoolWorkflowBinding } from '../../api/intercompanyPools'
import { i18n } from '../../i18n'
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
    bindingId || workflowName || i18n.t('common.topologyCoverage.bindingFallback', { ns: 'pools' }),
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
        detail: i18n.t('common.topologyCoverage.selectedBinding', { ns: 'pools', bindingLabel }),
        slotRefs: buildSlotRefsFromBinding(selectedBinding),
        source: 'selected',
      })
    }
    return {
      status: 'unavailable',
      bindingLabel: null,
      detail: i18n.t('common.topologyCoverage.selectedBindingUnavailable', { ns: 'pools' }),
      source: null,
      slotRefs: [],
    }
  }
  if (activeBindings.length === 1) {
    const activeBinding = activeBindings[0]
    const bindingLabel = describePoolWorkflowBindingCoverage(activeBinding)
    return buildTopologyCoverageContext({
      bindingLabel,
      detail: i18n.t('common.topologyCoverage.autoResolved', { ns: 'pools', bindingLabel }),
      slotRefs: buildSlotRefsFromBinding(activeBinding),
      source: 'auto',
    })
  }
  if (activeBindings.length === 0) {
    return {
      status: 'unavailable',
      bindingLabel: null,
      detail: i18n.t('common.topologyCoverage.noActiveBindings', { ns: 'pools' }),
      source: null,
      slotRefs: [],
    }
  }
  return {
    status: 'ambiguous',
    bindingLabel: null,
    detail: i18n.t('common.topologyCoverage.ambiguousContext', { ns: 'pools' }),
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
      label: i18n.t('common.topologyCoverage.slotRequired', { ns: 'pools' }),
      detail: i18n.t('common.topologyCoverage.slotRequiredDetail', { ns: 'pools' }),
    }
  }
  if (context.status === 'ambiguous') {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS',
      status: 'ambiguous_context',
      label: i18n.t('common.topologyCoverage.coverageUnavailable', { ns: 'pools' }),
      detail: context.detail,
    }
  }
  if (context.status === 'unavailable' || !context.bindingLabel) {
    return {
      code: null,
      status: 'unavailable_context',
      label: i18n.t('common.topologyCoverage.coverageUnavailable', { ns: 'pools' }),
      detail: context.detail,
    }
  }
  const matches = context.slotRefs.filter((slotRef) => slotRef.slotKey === normalizedSlotKey)
  if (matches.length === 0) {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND',
      status: 'missing_slot',
      label: i18n.t('common.topologyCoverage.slotMissing', { ns: 'pools' }),
      detail: i18n.t('common.topologyCoverage.slotMissingDetail', {
        ns: 'pools',
        bindingLabel: context.bindingLabel,
        slotKey: normalizedSlotKey,
      }),
    }
  }
  if (matches.length > 1) {
    return {
      code: 'POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS',
      status: 'ambiguous_slot',
      label: i18n.t('common.topologyCoverage.ambiguousSlot', { ns: 'pools' }),
      detail: i18n.t('common.topologyCoverage.ambiguousSlotDetail', {
        ns: 'pools',
        bindingLabel: context.bindingLabel,
        count: matches.length,
        slotKey: normalizedSlotKey,
      }),
    }
  }
  return {
    code: null,
    status: 'resolved',
    label: i18n.t('common.topologyCoverage.resolved', { ns: 'pools' }),
    detail: i18n.t('common.topologyCoverage.resolvedDetail', {
      ns: 'pools',
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
