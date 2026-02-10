import { describe, expect, it } from 'vitest'

import {
  buildSetFlagsRuntimeInput,
  hasSetFlagsMaskSelection,
  resolveExtensionsApplyMode,
} from '../setFlagsWorkflow'

describe('setFlagsWorkflow helpers', () => {
  it('builds runtime payload from editor state and policy fallback values', () => {
    const { applyMask, flagsValues } = buildSetFlagsRuntimeInput(
      {
        applyActiveEnabled: true,
        applyActiveValue: true,
        applySafeModeEnabled: false,
        applySafeModeValue: false,
        applyUnsafeActionProtectionEnabled: true,
        applyUnsafeActionProtectionValue: false,
      },
      {
        active: false,
        safe_mode: true,
        unsafe_action_protection: true,
      },
    )

    expect(applyMask).toEqual({
      active: true,
      safe_mode: false,
      unsafe_action_protection: true,
    })
    expect(flagsValues).toEqual({
      active: true,
      safe_mode: true,
      unsafe_action_protection: false,
    })
  })

  it('defaults to false when policy value is unknown and flag is not selected in mask', () => {
    const { flagsValues } = buildSetFlagsRuntimeInput(
      {
        applyActiveEnabled: false,
        applyActiveValue: true,
        applySafeModeEnabled: false,
        applySafeModeValue: true,
        applyUnsafeActionProtectionEnabled: false,
        applyUnsafeActionProtectionValue: true,
      },
      {
        active: null,
        safe_mode: null,
        unsafe_action_protection: null,
      },
    )

    expect(flagsValues).toEqual({
      active: false,
      safe_mode: false,
      unsafe_action_protection: false,
    })
  })

  it('detects selected mask and resolves launch mode', () => {
    expect(
      hasSetFlagsMaskSelection({
        active: false,
        safe_mode: false,
        unsafe_action_protection: false,
      }),
    ).toBe(false)

    expect(
      hasSetFlagsMaskSelection({
        active: false,
        safe_mode: true,
        unsafe_action_protection: false,
      }),
    ).toBe(true)

    expect(resolveExtensionsApplyMode(null)).toBe('workflow_bulk')
    expect(resolveExtensionsApplyMode('db-1')).toBe('targeted_fallback')
  })
})
