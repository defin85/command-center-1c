/**
 * Main Operations page with tabs.
 * Orchestrates OperationsTable, OperationDetailsModal, and NewOperationWizard components.
 *
 * Uses React Query for data fetching with automatic polling.
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import { Button, Space, Alert, Tag } from 'antd'
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { useOperations, useCancelOperation } from '../../api/queries/operations'
import { getV2 } from '../../api/generated'
import { executeOperation, type RASOperationType } from '../../api/operations'
import { apiClient } from '../../api/client'
import { getRuntimeSettings } from '../../api/runtimeSettings'
import { useAuthz } from '../../authz'
import type { TimelineStreamEvent } from '../../hooks/useOperationTimelineStream'
import { useOperationsMuxStream } from '../../hooks/useOperationsMuxStream'
import { OperationsTable, buildOperationsColumns } from './components/OperationsTable'
import { OperationDetailsModal } from './components/OperationDetailsModal'
import { NewOperationWizard } from './components/NewOperationWizard'
import OperationTimelineDrawer from '../../components/service-mesh/OperationTimelineDrawer'
import type { NewOperationData } from './components/NewOperationWizard'
import type { UIBatchOperation } from './types'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

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
const isActiveStatus = (
  status: UIBatchOperation['status']
): status is (typeof ACTIVE_STATUSES)[number] =>
  (ACTIVE_STATUSES as readonly string[]).includes(status)

/**
 * OperationsPage - Main page with tabs for operations list and live monitor
 */
