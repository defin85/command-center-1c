import type { DriverCommandRiskLevel, DriverCommandScope, DriverName } from '../../../api/driverCommands'

export type DriverCommandBuilderMode = 'guided' | 'manual'

export interface IbcmdCliConnectionOffline {
  config?: string
  data?: string
  dbms?: string
  db_server?: string
  db_name?: string
  db_path?: string
  db_user?: string
  db_pwd?: string
  ftext2_data?: string
  ftext_data?: string
  lock?: string
  log_data?: string
  openid_data?: string
  session_data?: string
  stt_data?: string
  system?: string
  temp?: string
  users_data?: string
}

export interface IbcmdCliConnection {
  remote?: string
  pid?: number | null
  offline?: IbcmdCliConnectionOffline
}

export interface IbcmdIbAuth {
  strategy?: 'actor' | 'service' | 'none'
}

export interface IbcmdDbmsAuth {
  strategy?: 'actor' | 'service'
}

export interface CliExtraOptions {
  disable_startup_messages?: boolean
  disable_startup_dialogs?: boolean
  log_capture?: boolean
  log_path?: string
  log_no_truncate?: boolean
}

export interface DriverCommandOperationConfig {
  driver: DriverName
  mode?: DriverCommandBuilderMode
  command_id?: string
  command_label?: string
  command_scope?: DriverCommandScope
  command_risk_level?: DriverCommandRiskLevel
  params?: Record<string, unknown>
  args_text?: string
  /** Precomputed args list for CLI execution/template payloads */
  resolved_args?: string[]
  confirm_dangerous?: boolean

  // IBCMD-only execution context
  /** For per_database: when false/undefined, connection is derived from database profiles. */
  connection_override?: boolean
  connection?: IbcmdCliConnection
  ib_auth?: IbcmdIbAuth
  dbms_auth?: IbcmdDbmsAuth
  stdin?: string
  timeout_seconds?: number
  auth_database_id?: string

  // CLI-only options
  cli_options?: CliExtraOptions
}
