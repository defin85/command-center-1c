/**
 * Waterfall Timeline Component
 *
 * Visualizes operation execution as a waterfall chart showing
 * the flow of events across services with timing information.
 *
 * Features:
 * - Horizontal bars showing event duration
 * - Service icons from SERVICE_DISPLAY_CONFIG
 * - Color coding by event status (received/completed/failed)
 * - Expandable metadata on click
 */
import React, { useState, useMemo } from 'react'
import { Tooltip, Tag, Collapse } from 'antd'
import {
  DesktopOutlined,
  GatewayOutlined,
  ApartmentOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  NotificationOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import type { WaterfallItem, EventStatus } from '../../types/operationTimeline'
import { SERVICE_DISPLAY_CONFIG } from '../../types/serviceMesh'
import {
  getEventStatus,
  formatDuration,
  formatTimestamp,
  calculateTotalDuration,
} from '../../utils/timelineTransforms'
import './WaterfallTimeline.css'

/**
 * Bar width constraints
 */
const MIN_BAR_WIDTH_PERCENT = 2
const MAX_BAR_WIDTH_PERCENT = 100

/**
 * Event status colors
 */
const STATUS_COLORS: Record<EventStatus, string> = {
  received: '#1890ff',    // Blue
  processing: '#faad14',  // Orange/Amber (Ant Design warning)
  completed: '#52c41a',   // Green
  failed: '#ff4d4f',      // Red
  unknown: '#8c8c8c',     // Gray
}

/**
 * Service icon mapping
 */
const SERVICE_ICONS: Record<string, React.ReactNode> = {
  frontend: <DesktopOutlined />,
  'api-gateway': <GatewayOutlined />,
  orchestrator: <ApartmentOutlined />,
  worker: <ThunderboltOutlined />,
  postgresql: <DatabaseOutlined />,
  redis: <CloudServerOutlined />,
  'event-subscriber': <NotificationOutlined />,
}

/**
 * Get icon for a service
 */
function getServiceIcon(service: string): React.ReactNode {
  return SERVICE_ICONS[service] || <QuestionCircleOutlined />
}

/**
 * Get display name for a service
 */
function getServiceDisplayName(service: string): string {
  return SERVICE_DISPLAY_CONFIG[service]?.displayName || service
}

interface WaterfallTimelineProps {
  items: WaterfallItem[]
  className?: string
}

/**
 * Format metadata for display
 */
function formatMetadata(metadata: Record<string, unknown>): React.ReactNode {
  const entries = Object.entries(metadata)
  if (entries.length === 0) {
    return <span className="waterfall-metadata-empty">No metadata</span>
  }

  return (
    <div className="waterfall-metadata-content">
      {entries.map(([key, value]) => (
        <div key={key} className="waterfall-metadata-item">
          <span className="waterfall-metadata-key">{key}:</span>
          <span className="waterfall-metadata-value">
            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

const WaterfallTimeline: React.FC<WaterfallTimelineProps> = ({ items, className }) => {
  const [expandedItems, setExpandedItems] = useState<string[]>([])

  // Calculate total duration for scale
  const totalDuration = useMemo(() => calculateTotalDuration(items), [items])

  // Calculate bar width as percentage
  const getBarWidth = (duration: number): number => {
    if (totalDuration === 0) return 0
    return Math.max(MIN_BAR_WIDTH_PERCENT, Math.min(MAX_BAR_WIDTH_PERCENT, (duration / totalDuration) * 100))
  }

  // Calculate bar offset as percentage
  const getBarOffset = (startOffset: number): number => {
    if (totalDuration === 0) return 0
    return (startOffset / totalDuration) * 100
  }

  const handleToggleExpand = (itemId: string) => {
    setExpandedItems((prev) =>
      prev.includes(itemId) ? prev.filter((id) => id !== itemId) : [...prev, itemId]
    )
  }

  if (items.length === 0) {
    return (
      <div className={`waterfall-container waterfall-empty ${className || ''}`}>
        No timeline events
      </div>
    )
  }

  return (
    <div className={`waterfall-container ${className || ''}`}>
      {/* Timeline header with time markers */}
      <div className="waterfall-header">
        <div className="waterfall-header-label">Event</div>
        <div className="waterfall-header-timeline">
          <span className="waterfall-time-marker waterfall-time-start">0ms</span>
          <span className="waterfall-time-marker waterfall-time-middle">
            {formatDuration(totalDuration / 2)}
          </span>
          <span className="waterfall-time-marker waterfall-time-end">
            {formatDuration(totalDuration)}
          </span>
        </div>
      </div>

      {/* Timeline rows */}
      <div className="waterfall-rows">
        {items.map((item) => {
          const status = getEventStatus(item.event)
          const barColor = STATUS_COLORS[status]
          const barWidth = getBarWidth(item.duration)
          const barOffset = getBarOffset(item.startOffset)
          const isExpanded = expandedItems.includes(item.id)
          const hasMetadata = item.metadata && Object.keys(item.metadata).length > 0

          return (
            <div key={item.id} className="waterfall-row-wrapper">
              <div
                className={`waterfall-row ${isExpanded ? 'waterfall-row-expanded' : ''}`}
                onClick={() => hasMetadata && handleToggleExpand(item.id)}
                style={{ cursor: hasMetadata ? 'pointer' : 'default' }}
              >
                {/* Event label with service icon */}
                <div className="waterfall-label">
                  <Tooltip title={getServiceDisplayName(item.service)}>
                    <span className="waterfall-service-icon">
                      {getServiceIcon(item.service)}
                    </span>
                  </Tooltip>
                  <span className="waterfall-event-name">{item.eventLabel}</span>
                  <Tag
                    color={barColor}
                    className="waterfall-status-tag"
                  >
                    {status}
                  </Tag>
                </div>

                {/* Bar container */}
                <div className="waterfall-bar-container">
                  <Tooltip
                    title={
                      <div>
                        <div>
                          <strong>{item.eventLabel}</strong>
                        </div>
                        <div>Service: {getServiceDisplayName(item.service)}</div>
                        <div>Time: {formatTimestamp(item.timestamp)}</div>
                        <div>Duration: {formatDuration(item.duration)}</div>
                        <div>Offset: +{formatDuration(item.startOffset)}</div>
                      </div>
                    }
                  >
                    <div
                      className="waterfall-bar"
                      style={{
                        backgroundColor: barColor,
                        width: `${barWidth}%`,
                        left: `${barOffset}%`,
                      }}
                    />
                  </Tooltip>
                </div>

                {/* Duration label */}
                <div className="waterfall-duration">
                  {item.duration > 0 ? formatDuration(item.duration) : '-'}
                </div>
              </div>

              {/* Expanded metadata */}
              {hasMetadata && (
                <Collapse
                  activeKey={isExpanded ? ['metadata'] : []}
                  ghost
                  className="waterfall-metadata-collapse"
                  items={[
                    {
                      key: 'metadata',
                      label: null,
                      children: formatMetadata(item.metadata),
                      showArrow: false,
                    },
                  ]}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default WaterfallTimeline
