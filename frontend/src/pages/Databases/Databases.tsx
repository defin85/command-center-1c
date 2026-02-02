import { useState, useCallback, useMemo, useEffect } from 'react'
import { App, Button, Space, Select, Breadcrumb, Form, Typography, Dropdown } from 'antd'
import type { TableRowSelection } from 'antd/es/table/interface'
import { PlusOutlined, HomeOutlined, ClusterOutlined, HeartOutlined, EditOutlined, DownOutlined, AppstoreOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import type { Database } from '../../api/generated/model/database'
import type { Cluster } from '../../api/generated/model/cluster'
import { SetDatabaseStatusRequestStatus as SetDatabaseStatusRequestStatusEnum } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { ActionCatalogAction } from '../../api/types/actionCatalog'
import { BulkActionsToolbar, OperationConfirmModal } from '../../components/actions'
import type { DatabaseActionKey } from '../../components/actions'
import type { RASOperationType } from '../../api/operations'
import {
  useDatabases,
  useExecuteRasOperation,
  useHealthCheckDatabase,
  useBulkHealthCheckDatabases,
  useSetDatabaseStatus,
  useUpdateDatabaseCredentials,
  useUpdateDatabaseDbmsMetadata,
  useUpdateDatabaseIbcmdConnectionProfile,
  useDatabaseExtensionsSnapshot,
} from '../../api/queries/databases'
import { useClusters } from '../../api/queries/clusters'
import { useActionCatalog } from '../../api/queries/ui'
import { useAuthz } from '../../authz/useAuthz'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { DatabaseCredentialsModal } from './components/DatabaseCredentialsModal'
import { DatabaseDbmsMetadataModal } from './components/DatabaseDbmsMetadataModal'
import { DatabaseIbcmdConnectionProfileModal } from './components/DatabaseIbcmdConnectionProfileModal'
import { ExtensionsDrawer } from './components/ExtensionsDrawer'
import { useDatabasesColumns } from './components/useDatabasesColumns'
import { useExtensionsActions } from './components/useExtensionsActions'
import { buildIbcmdConnectionProfileUpdatePayload } from './lib/ibcmdConnectionProfile'

const EMPTY_CLUSTERS: Cluster[] = []
const EMPTY_ACTIONS: ActionCatalogAction[] = []

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
  const [dbmsMetadataModalVisible, setDbmsMetadataModalVisible] = useState(false)
  const [dbmsMetadataDatabase, setDbmsMetadataDatabase] = useState<Database | null>(null)
  const [dbmsMetadataForm] = Form.useForm()
  const [ibcmdProfileModalVisible, setIbcmdProfileModalVisible] = useState(false)
  const [ibcmdProfileDatabase, setIbcmdProfileDatabase] = useState<Database | null>(null)
  const [ibcmdProfileForm] = Form.useForm()
  const [extensionsDrawerVisible, setExtensionsDrawerVisible] = useState(false)
  const [extensionsDatabase, setExtensionsDatabase] = useState<Database | null>(null)

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
  const clusters = clustersResponse?.clusters ?? EMPTY_CLUSTERS
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
  const updateDatabaseDbmsMetadata = useUpdateDatabaseDbmsMetadata()
  const updateDatabaseIbcmdConnectionProfile = useUpdateDatabaseIbcmdConnectionProfile()
  const { runExtensionsAction, extensionsActionPendingId, resetExtensionsActionPendingId } = useExtensionsActions({ isStaff, message, modal, navigate })

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

  const extensionsActionsRaw = (actionCatalogQuery.data as unknown as { extensions?: { actions?: unknown } } | null)?.extensions?.actions
  const extensionsActions: ActionCatalogAction[] = Array.isArray(extensionsActionsRaw)
    ? (extensionsActionsRaw as ActionCatalogAction[])
    : EMPTY_ACTIONS
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

  const closeCredentialsModal = useCallback(() => {
    setCredentialsModalVisible(false)
    setCredentialsDatabase(null)
    credentialsForm.resetFields()
  }, [credentialsForm])

  const openDbmsMetadataModal = (database: Database) => {
    if (!canManageDatabase(database.id)) {
      message.error('Недостаточно прав для управления DBMS metadata базы')
      return
    }
    const dbAny = database as Database & { dbms?: string | null; db_server?: string | null; db_name?: string | null }
    setDbmsMetadataDatabase(database)
    dbmsMetadataForm.setFieldsValue({
      dbms: typeof dbAny.dbms === 'string' ? dbAny.dbms : '',
      db_server: typeof dbAny.db_server === 'string' ? dbAny.db_server : '',
      db_name: typeof dbAny.db_name === 'string' ? dbAny.db_name : '',
    })
    setDbmsMetadataModalVisible(true)
  }

  const closeDbmsMetadataModal = useCallback(() => {
    setDbmsMetadataModalVisible(false)
    setDbmsMetadataDatabase(null)
    dbmsMetadataForm.resetFields()
  }, [dbmsMetadataForm])

  const openIbcmdProfileModal = (database: Database) => {
    if (!canManageDatabase(database.id)) {
      message.error('Недостаточно прав для управления IBCMD profile базы')
      return
    }
    const dbAny = database as Database & {
      ibcmd_connection?: {
        mode?: string | null
        remote_url?: string | null
        offline?: Record<string, unknown> | null
      } | null
    }
    const profile = dbAny.ibcmd_connection ?? null
    const offlineRaw = profile?.offline && typeof profile.offline === 'object' ? profile.offline : null
    const offline = offlineRaw ? (offlineRaw as Record<string, unknown>) : {}
    setIbcmdProfileDatabase(database)
    ibcmdProfileForm.setFieldsValue({
      mode: typeof profile?.mode === 'string' ? profile.mode : 'auto',
      remote_url: typeof profile?.remote_url === 'string' ? profile.remote_url : '',
      offline: {
        config: typeof offline.config === 'string' ? offline.config : '',
        data: typeof offline.data === 'string' ? offline.data : '',
        db_path: typeof offline.db_path === 'string' ? offline.db_path : '',
        dbms: typeof offline.dbms === 'string' ? offline.dbms : '',
        db_server: typeof offline.db_server === 'string' ? offline.db_server : '',
        db_name: typeof offline.db_name === 'string' ? offline.db_name : '',
      },
    })
    setIbcmdProfileModalVisible(true)
  }

  const closeIbcmdProfileModal = useCallback(() => {
    setIbcmdProfileModalVisible(false)
    setIbcmdProfileDatabase(null)
    ibcmdProfileForm.resetFields()
  }, [ibcmdProfileForm])

  const handleIbcmdProfileSave = async () => {
    if (!ibcmdProfileDatabase) return
    if (!canManageDatabase(ibcmdProfileDatabase.id)) {
      message.error('Недостаточно прав для управления IBCMD profile базы')
      return
    }

    const values = await ibcmdProfileForm.validateFields()
    const payload = buildIbcmdConnectionProfileUpdatePayload(ibcmdProfileDatabase.id, values)

    updateDatabaseIbcmdConnectionProfile.mutate(payload, {
      onSuccess: (response) => {
        message.success(response.message || 'IBCMD profile обновлён')
        closeIbcmdProfileModal()
      },
      onError: (error: Error) => {
        message.error('Не удалось обновить IBCMD profile: ' + error.message)
      },
    })
  }

  const handleIbcmdProfileReset = () => {
    if (!ibcmdProfileDatabase) return
    if (!canManageDatabase(ibcmdProfileDatabase.id)) {
      message.error('Недостаточно прав для управления IBCMD profile базы')
      return
    }

    modal.confirm({
      title: 'Сбросить IBCMD profile базы?',
      content: 'Профиль подключения ibcmd будет удалён из metadata базы.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => {
        updateDatabaseIbcmdConnectionProfile.mutate(
          { database_id: ibcmdProfileDatabase.id, reset: true },
          {
            onSuccess: (response) => {
              message.success(response.message || 'IBCMD profile сброшен')
              closeIbcmdProfileModal()
            },
            onError: (error: Error) => {
              message.error('Не удалось сбросить IBCMD profile: ' + error.message)
            },
          }
        )
      },
    })
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
        closeCredentialsModal()
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
              closeCredentialsModal()
            },
            onError: (error: Error) => {
              message.error('Не удалось сбросить креды: ' + error.message)
            },
          }
        )
      },
    })
  }

  const handleDbmsMetadataSave = async () => {
    if (!dbmsMetadataDatabase) return
    if (!canManageDatabase(dbmsMetadataDatabase.id)) {
      message.error('Недостаточно прав для управления DBMS metadata базы')
      return
    }

    const values = await dbmsMetadataForm.validateFields()
    const dbms = (values.dbms ?? '').trim()
    const dbServer = (values.db_server ?? '').trim()
    const dbName = (values.db_name ?? '').trim()

    const payload: { database_id: string; dbms?: string; db_server?: string; db_name?: string } = {
      database_id: dbmsMetadataDatabase.id,
    }
    if (dbms) payload.dbms = dbms
    if (dbServer) payload.db_server = dbServer
    if (dbName) payload.db_name = dbName

    if (!payload.dbms && !payload.db_server && !payload.db_name) {
      message.info('Нет изменений для сохранения')
      return
    }

    updateDatabaseDbmsMetadata.mutate(payload, {
      onSuccess: (response) => {
        message.success(response.message || 'DBMS metadata обновлены')
        closeDbmsMetadataModal()
      },
      onError: (error: Error) => {
        message.error('Не удалось обновить DBMS metadata: ' + error.message)
      },
    })
  }

  const handleDbmsMetadataReset = () => {
    if (!dbmsMetadataDatabase) return
    if (!canManageDatabase(dbmsMetadataDatabase.id)) {
      message.error('Недостаточно прав для управления DBMS metadata базы')
      return
    }

    modal.confirm({
      title: 'Сбросить DBMS metadata базы?',
      content: 'Поля DBMS/DB server/DB name будут очищены.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: async () => {
        updateDatabaseDbmsMetadata.mutate(
          { database_id: dbmsMetadataDatabase.id, reset: true },
          {
            onSuccess: (response) => {
              message.success(response.message || 'DBMS metadata сброшены')
              closeDbmsMetadataModal()
            },
            onError: (error: Error) => {
              message.error('Не удалось сбросить DBMS metadata: ' + error.message)
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
    resetExtensionsActionPendingId()
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
  const columns = useDatabasesColumns({
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
  })

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
            aria-label="Cluster filter"
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
      <DatabaseCredentialsModal
        open={credentialsModalVisible}
        database={credentialsDatabase}
        form={credentialsForm}
        saving={updateDatabaseCredentials.isPending}
        onCancel={closeCredentialsModal}
        onSave={() => void handleCredentialsSave()}
        onReset={handleCredentialsReset}
      />
      <DatabaseDbmsMetadataModal
        open={dbmsMetadataModalVisible}
        database={dbmsMetadataDatabase}
        form={dbmsMetadataForm}
        saving={updateDatabaseDbmsMetadata.isPending}
        onCancel={closeDbmsMetadataModal}
        onSave={() => void handleDbmsMetadataSave()}
        onReset={handleDbmsMetadataReset}
      />
      <DatabaseIbcmdConnectionProfileModal
        open={ibcmdProfileModalVisible}
        database={ibcmdProfileDatabase}
        form={ibcmdProfileForm}
        saving={updateDatabaseIbcmdConnectionProfile.isPending}
        onCancel={closeIbcmdProfileModal}
        onSave={() => void handleIbcmdProfileSave()}
        onReset={handleIbcmdProfileReset}
      />

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
