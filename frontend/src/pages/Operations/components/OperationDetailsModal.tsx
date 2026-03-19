/**
 * Secondary surfaces for inspecting operation details.
 *
 * Provides a reusable inspect panel for the canonical /operations workspace
 * and a modal wrapper kept for backward-compatible callers.
 */

import { useEffect, useMemo, useState } from 'react'
import { Modal, Space, Tag, Progress, Alert, Typography, Button, Tooltip, Table } from 'antd'
import { MonitorOutlined, BranchesOutlined, FilterOutlined, StopOutlined, ExportOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import type { OperationDetailsModalProps, UIBatchOperation, UITask } from '../types'
import { getStatusColor, getOperationTypeLabel } from '../utils'
import { useOperation } from '../../../api/queries/operations'
import type { TimelineStreamEvent } from '../../../hooks/useOperationTimelineStream'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { useAuthz } from '../../../authz/useAuthz'
import { EntityDetails, RouteButton } from '../../../components/platform'

const { Paragraph, Link, Text } = Typography

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
  bindingColumns: ColumnsType<UIBinding>
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

  const bindingColumns: ColumnsType<UIBinding> = useMemo(() => [
    { title: 'Target', dataIndex: 'target_ref', key: 'target_ref' },
    { title: 'Source', dataIndex: 'source_ref', key: 'source_ref' },
    { title: 'Resolve', dataIndex: 'resolve_at', key: 'resolve_at', width: 90 },
    {
      title: 'Sensitive',
      dataIndex: 'sensitive',
      key: 'sensitive',
      width: 90,
      render: (value: boolean | undefined) => (value ? <Tag color="red">yes</Tag> : <Tag>no</Tag>),
    },
    { title: 'Status', dataIndex: 'status', key: 'status', width: 110 },
    { title: 'Reason', dataIndex: 'reason', key: 'reason' },
  ], [])

  return {
    operationState,
    tasksLoading,
    queuedTasks,
    executionPlanText,
    bindings,
    taskColumns,
    bindingColumns,
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
  bindingColumns,
  taskTable,
}: OperationInspectBodyProps) {
  if (!operationId || !operationState) {
    return <Text type="secondary">Select an operation to inspect status, tasks, and execution context.</Text>
  }

  const showCancel = canCancel && typeof onCancel === 'function' && CANCELLABLE_OPERATION_STATUSES.has(operationState.status)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div
        style={{
          padding: '12px',
          background: '#f0f2f5',
          borderRadius: '8px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <div>
          <strong>Operation ID:</strong>
          <Paragraph
            copyable={{ text: operationState.id }}
            style={{ marginBottom: 0, marginLeft: 8, display: 'inline' }}
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
        <div>
          <strong>Workflow Execution:</strong>{' '}
          <Text code>{operationState.workflow_execution_id}</Text>
          <RouteButton
            size="small"
            type="link"
            icon={<ExportOutlined />}
            to={`/workflows/executions/${operationState.workflow_execution_id}`}
            style={{ marginLeft: 8 }}
          >
            Open workflow diagnostics
          </RouteButton>
          {operationState.node_id ? (
            <Paragraph
              copyable={{ text: operationState.node_id }}
              style={{ marginBottom: 0, marginLeft: 8, display: 'inline' }}
            >
              <BranchesOutlined style={{ marginRight: 6 }} />
              <code>{operationState.node_id}</code>
            </Paragraph>
          ) : null}
          {onFilterWorkflow ? (
            <Button
              size="small"
              icon={<FilterOutlined />}
              style={{ marginLeft: 8 }}
              onClick={() => {
                if (operationState.workflow_execution_id) {
                  onFilterWorkflow(operationState.workflow_execution_id)
                }
              }}
            >
              Filter
            </Button>
          ) : null}
          {operationState.node_id && onFilterNode ? (
            <Button
              size="small"
              icon={<FilterOutlined />}
              style={{ marginLeft: 8 }}
              onClick={() => {
                if (operationState.node_id) {
                  onFilterNode(operationState.node_id)
                }
              }}
            >
              Node
            </Button>
          ) : null}
        </div>
      ) : null}

      {operationState.trace_id ? (
        <div>
          <strong>Trace:</strong>{' '}
          <Tooltip title="Открыть trace через API Gateway">
            <Link
              href={`/api/v2/tracing/traces/${operationState.trace_id}`}
              target="_blank"
              rel="noreferrer"
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
          <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{executionPlanText}</pre>
        </div>
      ) : null}
      {bindings.length > 0 ? (
        <div>
          <strong>Binding Provenance (staff):</strong>
          <Table
            style={{ marginTop: 8 }}
            size="small"
            rowKey={(_, index) => String(index)}
            pagination={false}
            dataSource={bindings}
            columns={bindingColumns}
            scroll={{ x: 900 }}
          />
        </div>
      ) : null}
      <div>
        <strong>Progress:</strong> <Progress percent={operationState.progress} />
      </div>
      <div>
        <strong>Statistics:</strong>{' '}
        {`${operationState.completed_tasks} completed, ${operationState.failed_tasks} failed, ${queuedTasks} queued, ${operationState.total_tasks} total`}
      </div>

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
      <TableToolkit
        table={taskTable}
        data={operationState.tasks}
        total={operationState.total_tasks ?? operationState.tasks.length}
        loading={tasksLoading}
        rowKey="id"
        columns={taskColumns}
        size="small"
        tableLayout="fixed"
        scroll={{ x: taskTable.totalColumnsWidth }}
        searchPlaceholder="Search tasks"
      />
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
