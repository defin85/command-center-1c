import type { OperationTemplate, OperationTemplateWrite } from '../../api/queries/templates'
import { driverCommandConfigToTemplateData, templateDataToDriverCommandConfig } from '../../lib/commandConfigAdapter'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import { isPlainObject, parseJson, safeJsonStringify } from '../Settings/actionCatalogUtils'

type TemplatePayloadBuildResult =
  | { ok: true; payload: OperationTemplateWrite }
  | { ok: false; error: string }

const EXECUTOR_KINDS = new Set(['ibcmd_cli', 'designer_cli', 'workflow'])

const normalizeExecutorKind = (value: unknown): ActionFormValues['executor']['kind'] => {
  const kind = typeof value === 'string' ? value.trim() : ''
  if (EXECUTOR_KINDS.has(kind)) {
    return kind as ActionFormValues['executor']['kind']
  }
  return 'ibcmd_cli'
}

const normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean)
}

const resolveCommandIdFromTemplateData = (templateData: Record<string, unknown>): string => {
  const commandId = typeof templateData.command_id === 'string' ? templateData.command_id.trim() : ''
  if (commandId) return commandId
  const legacyCommand = typeof templateData.command === 'string' ? templateData.command.trim() : ''
  return legacyCommand
}

const resolveWorkflowIdFromTemplateData = (templateData: Record<string, unknown>): string => {
  const workflowId = typeof templateData.workflow_id === 'string' ? templateData.workflow_id.trim() : ''
  return workflowId
}

const resolveModeFromTemplateData = (templateData: Record<string, unknown>): 'guided' | 'manual' => (
  templateData.mode === 'manual' || templateData.cli_mode === 'manual'
    ? 'manual'
    : 'guided'
)

const resolveParamsFromTemplateData = (templateData: Record<string, unknown>): Record<string, unknown> => {
  if (isPlainObject(templateData.params)) return templateData.params
  if (isPlainObject(templateData.input_context)) return templateData.input_context
  if (isPlainObject(templateData.cli_params)) return templateData.cli_params
  return {}
}

const resolveTargetBindingExtensionNameParam = (
  templateData: Record<string, unknown>,
  capabilityConfig: Record<string, unknown>
): string => {
  const templateTargetBinding = isPlainObject(templateData.target_binding)
    ? templateData.target_binding as Record<string, unknown>
    : {}
  const configTargetBinding = isPlainObject(capabilityConfig.target_binding)
    ? capabilityConfig.target_binding as Record<string, unknown>
    : {}
  const fromTemplate = typeof templateTargetBinding.extension_name_param === 'string'
    ? templateTargetBinding.extension_name_param.trim()
    : ''
  if (fromTemplate) return fromTemplate
  return typeof configTargetBinding.extension_name_param === 'string'
    ? configTargetBinding.extension_name_param.trim()
    : ''
}

const toFixedPayload = (value: unknown): ActionFormValues['executor']['fixed'] | undefined => (
  isPlainObject(value) ? value as ActionFormValues['executor']['fixed'] : undefined
)

export const buildTemplateEditorValues = (template: OperationTemplate | null): ActionFormValues => {
  if (!template) {
    return {
      id: '',
      name: '',
      description: '',
      is_active: true,
      capability: '',
      label: '',
      contexts: ['database_card'],
      executor: {
        kind: 'ibcmd_cli',
        mode: 'guided',
        command_id: '',
        workflow_id: '',
        params_json: '{}',
        additional_args: [],
        stdin: '',
        target_binding_extension_name_param: '',
      },
    }
  }

  const templateData = isPlainObject(template.template_data) ? template.template_data : {}
  const capabilityConfig = isPlainObject(template.capability_config) ? template.capability_config : {}
  const executorKind = normalizeExecutorKind(template.executor_kind || template.operation_type || templateData.kind)
  const commandConfig = templateDataToDriverCommandConfig(templateData)
  const commandId = resolveCommandIdFromTemplateData(templateData)
  const workflowId = resolveWorkflowIdFromTemplateData(templateData)
  const mode = resolveModeFromTemplateData(templateData)
  const paramsObject = resolveParamsFromTemplateData(templateData)
  const additionalArgs = commandConfig.resolved_args && commandConfig.resolved_args.length > 0
    ? normalizeStringList(commandConfig.resolved_args)
    : normalizeStringList(templateData.additional_args || templateData.args)
  const stdin = typeof templateData.stdin === 'string'
    ? templateData.stdin
    : typeof commandConfig.stdin === 'string'
      ? commandConfig.stdin
      : ''
  const fixed = toFixedPayload(templateData.fixed)
  const targetBindingExtensionNameParam = resolveTargetBindingExtensionNameParam(templateData, capabilityConfig)

  return {
    id: template.id,
    name: template.name,
    description: template.description || '',
    is_active: template.is_active,
    capability: typeof template.capability === 'string' ? template.capability : '',
    label: '',
    contexts: ['database_card'],
    executor: {
      kind: executorKind,
      mode,
      command_id: executorKind === 'workflow' ? '' : commandId,
      workflow_id: executorKind === 'workflow' ? workflowId : '',
      params_json: safeJsonStringify(paramsObject),
      additional_args: additionalArgs,
      stdin,
      target_binding_extension_name_param: targetBindingExtensionNameParam,
      fixed,
    },
  }
}

