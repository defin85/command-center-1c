/**
 * Main Service Mesh Tab component.
 *
 * Combines all service mesh components:
 * - SystemHealthCard (header)
 * - ServiceFlowDiagram (main visualization)
 * - ServiceDetailDrawer (right drawer)
 * - RecentOperationsTable (bottom)
 */
import React, { useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Spin } from 'antd'
import useServiceMesh from '../../hooks/useServiceMesh'
import SystemHealthCard from './SystemHealthCard'
import ServiceFlowDiagram from './ServiceFlowDiagram'
import ServiceDetailDrawer from './ServiceDetailDrawer'
import RecentOperationsTable from './RecentOperationsTable'
import type { ServiceMetrics } from '../../types/serviceMesh'
import './ServiceMeshTab.css'

const ServiceMeshTab: React.FC = () => {
  const navigate = useNavigate()

  // WebSocket hook for real-time metrics
  const {
    services,
    connections,
    overallHealth,
    timestamp,
    isConnected,
    connectionError,
    activeOperation,
  } = useServiceMesh()

  // Selected service for detail drawer
  const [selectedService, setSelectedService] = useState<string | null>(null)

  // Get selected service metrics
  const selectedServiceMetrics: ServiceMetrics | null = useMemo(() => {
    if (!selectedService) return null
    return services.find((s) => s.name === selectedService) || null
  }, [selectedService, services])

  // Handle service selection from diagram
  const handleServiceSelect = useCallback((service: string | null) => {
    setSelectedService(service)
  }, [])

  // Handle drawer close
  const handleDrawerClose = useCallback(() => {
    setSelectedService(null)
  }, [])

  // Handle operation click
  const handleOperationClick = useCallback((operationId: string) => {
    // Navigate to operation details
    navigate(`/operation-monitor?operation=${operationId}`)
  }, [navigate])

  // Show loading state if no services yet
  if (services.length === 0 && !connectionError) {
    return (
      <div className="service-mesh-tab__loading">
        <Spin size="large" tip="Loading service mesh...">
          <div style={{ minHeight: 200 }} />
        </Spin>
      </div>
    )
  }

  return (
    <div className="service-mesh-tab">
      {/* Connection error alert */}
      {connectionError && !isConnected && (
        <Alert
          message="Connection Issue"
          description={connectionError}
          type="warning"
          showIcon
          className="service-mesh-tab__alert"
        />
      )}

      {/* System Health Overview */}
      <SystemHealthCard
        services={services}
        overallHealth={overallHealth}
        timestamp={timestamp}
        isConnected={isConnected}
        connectionError={connectionError}
      />

      {/* Service Flow Diagram */}
      <ServiceFlowDiagram
        services={services}
        connections={connections}
        selectedService={selectedService}
        onServiceSelect={handleServiceSelect}
        activeOperation={activeOperation}
      />

      {/* Recent Operations Table */}
      <RecentOperationsTable
        selectedService={selectedService}
        onOperationClick={handleOperationClick}
      />

      {/* Service Detail Drawer */}
      <ServiceDetailDrawer
        service={selectedServiceMetrics}
        visible={selectedService !== null}
        onClose={handleDrawerClose}
      />
    </div>
  )
}

export default ServiceMeshTab
