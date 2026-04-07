export { queryKeys } from './queryKeys'
export type { OperationFilters, DatabaseFilters, ClusterFilters, ArtifactFilters } from './types'

// Re-export hooks for convenience
export { useDashboardQuery } from './dashboard'
export {
  useOperations,
  useOperation,
  useCancelOperation,
  fetchOperations,
  fetchOperation,
  cancelOperation,
} from './operations'

export {
  useOperationTemplates,
  useSyncTemplatesFromRegistry,
  useCreateTemplate,
  useUpdateTemplate,
  useDeleteTemplate,
} from './templates'
export { useShellBootstrap } from './shellBootstrap'
export { useMe } from './me'
export { useDlqMessage, useDlqMessages, useRetryDlqMessage } from './dlq'
export { useTableMetadata } from './ui'
export { useUser, useUsers, useCreateUser, useUpdateUser, useSetUserPassword } from './users'
export type { UserSummary } from './users'
export { useExtensionsOverview, useExtensionsOverviewDatabases } from './extensions'
export {
  useManualOperationBindings,
  useUpsertManualOperationBinding,
  useDeleteManualOperationBinding,
} from './extensionsManualOperations'
export {
  useInfobaseUsers,
  useCreateInfobaseUser,
  useUpdateInfobaseUser,
  useDeleteInfobaseUser,
  useSetInfobaseUserPassword,
  useResetInfobaseUserPassword,
  useDbmsUsers,
  useCreateDbmsUser,
  useUpdateDbmsUser,
  useDeleteDbmsUser,
  useSetDbmsUserPassword,
  useResetDbmsUserPassword,
} from './databases'
export {
  useArtifacts,
  useArtifact,
  useArtifactVersions,
  useArtifactAliases,
  useUpsertArtifactAlias,
  useDeleteArtifact,
  useRestoreArtifact,
  usePurgeArtifact,
  useArtifactPurgeJob,
} from './artifacts'

export { useDriverCommands } from './driverCommands'
export { useDriverCommandShortcuts, useCreateDriverCommandShortcut, useDeleteDriverCommandShortcut } from './commandShortcuts'
export { useCanManageDriverCatalogs } from './commandSchemas'
export { useMyTenants, useSetActiveTenant } from './tenants'
