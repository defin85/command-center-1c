import {
  replacePoolWorkflowBindingsCollection,
  type PoolWorkflowBinding,
  type PoolWorkflowBindingCollection,
  type PoolWorkflowBindingInput,
} from '../../api/intercompanyPools'
const normalizeBindingForComparison = (binding: PoolWorkflowBinding | PoolWorkflowBindingInput) => ({
  contract_version: String(binding.contract_version ?? '').trim() || 'pool_workflow_binding.v1',
  binding_id: String(binding.binding_id ?? '').trim(),
  binding_profile_revision_id: String(
    ('binding_profile_revision_id' in binding
      ? binding.binding_profile_revision_id
      : undefined)
    ?? ('resolved_profile' in binding ? binding.resolved_profile?.binding_profile_revision_id : undefined)
    ?? ''
  ).trim(),
  status: String(binding.status ?? '').trim(),
  effective_from: String(binding.effective_from ?? '').trim(),
  effective_to: binding.effective_to ? String(binding.effective_to).trim() : null,
  selector: {
    direction: String(binding.selector?.direction ?? '').trim(),
    mode: String(binding.selector?.mode ?? '').trim(),
    tags: Array.from(new Set((binding.selector?.tags ?? []).map((tag) => String(tag).trim()).filter(Boolean))).sort(),
  },
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
