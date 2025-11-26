/**
 * System health overview card for service mesh.
 *
 * Displays:
 * - Overall system status
 * - Total ops/min across all services
 * - Active operations count
 * - Connection status indicator
 */
import React from 'react'
import { Card, Badge, Statistic, Row, Col, Tag, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  DisconnectOutlined,
  WifiOutlined,
} from '@ant-design/icons'
import type { ServiceMetrics, ServiceStatus } from '../../types/serviceMesh'
import { STATUS_COLORS, STATUS_TEXT } from '../../types/serviceMesh'
import './SystemHealthCard.css'

interface SystemHealthCardProps {
  services: ServiceMetrics[]
  overallHealth: ServiceStatus
  timestamp: string | null
  isConnected: boolean
  connectionError: string | null
}

/**
 * Get status icon component
 */
function getStatusIcon(status: ServiceStatus): React.ReactNode {
  switch (status) {
    case 'healthy':
      return <CheckCircleOutlined style={{ color: STATUS_COLORS.healthy }} />
    case 'degraded':
      return <WarningOutlined style={{ color: STATUS_COLORS.degraded }} />
    case 'critical':
      return <CloseCircleOutlined style={{ color: STATUS_COLORS.critical }} />
    default:
      return <WarningOutlined style={{ color: STATUS_COLORS.degraded }} />
  }
}

/**
 * Format timestamp to relative time
 */
function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return 'N/A'

  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSec = Math.floor(diffMs / 1000)

    if (diffSec < 5) return 'Just now'
    if (diffSec < 60) return `${diffSec}s ago`
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
    return date.toLocaleTimeString()
  } catch {
    return 'N/A'
  }
}

const SystemHealthCard: React.FC<SystemHealthCardProps> = ({
  services,
  overallHealth,
  timestamp,
  isConnected,
  connectionError,
}) => {
  // Calculate totals
  const totalOpsPerMinute = services.reduce((sum, s) => sum + s.opsPerMinute, 0)
  const totalActiveOps = services.reduce((sum, s) => sum + s.activeOperations, 0)
  const avgLatency =
    services.length > 0
      ? services.reduce((sum, s) => sum + s.p95LatencyMs, 0) / services.length
      : 0

  // Count services by status
  const healthyCount = services.filter((s) => s.status === 'healthy').length
  const degradedCount = services.filter((s) => s.status === 'degraded').length
  const criticalCount = services.filter((s) => s.status === 'critical').length

  return (
    <Card className="system-health-card" size="small">
      <Row gutter={[24, 16]} align="middle">
        {/* Overall Status */}
        <Col xs={24} sm={8} md={6}>
          <div className="system-health-card__status">
            <div className="system-health-card__status-icon">
              {getStatusIcon(overallHealth)}
            </div>
            <div className="system-health-card__status-info">
              <div className="system-health-card__status-label">System Status</div>
              <div
                className="system-health-card__status-value"
                style={{ color: STATUS_COLORS[overallHealth] }}
              >
                {STATUS_TEXT[overallHealth]}
              </div>
            </div>
          </div>
        </Col>

        {/* Total Ops/Min */}
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title="Total Ops/min"
            value={totalOpsPerMinute}
            precision={1}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>

        {/* Active Operations */}
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title="Active Ops"
            value={totalActiveOps}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>

        {/* Avg Latency */}
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title="Avg P95"
            value={avgLatency}
            suffix="ms"
            precision={0}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>

        {/* Service Status Summary */}
        <Col xs={12} sm={8} md={4}>
          <div className="system-health-card__services">
            <div className="system-health-card__services-label">Services</div>
            <div className="system-health-card__services-tags">
              {healthyCount > 0 && (
                <Tag color="success">{healthyCount} OK</Tag>
              )}
              {degradedCount > 0 && (
                <Tag color="warning">{degradedCount} Warn</Tag>
              )}
              {criticalCount > 0 && (
                <Tag color="error">{criticalCount} Crit</Tag>
              )}
            </div>
          </div>
        </Col>

        {/* Connection Status */}
        <Col xs={24} sm={8} md={2}>
          <div className="system-health-card__connection">
            <Tooltip
              title={
                connectionError
                  ? connectionError
                  : isConnected
                  ? `Last update: ${formatTimestamp(timestamp)}`
                  : 'Connecting...'
              }
            >
              {isConnected ? (
                <Badge status="success" text={<WifiOutlined />} />
              ) : connectionError ? (
                <Badge status="error" text={<DisconnectOutlined />} />
              ) : (
                <Badge status="processing" text={<SyncOutlined spin />} />
              )}
            </Tooltip>
          </div>
        </Col>
      </Row>
    </Card>
  )
}

export default SystemHealthCard
