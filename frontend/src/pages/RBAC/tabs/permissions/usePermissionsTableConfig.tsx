import type { ColumnsType } from 'antd/es/table'

import { useArtifactGroupPermissions, useArtifactPermissions, useClusterGroupPermissions, useClusterPermissions, useDatabaseGroupPermissions, useDatabasePermissions, useOperationTemplateGroupPermissions, useOperationTemplatePermissions, useWorkflowTemplateGroupPermissions, useWorkflowTemplatePermissions } from '../../../../api/queries/rbac'
import type { RbacPermissionsListState, RbacPermissionsResourceKey, RbacPermissionsTableConfig, PermissionsTableRow } from './types'

export function usePermissionsTableConfig(params: {
  enabled: boolean
  resourceKey: RbacPermissionsResourceKey
  principalType: 'user' | 'role'
  list: RbacPermissionsListState
  debouncedSearch: string
  columns: {
    clusterColumns: ColumnsType<any>
    databaseColumns: ColumnsType<any>
    clusterGroupColumns: ColumnsType<any>
    databaseGroupColumns: ColumnsType<any>
    operationTemplateUserColumns: ColumnsType<any>
    operationTemplateGroupColumns: ColumnsType<any>
    workflowTemplateUserColumns: ColumnsType<any>
    workflowTemplateGroupColumns: ColumnsType<any>
    artifactUserColumns: ColumnsType<any>
    artifactGroupColumns: ColumnsType<any>
  }
}): RbacPermissionsTableConfig {
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
      columns: columns.clusterColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: clustersUserQuery.isLoading,
      fetching: clustersUserQuery.isFetching,
      error: clustersUserQuery.error,
      rowKey: (row) => {
        const record = row as { user?: { id?: number | null }; cluster?: { id?: string | null } }
        return `${record.user?.id}:${record.cluster?.id}`
      },
      refetch: () => { clustersUserQuery.refetch() },
    }
  }

  if (resourceKey === 'clusters' && principalType === 'role') {
    const rows = clustersRoleQuery.data?.permissions ?? []
    const total = typeof clustersRoleQuery.data?.total === 'number'
      ? clustersRoleQuery.data.total
      : rows.length
    return {
      columns: columns.clusterGroupColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: clustersRoleQuery.isLoading,
      fetching: clustersRoleQuery.isFetching,
      error: clustersRoleQuery.error,
      rowKey: (row) => {
        const record = row as { group?: { id?: number | null }; cluster?: { id?: string | null } }
        return `${record.group?.id}:${record.cluster?.id}`
      },
      refetch: () => { clustersRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'databases' && principalType === 'user') {
    const rows = databasesUserQuery.data?.permissions ?? []
    const total = typeof databasesUserQuery.data?.total === 'number'
      ? databasesUserQuery.data.total
      : rows.length
    return {
      columns: columns.databaseColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: databasesUserQuery.isLoading,
      fetching: databasesUserQuery.isFetching,
      error: databasesUserQuery.error,
      rowKey: (row) => {
        const record = row as { user?: { id?: number | null }; database?: { id?: string | null } }
        return `${record.user?.id}:${record.database?.id}`
      },
      refetch: () => { databasesUserQuery.refetch() },
    }
  }

  if (resourceKey === 'databases' && principalType === 'role') {
    const rows = databasesRoleQuery.data?.permissions ?? []
    const total = typeof databasesRoleQuery.data?.total === 'number'
      ? databasesRoleQuery.data.total
      : rows.length
    return {
      columns: columns.databaseGroupColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: databasesRoleQuery.isLoading,
      fetching: databasesRoleQuery.isFetching,
      error: databasesRoleQuery.error,
      rowKey: (row) => {
        const record = row as { group?: { id?: number | null }; database?: { id?: string | null } }
        return `${record.group?.id}:${record.database?.id}`
      },
      refetch: () => { databasesRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'operation-templates' && principalType === 'user') {
    const rows = operationTemplatesUserQuery.data?.permissions ?? []
    const total = typeof operationTemplatesUserQuery.data?.total === 'number'
      ? operationTemplatesUserQuery.data.total
      : rows.length
    return {
      columns: columns.operationTemplateUserColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: operationTemplatesUserQuery.isLoading,
      fetching: operationTemplatesUserQuery.isFetching,
      error: operationTemplatesUserQuery.error,
      rowKey: (row) => {
        const record = row as { user?: { id?: number | null }; template?: { id?: string | null } }
        return `${record.user?.id}:${record.template?.id}`
      },
      refetch: () => { operationTemplatesUserQuery.refetch() },
    }
  }

  if (resourceKey === 'operation-templates' && principalType === 'role') {
    const rows = operationTemplatesRoleQuery.data?.permissions ?? []
    const total = typeof operationTemplatesRoleQuery.data?.total === 'number'
      ? operationTemplatesRoleQuery.data.total
      : rows.length
    return {
      columns: columns.operationTemplateGroupColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: operationTemplatesRoleQuery.isLoading,
      fetching: operationTemplatesRoleQuery.isFetching,
      error: operationTemplatesRoleQuery.error,
      rowKey: (row) => {
        const record = row as { group?: { id?: number | null }; template?: { id?: string | null } }
        return `${record.group?.id}:${record.template?.id}`
      },
      refetch: () => { operationTemplatesRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'workflow-templates' && principalType === 'user') {
    const rows = workflowTemplatesUserQuery.data?.permissions ?? []
    const total = typeof workflowTemplatesUserQuery.data?.total === 'number'
      ? workflowTemplatesUserQuery.data.total
      : rows.length
    return {
      columns: columns.workflowTemplateUserColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: workflowTemplatesUserQuery.isLoading,
      fetching: workflowTemplatesUserQuery.isFetching,
      error: workflowTemplatesUserQuery.error,
      rowKey: (row) => {
        const record = row as { user?: { id?: number | null }; template?: { id?: string | null } }
        return `${record.user?.id}:${record.template?.id}`
      },
      refetch: () => { workflowTemplatesUserQuery.refetch() },
    }
  }

  if (resourceKey === 'workflow-templates' && principalType === 'role') {
    const rows = workflowTemplatesRoleQuery.data?.permissions ?? []
    const total = typeof workflowTemplatesRoleQuery.data?.total === 'number'
      ? workflowTemplatesRoleQuery.data.total
      : rows.length
    return {
      columns: columns.workflowTemplateGroupColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: workflowTemplatesRoleQuery.isLoading,
      fetching: workflowTemplatesRoleQuery.isFetching,
      error: workflowTemplatesRoleQuery.error,
      rowKey: (row) => {
        const record = row as { group?: { id?: number | null }; template?: { id?: string | null } }
        return `${record.group?.id}:${record.template?.id}`
      },
      refetch: () => { workflowTemplatesRoleQuery.refetch() },
    }
  }

  if (resourceKey === 'artifacts' && principalType === 'user') {
    const rows = artifactsUserQuery.data?.permissions ?? []
    const total = typeof artifactsUserQuery.data?.total === 'number'
      ? artifactsUserQuery.data.total
      : rows.length
    return {
      columns: columns.artifactUserColumns as unknown as ColumnsType<PermissionsTableRow>,
      rows: rows as unknown as PermissionsTableRow[],
      total,
      loading: artifactsUserQuery.isLoading,
      fetching: artifactsUserQuery.isFetching,
      error: artifactsUserQuery.error,
      rowKey: (row) => {
        const record = row as { user?: { id?: number | null }; artifact?: { id?: string | null } }
        return `${record.user?.id}:${record.artifact?.id}`
      },
      refetch: () => { artifactsUserQuery.refetch() },
    }
  }

  const rows = artifactsRoleQuery.data?.permissions ?? []
  const total = typeof artifactsRoleQuery.data?.total === 'number'
    ? artifactsRoleQuery.data.total
    : rows.length
  return {
    columns: columns.artifactGroupColumns as unknown as ColumnsType<PermissionsTableRow>,
    rows: rows as unknown as PermissionsTableRow[],
    total,
    loading: artifactsRoleQuery.isLoading,
    fetching: artifactsRoleQuery.isFetching,
    error: artifactsRoleQuery.error,
    rowKey: (row) => {
      const record = row as { group?: { id?: number | null }; artifact?: { id?: string | null } }
      return `${record.group?.id}:${record.artifact?.id}`
    },
    refetch: () => { artifactsRoleQuery.refetch() },
  }
}
