import {
  deletePoolWorkflowBinding,
  upsertPoolWorkflowBinding,
  type PoolWorkflowBinding,
} from '../../api/intercompanyPools'

export async function syncPoolWorkflowBindings({
  poolId,
  previousBindings,
  nextBindings,
}: {
  poolId: string
  previousBindings: PoolWorkflowBinding[]
  nextBindings: PoolWorkflowBinding[]
}) {
  const retainedBindingIds = new Set(
    nextBindings
      .map((binding) => String(binding.binding_id ?? '').trim())
      .filter(Boolean)
  )

  for (const binding of nextBindings) {
    await upsertPoolWorkflowBinding({
      pool_id: poolId,
      workflow_binding: binding,
    })
  }

  for (const binding of previousBindings) {
    const bindingId = String(binding.binding_id ?? '').trim()
    const revision = Number(binding.revision)
    if (!bindingId || retainedBindingIds.has(bindingId)) {
      continue
    }
    if (!Number.isInteger(revision) || revision <= 0) {
      throw new Error(`Binding ${bindingId} is missing revision and cannot be deleted safely.`)
    }
    await deletePoolWorkflowBinding(poolId, bindingId, revision)
  }
}
