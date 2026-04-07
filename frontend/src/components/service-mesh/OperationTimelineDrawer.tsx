/**
 * Operation Timeline Drawer Component
 *
 * Displays a drawer with waterfall timeline visualization
 * for a specific operation, showing the flow of events
 * across services.
 *
 * Fetches timeline data from:
 * POST /api/v2/operations/get-operation-timeline/
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { Spin, Empty, Statistic, Row, Col, Alert, Grid, List, Tag, Typography, Space } from 'antd'
import {
  ClockCircleOutlined,
  NodeIndexOutlined,
  FieldTimeOutlined,
} from '@ant-design/icons'
import axios from 'axios'
import { apiClient } from '../../api/client'
import { DrawerSurfaceShell } from '../platform'
import type { OperationTimelineResponse } from '../../types/operationTimeline'
import { formatDuration, formatTimestamp, getEventStatus, transformToWaterfallItems } from '../../utils/timelineTransforms'
import WaterfallTimeline from './WaterfallTimeline'
import './OperationTimelineDrawer.css'

const { useBreakpoint } = Grid
const STATUS_COLORS = {
  received: 'blue',
  processing: 'gold',
  completed: 'green',
  failed: 'red',
  unknown: 'default',
} as const

interface OperationTimelineDrawerProps {
  operationId: string | null
  visible: boolean
  onClose: () => void
}

const OperationTimelineDrawer: React.FC<OperationTimelineDrawerProps> = ({
  operationId,
  visible,
  onClose,
}) => {
  const screens = useBreakpoint()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [timelineData, setTimelineData] = useState<OperationTimelineResponse | null>(null)
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.md
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < 768
        : false
    )

  /**
   * Fetch timeline data from API
   */
  const fetchTimeline = useCallback(async (opId: string) => {
    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.post<OperationTimelineResponse>(
        '/api/v2/operations/get-operation-timeline/',
        { operation_id: opId },
        { skipGlobalError: true }
      )

      setTimelineData(response.data)
    } catch (err) {
      console.error('Failed to fetch operation timeline:', err)

      // Extract error message
      let errorMessage = 'Failed to load timeline data'
      if (axios.isAxiosError(err)) {
        const data = err.response?.data
        // Support both formats: { error: "msg" } and { error: { code, message } }
        if (typeof data?.error === 'object' && data?.error?.message) {
          errorMessage = data.error.message
        } else if (typeof data?.error === 'string') {
          errorMessage = data.error
        } else if (data?.detail) {
          errorMessage = data.detail
        } else {
          errorMessage = err.message
        }
      } else if (err instanceof Error) {
        errorMessage = err.message
      }

      setError(errorMessage)
      setTimelineData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch data when drawer opens with an operation ID
  useEffect(() => {
    if (visible && operationId) {
      fetchTimeline(operationId)
    }
  }, [visible, operationId, fetchTimeline])

  // Reset state when drawer closes
  useEffect(() => {
    if (!visible) {
      setTimelineData(null)
      setError(null)
    }
  }, [visible])

  // Memoize transformed waterfall items
  const waterfallItems = useMemo(
    () => timelineData ? transformToWaterfallItems(timelineData.timeline) : [],
    [timelineData]
  )

  const highlightThresholdMs = useMemo(() => {
    if (!waterfallItems.length) return undefined
    const durations = waterfallItems
      .map((item) => item.duration)
      .filter((value) => value > 0)
      .sort((a, b) => a - b)
    if (durations.length === 0) return undefined
    const index = Math.floor(durations.length * 0.9)
    return durations[Math.min(index, durations.length - 1)]
  }, [waterfallItems])

  // Memoize unique services count
  const uniqueServicesCount = useMemo(
    () => timelineData ? new Set(timelineData.timeline.map((e) => e.service)).size : 0,
    [timelineData]
  )

  const timelineMeta = useMemo(() => {
    if (!timelineData?.timeline?.length) {
      return {
        traceId: undefined,
        workflowExecutionId: undefined,
        nodeId: undefined,
        rootOperationId: undefined,
        executionConsumer: undefined,
        lane: undefined,
      }
    }
    for (const event of timelineData.timeline) {
      if (
        event.trace_id ||
        event.workflow_execution_id ||
        event.node_id ||
        event.root_operation_id ||
        event.execution_consumer ||
        event.lane
      ) {
        return {
          traceId: event.trace_id || undefined,
          workflowExecutionId: event.workflow_execution_id || undefined,
          nodeId: event.node_id || undefined,
          rootOperationId: event.root_operation_id || undefined,
          executionConsumer: event.execution_consumer || undefined,
          lane: event.lane || undefined,
        }
      }
    }
    return {
      traceId: undefined,
      workflowExecutionId: undefined,
      nodeId: undefined,
      rootOperationId: undefined,
      executionConsumer: undefined,
      lane: undefined,
    }
  }, [timelineData])

  /**
   * Format operation ID for display (truncate if needed)
   */
  const formatOperationId = (id: string): string => {
    if (id.length <= 12) return id
    return `${id.slice(0, 8)}\u2026${id.slice(-4)}`
  }

  return (
    <DrawerSurfaceShell
      open={visible}
      onClose={onClose}
      width={600}
      drawerTestId="service-mesh-operation-timeline-drawer"
      title={
        <div className="operation-timeline-drawer__title">
          <NodeIndexOutlined />
          <span>Operation Timeline</span>
          {operationId && (
            <code className="operation-timeline-drawer__id">
              {formatOperationId(operationId)}
            </code>
          )}
        </div>
      }
    >
      <div className="operation-timeline-drawer">
        {/* Loading state */}
        {loading && (
          <div className="operation-timeline-drawer__loading">
            <Spin size="large" tip="Loading timeline\u2026">
              <div style={{ minHeight: 200 }} />
            </Spin>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <Alert
            message="Error Loading Timeline"
            description={error}
            type="error"
            showIcon
            className="operation-timeline-drawer__error"
          />
        )}

        {/* Content */}
        {!loading && !error && timelineData && (
          <>
            <div style={{ marginBottom: 12 }}>
              <Space size="middle" wrap>
                <Typography.Text type="secondary">Operation ID:</Typography.Text>
                {operationId && (
                  <Typography.Text
                    code
                    copyable={{ text: operationId }}
                    style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}
                  >
                    {operationId}
                  </Typography.Text>
                )}
              </Space>
            </div>
            {/* Summary statistics */}
            <div className="operation-timeline-drawer__summary">
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={8}>
                  <Statistic
                    title="Total Duration"
                    value={
                      timelineData.duration_ms !== null
                        ? formatDuration(timelineData.duration_ms)
                        : 'In Progress'
                    }
                    prefix={<ClockCircleOutlined />}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Col>
                <Col xs={24} sm={8}>
                  <Statistic
                    title="Events"
                    value={timelineData.total_events}
                    prefix={<FieldTimeOutlined />}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Col>
                <Col xs={24} sm={8}>
                  <Statistic
                    title="Services"
                    value={uniqueServicesCount}
                    prefix={<NodeIndexOutlined />}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Col>
              </Row>
              {(
                timelineMeta.traceId ||
                timelineMeta.workflowExecutionId ||
                timelineMeta.nodeId ||
                timelineMeta.rootOperationId ||
                timelineMeta.executionConsumer ||
                timelineMeta.lane
              ) && (
                <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {timelineMeta.traceId && <Tag>Trace: {timelineMeta.traceId.slice(0, 8)}{'\u2026'}</Tag>}
                  {timelineMeta.workflowExecutionId && (
                    <Tag>Workflow: {timelineMeta.workflowExecutionId.slice(0, 8)}{'\u2026'}</Tag>
                  )}
                  {timelineMeta.nodeId && <Tag>Node: {timelineMeta.nodeId}</Tag>}
                  {timelineMeta.rootOperationId && (
                    <Tag>Root: {timelineMeta.rootOperationId.slice(0, 8)}{'\u2026'}</Tag>
                  )}
                  {timelineMeta.executionConsumer && (
                    <Tag>Consumer: {timelineMeta.executionConsumer}</Tag>
                  )}
                  {timelineMeta.lane && <Tag>Lane: {timelineMeta.lane}</Tag>}
                </div>
              )}
            </div>

            {/* Waterfall timeline */}
            {waterfallItems.length > 0 ? (
              <div className="operation-timeline-drawer__timeline">
                {isNarrow ? (
                  <List
                    className="operation-timeline-drawer__event-list"
                    size="small"
                    dataSource={waterfallItems}
                    renderItem={(item) => {
                      const status = getEventStatus(item.event)
                      return (
                        <List.Item>
                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            <Space wrap size={[8, 8]}>
                              <Typography.Text strong>{item.eventLabel}</Typography.Text>
                              <Tag color={STATUS_COLORS[status]}>{status}</Tag>
                              <Typography.Text type="secondary">{item.service}</Typography.Text>
                            </Space>
                            <Space wrap size={[8, 8]}>
                              <Typography.Text type="secondary">{formatTimestamp(item.timestamp)}</Typography.Text>
                              <Typography.Text type="secondary">Offset +{formatDuration(item.startOffset)}</Typography.Text>
                              <Typography.Text type="secondary">
                                Duration {item.duration > 0 ? formatDuration(item.duration) : '-'}
                              </Typography.Text>
                            </Space>
                            {Object.keys(item.metadata).length > 0 ? (
                              <Typography.Text
                                type="secondary"
                                style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}
                              >
                                {JSON.stringify(item.metadata)}
                              </Typography.Text>
                            ) : null}
                          </Space>
                        </List.Item>
                      )
                    }}
                  />
                ) : (
                  <WaterfallTimeline items={waterfallItems} highlightThresholdMs={highlightThresholdMs} />
                )}
              </div>
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="No timeline events recorded"
                className="operation-timeline-drawer__empty"
              />
            )}
          </>
        )}

        {/* Empty state when no operation selected */}
        {!loading && !error && !timelineData && !operationId && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Select an operation to view its timeline"
            className="operation-timeline-drawer__empty"
          />
        )}
      </div>
    </DrawerSurfaceShell>
  )
}

export default OperationTimelineDrawer
