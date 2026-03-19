/**
 * Dashboard - Main overview page for CommandCenter1C
 *
 * Displays:
 * - Quick action buttons (New Operation, View All, System Status)
 * - KPI statistics cards (Operations, Databases, Success Rate)
 * - System health card with real-time updates (WebSocket)
 * - Recent operations table
 * - Failed operations alert
 * - Clusters overview
 */
import React, { useState, useCallback } from 'react'
import { Button, Tooltip } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

// Dashboard components
import {
  StatisticsCards,
  QuickActionsBar,
  FailedOperationsAlert,
  ClusterOverview,
} from './components'
import { useDashboardStats } from './hooks'

// Reusable components from service-mesh
import SystemHealthCard from '../../components/service-mesh/SystemHealthCard'
import RecentOperationsTable from '../../components/service-mesh/RecentOperationsTable'
import { DashboardPage, ErrorState, PageHeader } from '../../components/platform'

// Hooks
import { useServiceMesh } from '../../hooks/useServiceMesh'

// Operations components
import { NewOperationWizard } from '../Operations/components/NewOperationWizard'
import type { NewOperationData } from '../Operations/components/NewOperationWizard/types'
import './Dashboard.css'

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()

  // Dashboard statistics with polling
  const {
    operations,
    databases,
    clusters,
    failedOperations,
    loading,
    error,
    lastUpdated,
    refresh,
  } = useDashboardStats(30000) // 30 second refresh

  // Real-time service mesh data via WebSocket
  const {
    services,
    overallHealth,
    timestamp: meshTimestamp,
    isConnected,
    connectionError: meshError,
  } = useServiceMesh()

  // New Operation Wizard state
  const [wizardVisible, setWizardVisible] = useState(false)

  const handleNewOperation = useCallback(() => {
    setWizardVisible(true)
  }, [])

  const handleWizardClose = useCallback(() => {
    setWizardVisible(false)
  }, [])

  const handleWizardSubmit = useCallback(async (_data: NewOperationData) => {
    setWizardVisible(false)
    // Refresh stats after creating operation
    refresh()
  }, [refresh])

  const handleOperationClick = useCallback((operationId: string) => {
    navigate(`/operations?operation=${operationId}&tab=monitor`)
  }, [navigate])

  // Error state
  if (error && !loading) {
    return (
      <DashboardPage
        header={(
          <PageHeader title="Dashboard" />
        )}
      >
        <ErrorState
          message="Error loading dashboard"
          description={error}
          action={(
            <Tooltip title="Refresh dashboard">
              <Button
                type="text"
                icon={<ReloadOutlined />}
                onClick={refresh}
                aria-label="Refresh dashboard"
              />
            </Tooltip>
          )}
        />
      </DashboardPage>
    )
  }

  return (
    <DashboardPage
      header={(
        <PageHeader
          title="Dashboard"
          subtitle={lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString('ru-RU')}` : undefined}
          actions={(
            <Tooltip title="Refresh dashboard">
              <Button
                type="text"
                icon={<ReloadOutlined spin={loading} />}
                onClick={refresh}
                aria-label="Refresh dashboard"
                disabled={loading}
              />
            </Tooltip>
          )}
        />
      )}
    >
      <div className="dashboard-route">
        <div className="dashboard-route__section">
          <QuickActionsBar onNewOperation={handleNewOperation} />
        </div>

        <div
          className="dashboard-route__separator"
          aria-hidden="true"
        />

        <div className="dashboard-route__section">
          <StatisticsCards
            operations={operations}
            databases={databases}
            loading={loading}
          />
        </div>

        <div className="dashboard-route__section">
          <SystemHealthCard
            services={services}
            overallHealth={overallHealth}
            timestamp={meshTimestamp}
            isConnected={isConnected}
            connectionError={meshError}
          />
        </div>

        <div className="dashboard-route__support-grid">
          <RecentOperationsTable
            selectedService={null}
            onOperationClick={handleOperationClick}
          />

          <FailedOperationsAlert
            operations={failedOperations}
            maxDisplay={5}
          />
        </div>

        <div className="dashboard-route__section">
          <ClusterOverview
            clusters={clusters}
            loading={loading}
          />
        </div>
      </div>

      {/* New Operation Wizard Modal */}
      <NewOperationWizard
        visible={wizardVisible}
        onClose={handleWizardClose}
        onSubmit={handleWizardSubmit}
      />
    </DashboardPage>
  )
}

export default Dashboard
