import { useState, useCallback, useMemo, useEffect } from 'react'
import { App, Table, Button, Space, Tag, Select, Breadcrumb, Modal, Form, Typography, Dropdown, Tooltip, Input } from 'antd'
import type { TableRowSelection } from 'antd/es/table/interface'
import { PlusOutlined, HomeOutlined, ClusterOutlined, RocketOutlined, HeartOutlined, EditOutlined, DownOutlined, KeyOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { getV2 } from '../../api/generated'
import type { Database } from '../../api/generated/model/database'
import { SetDatabaseStatusRequestStatus } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import { extractInstallationFromStatus } from '../../utils/installationTransforms'
import { ExtensionFileSelector } from '../../components/Installation/ExtensionFileSelector'
import { InstallationProgressModal } from '../../components/Installation/InstallationProgressModal'
import type { ExtensionInstallation } from '../../types/installation'
import { DatabaseActionsMenu, BulkActionsToolbar, OperationConfirmModal } from '../../components/actions'
import type { DatabaseActionKey } from '../../components/actions'
import type { RASOperationType } from '../../api/operations'
import { queryKeys, useTableMetadata } from '../../api/queries'
import { useDatabases, useExecuteRasOperation, useInstallExtension, useHealthCheckDatabase, useBulkHealthCheckDatabases, useSetDatabaseStatus, useUpdateDatabaseCredentials } from '../../api/queries/databases'
import { useClusters } from '../../api/queries/clusters'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { getHealthTag, getStatusTag } from '../../utils/databaseStatus'
import { TableToolbar } from '../../components/table/TableToolbar'
import { TablePagination } from '../../components/table/TablePagination'
import { TableFiltersRow } from '../../components/table/TableFiltersRow'
import { useTableState } from '../../components/table/hooks/useTableState'
import type { TableFilterConfig, TableFilterValue, TableFilters } from '../../components/table/types'
import { TablePreferencesModal } from '../../components/table/TablePreferencesModal'
import { useTablePreferences } from '../../components/table/hooks/useTablePreferences'

// Get generated API functions (for fetchStatus in InstallationProgressModal)
const api = getV2()

export const Databases = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message, modal } = App.useApp()
  const [searchParams] = useSearchParams()
  const clusterIdFromUrl = searchParams.get('cluster')

  // UI State
  const [selectedClusterId, setSelectedClusterId] = useState<string | undefined>(
    clusterIdFromUrl || undefined
  )
  const [modalVisible, setModalVisible] = useState(false)
  const [progressModalVisible, setProgressModalVisible] = useState(false)
  const [selectedDatabase, setSelectedDatabase] = useState<Database | null>(null)
  const [credentialsModalVisible, setCredentialsModalVisible] = useState(false)
  const [credentialsDatabase, setCredentialsDatabase] = useState<Database | null>(null)
  const [form] = Form.useForm()
  const [credentialsForm] = Form.useForm()

  // Row selection state
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedDatabases, setSelectedDatabases] = useState<Database[]>([])
  const [healthCheckPendingIds, setHealthCheckPendingIds] = useState<Set<string>>(new Set())
  const [preferencesOpen, setPreferencesOpen] = useState(false)

  const { data: tableMetadata } = useTableMetadata('databases')

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

  const columnConfigs = useMemo(() => {
    const metadataColumns = tableMetadata?.columns ?? []
    if (metadataColumns.length === 0) {
      return fallbackColumnConfigs
    }
    return metadataColumns.map((col) => ({
      key: col.key,
      label: col.label,
      sortable: col.sortable ?? false,
      groupKey: col.group_key ?? undefined,
      groupLabel: col.group_label ?? undefined,
    }))
  }, [fallbackColumnConfigs, tableMetadata?.columns])

  const filterConfigs = useMemo<TableFilterConfig[]>(() => {
    const metadataColumns = tableMetadata?.columns ?? []
    if (metadataColumns.length === 0) {
      return columnConfigs
        .filter((col) => col.key !== 'actions')
        .map((col) => ({
          key: col.key,
          label: col.label,
          type: 'text',
          placeholder: col.label,
        }))
    }
    return metadataColumns
      .filter((col) => col.filter && col.key !== 'actions')
      .map((col) => ({
        key: col.key,
        label: col.label,
        type: col.filter?.type === 'select' || col.filter?.type === 'boolean'
          ? col.filter.type
          : 'text',
        options: col.filter?.options,
        placeholder: col.filter?.placeholder ?? col.label,
      }))
  }, [columnConfigs, tableMetadata?.columns])

  const filterConfigByKey = useMemo(() => {
    return new Map(filterConfigs.map((config) => [config.key, config]))
  }, [filterConfigs])

  const filterOperatorsByKey = useMemo<Record<string, string>>(() => {
    const metadataColumns = tableMetadata?.columns ?? []
    if (metadataColumns.length === 0) {
      return {}
    }
    const map: Record<string, string> = {}
    metadataColumns.forEach((col) => {
      if (!col.filter) return
      if (col.filter.operators?.includes('contains')) {
        map[col.key] = 'contains'
        return
      }
      map[col.key] = col.filter.operators?.[0] || 'eq'
    })
    return map
  }, [tableMetadata?.columns])

  const defaultFilterState = useMemo<TableFilters>(() => {
    const state: Record<string, TableFilterValue> = {}
    filterConfigs.forEach((config) => {
      state[config.key] = null
    })
    return state
  }, [filterConfigs])

  const hasFilterValue = useCallback((value: TableFilterValue) => {
    if (value === null || value === undefined) return false
    if (typeof value === 'string') return value.trim().length > 0
    if (Array.isArray(value)) return value.length > 0
    return true
  }, [])

  const { search, setSearch, filters, setFilter, setFilters, sort, setSort, pagination, setPage, setPageSize } =
    useTableState<TableFilters>({
      initialFilters: defaultFilterState,
      initialPageSize: 50,
    })

  const {
    preferences,
    activePreset,
    setActivePreset,
    updatePreset,
    createPreset,
    deletePreset,
  } = useTablePreferences('databases', columnConfigs, filterConfigs)

  const visibleColumns = useMemo(() => {
    return new Set(activePreset.visibleColumns)
  }, [activePreset.visibleColumns])

  const sortableColumns = useMemo(() => {
    return new Set(activePreset.sortableColumns)
  }, [activePreset.sortableColumns])

  const orderedFilters = useMemo(() => {
    const configs = filterConfigs.filter((filter) => activePreset.filterVisibility[filter.key] !== false)
    const order = activePreset.filterOrder
    return configs.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
  }, [activePreset.filterOrder, activePreset.filterVisibility, filterConfigs])

  useEffect(() => {
    const defaults = activePreset.defaultFilters || {}
    const nextFilters: TableFilters = { ...defaultFilterState }
    Object.entries(defaults).forEach(([key, value]) => {
      if (key in nextFilters) {
        nextFilters[key] = value
      }
    })
    setFilters(nextFilters)
    if (activePreset.defaultSort?.key && activePreset.defaultSort.order) {
      setSort(activePreset.defaultSort.key, activePreset.defaultSort.order)
    } else {
      setSort(null, null)
    }
    setPage(1)
  }, [activePreset.defaultFilters, activePreset.defaultSort, defaultFilterState, setFilters, setPage, setSort])

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
  const filtersPayload = useMemo(() => {
    const payload: Record<string, { op: string; value: TableFilterValue }> = {}
    filterConfigs.forEach((config) => {
      const value = filters[config.key]
      if (value === null || value === undefined || value === '') {
        return
      }
      const operator = filterOperatorsByKey[config.key]
        || (config.type === 'text' ? 'contains' : 'eq')
      payload[config.key] = {
        op: operator,
        value,
      }
    })
    return Object.keys(payload).length > 0 ? payload : undefined
  }, [filterConfigs, filterOperatorsByKey, filters])

  const sortPayload = useMemo(() => {
    if (!sort.key || !sort.order) return undefined
    return { key: sort.key, order: sort.order }
  }, [sort.key, sort.order])

  const handleToggleFilterVisibility = useCallback((key: string, visible: boolean) => {
    if (!visible && hasFilterValue(filters[key])) {
      return
    }
    updatePreset({
      ...activePreset,
      filterVisibility: {
        ...activePreset.filterVisibility,
        [key]: visible,
      },
    })
  }, [activePreset, filters, hasFilterValue, updatePreset])

  const renderFilterTitle = useCallback((key: string, label: string) => {
    if (!filterConfigByKey.has(key)) {
      return label
    }
    const isVisible = activePreset.filterVisibility[key] !== false
    const disableHide = isVisible && hasFilterValue(filters[key])
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span>{label}</span>
        <Button
          type="text"
          size="small"
          icon={isVisible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
          disabled={disableHide}
          onClick={(event) => {
            event.stopPropagation()
            handleToggleFilterVisibility(key, !isVisible)
          }}
        />
      </span>
    )
  }, [activePreset.filterVisibility, filterConfigByKey, filters, handleToggleFilterVisibility, hasFilterValue])

  const pageStart = (pagination.page - 1) * pagination.pageSize

  const { data: databasesResponse, isLoading: databasesLoading } = useDatabases({
    filters: {
      cluster_id: selectedClusterId,
      search,
      filters: filtersPayload,
      sort: sortPayload,
      limit: pagination.pageSize,
      offset: pageStart,
    },
    refetchInterval: fallbackPollIntervalMs,
  })
  const databases = databasesResponse?.databases ?? []
  const totalDatabases = typeof databasesResponse?.total === 'number'
    ? databasesResponse.total
    : databases.length

  // Mutations
  const executeRasOperation = useExecuteRasOperation()
  const installExtension = useInstallExtension()
  const healthCheck = useHealthCheckDatabase()
  const bulkHealthCheck = useBulkHealthCheckDatabases()
  const setDatabaseStatus = useSetDatabaseStatus()
  const updateDatabaseCredentials = useUpdateDatabaseCredentials()

  // Derived state: selected cluster object
  const selectedCluster = useMemo(() => {
    if (!selectedClusterId || !clusters.length) return null
    return clusters.find((c) => c.id === selectedClusterId) || null
  }, [selectedClusterId, clusters])

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

  const handleInstallExtension = (database: Database) => {
    setSelectedDatabase(database)
    setModalVisible(true)
  }

  const openCredentialsModal = (database: Database) => {
    setCredentialsDatabase(database)
    credentialsForm.setFieldsValue({
      username: database.username ?? '',
      password: '',
    })
    setCredentialsModalVisible(true)
  }

  const handleCredentialsSave = async () => {
    if (!credentialsDatabase) return

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

  const handleConfirmInstall = async () => {
    if (!selectedDatabase) return

    try {
      const values = await form.validateFields()

      if (!values.extension || !values.extension.name || !values.extension.path) {
        message.error('Vyberite fayl rasshireniya')
        return
      }

      installExtension.mutate(
        {
          databaseId: selectedDatabase.id,
          extensionName: values.extension.name,
          extensionPath: values.extension.path,
        },
        {
          onSuccess: (response) => {
            // Close file selection modal
            setModalVisible(false)
            form.resetFields()

            // Open progress modal
            setProgressModalVisible(true)

            // Show message
            message.success({
              content: (
                <div>
                  <div>{response.message}</div>
                </div>
              ),
              duration: 5,
            })
          },
        }
      )
    } catch (error) {
      console.error('Failed to validate form:', error)
    }
  }

  const handleProgressModalClose = () => {
    setProgressModalVisible(false)
    setSelectedDatabase(null)
    // Invalidate databases query to refresh data
    queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
  }

  // Row selection configuration
  const rowSelection: TableRowSelection<Database> = {
    selectedRowKeys,
    onChange: (keys, rows) => {
      setSelectedRowKeys(keys)
      setSelectedDatabases(rows)
    },
    getCheckboxProps: (record) => ({
      disabled: record.status === 'maintenance',
    }),
  }

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
    message.success(res.message)
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
  }, [navigate])

  // Handler for bulk action
  const handleBulkAction = useCallback((action: string) => {
    setConfirmModal({
      visible: true,
      operation: action,
      databases: selectedDatabases.map((db) => ({ id: db.id, name: db.name })),
    })
  }, [selectedDatabases])

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
  }, [confirmModal, executeRasOperation, navigate])

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
      title: renderFilterTitle('name', 'Name'),
      dataIndex: 'name',
      key: 'name',
      width: 200,
      sorter: sortableColumns.has('name'),
      render: (name: string) => {
        return <span>{name}</span>
      },
    },
    {
      title: renderFilterTitle('host', 'Host'),
      dataIndex: 'host',
      key: 'host',
      width: 160,
      sorter: sortableColumns.has('host'),
    },
    {
      title: renderFilterTitle('port', 'Port'),
      dataIndex: 'port',
      key: 'port',
      width: 90,
      sorter: sortableColumns.has('port'),
    },
    {
      title: renderFilterTitle('status', 'Status'),
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => {
        const tag = getStatusTag(status)
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
    {
      title: renderFilterTitle('last_check_status', 'Health'),
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
      title: renderFilterTitle('credentials', 'Credentials'),
      key: 'credentials',
      width: 130,
      render: (_: unknown, record: Database) => (
        <Tag color={record.password_configured ? 'green' : 'default'}>
          {record.password_configured ? 'Configured' : 'Missing'}
        </Tag>
      ),
    },
    {
      title: renderFilterTitle('restrictions', 'Restrictions'),
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
      title: renderFilterTitle('last_check', 'Last Check'),
      dataIndex: 'last_check',
      key: 'last_check',
      width: 170,
      sorter: sortableColumns.has('last_check'),
      render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
    },
    {
      title: renderFilterTitle('actions', 'Actions'),
      key: 'actions',
      width: 260,
      render: (_: unknown, record: Database) => (
        <Space size="small">
          <Button
            size="small"
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => handleInstallExtension(record)}
            disabled={record.status !== 'active'}
          >
            Install
          </Button>
          <Button
            size="small"
            icon={<HeartOutlined />}
            onClick={async () => {
              if (healthCheckPendingIds.has(record.id)) {
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
          >
            Check
          </Button>
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                { key: SetDatabaseStatusRequestStatus.active, label: 'Set Active' },
                { key: SetDatabaseStatusRequestStatus.inactive, label: 'Set Inactive' },
                { key: SetDatabaseStatusRequestStatus.maintenance, label: 'Set Maintenance' },
              ],
              onClick: async ({ key }) => {
                try {
                  await runSetStatus([record.id], key as SetDatabaseStatusValue)
                } catch (e: unknown) {
                  const status = getErrorStatus(e)
                  if (status === 403) {
                    message.error('Set status requires staff access')
                    return
                  }
                  message.error(`Set status failed: ${getErrorMessage(e)}`)
                }
              },
            }}
          >
            <Button size="small" icon={<EditOutlined />}>
              Status <DownOutlined />
            </Button>
          </Dropdown>
          <Button
            size="small"
            icon={<KeyOutlined />}
            onClick={() => openCredentialsModal(record)}
            title="Credentials"
          />
          <DatabaseActionsMenu
            databaseId={record.id}
            databaseStatus={record.status}
            onAction={(action) => handleSingleAction(action, record)}
            disabled={record.status !== 'active'}
          />
        </Space>
      ),
    },
  ]

  const columnsByKey = useMemo(() => {
    const map = new Map<string, (typeof columns)[number]>()
    columns.forEach((col) => {
      map.set(col.key, col)
    })
    return map
  }, [columns])

  const groupedTableColumns = useMemo(() => {
    const groups: Array<{ key: string; title: string; children: (typeof columns)[number][] }> = []
    const seen = new Map<string, number>()

    activePreset.columnOrder.forEach((key) => {
      if (!visibleColumns.has(key)) return
      const column = columnsByKey.get(key)
      if (!column) return
      const config = columnConfigs.find((item) => item.key === key)
      const groupKey = config?.groupKey || 'general'
      const groupLabel = config?.groupLabel || config?.groupKey || 'General'
      if (!seen.has(groupKey)) {
        seen.set(groupKey, groups.length)
        groups.push({ key: groupKey, title: groupLabel, children: [column] })
        return
      }
      const index = seen.get(groupKey) as number
      groups[index].children.push(column)
    })

    return groups.map((group) => ({
      title: group.title,
      key: group.key,
      children: group.children,
    }))
  }, [activePreset.columnOrder, columnConfigs, columnsByKey, visibleColumns])

  const filterColumns = useMemo(() => {
    return activePreset.columnOrder
      .filter((key) => visibleColumns.has(key))
      .map((key) => ({ key, width: columnsByKey.get(key)?.width }))
  }, [activePreset.columnOrder, columnsByKey, visibleColumns])

  const totalColumnsWidth = useMemo(() => {
    return filterColumns.reduce((sum, col) => sum + (col.width ?? 160), 0)
  }, [filterColumns])

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
        <Button type="primary" icon={<PlusOutlined />}>
          Add Database
        </Button>
      </Space>

      <BulkActionsToolbar
        selectedCount={selectedRowKeys.length}
        onAction={handleBulkAction}
        onClearSelection={handleClearSelection}
        loading={executeRasOperation.isPending || bulkHealthCheck.isPending || setDatabaseStatus.isPending}
      />

      {selectedRowKeys.length > 0 && (
        <Space style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary">Ops:</Typography.Text>
          <Button
            icon={<HeartOutlined />}
            onClick={async () => {
              try {
                await runBulkHealthCheck(selectedDatabases.map((d) => d.id))
              } catch (e: unknown) {
                message.error(`Bulk health check failed: ${getErrorMessage(e)}`)
              }
            }}
            loading={bulkHealthCheck.isPending}
          >
            Health check
          </Button>
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                { key: SetDatabaseStatusRequestStatus.active, label: 'Set Active' },
                { key: SetDatabaseStatusRequestStatus.inactive, label: 'Set Inactive' },
                { key: SetDatabaseStatusRequestStatus.maintenance, label: 'Set Maintenance' },
              ],
              onClick: async ({ key }) => {
                try {
                  await runSetStatus(selectedDatabases.map((d) => d.id), key as SetDatabaseStatusValue)
                } catch (e: unknown) {
                  const status = getErrorStatus(e)
                  if (status === 403) {
                    message.error('Set status requires staff access')
                    return
                  }
                  message.error(`Set status failed: ${getErrorMessage(e)}`)
                }
              },
            }}
          >
            <Button icon={<EditOutlined />} loading={setDatabaseStatus.isPending}>
              Set status <DownOutlined />
            </Button>
          </Dropdown>
        </Space>
      )}

      <TableToolbar
        searchValue={search}
        searchPlaceholder="Search databases"
        onSearchChange={setSearch}
        onReset={() => {
          setSearch('')
          const defaults = activePreset.defaultFilters || {}
          const nextFilters: TableFilters = { ...defaultFilterState }
          Object.entries(defaults).forEach(([key, value]) => {
            if (key in nextFilters) {
              nextFilters[key] = value
            }
          })
          setFilters(nextFilters)
        }}
        actions={
          <Button onClick={() => setPreferencesOpen(true)}>Table settings</Button>
        }
      />

      <TableFiltersRow
        columns={filterColumns}
        configs={orderedFilters}
        values={filters}
        visibility={activePreset.filterVisibility}
        onChange={setFilter}
      />

      <Table
        rowSelection={rowSelection}
        columns={groupedTableColumns}
        dataSource={databases}
        loading={databasesLoading}
        rowKey="id"
        pagination={false}
        tableLayout="fixed"
        scroll={{ x: totalColumnsWidth }}
        onChange={(_, __, sorter) => {
          if (Array.isArray(sorter)) {
            setSort(null, null)
            return
          }
          const key = sorter?.field ? String(sorter.field) : null
          if (key && !sortableColumns.has(key)) {
            setSort(null, null)
            return
          }
          const order = sorter?.order === 'ascend'
            ? 'asc'
            : sorter?.order === 'descend'
              ? 'desc'
              : null
          setSort(key, order)
        }}
      />

      <TablePagination
        total={totalDatabases}
        page={pagination.page}
        pageSize={pagination.pageSize}
        onChange={(page, pageSize) => {
          if (pageSize !== pagination.pageSize) {
            setPageSize(pageSize)
            return
          }
          setPage(page)
        }}
      />

      <TablePreferencesModal
        open={preferencesOpen}
        onClose={() => setPreferencesOpen(false)}
        columns={columnConfigs}
        filters={filterConfigs}
        presets={preferences.presets}
        activePresetId={preferences.activePresetId}
        onSelectPreset={setActivePreset}
        onUpdatePreset={updatePreset}
        onCreatePreset={createPreset}
        onDeletePreset={deletePreset}
      />

      <Modal
        title={`Install Extension on ${selectedDatabase?.name}`}
        open={modalVisible}
        onOk={handleConfirmInstall}
        onCancel={() => setModalVisible(false)}
        okText="Install"
        width={700}
        confirmLoading={installExtension.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="extension"
            rules={[{ required: true, message: 'Выберите файл расширения' }]}
          >
            <ExtensionFileSelector />
          </Form.Item>
        </Form>
      </Modal>

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
          <Form.Item label="OData Username" name="username">
            <Input placeholder="Optional OData username" />
          </Form.Item>
          <Form.Item label="OData Password" name="password">
            <Input.Password
              placeholder={credentialsDatabase?.password_configured ? 'Configured' : 'Enter password'}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Progress Modal с Operation ID внутри */}
      {selectedDatabase && (
        <InstallationProgressModal
          visible={progressModalVisible}
          databaseId={selectedDatabase.id}
          databaseName={selectedDatabase.name}
          onClose={handleProgressModalClose}
          fetchStatus={async (databaseId: string): Promise<ExtensionInstallation | null> => {
            try {
              const response = await api.getExtensionsGetInstallStatus({ database_id: databaseId })
              return extractInstallationFromStatus(response)
            } catch (error: unknown) {
              // If installation not found, return null
              if (
                error &&
                typeof error === 'object' &&
                'response' in error &&
                (error as { response?: { status?: number } }).response?.status === 404
              ) {
                return null
              }
              throw error
            }
          }}
        />
      )}

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
