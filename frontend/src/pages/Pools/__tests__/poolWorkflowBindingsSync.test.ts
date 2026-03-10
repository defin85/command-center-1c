import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PoolWorkflowBinding } from '../../../api/intercompanyPools'
import { syncPoolWorkflowBindings } from '../poolWorkflowBindingsSync'

const mockDeletePoolWorkflowBinding = vi.fn()
const mockUpsertPoolWorkflowBinding = vi.fn()

vi.mock('../../../api/intercompanyPools', () => ({
  deletePoolWorkflowBinding: (...args: unknown[]) => mockDeletePoolWorkflowBinding(...args),
  upsertPoolWorkflowBinding: (...args: unknown[]) => mockUpsertPoolWorkflowBinding(...args),
}))

function buildBinding(overrides: Partial<PoolWorkflowBinding> = {}): PoolWorkflowBinding {
  return {
    binding_id: 'binding-existing',
    revision: 3,
    workflow: {
      workflow_definition_key: 'services-publication',
      workflow_revision_id: '11111111-1111-1111-1111-111111111111',
      workflow_revision: 5,
      workflow_name: 'services_publication',
    },
    selector: {
      direction: 'top_down',
      mode: 'safe',
      tags: ['baseline'],
    },
    effective_from: '2026-01-01',
    status: 'active',
    ...overrides,
  }
}

describe('syncPoolWorkflowBindings', () => {
  beforeEach(() => {
    mockDeletePoolWorkflowBinding.mockReset()
    mockUpsertPoolWorkflowBinding.mockReset()
    mockUpsertPoolWorkflowBinding.mockResolvedValue(undefined)
    mockDeletePoolWorkflowBinding.mockResolvedValue(undefined)
  })

  it('passes revision to delete API for removed bindings', async () => {
    const retainedBinding = buildBinding()
    const removedBinding = buildBinding({
      binding_id: 'binding-removed',
      revision: 7,
    })

    await syncPoolWorkflowBindings({
      poolId: '44444444-4444-4444-4444-444444444444',
      previousBindings: [retainedBinding, removedBinding],
      nextBindings: [retainedBinding],
    })

    expect(mockUpsertPoolWorkflowBinding).toHaveBeenCalledTimes(1)
    expect(mockUpsertPoolWorkflowBinding).toHaveBeenCalledWith({
      pool_id: '44444444-4444-4444-4444-444444444444',
      workflow_binding: retainedBinding,
    })
    expect(mockDeletePoolWorkflowBinding).toHaveBeenCalledTimes(1)
    expect(mockDeletePoolWorkflowBinding).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      'binding-removed',
      7
    )
  })

  it('fails closed when removed binding has no revision', async () => {
    await expect(
      syncPoolWorkflowBindings({
        poolId: '44444444-4444-4444-4444-444444444444',
        previousBindings: [
          buildBinding({
            binding_id: 'binding-missing-revision',
            revision: undefined,
          }),
        ],
        nextBindings: [],
      })
    ).rejects.toThrow('Binding binding-missing-revision is missing revision and cannot be deleted safely.')

    expect(mockDeletePoolWorkflowBinding).not.toHaveBeenCalled()
  })
})
