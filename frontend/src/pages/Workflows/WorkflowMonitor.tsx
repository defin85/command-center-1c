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

import { useState, useEffect, useCallback, useMemo, type ReactNode } from 'react'
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom'
import {
  App,
  Alert,
  Badge,
  Button,
  Collapse,
  Descriptions,
  Progress,
  Result,
  Space,
  Spin,
  Timeline,
  Tooltip,
  Typography,
} from 'antd'
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ExportOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  ReloadOutlined,
  StopOutlined,
} from '@ant-design/icons'

import { WorkflowCanvas } from '../../components/workflow'
import { TraceViewerModal } from '../../components/workflow/TraceViewerModal'
import { useWorkflowExecution, type NodeStatus, type WorkflowStatusType } from '../../hooks/useWorkflowExecution'
import { getV2 } from '../../api/generated'
import { convertExecutionToLegacy, convertDAGToLegacy } from '../../utils/workflowTransforms'
import type { DAGStructure, WorkflowExecution } from '../../types/workflow'
import { useAuthz } from '../../authz/useAuthz'
import { NodeDetailsDrawer, type NodeDetails } from './components/NodeDetailsDrawer'
import {
  EntityDetails,
  JsonBlock,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { normalizeInternalReturnTo } from './routeState'
import './WorkflowMonitor.css'

const JAEGER_UI_URL = import.meta.env.VITE_JAEGER_UI_URL || 'http://localhost:16686'
const api = getV2()
const { Text } = Typography

const statusIcons: Record<WorkflowStatusType, ReactNode> = {
  pending: <ClockCircleOutlined />,
  running: <LoadingOutlined spin />,
  completed: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
  cancelled: <MinusCircleOutlined />,
}

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

type RawNodeStatus = {
  status?: unknown
  output?: unknown
  error?: unknown
  duration_ms?: unknown
  durationMs?: unknown
  span_id?: unknown
  spanId?: unknown
  started_at?: unknown
  startedAt?: unknown
  completed_at?: unknown
  completedAt?: unknown
}

const normalizeNodeStatuses = (value: unknown): Record<string, NodeStatus> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }

  const normalized: Record<string, NodeStatus> = {}

  Object.entries(value as Record<string, unknown>).forEach(([nodeId, rawStatus]) => {
    if (!rawStatus || typeof rawStatus !== 'object' || Array.isArray(rawStatus)) {
      return
    }

    const candidate = rawStatus as RawNodeStatus
    const status = typeof candidate.status === 'string'
      ? candidate.status
      : 'pending'

    normalized[nodeId] = {
      nodeId,
      status: status as NodeStatus['status'],
      output: candidate.output && typeof candidate.output === 'object'
        ? candidate.output as Record<string, unknown>
        : undefined,
      error: typeof candidate.error === 'string' && candidate.error.trim()
        ? candidate.error
        : undefined,
      durationMs: (() => {
        const parsed = Number(candidate.durationMs ?? candidate.duration_ms)
        return Number.isFinite(parsed) ? parsed : undefined
      })(),
      spanId: typeof candidate.spanId === 'string'
        ? candidate.spanId
        : typeof candidate.span_id === 'string'
          ? candidate.span_id
          : undefined,
      startedAt: typeof candidate.startedAt === 'string'
        ? candidate.startedAt
        : typeof candidate.started_at === 'string'
          ? candidate.started_at
          : undefined,
      completedAt: typeof candidate.completedAt === 'string'
        ? candidate.completedAt
        : typeof candidate.completed_at === 'string'
          ? candidate.completed_at
          : undefined,
    }
  })

  return normalized
}

const formatDateTime = (value: string | null | undefined) => (
  value ? new Date(value).toLocaleString() : 'Not available'
)

const formatDuration = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return `${value.toFixed(1)}s`
}

