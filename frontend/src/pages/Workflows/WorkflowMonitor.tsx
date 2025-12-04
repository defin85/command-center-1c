/**
 * WorkflowMonitor - Page for monitoring workflow execution in real-time.
 *
 * Features:
 * - Real-time status updates via WebSocket
 * - Visual DAG with node status highlighting
 * - Execution timeline
 * - Node output/error details
 * - Trace viewer integration
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Layout,
  Typography,
  Button,
  Space,
  Card,
  Descriptions,
  Progress,
  Tag,
  Timeline,
  Spin,
  Alert,
  Drawer,
  Result,
  Badge,
  Tooltip,
  Statistic,
  Row,
  Col
} from 'antd'
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  StopOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  ExportOutlined
} from '@ant-design/icons'
import { WorkflowCanvas } from '../../components/workflow'
import { TraceViewerModal } from '../../components/workflow/TraceViewerModal'
import { useWorkflowExecution, type NodeStatus, type WorkflowStatusType } from '../../hooks/useWorkflowExecution'
import type { DAGStructure, WorkflowExecution } from '../../types/workflow'
import { getWorkflowExecution, cancelWorkflowExecution, getWorkflowTemplate } from '../../api/endpoints/workflows'
import './WorkflowMonitor.css'

// v2 migration: использовать env variable для Jaeger UI
const JAEGER_UI_URL = import.meta.env.VITE_JAEGER_UI_URL || 'http://localhost:16686'

const { Header, Content, Sider } = Layout
const { Title, Text } = Typography

interface NodeDetails {
  nodeId: string
  nodeName: string
  status: NodeStatus
}

const statusColors: Record<WorkflowStatusType, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning'
}

const statusIcons: Record<WorkflowStatusType, React.ReactNode> = {
  pending: <ClockCircleOutlined />,
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
  cancelled: <MinusCircleOutlined />
}

const WorkflowMonitor = () => {
  const { executionId } = useParams<{ executionId: string }>()
  const navigate = useNavigate()

  // Execution data from API (initial load)
  const [execution, setExecution] = useState<WorkflowExecution | null>(null)
  const [dagStructure, setDagStructure] = useState<DAGStructure | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isCancelling, setIsCancelling] = useState(false)

  // Selected node for details drawer
  const [selectedNode, setSelectedNode] = useState<NodeDetails | null>(null)
  const [drawerVisible, setDrawerVisible] = useState(false)

  // Trace viewer modal state
  const [traceModalVisible, setTraceModalVisible] = useState(false)
  const [traceNodeId, setTraceNodeId] = useState<string | undefined>()

  // Real-time updates from WebSocket
  const {
    status: liveStatus,
    progress: liveProgress,
    currentNodeId,
    traceId,
    errorMessage: liveError,
    result: liveResult,
    nodeStatuses,
    isConnected,
    connectionError,
    reconnectAttempts
  } = useWorkflowExecution(executionId || null)

  // Load execution and template data
  useEffect(() => {
    const loadData = async () => {
      if (!executionId) {
        setError('Execution ID not provided')
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        const execData = await getWorkflowExecution(executionId)
        setExecution(execData)

        // Load template for DAG structure
        const template = await getWorkflowTemplate(execData.workflow_template)
        setDagStructure(template.dag_structure)

        setError(null)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load execution data')
      } finally {
        setIsLoading(false)
      }
    }

    loadData()
  }, [executionId])

  // Handle node selection
  const handleNodeSelect = useCallback((nodeId: string | null) => {
    if (!nodeId || !dagStructure) {
      setSelectedNode(null)
      setDrawerVisible(false)
      return
    }

    const node = dagStructure.nodes.find(n => n.id === nodeId)
    const nodeStatus = nodeStatuses[nodeId]

    if (node) {
      setSelectedNode({
        nodeId,
        nodeName: node.name,
        status: nodeStatus || {
          nodeId,
          status: 'pending'
        }
      })
      setDrawerVisible(true)
    }
  }, [dagStructure, nodeStatuses])

  // Cancel execution
  const handleCancel = async () => {
    if (!executionId) return

    try {
      setIsCancelling(true)
      await cancelWorkflowExecution(executionId)
    } catch (err: any) {
      console.error('Failed to cancel execution:', err)
    } finally {
      setIsCancelling(false)
    }
  }

  // Refresh execution data
  const handleRefresh = async () => {
    if (!executionId) return

    try {
      const execData = await getWorkflowExecution(executionId)
      setExecution(execData)
    } catch (err: any) {
      console.error('Failed to refresh:', err)
    }
  }

  // Convert nodeStatuses to format expected by WorkflowCanvas
  const canvasNodeStatuses = Object.fromEntries(
    Object.entries(nodeStatuses).map(([id, status]) => [
      id,
      {
        status: status.status,
        output: status.output,
        error: status.error,
        durationMs: status.durationMs
      }
    ])
  )

  // Use live status if connected, otherwise use from execution
  const displayStatus = isConnected ? liveStatus : (execution?.status || 'pending')
  const displayProgress = isConnected ? liveProgress : (execution?.progress_percent || 0) / 100
  const displayError = isConnected ? liveError : execution?.error_message

  // Build timeline items from node statuses
  const timelineItems = Object.values(nodeStatuses)
    .filter(ns => ns.status !== 'pending')
    .sort((a, b) => {
      if (a.startedAt && b.startedAt) {
        return new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime()
      }
      return 0
    })
    .map(ns => {
      const node = dagStructure?.nodes.find(n => n.id === ns.nodeId)
      const nodeName = node?.name || ns.nodeId

      let color = 'gray'
      let dot = <ClockCircleOutlined />

      switch (ns.status) {
        case 'running':
          color = 'blue'
          dot = <LoadingOutlined spin />
          break
        case 'completed':
          color = 'green'
          dot = <CheckCircleOutlined />
          break
        case 'failed':
          color = 'red'
          dot = <CloseCircleOutlined />
          break
        case 'skipped':
          color = 'orange'
          dot = <MinusCircleOutlined />
          break
      }

      return {
        key: ns.nodeId,
        color,
        dot,
        children: (
          <div className="timeline-item" onClick={() => handleNodeSelect(ns.nodeId)}>
            <Text strong>{nodeName}</Text>
            <Text type="secondary" style={{ marginLeft: 8 }}>
              {ns.status}
            </Text>
            {ns.durationMs !== undefined && (
              <Text type="secondary" style={{ marginLeft: 8 }}>
                ({(ns.durationMs / 1000).toFixed(2)}s)
              </Text>
            )}
          </div>
        )
      }
    })

  if (isLoading) {
    return (
      <div className="workflow-monitor-loading">
        <Spin size="large" tip="Loading execution...">
          <div style={{ minHeight: 200 }} />
        </Spin>
      </div>
    )
  }

  if (error) {
    return (
      <Result
        status="error"
        title="Failed to Load Execution"
        subTitle={error}
        extra={
          <Button type="primary" onClick={() => navigate('/workflows/executions')}>
            Back to Executions
          </Button>
        }
      />
    )
  }

  const isTerminal = ['completed', 'failed', 'cancelled'].includes(displayStatus)

  return (
    <Layout className="workflow-monitor">
      {/* Header */}
      <Header className="monitor-header">
        <div className="header-left">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/workflows/executions')}
          >
            Back
          </Button>
          <Title level={4} className="header-title">
            Workflow Execution
            <Tag color={statusColors[displayStatus]} style={{ marginLeft: 12 }}>
              {statusIcons[displayStatus]} {displayStatus.toUpperCase()}
            </Tag>
          </Title>
        </div>
        <Space className="header-actions">
          <Badge
            status={isConnected ? 'success' : 'error'}
            text={isConnected ? 'Connected' : 'Disconnected'}
          />
          {connectionError && (
            <Tooltip title={connectionError}>
              <Text type="danger">
                (Retry: {reconnectAttempts})
              </Text>
            </Tooltip>
          )}
          <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
            Refresh
          </Button>
          {!isTerminal && (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={handleCancel}
              loading={isCancelling}
            >
              Cancel
            </Button>
          )}
          {traceId && (
            <Tooltip title="View trace in Jaeger">
              <Button
                icon={<ExportOutlined />}
                href={`${JAEGER_UI_URL}/trace/${traceId}`}
                target="_blank"
              >
                View Trace
              </Button>
            </Tooltip>
          )}
        </Space>
      </Header>

      <Layout className="monitor-body">
        {/* Main Content - Canvas */}
        <Content className="monitor-content">
          {/* Progress bar */}
          <div className="progress-section">
            <Progress
              percent={Math.round(displayProgress * 100)}
              status={
                displayStatus === 'failed' ? 'exception' :
                displayStatus === 'completed' ? 'success' :
                'active'
              }
              strokeColor={{
                '0%': '#108ee9',
                '100%': '#87d068'
              }}
            />
          </div>

          {/* Error alert */}
          {displayError && (
            <Alert
              type="error"
              message="Execution Error"
              description={displayError}
              showIcon
              className="error-alert"
            />
          )}

          {/* Result alert */}
          {displayStatus === 'completed' && liveResult && (
            <Alert
              type="success"
              message="Execution Completed"
              description={
                <pre className="result-json">
                  {JSON.stringify(liveResult, null, 2)}
                </pre>
              }
              showIcon
              className="result-alert"
            />
          )}

          {/* Canvas */}
          {dagStructure && (
            <WorkflowCanvas
              dagStructure={dagStructure}
              mode="monitor"
              onNodeSelect={handleNodeSelect}
              nodeStatuses={canvasNodeStatuses}
              currentNodeId={currentNodeId}
            />
          )}
        </Content>

        {/* Right Sider - Info & Timeline */}
        <Sider width={320} className="monitor-sider">
          <Card title="Execution Info" size="small" className="info-card">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="ID">
                <Text copyable className="mono-text">
                  {executionId?.slice(0, 8)}...
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="Template">
                <Link to={`/workflows/${execution?.workflow_template}`}>
                  {execution?.workflow_template_name || 'Unknown'}
                </Link>
              </Descriptions.Item>
              <Descriptions.Item label="Started">
                {execution?.started_at
                  ? new Date(execution.started_at).toLocaleString()
                  : 'Not started'}
              </Descriptions.Item>
              {execution?.completed_at && (
                <Descriptions.Item label="Completed">
                  {new Date(execution.completed_at).toLocaleString()}
                </Descriptions.Item>
              )}
              {traceId && (
                <Descriptions.Item label="Trace ID">
                  <Text copyable className="mono-text">
                    {traceId.slice(0, 8)}...
                  </Text>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          <Card title="Statistics" size="small" className="stats-card">
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Statistic
                  title="Completed"
                  value={Object.values(nodeStatuses).filter(n => n.status === 'completed').length}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="Failed"
                  value={Object.values(nodeStatuses).filter(n => n.status === 'failed').length}
                  valueStyle={{ color: '#ff4d4f' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="Running"
                  value={Object.values(nodeStatuses).filter(n => n.status === 'running').length}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="Total"
                  value={dagStructure?.nodes.length || 0}
                />
              </Col>
            </Row>
          </Card>

          <Card title="Timeline" size="small" className="timeline-card">
            {timelineItems.length > 0 ? (
              <Timeline items={timelineItems} />
            ) : (
              <Text type="secondary">No activity yet</Text>
            )}
          </Card>
        </Sider>
      </Layout>

      {/* Node Details Drawer */}
      <Drawer
        title={selectedNode?.nodeName || 'Node Details'}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        width={400}
      >
        {selectedNode && (
          <div className="node-details">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Node ID">
                <Text copyable className="mono-text">
                  {selectedNode.nodeId}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <Tag color={
                  selectedNode.status.status === 'completed' ? 'success' :
                  selectedNode.status.status === 'failed' ? 'error' :
                  selectedNode.status.status === 'running' ? 'processing' :
                  selectedNode.status.status === 'skipped' ? 'warning' :
                  'default'
                }>
                  {selectedNode.status.status}
                </Tag>
              </Descriptions.Item>
              {selectedNode.status.startedAt && (
                <Descriptions.Item label="Started">
                  {new Date(selectedNode.status.startedAt).toLocaleString()}
                </Descriptions.Item>
              )}
              {selectedNode.status.completedAt && (
                <Descriptions.Item label="Completed">
                  {new Date(selectedNode.status.completedAt).toLocaleString()}
                </Descriptions.Item>
              )}
              {selectedNode.status.durationMs !== undefined && (
                <Descriptions.Item label="Duration">
                  {(selectedNode.status.durationMs / 1000).toFixed(3)}s
                </Descriptions.Item>
              )}
              {selectedNode.status.spanId && (
                <Descriptions.Item label="Span ID">
                  <Text copyable className="mono-text">
                    {selectedNode.status.spanId}
                  </Text>
                </Descriptions.Item>
              )}
            </Descriptions>

            {selectedNode.status.output && (
              <Card title="Output" size="small" className="detail-card">
                <pre className="json-output">
                  {JSON.stringify(selectedNode.status.output, null, 2)}
                </pre>
              </Card>
            )}

            {selectedNode.status.error && (
              <Alert
                type="error"
                message="Error"
                description={selectedNode.status.error}
                showIcon
                className="error-detail"
              />
            )}

            {selectedNode.status.spanId && traceId && (
              <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
                <Button
                  type="primary"
                  icon={<LinkOutlined />}
                  onClick={() => {
                    setTraceNodeId(selectedNode.nodeId)
                    setTraceModalVisible(true)
                  }}
                  block
                >
                  View Trace Details
                </Button>
                <Button
                  type="link"
                  icon={<ExportOutlined />}
                  href={`${JAEGER_UI_URL}/trace/${traceId}?uiFind=${selectedNode.status.spanId}`}
                  target="_blank"
                  className="trace-link"
                >
                  Open in Jaeger
                </Button>
              </Space>
            )}
          </div>
        )}
      </Drawer>

      {/* Trace Viewer Modal */}
      <TraceViewerModal
        visible={traceModalVisible}
        onClose={() => {
          setTraceModalVisible(false)
          setTraceNodeId(undefined)
        }}
        traceId={traceId || null}
        nodeId={traceNodeId}
        spanId={traceNodeId ? nodeStatuses[traceNodeId]?.spanId : undefined}
      />
    </Layout>
  )
}

export default WorkflowMonitor
