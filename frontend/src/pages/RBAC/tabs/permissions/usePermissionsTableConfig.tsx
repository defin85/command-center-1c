import type { ColumnsType } from 'antd/es/table'

import type { ClusterPermission } from '../../../../api/generated/model/clusterPermission'
import type { DatabasePermission } from '../../../../api/generated/model/databasePermission'
import {
  useArtifactGroupPermissions,
  useArtifactPermissions,
  useClusterGroupPermissions,
  useClusterPermissions,
  useDatabaseGroupPermissions,
  useDatabasePermissions,
  useOperationTemplateGroupPermissions,
  useOperationTemplatePermissions,
  useWorkflowTemplateGroupPermissions,
  useWorkflowTemplatePermissions,
  type ArtifactGroupPermission,
  type ArtifactPermission,
  type ClusterGroupPermission,
  type DatabaseGroupPermission,
  type OperationTemplateGroupPermission,
  type OperationTemplatePermission,
  type WorkflowTemplateGroupPermission,
  type WorkflowTemplatePermission,
} from '../../../../api/queries/rbac'
import type { RbacPermissionsListState, RbacPermissionsResourceKey } from './types'

export type TableConfig<TKind extends string, TRow> = {
  kind: TKind
  columns: ColumnsType<TRow>
  rows: TRow[]
  total: number
  loading: boolean
  fetching: boolean
  error: unknown
  rowKey: (row: TRow) => string
  refetch: () => void
}

export type PermissionsTableConfig =
  | TableConfig<'clusters/user', ClusterPermission>
  | TableConfig<'clusters/role', ClusterGroupPermission>
  | TableConfig<'databases/user', DatabasePermission>
  | TableConfig<'databases/role', DatabaseGroupPermission>
  | TableConfig<'operation-templates/user', OperationTemplatePermission>
  | TableConfig<'operation-templates/role', OperationTemplateGroupPermission>
  | TableConfig<'workflow-templates/user', WorkflowTemplatePermission>
  | TableConfig<'workflow-templates/role', WorkflowTemplateGroupPermission>
  | TableConfig<'artifacts/user', ArtifactPermission>
  | TableConfig<'artifacts/role', ArtifactGroupPermission>

