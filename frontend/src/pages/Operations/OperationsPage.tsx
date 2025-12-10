/**
 * Main Operations page with tabs.
 * Orchestrates OperationsTable, LiveMonitorTab, and NewOperationWizard components.
 *
 * Uses React Query for data fetching with automatic polling.
 */

import { useState, useCallback } from 'react'
import { Tabs, Button, Space, Alert } from 'antd'
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { useOperations, useCancelOperation } from '../../api/queries/operations'
import { OperationsTable } from './components/OperationsTable'
import { OperationDetailsModal } from './components/OperationDetailsModal'
import { LiveMonitorTab } from './components/LiveMonitorTab'
import { NewOperationWizard } from './components/NewOperationWizard'
import type { NewOperationData } from './components/NewOperationWizard'
import type { UIBatchOperation, OperationsTabKey } from './types'

/**
 * OperationsPage - Main page with tabs for operations list and live monitor
 */
export const OperationsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  // UI State (not data-related)
  const [selectedOperation, setSelectedOperation] = useState<UIBatchOperation | null>(null)
  const [detailsVisible, setDetailsVisible] = useState(false)
  const [wizardVisible, setWizardVisible] = useState(false)

  // Get active tab from URL or default to 'list'
  const activeTab = (searchParams.get('tab') as OperationsTabKey) || 'list'
  const operationId = searchParams.get('operation') || undefined

  // React Query: operations list with 5s polling
  const {
    data: operations = [],
    isLoading: loading,
    error: queryError,
    refetch,
  } = useOperations({ refetchInterval: 5000 })

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

  // Switch to monitor tab with selected operation
  const handleMonitor = (opId: string) => {
    setDetailsVisible(false)
    // Switch to monitor tab with operation ID in URL
    setSearchParams({ tab: 'monitor', operation: opId })
  }

  // Handle tab change - preserve operation param only for monitor tab
  const handleTabChange = (key: string) => {
    if (key === 'monitor' && operationId) {
      setSearchParams({ tab: key, operation: operationId })
    } else {
      setSearchParams({ tab: key })
    }
  }

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

  // Tab items configuration
  const tabItems = [
    {
      key: 'list',
      label: 'All Operations',
      children: (
        <OperationsTable
          operations={operations}
          loading={loading}
          onRefresh={handleRefresh}
          onViewDetails={handleViewDetails}
          onCancel={handleCancel}
        />
      ),
    },
    {
      key: 'monitor',
      label: 'Live Monitor',
      children: <LiveMonitorTab operationId={operationId} />,
    },
  ]

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

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={tabItems}
      />

      {/* Details Modal */}
      <OperationDetailsModal
        operation={selectedOperation}
        visible={detailsVisible}
        onClose={() => setDetailsVisible(false)}
        onMonitor={handleMonitor}
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
