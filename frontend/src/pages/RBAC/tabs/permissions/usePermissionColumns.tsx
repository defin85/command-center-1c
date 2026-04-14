import { useCallback, useMemo } from 'react'
import { Button, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ClusterPermission } from '../../../../api/generated/model/clusterPermission'
import type { DatabasePermission } from '../../../../api/generated/model/databasePermission'
import type {
  ArtifactGroupPermission,
  ArtifactPermission,
  ClusterGroupPermission,
  DatabaseGroupPermission,
  OperationTemplateGroupPermission,
  OperationTemplatePermission,
  WorkflowTemplateGroupPermission,
  WorkflowTemplatePermission,
} from '../../../../api/queries/rbac'
import { useLocaleFormatters, useRbacTranslation } from '../../../../i18n'

const { Text } = Typography

type ConfirmReasonFn = (title: string, onOk: (reason: string) => Promise<void>) => void

type RevokeMutation<T> = {
  isPending: boolean
  mutateAsync: (args: T) => Promise<unknown>
}

export function usePermissionColumns(params: {
  confirmReason: ConfirmReasonFn
  revokeCluster: RevokeMutation<{ user_id: number; cluster_id: string; reason: string }>
  revokeDatabase: RevokeMutation<{ user_id: number; database_id: string; reason: string }>
  revokeClusterGroup: RevokeMutation<{ group_id: number; cluster_id: string; reason: string }>
  revokeDatabaseGroup: RevokeMutation<{ group_id: number; database_id: string; reason: string }>
  revokeOperationTemplate: RevokeMutation<{ user_id: number; template_id: string; reason: string }>
  revokeOperationTemplateGroup: RevokeMutation<{ group_id: number; template_id: string; reason: string }>
  revokeWorkflowTemplate: RevokeMutation<{ user_id: number; template_id: string; reason: string }>
  revokeWorkflowTemplateGroup: RevokeMutation<{ group_id: number; template_id: string; reason: string }>
  revokeArtifact: RevokeMutation<{ user_id: number; artifact_id: string; reason: string }>
  revokeArtifactGroup: RevokeMutation<{ group_id: number; artifact_id: string; reason: string }>
}) {
  const {
    confirmReason,
    revokeArtifact,
    revokeArtifactGroup,
    revokeCluster,
    revokeClusterGroup,
    revokeDatabase,
    revokeDatabaseGroup,
    revokeOperationTemplate,
    revokeOperationTemplateGroup,
    revokeWorkflowTemplate,
    revokeWorkflowTemplateGroup,
  } = params
  const { t } = useRbacTranslation()
  const formatters = useLocaleFormatters()

  const emptyValue = t(($) => $.permissions.values.empty)

  const renderEntity = useCallback((label: string | undefined, id: string | number | undefined) => (
    <span>
      {label}
      {id !== undefined ? (
        <>
          {' '}
          <Text type="secondary">#{id}</Text>
        </>
      ) : null}
    </span>
  ), [])

  const renderGrantedAt = useCallback((value: string | undefined) => (
    value ? formatters.dateTime(value) : emptyValue
  ), [emptyValue, formatters])

  const renderGrantedBy = useCallback((row: { granted_by?: { username?: string; id?: number } | null }) => (
    row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : emptyValue
  ), [emptyValue])

  const revokeButton = useCallback((
    loading: boolean,
    title: string,
    onConfirm: (reason: string) => Promise<void>,
  ) => (
    <Button
      danger
      size="small"
      loading={loading}
      onClick={() => {
        void confirmReason(title, onConfirm)
      }}
    >
      {t(($) => $.permissions.actions.revoke)}
    </Button>
  ), [confirmReason, t])

  const clusterColumns: ColumnsType<ClusterPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.user),
        key: 'user_id',
        render: (_, row) => renderEntity(row.user?.username, row.user?.id),
      },
      { title: t(($) => $.permissions.columns.cluster), dataIndex: ['cluster', 'name'], key: 'cluster' },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => (
          !row.user?.id || !row.cluster?.id
            ? null
            : revokeButton(
              revokeCluster.isPending,
              t(($) => $.permissions.confirmTitles.revokeUserCluster),
              async (reason) => {
                await revokeCluster.mutateAsync({ user_id: row.user.id, cluster_id: row.cluster.id, reason })
              },
            )
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeCluster, t],
  )

  const databaseColumns: ColumnsType<DatabasePermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.user),
        key: 'user_id',
        render: (_, row) => renderEntity(row.user?.username, row.user?.id),
      },
      { title: t(($) => $.permissions.columns.database), dataIndex: ['database', 'name'], key: 'database' },
      { title: t(($) => $.permissions.columns.databaseId), dataIndex: ['database', 'id'], key: 'database_id' },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => (
          !row.user?.id || !row.database?.id
            ? null
            : revokeButton(
              revokeDatabase.isPending,
              t(($) => $.permissions.confirmTitles.revokeUserDatabase),
              async (reason) => {
                await revokeDatabase.mutateAsync({ user_id: row.user.id, database_id: row.database.id, reason })
              },
            )
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeDatabase, t],
  )

  const clusterGroupColumns: ColumnsType<ClusterGroupPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.group),
        key: 'group',
        render: (_, row) => renderEntity(row.group.name, row.group.id),
      },
      {
        title: t(($) => $.permissions.columns.cluster),
        key: 'cluster',
        render: (_, row) => renderEntity(row.cluster.name, row.cluster.id),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeClusterGroup.isPending,
          t(($) => $.permissions.confirmTitles.revokeGroupCluster),
          async (reason) => {
            await revokeClusterGroup.mutateAsync({ group_id: row.group.id, cluster_id: row.cluster.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeClusterGroup, t],
  )

  const databaseGroupColumns: ColumnsType<DatabaseGroupPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.group),
        key: 'group',
        render: (_, row) => renderEntity(row.group.name, row.group.id),
      },
      {
        title: t(($) => $.permissions.columns.database),
        key: 'database',
        render: (_, row) => (
          <span>
            {row.database.name} <Text type="secondary">#{row.database.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeDatabaseGroup.isPending,
          t(($) => $.permissions.confirmTitles.revokeGroupDatabase),
          async (reason) => {
            await revokeDatabaseGroup.mutateAsync({ group_id: row.group.id, database_id: row.database.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeDatabaseGroup, t],
  )

  const operationTemplateUserColumns: ColumnsType<OperationTemplatePermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.user),
        key: 'user',
        render: (_, row) => renderEntity(row.user.username, row.user.id),
      },
      {
        title: t(($) => $.permissions.columns.operationTemplate),
        key: 'template',
        render: (_, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeOperationTemplate.isPending,
          t(($) => $.permissions.confirmTitles.revokeUserOperationTemplate),
          async (reason) => {
            await revokeOperationTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeOperationTemplate, t],
  )

  const operationTemplateGroupColumns: ColumnsType<OperationTemplateGroupPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.group),
        key: 'group',
        render: (_, row) => renderEntity(row.group.name, row.group.id),
      },
      {
        title: t(($) => $.permissions.columns.operationTemplate),
        key: 'template',
        render: (_, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeOperationTemplateGroup.isPending,
          t(($) => $.permissions.confirmTitles.revokeGroupOperationTemplate),
          async (reason) => {
            await revokeOperationTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeOperationTemplateGroup, t],
  )

  const workflowTemplateUserColumns: ColumnsType<WorkflowTemplatePermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.user),
        key: 'user',
        render: (_, row) => renderEntity(row.user.username, row.user.id),
      },
      {
        title: t(($) => $.permissions.columns.workflowTemplate),
        key: 'template',
        render: (_, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeWorkflowTemplate.isPending,
          t(($) => $.permissions.confirmTitles.revokeUserWorkflowTemplate),
          async (reason) => {
            await revokeWorkflowTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeWorkflowTemplate, t],
  )

  const workflowTemplateGroupColumns: ColumnsType<WorkflowTemplateGroupPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.group),
        key: 'group',
        render: (_, row) => renderEntity(row.group.name, row.group.id),
      },
      {
        title: t(($) => $.permissions.columns.workflowTemplate),
        key: 'template',
        render: (_, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeWorkflowTemplateGroup.isPending,
          t(($) => $.permissions.confirmTitles.revokeGroupWorkflowTemplate),
          async (reason) => {
            await revokeWorkflowTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeWorkflowTemplateGroup, t],
  )

  const artifactUserColumns: ColumnsType<ArtifactPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.user),
        key: 'user',
        render: (_, row) => renderEntity(row.user.username, row.user.id),
      },
      {
        title: t(($) => $.permissions.columns.artifact),
        key: 'artifact',
        render: (_, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeArtifact.isPending,
          t(($) => $.permissions.confirmTitles.revokeUserArtifact),
          async (reason) => {
            await revokeArtifact.mutateAsync({ user_id: row.user.id, artifact_id: row.artifact.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeArtifact, t],
  )

  const artifactGroupColumns: ColumnsType<ArtifactGroupPermission> = useMemo(
    () => [
      {
        title: t(($) => $.permissions.columns.group),
        key: 'group',
        render: (_, row) => renderEntity(row.group.name, row.group.id),
      },
      {
        title: t(($) => $.permissions.columns.artifact),
        key: 'artifact',
        render: (_, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: t(($) => $.permissions.columns.level), dataIndex: 'level', key: 'level' },
      {
        title: t(($) => $.permissions.columns.grantedAt),
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: renderGrantedAt,
      },
      {
        title: t(($) => $.permissions.columns.grantedBy),
        key: 'granted_by',
        render: (_, row) => renderGrantedBy(row),
      },
      { title: t(($) => $.permissions.columns.notes), dataIndex: 'notes', key: 'notes' },
      {
        title: t(($) => $.permissions.columns.actions),
        key: 'actions',
        render: (_, row) => revokeButton(
          revokeArtifactGroup.isPending,
          t(($) => $.permissions.confirmTitles.revokeGroupArtifact),
          async (reason) => {
            await revokeArtifactGroup.mutateAsync({ group_id: row.group.id, artifact_id: row.artifact.id, reason })
          },
        ),
      },
    ],
    [renderEntity, renderGrantedAt, renderGrantedBy, revokeButton, revokeArtifactGroup, t],
  )

  return {
    clusterColumns,
    databaseColumns,
    clusterGroupColumns,
    databaseGroupColumns,
    operationTemplateUserColumns,
    operationTemplateGroupColumns,
    workflowTemplateUserColumns,
    workflowTemplateGroupColumns,
    artifactUserColumns,
    artifactGroupColumns,
  }
}
