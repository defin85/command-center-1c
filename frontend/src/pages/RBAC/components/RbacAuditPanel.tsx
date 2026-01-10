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
  run: (reason: string) => Promise<void>
}

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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-cluster-permission/', { user_id: userId, cluster_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore cluster permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-database-permission/', { user_id: userId, database_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore database permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-cluster-group-permission/', { group_id: groupId, cluster_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore cluster group permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-database-group-permission/', { group_id: groupId, database_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore database group permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-operation-template-permission/', { user_id: userId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore operation template permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-operation-template-group-permission/', { group_id: groupId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore operation template group permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-workflow-template-permission/', { user_id: userId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore workflow template permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-workflow-template-group-permission/', { group_id: groupId, template_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore workflow template group permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-artifact-permission/', { user_id: userId, artifact_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore artifact permission level`,
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
        run: async (reason) => {
          await apiClient.post('/api/v2/rbac/revoke-artifact-group-permission/', { group_id: groupId, artifact_id: targetId, reason })
        },
      }
    }
    if (created === false && oldLevel) {
      return {
        title: `Undo: restore artifact group permission level`,
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
  undoSuccessMessage?: string
  undoFailedMessage?: string
  undoNotSupportedMessage?: string
}) {
  const { modal, message } = App.useApp()
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
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: 'Actor',
      dataIndex: 'actor_username',
      key: 'actor_username',
      render: (value: string) => value || '-',
    },
    { title: 'Action', dataIndex: 'action', key: 'action' },
    {
      title: 'Outcome',
      dataIndex: 'outcome',
      key: 'outcome',
      render: (value: string) => (
        <Tag color={value === 'success' ? 'green' : (value === 'error' ? 'red' : 'default')}>
          {value}
        </Tag>
      ),
    },
    {
      title: 'Target',
      key: 'target',
      render: (_: unknown, row) => `${row.target_type}:${row.target_id}`,
    },
    {
      title: 'Reason',
      key: 'reason',
      render: (_: unknown, row) => {
        const reason = typeof row.metadata?.reason === 'string' ? row.metadata.reason : ''
        return reason ? reason : '-'
      },
    },
    {
      title: 'Details',
      key: 'details',
      render: (_: unknown, row) => (
        <Space size="small" wrap>
          <Button
            size="small"
            onClick={() => {
              modal.info({
                title: `Audit #${row.id}`,
                width: 860,
                content: (
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(row, null, 2)}
                  </pre>
                ),
              })
            }}
          >
            View
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
  ], [modal, props.enabled, props.undoLabel])

  return (
    <Card title={props.title ?? 'Admin Audit'} size="small">
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          placeholder="Search"
          style={{ width: 320 }}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Button onClick={() => query.refetch()} loading={query.isFetching}>
          Refresh
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
            message={getUndoCommand(undoItem)?.title ?? (props.undoNotSupportedMessage ?? 'Undo is not supported for this entry')}
            description={(
              <Space direction="vertical" size={4}>
                <div><Text type="secondary">Audit ID:</Text> <Text>#{undoItem.id}</Text></div>
                <div><Text type="secondary">Action:</Text> <Text>{undoItem.action}</Text></div>
                <div><Text type="secondary">Target:</Text> <Text>{undoItem.target_type}:{undoItem.target_id}</Text></div>
              </Space>
            )}
          />
        ) : null}
      </ReasonModal>
    </Card>
  )
}
