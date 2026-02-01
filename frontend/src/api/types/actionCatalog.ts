export type ActionCatalogExecutor = {
  kind: 'ibcmd_cli' | 'designer_cli' | 'workflow' | string
  driver?: string
  command_id?: string
  workflow_id?: string
  mode?: 'guided' | 'manual' | string
  params?: Record<string, unknown>
  additional_args?: string[]
  stdin?: string
  fixed?: {
    timeout_seconds?: number
    confirm_dangerous?: boolean
  }
}

export type ActionCatalogAction = {
  id: string
  label: string
  contexts: string[]
  executor: ActionCatalogExecutor
}

