import type {
  OrganizationPool,
  PoolWorkflowBinding,
  PoolWorkflowBindingInput,
  PoolWorkflowBindingProfileLifecycleWarning,
  PoolWorkflowBindingResolvedProfile,
  PoolWorkflowBindingStatus,
} from '../../api/intercompanyPools'
import {
  type PoolWorkflowBindingPresentationValue,
  resolvePoolWorkflowBindingProfileLabel,
  resolvePoolWorkflowBindingProfileRevisionNumber,
  resolvePoolWorkflowBindingWorkflow,
} from './poolWorkflowBindingPresentation'

export type PoolWorkflowBindingSelectorFormValue = {
  direction?: string
  mode?: string
  tags_csv?: string
}

export type PoolWorkflowBindingFormValue = {
  contract_version?: string
  binding_id?: string
  pool_id?: string
  revision?: number | string | null
  binding_profile_id?: string
  binding_profile_revision_id?: string
  binding_profile_revision_number?: number | string | null
  resolved_profile?: PoolWorkflowBindingResolvedProfile | null
  profile_lifecycle_warning?: PoolWorkflowBindingProfileLifecycleWarning | null
  selector?: PoolWorkflowBindingSelectorFormValue
  effective_from?: string
  effective_to?: string
  status?: PoolWorkflowBindingStatus
}

const DEFAULT_BINDING_STATUS: PoolWorkflowBindingStatus = 'draft'

const normalizeWorkflowBindingsArray = (rawBindings: unknown): PoolWorkflowBinding[] => {
  if (!Array.isArray(rawBindings)) {
    return []
  }
  return rawBindings.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as PoolWorkflowBinding[]
}

const parseTagsCsv = (value: string | undefined): string[] => (
  Array.from(new Set(
    String(value ?? '')
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
  ))
)

const formatWorkflowBindingScope = (
  selector: PoolWorkflowBindingSelectorFormValue | undefined,
): string => {
  const parts: string[] = []
  const direction = String(selector?.direction ?? '').trim()
  const mode = String(selector?.mode ?? '').trim()
  const tags = parseTagsCsv(selector?.tags_csv)
  if (direction) {
    parts.push(`direction=${direction}`)
  }
  if (mode) {
    parts.push(`mode=${mode}`)
  }
  if (tags.length > 0) {
    parts.push(`tags=${tags.join(', ')}`)
  }
  return parts.length > 0 ? parts.join(' · ') : 'unscoped'
}

const formatWorkflowBindingPeriod = (
  effectiveFrom: string | undefined,
  effectiveTo: string | undefined,
): string => {
  const normalizedFrom = String(effectiveFrom ?? '').trim()
  const normalizedTo = String(effectiveTo ?? '').trim()
  if (!normalizedFrom) {
    return 'period not set'
  }
  return normalizedTo ? `${normalizedFrom}..${normalizedTo}` : `${normalizedFrom}..open`
}

export const getWorkflowBindingCardTitle = (
  value: PoolWorkflowBindingFormValue | undefined,
  index: number,
): string => {
  const profileLabel = resolvePoolWorkflowBindingProfileLabel(
    value?.resolved_profile
      ? {
        binding_profile_id: value.binding_profile_id,
        binding_profile_revision_id: value.binding_profile_revision_id,
        binding_profile_revision_number: typeof value.binding_profile_revision_number === 'number'
          ? value.binding_profile_revision_number
          : undefined,
        resolved_profile: value.resolved_profile,
      } satisfies PoolWorkflowBindingPresentationValue
      : null,
  )
  const revisionNumber = String(value?.binding_profile_revision_number ?? '').trim()
  if (profileLabel !== '-') {
    return revisionNumber
      ? `Attachment #${index}: ${profileLabel} · r${revisionNumber}`
      : `Attachment #${index}: ${profileLabel}`
  }
  const bindingId = String(value?.binding_id ?? '').trim()
  if (bindingId) {
    return `Attachment #${index}: ${bindingId}`
  }
  return `Attachment #${index}`
}

export const getWorkflowBindingCardSummary = (
  value: PoolWorkflowBindingFormValue | undefined,
): string => {
  const status = String(value?.status ?? DEFAULT_BINDING_STATUS).trim() || DEFAULT_BINDING_STATUS
  const revisionNumber = String(value?.binding_profile_revision_number ?? '').trim()
  return [
    status,
    revisionNumber ? `profile r${revisionNumber}` : null,
    formatWorkflowBindingScope(value?.selector),
    formatWorkflowBindingPeriod(value?.effective_from, value?.effective_to),
  ]
    .filter((item): item is string => Boolean(item))
    .join(' · ')
}

export const createEmptyWorkflowBindingFormValue = (): PoolWorkflowBindingFormValue => ({
  binding_id: '',
  revision: null,
  binding_profile_id: '',
  binding_profile_revision_id: '',
  binding_profile_revision_number: null,
  resolved_profile: null,
  profile_lifecycle_warning: null,
  selector: {
    direction: '',
    mode: '',
    tags_csv: '',
  },
  effective_from: new Date().toISOString().slice(0, 10),
  effective_to: '',
  status: DEFAULT_BINDING_STATUS,
})

export const extractWorkflowBindingsFromPool = (
  pool: OrganizationPool | null | undefined,
): PoolWorkflowBinding[] => {
  return Array.isArray(pool?.workflow_bindings)
    ? normalizeWorkflowBindingsArray(pool.workflow_bindings)
    : []
}

