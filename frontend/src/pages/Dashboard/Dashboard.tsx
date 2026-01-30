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
import { Row, Col, Alert, Typography, Space, Divider, Button, Tooltip } from 'antd'
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

// Hooks
import { useServiceMesh } from '../../hooks/useServiceMesh'

// Operations components
import { NewOperationWizard } from '../Operations/components/NewOperationWizard'
import type { NewOperationData } from '../Operations/components/NewOperationWizard/types'

const { Title, Text } = Typography

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
      <div style={{ padding: 24 }}>
        <Alert
          message="Error loading dashboard"
          description={error}
          type="error"
          showIcon
          action={
            <Space>
              <Tooltip title="Refresh dashboard">
                <Button
                  type="text"
                  icon={<ReloadOutlined />}
                  onClick={refresh}
                  aria-label="Refresh dashboard"
                />
              </Tooltip>
            </Space>
          }
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={2} style={{ margin: 0 }}>Dashboard</Title>
          {lastUpdated && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Last updated: {lastUpdated.toLocaleTimeString('ru-RU')}
            </Text>
          )}
        </Col>
        <Col>
          <Space>
            <Tooltip title="Refresh dashboard">
              <Button
                type="text"
                icon={<ReloadOutlined spin={loading} />}
                onClick={refresh}
                aria-label="Refresh dashboard"
                disabled={loading}
              />
            </Tooltip>
          </Space>
        </Col>
      </Row>

      {/* Quick Actions */}
      <QuickActionsBar onNewOperation={handleNewOperation} />

      <Divider style={{ margin: '16px 0' }} />

      {/* Statistics Cards */}
      <StatisticsCards
        operations={operations}
        databases={databases}
        loading={loading}
      />

      {/* System Health Card (Real-time via WebSocket) */}
      <Row style={{ marginTop: 24 }}>
        <Col span={24}>
          <SystemHealthCard
            services={services}
            overallHealth={overallHealth}
            timestamp={meshTimestamp}
            isConnected={isConnected}
            connectionError={meshError}
          />
        </Col>
      </Row>

      {/* Recent Operations + Failed Operations Alert */}
      <Row gutter={24} style={{ marginTop: 24 }}>
        <Col xs={24} lg={16}>
          <RecentOperationsTable
            selectedService={null}
            onOperationClick={handleOperationClick}
          />
        </Col>
        <Col xs={24} lg={8}>
          <FailedOperationsAlert
            operations={failedOperations}
            maxDisplay={5}
          />
        </Col>
      </Row>

      {/* Clusters Overview */}
      <Row style={{ marginTop: 24 }}>
        <Col span={24}>
          <ClusterOverview
            clusters={clusters}
            loading={loading}
          />
        </Col>
      </Row>

      {/* New Operation Wizard Modal */}
      <NewOperationWizard
        visible={wizardVisible}
        onClose={handleWizardClose}
        onSubmit={handleWizardSubmit}
      />
    </div>
  )
}

export default Dashboard
