/**
 * Custom node component for react-flow service mesh visualization.
 *
 * Displays:
 * - Service name and status indicator
 * - Key metrics (ops/min, latency)
 * - Click handler for detail drawer
 */
import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { Badge, Tooltip } from 'antd'
import {
  DesktopOutlined,
  GatewayOutlined,
  ApartmentOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  BuildOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
} from '@ant-design/icons'
import type { ServiceStatus, ServiceNodeData, OperationFlowStatus } from '../../types/serviceMesh'
import { STATUS_COLORS, STATUS_TEXT } from '../../types/serviceMesh'
import './ServiceNode.css'

// Re-export for backward compatibility with existing imports
export type { ServiceNodeData }

const SERVICE_ICONS: Record<string, React.ReactNode> = {
  frontend: <DesktopOutlined />,
  'api-gateway': <GatewayOutlined />,
  orchestrator: <ApartmentOutlined />,
  worker: <ThunderboltOutlined />,
  'ras-adapter': <ApiOutlined />,
  'celery-worker': <SyncOutlined />,
  'celery-beat': <ClockCircleOutlined />,
  'batch-service': <BuildOutlined />,
  postgresql: <DatabaseOutlined />,
  redis: <CloudServerOutlined />,
}

/**
 * Format number with appropriate suffix (K, M)
 */
function formatNumber(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return value.toFixed(1)
}

/**
 * Format latency with appropriate unit
 */
function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`
  }
  return `${ms.toFixed(0)}ms`
}

/**
 * Get status badge color
 */
function getStatusBadge(status: ServiceStatus): 'success' | 'warning' | 'error' {
  switch (status) {
    case 'healthy':
      return 'success'
    case 'degraded':
      return 'warning'
    case 'critical':
      return 'error'
    default:
      return 'warning'
  }
}

/**
 * Get CSS class based on operation status
 */
function getOperationClassName(status: OperationFlowStatus | null | undefined): string {
  switch (status) {
    case 'active':
      return 'service-node--operation-active'
    case 'completed':
      return 'service-node--operation-completed'
    case 'failed':
      return 'service-node--operation-failed'
    default:
      return ''
  }
}

const ServiceNode: React.FC<NodeProps<ServiceNodeData>> = ({ data }) => {
  const { metrics, onSelect, isSelected, operationStatus } = data
  const icon = SERVICE_ICONS[metrics.name] || <ApiOutlined />
  const operationClass = getOperationClassName(operationStatus)

  const handleClick = () => {
    onSelect(metrics.name)
  }

  return (
    <div
      className={`service-node ${isSelected ? 'service-node--selected' : ''} ${operationClass}`}
      onClick={handleClick}
      style={{
        borderColor: isSelected ? STATUS_COLORS[metrics.status] : undefined,
      }}
    >
      {/* Input handle for connections from above */}
      <Handle
        type="target"
        position={Position.Top}
        className="service-node__handle"
      />

      {/* Header with icon, name, and status */}
      <div className="service-node__header">
        <span className="service-node__icon">{icon}</span>
        <span className="service-node__name">{metrics.displayName}</span>
        <Tooltip title={STATUS_TEXT[metrics.status]}>
          <span>
            <Badge
              status={getStatusBadge(metrics.status)}
              className="service-node__status"
            />
          </span>
        </Tooltip>
      </div>

      {/* Metrics section */}
      <div className="service-node__metrics">
        <div className="service-node__metric">
          <span className="service-node__metric-value">
            {formatNumber(metrics.opsPerMinute)}
          </span>
          <span className="service-node__metric-label">ops/min</span>
        </div>
        <div className="service-node__metric">
          <span className="service-node__metric-value">
            {formatLatency(metrics.p95LatencyMs)}
          </span>
          <span className="service-node__metric-label">p95</span>
        </div>
      </div>

      {/* Error rate indicator (only show if > 0) */}
      {metrics.errorRate > 0 && (
        <div
          className="service-node__error-rate"
          style={{
            color: metrics.errorRate > 0.01 ? STATUS_COLORS.critical : STATUS_COLORS.degraded,
          }}
        >
          {(metrics.errorRate * 100).toFixed(2)}% errors
        </div>
      )}

      {/* Output handle for connections to below */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="service-node__handle"
      />
    </div>
  )
}

export default memo(ServiceNode)
