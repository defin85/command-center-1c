/**
 * Types for NewOperationWizard component.
 * Defines operation types, wizard state, and component props.
 */

import type { Database } from '../../../../api/generated/model/database'
import type { DriverCommandOperationConfig } from '../../../../components/driverCommands/DriverCommandBuilder'

/**
 * Available operation types categorized by their execution method
 */
export type OperationType =
  // RAS Operations - executed via RAS adapter
  | 'lock_scheduled_jobs'
  | 'unlock_scheduled_jobs'
  | 'block_sessions'
  | 'unblock_sessions'
  | 'terminate_sessions'
  // OData Operations - executed via OData protocol
  | 'create'
  | 'update'
  | 'delete'
  | 'query'
  // System Operations - internal system operations
  | 'sync_cluster'
  | 'health_check'
  // IBCMD Operations
  | 'ibcmd_backup'
  | 'ibcmd_restore'
  | 'ibcmd_replicate'
  | 'ibcmd_create'
  | 'ibcmd_load_cfg'
  | 'ibcmd_extension_update'
  | 'ibcmd_cli'
  // CLI Operations
  | 'designer_cli'

/**
 * Operation category for grouping in UI
 * 'custom' is used for user-defined workflow templates
 */
export type OperationCategory = 'ras' | 'odata' | 'system' | 'cli' | 'custom'

/**
 * Configuration for operation type display in UI
 */
export interface OperationTypeConfig {
  type: OperationType
  label: string
  description: string
  icon: string
  category: OperationCategory
  /** Whether this operation requires additional configuration in Step 3 */
  requiresConfig: boolean
}

/**
 * All available operation types with their display configuration
 */
export const OPERATION_TYPES: OperationTypeConfig[] = [
  // RAS Operations
  {
    type: 'lock_scheduled_jobs',
    label: 'Lock Scheduled Jobs',
    description: 'Prevent scheduled jobs from running',
    icon: 'LockOutlined',
    category: 'ras',
    requiresConfig: false,
  },
  {
    type: 'unlock_scheduled_jobs',
    label: 'Unlock Scheduled Jobs',
    description: 'Allow scheduled jobs to run',
    icon: 'UnlockOutlined',
    category: 'ras',
    requiresConfig: false,
  },
  {
    type: 'block_sessions',
    label: 'Block Sessions',
    description: 'Block new user connections',
    icon: 'StopOutlined',
    category: 'ras',
    requiresConfig: true,
  },
  {
    type: 'unblock_sessions',
    label: 'Unblock Sessions',
    description: 'Allow new user connections',
    icon: 'CheckCircleOutlined',
    category: 'ras',
    requiresConfig: false,
  },
  {
    type: 'terminate_sessions',
    label: 'Terminate Sessions',
    description: 'Disconnect active user sessions',
    icon: 'CloseCircleOutlined',
    category: 'ras',
    requiresConfig: true,
  },
  // CLI Operations
  {
    type: 'designer_cli',
    label: 'Designer CLI',
    description: 'Execute 1C DESIGNER batch command',
    icon: 'CodeOutlined',
    category: 'cli',
    requiresConfig: true,
  },
  // OData Operations
  {
    type: 'query',
    label: 'Execute Query',
    description: 'Run OData query on databases',
    icon: 'SearchOutlined',
    category: 'odata',
    requiresConfig: true,
  },
  // System Operations
  {
    type: 'sync_cluster',
    label: 'Sync Cluster',
    description: 'Synchronize cluster data with RAS',
    icon: 'SyncOutlined',
    category: 'system',
    requiresConfig: false,
  },
  {
    type: 'health_check',
    label: 'Health Check',
    description: 'Check database connectivity',
    icon: 'HeartOutlined',
    category: 'system',
    requiresConfig: false,
  },
]

/**
 * Category configuration for UI grouping
 */
export const OPERATION_CATEGORIES: Record<OperationCategory, { label: string; order: number }> = {
  ras: { label: 'RAS Operations', order: 1 },
  odata: { label: 'OData Operations', order: 2 },
  cli: { label: 'CLI Operations', order: 3 },
  system: { label: 'System Operations', order: 4 },
  custom: { label: 'Custom Templates', order: 5 },
}

/**
 * Data submitted when wizard completes
 */
export interface NewOperationData {
  /** Operation type for built-in operations, null for custom templates */
  operationType: OperationType | null
  databaseIds: string[]
  config: OperationConfig
  /** Template ID if using a custom workflow template */
  templateId?: string
  /** Uploaded file IDs for file fields in custom templates */
  uploadedFiles?: Record<string, string>
}

/**
 * Internal wizard state
 */
