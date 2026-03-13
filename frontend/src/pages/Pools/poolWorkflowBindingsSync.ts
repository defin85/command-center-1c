import {
  replacePoolWorkflowBindingsCollection,
  type PoolWorkflowBinding,
  type PoolWorkflowBindingCollection,
  type PoolWorkflowBindingInput,
} from '../../api/intercompanyPools'

type NormalizedDecisionRef = {
  decision_table_id: string
  decision_key: string
  decision_revision: number
}

const normalizeBindingForComparison = (binding: PoolWorkflowBinding | PoolWorkflowBindingInput) => ({
  contract_version: String(binding.contract_version ?? '').trim() || 'pool_workflow_binding.v1',
  binding_id: String(binding.binding_id ?? '').trim(),
  status: String(binding.status ?? '').trim(),
  effective_from: String(binding.effective_from ?? '').trim(),
  effective_to: binding.effective_to ? String(binding.effective_to).trim() : null,
  selector: {
    direction: String(binding.selector?.direction ?? '').trim(),
    mode: String(binding.selector?.mode ?? '').trim(),
    tags: Array.from(new Set((binding.selector?.tags ?? []).map((tag) => String(tag).trim()).filter(Boolean))).sort(),
  },
  workflow: {
    workflow_definition_key: String(binding.workflow?.workflow_definition_key ?? '').trim(),
    workflow_revision_id: String(binding.workflow?.workflow_revision_id ?? '').trim(),
    workflow_revision: Number(binding.workflow?.workflow_revision ?? 0),
    workflow_name: String(binding.workflow?.workflow_name ?? '').trim(),
  },
  decisions: (binding.decisions ?? [])
    .map((decision) => ({
      decision_table_id: String(decision.decision_table_id ?? '').trim(),
      decision_key: String(decision.decision_key ?? '').trim(),
      decision_revision: Number(decision.decision_revision ?? 0),
    }) satisfies NormalizedDecisionRef)
    .sort((left, right) => (
      left.decision_table_id.localeCompare(right.decision_table_id)
      || left.decision_key.localeCompare(right.decision_key)
      || left.decision_revision - right.decision_revision
    )),
  parameters: Object.fromEntries(
    (Object.entries(binding.parameters ?? {}) as Array<[string, unknown]>)
      .map(([key, value]): [string, unknown] => [String(key).trim(), value])
      .sort(([left], [right]) => left.localeCompare(right))
  ),
  role_mapping: Object.fromEntries(
    (Object.entries(binding.role_mapping ?? {}) as Array<[string, string]>)
      .map(([key, value]): [string, string] => [String(key).trim(), String(value ?? '').trim()])
      .sort(([left], [right]) => left.localeCompare(right))
  ),
})

const areBindingsEquivalent = (
  left: PoolWorkflowBinding,
  right: PoolWorkflowBinding | PoolWorkflowBindingInput,
) => (
  JSON.stringify(normalizeBindingForComparison(left)) === JSON.stringify(normalizeBindingForComparison(right))
)

export function hasWorkflowBindingChanges({
  previousBindings,
  nextBindings,
}: {
  previousBindings: PoolWorkflowBinding[]
  nextBindings: PoolWorkflowBindingInput[]
}) {
  if (previousBindings.length !== nextBindings.length) {
    return true
  }

  const previousById = new Map(
    previousBindings
      .map((binding) => [String(binding.binding_id ?? '').trim(), binding] as const)
      .filter(([bindingId]) => bindingId.length > 0)
  )

  for (const binding of nextBindings) {
    const bindingId = String(binding.binding_id ?? '').trim()
    if (!bindingId) {
      return true
    }
    const previousBinding = previousById.get(bindingId)
    if (!previousBinding || !areBindingsEquivalent(previousBinding, binding)) {
      return true
    }
  }

  return false
}

export async function syncPoolWorkflowBindings({
  poolId,
  collectionEtag,
  nextBindings,
}: {
  poolId: string
  collectionEtag: string
  nextBindings: PoolWorkflowBindingInput[]
}): Promise<PoolWorkflowBindingCollection> {
  const normalizedCollectionEtag = String(collectionEtag ?? '').trim()
  if (!normalizedCollectionEtag) {
    throw new Error('collectionEtag is required for atomic workflow binding save.')
  }

  return replacePoolWorkflowBindingsCollection({
    pool_id: poolId,
    expected_collection_etag: normalizedCollectionEtag,
    workflow_bindings: nextBindings,
  })
}
