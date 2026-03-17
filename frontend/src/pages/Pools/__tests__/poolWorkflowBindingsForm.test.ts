import { describe, expect, it } from 'vitest'

import type { PoolWorkflowBinding } from '../../../api/intercompanyPools'
import {
  buildWorkflowBindingsFromForm,
  workflowBindingsToFormValues,
} from '../poolWorkflowBindingsForm'

function buildBinding(overrides: Partial<PoolWorkflowBinding> = {}): PoolWorkflowBinding {
  const workflow = {
    workflow_definition_key: 'services-publication',
    workflow_revision_id: '11111111-1111-1111-1111-111111111111',
    workflow_revision: 5,
    workflow_name: 'services_publication',
  }
  const decisions = [
    {
      decision_table_id: 'decision-1',
      decision_key: 'document_policy',
      slot_key: 'sale',
      decision_revision: 4,
    },
  ]
  const parameters = {
    strategy: 'strict',
  }
  const roleMapping = {
    owner: 'publisher',
  }
  return {
    binding_id: 'binding-existing',
    pool_id: '44444444-4444-4444-4444-444444444444',
    revision: 3,
    binding_profile_id: 'bp-services',
    binding_profile_revision_id: 'bp-rev-services-r2',
    binding_profile_revision_number: 2,
    workflow,
    selector: {
      direction: 'top_down',
      mode: 'safe',
      tags: ['baseline', 'monthly'],
    },
    decisions,
    role_mapping: roleMapping,
    parameters,
    resolved_profile: {
      binding_profile_id: 'bp-services',
      code: 'services-publication-profile',
      name: 'Services Publication Profile',
      status: 'active',
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_revision_number: 2,
      workflow,
      decisions,
      parameters,
      role_mapping: roleMapping,
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
      binding_profile_revision_id: 'bp-rev-services-r2',
      binding_profile_revision_number: 2,
    })
    expect(prepared.errors).toEqual([])
    expect(prepared.bindings).toEqual([{
      binding_id: 'binding-existing',
      pool_id: '44444444-4444-4444-4444-444444444444',
      revision: 3,
      binding_profile_revision_id: 'bp-rev-services-r2',
      selector: {
        direction: 'top_down',
        mode: 'safe',
        tags: ['baseline', 'monthly'],
      },
      effective_from: '2026-01-01',
      effective_to: '2026-12-31',
      status: 'active',
    }])
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
      'Attachment #1: revision обязателен для обновления существующего attachment.'
    )
  })

  it('fails closed when effective_to is earlier than effective_from', () => {
    const binding = buildBinding({
      effective_to: '2025-12-31',
    })

    const prepared = buildWorkflowBindingsFromForm(workflowBindingsToFormValues([binding]))

    expect(prepared.bindings).toEqual([])
    expect(prepared.errors).toContain(
      'Attachment #1: effective_to не может быть раньше effective_from.'
    )
  })
})
