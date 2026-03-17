import type { BindingProfileCreateRequest, BindingProfileRevision, BindingProfileRevisionCreateRequest } from '../../api/poolBindingProfiles'

export type BindingProfileEditorMode = 'create' | 'revise'

export type BindingProfileEditorFormValues = {
  code: string
  name: string
  description: string
  workflow_definition_key: string
  workflow_revision_id: string
  workflow_revision: number
  workflow_name: string
  contract_version: string
  decisions_json: string
  parameters_json: string
  role_mapping_json: string
  metadata_json: string
}

type FormError = {
  field: keyof BindingProfileEditorFormValues
  message: string
}

const DEFAULT_DECISIONS_JSON = '[]'
const DEFAULT_OBJECT_JSON = '{}'

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
    decisions_json: JSON.stringify(revision?.decisions ?? [], null, 2),
    parameters_json: JSON.stringify(revision?.parameters ?? {}, null, 2),
    role_mapping_json: JSON.stringify(revision?.role_mapping ?? {}, null, 2),
    metadata_json: JSON.stringify(revision?.metadata ?? {}, null, 2),
  }
}

const parseJsonField = <T,>(
  value: string,
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
  const trimmed = value.trim()
  if (!trimmed) {
    return { value: emptyValue }
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown
    if (kind === 'array' && !Array.isArray(parsed)) {
      return { error: { field, message: 'Expected a JSON array.' } }
    }
    if (
      kind === 'object'
      && (parsed == null || typeof parsed !== 'object' || Array.isArray(parsed))
    ) {
      return { error: { field, message: 'Expected a JSON object.' } }
    }
    return { value: parsed as T }
  } catch (_error) {
    return { error: { field, message: 'Invalid JSON.' } }
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
  const decisions = parseJsonField<unknown[]>(values.decisions_json, {
    field: 'decisions_json',
    emptyValue: [],
    kind: 'array',
  })
  const parameters = parseJsonField<Record<string, unknown>>(values.parameters_json, {
    field: 'parameters_json',
    emptyValue: {},
    kind: 'object',
  })
  const roleMapping = parseJsonField<Record<string, unknown>>(values.role_mapping_json, {
    field: 'role_mapping_json',
    emptyValue: {},
    kind: 'object',
  })
  const metadata = parseJsonField<Record<string, unknown>>(values.metadata_json, {
    field: 'metadata_json',
    emptyValue: {},
    kind: 'object',
  })

  const errors = [decisions.error, parameters.error, roleMapping.error, metadata.error].filter(Boolean) as FormError[]
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
        decisions: decisions.value,
        parameters: parameters.value,
        role_mapping: roleMapping.value,
        metadata: metadata.value,
      },
    },
    errors: [],
  }
}

export const DEFAULT_BINDING_PROFILE_EDITOR_VALUES = buildBindingProfileEditorInitialValues(undefined)
export const DEFAULT_BINDING_PROFILE_DECISIONS_JSON = DEFAULT_DECISIONS_JSON
export const DEFAULT_BINDING_PROFILE_OBJECT_JSON = DEFAULT_OBJECT_JSON
