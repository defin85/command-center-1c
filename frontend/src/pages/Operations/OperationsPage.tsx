/**
 * Main Operations page with tabs.
 * Orchestrates OperationsTable, OperationDetailsModal, and NewOperationWizard components.
 *
 * Uses React Query for data fetching with automatic polling.
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import { Button, Space, Alert, Input, Pagination, Tag, Typography } from 'antd'
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { useOperations, useCancelOperation } from '../../api/queries/operations'
import { getV2 } from '../../api/generated'
import { executeOperation, type RASOperationType } from '../../api/operations'
import { apiClient } from '../../api/client'
import { getRuntimeSettings } from '../../api/runtimeSettings'
import { useAuthz } from '../../authz/useAuthz'
import type { TimelineStreamEvent } from '../../hooks/useOperationTimelineStream'
import { useOperationsMuxStream } from '../../hooks/useOperationsMuxStream'
import { buildOperationsColumns } from './components/OperationsTableColumns'
import { OperationInspectPanel } from './components/OperationDetailsModal'
import { NewOperationWizard } from './components/NewOperationWizard'
import OperationTimelineDrawer from '../../components/service-mesh/OperationTimelineDrawer'
import type { NewOperationData } from './components/NewOperationWizard'
import type { UIBatchOperation } from './types'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { EntityDetails, EntityList, MasterDetailShell, PageHeader, WorkspacePage } from '../../components/platform'
import { useLocaleFormatters, useOperationsTranslation } from '../../i18n'
import { getOperationStatusLabel, getOperationTypeLabel, getStatusColor } from './utils'

const api = getV2()

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

const DEFAULT_MAX_LIVE_STREAMS = 10
const DEFAULT_MAX_SUBSCRIPTIONS = 200
const ACTIVE_STATUSES = ['pending', 'queued', 'processing'] as const
const EMPTY_OPERATIONS: UIBatchOperation[] = []
const DEFAULT_OPERATIONS_VIEW = 'inspect' as const
const isActiveStatus = (
  status: UIBatchOperation['status']
): status is (typeof ACTIVE_STATUSES)[number] =>
  (ACTIVE_STATUSES as readonly string[]).includes(status)

const parseOperationsView = (value: string | null): 'inspect' | 'timeline' => (
  value === 'monitor' || value === 'timeline'
    ? 'timeline'
    : DEFAULT_OPERATIONS_VIEW
)

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

const formatShortRef = (value: string | undefined) => (value ? `${value.slice(0, 8)}...` : null)

/**
 * OperationsPage - Main page with tabs for operations list and live monitor
 */
