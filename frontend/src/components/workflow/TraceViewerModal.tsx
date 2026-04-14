/**
 * TraceViewerModal - Modal for viewing Jaeger trace details.
 *
 * Features:
 * - Timeline view of all spans
 * - Service flow visualization
 * - Span details panel
 * - Direct link to Jaeger UI
 */

import { useState, useMemo, useEffect } from 'react'
import {
  Modal,
  Tabs,
  Typography,
  Tag,
  List,
  Card,
  Descriptions,
  Space,
  Button,
  Spin,
  Alert,
  Progress,
  Tooltip,
  Empty
} from 'antd'
import {
  ReloadOutlined,
  ExportOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  ApiOutlined
} from '@ant-design/icons'
import { useJaegerTraces } from '../../hooks/useJaegerTraces'
import { getJaegerTraceUrl, getJaegerSpanUrl } from '../../api/endpoints/jaeger'
import {
  getTimelineItems,
  getServiceSummaries,
  formatTraceDuration,
  type TraceSpan,
  type TimelineItem,
  type ServiceSummary
} from '../../types/tracing'
import { useLocaleFormatters, useWorkflowTranslation } from '../../i18n'
import './TraceViewerModal.css'

const { Text, Title } = Typography

interface TraceViewerModalProps {
  visible: boolean
  onClose: () => void
  traceId: string | null
  nodeId?: string  // Optional: highlight spans related to this node
  spanId?: string  // Optional: initially selected span
}

const statusColors = {
  ok: '#52c41a',
  error: '#ff4d4f',
  unset: '#d9d9d9'
}

const statusIcons = {
  ok: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  error: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
  unset: <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
}

