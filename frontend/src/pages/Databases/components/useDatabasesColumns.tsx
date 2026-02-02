import { useMemo } from 'react'
import { Button, Dropdown, Space, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { AppstoreOutlined, DatabaseOutlined, DownOutlined, EditOutlined, HeartOutlined, KeyOutlined, LinkOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

import type { Database } from '../../../api/generated/model/database'
import { SetDatabaseStatusRequestStatus as SetDatabaseStatusRequestStatusEnum } from '../../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../../api/generated/model/setDatabaseStatusRequestStatus'
import { DatabaseActionsMenu } from '../../../components/actions'
import type { DatabaseActionKey } from '../../../components/actions'
import { getHealthTag, getStatusTag } from '../../../utils/databaseStatus'

type MessageApi = {
  success: (content: string) => void
  error: (content: string) => void
  info: (content: string) => void
}

export type UseDatabasesColumnsParams = {
  canOperateDatabase: (databaseId: string) => boolean
  canManageDatabase: (databaseId: string) => boolean
  openCredentialsModal: (database: Database) => void
  openDbmsMetadataModal: (database: Database) => void
  openIbcmdProfileModal: (database: Database) => void
  openExtensionsDrawer: (database: Database) => void
  handleSingleAction: (action: DatabaseActionKey, database: Database) => void
  healthCheckPendingIds: Set<string>
  markHealthCheckPending: (databaseId: string, pending: boolean) => void
  healthCheck: { mutateAsync: (databaseId: string) => Promise<{ operation_id?: string }> }
  runSetStatus: (ids: string[], status: SetDatabaseStatusValue) => Promise<void>
  getErrorStatus: (error: unknown) => number | undefined
  getErrorMessage: (error: unknown) => string
  message: MessageApi
}

export const useDatabasesColumns = ({
  canOperateDatabase,
  canManageDatabase,
  openCredentialsModal,
  openDbmsMetadataModal,
  openIbcmdProfileModal,
  openExtensionsDrawer,
  handleSingleAction,
  healthCheckPendingIds,
  markHealthCheckPending,
  healthCheck,
  runSetStatus,
  getErrorStatus,
  getErrorMessage,
  message,
}: UseDatabasesColumnsParams) => {
  const formatDeniedTime = (value?: string | null) => {
    if (!value) return 'n/a'
    const parsed = dayjs(value)
    return parsed.isValid() ? parsed.format('DD.MM.YYYY HH:mm') : value
  }

  type DatabaseHealthMeta = Database & {
    last_health_error?: string | null
    last_health_error_code?: string | null
  }

  return useMemo<ColumnsType<Database>>(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string) => <span>{name}</span>,
    },
    {
      title: 'Host',
      dataIndex: 'host',
      key: 'host',
      width: 160,
    },
    {
      title: 'Port',
      dataIndex: 'port',
      key: 'port',
      width: 90,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => {
        const tag = getStatusTag(status)
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
    {
      title: 'Health',
      dataIndex: 'last_check_status',
      key: 'last_check_status',
      width: 130,
      render: (_status: string, record: Database) => {
        const tag = getHealthTag(record.last_check_status)
        const healthMeta = record as DatabaseHealthMeta
        const errorMessage = healthMeta.last_health_error
        const errorCode = healthMeta.last_health_error_code
        const tooltip = errorMessage || errorCode
          ? (
            <div>
              {errorCode && <div>Code: {errorCode}</div>}
              {errorMessage && <div>Message: {errorMessage}</div>}
            </div>
          )
          : null

        if (!tooltip) {
          return <Tag color={tag.color}>{tag.label}</Tag>
        }

        return (
          <Tooltip title={tooltip}>
            <Tag color={tag.color}>{tag.label}</Tag>
          </Tooltip>
        )
      },
    },
    {
      title: 'Credentials',
      key: 'credentials',
      width: 130,
      render: (_: unknown, record: Database) => (
        <Tag color={record.password_configured ? 'green' : 'default'}>
          {record.password_configured ? 'Configured' : 'Missing'}
        </Tag>
      ),
    },
    {
      title: 'Restrictions',
      key: 'restrictions',
      width: 280,
      render: (_: unknown, record: Database) => {
        const jobsDeny = record.scheduled_jobs_deny
        const sessionsDeny = record.sessions_deny
        const jobsTag = (
          <Tag color={jobsDeny === true ? 'red' : jobsDeny === false ? 'green' : 'default'}>
            {jobsDeny === true ? 'Jobs: Locked' : jobsDeny === false ? 'Jobs: Allowed' : 'Jobs: Unknown'}
          </Tag>
        )
        const sessionsTagBase = (
          <Tag color={sessionsDeny === true ? 'red' : sessionsDeny === false ? 'green' : 'default'}>
            {sessionsDeny === true ? 'Sessions: Blocked' : sessionsDeny === false ? 'Sessions: Allowed' : 'Sessions: Unknown'}
          </Tag>
        )
        const sessionsTag = sessionsDeny === true ? (
          <Tooltip
            title={
              <div>
                <div>From: {formatDeniedTime(record.denied_from)}</div>
                <div>To: {formatDeniedTime(record.denied_to)}</div>
                <div>Message: {record.denied_message || 'n/a'}</div>
                <div>Permission code: {record.permission_code || 'n/a'}</div>
                <div>Parameter: {record.denied_parameter || 'n/a'}</div>
              </div>
            }
          >
            {sessionsTagBase}
          </Tooltip>
        ) : sessionsTagBase

        return (
          <Space size="small" wrap>
            {jobsTag}
            {sessionsTag}
          </Space>
        )
      },
    },
    {
      title: 'Last Check',
      dataIndex: 'last_check',
      key: 'last_check',
      width: 170,
      render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 260,
      render: (_: unknown, record: Database) => {
        const canOperate = canOperateDatabase(record.id)
        const canManage = canManageDatabase(record.id)

        return (
          <Space size="small">
            <Button
              size="small"
              icon={<HeartOutlined />}
              onClick={async () => {
                if (!canOperate || healthCheckPendingIds.has(record.id)) {
                  return
                }
                markHealthCheckPending(record.id, true)
                try {
                  const res = await healthCheck.mutateAsync(record.id)
                  message.success(`${record.name}: health check queued`)
                  if (res.operation_id) {
                    message.info(`Operation ${res.operation_id} queued`)
                  }
                } catch (e: unknown) {
                  const status = getErrorStatus(e)
                  const statusLabel = status ? ` (status ${status})` : ''
                  message.error(`Health check failed: ${getErrorMessage(e)}${statusLabel}`)
                } finally {
                  markHealthCheckPending(record.id, false)
                }
              }}
              loading={healthCheckPendingIds.has(record.id)}
              disabled={!canOperate}
            >
              Check
            </Button>
            <Dropdown
              trigger={['click']}
              disabled={!canManage}
              menu={{
                items: [
                  { key: SetDatabaseStatusRequestStatusEnum.active, label: 'Set Active' },
                  { key: SetDatabaseStatusRequestStatusEnum.inactive, label: 'Set Inactive' },
                  { key: SetDatabaseStatusRequestStatusEnum.maintenance, label: 'Set Maintenance' },
                ],
                onClick: async ({ key }) => {
                  try {
                    await runSetStatus([record.id], key as SetDatabaseStatusValue)
                  } catch (e: unknown) {
                    const status = getErrorStatus(e)
                    if (status === 403) {
                      message.error('Set status requires manage access')
                      return
                    }
                    message.error(`Set status failed: ${getErrorMessage(e)}`)
                  }
                },
              }}
            >
              <Button size="small" icon={<EditOutlined />} disabled={!canManage}>
                Status <DownOutlined />
              </Button>
            </Dropdown>
            <Button
              size="small"
              icon={<KeyOutlined />}
              onClick={() => openCredentialsModal(record)}
              title="Credentials"
              aria-label="Credentials"
              disabled={!canManage}
            />
            <Tooltip title="DBMS metadata">
              <Button
                size="small"
                icon={<DatabaseOutlined />}
                onClick={() => openDbmsMetadataModal(record)}
                aria-label="DBMS metadata"
                disabled={!canManage}
              />
            </Tooltip>
            <Tooltip title="IBCMD connection profile">
              <Button
                size="small"
                icon={<LinkOutlined />}
                onClick={() => openIbcmdProfileModal(record)}
                aria-label="IBCMD connection profile"
                disabled={!canManage}
              />
            </Tooltip>
            <Tooltip title="Extensions">
              <Button
                size="small"
                icon={<AppstoreOutlined />}
                onClick={() => openExtensionsDrawer(record)}
                aria-label="Extensions"
                disabled={!canOperate}
              />
            </Tooltip>
            <DatabaseActionsMenu
              databaseId={record.id}
              databaseStatus={record.status}
              onAction={(action) => handleSingleAction(action, record)}
              disabled={!canOperate}
            />
          </Space>
        )
      },
    },
  ]), [
    canManageDatabase,
    canOperateDatabase,
    getErrorMessage,
    getErrorStatus,
    handleSingleAction,
    healthCheck,
    healthCheckPendingIds,
    markHealthCheckPending,
    message,
    openCredentialsModal,
    openDbmsMetadataModal,
    openIbcmdProfileModal,
    openExtensionsDrawer,
    runSetStatus,
  ])
}