export function usePermissionsTableConfig(params: {
  enabled: boolean
  resourceKey: RbacPermissionsResourceKey
  principalType: 'user' | 'role'
  list: RbacPermissionsListState
  debouncedSearch: string
  columns: {
    clusterColumns: ColumnsType<ClusterPermission>
    databaseColumns: ColumnsType<DatabasePermission>
    clusterGroupColumns: ColumnsType<ClusterGroupPermission>
    databaseGroupColumns: ColumnsType<DatabaseGroupPermission>
    operationTemplateUserColumns: ColumnsType<OperationTemplatePermission>
    operationTemplateGroupColumns: ColumnsType<OperationTemplateGroupPermission>
    workflowTemplateUserColumns: ColumnsType<WorkflowTemplatePermission>
    workflowTemplateGroupColumns: ColumnsType<WorkflowTemplateGroupPermission>
    artifactUserColumns: ColumnsType<ArtifactPermission>
    artifactGroupColumns: ColumnsType<ArtifactGroupPermission>
  }
}): PermissionsTableConfig {
  const { enabled, resourceKey, principalType, list, debouncedSearch, columns } = params

  const offset = (list.page - 1) * list.pageSize
  const search = debouncedSearch || undefined

  const clustersUserQuery = useClusterPermissions({
    user_id: list.principal_id,
    cluster_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'user' && resourceKey === 'clusters',
  })

  const clustersRoleQuery = useClusterGroupPermissions({
    group_id: list.principal_id,
    cluster_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'role' && resourceKey === 'clusters',
  })

  const databasesUserQuery = useDatabasePermissions({
    user_id: list.principal_id,
    database_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'user' && resourceKey === 'databases',
  })

  const databasesRoleQuery = useDatabaseGroupPermissions({
    group_id: list.principal_id,
    database_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'role' && resourceKey === 'databases',
  })

  const operationTemplatesUserQuery = useOperationTemplatePermissions({
    user_id: list.principal_id,
    template_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'user' && resourceKey === 'operation-templates',
  })

  const operationTemplatesRoleQuery = useOperationTemplateGroupPermissions({
    group_id: list.principal_id,
    template_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'role' && resourceKey === 'operation-templates',
  })

  const workflowTemplatesUserQuery = useWorkflowTemplatePermissions({
    user_id: list.principal_id,
    template_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'user' && resourceKey === 'workflow-templates',
  })

  const workflowTemplatesRoleQuery = useWorkflowTemplateGroupPermissions({
    group_id: list.principal_id,
    template_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'role' && resourceKey === 'workflow-templates',
  })

  const artifactsUserQuery = useArtifactPermissions({
    user_id: list.principal_id,
    artifact_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'user' && resourceKey === 'artifacts',
  })

  const artifactsRoleQuery = useArtifactGroupPermissions({
    group_id: list.principal_id,
    artifact_id: list.resource_id,
    level: list.level,
    search,
    limit: list.pageSize,
    offset,
  }, {
    enabled: enabled && principalType === 'role' && resourceKey === 'artifacts',
  })

  if (resourceKey === 'clusters' && principalType === 'user') {
    const rows = clustersUserQuery.data?.permissions ?? []
    const total = typeof clustersUserQuery.data?.total === 'number'
      ? clustersUserQuery.data.total
      : rows.length
    return {
      kind: 'clusters/user',
      columns: columns.clusterColumns,
      rows,
      total,
      loading: clustersUserQuery.isLoading,
      fetching: clustersUserQuery.isFetching,
      error: clustersUserQuery.error,
      rowKey: (row) => `${row.user.id}:${row.cluster.id}`,
      refetch: () => { clustersUserQuery.refetch() },
    }
  }

  if (resourceKey === 'clusters' && principalType === 'role') {
    const rows = clustersRoleQuery.data?.permissions ?? []
    const total = typeof clustersRoleQuery.data?.total === 'number'
      ? clustersRoleQuery.data.total
      : rows.length
    return {
      kind: 'clusters/role',
      columns: columns.clusterGroupColumns,
      rows,
      total,
      loading: clustersRoleQuery.isLoading,
      fetching: clustersRoleQuery.isFetching,
      error: clustersRoleQuery.error,
      rowKey: (row) => `${row.group.id}:${row.cluster.id}`,
      refetch: () => { clustersRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'databases' && principalType === 'user') {
    const rows = databasesUserQuery.data?.permissions ?? []
    const total = typeof databasesUserQuery.data?.total === 'number'
      ? databasesUserQuery.data.total
      : rows.length
    return {
      kind: 'databases/user',
      columns: columns.databaseColumns,
      rows,
      total,
      loading: databasesUserQuery.isLoading,
      fetching: databasesUserQuery.isFetching,
      error: databasesUserQuery.error,
      rowKey: (row) => `${row.user.id}:${row.database.id}`,
      refetch: () => { databasesUserQuery.refetch() },
    }
  }

  if (resourceKey === 'databases' && principalType === 'role') {
    const rows = databasesRoleQuery.data?.permissions ?? []
    const total = typeof databasesRoleQuery.data?.total === 'number'
      ? databasesRoleQuery.data.total
      : rows.length
    return {
      kind: 'databases/role',
      columns: columns.databaseGroupColumns,
      rows,
      total,
      loading: databasesRoleQuery.isLoading,
      fetching: databasesRoleQuery.isFetching,
      error: databasesRoleQuery.error,
      rowKey: (row) => `${row.group.id}:${row.database.id}`,
      refetch: () => { databasesRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'operation-templates' && principalType === 'user') {
    const rows = operationTemplatesUserQuery.data?.permissions ?? []
    const total = typeof operationTemplatesUserQuery.data?.total === 'number'
      ? operationTemplatesUserQuery.data.total
      : rows.length
    return {
      kind: 'operation-templates/user',
      columns: columns.operationTemplateUserColumns,
      rows,
      total,
      loading: operationTemplatesUserQuery.isLoading,
      fetching: operationTemplatesUserQuery.isFetching,
      error: operationTemplatesUserQuery.error,
      rowKey: (row) => `${row.user.id}:${row.template.id}`,
      refetch: () => { operationTemplatesUserQuery.refetch() },
    }
  }

  if (resourceKey === 'operation-templates' && principalType === 'role') {
    const rows = operationTemplatesRoleQuery.data?.permissions ?? []
    const total = typeof operationTemplatesRoleQuery.data?.total === 'number'
      ? operationTemplatesRoleQuery.data.total
      : rows.length
    return {
      kind: 'operation-templates/role',
      columns: columns.operationTemplateGroupColumns,
      rows,
      total,
      loading: operationTemplatesRoleQuery.isLoading,
      fetching: operationTemplatesRoleQuery.isFetching,
      error: operationTemplatesRoleQuery.error,
      rowKey: (row) => `${row.group.id}:${row.template.id}`,
      refetch: () => { operationTemplatesRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'workflow-templates' && principalType === 'user') {
    const rows = workflowTemplatesUserQuery.data?.permissions ?? []
    const total = typeof workflowTemplatesUserQuery.data?.total === 'number'
      ? workflowTemplatesUserQuery.data.total
      : rows.length
    return {
      kind: 'workflow-templates/user',
      columns: columns.workflowTemplateUserColumns,
      rows,
      total,
      loading: workflowTemplatesUserQuery.isLoading,
      fetching: workflowTemplatesUserQuery.isFetching,
      error: workflowTemplatesUserQuery.error,
      rowKey: (row) => `${row.user.id}:${row.template.id}`,
      refetch: () => { workflowTemplatesUserQuery.refetch() },
    }
  }

  if (resourceKey === 'workflow-templates' && principalType === 'role') {
    const rows = workflowTemplatesRoleQuery.data?.permissions ?? []
    const total = typeof workflowTemplatesRoleQuery.data?.total === 'number'
      ? workflowTemplatesRoleQuery.data.total
      : rows.length
    return {
      kind: 'workflow-templates/role',
      columns: columns.workflowTemplateGroupColumns,
      rows,
      total,
      loading: workflowTemplatesRoleQuery.isLoading,
      fetching: workflowTemplatesRoleQuery.isFetching,
      error: workflowTemplatesRoleQuery.error,
      rowKey: (row) => `${row.group.id}:${row.template.id}`,
      refetch: () => { workflowTemplatesRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'artifacts' && principalType === 'user') {
    const rows = artifactsUserQuery.data?.permissions ?? []
    const total = typeof artifactsUserQuery.data?.total === 'number'
      ? artifactsUserQuery.data.total
      : rows.length
    return {
      kind: 'artifacts/user',
      columns: columns.artifactUserColumns,
      rows,
      total,
      loading: artifactsUserQuery.isLoading,
      fetching: artifactsUserQuery.isFetching,
      error: artifactsUserQuery.error,
      rowKey: (row) => `${row.user.id}:${row.artifact.id}`,
      refetch: () => { artifactsUserQuery.refetch() },
    }
  }

  const rows = artifactsRoleQuery.data?.permissions ?? []
  const total = typeof artifactsRoleQuery.data?.total === 'number'
    ? artifactsRoleQuery.data.total
    : rows.length
  return {
    kind: 'artifacts/role',
    columns: columns.artifactGroupColumns,
    rows,
    total,
    loading: artifactsRoleQuery.isLoading,
    fetching: artifactsRoleQuery.isFetching,
    error: artifactsRoleQuery.error,
    rowKey: (row) => `${row.group.id}:${row.artifact.id}`,
    refetch: () => { artifactsRoleQuery.refetch() },
  }
}