export const TraceViewerModal = ({
  visible,
  onClose,
  traceId,
  nodeId: _nodeId,  // Reserved for future use: highlighting spans related to workflow node
  spanId
}: TraceViewerModalProps) => {
  // _nodeId can be used in future to filter/highlight spans by workflow node
  void _nodeId  // Suppress unused variable warning
  const { t } = useWorkflowTranslation()
  const formatters = useLocaleFormatters()
  const { trace, isLoading, error, refresh } = useJaegerTraces(visible ? traceId : null)
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null)
  const [activeTab, setActiveTab] = useState<string>('timeline')

  // Get timeline items
  const timelineItems = useMemo(() => {
    if (!trace) return []
    return getTimelineItems(trace)
  }, [trace])

  // Get service summaries
  const serviceSummaries = useMemo(() => {
    if (!trace) return []
    return getServiceSummaries(trace)
  }, [trace])

  // Find and set initial selected span
  useEffect(() => {
    if (trace && spanId) {
      const span = trace.spans.find(s => s.spanId === spanId)
      if (span) {
        setSelectedSpan(span)
        setActiveTab('details')
      }
    }
  }, [trace, spanId])

  // Handle span selection
  const handleSpanSelect = (item: TimelineItem) => {
    const span = trace?.spans.find(s => s.spanId === item.spanId)
    if (span) {
      setSelectedSpan(span)
      setActiveTab('details')
    }
  }

  // Render timeline tab
  const renderTimeline = () => {
    if (!trace || timelineItems.length === 0) {
      return <Empty description={t('traceViewer.emptySpans')} />
    }

    const maxDuration = Math.max(...timelineItems.map(i => i.startOffset + i.duration))

    return (
      <div className="trace-timeline">
        <div className="timeline-header">
          <Text type="secondary">
            {t('traceViewer.header.spansAcross', {
              spans: trace.spanCount,
              services: trace.services.length,
            })}
          </Text>
          <Text type="secondary">
            {t('traceViewer.header.totalDuration', { value: formatTraceDuration(trace.duration) })}
          </Text>
        </div>

        <List
          dataSource={timelineItems}
          renderItem={(item) => {
            const startPercent = (item.startOffset / maxDuration) * 100
            const widthPercent = Math.max((item.duration / maxDuration) * 100, 0.5)
            const isSelected = selectedSpan?.spanId === item.spanId

            return (
              <List.Item
                className={`timeline-item ${isSelected ? 'selected' : ''}`}
                onClick={() => handleSpanSelect(item)}
                style={{ paddingLeft: item.depth * 16 }}
              >
                <div className="timeline-row">
                  <div className="timeline-info">
                    <div className="span-operation">
                      {statusIcons[item.status]}
                      <Text strong className="operation-name">
                        {item.operationName}
                      </Text>
                    </div>
                    <Tag color="blue" className="service-tag">
                      {item.serviceName}
                    </Tag>
                  </div>

                  <div className="timeline-bar-container">
                    <Tooltip title={`${formatTraceDuration(item.duration)}`}>
                      <div
                        className="timeline-bar"
                        style={{
                          left: `${startPercent}%`,
                          width: `${widthPercent}%`,
                          backgroundColor: statusColors[item.status]
                        }}
                      />
                    </Tooltip>
                  </div>

                  <div className="timeline-duration">
                    <Text type="secondary">{formatTraceDuration(item.duration)}</Text>
                  </div>
                </div>
              </List.Item>
            )
          }}
        />
      </div>
    )
  }

  // Render service flow tab
  const renderServiceFlow = () => {
    if (!trace || serviceSummaries.length === 0) {
      return <Empty description={t('traceViewer.emptyServices')} />
    }

    return (
      <div className="service-flow">
        {serviceSummaries.map((service) => (
          <ServiceCard key={service.serviceName} service={service} trace={trace} />
        ))}
      </div>
    )
  }

  // Render span details tab
  const renderSpanDetails = () => {
    if (!selectedSpan) {
      return (
        <Empty
          description={t('traceViewer.emptySpanDetails')}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )
    }

    const tagEntries = Object.entries(selectedSpan.tags)

    return (
      <div className="span-details">
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label={t('traceViewer.details.operation')}>
            {selectedSpan.operationName}
          </Descriptions.Item>
          <Descriptions.Item label={t('traceViewer.details.service')}>
            {selectedSpan.serviceName}
          </Descriptions.Item>
          <Descriptions.Item label={t('traceViewer.details.spanId')}>
            <Text copyable className="mono-text">{selectedSpan.spanId}</Text>
          </Descriptions.Item>
          {selectedSpan.parentSpanId && (
            <Descriptions.Item label={t('traceViewer.details.parentSpanId')}>
              <Text copyable className="mono-text">{selectedSpan.parentSpanId}</Text>
            </Descriptions.Item>
          )}
          <Descriptions.Item label={t('traceViewer.details.startTime')}>
            {formatters.dateTime(selectedSpan.startTime, { fallback: t('common.notAvailable') })}
          </Descriptions.Item>
          <Descriptions.Item label={t('traceViewer.details.duration')}>
            {formatTraceDuration(selectedSpan.duration)}
          </Descriptions.Item>
          <Descriptions.Item label={t('traceViewer.details.status')}>
            <Space>
              {statusIcons[selectedSpan.status]}
              <Text>{selectedSpan.status}</Text>
            </Space>
          </Descriptions.Item>
        </Descriptions>

        {tagEntries.length > 0 && (
          <Card title={t('traceViewer.details.tags')} size="small" className="detail-card">
            <div className="tags-list">
              {tagEntries.map(([key, value]) => (
                <div key={key} className="tag-item">
                  <Text type="secondary" className="tag-key">{key}:</Text>
                  <Text className="tag-value">{String(value)}</Text>
                </div>
              ))}
            </div>
          </Card>
        )}

        {selectedSpan.logs.length > 0 && (
          <Card title={t('traceViewer.details.logs')} size="small" className="detail-card">
            <List
              dataSource={selectedSpan.logs}
              renderItem={(log) => (
                <List.Item className="log-item">
                  <div>
                    <Text type="secondary">{formatters.time(log.timestamp, { fallback: t('common.notAvailable') })}</Text>
                    <Text strong style={{ marginLeft: 8 }}>{log.name}</Text>
                  </div>
                  <pre className="log-attributes">
                    {JSON.stringify(log.attributes, null, 2)}
                  </pre>
                </List.Item>
              )}
            />
          </Card>
        )}

        {trace && (
          <Button
            type="link"
            icon={<ExportOutlined />}
            href={getJaegerSpanUrl(trace.traceId, selectedSpan.spanId)}
            target="_blank"
            className="view-in-jaeger"
          >
            {t('traceViewer.details.viewInJaeger')}
          </Button>
        )}
      </div>
    )
  }

  return (
    <Modal
      title={
        <Space>
          <ApiOutlined />
          <span>{t('traceViewer.title')}</span>
          {trace && (
            <Text type="secondary" className="trace-id-header">
              {trace.traceId.slice(0, 16)}{'\u2026'}
            </Text>
          )}
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={900}
      footer={null}
      className="trace-viewer-modal"
    >
      {isLoading && (
        <div className="trace-loading">
          <Spin size="large" tip={t('traceViewer.header.loadTrace')}>
            <div style={{ minHeight: 200 }} />
          </Spin>
        </div>
      )}

      {error && (
        <Alert
          type="error"
          message={t('traceViewer.header.failedToLoad')}
          description={error}
          showIcon
          action={
            <Button size="small" onClick={refresh}>
              {t('traceViewer.header.retry')}
            </Button>
          }
        />
      )}

      {trace && !isLoading && (
        <>
          <div className="trace-header">
            <div className="trace-stats">
              <Space size="large">
                <div className="stat">
                  <Text type="secondary">{t('traceViewer.header.duration')}</Text>
                  <Title level={5}>{formatTraceDuration(trace.duration)}</Title>
                </div>
                <div className="stat">
                  <Text type="secondary">{t('traceViewer.header.spans')}</Text>
                  <Title level={5}>{trace.spanCount}</Title>
                </div>
                <div className="stat">
                  <Text type="secondary">{t('traceViewer.header.services')}</Text>
                  <Title level={5}>{trace.services.length}</Title>
                </div>
                {trace.errorCount > 0 && (
                  <div className="stat error">
                    <Text type="secondary">{t('traceViewer.header.errors')}</Text>
                    <Title level={5} style={{ color: '#ff4d4f' }}>
                      {trace.errorCount}
                    </Title>
                  </div>
                )}
              </Space>
            </div>

            <Space>
              <Button icon={<ReloadOutlined />} onClick={refresh}>
                {t('traceViewer.header.refresh')}
              </Button>
              <Button
                icon={<ExportOutlined />}
                onClick={() => {
                  window.open(
                    getJaegerTraceUrl(trace.traceId),
                    '_blank',
                    'noopener,noreferrer'
                  )
                }}
              >
                {t('traceViewer.header.openInJaeger')}
              </Button>
            </Space>
          </div>

          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'timeline',
                label: (
                  <span>
                    <ClockCircleOutlined />
                    {t('traceViewer.tabs.timeline')}
                  </span>
                ),
                children: renderTimeline()
              },
              {
                key: 'services',
                label: (
                  <span>
                    <ApiOutlined />
                    {t('traceViewer.tabs.services')}
                  </span>
                ),
                children: renderServiceFlow()
              },
              {
                key: 'details',
                label: (
                  <span>
                    <InfoCircleOutlined />
                    {t('traceViewer.tabs.details')}
                  </span>
                ),
                children: renderSpanDetails()
              }
            ]}
          />
        </>
      )}
    </Modal>
  )
}

