import { describe, expect, it } from 'vitest'

import type { ActionFormValues } from '../../Settings/actionCatalogTypes'
import { buildTemplateEditorValues, buildTemplateWritePayloadFromEditor } from '../templateEditorAdapter'

describe('templateEditorAdapter', () => {
  it('builds editor values from template payload', () => {
    const values = buildTemplateEditorValues({
      id: 'tpl-custom-1',
      name: 'Custom template',
      description: 'Template description',
      operation_type: 'designer_cli',
      target_entity: 'infobase',
      template_data: {
        command: 'infobase.extension.list',
        args: ['--format=json'],
        options: {
          disable_startup_messages: true,
          disable_startup_dialogs: false,
        },
        cli_mode: 'manual',
        cli_params: { force: true },
        stdin: '{"a":1}',
        fixed: {
          confirm_dangerous: true,
        },
        target_binding: {
          extension_name_param: 'extension_name',
        },
      },
      is_active: false,
      created_at: '2026-02-08T12:00:00Z',
      updated_at: '2026-02-08T12:00:00Z',
    })

    expect(values.id).toBe('tpl-custom-1')
    expect(values.name).toBe('Custom template')
    expect(values.description).toBe('Template description')
    expect(values.is_active).toBe(false)
    expect(values.executor.kind).toBe('designer_cli')
    expect(values.executor.command_id).toBe('infobase.extension.list')
    expect(values.executor.mode).toBe('manual')
    expect(values.executor.target_binding_extension_name_param).toBe('extension_name')
    expect(values.executor.fixed?.confirm_dangerous).toBe(true)
  })

  it('returns validation error when command is missing', () => {
    const values = buildTemplateEditorValues(null)
    values.name = 'No command'
    values.executor.command_id = '  '

    const result = buildTemplateWritePayloadFromEditor(values)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error).toBe('Command is required')
    }
  })

  it('serializes editor values to template write payload', () => {
    const values: ActionFormValues = {
      id: 'tpl-custom-2',
      name: 'Template 2',
      description: 'desc',
      is_active: true,
      capability: '',
      label: '',
      contexts: ['database_card'],
      executor: {
        kind: 'designer_cli',
        mode: 'guided',
        command_id: 'infobase.extension.update',
        params_json: '{"active":true}',
        additional_args: ['--force', '  ', '--timeout=30'],
        stdin: '',
        target_binding_extension_name_param: 'extension_name',
        fixed: {
          timeout_seconds: 120,
        },
      },
    }

    const result = buildTemplateWritePayloadFromEditor(values)
    expect(result.ok).toBe(true)
    if (!result.ok) return

    const payload = result.payload
    expect(payload.id).toBe('tpl-custom-2')
    expect(payload.operation_type).toBe('designer_cli')
    expect(payload.target_entity).toBe('infobase')
    expect(payload.template_data.command).toBe('infobase.extension.update')
    expect(payload.template_data.args).toEqual(['--force', '--timeout=30'])
    expect(payload.template_data.target_binding).toEqual({ extension_name_param: 'extension_name' })
    expect(payload.template_data.fixed).toEqual({ timeout_seconds: 120 })
    expect(payload.template_data.kind).toBe('designer_cli')
  })
})

