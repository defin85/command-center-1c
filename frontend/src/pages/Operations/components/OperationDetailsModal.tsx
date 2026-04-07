/**
 * Secondary surfaces for inspecting operation details.
 *
 * Provides a reusable inspect panel for the canonical /operations workspace
 * and a modal wrapper kept for backward-compatible callers.
 */

import { useEffect, useMemo, useState } from 'react'
import { Grid, Modal, Space, Tag, Progress, Alert, Typography, Button, Tooltip, Table, Pagination } from 'antd'
import { MonitorOutlined, FilterOutlined, StopOutlined, ExportOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import type { OperationDetailsModalProps, UIBatchOperation, UITask } from '../types'
import { getStatusColor, getOperationTypeLabel } from '../utils'
import { useOperation } from '../../../api/queries/operations'
import type { TimelineStreamEvent } from '../../../hooks/useOperationTimelineStream'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { useAuthz } from '../../../authz/useAuthz'
import { EntityDetails, RouteButton } from '../../../components/platform'

const { Paragraph, Link, Text } = Typography
const { useBreakpoint } = Grid
const DESKTOP_BREAKPOINT_PX = 992

type OperationInspectPanelProps = {
  operationId: string | null
  operationSnapshot?: UIBatchOperation | null
  onTimeline: (operationId: string) => void
  liveEvent?: TimelineStreamEvent | null
  onFilterWorkflow?: (workflowExecutionId: string) => void
  onFilterNode?: (nodeId: string) => void
  canCancel?: boolean
  onCancel?: (operationId: string) => void
}

type OperationInspectBodyProps = OperationInspectPanelProps & {
  operationState: UIBatchOperation | null
  tasksLoading: boolean
  queuedTasks: number
  executionPlanText: string | null
  bindings: UIBinding[]
  taskColumns: ColumnsType<UITask>
  taskTable: ReturnType<typeof useTableToolkit<UITask>>
}

type UIBinding = {
  target_ref?: string
  source_ref?: string
  resolve_at?: string
  sensitive?: boolean
  status?: string
  reason?: string | null
}

const CANCELLABLE_OPERATION_STATUSES = new Set<UIBatchOperation['status']>([
  'pending',
  'queued',
  'processing',
])

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

const extractTaskResultField = <T,>(
  result: unknown,
  key: string,
  predicate: (value: unknown) => value is T,
): T | null => {
  if (!result || typeof result !== 'object') return null
  const value = (result as Record<string, unknown>)[key]
  return predicate(value) ? value : null
}

const extractTaskStderr = (result: unknown): string | null => {
  const raw = extractTaskResultField(result, 'stderr', (value): value is string => typeof value === 'string')
  const trimmed = raw?.trim()
  return trimmed ? trimmed : null
}

const extractTaskExitStatus = (result: unknown): number | null =>
  extractTaskResultField(result, 'exit_code', (value): value is number => typeof value === 'number' && Number.isFinite(value))

const applyTimelineUpdate = (
  operation: UIBatchOperation | null,
  event: TimelineStreamEvent | null,
) => {
  if (!operation || !event || operation.id !== event.operation_id) {
    return operation
  }

  const metadata = (event.metadata ?? {}) as Record<string, unknown>
  const totalTasks = toNumber(metadata.total_tasks)
  const completedTasks = toNumber(metadata.completed_tasks)
  const failedTasks = toNumber(metadata.failed_tasks)
  const progressPercent = toNumber(metadata.progress_percent)
  const databaseId = typeof metadata.database_id === 'string' ? metadata.database_id : null
  const taskStatus = typeof metadata.task_status === 'string' ? metadata.task_status : null
  const durationSeconds = toNumber(metadata.duration_seconds)
  const errorMessage = typeof metadata.error === 'string' ? metadata.error : ''
  const errorCode = typeof metadata.error_code === 'string' ? metadata.error_code : ''

  const updatedOperation = { ...operation }

  if (totalTasks !== null) {
    updatedOperation.total_tasks = totalTasks
  }
  if (completedTasks !== null) {
    updatedOperation.completed_tasks = completedTasks
  }
  if (failedTasks !== null) {
    updatedOperation.failed_tasks = failedTasks
  }
  if (progressPercent !== null) {
    updatedOperation.progress = Math.min(100, Math.max(0, Math.round(progressPercent)))
  } else if (
    totalTasks !== null &&
    completedTasks !== null &&
    failedTasks !== null &&
    totalTasks > 0
  ) {
    const processed = completedTasks + failedTasks
    updatedOperation.progress = Math.round((processed / totalTasks) * 100)
  }

  if (databaseId && taskStatus) {
    const now = new Date().toISOString()
    updatedOperation.tasks = updatedOperation.tasks.map((task) => {
      if (task.database !== databaseId) {
        return task
      }

      return {
        ...task,
        status: taskStatus as UITask['status'],
        duration_seconds: durationSeconds ?? task.duration_seconds,
        completed_at:
          taskStatus === 'completed' || taskStatus === 'failed'
            ? now
            : task.completed_at,
        error_message: taskStatus === 'failed' ? errorMessage : task.error_message,
        error_code: taskStatus === 'failed' ? errorCode : task.error_code,
      }
    })
  }

  if (event.event === 'operation.completed' || event.event === 'operation.failed') {
    updatedOperation.status = event.event === 'operation.failed' ? 'failed' : 'completed'
    updatedOperation.progress = 100
  }

  return updatedOperation
}

function useOperationInspectModel({
  operationId,
  operationSnapshot,
  liveEvent,
}: Pick<OperationInspectPanelProps, 'operationId' | 'operationSnapshot' | 'liveEvent'>) {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const [operationState, setOperationState] = useState<UIBatchOperation | null>(operationSnapshot ?? null)

  useEffect(() => {
    if (!operationId) {
      setOperationState(null)
      return
    }
    setOperationState(operationSnapshot ?? null)
  }, [operationId, operationSnapshot])

  useEffect(() => {
    if (!liveEvent) return
    setOperationState((current) => applyTimelineUpdate(current, liveEvent))
  }, [liveEvent])

  const queuedTasks = useMemo(() => {
    if (!operationState) return 0
    const queued = operationState.total_tasks - operationState.completed_tasks - operationState.failed_tasks
    return Math.max(queued, 0)
  }, [operationState])

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'database_name', label: 'Database', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'status', groupLabel: 'Status' },
    { key: 'duration_seconds', label: 'Duration', sortable: true, groupKey: 'timing', groupLabel: 'Timing' },
    { key: 'retry_count', label: 'Retries', sortable: true, groupKey: 'timing', groupLabel: 'Timing' },
    { key: 'error_message', label: 'Error', groupKey: 'details', groupLabel: 'Details' },
  ], [])

  const taskColumns: ColumnsType<UITask> = useMemo(() => [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{status}</Tag>,
    },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      render: (seconds: number | null) => (seconds ? `${seconds.toFixed(2)}s` : '-'),
    },
    {
      title: 'Retries',
      dataIndex: 'retry_count',
      key: 'retry_count',
      render: (count: number, record: UITask) => `${count}/${record.max_retries}`,
    },
    {
      title: 'Error',
      dataIndex: 'error_message',
      key: 'error_message',
      render: (_error: string, record: UITask) => {
        const stderr = extractTaskStderr(record.result)
        const exitStatus = extractTaskExitStatus(record.result)
        const error = (record.error_message ?? '').trim()
        const primary = stderr ?? error

        if (!primary) return '-'

        const showExitStatus = exitStatus !== null && primary !== `exit status ${exitStatus}`

        return (
          <Space direction="vertical" size={0}>
            <Text type="danger" ellipsis={{ tooltip: primary }} style={{ maxWidth: 420 }}>
              {primary}
            </Text>
            {showExitStatus ? <Text type="secondary">exit status {exitStatus}</Text> : null}
          </Space>
        )
      },
    },
  ], [])

  const taskTable = useTableToolkit({
    tableId: 'operation_tasks',
    columns: taskColumns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 25,
    disableServerMetadata: true,
  })

  const taskPageStart = (taskTable.pagination.page - 1) * taskTable.pagination.pageSize

  const { data: freshOperation, isFetching: tasksLoading } = useOperation(operationId ?? '', {
    enabled: Boolean(operationId),
    taskParams: {
      limit: taskTable.pagination.pageSize,
      offset: taskPageStart,
      filters: taskTable.filtersPayload,
      sort: taskTable.sortPayload,
    },
  })

  useEffect(() => {
    if (freshOperation) {
      setOperationState(freshOperation)
    }
  }, [freshOperation])

  const executionPlanText = useMemo(() => {
    if (!operationState || !isStaff) return null
    const plan = operationState.execution_plan as Record<string, unknown> | undefined
    if (!plan || typeof plan !== 'object') return null

    const kind = String(plan.kind ?? '')
    const argv = Array.isArray(plan.argv_masked) ? plan.argv_masked.filter((item) => typeof item === 'string') : []
    const stdinMasked = typeof plan.stdin_masked === 'string' ? plan.stdin_masked : null
    const workflowId = typeof plan.workflow_id === 'string' ? plan.workflow_id : null
    const inputContextMasked = plan.input_context_masked as unknown

    const lines: string[] = []
    if (kind) lines.push(`kind: ${kind}`)
    if (workflowId) lines.push(`workflow_id: ${workflowId}`)
    if (argv.length > 0) {
      lines.push('argv_masked:')
      lines.push(...argv.map((item) => `  ${item}`))
    }
    if (stdinMasked) {
      lines.push(`stdin_masked: ${stdinMasked}`)
    }
    if (inputContextMasked && typeof inputContextMasked === 'object') {
      lines.push('input_context_masked:')
      lines.push(JSON.stringify(inputContextMasked, null, 2))
    }
    return lines.length > 0 ? lines.join('\n') : null
  }, [isStaff, operationState])

  const bindings = useMemo(() => {
    if (!operationState || !isStaff) return [] as UIBinding[]
    return Array.isArray(operationState.bindings) ? (operationState.bindings as UIBinding[]) : []
  }, [isStaff, operationState])

  return {
    operationState,
    tasksLoading,
    queuedTasks,
    executionPlanText,
    bindings,
    taskColumns,
    taskTable,
  }
}

