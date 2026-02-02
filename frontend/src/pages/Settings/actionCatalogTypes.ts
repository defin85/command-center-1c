import type { DriverName } from '../../api/driverCommands'

export type ActionCatalogMode = 'guided' | 'raw'

export type ActionRow = {
  pos: number
  id: string
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
    fixed?: {
      confirm_dangerous?: boolean
      timeout_seconds?: number
    }
  }
}
