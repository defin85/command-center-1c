import { describe, expect, it } from 'vitest'

import {
  DEFAULT_BINDING_PROFILE_EDITOR_VALUES,
  buildBindingProfileCreateRequest,
} from '../poolBindingProfilesForm'

describe('poolBindingProfilesForm', () => {
  it('defaults hidden advanced JSON fields when create flow omits them', () => {
    const baseValues = {
      ...DEFAULT_BINDING_PROFILE_EDITOR_VALUES,
      code: 'commission-profile',
      name: 'Commission Profile',
      workflow_definition_key: 'services-publication',
      workflow_revision_id: '11111111-1111-1111-1111-111111111111',
      workflow_revision: 3,
      workflow_name: 'Services Publication',
      decisions: [{
        decision_table_id: 'decision-1',
        decision_key: 'document_policy',
        slot_key: 'realization',
        decision_revision: 2,
      }],
    }
    const valuesWithoutAdvancedJson = {
      ...baseValues,
      parameters_json: undefined,
      role_mapping_json: undefined,
      metadata_json: undefined,
    }

    const result = buildBindingProfileCreateRequest(valuesWithoutAdvancedJson as typeof baseValues)

    expect(result.errors).toEqual([])
    expect(result.request).toEqual({
      code: 'commission-profile',
      name: 'Commission Profile',
      description: undefined,
      revision: {
        contract_version: undefined,
        workflow: {
          workflow_definition_key: 'services-publication',
          workflow_revision_id: '11111111-1111-1111-1111-111111111111',
          workflow_revision: 3,
          workflow_name: 'Services Publication',
        },
        decisions: [{
          decision_table_id: 'decision-1',
          decision_key: 'document_policy',
          slot_key: 'realization',
          decision_revision: 2,
        }],
        parameters: {},
        role_mapping: {},
        metadata: {},
      },
    })
  })
})