export const workflowBindingsToFormValues = (
  bindings: PoolWorkflowBinding[],
): PoolWorkflowBindingFormValue[] => (
  bindings.map((binding) => ({
    contract_version: binding.contract_version,
    binding_id: binding.binding_id ?? '',
    pool_id: binding.pool_id ?? '',
    revision: binding.revision ?? null,
    binding_profile_id: binding.binding_profile_id ?? binding.resolved_profile?.binding_profile_id ?? '',
    binding_profile_revision_id: binding.binding_profile_revision_id ?? binding.resolved_profile?.binding_profile_revision_id ?? '',
    binding_profile_revision_number: (
      binding.binding_profile_revision_number
      ?? binding.resolved_profile?.binding_profile_revision_number
      ?? null
    ),
    resolved_profile: binding.resolved_profile ?? null,
    profile_lifecycle_warning: binding.profile_lifecycle_warning ?? null,
    selector: {
      direction: binding.selector?.direction ?? '',
      mode: binding.selector?.mode ?? '',
      tags_csv: (binding.selector?.tags ?? []).join(', '),
    },
    effective_from: binding.effective_from,
    effective_to: binding.effective_to ?? '',
    status: binding.status ?? DEFAULT_BINDING_STATUS,
  }))
)

export const summarizeWorkflowBindings = (
  pool: OrganizationPool,
): { primary: string; secondary: string | null } => {
  const bindings = extractWorkflowBindingsFromPool(pool)
  if (bindings.length === 0) {
    return { primary: '0 bindings', secondary: null }
  }

  const activeCount = bindings.filter((binding) => binding.status === 'active').length
  const firstBinding = bindings[0]
  const workflow = resolvePoolWorkflowBindingWorkflow(firstBinding)
  const profileRevisionNumber = resolvePoolWorkflowBindingProfileRevisionNumber({
    binding: firstBinding,
    runtimeProjection: null,
  })

  return {
    primary: `${bindings.length} ${bindings.length === 1 ? 'binding' : 'bindings'}`,
    secondary: [
      workflow?.workflow_definition_key || workflow?.workflow_name || '',
      profileRevisionNumber ? `profile r${profileRevisionNumber}` : null,
      activeCount > 0 ? `${activeCount} active` : null,
    ]
      .filter((item): item is string => Boolean(item))
      .join(' · ') || null,
  }
}

export const buildWorkflowBindingsFromForm = (
  rawBindings: PoolWorkflowBindingFormValue[] | undefined,
): { bindings: PoolWorkflowBindingInput[]; errors: string[] } => {
  const bindings = Array.isArray(rawBindings) ? rawBindings : []
  const errors: string[] = []
  const normalized: PoolWorkflowBindingInput[] = []

  bindings.forEach((binding, index) => {
    const bindingLabel = `Attachment #${index + 1}`
    const bindingProfileRevisionId = String(binding?.binding_profile_revision_id ?? '').trim()
    const revisionRaw = String(binding?.revision ?? '').trim()
    const effectiveFrom = String(binding?.effective_from ?? '').trim()
    const effectiveTo = String(binding?.effective_to ?? '').trim()
    const bindingId = String(binding?.binding_id ?? '').trim()

    if (!bindingProfileRevisionId) {
      errors.push(`${bindingLabel}: binding_profile_revision_id обязателен.`)
    }
    if (!effectiveFrom) {
      errors.push(`${bindingLabel}: effective_from обязателен.`)
    }
    if (bindingId && !revisionRaw) {
      errors.push(`${bindingLabel}: revision обязателен для обновления существующего attachment.`)
    }
    if (effectiveTo && effectiveFrom && effectiveTo < effectiveFrom) {
      errors.push(`${bindingLabel}: effective_to не может быть раньше effective_from.`)
    }

    const revision = Number(revisionRaw)
    if (revisionRaw && (!Number.isInteger(revision) || revision <= 0)) {
      errors.push(`${bindingLabel}: revision должен быть положительным integer.`)
    }

    if (errors.length > 0) {
      return
    }

    const selectorDirection = String(binding?.selector?.direction ?? '').trim()
    const selectorMode = String(binding?.selector?.mode ?? '').trim()
    const selectorTags = parseTagsCsv(binding?.selector?.tags_csv)
    const selector = (
      selectorDirection || selectorMode || selectorTags.length > 0
        ? {
          ...(selectorDirection ? { direction: selectorDirection } : {}),
          ...(selectorMode ? { mode: selectorMode } : {}),
          ...(selectorTags.length > 0 ? { tags: selectorTags } : {}),
        }
        : undefined
    )

    normalized.push({
      ...(String(binding?.contract_version ?? '').trim()
        ? { contract_version: String(binding?.contract_version).trim() }
        : {}),
      ...(bindingId ? { binding_id: bindingId } : {}),
      ...(String(binding?.pool_id ?? '').trim()
        ? { pool_id: String(binding?.pool_id).trim() }
        : {}),
      ...(revisionRaw ? { revision } : {}),
      binding_profile_revision_id: bindingProfileRevisionId,
      ...(selector ? { selector } : {}),
      effective_from: effectiveFrom,
      ...(effectiveTo ? { effective_to: effectiveTo } : {}),
      status: (binding?.status ?? DEFAULT_BINDING_STATUS) as PoolWorkflowBindingStatus,
    })
  })

  if (errors.length > 0) {
    return { bindings: [], errors }
  }
  return { bindings: normalized, errors: [] }
}
