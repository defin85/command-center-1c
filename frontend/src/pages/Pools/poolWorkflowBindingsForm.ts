import type {
  OrganizationPool,
  PoolWorkflowBinding,
  PoolWorkflowBindingInput,
  PoolWorkflowBindingStatus,
} from '../../api/intercompanyPools'

export type PoolWorkflowBindingDecisionFormValue = {
  decision_table_id?: string
  decision_key?: string
  decision_revision?: number | string | null
}

export type PoolWorkflowBindingRoleMappingFormValue = {
  source_role?: string
  target_role?: string
}

export type PoolWorkflowBindingParameterFormValue = {
  key?: string
  value_json?: string
}

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
  workflow_definition_key?: string
  workflow_revision_id?: string
  workflow_revision?: number | string | null
  workflow_name?: string
  decisions?: PoolWorkflowBindingDecisionFormValue[]
  parameters?: PoolWorkflowBindingParameterFormValue[]
  role_mapping?: PoolWorkflowBindingRoleMappingFormValue[]
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

const formatJsonValue = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return JSON.stringify(String(value))
  }
}

const toSortedRecord = (pairs: Array<[string, string]>): Record<string, string> => (
  Object.fromEntries(
    pairs.sort(([left], [right]) => left.localeCompare(right))
  )
)

const toSortedJsonRecord = (pairs: Array<[string, unknown]>): Record<string, unknown> => (
  Object.fromEntries(
    pairs.sort(([left], [right]) => left.localeCompare(right))
  )
)

const parseTagsCsv = (value: string | undefined): string[] => (
  Array.from(new Set(
    String(value ?? '')
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
  ))
)

const formatWorkflowBindingScope = (
  selector: PoolWorkflowBindingSelectorFormValue | undefined
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
  effectiveTo: string | undefined
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
  index: number
): string => {
  const workflowKey = String(value?.workflow_definition_key ?? '').trim()
  const workflowName = String(value?.workflow_name ?? '').trim()
  const effectiveFrom = String(value?.effective_from ?? '').trim()
  if (workflowKey) {
    return `Binding #${index}: ${workflowKey}`
  }
  if (workflowName) {
    return `Binding #${index}: ${workflowName}`
  }
  if (effectiveFrom) {
    return `Binding #${index}: ${effectiveFrom}`
  }
  return `Binding #${index}`
}

export const getWorkflowBindingCardSummary = (
  value: PoolWorkflowBindingFormValue | undefined
): string => {
  const status = String(value?.status ?? DEFAULT_BINDING_STATUS).trim() || DEFAULT_BINDING_STATUS
  return [
    status,
    formatWorkflowBindingScope(value?.selector),
    formatWorkflowBindingPeriod(value?.effective_from, value?.effective_to),
  ].join(' · ')
}

export const createEmptyWorkflowBindingFormValue = (): PoolWorkflowBindingFormValue => ({
  binding_id: '',
  revision: null,
  workflow_definition_key: '',
  workflow_revision_id: '',
  workflow_revision: null,
  workflow_name: '',
  decisions: [],
  parameters: [],
  role_mapping: [],
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
  pool: OrganizationPool | null | undefined
): PoolWorkflowBinding[] => {
  return Array.isArray(pool?.workflow_bindings)
    ? normalizeWorkflowBindingsArray(pool.workflow_bindings)
    : []
}

export const workflowBindingsToFormValues = (
  bindings: PoolWorkflowBinding[]
): PoolWorkflowBindingFormValue[] => (
  bindings.map((binding) => ({
    contract_version: binding.contract_version,
    binding_id: binding.binding_id ?? '',
    pool_id: binding.pool_id ?? '',
    revision: binding.revision ?? null,
    workflow_definition_key: binding.workflow.workflow_definition_key,
    workflow_revision_id: binding.workflow.workflow_revision_id,
    workflow_revision: binding.workflow.workflow_revision,
    workflow_name: binding.workflow.workflow_name,
    decisions: (binding.decisions ?? []).map((decision) => ({
      decision_table_id: decision.decision_table_id,
      decision_key: decision.decision_key,
      decision_revision: decision.decision_revision,
    })),
    parameters: Object.entries(binding.parameters ?? {})
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        value_json: formatJsonValue(value),
      })),
    role_mapping: Object.entries(binding.role_mapping ?? {})
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([source_role, target_role]) => ({
        source_role,
        target_role,
      })),
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
  pool: OrganizationPool
): { primary: string; secondary: string | null } => {
  const bindings = extractWorkflowBindingsFromPool(pool)
  if (bindings.length === 0) {
    return { primary: '0 bindings', secondary: null }
  }

  const activeCount = bindings.filter((binding) => binding.status === 'active').length
  const firstBinding = bindings[0]
  const workflowKey = String(
    firstBinding?.workflow?.workflow_definition_key || firstBinding?.workflow?.workflow_name || ''
  ).trim()

  return {
    primary: `${bindings.length} ${bindings.length === 1 ? 'binding' : 'bindings'}`,
    secondary: [
      workflowKey,
      activeCount > 0 ? `${activeCount} active` : null,
    ]
      .filter((item): item is string => Boolean(item))
      .join(' · ') || null,
  }
}