export const OperationsPage = () => {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const [searchParams, setSearchParams] = useSearchParams()

  // UI State (not data-related)
  const [selectedOperation, setSelectedOperation] = useState<UIBatchOperation | null>(null)
  const [detailsVisible, setDetailsVisible] = useState(false)
  const [wizardVisible, setWizardVisible] = useState(false)
  const [timelineVisible, setTimelineVisible] = useState(false)
  const [timelineOperationId, setTimelineOperationId] = useState<string | undefined>()
  const [operationsState, setOperationsState] = useState<UIBatchOperation[]>([])
  const [liveEvents, setLiveEvents] = useState<Record<string, TimelineStreamEvent>>({})
  const [maxLiveStreams, setMaxLiveStreams] = useState(DEFAULT_MAX_LIVE_STREAMS)
  const [maxSubscriptions, setMaxSubscriptions] = useState(DEFAULT_MAX_SUBSCRIPTIONS)

  const operationIdFromUrl = searchParams.get('operation') || undefined
  const operationIdFilter = (searchParams.get('operation_id') || '').trim() || undefined
  const workflowExecutionId = searchParams.get('workflow_execution_id') || undefined
  const nodeId = searchParams.get('node_id') || undefined
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

  // Show operation details modal
  const handleViewDetails = (operation: UIBatchOperation) => {
    setSelectedOperation(operation)
    setDetailsVisible(true)
  }

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

  const handleTimelineOpen = useCallback(
    (opId: string) => {
      setDetailsVisible(false)
      setTimelineOperationId(opId)
      setTimelineVisible(true)
      updateSearchParams({ operation: opId })
    },
    [updateSearchParams]
  )

  const handleTimelineClose = useCallback(() => {
    setTimelineVisible(false)
    setTimelineOperationId(undefined)
    updateSearchParams({ operation: null })
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
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'id', label: 'Operation ID', groupKey: 'core', groupLabel: 'Core' },
    { key: 'workflow_execution_id', label: 'Workflow', groupKey: 'workflow', groupLabel: 'Workflow' },
    { key: 'operation_type', label: 'Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'progress', label: 'Progress', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'databases', label: 'Databases', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'created_at', label: 'Created', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'duration_seconds', label: 'Duration', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const operationsColumns = useMemo(
    () => buildOperationsColumns({
      onViewDetails: handleViewDetails,
      onCancel: handleCancel,
      onFilterWorkflow: handleFilterWorkflow,
      onFilterNode: handleFilterNode,
      canCancel,
    }),
    [canCancel, handleCancel, handleFilterNode, handleFilterWorkflow, handleViewDetails]
  )

  const table = useTableToolkit({
    tableId: 'operations',
    columns: operationsColumns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  useEffect(() => {
    table.setFilter('id', operationIdFilter ?? null)
    table.setFilter('workflow_execution_id', workflowExecutionId ?? null)
  }, [operationIdFilter, table.setFilter, workflowExecutionId])

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
      node_id: nodeId,
      limit: table.pagination.pageSize,
      offset: pageStart,
    },
  })

  const operations = operationsResponse?.operations ?? []
  const totalOperations = typeof operationsResponse?.total === 'number'
    ? operationsResponse.total
    : operations.length

  const error = queryError
    ? 'Failed to load operations. Please try again.'
    : null

  const handleRefresh = useCallback(() => {
    refetch()
  }, [refetch])

  useEffect(() => {
    if (operationIdFromUrl) {
      setTimelineOperationId(operationIdFromUrl)
      setTimelineVisible(true)
    }
  }, [operationIdFromUrl])

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

        await apiClient.post('/api/v2/operations/execute-ibcmd-cli/', {
          command_id: commandId,
          mode: dc.mode || 'guided',
          database_ids: scope === 'global' ? [] : data.databaseIds,
          auth_database_id: scope === 'global' ? authDatabaseId : undefined,
          connection: dc.connection,
          params: dc.params ?? {},
          additional_args: additionalArgs,
          stdin: typeof dc.stdin === 'string' ? dc.stdin : '',
          confirm_dangerous: dc.confirm_dangerous === true,
          timeout_seconds: boundedTimeout,
        })

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

      if (String(data.operationType).startsWith('ibcmd_')) {
        await api.postOperationsExecuteIbcmd({
          operation_type: data.operationType as
            | 'ibcmd_backup'
            | 'ibcmd_restore'
            | 'ibcmd_replicate'
            | 'ibcmd_create'
            | 'ibcmd_load_cfg'
            | 'ibcmd_extension_update',
          database_ids: data.databaseIds,
          config: data.config,
        })
        handleRefresh()
        return
      }

      throw new Error(`Operation type ${data.operationType} is not supported in wizard`)
    },
    [api, handleRefresh]
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

  return (
    <div>
      {/* Header */}
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <h1 style={{ margin: 0 }}>Operations Monitor</h1>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setWizardVisible(true)}
            disabled={!canCreateOperation}
          >
            New Operation
          </Button>
        </Space>
      </Space>

      {/* Error Alert */}
      {error && (
        <Alert
          message={error}
          type="error"
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      {workflowExecutionId && (
        <Tag closable onClose={() => updateSearchParams({ workflow_execution_id: null })}>
          Workflow: {workflowExecutionId}
        </Tag>
      )}
      {operationIdFilter && (
        <Tag closable onClose={() => updateSearchParams({ operation_id: null })}>
          Operation: {operationIdFilter}
        </Tag>
      )}
      {nodeId && (
        <Tag closable onClose={() => updateSearchParams({ node_id: null })}>
          Node: {nodeId}
        </Tag>
      )}

      <div style={{ marginTop: 12 }}>
      <OperationsTable
        table={table}
        operations={operationsState}
        total={totalOperations}
        loading={loading}
        columns={operationsColumns}
        toolbarActions={(
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={loading}
          >
            Refresh
          </Button>
        )}
        onViewDetails={handleViewDetails}
        onCancel={handleCancel}
        onFilterWorkflow={handleFilterWorkflow}
        onFilterNode={handleFilterNode}
      />
      </div>

      {/* Details Modal */}
      <OperationDetailsModal
        operation={selectedOperation}
        visible={detailsVisible}
        onClose={() => setDetailsVisible(false)}
        onTimeline={handleTimelineOpen}
        liveEvent={selectedOperation ? liveEvents[selectedOperation.id] ?? null : null}
      />

      <OperationTimelineDrawer
        visible={timelineVisible}
        operationId={timelineOperationId || null}
        onClose={handleTimelineClose}
      />

      {/* New Operation Wizard */}
      <NewOperationWizard
        visible={wizardVisible}
        onClose={() => setWizardVisible(false)}
        onSubmit={handleWizardSubmit}
      />
    </div>
  )
}
