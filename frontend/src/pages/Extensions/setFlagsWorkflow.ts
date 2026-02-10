export type SetFlagsRuntimeMask = {
  active: boolean
  safe_mode: boolean
  unsafe_action_protection: boolean
}

export type SetFlagsPolicyState = {
  active: boolean | null
  safe_mode: boolean | null
  unsafe_action_protection: boolean | null
}

export type SetFlagsEditorState = {
  applyActiveEnabled: boolean
  applyActiveValue: boolean
  applySafeModeEnabled: boolean
  applySafeModeValue: boolean
  applyUnsafeActionProtectionEnabled: boolean
  applyUnsafeActionProtectionValue: boolean
}

export type ExtensionsApplyMode = 'workflow_bulk' | 'targeted_fallback'

const normalizePolicyBool = (value: boolean | null | undefined): boolean | null => {
  if (value === true) return true
  if (value === false) return false
  return null
}

const resolveRuntimeValue = (enabled: boolean, selectedValue: boolean, policyValue: boolean | null): boolean => {
  if (enabled) return selectedValue
  if (policyValue === true || policyValue === false) return policyValue
  return false
}

export const buildSetFlagsRuntimeInput = (
  editor: SetFlagsEditorState,
  policy: SetFlagsPolicyState
): { applyMask: SetFlagsRuntimeMask; flagsValues: SetFlagsRuntimeMask } => {
  const normalizedPolicy: SetFlagsPolicyState = {
    active: normalizePolicyBool(policy.active),
    safe_mode: normalizePolicyBool(policy.safe_mode),
    unsafe_action_protection: normalizePolicyBool(policy.unsafe_action_protection),
  }
  const applyMask: SetFlagsRuntimeMask = {
    active: Boolean(editor.applyActiveEnabled),
    safe_mode: Boolean(editor.applySafeModeEnabled),
    unsafe_action_protection: Boolean(editor.applyUnsafeActionProtectionEnabled),
  }
  const flagsValues: SetFlagsRuntimeMask = {
    active: resolveRuntimeValue(applyMask.active, editor.applyActiveValue, normalizedPolicy.active),
    safe_mode: resolveRuntimeValue(applyMask.safe_mode, editor.applySafeModeValue, normalizedPolicy.safe_mode),
    unsafe_action_protection: resolveRuntimeValue(
      applyMask.unsafe_action_protection,
      editor.applyUnsafeActionProtectionValue,
      normalizedPolicy.unsafe_action_protection,
    ),
  }
  return { applyMask, flagsValues }
}

export const hasSetFlagsMaskSelection = (mask: SetFlagsRuntimeMask): boolean => (
  Boolean(mask.active || mask.safe_mode || mask.unsafe_action_protection)
)

export const resolveExtensionsApplyMode = (databaseId: string | null | undefined): ExtensionsApplyMode => (
  databaseId ? 'targeted_fallback' : 'workflow_bulk'
)
