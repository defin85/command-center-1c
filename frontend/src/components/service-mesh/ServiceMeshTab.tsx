/**
 * Main Service Mesh Tab component.
 *
 * Combines all service mesh components:
 * - SystemHealthCard (header)
 * - ServiceFlowDiagram (main visualization)
 * - ServiceDetailDrawer (right drawer)
 * - OperationTimelineDrawer (timeline visualization)
 * - RecentOperationsTable (bottom)
 */
import React, { useState, useCallback, useMemo, useRef } from 'react'
import { Alert, Spin } from 'antd'
import useServiceMesh from '../../hooks/useServiceMesh'
import { useResponsiveDirection } from '../../hooks/useResponsiveDirection'
import { getV2 } from '../../api/generated/v2/v2'
import type { SystemHealthResponse, ServiceHealth } from '../../api/generated/model'
import SystemHealthCard from './SystemHealthCard'
import ServiceFlowDiagram from './ServiceFlowDiagram'
import ServiceDetailDrawer from './ServiceDetailDrawer'
import OperationTimelineDrawer from './OperationTimelineDrawer'
import RecentOperationsTable from './RecentOperationsTable'
import type { ServiceMetrics } from '../../types/serviceMesh'
import './ServiceMeshTab.css'

const api = getV2()

const ServiceMeshTab: React.FC = () => {
  // Ref for diagram container (used by useResponsiveDirection)
  const diagramContainerRef = useRef<HTMLDivElement>(null)

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

  // Responsive layout direction
  const { mode: directionMode, direction, setMode: setDirectionMode } = useResponsiveDirection(diagramContainerRef)

  // Selected service for detail drawer
  const [selectedService, setSelectedService] = useState<string | null>(null)

  // Selected operation for timeline drawer
  const [selectedOperationId, setSelectedOperationId] = useState<string | null>(null)

  // External dependency health (not covered by Prometheus service targets)
  const [rasServerHealth, setRasServerHealth] = useState<{
    status: 'online' | 'offline' | 'degraded'
    message: string
  } | null>(null)

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

  // Handle operation click - open timeline drawer
  const handleOperationClick = useCallback((operationId: string) => {
    setSelectedOperationId(operationId)
  }, [])

  // Handle timeline drawer close
  const handleTimelineClose = useCallback(() => {
    setSelectedOperationId(null)
  }, [])

  React.useEffect(() => {
    let isMounted = true

    const refresh = async () => {
      try {
        const data: SystemHealthResponse = await api.getSystemHealth()
        const ras = (data.services || []).find((s: ServiceHealth) => s.name === 'RAS Server')
        if (!ras) {
          if (isMounted) setRasServerHealth(null)
          return
        }
        const targetRaw = ras.details?.target
        const errorRaw = ras.details?.error
        const target = targetRaw ? String(targetRaw) : ''
        const error = errorRaw ? String(errorRaw) : ''
        const msgParts = ['RAS Server']
        if (target) msgParts.push(`target: ${target}`)
        if (error) msgParts.push(`error: ${error}`)

        if (isMounted) {
          setRasServerHealth({
            status: ras.status,
            message: msgParts.join(' • '),
          })
        }
      } catch {
        if (isMounted) {
          setRasServerHealth({
            status: 'offline',
            message: 'RAS Server • health check failed',
          })
        }
      }
    }

    refresh()
    const interval = setInterval(refresh, 60_000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

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

      {rasServerHealth && rasServerHealth.status !== 'online' && (
        <Alert
          message="RAS connectivity"
          description={rasServerHealth.message}
          type={rasServerHealth.status === 'degraded' ? 'warning' : 'error'}
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
      <div ref={diagramContainerRef} className="service-mesh-tab__diagram-container">
        <ServiceFlowDiagram
          services={services}
          connections={connections}
          selectedService={selectedService}
          onServiceSelect={handleServiceSelect}
          activeOperation={activeOperation}
          directionMode={directionMode}
          direction={direction}
          onDirectionModeChange={setDirectionMode}
        />
      </div>

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

      {/* Operation Timeline Drawer */}
      <OperationTimelineDrawer
        operationId={selectedOperationId}
        visible={selectedOperationId !== null}
        onClose={handleTimelineClose}
      />
    </div>
  )
}

export default ServiceMeshTab
