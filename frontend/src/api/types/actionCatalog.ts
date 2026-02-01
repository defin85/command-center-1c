export type ActionCatalogExecutor = {
  kind: 'ibcmd_cli' | 'designer_cli' | 'workflow' | string
  driver?: string
  command_id?: string
  workflow_id?: string
  mode?: 'guided' | 'manual' | string
  // Optional executor-level connection override (used by some ibcmd_cli executors).
  // Kept generic because Action Catalog is a UI-provided contract.
  connection?: Record<string, unknown>
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
