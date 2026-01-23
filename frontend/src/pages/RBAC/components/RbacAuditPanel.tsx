import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Input, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useAdminAuditLog, type AdminAuditLogItem } from '../../../api/queries/rbac'
import { apiClient } from '../../../api/client'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { ReasonModal } from './ReasonModal'

const { Text } = Typography

type UndoCommand = {
  title: string
  code: string
  meta?: Record<string, unknown>
  run: (reason: string) => Promise<void>
}

type RbacAuditPanelI18n = {
  searchPlaceholder?: string
  refreshText?: string
  viewText?: string
  detailsModalTitle?: (id: number) => string
  columnCreatedAt?: string
  columnActor?: string
  columnAction?: string
  columnOutcome?: string
  columnTarget?: string
  columnReason?: string
  columnDetails?: string
  detailsAuditIdLabel?: string
  detailsActionLabel?: string
  detailsTargetLabel?: string
  formatUndoTitle?: (cmd: UndoCommand, item: AdminAuditLogItem) => string
}

const EMPTY_I18N: RbacAuditPanelI18n = {}

function getNumber(meta: Record<string, unknown>, key: string): number | null {
  const value = meta[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function getString(meta: Record<string, unknown>, key: string): string | null {
  const value = meta[key]
  return typeof value === 'string' ? value : null
}

function getBoolean(meta: Record<string, unknown>, key: string): boolean | null {
  const value = meta[key]
  return typeof value === 'boolean' ? value : null
}

function parseIntStrict(value: string): number | null {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

function getUndoCommand(item: AdminAuditLogItem): UndoCommand | null {
  if (item.outcome !== 'success') return null
  const meta = item.metadata ?? {}

  if (item.action === 'rbac.create_role') {
    const groupId = parseIntStrict(String(item.target_id))
    if (!groupId) return null
    return {
      title: `Undo: delete role #${groupId}`,
      code: 'delete_role',
      meta: { groupId },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/delete-role/', { group_id: groupId, reason })
      },
    }
  }

  if (item.action === 'rbac.update_role') {
    const groupId = parseIntStrict(String(item.target_id))
    const oldName = getString(meta, 'old_name')
    if (!groupId || !oldName) return null
    return {
      title: `Undo: rename role #${groupId}`,
      code: 'rename_role',
      meta: { groupId, oldName },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/update-role/', { group_id: groupId, name: oldName, reason })
      },
    }
  }

  if (item.action === 'rbac.set_user_roles') {
    const userId = parseIntStrict(String(item.target_id))
    const oldGroupIdsRaw = meta['old_group_ids']
    const oldGroupIds = Array.isArray(oldGroupIdsRaw)
      ? oldGroupIdsRaw.filter((v) => typeof v === 'number' && Number.isFinite(v)) as number[]
      : null
    if (!userId || !oldGroupIds) return null
    return {
      title: `Undo: restore user roles #${userId}`,
      code: 'restore_user_roles',
      meta: { userId, oldGroupIdsCount: oldGroupIds.length },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/set-user-roles/', {
          user_id: userId,
          group_ids: oldGroupIds,
          mode: 'replace',
          reason,
        })
      },
    }
  }

  if (item.action === 'rbac.set_role_capabilities') {
    const groupId = parseIntStrict(String(item.target_id))
    const oldCodesRaw = meta['old_permission_codes']
    const oldCodes = Array.isArray(oldCodesRaw)
      ? oldCodesRaw.filter((v) => typeof v === 'string') as string[]
      : null
    if (!groupId || !oldCodes) return null
    return {
      title: `Undo: restore role capabilities #${groupId}`,
      code: 'restore_role_capabilities',
      meta: { groupId, oldCodesCount: oldCodes.length },
      run: async (reason) => {
        await apiClient.post('/api/v2/rbac/set-role-capabilities/', {
          group_id: groupId,
          permission_codes: oldCodes,
          mode: 'replace',
          reason,
        })
      },
    }
  }

  const created = getBoolean(meta, 'created')
  const deleted = getBoolean(meta, 'deleted')
  const oldLevel = getString(meta, 'old_level')
  const oldNotes = getString(meta, 'old_notes') ?? ''

  const userId = getNumber(meta, 'user_id')
  const groupId = getNumber(meta, 'group_id')
  const targetId = String(item.target_id)

  const grantOrRestore = async (path: string, payload: Record<string, unknown>, reason: string) => {
    await apiClient.post(path, { ...payload, reason })
  }

  if (item.action === 'rbac.grant_cluster_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: `Undo: revoke cluster permission`,
        code: 'revoke_cluster_permission',
        meta: { userId, clusterId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-cluster-permission/', { user_id: userId, cluster_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore cluster permission level`,
        code: 'restore_cluster_permission_level',
        meta: { userId, clusterId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-cluster-permission/', { user_id: userId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_cluster_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore cluster permission`,
      code: 'restore_cluster_permission',
      meta: { userId, clusterId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-cluster-permission/', { user_id: userId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_database_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: `Undo: revoke database permission`,
        code: 'revoke_database_permission',
        meta: { userId, databaseId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-database-permission/', { user_id: userId, database_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore database permission level`,
        code: 'restore_database_permission_level',
        meta: { userId, databaseId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-database-permission/', { user_id: userId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_database_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore database permission`,
      code: 'restore_database_permission',
      meta: { userId, databaseId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-database-permission/', { user_id: userId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_cluster_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: `Undo: revoke cluster group permission`,
        code: 'revoke_cluster_group_permission',
        meta: { groupId, clusterId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore cluster group permission level`,
        code: 'restore_cluster_group_permission_level',
        meta: { groupId, clusterId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_cluster_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore cluster group permission`,
      code: 'restore_cluster_group_permission',
      meta: { groupId, clusterId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_database_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: `Undo: revoke database group permission`,
        code: 'revoke_database_group_permission',
        meta: { groupId, databaseId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-database-group-permission/', { group_id: groupId, database_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore database group permission level`,
        code: 'restore_database_group_permission_level',
        meta: { groupId, databaseId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-database-group-permission/', { group_id: groupId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_database_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore database group permission`,
      code: 'restore_database_group_permission',
      meta: { groupId, databaseId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-database-group-permission/', { group_id: groupId, database_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_operation_template_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: `Undo: revoke operation template permission`,
        code: 'revoke_operation_template_permission',
        meta: { userId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-operation-template-permission/', { user_id: userId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore operation template permission level`,
        code: 'restore_operation_template_permission_level',
        meta: { userId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-operation-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_operation_template_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore operation template permission`,
      code: 'restore_operation_template_permission',
      meta: { userId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-operation-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_operation_template_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: `Undo: revoke operation template group permission`,
        code: 'revoke_operation_template_group_permission',
        meta: { groupId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-operation-template-group-permission/', { group_id: groupId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore operation template group permission level`,
        code: 'restore_operation_template_group_permission_level',
        meta: { groupId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-operation-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_operation_template_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore operation template group permission`,
      code: 'restore_operation_template_group_permission',
      meta: { groupId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-operation-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_workflow_template_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: `Undo: revoke workflow template permission`,
        code: 'revoke_workflow_template_permission',
        meta: { userId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-workflow-template-permission/', { user_id: userId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore workflow template permission level`,
        code: 'restore_workflow_template_permission_level',
        meta: { userId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-workflow-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_workflow_template_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore workflow template permission`,
      code: 'restore_workflow_template_permission',
      meta: { userId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-workflow-template-permission/', { user_id: userId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_workflow_template_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: `Undo: revoke workflow template group permission`,
        code: 'revoke_workflow_template_group_permission',
        meta: { groupId, templateId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore workflow template group permission level`,
        code: 'restore_workflow_template_group_permission_level',
        meta: { groupId, templateId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_workflow_template_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore workflow template group permission`,
      code: 'restore_workflow_template_group_permission',
      meta: { groupId, templateId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_artifact_permission') {
    if (!userId) return null
    if (created === true) {
      return {
        title: `Undo: revoke artifact permission`,
        code: 'revoke_artifact_permission',
        meta: { userId, artifactId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-artifact-permission/', { user_id: userId, artifact_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore artifact permission level`,
        code: 'restore_artifact_permission_level',
        meta: { userId, artifactId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-artifact-permission/', { user_id: userId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_artifact_permission') {
    if (!userId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore artifact permission`,
      code: 'restore_artifact_permission',
      meta: { userId, artifactId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-artifact-permission/', { user_id: userId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  if (item.action === 'rbac.grant_artifact_group_permission') {
    if (!groupId) return null
    if (created === true) {
      return {
        title: `Undo: revoke artifact group permission`,
        code: 'revoke_artifact_group_permission',
        meta: { groupId, artifactId: targetId },
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore artifact group permission level`,
        code: 'restore_artifact_group_permission_level',
        meta: { groupId, artifactId: targetId, oldLevel },
        run: async (reason) => {
          await grantOrRestore('/api/v2/rbac/grant-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
        },
      }
    }
  }

  if (item.action === 'rbac.revoke_artifact_group_permission') {
    if (!groupId || deleted !== true || !oldLevel) return null
    return {
      title: `Undo: restore artifact group permission`,
      code: 'restore_artifact_group_permission',
      meta: { groupId, artifactId: targetId, oldLevel },
      run: async (reason) => {
        await grantOrRestore('/api/v2/rbac/grant-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, level: oldLevel, notes: oldNotes }, reason)
      },
    }
  }

  return null
}

export function RbacAuditPanel(props: {
  enabled: boolean
  title?: string
  errorMessage?: string
  undoLabel?: string
  undoModalTitle?: string
  undoOkText?: string
  undoCancelText?: string
  undoReasonPlaceholder?: string
  undoReasonRequiredMessage?: string
  undoSuccessMessage?: string
  undoFailedMessage?: string
  undoNotSupportedMessage?: string
  i18n?: RbacAuditPanelI18n
}) {
  const { modal, message } = App.useApp()
  const i18n = props.i18n ?? EMPTY_I18N
  const [search, setSearch] = useState<string>('')
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(100)
  const debouncedSearch = useDebouncedValue(search, 300)
  const [undoOpen, setUndoOpen] = useState(false)
  const [undoItem, setUndoItem] = useState<AdminAuditLogItem | null>(null)
  const [undoLoading, setUndoLoading] = useState(false)

  const query = useAdminAuditLog({
    search: debouncedSearch || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  }, { enabled: props.enabled })

  const items = query.data?.items ?? []
  const total = typeof query.data?.total === 'number' ? query.data.total : items.length

  const columns: ColumnsType<AdminAuditLogItem> = useMemo(() => [
    {
      title: i18n.columnCreatedAt ?? 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: i18n.columnActor ?? 'Actor',
      dataIndex: 'actor_username',
      key: 'actor_username',
      render: (value: string) => value || '-',
    },
    { title: i18n.columnAction ?? 'Action', dataIndex: 'action', key: 'action' },
    {
      title: i18n.columnOutcome ?? 'Outcome',
      dataIndex: 'outcome',
      key: 'outcome',
      render: (value: string) => (
        <Tag color={value === 'success' ? 'green' : (value === 'error' ? 'red' : 'default')}>
          {value}
        </Tag>
      ),
    },
    {
      title: i18n.columnTarget ?? 'Target',
      key: 'target',
      render: (_: unknown, row) => `${row.target_type}:${row.target_id}`,
    },
    {
      title: i18n.columnReason ?? 'Reason',
      key: 'reason',
      render: (_: unknown, row) => {
        const reason = typeof row.metadata?.reason === 'string' ? row.metadata.reason : ''
        return reason ? reason : '-'
      },
    },
    {
      title: i18n.columnDetails ?? 'Details',
      key: 'details',
      render: (_: unknown, row) => (
        <Space size="small" wrap>
          <Button
            size="small"
            onClick={() => {
              modal.info({
                title: i18n.detailsModalTitle?.(row.id) ?? `Audit #${row.id}`,
                width: 860,
                content: (
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(row, null, 2)}
                  </pre>
                ),
              })
            }}
          >
            {i18n.viewText ?? 'View'}
          </Button>
          {props.enabled && (
            (() => {
              const cmd = getUndoCommand(row)
              if (!cmd) return <Text type="secondary">-</Text>
              return (
                <Button
                  size="small"
                  onClick={() => {
                    setUndoItem(row)
                    setUndoOpen(true)
                  }}
                >
                  {props.undoLabel ?? 'Undo'}
                </Button>
              )
            })()
          )}
        </Space>
      ),
    },
  ], [i18n, modal, props.enabled, props.undoLabel])

  return (
    <Card title={props.title ?? 'Admin Audit'} size="small">
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          placeholder={i18n.searchPlaceholder ?? 'Search'}
          style={{ width: 320 }}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Button onClick={() => query.refetch()} loading={query.isFetching}>
          {i18n.refreshText ?? 'Refresh'}
        </Button>
      </Space>
      {query.error && (
        <Alert
          style={{ marginBottom: 12 }}
          type="warning"
          message={props.errorMessage ?? 'Failed to load audit log'}
        />
      )}
      <Table
        size="small"
        columns={columns}
        dataSource={items}
        loading={query.isLoading}
        rowKey="id"
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage)
            setPageSize(nextPageSize)
          },
        }}
      />

      <ReasonModal
        title={props.undoModalTitle ?? 'Undo change'}
        open={undoOpen}
        okText={props.undoOkText ?? 'Undo'}
        cancelText={props.undoCancelText ?? 'Cancel'}
        okButtonProps={{ loading: undoLoading }}
        reasonPlaceholder={props.undoReasonPlaceholder}
        requiredMessage={props.undoReasonRequiredMessage}
        onCancel={() => {
          if (undoLoading) return
          setUndoOpen(false)
          setUndoItem(null)
        }}
        onOk={async (reason) => {
          if (!undoItem) return
          const cmd = getUndoCommand(undoItem)
          if (!cmd) {
            message.warning(props.undoNotSupportedMessage ?? 'Undo is not supported for this entry')
            setUndoOpen(false)
            setUndoItem(null)
            return
          }

          setUndoLoading(true)
          try {
            await cmd.run(reason)
            message.success(props.undoSuccessMessage ?? 'Undo completed')
            setUndoOpen(false)
            setUndoItem(null)
            query.refetch()
          } catch {
            message.error(props.undoFailedMessage ?? 'Undo failed')
          } finally {
            setUndoLoading(false)
          }
        }}
      >
        {undoItem ? (
          <Alert
            type="info"
            showIcon
            message={(() => {
              const cmd = getUndoCommand(undoItem)
              if (!cmd) return props.undoNotSupportedMessage ?? 'Undo is not supported for this entry'
              return i18n.formatUndoTitle ? i18n.formatUndoTitle(cmd, undoItem) : cmd.title
            })()}
            description={(
              <Space direction="vertical" size={4}>
                <div><Text type="secondary">{i18n.detailsAuditIdLabel ?? 'Audit ID:'}</Text> <Text>#{undoItem.id}</Text></div>
                <div><Text type="secondary">{i18n.detailsActionLabel ?? 'Action:'}</Text> <Text>{undoItem.action}</Text></div>
                <div><Text type="secondary">{i18n.detailsTargetLabel ?? 'Target:'}</Text> <Text>{undoItem.target_type}:{undoItem.target_id}</Text></div>
              </Space>
            )}
          />
        ) : null}
      </ReasonModal>
    </Card>
  )
}
