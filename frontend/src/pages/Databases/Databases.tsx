import { useState, useCallback, useMemo, useEffect } from 'react'
import { App, Button, Space, Tag, Select, Breadcrumb, Modal, Form, Typography, Dropdown, Tooltip, Input, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { TableRowSelection } from 'antd/es/table/interface'
import { PlusOutlined, HomeOutlined, ClusterOutlined, HeartOutlined, EditOutlined, DownOutlined, KeyOutlined, AppstoreOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import type { Database } from '../../api/generated/model/database'
import { SetDatabaseStatusRequestStatus as SetDatabaseStatusRequestStatusEnum } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { ActionCatalogAction } from '../../api/generated/model/actionCatalogAction'
import type { ExecuteIbcmdCliOperationRequest } from '../../api/generated/model/executeIbcmdCliOperationRequest'
import { getV2 } from '../../api/generated'
import { apiClient } from '../../api/client'
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
  useDatabaseExtensionsSnapshot,
} from '../../api/queries/databases'
import { useClusters } from '../../api/queries/clusters'
import { useActionCatalog } from '../../api/queries/ui'
import { useAuthz } from '../../authz'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { getHealthTag, getStatusTag } from '../../utils/databaseStatus'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { ExtensionsDrawer } from './components/ExtensionsDrawer'

const api = getV2()

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
  const [extensionsDrawerVisible, setExtensionsDrawerVisible] = useState(false)
  const [extensionsDatabase, setExtensionsDatabase] = useState<Database | null>(null)
  const [extensionsActionPendingId, setExtensionsActionPendingId] = useState<string | null>(null)

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
  const actionCatalogQuery = useActionCatalog()
  const extensionsSnapshotQuery = useDatabaseExtensionsSnapshot({
    id: extensionsDatabase?.id ?? '',
    enabled: extensionsDrawerVisible && Boolean(extensionsDatabase?.id),
  })

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

  const extensionsActions: ActionCatalogAction[] = (actionCatalogQuery.data?.extensions?.actions ?? []) as ActionCatalogAction[]
  const extensionsDatabaseCardActions = useMemo(
    () => extensionsActions.filter((action) => action.contexts.includes('database_card')),
    [extensionsActions]
  )
  const extensionsBulkActions = useMemo(
    () => extensionsActions.filter((action) => action.contexts.includes('bulk_page')),
    [extensionsActions]
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

  const openExtensionsDrawer = (database: Database) => {
    if (!canOperateDatabase(database.id)) {
      message.error('Недостаточно прав для операций с расширениями')
      return
    }
    setExtensionsDatabase(database)
    setExtensionsDrawerVisible(true)
  }

  const closeExtensionsDrawer = () => {
    setExtensionsDrawerVisible(false)
    setExtensionsDatabase(null)
    setExtensionsActionPendingId(null)
  }

  const executeExtensionsAction = useCallback(async (action: ActionCatalogAction, databaseIds: string[]) => {
    const executor = action.executor
    const kind = executor.kind

    if (kind === 'ibcmd_cli') {
      const commandId = (executor.command_id ?? '').trim()
      if (!commandId) {
        throw new Error('Action executor missing command_id')
      }

      const timeoutSeconds = executor.fixed?.timeout_seconds
      const payload: ExecuteIbcmdCliOperationRequest = {
        command_id: commandId,
        mode: executor.mode === 'manual' ? 'manual' : 'guided',
        database_ids: databaseIds,
        params: executor.params ?? {},
        additional_args: executor.additional_args ?? [],
        stdin: executor.stdin ?? '',
        confirm_dangerous: executor.fixed?.confirm_dangerous === true,
        timeout_seconds: typeof timeoutSeconds === 'number' ? timeoutSeconds : undefined,
      }

      const res = await api.postOperationsExecuteIbcmdCli(payload)
      message.success(`Операция поставлена в очередь: ${action.label}`)
      if (res.operation_id) {
        navigate(`/operations?operation=${res.operation_id}`)
      }
      return
    }

    if (kind === 'designer_cli') {
      const command = (executor.command_id ?? '').trim()
      if (!command) {
        throw new Error('Action executor missing command_id')
      }
      const res = await api.postOperationsExecute({
        operation_type: 'designer_cli',
        database_ids: databaseIds,
        config: {
          command,
          args: executor.additional_args ?? [],
        },
      })
      message.success(`Операция поставлена в очередь: ${action.label}`)
      if (res.operation_id) {
        navigate(`/operations?operation=${res.operation_id}`)
      }
      return
    }

    if (kind === 'workflow') {
      const workflowId = (executor.workflow_id ?? '').trim()
      if (!workflowId) {
        throw new Error('Action executor missing workflow_id')
      }
      const baseContext = executor.params && typeof executor.params === 'object' ? executor.params : {}
      const res = await api.postWorkflowsExecuteWorkflow({
        workflow_id: workflowId,
        mode: 'async',
        input_context: {
          ...baseContext,
          database_ids: databaseIds,
        },
      })
      message.success(`Workflow запущен: ${action.label}`)
      if (res.execution_id) {
        navigate(`/workflows/executions/${res.execution_id}`)
      }
      return
    }

    throw new Error(`Unsupported action executor kind: ${kind}`)
  }, [message, navigate])

  const runExtensionsAction = useCallback(async (action: ActionCatalogAction, databaseIds: string[]) => {
    if (extensionsActionPendingId) return

    const loadPreview = async () => {
      const response = await apiClient.post('/api/v2/ui/execution-plan/preview/', {
        executor: action.executor,
        database_ids: databaseIds,
      })
      return response.data as unknown
    }

    type UIBinding = {
      target_ref?: string
      source_ref?: string
      resolve_at?: string
      sensitive?: boolean
      status?: string
      reason?: string | null
    }

    const extractBindings = (preview: unknown): UIBinding[] => {
      if (!preview || typeof preview !== 'object') return []
      const p = preview as Record<string, unknown>
      const raw = p.bindings
      if (!Array.isArray(raw)) return []
      return raw.filter((item) => item && typeof item === 'object') as UIBinding[]
    }

    const formatPreview = (preview: unknown): string => {
      if (!preview || typeof preview !== 'object') return ''
      const p = preview as Record<string, unknown>
      const plan = p.execution_plan as Record<string, unknown> | undefined
      if (!plan || typeof plan !== 'object') return ''
      const kind = String(plan.kind ?? '')
      const argv = Array.isArray(plan.argv_masked) ? plan.argv_masked.filter((x) => typeof x === 'string') : []
      const workflowId = typeof plan.workflow_id === 'string' ? plan.workflow_id : null
      const lines: string[] = []
      if (kind) lines.push(`kind: ${kind}`)
      if (workflowId) lines.push(`workflow_id: ${workflowId}`)
      if (argv.length > 0) {
        lines.push('argv_masked:')
        lines.push(...argv.map((x) => `  ${x}`))
      }
      return lines.join('\n')
    }

    const bindingColumns: ColumnsType<UIBinding> = [
      { title: 'Target', dataIndex: 'target_ref', key: 'target_ref' },
      { title: 'Source', dataIndex: 'source_ref', key: 'source_ref' },
      { title: 'Resolve', dataIndex: 'resolve_at', key: 'resolve_at', width: 90 },
      {
        title: 'Sensitive',
        dataIndex: 'sensitive',
        key: 'sensitive',
        width: 90,
        render: (value: boolean | undefined) => (value ? <Tag color="red">yes</Tag> : <Tag>no</Tag>),
      },
      { title: 'Status', dataIndex: 'status', key: 'status', width: 110 },
      { title: 'Reason', dataIndex: 'reason', key: 'reason' },
    ]

    const doRun = async () => {
      setExtensionsActionPendingId(action.id)
      try {
        await executeExtensionsAction(action, databaseIds)
      } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : 'unknown error'
        message.error(`Не удалось выполнить действие: ${errorMessage}`)
      } finally {
        setExtensionsActionPendingId(null)
      }
    }

    if (isStaff) {
      const count = databaseIds.length
      let previewText = ''
      let previewError = ''
      let previewBindings: UIBinding[] = []
      try {
        const preview = await loadPreview()
        previewText = formatPreview(preview)
        previewBindings = extractBindings(preview)
      } catch (e: unknown) {
        previewError = e instanceof Error ? e.message : 'preview failed'
      }

      modal.confirm({
        title: action.executor.fixed?.confirm_dangerous === true ? 'Подтвердить опасное действие?' : 'Подтвердить действие?',
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              Действие &quot;{action.label}&quot; будет выполнено для {count} баз(ы).
            </div>
            {previewError ? (
              <div style={{ marginBottom: 8, color: '#cf1322' }}>Preview error: {previewError}</div>
            ) : null}
            {previewText ? (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{previewText}</pre>
            ) : (
              <div style={{ opacity: 0.7 }}>Preview not available</div>
            )}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Binding Provenance:</div>
              {previewBindings.length > 0 ? (
                <Table
                  size="small"
                  rowKey={(_, idx) => String(idx)}
                  pagination={false}
                  dataSource={previewBindings}
                  columns={bindingColumns}
                  scroll={{ x: 900 }}
                />
              ) : (
                <div style={{ opacity: 0.7 }}>No bindings</div>
              )}
            </div>
          </div>
        ),
        okText: 'Выполнить',
        cancelText: 'Отмена',
        okButtonProps: { danger: action.executor.fixed?.confirm_dangerous === true },
        onOk: doRun,
      })
      return
    }

    if (action.executor.fixed?.confirm_dangerous === true) {
      const count = databaseIds.length
      modal.confirm({
        title: 'Подтвердить опасное действие?',
        content: `Действие "${action.label}" будет выполнено для ${count} баз(ы).`,
        okText: 'Выполнить',
        cancelText: 'Отмена',
        okButtonProps: { danger: true },
        onOk: doRun,
      })
      return
    }

    await doRun()
  }, [executeExtensionsAction, extensionsActionPendingId, isStaff, message, modal])

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
            <Tooltip title="Extensions">
              <Button
                size="small"
                icon={<AppstoreOutlined />}
                onClick={() => openExtensionsDrawer(record)}
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
          {extensionsBulkActions.length > 0 && (
            <Dropdown
              trigger={['click']}
              disabled={!canOperateSelected || actionCatalogQuery.isLoading || Boolean(extensionsActionPendingId)}
              menu={{
                items: extensionsBulkActions.map((action) => ({
                  key: action.id,
                  label: action.label,
                  danger: action.executor.fixed?.confirm_dangerous === true,
                })),
                onClick: async ({ key }) => {
                  if (!canOperateSelected) {
                    message.error('Недостаточно прав для операций с расширениями')
                    return
                  }
                  const action = extensionsBulkActions.find((item) => item.id === key)
                  if (!action) return
                  await runExtensionsAction(action, selectedDatabases.map((d) => d.id))
                },
              }}
            >
              <Button icon={<AppstoreOutlined />} loading={extensionsActionPendingId !== null} disabled={!canOperateSelected}>
                Extensions <DownOutlined />
              </Button>
            </Dropdown>
          )}
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

      <ExtensionsDrawer
        open={extensionsDrawerVisible}
        databaseName={extensionsDatabase?.name}
        actions={extensionsDatabaseCardActions}
        actionsLoading={actionCatalogQuery.isLoading}
        pendingActionId={extensionsActionPendingId}
        onClose={closeExtensionsDrawer}
        onRunAction={async (action) => {
          if (!extensionsDatabase) return
          await runExtensionsAction(action, [extensionsDatabase.id])
        }}
        snapshot={extensionsSnapshotQuery.data ?? null}
        snapshotLoading={extensionsSnapshotQuery.isLoading}
        snapshotFetching={extensionsSnapshotQuery.isFetching}
        onRefreshSnapshot={() => {
          if (!extensionsDatabase) return
          extensionsSnapshotQuery.refetch()
        }}
      />

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