export const OperationsPage = () => {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const { t, ready } = useOperationsTranslation()
  const formatters = useLocaleFormatters()

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedOperationIdFromUrl = searchParams.get('operation') || undefined
  const activeView = parseOperationsView(searchParams.get('tab'))

  // UI State (not data-related)
  const [wizardVisible, setWizardVisible] = useState(false)
  const [operationsState, setOperationsState] = useState<UIBatchOperation[]>([])
  const [liveEvents, setLiveEvents] = useState<Record<string, TimelineStreamEvent>>({})
  const [maxLiveStreams, setMaxLiveStreams] = useState(DEFAULT_MAX_LIVE_STREAMS)
  const [maxSubscriptions, setMaxSubscriptions] = useState(DEFAULT_MAX_SUBSCRIPTIONS)

  const operationIdFilter = (searchParams.get('operation_id') || '').trim() || undefined
  const workflowExecutionId = searchParams.get('workflow_execution_id') || undefined
  const nodeId = searchParams.get('node_id') || undefined
  const rootOperationId = searchParams.get('root_operation_id') || undefined
  const executionConsumer = searchParams.get('execution_consumer') || undefined
  const lane = searchParams.get('lane') || undefined
  const canOperateAny = authz.isStaff || authz.canAnyDatabase('OPERATE')
  const canViewAny = authz.isStaff || authz.canAnyDatabase('VIEW')
  const canCreateOperation = canOperateAny
  const canCancel = canOperateAny
  const canStreamOperations = canViewAny

  // React Query: cancel mutation
  const cancelMutation = useCancelOperation()

  const applyTimelineUpdate = useCallback(
    (current: UIBatchOperation, event: TimelineStreamEvent): UIBatchOperation => {
      if (current.id !== event.operation_id) {
        return current
      }

      const metadata = (event.metadata ?? {}) as Record<string, unknown>
      const totalTasks = toNumber(metadata.total_tasks)
      const completedTasks = toNumber(metadata.completed_tasks)
      const failedTasks = toNumber(metadata.failed_tasks)
      const progressPercent = toNumber(metadata.progress_percent)

      const updated = { ...current }
      if (event.workflow_execution_id) {
        updated.workflow_execution_id = event.workflow_execution_id
      }
      if (event.node_id) {
        updated.node_id = event.node_id
      }
      if (event.root_operation_id) {
        updated.root_operation_id = event.root_operation_id
      }
      if (event.execution_consumer) {
        updated.execution_consumer = event.execution_consumer
      }
      if (event.lane) {
        updated.lane = event.lane
      }
      if (totalTasks !== null) {
        updated.total_tasks = totalTasks
      }
      if (completedTasks !== null) {
        updated.completed_tasks = completedTasks
      }
      if (failedTasks !== null) {
        updated.failed_tasks = failedTasks
      }
      if (progressPercent !== null) {
        updated.progress = Math.min(100, Math.max(0, Math.round(progressPercent)))
      } else if (
        totalTasks !== null &&
        completedTasks !== null &&
        failedTasks !== null &&
        totalTasks > 0
      ) {
        const processed = completedTasks + failedTasks
        updated.progress = Math.round((processed / totalTasks) * 100)
      }

      if (event.event === 'operation.completed' || event.event === 'operation.failed') {
        updated.status = event.event === 'operation.failed' ? 'failed' : 'completed'
        updated.progress = 100
      }

      return updated
    },
    []
  )

  // Handle cancel operation
  const handleCancel = useCallback(
    (id: string) => {
      cancelMutation.mutate(id)
    },
    [cancelMutation]
  )

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams]
  )

  const handleViewDetails = useCallback((operation: UIBatchOperation) => {
    updateSearchParams({ operation: operation.id, tab: 'inspect' })
  }, [updateSearchParams])

  const handleTimelineOpen = useCallback(
    (opId: string) => {
      updateSearchParams({ operation: opId, tab: 'monitor' })
    },
    [updateSearchParams]
  )

  const handleTimelineClose = useCallback(() => {
    if (selectedOperationIdFromUrl) {
      updateSearchParams({ tab: 'inspect' })
      return
    }
    updateSearchParams({ operation: null, tab: null })
  }, [selectedOperationIdFromUrl, updateSearchParams])

  const handleInspectClose = useCallback(() => {
    updateSearchParams({ operation: null, tab: null })
  }, [updateSearchParams])

  const handleFilterWorkflow = useCallback(
    (workflowId: string) => {
      updateSearchParams({ workflow_execution_id: workflowId })
    },
    [updateSearchParams]
  )

  const handleFilterNode = useCallback(
    (nodeIdValue: string) => {
      updateSearchParams({ node_id: nodeIdValue })
    },
    [updateSearchParams]
  )

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: t(($) => $.table.name), sortable: true, groupKey: 'core', groupLabel: t(($) => $.table.name) },
    { key: 'id', label: t(($) => $.table.operationId), groupKey: 'core', groupLabel: t(($) => $.table.name) },
    { key: 'workflow_execution_id', label: t(($) => $.table.workflow), groupKey: 'workflow', groupLabel: t(($) => $.table.workflow) },
    { key: 'operation_type', label: t(($) => $.table.type), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.table.status) },
    { key: 'status', label: t(($) => $.table.status), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.table.status) },
    { key: 'progress', label: t(($) => $.table.progress), groupKey: 'meta', groupLabel: t(($) => $.table.status) },
    { key: 'databases', label: t(($) => $.table.databases), groupKey: 'meta', groupLabel: t(($) => $.table.status) },
    { key: 'created_at', label: t(($) => $.table.created), sortable: true, groupKey: 'time', groupLabel: t(($) => $.table.created) },
    { key: 'duration_seconds', label: t(($) => $.table.duration), sortable: true, groupKey: 'time', groupLabel: t(($) => $.table.created) },
    { key: 'actions', label: t(($) => $.table.actions), groupKey: 'actions', groupLabel: t(($) => $.table.actions) },
  ], [t])

  const formatOperationTaskSummary = useCallback((operation: UIBatchOperation) => {
    if (operation.total_tasks <= 0) {
      return t(($) => $.page.taskSummaryNone)
    }

    if (operation.failed_tasks > 0) {
      return t(($) => $.page.taskSummaryWithFailed, {
        completed: String(operation.completed_tasks),
        total: String(operation.total_tasks),
        failed: String(operation.failed_tasks),
      })
    }

    return t(($) => $.page.taskSummary, {
      completed: String(operation.completed_tasks),
      total: String(operation.total_tasks),
    })
  }, [t])

  const operationsColumns = useMemo(
    () => buildOperationsColumns({
      onViewDetails: handleViewDetails,
      onCancel: handleCancel,
      onFilterWorkflow: handleFilterWorkflow,
      onFilterNode: handleFilterNode,
      canCancel,
      formatDateTime: (value) => formatters.dateTime(value, { fallback: t(($) => $.inspect.noValue) }),
      t,
    }),
    [canCancel, formatters, handleCancel, handleFilterNode, handleFilterWorkflow, handleViewDetails, t]
  )

  const table = useTableToolkit({
    tableId: 'operations',
    columns: operationsColumns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
    disableServerMetadata: true,
  })

  const setFilter = table.setFilter
  useEffect(() => {
    setFilter('id', operationIdFilter ?? null)
    setFilter('workflow_execution_id', workflowExecutionId ?? null)
  }, [operationIdFilter, setFilter, workflowExecutionId])

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const {
    data: operationsResponse,
    isLoading: loading,
    error: queryError,
    refetch,
  } = useOperations({
    refetchInterval: 5000,
    filters: {
      search: table.search,
      filters: table.filtersPayload,
      sort: table.sortPayload,
      operation_id: operationIdFilter,
      workflow_execution_id: workflowExecutionId,
      node_id: nodeId,
      root_operation_id: rootOperationId,
      execution_consumer: executionConsumer,
      lane,
      limit: table.pagination.pageSize,
      offset: pageStart,
    },
  })

  const operations = operationsResponse?.operations ?? EMPTY_OPERATIONS
  const catalogOperations = operationsState.length > 0 ? operationsState : operations
  const totalOperations = typeof operationsResponse?.total === 'number'
    ? operationsResponse.total
    : operations.length
  const selectedOperation = useMemo(
    () => catalogOperations.find((item) => item.id === selectedOperationIdFromUrl)
      ?? operations.find((item) => item.id === selectedOperationIdFromUrl)
      ?? null,
    [catalogOperations, operations, selectedOperationIdFromUrl]
  )
  const inspectVisible = Boolean(selectedOperationIdFromUrl) && activeView === 'inspect'
  const timelineVisible = Boolean(selectedOperationIdFromUrl) && activeView === 'timeline'

  const error = queryError ? t(($) => $.page.failedToLoad) : null

  const handleRefresh = useCallback(() => {
    refetch()
  }, [refetch])

  useEffect(() => {
    if (!isStaff) {
      return
    }
    let isActive = true
    void (async () => {
      try {
        const settings = await getRuntimeSettings()
        const entry = settings.find((item) => item.key === 'ui.operations.max_live_streams')
        const value = toNumber(entry?.value)
        if (isActive && value !== null && value > 0) {
          setMaxLiveStreams(value)
        }
        const muxEntry = settings.find((item) => item.key === 'observability.operations.max_subscriptions')
        const muxValue = toNumber(muxEntry?.value)
        if (isActive && muxValue !== null && muxValue > 0) {
          setMaxSubscriptions(muxValue)
        }
      } catch (_error) {
        // Use default if settings are unavailable.
      }
    })()

    return () => {
      isActive = false
    }
  }, [isStaff])

  useEffect(() => {
    setOperationsState((current) => {
      if (current.length === 0) {
        return operations
      }
      const currentMap = new Map(current.map((item) => [item.id, item]))
      return operations.map((item) => {
        const existing = currentMap.get(item.id)
        if (!existing) {
          return item
        }
        const isExistingActive = isActiveStatus(existing.status)
        const isIncomingActive = isActiveStatus(item.status)
        if (isExistingActive && isIncomingActive) {
          const merged = { ...item }
          merged.total_tasks = item.total_tasks || existing.total_tasks
          merged.completed_tasks = Math.max(item.completed_tasks, existing.completed_tasks)
          merged.failed_tasks = Math.max(item.failed_tasks, existing.failed_tasks)
          merged.progress = Math.max(item.progress, existing.progress)
          return merged
        }
        return item
      })
    })
  }, [operations])

  const activeFilterChips = (
    <>
      {workflowExecutionId ? (
        <Tag closable onClose={() => updateSearchParams({ workflow_execution_id: null })}>
          {t(($) => $.page.activeFilters.workflow, { value: workflowExecutionId })}
        </Tag>
      ) : null}
      {operationIdFilter ? (
        <Tag closable onClose={() => updateSearchParams({ operation_id: null })}>
          {t(($) => $.page.activeFilters.operation, { value: operationIdFilter })}
        </Tag>
      ) : null}
      {nodeId ? (
        <Tag closable onClose={() => updateSearchParams({ node_id: null })}>
          {t(($) => $.page.activeFilters.node, { value: nodeId })}
        </Tag>
      ) : null}
      {rootOperationId ? (
        <Tag closable onClose={() => updateSearchParams({ root_operation_id: null })}>
          {t(($) => $.page.activeFilters.root, { value: rootOperationId })}
        </Tag>
      ) : null}
      {executionConsumer ? (
        <Tag closable onClose={() => updateSearchParams({ execution_consumer: null })}>
          {t(($) => $.page.activeFilters.consumer, { value: executionConsumer })}
        </Tag>
      ) : null}
      {lane ? (
        <Tag closable onClose={() => updateSearchParams({ lane: null })}>
          {t(($) => $.page.activeFilters.lane, { value: lane })}
        </Tag>
      ) : null}
    </>
  )

  const operationsToolbar = (
    <Space direction="vertical" size="middle" style={{ width: '100%', marginBottom: 16 }}>
      {error ? (
        <Alert
          message={error}
          type="error"
          closable
        />
      ) : null}
      {workflowExecutionId || operationIdFilter || nodeId || rootOperationId || executionConsumer || lane ? (
        <Space size={[8, 8]} wrap>
          {activeFilterChips}
        </Space>
      ) : null}
    </Space>
  )

  // Handle new operation wizard submit
  const handleWizardSubmit = useCallback(
    async (data: NewOperationData) => {
      if (data.templateId) {
        await api.postWorkflowsExecuteWorkflow({
          workflow_id: data.templateId,
          input_context: {
            ...data.config,
            database_ids: data.databaseIds,
            uploaded_files: data.uploadedFiles,
          },
          mode: 'async',
        })
        handleRefresh()
        return
      }

      if (!data.operationType) {
        throw new Error('operation_type is required')
      }

      const normalizeSelect = (value: unknown): string[] | undefined => {
        if (Array.isArray(value)) {
          const list = value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
          return list.length > 0 ? list : undefined
        }
        if (typeof value === 'string') {
          const list = value
            .split(',')
            .map((item) => item.trim())
            .filter((item) => item.length > 0)
          return list.length > 0 ? list : undefined
        }
        return undefined
      }

      const rasOperations: Set<NewOperationData['operationType']> = new Set([
        'lock_scheduled_jobs',
        'unlock_scheduled_jobs',
        'block_sessions',
        'unblock_sessions',
        'terminate_sessions',
      ])

      if (rasOperations.has(data.operationType)) {
        await executeOperation({
          operation_type: data.operationType as RASOperationType,
          database_ids: data.databaseIds,
          config: data.config,
        })
        handleRefresh()
        return
      }

      if (data.operationType === 'designer_cli') {
        const dc = data.config.driver_command
        if (dc && dc.driver === 'cli') {
          const command = typeof dc.command_id === 'string' ? dc.command_id.trim() : ''
          if (!command) {
            throw new Error('command is required')
          }

          const args = Array.isArray(dc.resolved_args)
            ? dc.resolved_args.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
            : []

          const opt = dc.cli_options ?? {}
          await apiClient.post('/api/v2/operations/execute/', {
            operation_type: 'designer_cli',
            database_ids: data.databaseIds,
            config: {
              command,
              args: args.length > 0 ? args : undefined,
              options: {
                disable_startup_messages: opt.disable_startup_messages !== false,
                disable_startup_dialogs: opt.disable_startup_dialogs !== false,
                log_capture: opt.log_capture === true,
                log_path: typeof opt.log_path === 'string' && opt.log_path.trim().length > 0
                  ? opt.log_path.trim()
                  : undefined,
                log_no_truncate: opt.log_no_truncate === true,
              },
            },
          })
          handleRefresh()
          return
        }

        // Fallback to legacy payload fields (backward-compatible)
        const command = typeof data.config.command === 'string' ? data.config.command.trim() : ''
        if (!command) {
          throw new Error('command is required')
        }
        const normalizeArgs = (value: unknown): string[] | undefined => {
          if (Array.isArray(value)) {
            const list = value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
            return list.length > 0 ? list : undefined
          }
          if (typeof value === 'string') {
            const list = value
              .split('\n')
              .map((item) => item.trim())
              .filter((item) => item.length > 0)
            return list.length > 0 ? list : undefined
          }
          return undefined
        }
        await apiClient.post('/api/v2/operations/execute/', {
          operation_type: 'designer_cli',
          database_ids: data.databaseIds,
          config: {
            command,
            args: normalizeArgs(data.config.args),
            options: {
              disable_startup_messages: data.config.disable_startup_messages !== false,
              disable_startup_dialogs: data.config.disable_startup_dialogs !== false,
              log_capture: data.config.log_capture === true,
              log_path: typeof data.config.log_path === 'string' && data.config.log_path.trim().length > 0
                ? data.config.log_path.trim()
                : undefined,
              log_no_truncate: data.config.log_no_truncate === true,
            },
          },
        })
        handleRefresh()
        return
      }

      if (data.operationType === 'ibcmd_cli') {
        const dc = data.config.driver_command
        if (!dc || dc.driver !== 'ibcmd') {
          throw new Error('driver_command is required')
        }

        const commandId = typeof dc.command_id === 'string' ? dc.command_id.trim() : ''
        if (!commandId) {
          throw new Error('command_id is required')
        }

        const parseLines = (value: unknown): string[] => {
          if (typeof value !== 'string') return []
          return value
            .split('\n')
            .map((item) => item.trim())
            .filter((item) => item.length > 0)
        }

        const additionalArgs = parseLines(dc.args_text)
        const scope = dc.command_scope === 'global' ? 'global' : 'per_database'
        const authDatabaseId = typeof dc.auth_database_id === 'string' ? dc.auth_database_id : undefined

        const timeoutSeconds = typeof dc.timeout_seconds === 'number' ? dc.timeout_seconds : 900
        const boundedTimeout = Math.min(Math.max(timeoutSeconds, 1), 3600)

        const payload: Record<string, unknown> = {
          command_id: commandId,
          mode: dc.mode || 'guided',
          database_ids: scope === 'global' ? [] : data.databaseIds,
          auth_database_id: scope === 'global' ? authDatabaseId : undefined,
          ib_auth: dc.ib_auth,
          params: dc.params ?? {},
          additional_args: additionalArgs,
          stdin: typeof dc.stdin === 'string' ? dc.stdin : '',
          confirm_dangerous: dc.confirm_dangerous === true,
          timeout_seconds: boundedTimeout,
        }

        if (scope === 'global' || dc.connection_override === true) {
          payload.connection = dc.connection ?? {}
        }

        await apiClient.post('/api/v2/operations/execute-ibcmd-cli/', payload)

        handleRefresh()
        return
      }

      if (data.operationType === 'query') {
        const select = normalizeSelect(data.config.select)
        await apiClient.post('/api/v2/operations/execute/', {
          operation_type: 'query',
          database_ids: data.databaseIds,
          config: {
            entity: data.config.entity,
            filter: data.config.filter,
            select,
            top: data.config.top,
          },
        })
        handleRefresh()
        return
      }

      if (data.operationType === 'health_check') {
        await api.postDatabasesBulkHealthCheck({
          database_ids: data.databaseIds,
        })
        handleRefresh()
        return
      }

      throw new Error(`Operation type ${data.operationType} is not supported in wizard`)
    },
    [handleRefresh]
  )

  const activeOperationIds = canStreamOperations
    ? operationsState
      .filter((operation) => isActiveStatus(operation.status))
      .slice(0, Math.min(maxLiveStreams, maxSubscriptions))
      .map((operation) => operation.id)
    : []

  const { lastEvent: muxEvent } = useOperationsMuxStream(activeOperationIds)

  useEffect(() => {
    if (!muxEvent) return
    setOperationsState((current) =>
      current.map((operation) => applyTimelineUpdate(operation, muxEvent))
    )
    setLiveEvents((current) => ({
      ...current,
      [muxEvent.operation_id]: muxEvent,
    }))
  }, [muxEvent, applyTimelineUpdate])

  if (!ready) {
    return null
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.page.title)}
          subtitle={t(($) => $.page.subtitle)}
          actions={(
            <Space wrap>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading}
              >
                {t(($) => $.page.refresh)}
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setWizardVisible(true)}
                disabled={!canCreateOperation}
              >
                {t(($) => $.page.newOperation)}
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
              title={t(($) => $.page.catalogTitle)}
              extra={(
                <Input.Search
                  aria-label={t(($) => $.page.searchAriaLabel)}
                  allowClear
                  placeholder={t(($) => $.page.searchPlaceholder)}
                  value={table.search}
                  onChange={(event) => table.setSearch(event.target.value)}
                  style={{ width: '100%', maxWidth: 260 }}
                />
              )}
              toolbar={operationsToolbar}
              loading={loading}
              emptyDescription={t(($) => $.page.emptyDescription)}
              dataSource={catalogOperations}
              renderItem={(operation) => {
                const selected = operation.id === selectedOperationIdFromUrl
                return (
                  <Button
                    key={operation.id}
                    type="text"
                    block
                    aria-label={t(($) => $.page.openOperation, { name: operation.name })}
                    aria-pressed={selected}
                    onClick={() => handleViewDetails(operation)}
                    style={buildCatalogButtonStyle(selected)}
                  >
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Space wrap size={[8, 8]}>
                        <Typography.Text strong>{operation.name}</Typography.Text>
                        <Tag color={getStatusColor(operation.status)}>{getOperationStatusLabel(operation.status, t)}</Tag>
                        {operation.workflow_execution_id ? (
                          <Typography.Text code>
                            {t(($) => $.page.workflowShort, { value: formatShortRef(operation.workflow_execution_id) ?? operation.workflow_execution_id })}
                          </Typography.Text>
                        ) : null}
                      </Space>
                      <Typography.Text type="secondary">
                        {t(($) => $.page.typeAndTarget, {
                          type: getOperationTypeLabel(operation.operation_type, t),
                          target: operation.target_entity || t(($) => $.page.noTargetEntity),
                        })}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        {`${formatOperationTaskSummary(operation)} · ${t(($) => $.page.databaseCount, { value: String(operation.database_names.length) })}`}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        {t(($) => $.page.createdAt, {
                          value: formatters.dateTime(operation.created_at, { fallback: t(($) => $.inspect.noValue) }),
                        })}
                      </Typography.Text>
                    </Space>
                  </Button>
                )
              }}
            />
            <Pagination
              size="small"
              align="end"
              current={table.pagination.page}
              pageSize={table.pagination.pageSize}
              total={totalOperations}
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
        detail={inspectVisible ? (
          <OperationInspectPanel
            operationId={selectedOperationIdFromUrl ?? null}
            operationSnapshot={selectedOperation}
            onTimeline={handleTimelineOpen}
            liveEvent={selectedOperationIdFromUrl ? liveEvents[selectedOperationIdFromUrl] ?? null : null}
            onFilterWorkflow={handleFilterWorkflow}
            onFilterNode={handleFilterNode}
            canCancel={canCancel}
            onCancel={handleCancel}
          />
        ) : (
          <EntityDetails title={t(($) => $.inspect.title)}>
            <Typography.Text type="secondary">
              {t(($) => $.page.inspectEmptyDescription)}
            </Typography.Text>
          </EntityDetails>
        )}
        detailOpen={inspectVisible}
        onCloseDetail={handleInspectClose}
        detailDrawerTitle={selectedOperation?.name ?? t(($) => $.page.detailDrawerTitle)}
        listMinWidth={420}
        listMaxWidth={560}
      />

      <OperationTimelineDrawer
        visible={timelineVisible}
        operationId={selectedOperationIdFromUrl ?? null}
        onClose={handleTimelineClose}
      />

      <NewOperationWizard
        visible={wizardVisible}
        onClose={() => setWizardVisible(false)}
        onSubmit={handleWizardSubmit}
      />
    </WorkspacePage>
  )
}
