import { describe, expect, it } from 'vitest'

import type { DriverCommandV2 } from '../../../../api/driverCommands'
import { buildParamsTemplate } from '../utils'

const makeCommand = (paramsByName: DriverCommandV2['params_by_name']): DriverCommandV2 => ({
  label: 'test',
  argv: ['cmd'],
  scope: 'per_database',
  risk_level: 'safe',
  params_by_name: paramsByName,
})

describe('buildParamsTemplate', () => {
  it('uses default when provided (including null)', () => {
    const command = makeCommand({
      format: { kind: 'flag', required: false, expects_value: true, default: 'json' },
      maybe: { kind: 'flag', required: false, expects_value: true, default: null },
    })

    expect(buildParamsTemplate(command, 'cli')).toEqual({
      format: 'json',
      maybe: null,
    })
  })

  it('uses [] for repeatable and null otherwise when default is missing', () => {
    const command = makeCommand({
      ids: { kind: 'flag', required: false, expects_value: true, repeatable: true },
      name: { kind: 'flag', required: false, expects_value: true },
    })

    expect(buildParamsTemplate(command, 'cli')).toEqual({
      ids: [],
      name: null,
    })
  })

  it('filters out disabled params', () => {
    const command = makeCommand({
      a: { kind: 'flag', required: false, expects_value: true },
      b: { kind: 'flag', required: false, expects_value: true, disabled: true },
    })

    expect(buildParamsTemplate(command, 'cli')).toEqual({ a: null })
  })

  it('filters out ibcmd connection params (by name) when driver=ibcmd', () => {
    const command = makeCommand({
      remote: { kind: 'flag', required: false, expects_value: true, default: 'ssh://x:1545' },
      format: { kind: 'flag', required: false, expects_value: true, default: 'json' },
    })

    expect(buildParamsTemplate(command, 'ibcmd')).toEqual({ format: 'json' })
    expect(buildParamsTemplate(command, 'cli')).toEqual({ format: 'json', remote: 'ssh://x:1545' })
  })
})

