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
import { OperationsTable } from './components/OperationsTable'
import { OperationDetailsModal } from './components/OperationDetailsModal'
import { OperationsFilters } from './components/OperationsFilters'
import { NewOperationWizard } from './components/NewOperationWizard'
import OperationTimelineDrawer from '../../components/service-mesh/OperationTimelineDrawer'
import type { NewOperationData } from './components/NewOperationWizard'
import type { UIBatchOperation } from './types'

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

  const operationIdFromUrl = searchParams.get('operation') || undefined
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
    filters: { workflow_execution_id: workflowExecutionId, node_id: nodeId },
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
      {nodeId && (
        <Tag closable onClose={() => updateSearchParams({ node_id: null })}>
          Node: {nodeId}
        </Tag>
      )}

      <OperationsFilters
        filters={{ workflow_execution_id: workflowExecutionId, node_id: nodeId }}
        onChange={(next) => {
          updateSearchParams({
            workflow_execution_id: next.workflow_execution_id || null,
            node_id: next.node_id || null,
          })
        }}
      />

      <div style={{ marginTop: 12 }}>
      <OperationsTable
        operations={operations}
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
