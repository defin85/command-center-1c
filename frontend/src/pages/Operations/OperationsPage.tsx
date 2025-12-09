/**
 * Main Operations page with tabs.
 * Orchestrates OperationsTable, LiveMonitorTab, and NewOperationWizard components.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Tabs, Button, Space, Alert } from 'antd'
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { getV2 } from '../../api/generated'
import { transformBatchOperation } from '../../utils/operationTransforms'
import { OperationsTable } from './components/OperationsTable'
import { OperationDetailsModal } from './components/OperationDetailsModal'
import { LiveMonitorTab } from './components/LiveMonitorTab'
import { NewOperationWizard } from './components/NewOperationWizard'
import type { NewOperationData } from './components/NewOperationWizard'
import type { UIBatchOperation, OperationsTabKey } from './types'

// Initialize generated API
const api = getV2()

/**
 * OperationsPage - Main page with tabs for operations list and live monitor
 */
export const OperationsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  // State
  const [operations, setOperations] = useState<UIBatchOperation[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedOperation, setSelectedOperation] = useState<UIBatchOperation | null>(null)
  const [detailsVisible, setDetailsVisible] = useState(false)
  const [wizardVisible, setWizardVisible] = useState(false)

  // AbortController ref for cancelling in-flight requests
  const abortControllerRef = useRef<AbortController | null>(null)

  // Get active tab from URL or default to 'list'
  const activeTab = (searchParams.get('tab') as OperationsTabKey) || 'list'
  const operationId = searchParams.get('operation') || undefined

  // Fetch operations from API with abort support
  const fetchOperations = useCallback(async (signal?: AbortSignal) => {
    try {
      setLoading(true)
      setError(null)
      const response = await api.getOperationsListOperations()
      if (!signal?.aborted) {
        setOperations(response.operations.map(transformBatchOperation))
      }
    } catch (err) {
      if (!signal?.aborted) {
        console.error('Failed to load operations:', err)
        setError('Failed to load operations. Please try again.')
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false)
      }
    }
  }, [])

  // Auto-refresh polling with abort support
  useEffect(() => {
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    fetchOperations(abortController.signal)

    // Auto-refresh every 5 seconds
    const interval = setInterval(() => {
      fetchOperations(abortController.signal)
    }, 5000)

    return () => {
      abortController.abort()
      clearInterval(interval)
    }
  }, [fetchOperations])

  // Manual refresh handler
  const handleRefresh = useCallback(() => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const newController = new AbortController()
    abortControllerRef.current = newController
    fetchOperations(newController.signal)
  }, [fetchOperations])

  // Handle cancel operation
  const handleCancel = async (id: string) => {
    try {
      await api.postOperationsCancelOperation({ operation_id: id })
      handleRefresh()
    } catch (err) {
      console.error('Failed to cancel operation:', err)
    }
  }

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
  const handleWizardSubmit = useCallback(async (data: NewOperationData) => {
    // TODO: Implement actual API call to create operation
    // For now, just log and close
    console.log('Creating operation:', data)

    // Placeholder: In future phases, this will call the appropriate API
    // based on data.operationType (e.g., batch lock, batch health check, etc.)

    // Refresh operations list after creation
    handleRefresh()
  }, [handleRefresh])

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
          onClose={() => setError(null)}
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