const buildDecisions = (
  rawDecisions: PoolWorkflowBindingDecisionFormValue[] | undefined,
  bindingLabel: string,
  errors: string[]
) => {
  const decisions = Array.isArray(rawDecisions) ? rawDecisions : []
  const seenDecisionKeys = new Set<string>()
  const normalized: Array<{
    decision_table_id: string
    decision_key: string
    decision_revision: number
  }> = []

  decisions.forEach((decision, index) => {
    const decisionLabel = `${bindingLabel} decision #${index + 1}`
    const decisionTableId = String(decision?.decision_table_id ?? '').trim()
    const decisionKey = String(decision?.decision_key ?? '').trim()
    const decisionRevisionRaw = String(decision?.decision_revision ?? '').trim()

    if (!decisionTableId && !decisionKey && !decisionRevisionRaw) {
      return
    }
    if (!decisionTableId || !decisionKey || !decisionRevisionRaw) {
      errors.push(`${decisionLabel}: required fields are decision_table_id, decision_key, decision_revision.`)
      return
    }
    const decisionRevision = Number(decisionRevisionRaw)
    if (!Number.isInteger(decisionRevision) || decisionRevision <= 0) {
      errors.push(`${decisionLabel}: decision_revision должен быть положительным integer.`)
      return
    }
    if (seenDecisionKeys.has(decisionKey)) {
      errors.push(`${bindingLabel}: decisions.decision_key должен быть уникальным внутри binding.`)
      return
    }
    seenDecisionKeys.add(decisionKey)
    normalized.push({
      decision_table_id: decisionTableId,
      decision_key: decisionKey,
      decision_revision: decisionRevision,
    })
  })

  return normalized
}

const buildRoleMapping = (
  rawRoles: PoolWorkflowBindingRoleMappingFormValue[] | undefined,
  bindingLabel: string,
  errors: string[]
) => {
  const roles = Array.isArray(rawRoles) ? rawRoles : []
  const pairs: Array<[string, string]> = []

  roles.forEach((role, index) => {
    const sourceRole = String(role?.source_role ?? '').trim()
    const targetRole = String(role?.target_role ?? '').trim()
    if (!sourceRole && !targetRole) {
      return
    }
    if (!sourceRole || !targetRole) {
      errors.push(`${bindingLabel} role mapping #${index + 1}: both source_role and target_role are required.`)
      return
    }
    pairs.push([sourceRole, targetRole])
  })

  return toSortedRecord(pairs)
}