export interface WizardState {
  currentStep: number
  operationType: OperationType | null
  /** Selected custom template ID (null for built-in operations) */
  selectedTemplateId: string | null
  selectedDatabases: string[]
  config: OperationConfig
  /** Uploaded file IDs for file fields in custom templates */
  uploadedFiles: Record<string, string>
}

/**
 * Props for NewOperationWizard main component
 */
export interface NewOperationWizardProps {
  visible: boolean
  onClose: () => void
  onSubmit: (data: NewOperationData) => Promise<void>
  /** Pre-selected database IDs (e.g., from context menu) */
  preselectedDatabases?: string[]
}

/**
 * Props for SelectTypeStep component
 */
export interface SelectTypeStepProps {
  selectedType: OperationType | null
  /** Selected custom template ID (null for built-in operations) */
  selectedTemplateId: string | null
  onSelect: (type: OperationType) => void
  /** Callback when a custom template is selected */
  onSelectTemplate: (templateId: string | null) => void
}

/**
 * Props for SelectTargetStep component
 */
export interface SelectTargetStepProps {
  selectedDatabases: string[]
  onSelectionChange: (ids: string[]) => void
  onSelectionMetadataChange?: (databasesById: Record<string, string>) => void
  preselectedDatabases?: string[]
}

/**
 * Operation-specific configuration fields
 */
export interface OperationConfig {
  // RAS - block_sessions
  message?: string
  permission_code?: string
  denied_from?: string
  denied_to?: string
  parameter?: string
  // RAS - terminate_sessions
  filter_by_app?: string
  exclude_admin?: boolean
  // Designer CLI
  command?: string
  args?: string | string[]
  disable_startup_messages?: boolean
  disable_startup_dialogs?: boolean
  log_capture?: boolean
  log_path?: string
  log_no_truncate?: boolean
  cli_mode?: 'manual' | 'guided'
  cli_params?: Record<string, string | boolean>
  // OData - query
  entity?: string
  filter?: string
  select?: string
  top?: number
  // IBCMD
  ibcmd_mode?: 'guided' | 'manual'
  dbms?: string
  db_server?: string
  db_name?: string
  db_user?: string
  db_password?: string
  user?: string
  password?: string
  output_path?: string
  input_path?: string
  create_database?: boolean
  force?: boolean
  target_dbms?: string
  target_db_server?: string
  target_db_name?: string
  target_db_user?: string
  target_db_password?: string
  jobs_count?: number
  target_jobs_count?: number
  file?: string
  extension?: string
  name?: string
  active?: boolean
  safe_mode?: boolean
  scope?: 'infobase' | 'data-separation'
  security_profile_name?: string
  unsafe_action_protection?: boolean
  used_in_distributed_infobase?: boolean
  additional_args?: string[] | string
  stdin?: string
  // Schema-driven commands (cli + ibcmd)
  driver_command?: DriverCommandOperationConfig
  // Allow custom fields for workflow templates
  [key: string]: unknown
}

/**
 * Validation error from DynamicForm
 */
export interface DynamicFormValidationError {
  field: string
  message: string
  code: string
}

/**
 * Required fields by operation type
 */
export const REQUIRED_CONFIG_FIELDS: Partial<Record<OperationType, (keyof OperationConfig)[]>> = {
  query: ['entity'],
  block_sessions: ['message'],
}

/**
 * Props for ConfigureStep component
 */
export interface ConfigureStepProps {
  operationType: OperationType | null
  /** Template ID if using a custom workflow template */
  templateId: string | null
  /** Selected database IDs from Step 2 (used for global scope auth_database_id) */
  selectedDatabases: string[]
  /** Optional mapping for nicer labels */
  databaseNamesById?: Record<string, string>
  config: OperationConfig
  onConfigChange: (config: OperationConfig) => void
  /** Uploaded file IDs for file fields in custom templates */
  uploadedFiles?: Record<string, string>
  /** Callback when a file is uploaded in DynamicForm */
  onFileUpload?: (fieldName: string, fileId: string) => void
  /** Callback when a file is removed in DynamicForm */
  onFileRemove?: (fieldName: string) => void
  /** Callback when DynamicForm validation errors change */
  onValidationErrorsChange?: (errors: DynamicFormValidationError[]) => void
}

/**
 * Props for ReviewStep component
 */
export interface ReviewStepProps {
  operationType: OperationType | null
  selectedDatabases: string[]
  config: OperationConfig
  databases: Database[]
}

/**
 * Extended database type with cluster info for table display
 */
export interface DatabaseWithCluster extends Database {
  clusterName?: string
  clusterId?: string
}

/**
 * Filter state for database selection table
 */
export interface DatabaseFilters {
  search: string
  clusterId: string | null
  status: string | null
}
