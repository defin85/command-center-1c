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
export { useMe } from './me'
export { useDlqMessages, useRetryDlqMessage } from './dlq'
export { useTableMetadata, useActionCatalog } from './ui'
export { useUsers, useCreateUser, useUpdateUser, useSetUserPassword } from './users'
export type { UserSummary } from './users'
export { useExtensionsOverview, useExtensionsOverviewDatabases } from './extensions'
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
