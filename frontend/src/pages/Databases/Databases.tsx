import { useState, useCallback, useMemo, useEffect } from 'react'
import { App, Button, Space, Tag, Select, Breadcrumb, Modal, Form, Typography, Dropdown, Tooltip, Input } from 'antd'
import type { TableRowSelection } from 'antd/es/table/interface'
import { PlusOutlined, HomeOutlined, ClusterOutlined, HeartOutlined, EditOutlined, DownOutlined, KeyOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import type { Database } from '../../api/generated/model/database'
import { SetDatabaseStatusRequestStatusEnum } from '../../api/generated/model/setDatabaseStatusRequestStatusEnum'
import type { SetDatabaseStatusRequestStatusEnum as SetDatabaseStatusValue } from '../../api/generated/model/setDatabaseStatusRequestStatusEnum'
import { DatabaseActionsMenu, BulkActionsToolbar, OperationConfirmModal } from '../../components/actions'
import type { DatabaseActionKey } from '../../components/actions'
import type { RASOperationType } from '../../api/operations'
import {
  useDatabases,
  useExecuteRasOperation,
  useHealthCheckDatabase,
  useBulkHealthCheckDatabases,
  useSetDatabaseStatus,
  useUpdateDatabaseCredentials,
} from '../../api/queries/databases'
import { useClusters } from '../../api/queries/clusters'
import { useAuthz } from '../../authz'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { getHealthTag, getStatusTag } from '../../utils/databaseStatus'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

export const Databases = () => {
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const [searchParams] = useSearchParams()
  const clusterIdFromUrl = searchParams.get('cluster')

  // UI State
  const [selectedClusterId, setSelectedClusterId] = useState<string | undefined>(
    clusterIdFromUrl || undefined
  )
  const [credentialsModalVisible, setCredentialsModalVisible] = useState(false)
  const [credentialsDatabase, setCredentialsDatabase] = useState<Database | null>(null)
  const [credentialsForm] = Form.useForm()

  // Row selection state
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedDatabases, setSelectedDatabases] = useState<Database[]>([])
  const [healthCheckPendingIds, setHealthCheckPendingIds] = useState<Set<string>>(new Set())

  const canOperateAny = authz.isStaff || authz.canAnyDatabase('OPERATE')
  const canSelectRows = canOperateAny

  useEffect(() => {
    if (canSelectRows) return
    setSelectedRowKeys([])
    setSelectedDatabases([])
  }, [canSelectRows])

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'host', label: 'Host', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'port', label: 'Port', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'status', label: 'Status', groupKey: 'status', groupLabel: 'Status' },
    { key: 'last_check_status', label: 'Health', groupKey: 'status', groupLabel: 'Status' },
    { key: 'last_check', label: 'Last Check', sortable: true, groupKey: 'status', groupLabel: 'Status' },
    { key: 'credentials', label: 'Credentials', groupKey: 'access', groupLabel: 'Access' },
    { key: 'restrictions', label: 'Restrictions', groupKey: 'access', groupLabel: 'Access' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  // Confirm modal state
  const [confirmModal, setConfirmModal] = useState<{
    visible: boolean
    operation: string
    databases: Array<{ id: string; name: string }>
  }>({ visible: false, operation: '', databases: [] })

  // React Query hooks
  const { data: clustersResponse, isLoading: clustersLoading } = useClusters()
  const clusters = clustersResponse?.clusters ?? []
  const { isConnected: isDatabaseStreamConnected } = useDatabaseStreamStatus()
  const fallbackPollIntervalMs = isDatabaseStreamConnected ? false : 120000

  // Mutations
  const executeRasOperation = useExecuteRasOperation()
  const healthCheck = useHealthCheckDatabase()
  const bulkHealthCheck = useBulkHealthCheckDatabases()
  const setDatabaseStatus = useSetDatabaseStatus()
  const updateDatabaseCredentials = useUpdateDatabaseCredentials()

  // Derived state: selected cluster object
  const selectedCluster = useMemo(() => {
    if (!selectedClusterId || !clusters.length) return null
    return clusters.find((c) => c.id === selectedClusterId) || null
  }, [selectedClusterId, clusters])

  const canOperateDatabase = useCallback(
    (databaseId: string) => authz.canDatabase(databaseId, 'OPERATE'),
    [authz]
  )

  const canManageDatabase = useCallback(
    (databaseId: string) => authz.canDatabase(databaseId, 'MANAGE'),
    [authz]
  )

  const canOperateSelected = useMemo(
    () => selectedDatabases.length > 0 && selectedDatabases.every((db) => canOperateDatabase(db.id)),
    [selectedDatabases, canOperateDatabase]
  )

  const canManageSelected = useMemo(
    () => selectedDatabases.length > 0 && selectedDatabases.every((db) => canManageDatabase(db.id)),
    [selectedDatabases, canManageDatabase]
  )

  type AxiosErrorLike = { response?: { status?: number }; message?: string }

  const getErrorStatus = (error: unknown): number | undefined => {
    const maybe = error as AxiosErrorLike | null
    return maybe?.response?.status
  }

  const getErrorMessage = (error: unknown): string => {
    const maybe = error as AxiosErrorLike | null
    return maybe?.message || 'unknown error'
  }

  const handleClusterChange = (value: string | undefined) => {
    setSelectedClusterId(value)

    // Update URL
    if (value) {
      navigate(`/databases?cluster=${value}`, { replace: true })
    } else {
      navigate('/databases', { replace: true })
    }
  }

  const openCredentialsModal = (database: Database) => {
    if (!canManageDatabase(database.id)) {
      message.error('Недостаточно прав для управления кредами базы')
      return
    }
    setCredentialsDatabase(database)
    credentialsForm.setFieldsValue({
      username: database.username ?? '',
      password: '',
    })
    setCredentialsModalVisible(true)
  }

  const handleCredentialsSave = async () => {
    if (!credentialsDatabase) return
    if (!canManageDatabase(credentialsDatabase.id)) {
      message.error('Недостаточно прав для управления кредами базы')
      return
    }

    const values = await credentialsForm.validateFields()
    const username = (values.username ?? '').trim()
    const password = values.password ?? ''

    const payload: { database_id: string; username?: string; password?: string } = {
      database_id: credentialsDatabase.id,
    }

    if (username) payload.username = username
    if (password) payload.password = password

    if (!payload.username && !payload.password) {
      message.info('Нет изменений для сохранения')
      return
    }

    updateDatabaseCredentials.mutate(payload, {
      onSuccess: (response) => {
        message.success(response.message || 'Креды базы обновлены')
        setCredentialsModalVisible(false)
        setCredentialsDatabase(null)
        credentialsForm.resetFields()
      },
      onError: (error: Error) => {
        message.error('Не удалось обновить креды: ' + error.message)
      },
    })
  }

  const handleCredentialsReset = () => {
    if (!credentialsDatabase) return
    if (!canManageDatabase(credentialsDatabase.id)) {
      message.error('Недостаточно прав для управления кредами базы')
      return
    }

    modal.confirm({
      title: 'Сбросить креды базы?',
      content: 'Логин и пароль будут очищены.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: async () => {
        updateDatabaseCredentials.mutate(
          { database_id: credentialsDatabase.id, reset: true },
          {
            onSuccess: (response) => {
              message.success(response.message || 'Креды базы сброшены')
              setCredentialsModalVisible(false)
              setCredentialsDatabase(null)
              credentialsForm.resetFields()
            },
            onError: (error: Error) => {
              message.error('Не удалось сбросить креды: ' + error.message)
            },
          }
        )
      },
    })
  }


  // Row selection configuration
  const rowSelection: TableRowSelection<Database> | undefined = canSelectRows
    ? {
      selectedRowKeys,
      onChange: (keys, rows) => {
        setSelectedRowKeys(keys)
        setSelectedDatabases(rows)
      },
      getCheckboxProps: (record) => ({
        disabled: record.status === 'maintenance' || !canOperateDatabase(record.id),
      }),
    }
    : undefined

  const runBulkHealthCheck = useCallback(async (ids: string[]) => {
    const chunks: string[][] = []
    for (let i = 0; i < ids.length; i += 50) chunks.push(ids.slice(i, i + 50))

    const operationIds: string[] = []

    for (let i = 0; i < chunks.length; i++) {
      const res = await bulkHealthCheck.mutateAsync({ databaseIds: chunks[i] })
      if (res.operation_id) {
        operationIds.push(res.operation_id)
      }
    }

    if (operationIds.length === 1) {
      navigate(`/operations?operation=${operationIds[0]}`)
      return
    }

    modal.info({
      title: 'Health check queued',
      content: `Queued ${operationIds.length} operations. Check Operations for progress.`,
    })
    navigate('/operations')
  }, [bulkHealthCheck, modal, navigate])

  const runSetStatus = useCallback(async (ids: string[], status: SetDatabaseStatusValue) => {
    const res = await setDatabaseStatus.mutateAsync({ databaseIds: ids, status })
    const missingCount = res.not_found?.length ?? 0
    const missingSuffix = missingCount > 0 ? `, не найдено: ${missingCount}` : ''
    message.success(`Статус "${res.status}" применен к ${res.updated}${missingSuffix}`)
  }, [setDatabaseStatus, message])

  const markHealthCheckPending = useCallback((databaseId: string, pending: boolean) => {
    setHealthCheckPendingIds((prev) => {
      const next = new Set(prev)
      if (pending) {
        next.add(databaseId)
      } else {
        next.delete(databaseId)
      }
      return next
    })
  }, [])

  // Handler for single database action (context menu)
  const handleSingleAction = useCallback((action: DatabaseActionKey, database: Database) => {
    if (!canOperateDatabase(database.id)) {
      message.error('Недостаточно прав для операции')
      return
    }
    if (action === 'more') {
      // Open Operations Wizard with preselected database
      navigate(`/operations?wizard=true&databases=${database.id}`)
      return
    }

    // Show confirm modal for other actions
    setConfirmModal({
      visible: true,
      operation: action,
      databases: [{ id: database.id, name: database.name }],
    })
  }, [canOperateDatabase, message, navigate])

  // Handler for bulk action
  const handleBulkAction = useCallback((action: string) => {
    if (!canOperateSelected) {
      message.error('Недостаточно прав для массовой операции')
      return
    }
    setConfirmModal({
      visible: true,
      operation: action,
      databases: selectedDatabases.map((db) => ({ id: db.id, name: db.name })),
    })
  }, [canOperateSelected, message, selectedDatabases])

  // Confirm operation handler
  const handleConfirmOperation = useCallback(async (config?: {
    message?: string
    permission_code?: string
    denied_from?: string
    denied_to?: string
    parameter?: string
  }) => {
    const operationType = confirmModal.operation as RASOperationType
    const dbs = confirmModal.databases
    if (!dbs.every((db) => canOperateDatabase(db.id))) {
      message.error('Недостаточно прав для операции')
      return
    }

    executeRasOperation.mutate(
      {
        operationType,
        databaseIds: dbs.map((db) => db.id),
        config,
      },
      {
        onSuccess: (data) => {
          setConfirmModal({ visible: false, operation: '', databases: [] })
          setSelectedRowKeys([])
          setSelectedDatabases([])

          if (data.operation_id) {
            // Navigate to Operations Center to track the operation
            navigate(`/operations?operation=${data.operation_id}`)
          }
        },
      }
    )
  }, [canOperateDatabase, confirmModal, executeRasOperation, message, navigate])

  // Clear selection handler
  const handleClearSelection = useCallback(() => {
    setSelectedRowKeys([])
    setSelectedDatabases([])
  }, [])

  const formatDeniedTime = (value?: string | null) => {
    if (!value) return 'n/a'
    const parsed = dayjs(value)
    return parsed.isValid() ? parsed.format('DD.MM.YYYY HH:mm') : value
  }

  type DatabaseHealthMeta = Database & {
    last_health_error?: string | null
    last_health_error_code?: string | null
  }


  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string) => {
        return <span>{name}</span>
      },
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
              disabled={!canManage}
            />
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
  ]

  const table = useTableToolkit({
    tableId: 'databases',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const { data: databasesResponse, isLoading: databasesLoading } = useDatabases({
    filters: {
      cluster_id: selectedClusterId,
      search: table.search,
      filters: table.filtersPayload,
      sort: table.sortPayload,
      limit: table.pagination.pageSize,
      offset: pageStart,
    },
    refetchInterval: fallbackPollIntervalMs,
  })
  const databases = databasesResponse?.databases ?? []
  const totalDatabases = typeof databasesResponse?.total === 'number'
    ? databasesResponse.total
    : databases.length

  const totalColumnsWidth = table.totalColumnsWidth

  return (
    <div>
      {/* Breadcrumbs если пришли из кластера */}
      {selectedCluster && (
        <Breadcrumb style={{ marginBottom: 16 }}>
          <Breadcrumb.Item href="/">
            <HomeOutlined />
          </Breadcrumb.Item>
          <Breadcrumb.Item href="/clusters">
            <ClusterOutlined />
            <span>Clusters</span>
          </Breadcrumb.Item>
          <Breadcrumb.Item>{selectedCluster.name}</Breadcrumb.Item>
          <Breadcrumb.Item>Databases</Breadcrumb.Item>
        </Breadcrumb>
      )}

      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Space>
          <h1>Databases</h1>
          <Select
            style={{ width: 250 }}
            placeholder="All Clusters"
            allowClear
            value={selectedClusterId}
            onChange={handleClusterChange}
            loading={clustersLoading}
          >
            {clusters.map((cluster) => (
              <Select.Option key={cluster.id} value={cluster.id}>
                {cluster.name} ({cluster.databases_count ?? 0} databases)
              </Select.Option>
            ))}
          </Select>
        </Space>
        <Button type="primary" icon={<PlusOutlined />} disabled={!isStaff}>
          Add Database
        </Button>
      </Space>

      {canOperateAny && (
        <BulkActionsToolbar
          selectedCount={selectedRowKeys.length}
          onAction={handleBulkAction}
          onClearSelection={handleClearSelection}
          loading={executeRasOperation.isPending || bulkHealthCheck.isPending || setDatabaseStatus.isPending}
          disabled={!canOperateSelected}
        />
      )}

      {canOperateAny && selectedRowKeys.length > 0 && (
        <Space style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary">Ops:</Typography.Text>
          <Button
            icon={<HeartOutlined />}
            onClick={async () => {
              if (!canOperateSelected) {
                message.error('Недостаточно прав для массовой проверки')
                return
              }
              try {
                await runBulkHealthCheck(selectedDatabases.map((d) => d.id))
              } catch (e: unknown) {
                message.error(`Bulk health check failed: ${getErrorMessage(e)}`)
              }
            }}
            loading={bulkHealthCheck.isPending}
            disabled={!canOperateSelected}
          >
            Health check
          </Button>
          <Dropdown
            trigger={['click']}
            disabled={!canManageSelected}
            menu={{
              items: [
                { key: SetDatabaseStatusRequestStatusEnum.active, label: 'Set Active' },
                { key: SetDatabaseStatusRequestStatusEnum.inactive, label: 'Set Inactive' },
                { key: SetDatabaseStatusRequestStatusEnum.maintenance, label: 'Set Maintenance' },
              ],
              onClick: async ({ key }) => {
                if (!canManageSelected) {
                  message.error('Недостаточно прав для смены статуса')
                  return
                }
                try {
                  await runSetStatus(selectedDatabases.map((d) => d.id), key as SetDatabaseStatusValue)
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
            <Button icon={<EditOutlined />} loading={setDatabaseStatus.isPending} disabled={!canManageSelected}>
              Set status <DownOutlined />
            </Button>
          </Dropdown>
        </Space>
      )}

      <TableToolkit
        table={table}
        data={databases}
        total={totalDatabases}
        loading={databasesLoading}
        rowKey="id"
        columns={columns}
        rowSelection={rowSelection}
        tableLayout="fixed"
        scroll={{ x: totalColumnsWidth }}
        searchPlaceholder="Search databases"
      />

      <Modal
        title={credentialsDatabase ? `Credentials: ${credentialsDatabase.name}` : 'Credentials'}
        open={credentialsModalVisible}
        onCancel={() => {
          setCredentialsModalVisible(false)
          setCredentialsDatabase(null)
          credentialsForm.resetFields()
        }}
        footer={[
          <Button
            key="reset"
            danger
            onClick={handleCredentialsReset}
            disabled={!credentialsDatabase?.password_configured && !credentialsDatabase?.username}
          >
            Reset
          </Button>,
          <Button
            key="cancel"
            onClick={() => {
              setCredentialsModalVisible(false)
              setCredentialsDatabase(null)
              credentialsForm.resetFields()
            }}
          >
            Cancel
          </Button>,
          <Button
            key="save"
            type="primary"
            onClick={handleCredentialsSave}
            loading={updateDatabaseCredentials.isPending}
          >
            Save
          </Button>,
        ]}
      >
        <Form form={credentialsForm} layout="vertical">
          <Form.Item label="OData Username" name="username" htmlFor="database-credentials-username">
            <Input id="database-credentials-username" placeholder="Optional OData username" />
          </Form.Item>
          <Form.Item label="OData Password" name="password" htmlFor="database-credentials-password">
            <Input.Password
              id="database-credentials-password"
              placeholder={credentialsDatabase?.password_configured ? 'Configured' : 'Enter password'}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Operation Confirm Modal for RAS actions */}
      <OperationConfirmModal
        visible={confirmModal.visible}
        operation={confirmModal.operation}
        databases={confirmModal.databases}
        onConfirm={handleConfirmOperation}
        onCancel={() => setConfirmModal({ visible: false, operation: '', databases: [] })}
        loading={executeRasOperation.isPending}
      />
    </div>
  )
}