const WorkflowMonitor = () => {
  const { executionId } = useParams<{ executionId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const selectedNodeId = normalizeRouteParam(searchParams.get('node'))
  const returnToFromUrl = normalizeInternalReturnTo(searchParams.get('returnTo'))
  const backTarget = returnToFromUrl ?? '/workflows/executions'

  const [execution, setExecution] = useState<WorkflowExecution | null>(null)
  const [dagStructure, setDagStructure] = useState<DAGStructure | null>(null)
  const [executionPlan, setExecutionPlan] = useState<unknown | null>(null)
  const [executionBindings, setExecutionBindings] = useState<unknown | null>(null)
  const [initialNodeStatuses, setInitialNodeStatuses] = useState<Record<string, NodeStatus>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isCancelling, setIsCancelling] = useState(false)
  const [traceModalVisible, setTraceModalVisible] = useState(false)
  const [traceNodeId, setTraceNodeId] = useState<string | undefined>()

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
    reconnectAttempts,
  } = useWorkflowExecution(executionId || null)

  const updateParams = useCallback((
    updates: Record<string, string | null>,
    mode: 'push' | 'replace' = 'push',
  ) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) {
        next.delete(key)
      } else {
        next.set(key, value)
      }
    })
    if (next.toString() === searchParams.toString()) {
      return
    }
    setSearchParams(
      next,
      mode === 'replace'
        ? { replace: true }
        : undefined
    )
  }, [searchParams, setSearchParams])

  const loadData = useCallback(async () => {
    if (!executionId) {
      setError('Execution ID not provided')
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      const execResponse = await api.getWorkflowsGetExecution({ execution_id: executionId })
      const execData = convertExecutionToLegacy(execResponse.execution)
      setExecution(execData)
      setExecutionPlan((execResponse as unknown as { execution_plan?: unknown }).execution_plan ?? null)
      setExecutionBindings((execResponse as unknown as { bindings?: unknown }).bindings ?? null)
      setInitialNodeStatuses(normalizeNodeStatuses(execResponse.execution.node_statuses))

      const templateResponse = await api.getWorkflowsGetWorkflow({ workflow_id: execData.workflow_template })
      setDagStructure(convertDAGToLegacy(templateResponse.workflow.dag_structure))

      setError(null)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail
      setError(detail || 'Failed to load execution data')
    } finally {
      setIsLoading(false)
    }
  }, [executionId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const bindings = useMemo(() => {
    if (!isStaff) {
      return [] as Array<Record<string, unknown>>
    }
    return Array.isArray(executionBindings) ? executionBindings as Array<Record<string, unknown>> : []
  }, [executionBindings, isStaff])

  const effectiveNodeStatuses = useMemo(
    () => ({ ...initialNodeStatuses, ...nodeStatuses }),
    [initialNodeStatuses, nodeStatuses]
  )

  const displayStatus = isConnected ? liveStatus : (execution?.status || 'pending')
  const displayProgress = isConnected ? liveProgress : (execution?.progress_percent || 0) / 100
  const displayCurrentNodeId = isConnected ? currentNodeId : execution?.current_node_id
  const displayError = isConnected ? liveError : execution?.error_message
  const displayResult = liveResult !== undefined ? liveResult : execution?.final_result

  const selectedNode = useMemo<NodeDetails | null>(() => {
    if (!selectedNodeId || !dagStructure) {
      return null
    }

    const node = dagStructure.nodes.find((entry) => entry.id === selectedNodeId)
    if (!node) {
      return null
    }

    return {
      nodeId: selectedNodeId,
      nodeName: node.name,
      status: effectiveNodeStatuses[selectedNodeId] || {
        nodeId: selectedNodeId,
        status: 'pending',
      },
    }
  }, [dagStructure, effectiveNodeStatuses, selectedNodeId])

  useEffect(() => {
    if (!selectedNodeId || !dagStructure) {
      return
    }
    if (dagStructure.nodes.some((node) => node.id === selectedNodeId)) {
      return
    }
    updateParams({ node: null }, 'replace')
  }, [dagStructure, selectedNodeId, updateParams])

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    updateParams({ node: nodeId }, 'push')
  }, [updateParams])

  const handleCancel = async () => {
    if (!executionId) {
      return
    }

    try {
      setIsCancelling(true)
      await api.postWorkflowsCancelExecution({ execution_id: executionId })
      message.success('Execution cancellation requested')
      await loadData()
    } catch (err) {
      console.error('Failed to cancel execution:', err)
      message.error('Failed to cancel execution')
    } finally {
      setIsCancelling(false)
    }
  }

  const handleRefresh = async () => {
    try {
      await loadData()
      message.success('Execution refreshed')
    } catch (err) {
      console.error('Failed to refresh execution:', err)
    }
  }

  const canvasNodeStatuses = useMemo(() => Object.fromEntries(
    Object.entries(effectiveNodeStatuses).map(([id, status]) => [
      id,
      {
        status: status.status,
        output: status.output,
        error: status.error,
        durationMs: status.durationMs,
      },
    ])
  ), [effectiveNodeStatuses])

  const timelineItems = Object.values(effectiveNodeStatuses)
    .filter((status) => status.status !== 'pending')
    .sort((left, right) => {
      if (left.startedAt && right.startedAt) {
        return new Date(left.startedAt).getTime() - new Date(right.startedAt).getTime()
      }
      return 0
    })
    .map((status) => {
      const node = dagStructure?.nodes.find((entry) => entry.id === status.nodeId)
      const nodeName = node?.name || status.nodeId

      let color = 'gray'
      let dot = <ClockCircleOutlined />

      switch (status.status) {
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
        default:
          break
      }

      return {
        key: status.nodeId,
        color,
        dot,
        children: (
          <button
            type="button"
            className="timeline-item"
            onClick={() => handleNodeSelect(status.nodeId)}
          >
            <Text strong>{nodeName}</Text>
            <Text type="secondary" style={{ marginLeft: 8 }}>
              {status.status}
            </Text>
            {status.durationMs !== undefined ? (
              <Text type="secondary" style={{ marginLeft: 8 }}>
                ({(status.durationMs / 1000).toFixed(2)}s)
              </Text>
            ) : null}
          </button>
        ),
      }
    })

  if (isLoading) {
    return (
      <div className="workflow-monitor-loading">
        <Spin size="large" tip="Loading execution…">
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
        extra={(
          <Button type="primary" onClick={() => navigate(backTarget)}>
            Back to Executions
          </Button>
        )}
      />
    )
  }

  const isTerminal = ['completed', 'failed', 'cancelled'].includes(displayStatus)
  const completedCount = Object.values(effectiveNodeStatuses).filter((status) => status.status === 'completed').length
  const failedCount = Object.values(effectiveNodeStatuses).filter((status) => status.status === 'failed').length
  const runningCount = Object.values(effectiveNodeStatuses).filter((status) => status.status === 'running').length

  return (
    <div className="workflow-monitor">
      <WorkspacePage
        header={(
          <PageHeader
            title="Workflow Execution"
            subtitle={execution?.workflow_template_name
              ? `${execution.workflow_template_name} · ${executionId}`
              : executionId || 'Execution diagnostics'}
            actions={(
              <Space className="monitor-header" wrap size={[8, 8]}>
                <Button
                  icon={<ArrowLeftOutlined />}
                  onClick={() => navigate(backTarget)}
                >
                  Back
                </Button>
                <Badge
                  status={isConnected ? 'success' : 'error'}
                  text={isConnected ? 'Connected' : 'Disconnected'}
                />
                {connectionError ? (
                  <Tooltip title={connectionError}>
                    <Text type="danger">
                      {`Retry: ${reconnectAttempts}`}
                    </Text>
                  </Tooltip>
                ) : null}
                <Button icon={<ReloadOutlined />} onClick={() => void handleRefresh()}>
                  Refresh
                </Button>
                {!isTerminal ? (
                  <Button
                    danger
                    icon={<StopOutlined />}
                    onClick={() => void handleCancel()}
                    loading={isCancelling}
                  >
                    Cancel
                  </Button>
                ) : null}
                {traceId ? (
                  <Button
                    icon={<ExportOutlined />}
                    onClick={() => window.open(`${JAEGER_UI_URL}/trace/${traceId}`, '_blank', 'noopener,noreferrer')}
                  >
                    View Trace
                  </Button>
                ) : null}
              </Space>
            )}
          />
        )}
      >
        <div className="workflow-monitor-status">
          <StatusBadge
            status={
              displayStatus === 'completed'
                ? 'active'
                : displayStatus === 'failed'
                  ? 'error'
                  : displayStatus === 'cancelled'
                    ? 'warning'
                    : 'unknown'
            }
            label={(
              <Space size={6}>
                {statusIcons[displayStatus]}
                <span>{displayStatus.toUpperCase()}</span>
              </Space>
            )}
          />
          {selectedNode ? (
            <Text data-testid="workflow-monitor-selected-node" type="secondary">
              {`Selected node: ${selectedNode.nodeName}`}
            </Text>
          ) : null}
        </div>

        <div className="workflow-monitor-shell">
          <section className="monitor-content">
            <div className="progress-section">
              <Progress
                percent={Math.round(displayProgress * 100)}
                status={
                  displayStatus === 'failed'
                    ? 'exception'
                    : displayStatus === 'completed'
                      ? 'success'
                      : 'active'
                }
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
              />
            </div>

            {displayError ? (
              <Alert
                type="error"
                message="Execution Error"
                description={displayError}
                showIcon
                className="error-alert"
              />
            ) : null}

            {displayStatus === 'completed' && displayResult !== undefined && displayResult !== null ? (
              <Collapse
                size="small"
                defaultActiveKey={[]}
                className="result-collapse"
                items={[
                  {
                    key: 'result',
                    label: (
                      <Space size={8}>
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        Execution Completed
                      </Space>
                    ),
                    children: (
                      <JsonBlock
                        title="Final result"
                        value={displayResult}
                        height={260}
                        dataTestId="workflow-monitor-final-result"
                      />
                    ),
                  },
                ]}
              />
            ) : null}

            {dagStructure ? (
              <WorkflowCanvas
                dagStructure={dagStructure}
                mode="monitor"
                onNodeSelect={handleNodeSelect}
                nodeStatuses={canvasNodeStatuses}
                currentNodeId={displayCurrentNodeId}
              />
            ) : null}
          </section>

          <aside className="monitor-sidebar">
            <EntityDetails title="Execution Info">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="ID">
                  <Text
                    copyable={executionId ? { text: executionId } : false}
                    className="mono-text"
                  >
                    {executionId || '—'}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="Workflow">
                  <Link to={`/workflows/${execution?.workflow_template}`}>
                    {execution?.workflow_template_name || 'Unknown'}
                  </Link>
                </Descriptions.Item>
                <Descriptions.Item label="Started">
                  {formatDateTime(execution?.started_at)}
                </Descriptions.Item>
                <Descriptions.Item label="Completed">
                  {formatDateTime(execution?.completed_at)}
                </Descriptions.Item>
                <Descriptions.Item label="Duration">
                  {formatDuration(execution?.duration_seconds)}
                </Descriptions.Item>
                {traceId ? (
                  <Descriptions.Item label="Trace ID">
                    <Text copyable={{ text: traceId }} className="mono-text">
                      {traceId}
                    </Text>
                  </Descriptions.Item>
                ) : null}
              </Descriptions>
            </EntityDetails>

            {isStaff ? (
              <EntityDetails title="Execution Plan (staff)">
                {executionPlan ? (
                  <JsonBlock
                    title="Execution plan"
                    value={executionPlan}
                    height={220}
                    dataTestId="workflow-monitor-execution-plan"
                  />
                ) : (
                  <Text type="secondary">Not available</Text>
                )}
                <div className="workflow-monitor-bindings-header">
                  Binding Provenance (staff):
                </div>
                {bindings.length > 0 ? (
                  <div className="workflow-monitor-bindings-scroll">
                    <table className="workflow-monitor-bindings-table">
                      <thead>
                        <tr>
                          <th scope="col">Target</th>
                          <th scope="col">Source</th>
                          <th scope="col">Resolve</th>
                          <th scope="col">Sensitive</th>
                          <th scope="col">Status</th>
                          <th scope="col">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bindings.map((binding, index) => (
                          <tr key={`${String(binding.target_ref ?? 'binding')}-${index}`}>
                            <td>{String(binding.target_ref ?? '')}</td>
                            <td>{String(binding.source_ref ?? '')}</td>
                            <td>{String(binding.resolve_at ?? '')}</td>
                            <td>{binding.sensitive ? 'yes' : 'no'}</td>
                            <td>{String(binding.status ?? '')}</td>
                            <td>{String(binding.reason ?? '')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Text type="secondary">No bindings</Text>
                )}
              </EntityDetails>
            ) : null}

            <EntityDetails title="Statistics">
              <div className="workflow-monitor-stats-grid">
                <div className="workflow-monitor-stat">
                  <Text type="secondary">Completed</Text>
                  <strong>{completedCount}</strong>
                </div>
                <div className="workflow-monitor-stat">
                  <Text type="secondary">Failed</Text>
                  <strong>{failedCount}</strong>
                </div>
                <div className="workflow-monitor-stat">
                  <Text type="secondary">Running</Text>
                  <strong>{runningCount}</strong>
                </div>
                <div className="workflow-monitor-stat">
                  <Text type="secondary">Total nodes</Text>
                  <strong>{dagStructure?.nodes.length || 0}</strong>
                </div>
              </div>
            </EntityDetails>

            <EntityDetails title="Timeline">
              {timelineItems.length > 0 ? (
                <Timeline items={timelineItems} />
              ) : (
                <Text type="secondary">No activity yet</Text>
              )}
            </EntityDetails>
          </aside>
        </div>

        <NodeDetailsDrawer
          open={Boolean(selectedNode)}
          selectedNode={selectedNode}
          traceId={traceId || null}
          jaegerUiUrl={JAEGER_UI_URL}
          onClose={() => updateParams({ node: null }, 'push')}
          onOpenTraceDetails={(nodeId) => {
            setTraceNodeId(nodeId)
            setTraceModalVisible(true)
          }}
        />

        <TraceViewerModal
          visible={traceModalVisible}
          onClose={() => {
            setTraceModalVisible(false)
            setTraceNodeId(undefined)
          }}
          traceId={traceId || null}
          nodeId={traceNodeId}
          spanId={traceNodeId ? effectiveNodeStatuses[traceNodeId]?.spanId : undefined}
        />
      </WorkspacePage>
    </div>
  )
}

export default WorkflowMonitor
