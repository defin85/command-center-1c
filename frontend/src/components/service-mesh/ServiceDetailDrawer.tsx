/**
 * Service detail drawer component.
 *
 * Displays:
 * - Service name and status
 * - Current metrics cards
 * - Historical chart (30 min)
 * - Recent operations for this service
 */
import React, { useState, useEffect, useCallback } from 'react'
import { Button, Card, Statistic, Row, Col, Spin, Empty } from 'antd'
import {
  LineChartOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  HistoryOutlined,
} from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type {
  ServiceMetrics,
  HistoricalDataPoint,
} from '../../types/serviceMesh'
import {
  STATUS_COLORS,
} from '../../types/serviceMesh'
import { getV2 } from '../../api/generated'
import { useLocaleFormatters, useServiceMeshTranslation } from '../../i18n'
import { transformServiceHistoryResponse } from '../../utils/serviceMeshTransforms'
import { DrawerSurfaceShell, RouteButton } from '../platform'
import './ServiceDetailDrawer.css'

const api = getV2()

interface ServiceDetailDrawerProps {
  service: ServiceMetrics | null
  visible: boolean
  onClose: () => void
}

const ServiceDetailDrawer: React.FC<ServiceDetailDrawerProps> = ({
  service,
  visible,
  onClose,
}) => {
  const { t } = useServiceMeshTranslation()
  const formatters = useLocaleFormatters()
  const [historicalData, setHistoricalData] = useState<HistoricalDataPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedMinutes, setSelectedMinutes] = useState(30)

  const fetchHistoricalData = useCallback(async () => {
    if (!service) return

    setLoading(true)
    try {
      const rawResponse = await api.getServiceMeshGetHistory({
        service: service.name,
        minutes: selectedMinutes,
      })
      const response = transformServiceHistoryResponse(rawResponse)
      setHistoricalData(response.dataPoints)
    } catch (error) {
      console.error('Failed to fetch historical data:', error)
      setHistoricalData([])
    } finally {
      setLoading(false)
    }
  }, [service, selectedMinutes])

  // Fetch historical data when service changes
  useEffect(() => {
    if (service && visible) {
      fetchHistoricalData()
    }
  }, [service, visible, fetchHistoricalData])

  if (!service) {
    return null
  }

  const serviceDescriptions = {
    frontend: t(($) => $.services.frontend.description),
    'api-gateway': t(($) => $.services.apiGateway.description),
    orchestrator: t(($) => $.services.orchestrator.description),
    worker: t(($) => $.services.worker.description),
    'worker-workflows': t(($) => $.services.workerWorkflows.description),
    'ras-server': t(($) => $.services.rasServer.description),
    postgresql: t(($) => $.services.postgresql.description),
    redis: t(($) => $.services.redis.description),
    minio: t(($) => $.services.minio.description),
    'event-subscriber': t(($) => $.services.eventSubscriber.description),
    'pool-outbox-dispatcher': t(($) => $.services.poolOutboxDispatcher.description),
  } as const
  const description = serviceDescriptions[service.name as keyof typeof serviceDescriptions]
    ?? t(($) => $.serviceDetail.fallbackDescription)

  // Prepare chart data
  const chartData = historicalData.map((point) => ({
    time: formatters.time(point.timestamp, {
      hour: '2-digit',
      minute: '2-digit',
      fallback: '',
    }),
    opsPerMinute: point.opsPerMinute,
    p95LatencyMs: point.p95LatencyMs,
    errorRate: point.errorRate * 100, // Convert to percentage
  }))

  return (
    <DrawerSurfaceShell
      open={visible}
      onClose={onClose}
      width={500}
      drawerTestId="service-mesh-service-drawer"
      title={
        <div className="service-detail-drawer__title">
          <span
            className="service-detail-drawer__status-dot"
            style={{ backgroundColor: STATUS_COLORS[service.status] }}
          />
          <span className="service-detail-drawer__name">
            {service.displayName}
          </span>
          <span className="service-detail-drawer__status-text">
            {t(($) => $.status[service.status])}
          </span>
        </div>
      }
    >
      <div className="service-detail-drawer">
        {/* Description */}
        <p className="service-detail-drawer__description">{description}</p>

      {/* Current Metrics */}
      <Card size="small" className="service-detail-drawer__metrics">
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title={t(($) => $.serviceDetail.opsPerMinute)}
              value={service.opsPerMinute}
              precision={1}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title={t(($) => $.serviceDetail.p95Latency)}
              value={service.p95LatencyMs}
              suffix="ms"
              precision={0}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title={t(($) => $.serviceDetail.errorRate)}
              value={service.errorRate * 100}
              suffix="%"
              precision={2}
              prefix={<WarningOutlined />}
              valueStyle={{
                fontSize: 18,
                color: service.errorRate > 0.01 ? STATUS_COLORS.critical : undefined,
              }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title={t(($) => $.serviceDetail.active)}
              value={service.activeOperations}
              prefix={<HistoryOutlined />}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
        </Row>
      </Card>

      {/* Historical Chart */}
      <Card
        size="small"
        className="service-detail-drawer__chart-card"
        title={
          <div className="service-detail-drawer__chart-header">
            <LineChartOutlined /> {t(($) => $.serviceDetail.historicalMetrics)}
          </div>
        }
        extra={
          <div className="service-detail-drawer__time-range">
            {[15, 30, 60].map((minutes) => (
              <Button
                key={minutes}
                size="small"
                type={selectedMinutes === minutes ? 'primary' : 'default'}
                onClick={() => setSelectedMinutes(minutes)}
              >
                {t(($) => $.serviceDetail.minutesShort, { count: minutes })}
              </Button>
            ))}
          </div>
        }
      >
        {loading ? (
          <div className="service-detail-drawer__loading">
            <Spin />
          </div>
        ) : chartData.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t(($) => $.serviceDetail.noHistoricalData)}
          />
        ) : (
          <div className="service-detail-drawer__chart">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 10 }}
                  stroke="#8c8c8c"
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 10 }}
                  stroke="#1890ff"
                  label={{
                    value: t(($) => $.serviceDetail.opsPerMinute),
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 10, fill: '#1890ff' },
                  }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 10 }}
                  stroke="#52c41a"
                  label={{
                    value: `${t(($) => $.serviceDetail.p95Latency)} (ms)`,
                    angle: 90,
                    position: 'insideRight',
                    style: { fontSize: 10, fill: '#52c41a' },
                  }}
                />
                <RechartsTooltip
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 4,
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11 }}
                  iconSize={10}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="opsPerMinute"
                  name={t(($) => $.serviceDetail.opsPerMinute)}
                  stroke="#1890ff"
                  dot={false}
                  strokeWidth={2}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="p95LatencyMs"
                  name={t(($) => $.serviceDetail.p95Latency)}
                  stroke="#52c41a"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>

            {/* Error rate chart (separate, smaller) */}
            <div className="service-detail-drawer__error-chart">
              <div className="service-detail-drawer__error-chart-title">
                {t(($) => $.serviceDetail.errorRateChartTitle)}
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tick={false} />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    stroke="#ff4d4f"
                    domain={[0, 'auto']}
                  />
                  <Line
                    type="monotone"
                    dataKey="errorRate"
                    stroke="#ff4d4f"
                    fill="#fff1f0"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </Card>

      {/* View All Operations Button */}
      <RouteButton
        className="service-detail-drawer__view-all"
        to={`/operations?service=${service.name}`}
      >
        {t(($) => $.serviceDetail.viewAllOperations, { service: service.displayName })}
      </RouteButton>
      </div>
    </DrawerSurfaceShell>
  )
}

export default ServiceDetailDrawer
