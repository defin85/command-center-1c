import { useState, useCallback, useMemo, useEffect } from 'react'
import { App, Button, Checkbox, Dropdown, Form, Input, Pagination, Select, Space, Tag, Typography } from 'antd'
import { PlusOutlined, HeartOutlined, EditOutlined, DownOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import type { Database } from '../../api/generated/model/database'
import type { Cluster } from '../../api/generated/model/cluster'
import { SetDatabaseStatusRequestStatus as SetDatabaseStatusRequestStatusEnum } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import { BulkActionsToolbar, OperationConfirmModal } from '../../components/actions'
import type { DatabaseActionKey } from '../../components/actions'
import type { RASOperationType } from '../../api/operations'
import {
  useDatabases,
  useDatabase,
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
import { useAuthz } from '../../authz/useAuthz'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { DatabaseCredentialsModal } from './components/DatabaseCredentialsModal'
import { DatabaseDbmsMetadataModal } from './components/DatabaseDbmsMetadataModal'
import { DatabaseIbcmdConnectionProfileModal } from './components/DatabaseIbcmdConnectionProfileModal'
import { DatabaseMetadataManagementDrawer } from './components/DatabaseMetadataManagementDrawer'
import { ExtensionsDrawer } from './components/ExtensionsDrawer'
import { useDatabasesColumns } from './components/useDatabasesColumns'
import {
  DatabaseWorkspaceDetailPanel,
  type DatabaseManagementContext,
} from './components/DatabaseWorkspaceDetailPanel'
import { buildIbcmdConnectionProfileUpdatePayload } from './lib/ibcmdConnectionProfile'
import { getHealthTag, getStatusTag } from '../../utils/databaseStatus'
import { EntityDetails, EntityList, MasterDetailShell, PageHeader, WorkspacePage } from '../../components/platform'
import { confirmWithTracking } from '../../observability/confirmWithTracking'

const EMPTY_CLUSTERS: Cluster[] = []
const EMPTY_DATABASES: Database[] = []
const DEFAULT_DATABASE_CONTEXT = 'inspect' as const

const parseDatabaseContext = (value: string | null): DatabaseManagementContext => (
  value === 'credentials'
  || value === 'dbms'
  || value === 'ibcmd'
  || value === 'metadata'
  || value === 'extensions'
    ? value
    : DEFAULT_DATABASE_CONTEXT
)

const buildIbcmdOfflineEntries = (database: Database): Array<{ key: string; value: string }> => {
  const profile = database.ibcmd_connection
  const offlineRaw = profile && typeof profile === 'object' && 'offline' in profile
    ? profile.offline
    : null
  const offline = offlineRaw && typeof offlineRaw === 'object'
    ? offlineRaw as Record<string, unknown>
    : {}

  const entries: Array<{ key: string; value: string }> = []
  for (const [rawKey, rawValue] of Object.entries(offline)) {
    const key = rawKey.trim()
    if (!key || typeof rawValue !== 'string') continue
    const value = rawValue.trim()
    if (!value) continue
    if (key === 'db_user' || key === 'db_pwd' || key === 'db_password') continue
    entries.push({ key, value })
  }

  entries.sort((left, right) => left.key.localeCompare(right.key))
  return entries
}

const buildCatalogButtonStyle = (selected: boolean) => ({
  justifyContent: 'flex-start',
  height: 'auto',
  paddingBlock: 12,
  paddingInline: 12,
  borderRadius: 8,
  border: selected ? '1px solid #91caff' : '1px solid #f0f0f0',
  borderInlineStart: selected ? '4px solid #1677ff' : '4px solid transparent',
  background: selected ? '#e6f4ff' : '#fff',
  boxShadow: selected ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
})

export const Databases = () => {
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const hasTenantContext = Boolean(localStorage.getItem('active_tenant_id'))
  const mutatingDisabled = isStaff && !hasTenantContext
  const [searchParams, setSearchParams] = useSearchParams()
  const clusterIdFromUrl = searchParams.get('cluster') || undefined
  const selectedDatabaseIdFromUrl = searchParams.get('database') || undefined
  const activeContext = parseDatabaseContext(searchParams.get('context'))

  // UI State
  const [credentialsForm] = Form.useForm()
  const [dbmsMetadataForm] = Form.useForm()
  const [ibcmdProfileForm] = Form.useForm()

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

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams]
  )

  // React Query hooks
  const { data: clustersResponse, isLoading: clustersLoading } = useClusters()
  const clusters = clustersResponse?.clusters ?? EMPTY_CLUSTERS
  const { isConnected: isDatabaseStreamConnected } = useDatabaseStreamStatus()
  const fallbackPollIntervalMs = isDatabaseStreamConnected ? false : 120000

  // Mutations
  const executeRasOperation = useExecuteRasOperation()
  const healthCheck = useHealthCheckDatabase()
  const bulkHealthCheck = useBulkHealthCheckDatabases()
  const setDatabaseStatus = useSetDatabaseStatus()
  const updateDatabaseCredentials = useUpdateDatabaseCredentials()
  const updateDatabaseDbmsMetadata = useUpdateDatabaseDbmsMetadata()
  const updateDatabaseIbcmdConnectionProfile = useUpdateDatabaseIbcmdConnectionProfile()

  // Derived state: selected cluster object
  const selectedCluster = useMemo(() => {
    if (!clusterIdFromUrl || !clusters.length) return null
    return clusters.find((c) => c.id === clusterIdFromUrl) || null
  }, [clusterIdFromUrl, clusters])

  const canOperateDatabase = useCallback(
    (databaseId: string) => authz.canDatabase(databaseId, 'OPERATE'),
    [authz]
  )

  const canManageDatabase = useCallback(
    (databaseId: string) => authz.canDatabase(databaseId, 'MANAGE'),
    [authz]
  )

  const canViewDatabase = useCallback(
    (databaseId: string) => authz.canDatabase(databaseId, 'VIEW'),
    [authz]
  )

  const canOperateSelected = useMemo(
    () => selectedDatabases.length > 0 && selectedDatabases.every((db) => canOperateDatabase(db.id)),
    [selectedDatabases, canOperateDatabase]
  )

  const metadataManagementMutatingDisabled = useMemo(() => {
    if (mutatingDisabled) return true
    if (!selectedDatabaseIdFromUrl) return true
    return !canOperateDatabase(selectedDatabaseIdFromUrl)
  }, [canOperateDatabase, mutatingDisabled, selectedDatabaseIdFromUrl])

  const metadataManagementEligibilityMutatingDisabled = useMemo(() => {
    if (mutatingDisabled) return true
    if (!selectedDatabaseIdFromUrl) return true
    return !canManageDatabase(selectedDatabaseIdFromUrl)
  }, [canManageDatabase, mutatingDisabled, selectedDatabaseIdFromUrl])

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
    updateSearchParams({
      cluster: value ?? null,
      database: null,
      context: null,
    })
  }

  const handleSelectDatabase = useCallback((database: Database) => {
    updateSearchParams({
      database: database.id,
      context: DEFAULT_DATABASE_CONTEXT,
    })
  }, [updateSearchParams])

  const openCredentialsModal = useCallback((database: Database) => {
    if (!canManageDatabase(database.id)) {
      message.error('Недостаточно прав для управления кредами базы')
      return
    }
    updateSearchParams({
      database: database.id,
      context: 'credentials',
    })
  }, [canManageDatabase, message, updateSearchParams])

  const closeCredentialsModal = useCallback(() => {
    credentialsForm.resetFields()
    updateSearchParams({
      context: selectedDatabaseIdFromUrl ? DEFAULT_DATABASE_CONTEXT : null,
    })
  }, [credentialsForm, selectedDatabaseIdFromUrl, updateSearchParams])

  const openDbmsMetadataModal = useCallback((database: Database) => {
    if (!canManageDatabase(database.id)) {
      message.error('Недостаточно прав для управления DBMS metadata базы')
      return
    }
    updateSearchParams({
      database: database.id,
      context: 'dbms',
    })
  }, [canManageDatabase, message, updateSearchParams])

  const closeDbmsMetadataModal = useCallback(() => {
    dbmsMetadataForm.resetFields()
    updateSearchParams({
      context: selectedDatabaseIdFromUrl ? DEFAULT_DATABASE_CONTEXT : null,
    })
  }, [dbmsMetadataForm, selectedDatabaseIdFromUrl, updateSearchParams])

  const openIbcmdProfileModal = useCallback((database: Database) => {
    if (!canManageDatabase(database.id)) {
      message.error('Недостаточно прав для управления IBCMD profile базы')
      return
    }
    updateSearchParams({
      database: database.id,
      context: 'ibcmd',
    })
  }, [canManageDatabase, message, updateSearchParams])

  const closeIbcmdProfileModal = useCallback(() => {
    ibcmdProfileForm.resetFields()
    updateSearchParams({
      context: selectedDatabaseIdFromUrl ? DEFAULT_DATABASE_CONTEXT : null,
    })
  }, [ibcmdProfileForm, selectedDatabaseIdFromUrl, updateSearchParams])

  const handleIbcmdProfileSave = async () => {
    if (!selectedDatabaseIdFromUrl) return
    if (!canManageDatabase(selectedDatabaseIdFromUrl)) {
      message.error('Недостаточно прав для управления IBCMD profile базы')
      return
    }

    const values = await ibcmdProfileForm.validateFields()
    const payload = buildIbcmdConnectionProfileUpdatePayload(selectedDatabaseIdFromUrl, values)

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
    if (!selectedDatabaseIdFromUrl) return
    if (!canManageDatabase(selectedDatabaseIdFromUrl)) {
      message.error('Недостаточно прав для управления IBCMD profile базы')
      return
    }

    confirmWithTracking(modal, {
      title: 'Сбросить IBCMD profile базы?',
      content: 'Профиль подключения ibcmd будет удалён из metadata базы.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => {
        updateDatabaseIbcmdConnectionProfile.mutate(
          { database_id: selectedDatabaseIdFromUrl, reset: true },
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
    }, {
      actionKind: 'operator.action',
      actionName: 'Reset IBCMD connection profile',
      context: {
        database_id: selectedDatabaseIdFromUrl,
      },
    })
  }

  const handleCredentialsSave = async () => {
    if (!selectedDatabaseIdFromUrl) return
    if (!canManageDatabase(selectedDatabaseIdFromUrl)) {
      message.error('Недостаточно прав для управления кредами базы')
      return
    }

    const values = await credentialsForm.validateFields()
    const username = (values.username ?? '').trim()
    const password = values.password ?? ''

    const payload: { database_id: string; username?: string; password?: string } = {
      database_id: selectedDatabaseIdFromUrl,
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
    if (!selectedDatabaseIdFromUrl) return
    if (!canManageDatabase(selectedDatabaseIdFromUrl)) {
      message.error('Недостаточно прав для управления кредами базы')
      return
    }

    confirmWithTracking(modal, {
      title: 'Сбросить креды базы?',
      content: 'Логин и пароль будут очищены.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: async () => {
        updateDatabaseCredentials.mutate(
          { database_id: selectedDatabaseIdFromUrl, reset: true },
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
    }, {
      actionKind: 'operator.action',
      actionName: 'Reset database credentials',
      context: {
        database_id: selectedDatabaseIdFromUrl,
      },
    })
  }

  const handleDbmsMetadataSave = async () => {
    if (!selectedDatabaseIdFromUrl) return
    if (!canManageDatabase(selectedDatabaseIdFromUrl)) {
      message.error('Недостаточно прав для управления DBMS metadata базы')
      return
    }

    const values = await dbmsMetadataForm.validateFields()
    const dbms = (values.dbms ?? '').trim()
    const dbServer = (values.db_server ?? '').trim()
    const dbName = (values.db_name ?? '').trim()

    const payload: { database_id: string; dbms?: string; db_server?: string; db_name?: string } = {
      database_id: selectedDatabaseIdFromUrl,
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
    if (!selectedDatabaseIdFromUrl) return
    if (!canManageDatabase(selectedDatabaseIdFromUrl)) {
      message.error('Недостаточно прав для управления DBMS metadata базы')
      return
    }

    confirmWithTracking(modal, {
      title: 'Сбросить DBMS metadata базы?',
      content: 'Поля DBMS/DB server/DB name будут очищены.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: async () => {
        updateDatabaseDbmsMetadata.mutate(
          { database_id: selectedDatabaseIdFromUrl, reset: true },
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
    }, {
      actionKind: 'operator.action',
      actionName: 'Reset DBMS metadata',
      context: {
        database_id: selectedDatabaseIdFromUrl,
      },
    })
  }

  const openExtensionsDrawer = useCallback((database: Database) => {
    if (!canOperateDatabase(database.id)) {
      message.error('Недостаточно прав для операций с расширениями')
      return
    }
    updateSearchParams({
      database: database.id,
      context: 'extensions',
    })
  }, [canOperateDatabase, message, updateSearchParams])

  const closeExtensionsDrawer = useCallback(() => {
    updateSearchParams({
      context: selectedDatabaseIdFromUrl ? DEFAULT_DATABASE_CONTEXT : null,
    })
  }, [selectedDatabaseIdFromUrl, updateSearchParams])

  const openMetadataManagementDrawer = useCallback((database: Database) => {
    if (!canViewDatabase(database.id)) {
      message.error('Недостаточно прав для просмотра metadata management')
      return
    }
    updateSearchParams({
      database: database.id,
      context: 'metadata',
    })
  }, [canViewDatabase, message, updateSearchParams])

  const closeMetadataManagementDrawer = useCallback(() => {
    updateSearchParams({
      context: selectedDatabaseIdFromUrl ? DEFAULT_DATABASE_CONTEXT : null,
    })
  }, [selectedDatabaseIdFromUrl, updateSearchParams])

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

  const handleToggleBulkSelection = useCallback((database: Database, checked: boolean) => {
    setSelectedRowKeys((current) => {
      if (checked) {
        return current.includes(database.id) ? current : [...current, database.id]
      }
      return current.filter((key) => key !== database.id)
    })
  }, [])

  const columns = useDatabasesColumns({
    canViewDatabase,
    canOperateDatabase,
    canManageDatabase,
    selectedDatabaseId: selectedDatabaseIdFromUrl,
    onSelectDatabase: handleSelectDatabase,
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
  })

  const table = useTableToolkit({
    tableId: 'databases',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
    disableServerMetadata: true,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const { data: databasesResponse, isLoading: databasesLoading } = useDatabases({
    filters: {
      cluster_id: clusterIdFromUrl,
      search: table.search,
      filters: table.filtersPayload,
      sort: table.sortPayload,
      limit: table.pagination.pageSize,
      offset: pageStart,
    },
    refetchInterval: fallbackPollIntervalMs,
  })
  const databases = databasesResponse?.databases ?? EMPTY_DATABASES

  useEffect(() => {
    setSelectedRowKeys((current) => current.filter((key) => databases.some((database) => database.id === key)))
  }, [databases])

  useEffect(() => {
    setSelectedDatabases(databases.filter((database) => selectedRowKeys.includes(database.id)))
  }, [databases, selectedRowKeys])

  const totalDatabases = typeof databasesResponse?.total === 'number'
    ? databasesResponse.total
    : databases.length
  const selectedDatabaseFromCatalog = useMemo(
    () => databases.find((database) => database.id === selectedDatabaseIdFromUrl) ?? null,
    [databases, selectedDatabaseIdFromUrl]
  )
  const selectedDatabaseQuery = useDatabase({
    id: selectedDatabaseIdFromUrl ?? '',
    enabled: Boolean(selectedDatabaseIdFromUrl) && !selectedDatabaseFromCatalog,
  })
  const selectedDatabase = selectedDatabaseFromCatalog ?? selectedDatabaseQuery.data ?? null
  const selectedDatabaseLoading = Boolean(selectedDatabaseIdFromUrl) && !selectedDatabaseFromCatalog && selectedDatabaseQuery.isLoading
  const selectedDatabaseError = selectedDatabaseQuery.error
    ? getErrorMessage(selectedDatabaseQuery.error)
    : null
  const credentialsModalVisible = activeContext === 'credentials' && Boolean(selectedDatabaseIdFromUrl)
  const dbmsMetadataModalVisible = activeContext === 'dbms' && Boolean(selectedDatabaseIdFromUrl)
  const ibcmdProfileModalVisible = activeContext === 'ibcmd' && Boolean(selectedDatabaseIdFromUrl)
  const metadataManagementDrawerVisible = activeContext === 'metadata' && Boolean(selectedDatabaseIdFromUrl)
  const extensionsDrawerVisible = activeContext === 'extensions' && Boolean(selectedDatabaseIdFromUrl)
  const inspectDetailOpen = Boolean(selectedDatabaseIdFromUrl) && activeContext === DEFAULT_DATABASE_CONTEXT
  const extensionsSnapshotQuery = useDatabaseExtensionsSnapshot({
    id: selectedDatabase?.id ?? '',
    enabled: extensionsDrawerVisible && Boolean(selectedDatabase?.id),
  })
  const canViewSelectedDatabase = selectedDatabase ? canViewDatabase(selectedDatabase.id) : false
  const canManageSelectedDatabase = selectedDatabase ? canManageDatabase(selectedDatabase.id) : false
  const canOperateSelectedDatabase = selectedDatabase ? canOperateDatabase(selectedDatabase.id) : false

  useEffect(() => {
    if (!credentialsModalVisible || !selectedDatabase) return
    credentialsForm.setFieldsValue({
      username: selectedDatabase.username ?? '',
      password: '',
    })
  }, [credentialsForm, credentialsModalVisible, selectedDatabase])

  useEffect(() => {
    if (!dbmsMetadataModalVisible || !selectedDatabase) return
    dbmsMetadataForm.setFieldsValue({
      dbms: typeof selectedDatabase.dbms === 'string' ? selectedDatabase.dbms : '',
      db_server: typeof selectedDatabase.db_server === 'string' ? selectedDatabase.db_server : '',
      db_name: typeof selectedDatabase.db_name === 'string' ? selectedDatabase.db_name : '',
    })
  }, [dbmsMetadataForm, dbmsMetadataModalVisible, selectedDatabase])

  useEffect(() => {
    if (!ibcmdProfileModalVisible || !selectedDatabase) return
    const profile = selectedDatabase.ibcmd_connection && typeof selectedDatabase.ibcmd_connection === 'object'
      ? selectedDatabase.ibcmd_connection
      : null
    ibcmdProfileForm.setFieldsValue({
      remote: typeof profile?.remote === 'string' ? profile.remote : '',
      pid: typeof profile?.pid === 'number' ? profile.pid : null,
      offline_entries: buildIbcmdOfflineEntries(selectedDatabase),
    })
  }, [ibcmdProfileForm, ibcmdProfileModalVisible, selectedDatabase])

  const handleOpenDetailContext = useCallback(
    (context: Exclude<DatabaseManagementContext, 'inspect'>) => {
      if (!selectedDatabase) return
      switch (context) {
        case 'credentials':
          openCredentialsModal(selectedDatabase)
          break
        case 'dbms':
          openDbmsMetadataModal(selectedDatabase)
          break
        case 'ibcmd':
          openIbcmdProfileModal(selectedDatabase)
          break
        case 'metadata':
          openMetadataManagementDrawer(selectedDatabase)
          break
        case 'extensions':
          openExtensionsDrawer(selectedDatabase)
          break
      }
    },
    [
      openCredentialsModal,
      openDbmsMetadataModal,
      openExtensionsDrawer,
      openIbcmdProfileModal,
      openMetadataManagementDrawer,
      selectedDatabase,
    ]
  )

  const handleCloseDatabaseWorkspace = useCallback(() => {
    updateSearchParams({
      database: null,
      context: null,
    })
  }, [updateSearchParams])

  const databasesSubtitle = selectedCluster
    ? `Manage database metadata, DBMS context, credentials, and extensions for ${selectedCluster.name}.`
    : 'Manage database metadata, DBMS context, credentials, and extensions from one operational workspace.'

  const databasesToolbar = (
    <Space direction="vertical" size="middle" style={{ width: '100%', marginBottom: 16 }}>
      {selectedCluster ? (
        <Typography.Text type="secondary">
          Cluster: {selectedCluster.name}
        </Typography.Text>
      ) : null}

      {canOperateAny ? (
        <BulkActionsToolbar
          selectedCount={selectedRowKeys.length}
          onAction={handleBulkAction}
          onClearSelection={handleClearSelection}
          loading={executeRasOperation.isPending || bulkHealthCheck.isPending || setDatabaseStatus.isPending}
          disabled={!canOperateSelected}
        />
      ) : null}

      {canOperateAny && selectedRowKeys.length > 0 ? (
        <Space wrap>
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
      ) : null}
    </Space>
  )

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Databases"
          subtitle={databasesSubtitle}
          actions={(
            <Space wrap size="middle">
              <Select
                style={{ width: 250 }}
                placeholder="All clusters"
                allowClear
                value={clusterIdFromUrl}
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
              <Button type="primary" icon={<PlusOutlined />} disabled={!isStaff}>
                Add Database
              </Button>
            </Space>
          )}
        />
      )}
    >
      <MasterDetailShell
        list={(
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <EntityList
              title="Database Catalog"
              extra={(
                <Input.Search
                  aria-label="Search databases"
                  allowClear
                  placeholder="Search databases"
                  value={table.search}
                  onChange={(event) => table.setSearch(event.target.value)}
                  style={{ width: '100%', maxWidth: 260 }}
                />
              )}
              toolbar={databasesToolbar}
              loading={databasesLoading}
              emptyDescription={selectedCluster ? 'No databases found for the selected cluster.' : 'No databases found.'}
              dataSource={databases}
              renderItem={(database) => {
                const statusTag = getStatusTag(database.status)
                const healthTag = getHealthTag(database.last_check_status)
                const selected = database.id === selectedDatabaseIdFromUrl
                const bulkSelected = selectedRowKeys.includes(database.id)
                const bulkSelectionDisabled = database.status === 'maintenance' || !canOperateDatabase(database.id)

                return (
                  <div
                    key={database.id}
                    style={{ display: 'flex', gap: 12, alignItems: 'flex-start', width: '100%' }}
                  >
                    {canSelectRows ? (
                      <Checkbox
                        aria-label={`Select database ${database.name} for bulk operations`}
                        checked={bulkSelected}
                        disabled={bulkSelectionDisabled}
                        onChange={(event) => handleToggleBulkSelection(database, event.target.checked)}
                        onClick={(event) => event.stopPropagation()}
                        style={{ marginTop: 14 }}
                      />
                    ) : null}
                    <Button
                      type="text"
                      block
                      aria-label={`Open database ${database.name}`}
                      aria-pressed={selected}
                      onClick={() => handleSelectDatabase(database)}
                      disabled={!canViewDatabase(database.id)}
                      style={buildCatalogButtonStyle(selected)}
                    >
                      <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        <Space wrap size={[8, 8]}>
                          <Typography.Text strong>{database.name}</Typography.Text>
                          <Tag color={statusTag.color}>{statusTag.label}</Tag>
                          <Tag color={healthTag.color}>{`Health ${healthTag.label}`}</Tag>
                          <Tag color={database.password_configured ? 'green' : 'default'}>
                            {database.password_configured ? 'Credentials ready' : 'Credentials missing'}
                          </Tag>
                        </Space>
                        <Typography.Text type="secondary">
                          {`${database.host}:${database.port} · ${database.infobase_name || database.base_name || 'n/a'}`}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {`${database.server_address || 'n/a'}:${database.server_port || 'n/a'} · ${database.last_check ? `Last check ${new Date(database.last_check).toLocaleString()}` : 'Never checked'}`}
                        </Typography.Text>
                      </Space>
                    </Button>
                  </div>
                )
              }}
            />
            <Pagination
              size="small"
              current={table.pagination.page}
              pageSize={table.pagination.pageSize}
              total={totalDatabases}
              showSizeChanger
              pageSizeOptions={[20, 50, 100]}
              onChange={(page, pageSize) => {
                if (pageSize !== table.pagination.pageSize) {
                  table.setPageSize(pageSize)
                  return
                }
                table.setPage(page)
              }}
            />
          </Space>
        )}
        detail={selectedDatabase ? (
          <DatabaseWorkspaceDetailPanel
            database={selectedDatabase}
            activeContext={activeContext}
            canView={canViewSelectedDatabase}
            canManage={canManageSelectedDatabase}
            canOperate={canOperateSelectedDatabase}
            mutatingDisabled={mutatingDisabled}
            onOpenContext={handleOpenDetailContext}
          />
        ) : (
          <EntityDetails
            title="Database Workspace"
            loading={selectedDatabaseLoading}
            error={selectedDatabaseIdFromUrl && selectedDatabaseError ? selectedDatabaseError : null}
            empty
            emptyDescription={selectedDatabaseIdFromUrl
              ? 'Selected database could not be resolved in the current workspace.'
              : 'Select a database from the catalog to inspect metadata, credentials, DBMS context, and extensions.'
            }
          />
        )}
        detailOpen={inspectDetailOpen}
        onCloseDetail={handleCloseDatabaseWorkspace}
        detailDrawerTitle={selectedDatabase ? `Database Workspace: ${selectedDatabase.name}` : 'Database Workspace'}
        listMinWidth={420}
        listMaxWidth={560}
      />

      <DatabaseCredentialsModal
        open={credentialsModalVisible}
        database={selectedDatabase}
        form={credentialsForm}
        saving={updateDatabaseCredentials.isPending}
        onCancel={closeCredentialsModal}
        onSave={() => void handleCredentialsSave()}
        onReset={handleCredentialsReset}
      />
      <DatabaseDbmsMetadataModal
        open={dbmsMetadataModalVisible}
        database={selectedDatabase}
        form={dbmsMetadataForm}
        saving={updateDatabaseDbmsMetadata.isPending}
        onCancel={closeDbmsMetadataModal}
        onSave={() => void handleDbmsMetadataSave()}
        onReset={handleDbmsMetadataReset}
      />
      <DatabaseIbcmdConnectionProfileModal
        open={ibcmdProfileModalVisible}
        database={selectedDatabase}
        form={ibcmdProfileForm}
        saving={updateDatabaseIbcmdConnectionProfile.isPending}
        onCancel={closeIbcmdProfileModal}
        onSave={() => void handleIbcmdProfileSave()}
        onReset={handleIbcmdProfileReset}
      />
      <DatabaseMetadataManagementDrawer
        open={metadataManagementDrawerVisible}
        databaseId={selectedDatabase?.id}
        databaseName={selectedDatabase?.name}
        mutatingDisabled={metadataManagementMutatingDisabled}
        eligibilityMutatingDisabled={metadataManagementEligibilityMutatingDisabled}
        onClose={closeMetadataManagementDrawer}
        onOperationQueued={(operationId) => navigate(`/operations?operation=${operationId}`)}
        onOpenIbcmdProfile={() => {
          if (!selectedDatabase) return
          openIbcmdProfileModal(selectedDatabase)
        }}
      />

      <ExtensionsDrawer
        open={extensionsDrawerVisible}
        databaseId={selectedDatabase?.id}
        databaseName={selectedDatabase?.name}
        mutatingDisabled={mutatingDisabled || !canOperateSelectedDatabase}
        onClose={closeExtensionsDrawer}
        onOperationQueued={(operationId) => navigate(`/operations?operation=${operationId}`)}
        snapshot={extensionsSnapshotQuery.data ?? null}
        snapshotLoading={extensionsSnapshotQuery.isLoading}
        snapshotFetching={extensionsSnapshotQuery.isFetching}
        onRefreshSnapshot={() => {
          if (!selectedDatabase) return
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
    </WorkspacePage>
  )
}
