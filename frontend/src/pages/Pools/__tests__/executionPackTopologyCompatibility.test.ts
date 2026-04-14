import { describe, expect, it } from 'vitest'

import { describeExecutionPackTopologyCompatibility } from '../executionPackTopologyCompatibility'

const localizedMessages = {
  notAvailableStatus: 'недоступно',
  notAvailableMessage: 'Нет данных о совместимости.',
  compatibleStatus: 'совместимо',
  compatibleMessage: 'Совместимость готова.',
  incompatibleStatus: 'несовместимо',
  incompatibleMessage: 'Совместимость заблокирована.',
} as const

describe('execution pack topology compatibility', () => {
  it('maps missing summaries to the localized not-available state', () => {
    expect(describeExecutionPackTopologyCompatibility(undefined, localizedMessages)).toEqual({
      statusText: 'недоступно',
      alertType: 'info',
      message: 'Нет данных о совместимости.',
      coveredSlotsText: '-',
      diagnostics: [],
    })
  })

  it('maps compatible summaries to the localized success state', () => {
    expect(describeExecutionPackTopologyCompatibility({
      status: 'compatible',
      topology_aware_ready: true,
      covered_slot_keys: ['sale', 'purchase'],
      diagnostics: [],
    }, localizedMessages)).toEqual({
      statusText: 'совместимо',
      alertType: 'success',
      message: 'Совместимость готова.',
      coveredSlotsText: 'sale, purchase',
      diagnostics: [],
    })
  })

  it('maps incompatible summaries to the localized warning state and keeps diagnostics', () => {
    const result = describeExecutionPackTopologyCompatibility({
      status: 'blocked',
      topology_aware_ready: false,
      covered_slot_keys: ['sale'],
      diagnostics: [
        {
          slot_key: 'sale',
          decision_table_id: 'decision-1',
          decision_revision: 3,
          field_or_table_path: 'document.policy',
          detail: 'alias is missing',
        },
      ],
    }, localizedMessages)

    expect(result.statusText).toBe('несовместимо')
    expect(result.alertType).toBe('warning')
    expect(result.message).toBe('Совместимость заблокирована.')
    expect(result.coveredSlotsText).toBe('sale')
    expect(result.diagnostics).toEqual(['slot sale · decision-1 r3 · document.policy — alias is missing'])
  })
})
