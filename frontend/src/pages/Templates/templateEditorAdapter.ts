import type { OperationTemplate, OperationTemplateWrite } from '../../api/queries/templates'
import { driverCommandConfigToTemplateData, templateDataToDriverCommandConfig } from '../../lib/commandConfigAdapter'
import type { ActionFormValues } from '../Settings/actionCatalogTypes'
import { isPlainObject, parseJson, safeJsonStringify } from '../Settings/actionCatalogUtils'

type TemplatePayloadBuildResult =
  | { ok: true; payload: OperationTemplateWrite }
  | { ok: false; error: string }

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
        kind: 'designer_cli',
        mode: 'guided',
        command_id: '',
        params_json: '{}',
        additional_args: [],
        stdin: '',
        target_binding_extension_name_param: '',
      },
    }
  }

  const commandConfig = templateDataToDriverCommandConfig(template.template_data)
  const fixed = isPlainObject(template.template_data.fixed)
    ? template.template_data.fixed as ActionFormValues['executor']['fixed']
    : undefined
  const targetBinding = isPlainObject(template.template_data.target_binding)
    ? template.template_data.target_binding as Record<string, unknown>
    : {}
  const targetBindingExtensionNameParam = typeof targetBinding.extension_name_param === 'string'
    ? targetBinding.extension_name_param
    : ''

  return {
    id: template.id,
    name: template.name,
    description: template.description || '',
    is_active: template.is_active,
    capability: '',
    label: '',
    contexts: ['database_card'],
    executor: {
      kind: 'designer_cli',
      mode: commandConfig.mode === 'manual' ? 'manual' : 'guided',
      command_id: typeof commandConfig.command_id === 'string' ? commandConfig.command_id : '',
      params_json: safeJsonStringify(isPlainObject(commandConfig.params) ? commandConfig.params : {}),
      additional_args: Array.isArray(commandConfig.resolved_args)
        ? commandConfig.resolved_args.filter((item): item is string => typeof item === 'string')
        : [],
      stdin: typeof commandConfig.stdin === 'string' ? commandConfig.stdin : '',
      target_binding_extension_name_param: targetBindingExtensionNameParam,
      fixed,
    },
  }
}

export const buildTemplateWritePayloadFromEditor = (
  values: ActionFormValues,
  opts: { existingId?: string | null } = {}
): TemplatePayloadBuildResult => {
  const name = (values.name || '').trim()
  if (!name) {
    return { ok: false, error: 'Name is required' }
  }

  const command = typeof values.executor.command_id === 'string' ? values.executor.command_id.trim() : ''
  if (!command) {
    return { ok: false, error: 'Command is required' }
  }

  const parsedParams = parseJson(typeof values.executor.params_json === 'string' ? values.executor.params_json : '{}')
  const params = isPlainObject(parsedParams) ? parsedParams : {}
  const additionalArgs = Array.isArray(values.executor.additional_args)
    ? values.executor.additional_args.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : []

  const templateData = driverCommandConfigToTemplateData({
    driver: 'cli',
    mode: values.executor.mode === 'manual' ? 'manual' : 'guided',
    command_id: command,
    params,
    resolved_args: additionalArgs,
    stdin: typeof values.executor.stdin === 'string' ? values.executor.stdin : '',
  })

  if (isPlainObject(values.executor.fixed)) {
    templateData.fixed = values.executor.fixed
  } else {
    delete templateData.fixed
  }

  const targetBindingExtensionNameParam = typeof values.executor.target_binding_extension_name_param === 'string'
    ? values.executor.target_binding_extension_name_param.trim()
    : ''
  if (targetBindingExtensionNameParam) {
    templateData.target_binding = { extension_name_param: targetBindingExtensionNameParam }
  } else {
    delete templateData.target_binding
  }
  templateData.kind = 'designer_cli'

  return {
    ok: true,
    payload: {
      id: (values.id || '').trim() || opts.existingId || undefined,
      name,
      description: values.description || '',
      operation_type: 'designer_cli',
      target_entity: 'infobase',
      template_data: templateData,
      is_active: values.is_active !== false,
    },
  }
}

