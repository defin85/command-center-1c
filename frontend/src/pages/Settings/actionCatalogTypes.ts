import type { DriverName } from '../../api/driverCommands'

export type ActionCatalogMode = 'guided' | 'raw'

export type ActionRow = {
  pos: number
  id: string
  capability?: string
  label: string
  contexts: string[]
  executor_kind: string
  driver?: string
  command_id?: string
  workflow_id?: string
}

export type ActionContext = 'database_card' | 'bulk_page'
export type ExecutorKind = 'ibcmd_cli' | 'designer_cli' | 'workflow'

export type PlainObject = Record<string, unknown>
type ActionFixedValue = string | number | boolean | PlainObject | unknown[] | undefined

export type DiffKind = 'added' | 'removed' | 'changed'

export type DiffItem = {
  path: string
  kind: DiffKind
  before?: unknown
  after?: unknown
}

export type SaveErrorHint = {
  message: string
  action_pos?: number
  action_id?: string
}

export type ActionFormValues = {
  id: string
  name?: string
  description?: string
  is_active?: boolean
  capability?: string
  label: string
  contexts: ActionContext[]
  executor: {
    kind: ExecutorKind
    driver?: DriverName
    command_id?: string
    workflow_id?: string
    mode?: 'guided' | 'manual'
    params_json?: string
    additional_args?: string[]
    stdin?: string
    target_binding_extension_name_param?: string
    fixed?: {
      confirm_dangerous?: boolean
      timeout_seconds?: number
      [key: string]: ActionFixedValue
    }
  }
}
