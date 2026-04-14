import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import {
  DEFAULT_BINDING_PROFILE_EDITOR_VALUES,
  buildBindingProfileCreateRequest,
} from '../poolBindingProfilesForm'

describe('poolBindingProfilesForm', () => {
  beforeEach(async () => {
    await ensureNamespaces('en', 'pools')
    await ensureNamespaces('ru', 'pools')
    await changeLanguage('en')
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

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

    const result = buildBindingProfileCreateRequest(
      valuesWithoutAdvancedJson as unknown as Parameters<typeof buildBindingProfileCreateRequest>[0],
    )

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

  it('localizes advanced JSON and decision validation errors for English runtime', () => {
    const result = buildBindingProfileCreateRequest({
      ...DEFAULT_BINDING_PROFILE_EDITOR_VALUES,
      code: 'commission-profile',
      name: 'Commission Profile',
      workflow_definition_key: 'services-publication',
      workflow_revision_id: '11111111-1111-1111-1111-111111111111',
      workflow_revision: 3,
      workflow_name: 'Services Publication',
      parameters_json: '[]',
      role_mapping_json: '{',
      decisions: [{
        decision_table_id: 'decision-1',
        decision_key: 'document_policy',
        slot_key: '',
        decision_revision: null,
      }],
    })

    expect(result.request).toBeUndefined()
    expect(result.errors).toEqual([
      { field: 'parameters_json', message: 'Expected a JSON object.' },
      { field: 'role_mapping_json', message: 'Invalid JSON.' },
      { field: 'decisions', message: 'Each publication slot requires slot_key and pinned decision revision.' },
    ])
  })

  it('localizes advanced JSON and decision validation errors for Russian runtime', async () => {
    await changeLanguage('ru')

    const result = buildBindingProfileCreateRequest({
      ...DEFAULT_BINDING_PROFILE_EDITOR_VALUES,
      code: 'commission-profile',
      name: 'Commission Profile',
      workflow_definition_key: 'services-publication',
      workflow_revision_id: '11111111-1111-1111-1111-111111111111',
      workflow_revision: 3,
      workflow_name: 'Services Publication',
      parameters_json: '[]',
      role_mapping_json: '{',
      decisions: [{
        decision_table_id: 'decision-1',
        decision_key: 'document_policy',
        slot_key: '',
        decision_revision: null,
      }],
    })

    expect(result.request).toBeUndefined()
    expect(result.errors).toEqual([
      { field: 'parameters_json', message: 'Ожидается JSON-объект.' },
      { field: 'role_mapping_json', message: 'Некорректный JSON.' },
      {
        field: 'decisions',
        message: 'Для каждого publication slot обязательны slot_key и pinned decision revision.',
      },
    ])
  })
})
