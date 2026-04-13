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
import { STATUS_COLORS } from '../../types/serviceMesh'
import { useDashboardTranslation, useLocaleFormatters } from '../../i18n'
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

function formatTimestamp(
  timestamp: string | null,
  formatters: ReturnType<typeof useLocaleFormatters>,
  fallback: string,
): string {
  if (!timestamp) return fallback

  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSec = Math.floor(diffMs / 1000)

    if (diffSec < 5) return formatters.relativeTime(0, 'second')
    if (diffSec < 60) return formatters.relativeTime(-diffSec, 'second')
    if (diffSec < 3600) return formatters.relativeTime(-Math.floor(diffSec / 60), 'minute')
    return formatters.time(date)
  } catch {
    return fallback
  }
}

const SystemHealthCard: React.FC<SystemHealthCardProps> = ({
  services,
  overallHealth,
  timestamp,
  isConnected,
  connectionError,
}) => {
  const { t } = useDashboardTranslation()
  const formatters = useLocaleFormatters()

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
              <div className="system-health-card__status-label">{t(($) => $.systemHealthCard.systemStatus)}</div>
              <div
                className="system-health-card__status-value"
                style={{ color: STATUS_COLORS[overallHealth] }}
              >
                {t(($) => $.systemHealthCard.overallStatus[overallHealth])}
              </div>
            </div>
          </div>
        </Col>

        {/* Total Ops/Min */}
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title={t(($) => $.systemHealthCard.totalOpsPerMinute)}
            value={formatters.number(totalOpsPerMinute, { maximumFractionDigits: 1 })}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>

        {/* Active Operations */}
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title={t(($) => $.systemHealthCard.activeOps)}
            value={formatters.number(totalActiveOps)}
            valueStyle={{ fontSize: 20 }}
          />
        </Col>

        {/* Avg Latency */}
        <Col xs={12} sm={8} md={4}>
          <Statistic
            title={t(($) => $.systemHealthCard.avgP95)}
            value={formatters.number(avgLatency, { maximumFractionDigits: 0 })}
            suffix="ms"
            valueStyle={{ fontSize: 20 }}
          />
        </Col>

        {/* Service Status Summary */}
        <Col xs={12} sm={8} md={4}>
          <div className="system-health-card__services">
            <div className="system-health-card__services-label">{t(($) => $.systemHealthCard.services)}</div>
            <div className="system-health-card__services-tags">
              {healthyCount > 0 && (
                <Tag color="success">{formatters.number(healthyCount)} {t(($) => $.systemHealthCard.ok)}</Tag>
              )}
              {degradedCount > 0 && (
                <Tag color="warning">{formatters.number(degradedCount)} {t(($) => $.systemHealthCard.warn)}</Tag>
              )}
              {criticalCount > 0 && (
                <Tag color="error">{formatters.number(criticalCount)} {t(($) => $.systemHealthCard.crit)}</Tag>
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
                  ? t(($) => $.systemHealthCard.lastUpdate, {
                    value: formatTimestamp(timestamp, formatters, t(($) => $.systemHealthCard.unavailable)),
                  })
                  : t(($) => $.systemHealthCard.connecting)
              }
            >
              <span>
                {isConnected ? (
                  <Badge status="success" text={<WifiOutlined />} />
                ) : connectionError ? (
                  <Badge status="error" text={<DisconnectOutlined />} />
                ) : (
                  <Badge status="processing" text={<SyncOutlined spin />} />
                )}
              </span>
            </Tooltip>
          </div>
        </Col>
      </Row>
    </Card>
  )
}

export default SystemHealthCard
