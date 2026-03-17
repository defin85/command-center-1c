import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PoolWorkflowBindingInput } from '../../../api/intercompanyPools'
import { syncPoolWorkflowBindings } from '../poolWorkflowBindingsSync'

const mockReplacePoolWorkflowBindingsCollection = vi.fn()

vi.mock('../../../api/intercompanyPools', () => ({
  replacePoolWorkflowBindingsCollection: (...args: unknown[]) => (
    mockReplacePoolWorkflowBindingsCollection(...args)
  ),
}))

function buildBinding(overrides: Partial<PoolWorkflowBindingInput> = {}): PoolWorkflowBindingInput {
  return {
    binding_id: 'binding-existing',
    pool_id: 'pool-1',
    revision: 3,
    binding_profile_revision_id: 'bp-rev-services-r2',
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
    mockReplacePoolWorkflowBindingsCollection.mockReset()
    mockReplacePoolWorkflowBindingsCollection.mockResolvedValue(undefined)
  })

  it('sends the full workflow binding collection with collection etag in a single request', async () => {
    const retainedBinding = buildBinding()
    const removedBinding = buildBinding({
      binding_id: 'binding-removed',
      revision: 7,
    })

    await syncPoolWorkflowBindings({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:etag-1',
      nextBindings: [retainedBinding],
    })

    expect(mockReplacePoolWorkflowBindingsCollection).toHaveBeenCalledTimes(1)
    expect(mockReplacePoolWorkflowBindingsCollection).toHaveBeenCalledWith({
      pool_id: '44444444-4444-4444-4444-444444444444',
      expected_collection_etag: 'sha256:etag-1',
      workflow_bindings: [retainedBinding],
    })
    expect(mockReplacePoolWorkflowBindingsCollection).not.toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_bindings: [retainedBinding, removedBinding],
      })
    )
  })

  it('keeps existing binding revisions inside the atomic replace payload', async () => {
    const changedBinding = buildBinding({
      selector: {
        direction: 'top_down',
        mode: 'unsafe',
        tags: ['baseline'],
      },
    })

    await syncPoolWorkflowBindings({
      poolId: '44444444-4444-4444-4444-444444444444',
      collectionEtag: 'sha256:etag-2',
      nextBindings: [changedBinding],
    })

    expect(mockReplacePoolWorkflowBindingsCollection).toHaveBeenCalledTimes(1)
    expect(mockReplacePoolWorkflowBindingsCollection).toHaveBeenCalledWith({
      pool_id: '44444444-4444-4444-4444-444444444444',
      expected_collection_etag: 'sha256:etag-2',
      workflow_bindings: [changedBinding],
    })
  })

  it('fails closed when collection etag is missing', async () => {
    await expect(
      syncPoolWorkflowBindings({
        poolId: '44444444-4444-4444-4444-444444444444',
        collectionEtag: '',
        nextBindings: [buildBinding()],
      })
    ).rejects.toThrow('collectionEtag is required for atomic workflow binding save.')

    expect(mockReplacePoolWorkflowBindingsCollection).not.toHaveBeenCalled()
  })
})