// Service Card component
interface ServiceCardProps {
  service: ServiceSummary
  trace: { duration: number }
}

const ServiceCard = ({ service, trace }: ServiceCardProps) => {
  const { t } = useWorkflowTranslation()
  const percentOfTrace = Math.round((service.totalDuration / trace.duration) * 100)

  return (
    <Card className="service-card" size="small">
      <div className="service-header">
        <Title level={5} className="service-name">{service.serviceName}</Title>
        {service.errorCount > 0 && (
          <Tag color="error">{t('traceViewer.serviceCard.errors', { count: service.errorCount })}</Tag>
        )}
      </div>

      <div className="service-stats">
        <div className="service-stat">
          <Text type="secondary">{t('traceViewer.serviceCard.spans')}</Text>
          <Text strong>{service.spanCount}</Text>
        </div>
        <div className="service-stat">
          <Text type="secondary">{t('traceViewer.serviceCard.time')}</Text>
          <Text strong>{formatTraceDuration(service.totalDuration)}</Text>
        </div>
      </div>

      <div className="service-time-bar">
        <Progress
          percent={percentOfTrace}
          size="small"
          status={service.errorCount > 0 ? 'exception' : 'normal'}
          format={() => `${percentOfTrace}%`}
        />
      </div>

      <div className="service-operations">
        <Text type="secondary">{t('traceViewer.serviceCard.operations')}</Text>
        <div className="operations-list">
          {service.operations.map(op => (
            <Tag key={op} className="operation-tag">{op}</Tag>
          ))}
        </div>
      </div>
    </Card>
  )
}

export default TraceViewerModal
