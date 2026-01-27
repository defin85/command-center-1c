import { useMemo } from 'react'
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

  const clusterColumns: ColumnsType<ClusterPermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'Кластер', dataIndex: ['cluster', 'name'], key: 'cluster' },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      { title: 'Выдано', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeCluster.isPending}
            onClick={() => {
              if (!row.user?.id || !row.cluster?.id) return
              confirmReason('Отозвать доступ пользователя к кластеру?', async (reason) => {
                await revokeCluster.mutateAsync({ user_id: row.user.id, cluster_id: row.cluster.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeCluster]
  )

  const databaseColumns: ColumnsType<DatabasePermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'База', dataIndex: ['database', 'name'], key: 'database' },
      { title: 'ID базы', dataIndex: ['database', 'id'], key: 'database_id' },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      { title: 'Выдано', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabase.isPending}
            onClick={() => {
              if (!row.user?.id || !row.database?.id) return
              confirmReason('Отозвать доступ пользователя к базе?', async (reason) => {
                await revokeDatabase.mutateAsync({ user_id: row.user.id, database_id: row.database.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeDatabase]
  )

  const clusterGroupColumns: ColumnsType<ClusterGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Кластер',
        key: 'cluster',
        render: (_: unknown, row) => (
          <span>
            {row.cluster.name} <Text type="secondary">#{row.cluster.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeClusterGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к кластеру?', async (reason) => {
                await revokeClusterGroup.mutateAsync({ group_id: row.group.id, cluster_id: row.cluster.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeClusterGroup]
  )

  const databaseGroupColumns: ColumnsType<DatabaseGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'База',
        key: 'database',
        render: (_: unknown, row) => (
          <span>
            {row.database.name} <Text type="secondary">#{row.database.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabaseGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к базе?', async (reason) => {
                await revokeDatabaseGroup.mutateAsync({ group_id: row.group.id, database_id: row.database.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeDatabaseGroup]
  )

  const operationTemplateUserColumns: ColumnsType<OperationTemplatePermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон операции',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeOperationTemplate.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ пользователя к шаблону операции?', async (reason) => {
                await revokeOperationTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeOperationTemplate]
  )

  const operationTemplateGroupColumns: ColumnsType<OperationTemplateGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон операции',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeOperationTemplateGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к шаблону операции?', async (reason) => {
                await revokeOperationTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeOperationTemplateGroup]
  )

  const workflowTemplateUserColumns: ColumnsType<WorkflowTemplatePermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон рабочего процесса',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeWorkflowTemplate.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ пользователя к шаблону рабочего процесса?', async (reason) => {
                await revokeWorkflowTemplate.mutateAsync({ user_id: row.user.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeWorkflowTemplate]
  )

  const workflowTemplateGroupColumns: ColumnsType<WorkflowTemplateGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Шаблон рабочего процесса',
        key: 'template',
        render: (_: unknown, row) => (
          <span>
            {row.template.name} <Text type="secondary">#{row.template.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeWorkflowTemplateGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к шаблону рабочего процесса?', async (reason) => {
                await revokeWorkflowTemplateGroup.mutateAsync({ group_id: row.group.id, template_id: row.template.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeWorkflowTemplateGroup]
  )

  const artifactUserColumns: ColumnsType<ArtifactPermission> = useMemo(
    () => [
      {
        title: 'Пользователь',
        key: 'user',
        render: (_: unknown, row) => (
          <span>
            {row.user.username} <Text type="secondary">#{row.user.id}</Text>
          </span>
        ),
      },
      {
        title: 'Артефакт',
        key: 'artifact',
        render: (_: unknown, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeArtifact.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ пользователя к артефакту?', async (reason) => {
                await revokeArtifact.mutateAsync({ user_id: row.user.id, artifact_id: row.artifact.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeArtifact]
  )

  const artifactGroupColumns: ColumnsType<ArtifactGroupPermission> = useMemo(
    () => [
      {
        title: 'Группа',
        key: 'group',
        render: (_: unknown, row) => (
          <span>
            {row.group.name} <Text type="secondary">#{row.group.id}</Text>
          </span>
        ),
      },
      {
        title: 'Артефакт',
        key: 'artifact',
        render: (_: unknown, row) => (
          <span>
            {row.artifact.name} <Text type="secondary">#{row.artifact.id}</Text>
          </span>
        ),
      },
      { title: 'Уровень', dataIndex: 'level', key: 'level' },
      {
        title: 'Выдано',
        dataIndex: 'granted_at',
        key: 'granted_at',
        render: (value: string | undefined) => value ? new Date(value).toLocaleString() : '-',
      },
      {
        title: 'Кем выдано',
        key: 'granted_by',
        render: (_: unknown, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Комментарий', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Действия',
        key: 'actions',
        render: (_: unknown, row) => (
          <Button
            danger
            size="small"
            loading={revokeArtifactGroup.isPending}
            onClick={() => {
              confirmReason('Отозвать доступ группы к артефакту?', async (reason) => {
                await revokeArtifactGroup.mutateAsync({ group_id: row.group.id, artifact_id: row.artifact.id, reason })
              })
            }}
          >
            Отозвать
          </Button>
        ),
      },
    ],
    [confirmReason, revokeArtifactGroup]
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
