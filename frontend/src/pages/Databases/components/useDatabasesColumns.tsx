import { useCallback, useMemo } from 'react'
import { Button, Dropdown, Space, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { AppstoreOutlined, DatabaseOutlined, DeploymentUnitOutlined, DownOutlined, EditOutlined, HeartOutlined, KeyOutlined, LinkOutlined } from '@ant-design/icons'

import type { Database } from '../../../api/generated/model/database'
import { SetDatabaseStatusRequestStatus as SetDatabaseStatusRequestStatusEnum } from '../../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../../api/generated/model/setDatabaseStatusRequestStatus'
import { DatabaseActionsMenu } from '../../../components/actions'
import type { DatabaseActionKey } from '../../../components/actions'
import { useDatabasesTranslation, useLocaleFormatters } from '../../../i18n'
import { getHealthTag, getStatusTag } from '../../../utils/databaseStatus'

type MessageApi = {
  success: (content: string) => void
  error: (content: string) => void
  info: (content: string) => void
}

export type UseDatabasesColumnsParams = {
  canViewDatabase: (databaseId: string) => boolean
  canOperateDatabase: (databaseId: string) => boolean
  canManageDatabase: (databaseId: string) => boolean
  selectedDatabaseId?: string
  onSelectDatabase: (database: Database) => void
  openCredentialsModal: (database: Database) => void
  openDbmsMetadataModal: (database: Database) => void
  openIbcmdProfileModal: (database: Database) => void
  openMetadataManagementDrawer: (database: Database) => void
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
  canViewDatabase,
  canOperateDatabase,
  canManageDatabase,
  selectedDatabaseId,
  onSelectDatabase,
  openCredentialsModal,
  openDbmsMetadataModal,
  openIbcmdProfileModal,
  openMetadataManagementDrawer,
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
  const { t } = useDatabasesTranslation()
  const formatters = useLocaleFormatters()
  const statusLabels = useMemo(() => ({
    active: t(($) => $.status.active),
    inactive: t(($) => $.status.inactive),
    maintenance: t(($) => $.status.maintenance),
    error: t(($) => $.status.error),
    unknown: t(($) => $.status.unknown),
  }), [t])
  const healthLabels = useMemo(() => ({
    ok: t(($) => $.health.ok),
    degraded: t(($) => $.health.degraded),
    down: t(($) => $.health.down),
    unknown: t(($) => $.health.unknown),
  }), [t])
  const notAvailable = t(($) => $.shared.notAvailable)

  const formatDeniedTime = useCallback(
    (value?: string | null) => formatters.dateTime(value, { fallback: notAvailable }),
    [formatters, notAvailable]
  )

  type DatabaseHealthMeta = Database & {
    last_health_error?: string | null
    last_health_error_code?: string | null
  }

  return useMemo<ColumnsType<Database>>(() => ([
    {
      title: t(($) => $.columns.name),
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record: Database) => {
        const isSelected = record.id === selectedDatabaseId
        return (
          <Button
            type="text"
            style={{
              paddingInline: 0,
              height: 'auto',
              fontWeight: isSelected ? 600 : 500,
            }}
            onClick={() => onSelectDatabase(record)}
            aria-label={t(($) => $.page.openDatabase, { name })}
            aria-pressed={isSelected}
            disabled={!canViewDatabase(record.id)}
          >
            {name}
          </Button>
        )
      },
    },
    {
      title: t(($) => $.columns.host),
      dataIndex: 'host',
      key: 'host',
      width: 160,
    },
    {
      title: t(($) => $.columns.port),
      dataIndex: 'port',
      key: 'port',
      width: 90,
    },
    {
      title: t(($) => $.columns.status),
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => {
        const tag = getStatusTag(status, statusLabels)
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
    {
      title: t(($) => $.columns.health),
      dataIndex: 'last_check_status',
      key: 'last_check_status',
      width: 130,
      render: (_status: string, record: Database) => {
        const tag = getHealthTag(record.last_check_status, healthLabels)
        const healthMeta = record as DatabaseHealthMeta
        const errorMessage = healthMeta.last_health_error
        const errorCode = healthMeta.last_health_error_code
        const tooltip = errorMessage || errorCode
          ? (
            <div>
              {errorCode && <div>{`${t(($) => $.restrictions.permissionCode)}: ${errorCode}`}</div>}
              {errorMessage && <div>{`${t(($) => $.restrictions.message)}: ${errorMessage}`}</div>}
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
      title: t(($) => $.columns.credentials),
      key: 'credentials',
      width: 130,
      render: (_: unknown, record: Database) => (
        <Tag color={record.password_configured ? 'green' : 'default'}>
          {record.password_configured
            ? t(($) => $.credentials.configured)
            : t(($) => $.credentials.missing)}
        </Tag>
      ),
    },
    {
      title: t(($) => $.columns.restrictions),
      key: 'restrictions',
      width: 280,
      render: (_: unknown, record: Database) => {
        const jobsDeny = record.scheduled_jobs_deny
        const sessionsDeny = record.sessions_deny
        const jobsTag = (
          <Tag color={jobsDeny === true ? 'red' : jobsDeny === false ? 'green' : 'default'}>
            {jobsDeny === true
              ? t(($) => $.restrictions.jobsLocked)
              : jobsDeny === false
                ? t(($) => $.restrictions.jobsAllowed)
                : t(($) => $.restrictions.jobsUnknown)}
          </Tag>
        )
        const sessionsTagBase = (
          <Tag color={sessionsDeny === true ? 'red' : sessionsDeny === false ? 'green' : 'default'}>
            {sessionsDeny === true
              ? t(($) => $.restrictions.sessionsBlocked)
              : sessionsDeny === false
                ? t(($) => $.restrictions.sessionsAllowed)
                : t(($) => $.restrictions.sessionsUnknown)}
          </Tag>
        )
        const sessionsTag = sessionsDeny === true ? (
          <Tooltip
            title={
              <div>
                <div>{`${t(($) => $.restrictions.from)}: ${formatDeniedTime(record.denied_from)}`}</div>
                <div>{`${t(($) => $.restrictions.to)}: ${formatDeniedTime(record.denied_to)}`}</div>
                <div>{`${t(($) => $.restrictions.message)}: ${record.denied_message || notAvailable}`}</div>
                <div>{`${t(($) => $.restrictions.permissionCode)}: ${record.permission_code || notAvailable}`}</div>
                <div>{`${t(($) => $.restrictions.parameter)}: ${record.denied_parameter || notAvailable}`}</div>
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
      title: t(($) => $.columns.lastCheck),
      dataIndex: 'last_check',
      key: 'last_check',
      width: 170,
      render: (date: string) => formatters.dateTime(date, {
        fallback: t(($) => $.shared.never),
      }),
    },
    {
      title: t(($) => $.columns.actions),
      key: 'actions',
      width: 320,
      render: (_: unknown, record: Database) => {
        const canView = canViewDatabase(record.id)
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
                  message.success(t(($) => $.messages.healthCheckQueued, { name: record.name }))
                  if (res.operation_id) {
                    message.info(t(($) => $.messages.operationQueued, { id: res.operation_id }))
                  }
                } catch (e: unknown) {
                  const status = getErrorStatus(e)
                  const statusLabel = status ? ` (status ${status})` : ''
                  message.error(t(($) => $.messages.healthCheckFailed, {
                    error: getErrorMessage(e),
                    statusSuffix: statusLabel,
                  }))
                } finally {
                  markHealthCheckPending(record.id, false)
                }
              }}
              loading={healthCheckPendingIds.has(record.id)}
              disabled={!canOperate}
            >
              {t(($) => $.columns.check)}
            </Button>
            <Dropdown
              trigger={['click']}
              disabled={!canManage}
              menu={{
                items: [
                  { key: SetDatabaseStatusRequestStatusEnum.active, label: t(($) => $.bulk.setActive) },
                  { key: SetDatabaseStatusRequestStatusEnum.inactive, label: t(($) => $.bulk.setInactive) },
                  { key: SetDatabaseStatusRequestStatusEnum.maintenance, label: t(($) => $.bulk.setMaintenance) },
                ],
                onClick: async ({ key }) => {
                  try {
                    await runSetStatus([record.id], key as SetDatabaseStatusValue)
                  } catch (e: unknown) {
                    const status = getErrorStatus(e)
                    if (status === 403) {
                      message.error(t(($) => $.messages.manageAccessRequired))
                      return
                    }
                    message.error(t(($) => $.messages.statusUpdateFailed, { error: getErrorMessage(e) }))
                  }
                },
              }}
            >
              <Button size="small" icon={<EditOutlined />} disabled={!canManage}>
                {t(($) => $.columns.status)} <DownOutlined />
              </Button>
            </Dropdown>
            <Button
              size="small"
              icon={<KeyOutlined />}
              onClick={() => openCredentialsModal(record)}
              title={t(($) => $.detail.actions.credentials)}
              aria-label={t(($) => $.detail.actions.credentials)}
              disabled={!canManage}
            />
            <Tooltip title={t(($) => $.detail.actions.dbms)}>
              <Button
                size="small"
                icon={<DatabaseOutlined />}
                onClick={() => openDbmsMetadataModal(record)}
                aria-label={t(($) => $.detail.actions.dbms)}
                disabled={!canManage}
              />
            </Tooltip>
            <Tooltip title={t(($) => $.detail.actions.ibcmd)}>
              <Button
                size="small"
                icon={<LinkOutlined />}
                onClick={() => openIbcmdProfileModal(record)}
                aria-label={t(($) => $.detail.actions.ibcmd)}
                disabled={!canManage}
              />
            </Tooltip>
            <Tooltip title={t(($) => $.detail.actions.metadata)}>
              <Button
                size="small"
                icon={<DeploymentUnitOutlined />}
                onClick={() => openMetadataManagementDrawer(record)}
                aria-label={t(($) => $.detail.actions.metadata)}
                disabled={!canView}
              />
            </Tooltip>
            <Tooltip title={t(($) => $.detail.actions.extensions)}>
              <Button
                size="small"
                icon={<AppstoreOutlined />}
                onClick={() => openExtensionsDrawer(record)}
                aria-label={t(($) => $.detail.actions.extensions)}
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
    canViewDatabase,
    canManageDatabase,
    canOperateDatabase,
    getErrorMessage,
    getErrorStatus,
    handleSingleAction,
    healthCheck,
    healthCheckPendingIds,
    healthLabels,
    markHealthCheckPending,
    message,
    notAvailable,
    onSelectDatabase,
    openCredentialsModal,
    openDbmsMetadataModal,
    openIbcmdProfileModal,
    openMetadataManagementDrawer,
    openExtensionsDrawer,
    runSetStatus,
    selectedDatabaseId,
    statusLabels,
    t,
    formatters,
    formatDeniedTime,
  ])
}