const buildParameters = (
  rawParameters: PoolWorkflowBindingParameterFormValue[] | undefined,
  bindingLabel: string,
  errors: string[]
) => {
  const parameters = Array.isArray(rawParameters) ? rawParameters : []
  const pairs: Array<[string, unknown]> = []

  parameters.forEach((parameter, index) => {
    const key = String(parameter?.key ?? '').trim()
    const valueJson = String(parameter?.value_json ?? '').trim()
    if (!key && !valueJson) {
      return
    }
    if (!key || !valueJson) {
      errors.push(`${bindingLabel} parameter #${index + 1}: both key and JSON value are required.`)
      return
    }
    try {
      pairs.push([key, JSON.parse(valueJson)])
    } catch {
      errors.push(`${bindingLabel}: parameters.${key} должен быть валидным JSON.`)
    }
  })

  return toSortedJsonRecord(pairs)
}

export const buildWorkflowBindingsFromForm = (
  rawBindings: PoolWorkflowBindingFormValue[] | undefined
): { bindings: PoolWorkflowBindingInput[]; errors: string[] } => {
  const bindings = Array.isArray(rawBindings) ? rawBindings : []
  const errors: string[] = []
  const normalized: PoolWorkflowBindingInput[] = []

  bindings.forEach((binding, index) => {
    const bindingLabel = `Binding #${index + 1}`
    const workflowDefinitionKey = String(binding?.workflow_definition_key ?? '').trim()
    const workflowRevisionId = String(binding?.workflow_revision_id ?? '').trim()
    const workflowRevisionRaw = String(binding?.workflow_revision ?? '').trim()
    const revisionRaw = String(binding?.revision ?? '').trim()
    const workflowName = String(binding?.workflow_name ?? '').trim()
    const effectiveFrom = String(binding?.effective_from ?? '').trim()
    const effectiveTo = String(binding?.effective_to ?? '').trim()
    const bindingId = String(binding?.binding_id ?? '').trim()

    if (!workflowDefinitionKey) {
      errors.push(`${bindingLabel}: workflow_definition_key обязателен.`)
    }
    if (!workflowRevisionId) {
      errors.push(`${bindingLabel}: workflow_revision_id обязателен.`)
    }
    if (!workflowRevisionRaw) {
      errors.push(`${bindingLabel}: workflow_revision обязателен.`)
    }
    if (!workflowName) {
      errors.push(`${bindingLabel}: workflow_name обязателен.`)
    }
    if (!effectiveFrom) {
      errors.push(`${bindingLabel}: effective_from обязателен.`)
    }
    if (bindingId && !revisionRaw) {
      errors.push(`${bindingLabel}: revision обязателен для обновления существующего binding.`)
    }
    if (effectiveTo && effectiveFrom && effectiveTo < effectiveFrom) {
      errors.push(`${bindingLabel}: effective_to не может быть раньше effective_from.`)
    }

    const workflowRevision = Number(workflowRevisionRaw)
    if (workflowRevisionRaw && (!Number.isInteger(workflowRevision) || workflowRevision <= 0)) {
      errors.push(`${bindingLabel}: workflow_revision должен быть положительным integer.`)
    }
    const revision = Number(revisionRaw)
    if (revisionRaw && (!Number.isInteger(revision) || revision <= 0)) {
      errors.push(`${bindingLabel}: revision должен быть положительным integer.`)
    }

    const decisions = buildDecisions(binding?.decisions, bindingLabel, errors)
    const roleMapping = buildRoleMapping(binding?.role_mapping, bindingLabel, errors)
    const parameters = buildParameters(binding?.parameters, bindingLabel, errors)

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
      ...(String(binding?.binding_id ?? '').trim()
        ? { binding_id: String(binding?.binding_id).trim() }
        : {}),
      ...(String(binding?.pool_id ?? '').trim()
        ? { pool_id: String(binding?.pool_id).trim() }
        : {}),
      ...(revisionRaw ? { revision } : {}),
      workflow: {
        workflow_definition_key: workflowDefinitionKey,
        workflow_revision_id: workflowRevisionId,
        workflow_revision: workflowRevision,
        workflow_name: workflowName,
      },
      ...(decisions.length > 0 ? { decisions } : {}),
      ...(Object.keys(parameters).length > 0 ? { parameters } : {}),
      ...(Object.keys(roleMapping).length > 0 ? { role_mapping: roleMapping } : {}),
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
