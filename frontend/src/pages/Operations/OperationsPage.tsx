/**
 * Main Operations page with tabs.
 * Orchestrates OperationsTable, OperationDetailsModal, and NewOperationWizard components.
 *
 * Uses React Query for data fetching with automatic polling.
 */

import { useState, useCallback, useEffect } from 'react'
import { Button, Space, Alert, Tag } from 'antd'
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { useOperations, useCancelOperation } from '../../api/queries/operations'
import { getRuntimeSettings } from '../../api/runtimeSettings'
import type { TimelineStreamEvent } from '../../hooks/useOperationTimelineStream'
import { useOperationsMuxStream } from '../../hooks/useOperationsMuxStream'
import { OperationsTable } from './components/OperationsTable'
import { OperationDetailsModal } from './components/OperationDetailsModal'
import { OperationsFilters } from './components/OperationsFilters'
import { NewOperationWizard } from './components/NewOperationWizard'
import OperationTimelineDrawer from '../../components/service-mesh/OperationTimelineDrawer'
import type { NewOperationData } from './components/NewOperationWizard'
import type { UIBatchOperation } from './types'

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

  // React Query: operations list with 5s polling
  const {
    data: operations = [],
    isLoading: loading,
    error: queryError,
    refetch,
  } = useOperations({
    refetchInterval: 5000,
    filters: {
      operation_id: operationIdFilter,
      workflow_execution_id: workflowExecutionId,
      node_id: nodeId,
    },
  })

  // React Query: cancel mutation
  const cancelMutation = useCancelOperation()

  // Derive error message from query error
  const error = queryError
    ? 'Failed to load operations. Please try again.'
    : null

  // Manual refresh handler
  const handleRefresh = useCallback(() => {
    refetch()
  }, [refetch])

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

  useEffect(() => {
    if (operationIdFromUrl) {
      setTimelineOperationId(operationIdFromUrl)
      setTimelineVisible(true)
    }
  }, [operationIdFromUrl])

  useEffect(() => {
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
  }, [])

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
      // TODO: Implement actual API call to create operation
      // For now, just log and close
      console.log('Creating operation:', data)

      // Placeholder: In future phases, this will call the appropriate API
      // based on data.operationType (e.g., batch lock, batch health check, etc.)

      // Refresh operations list after creation
      handleRefresh()
    },
    [handleRefresh]
  )

  const activeOperationIds = operationsState
    .filter((operation) => isActiveStatus(operation.status))
    .slice(0, Math.min(maxLiveStreams, maxSubscriptions))
    .map((operation) => operation.id)

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
          >
            New Operation
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={loading}
          >
            Refresh
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

      <OperationsFilters
        filters={{
          operation_id: operationIdFilter,
          workflow_execution_id: workflowExecutionId,
          node_id: nodeId,
        }}
        onChange={(next) => {
          updateSearchParams({
            operation_id: next.operation_id?.trim() || null,
            workflow_execution_id: next.workflow_execution_id || null,
            node_id: next.node_id || null,
          })
        }}
      />

      <div style={{ marginTop: 12 }}>
      <OperationsTable
        operations={operationsState}
        loading={loading}
        onRefresh={handleRefresh}
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
