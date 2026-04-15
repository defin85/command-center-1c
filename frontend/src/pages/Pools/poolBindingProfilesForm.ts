import type {
  BindingProfileCreateRequest,
  BindingProfileRevision,
  BindingProfileRevisionCreateRequest,
} from '../../api/poolBindingProfiles'
import type { BindingProfileRevisionWriteRoleMapping } from '../../api/generated/model/bindingProfileRevisionWriteRoleMapping'
import type { PoolWorkflowBindingDecisionRef } from '../../api/intercompanyPools'
import { translateNamespace } from '../../i18n'

export type BindingProfileEditorMode = 'create' | 'revise'

export type BindingProfileDecisionRefFormValue = {
  decision_table_id: string
  decision_key: string
  slot_key: string
  decision_revision?: number | null
}

export type BindingProfileEditorFormValues = {
  code: string
  name: string
  description: string
  workflow_definition_key: string
  workflow_revision_id: string
  workflow_revision: number
  workflow_name: string
  contract_version: string
  decisions: BindingProfileDecisionRefFormValue[]
  parameters_json: string
  role_mapping_json: string
  metadata_json: string
}

type FormError = {
  field: keyof BindingProfileEditorFormValues
  message: string
}

const DEFAULT_OBJECT_JSON = '{}'

const tPools = (key: string, options?: Record<string, unknown>) => (
  translateNamespace('pools', key, options)
)

export function buildBindingProfileEditorInitialValues(
  revision?: BindingProfileRevision,
  profile?: {
    code?: string
    name?: string
    description?: string
  },
): BindingProfileEditorFormValues {
  return {
    code: profile?.code ?? '',
    name: profile?.name ?? '',
    description: profile?.description ?? '',
    workflow_definition_key: revision?.workflow.workflow_definition_key ?? '',
    workflow_revision_id: revision?.workflow.workflow_revision_id ?? '',
    workflow_revision: revision?.workflow.workflow_revision ?? 1,
    workflow_name: revision?.workflow.workflow_name ?? '',
    contract_version: revision?.contract_version ?? '',
    decisions: (revision?.decisions ?? []).map((decision) => ({
      decision_table_id: decision.decision_table_id,
      decision_key: decision.decision_key,
      slot_key: String(decision.slot_key ?? ''),
      decision_revision: decision.decision_revision,
    })),
    parameters_json: JSON.stringify(revision?.parameters ?? {}, null, 2),
    role_mapping_json: JSON.stringify(revision?.role_mapping ?? {}, null, 2),
    metadata_json: JSON.stringify(revision?.metadata ?? {}, null, 2),
  }
}

const parseJsonField = <T,>(
  value: string | null | undefined,
  {
    field,
    emptyValue,
    kind,
  }: {
    field: keyof BindingProfileEditorFormValues
    emptyValue: T
    kind: 'array' | 'object'
  },
): { value?: T; error?: FormError } => {
  const trimmed = typeof value === 'string' ? value.trim() : ''
  if (!trimmed) {
    return { value: emptyValue }
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown
    if (kind === 'array' && !Array.isArray(parsed)) {
      return { error: { field, message: tPools('executionPacks.editor.errors.jsonArrayExpected') } }
    }
    if (
      kind === 'object'
      && (parsed == null || typeof parsed !== 'object' || Array.isArray(parsed))
    ) {
      return { error: { field, message: tPools('executionPacks.editor.errors.jsonObjectExpected') } }
    }
    return { value: parsed as T }
  } catch (_error) {
    return { error: { field, message: tPools('executionPacks.editor.errors.invalidJson') } }
  }
}

export function buildBindingProfileCreateRequest(
  values: BindingProfileEditorFormValues,
): { request?: BindingProfileCreateRequest; errors: FormError[] } {
  const revisionResult = buildBindingProfileRevisionCreateRequest(values)
  if (!revisionResult.request) {
    return { errors: revisionResult.errors }
  }

  return {
    request: {
      code: values.code.trim(),
      name: values.name.trim(),
      description: values.description.trim() || undefined,
      revision: revisionResult.request.revision,
    },
    errors: [],
  }
}

export function buildBindingProfileRevisionCreateRequest(
  values: BindingProfileEditorFormValues,
): { request?: BindingProfileRevisionCreateRequest; errors: FormError[] } {
  const parameters = parseJsonField<Record<string, unknown>>(values.parameters_json, {
    field: 'parameters_json',
    emptyValue: {},
    kind: 'object',
  })
  const roleMapping = parseJsonField<BindingProfileRevisionWriteRoleMapping>(values.role_mapping_json, {
    field: 'role_mapping_json',
    emptyValue: {} as BindingProfileRevisionWriteRoleMapping,
    kind: 'object',
  })
  const metadata = parseJsonField<Record<string, unknown>>(values.metadata_json, {
    field: 'metadata_json',
    emptyValue: {},
    kind: 'object',
  })

  const normalizedDecisions: PoolWorkflowBindingDecisionRef[] = values.decisions
    .map((decision) => ({
      decision_table_id: decision.decision_table_id.trim(),
      decision_key: decision.decision_key.trim(),
      slot_key: decision.slot_key.trim(),
      decision_revision: Number(decision.decision_revision),
    }))
    .filter((decision) => (
      decision.decision_table_id
      || decision.decision_key
      || decision.slot_key
      || Number.isFinite(decision.decision_revision)
    ))

  const decisionErrors = normalizedDecisions.flatMap((decision) => {
    if (
      decision.decision_table_id
      && decision.decision_key
      && decision.slot_key
      && Number.isFinite(decision.decision_revision)
      && decision.decision_revision > 0
    ) {
      return []
    }
    return [{
      field: 'decisions' as const,
      message: tPools('executionPacks.editor.errors.decisionRefIncomplete'),
    }]
  })

  const errors = [parameters.error, roleMapping.error, metadata.error, ...decisionErrors]
    .filter(Boolean) as FormError[]
  if (errors.length > 0) {
    return { errors }
  }

  return {
    request: {
      revision: {
        contract_version: values.contract_version.trim() || undefined,
        workflow: {
          workflow_definition_key: values.workflow_definition_key.trim(),
          workflow_revision_id: values.workflow_revision_id.trim(),
          workflow_revision: Number(values.workflow_revision),
          workflow_name: values.workflow_name.trim(),
        },
        decisions: normalizedDecisions,
        parameters: parameters.value,
        role_mapping: roleMapping.value,
        metadata: metadata.value,
      },
    },
    errors: [],
  }
}

export const DEFAULT_BINDING_PROFILE_EDITOR_VALUES = buildBindingProfileEditorInitialValues(undefined)
export const DEFAULT_BINDING_PROFILE_OBJECT_JSON = DEFAULT_OBJECT_JSON