function OperationInspectBody({
  operationId,
  operationState,
  onTimeline,
  liveEvent: _liveEvent,
  onFilterWorkflow,
  onFilterNode,
  canCancel = false,
  onCancel,
  tasksLoading,
  queuedTasks,
  executionPlanText,
  bindings,
  taskColumns,
  taskTable,
}: OperationInspectBodyProps) {
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )

  if (!operationId || !operationState) {
    return <Text type="secondary">Select an operation to inspect status, tasks, and execution context.</Text>
  }

  const showCancel = canCancel && typeof onCancel === 'function' && CANCELLABLE_OPERATION_STATUSES.has(operationState.status)
  const hasTaskTelemetry = operationState.total_tasks > 0 || operationState.tasks.length > 0

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }} data-testid="operation-inspect-surface">
      <div
        style={{
          padding: '12px',
          background: '#f0f2f5',
          borderRadius: '8px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ flex: '1 1 260px', minWidth: 0 }}>
          <strong>Operation ID:</strong>
          <Paragraph
            copyable={{ text: operationState.id }}
            style={{
              marginBottom: 0,
              marginTop: 8,
              display: 'block',
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
            }}
          >
            <code>{operationState.id}</code>
          </Paragraph>
        </div>
        <Space wrap>
          {showCancel ? (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={() => onCancel(operationState.id)}
            >
              Cancel
            </Button>
          ) : null}
          <Button
            type="primary"
            icon={<MonitorOutlined />}
            onClick={() => onTimeline(operationState.id)}
          >
            Timeline
          </Button>
        </Space>
      </div>

      {operationState.workflow_execution_id ? (
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Space wrap size={[8, 8]}>
            <strong>Workflow Execution:</strong>
            <Text code style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
              {operationState.workflow_execution_id}
            </Text>
            <RouteButton
              size="small"
              type="link"
              icon={<ExportOutlined />}
              to={`/workflows/executions/${operationState.workflow_execution_id}`}
            >
              Open workflow diagnostics
            </RouteButton>
            {onFilterWorkflow ? (
              <Button
                size="small"
                icon={<FilterOutlined />}
                onClick={() => {
                  if (operationState.workflow_execution_id) {
                    onFilterWorkflow(operationState.workflow_execution_id)
                  }
                }}
              >
                Filter
              </Button>
            ) : null}
          </Space>
          {operationState.node_id ? (
            <Space wrap size={[8, 8]}>
              <strong>Node:</strong>
              <Paragraph
                copyable={{ text: operationState.node_id }}
                style={{ marginBottom: 0, display: 'block', overflowWrap: 'anywhere', wordBreak: 'break-word' }}
              >
                <code>{operationState.node_id}</code>
              </Paragraph>
              {onFilterNode ? (
                <Button
                  size="small"
                  icon={<FilterOutlined />}
                  onClick={() => {
                    if (operationState.node_id) {
                      onFilterNode(operationState.node_id)
                    }
                  }}
                >
                  Filter node
                </Button>
              ) : null}
            </Space>
          ) : null}
        </Space>
      ) : null}

      {operationState.trace_id ? (
        <div>
          <strong>Trace:</strong>{' '}
          <Tooltip title="Открыть trace через API Gateway">
            <Link
              href={`/api/v2/tracing/traces/${operationState.trace_id}`}
              target="_blank"
              rel="noreferrer"
              style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}
            >
              {operationState.trace_id}
            </Link>
          </Tooltip>
        </div>
      ) : null}

      <div>
        <strong>Description:</strong> {operationState.description || '-'}
      </div>
      <div>
        <strong>Type:</strong> {getOperationTypeLabel(operationState.operation_type)}
      </div>
      <div>
        <strong>Target Entity:</strong> {operationState.target_entity || '-'}
      </div>
      {executionPlanText ? (
        <div>
          <strong>Execution Plan (staff):</strong>
          <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
            {executionPlanText}
          </pre>
        </div>
      ) : null}
      {bindings.length > 0 ? (
        <div>
          <strong>Binding Provenance (staff):</strong>
          <div
            data-testid="operation-inspect-bindings-surface"
            style={{
              display: 'grid',
              gap: 12,
              gridTemplateColumns: isNarrow ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(220px, 1fr))',
              marginTop: 8,
            }}
          >
            {bindings.map((binding, index) => (
              <div
                key={`${binding.target_ref ?? 'binding'}-${index}`}
                style={{
                  border: '1px solid #f0f0f0',
                  borderRadius: 8,
                  padding: 12,
                }}
              >
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Text strong style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                    {binding.target_ref || 'Unnamed binding target'}
                  </Text>
                  <Text type="secondary" style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{`Source: ${binding.source_ref || '-'}`}</Text>
                  <Text type="secondary" style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{`Resolve: ${binding.resolve_at || '-'}`}</Text>
                  <Text type="secondary" style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{`Sensitive: ${binding.sensitive ? 'yes' : 'no'}`}</Text>
                  <Text type="secondary" style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{`Status: ${binding.status || '-'}`}</Text>
                  {binding.reason ? (
                    <Text type="secondary" style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{`Reason: ${binding.reason}`}</Text>
                  ) : null}
                </Space>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {hasTaskTelemetry ? (
        <>
          <div>
            <strong>Progress:</strong> <Progress percent={operationState.progress} />
          </div>
          <div>
            <strong>Statistics:</strong>{' '}
            {`${operationState.completed_tasks} completed, ${operationState.failed_tasks} failed, ${queuedTasks} queued, ${operationState.total_tasks} total`}
          </div>
        </>
      ) : (
        <Alert
          type="info"
          showIcon
          message="No task telemetry yet"
          description="This execution currently exposes no task workset telemetry. Inspect the execution plan, bindings, or timeline context instead."
          data-testid="operation-inspect-no-task-telemetry"
        />
      )}

      {operationState.status === 'failed' &&
      operationState.metadata &&
      (operationState.metadata as Record<string, unknown>).error ? (
        <Alert
          type="error"
          showIcon
          message="Operation Failed"
          description={String(
            (operationState.metadata as Record<string, unknown>).error,
          )}
        />
      ) : null}

      <h3 style={{ marginBottom: 0 }}>Tasks</h3>
      {hasTaskTelemetry ? (
        isNarrow ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {tasksLoading && operationState.tasks.length === 0 ? (
              <Text type="secondary">Loading task telemetry...</Text>
            ) : null}
            {operationState.tasks.map((task) => (
              <div
                key={task.id}
                style={{
                  border: '1px solid #f0f0f0',
                  borderRadius: 8,
                  padding: 12,
                }}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space wrap size={[8, 8]}>
                    <Text strong>{task.database_name}</Text>
                    <Tag color={getStatusColor(task.status)}>{task.status}</Tag>
                  </Space>
                  <Text type="secondary">
                    {`Duration: ${task.duration_seconds ? `${task.duration_seconds.toFixed(2)}s` : '-'}`}
                  </Text>
                  <Text type="secondary">
                    {`Retries: ${task.retry_count}/${task.max_retries}`}
                  </Text>
                  {task.error_message ? (
                    <Text type="danger">{task.error_message}</Text>
                  ) : null}
                </Space>
              </div>
            ))}
          </Space>
        ) : (
          <div data-testid="operation-inspect-tasks-surface">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Table
                dataSource={operationState.tasks}
                pagination={false}
                rowKey="id"
                columns={taskColumns}
                size="small"
                tableLayout="fixed"
                loading={tasksLoading}
              />
              <Pagination
                size="small"
                current={taskTable.pagination.page}
                pageSize={taskTable.pagination.pageSize}
                total={operationState.total_tasks ?? operationState.tasks.length}
                showSizeChanger
                pageSizeOptions={[10, 25, 50]}
                onChange={(page, pageSize) => {
                  if (pageSize !== taskTable.pagination.pageSize) {
                    taskTable.setPageSize(pageSize)
                    return
                  }
                  taskTable.setPage(page)
                }}
              />
            </Space>
          </div>
        )
      ) : (
        <Text type="secondary">
          Task list will appear when runtime reports a task workset for this operation.
        </Text>
      )}
    </Space>
  )
}

export function OperationInspectPanel(props: OperationInspectPanelProps) {
  const model = useOperationInspectModel(props)
  const title = model.operationState
    ? `Operation Details: ${model.operationState.name}`
    : 'Operation Details'

  return (
    <EntityDetails title={title}>
      <OperationInspectBody
        {...props}
        {...model}
      />
    </EntityDetails>
  )
}

/**
 * Modal wrapper retained for backward-compatible callers.
 */
export const OperationDetailsModal = ({
  operation,
  visible,
  onClose,
  onTimeline,
  liveEvent,
}: OperationDetailsModalProps) => {
  const model = useOperationInspectModel({
    operationId: visible ? operation?.id ?? null : null,
    operationSnapshot: operation,
    liveEvent,
  })

  return (
    <Modal
      title={model.operationState ? `Operation Details: ${model.operationState.name}` : 'Operation Details'}
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={null}
    >
      <OperationInspectBody
        operationId={visible ? operation?.id ?? null : null}
        operationSnapshot={operation}
        onTimeline={onTimeline}
        liveEvent={liveEvent}
        {...model}
      />
    </Modal>
  )
}
