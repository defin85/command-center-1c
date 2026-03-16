import { describe, expect, it } from 'vitest'

import type { PoolWorkflowBinding } from '../../../api/intercompanyPools'
import {
  buildWorkflowBindingsFromForm,
  workflowBindingsToFormValues,
} from '../poolWorkflowBindingsForm'

function buildBinding(overrides: Partial<PoolWorkflowBinding> = {}): PoolWorkflowBinding {
  return {
    binding_id: 'binding-existing',
    pool_id: '44444444-4444-4444-4444-444444444444',
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
      tags: ['baseline', 'monthly'],
    },
    decisions: [
      {
        decision_table_id: 'decision-1',
        decision_key: 'document_policy',
        slot_key: 'sale',
        decision_revision: 4,
      },
    ],
    role_mapping: {
      owner: 'publisher',
    },
    parameters: {
      strategy: 'strict',
    },
    effective_from: '2026-01-01',
    effective_to: '2026-12-31',
    status: 'active',
    ...overrides,
  }
}

describe('poolWorkflowBindingsForm', () => {
  it('preserves revision when existing bindings round-trip through form values', () => {
    const binding = buildBinding()

    const formValues = workflowBindingsToFormValues([binding])
    const prepared = buildWorkflowBindingsFromForm(formValues)

    expect(formValues[0]).toMatchObject({
      binding_id: 'binding-existing',
      revision: 3,
      workflow_definition_key: 'services-publication',
    })
    expect(prepared.errors).toEqual([])
    expect(prepared.bindings).toEqual([binding])
  })

  it('fails closed when existing binding update loses revision', () => {
    const binding = buildBinding()
    const formValues = workflowBindingsToFormValues([binding])
    formValues[0] = {
      ...formValues[0],
      revision: null,
    }

    const prepared = buildWorkflowBindingsFromForm(formValues)

    expect(prepared.bindings).toEqual([])
    expect(prepared.errors).toContain(
      'Binding #1: revision обязателен для обновления существующего binding.'
    )
  })

  it('fails closed on duplicate slot_key inside one binding', () => {
    const binding = buildBinding({
      decisions: [
        {
          decision_table_id: 'decision-1',
          decision_key: 'document_policy',
          slot_key: 'shared_slot',
          decision_revision: 4,
        },
        {
          decision_table_id: 'decision-2',
          decision_key: 'document_policy',
          slot_key: 'shared_slot',
          decision_revision: 5,
        },
      ],
    })

    const prepared = buildWorkflowBindingsFromForm(workflowBindingsToFormValues([binding]))

    expect(prepared.bindings).toEqual([])
    expect(prepared.errors).toContain(
      'Binding #1: decisions.slot_key должен быть уникальным внутри binding.'
    )
  })
})