export const buildTemplateWritePayloadFromEditor = (
  values: ActionFormValues,
  opts: { existingId?: string | null } = {}
): TemplatePayloadBuildResult => {
  const executorKind = normalizeExecutorKind(values.executor.kind)
  const name = (values.name || '').trim()
  if (!name) {
    return { ok: false, error: 'Name is required' }
  }

  const parsedParams = parseJson(typeof values.executor.params_json === 'string' ? values.executor.params_json : '{}')
  const params = isPlainObject(parsedParams) ? parsedParams : {}
  const additionalArgs = Array.isArray(values.executor.additional_args)
    ? values.executor.additional_args.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : []
  const fixed = toFixedPayload(values.executor.fixed)
  const stdin = typeof values.executor.stdin === 'string' ? values.executor.stdin : ''
  const targetBindingExtensionNameParam = typeof values.executor.target_binding_extension_name_param === 'string'
    ? values.executor.target_binding_extension_name_param.trim()
    : ''
  const capability = typeof values.capability === 'string' ? values.capability.trim() : ''

  const templateData: Record<string, unknown> = {}
  if (fixed) {
    templateData.fixed = fixed
  }
  if (targetBindingExtensionNameParam) {
    templateData.target_binding = { extension_name_param: targetBindingExtensionNameParam }
  }

  if (executorKind === 'workflow') {
    const workflowId = typeof values.executor.workflow_id === 'string' ? values.executor.workflow_id.trim() : ''
    if (!workflowId) {
      return { ok: false, error: 'Workflow is required' }
    }
    templateData.kind = 'workflow'
    templateData.workflow_id = workflowId
    templateData.input_context = params
  } else {
    const command = typeof values.executor.command_id === 'string' ? values.executor.command_id.trim() : ''
    if (!command) {
      return { ok: false, error: 'Command is required' }
    }

    const driver = executorKind === 'designer_cli' ? 'cli' : 'ibcmd'
    const mode = values.executor.mode === 'manual' ? 'manual' : 'guided'
    const legacyTemplateData = driverCommandConfigToTemplateData({
      driver,
      mode,
      command_id: command,
      params,
      resolved_args: additionalArgs,
      stdin,
    })
    Object.assign(templateData, legacyTemplateData)
    templateData.kind = executorKind
    templateData.driver = driver
    templateData.command_id = command
    templateData.mode = mode
    templateData.params = params
    templateData.additional_args = additionalArgs
    templateData.stdin = stdin
  }

  const capabilityConfig: Record<string, unknown> = {}
  if (capability === 'extensions.set_flags' && targetBindingExtensionNameParam) {
    capabilityConfig.target_binding = { extension_name_param: targetBindingExtensionNameParam }
  }

  return {
    ok: true,
    payload: {
      id: (values.id || '').trim() || opts.existingId || undefined,
      name,
      description: values.description || '',
      operation_type: executorKind,
      target_entity: 'infobase',
      capability,
      capability_config: capabilityConfig,
      template_data: templateData,
      is_active: values.is_active !== false,
    },
  }
}
