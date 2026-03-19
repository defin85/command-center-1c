/**
 * Modal component for displaying operation details and task list.
 * Extracted from Operations.tsx.
 */

import { useEffect, useMemo, useState } from 'react'
import { Modal, Space, Tag, Progress, Alert, Typography, Button, Tooltip, Table } from 'antd'
import { MonitorOutlined, BranchesOutlined, FilterOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { Link as RouterLink } from 'react-router-dom'
import type { OperationDetailsModalProps, UITask } from '../types'
import { getStatusColor, getOperationTypeLabel } from '../utils'
import { useOperation } from '../../../api/queries/operations'
import type { TimelineStreamEvent } from '../../../hooks/useOperationTimelineStream'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { useAuthz } from '../../../authz/useAuthz'

const { Paragraph, Link, Text } = Typography

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
  predicate: (value: unknown) => value is T
): T | null => {
  if (!result || typeof result !== 'object') return null
  const value = (result as Record<string, unknown>)[key]
  return predicate(value) ? value : null
}

const extractTaskStderr = (result: unknown): string | null => {
  const raw = extractTaskResultField(result, 'stderr', (v): v is string => typeof v === 'string')
  const trimmed = raw?.trim()
  return trimmed ? trimmed : null
}

const extractTaskExitStatus = (result: unknown): number | null =>
  extractTaskResultField(result, 'exit_code', (v): v is number => typeof v === 'number' && Number.isFinite(v))

const applyTimelineUpdate = (
  operation: OperationDetailsModalProps['operation'],
  event: TimelineStreamEvent | null
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

/**
 * OperationDetailsModal - Shows detailed operation info with task breakdown
 */
export const OperationDetailsModal = ({
  operation,
  visible,
  onClose,
  onTimeline,
  liveEvent,
}: OperationDetailsModalProps) => {
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const operationId = operation?.id ?? null
  const [operationState, setOperationState] = useState(operation)

  useEffect(() => {
    if (!operationId) {
      setOperationState(null)
      return
    }
    setOperationState(operation)
  }, [operation, operationId])

  useEffect(() => {
    if (!liveEvent) return
    setOperationState((current) => applyTimelineUpdate(current, liveEvent))
  }, [liveEvent])

  const queuedTasks = useMemo(() => {
    if (!operationState) return 0
    const queued = operationState.total_tasks - operationState.completed_tasks - operationState.failed_tasks
    return Math.max(queued, 0)
  }, [operationState])

  const applyFilter = (key: 'workflow_execution_id' | 'node_id', value?: string) => {
    if (!value) return
    const params = new URLSearchParams(window.location.search)
    params.set(key, value)
    window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }
  const fallbackColumnConfigs = useMemo(() => [
    { key: 'database_name', label: 'Database', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'status', groupLabel: 'Status' },
    { key: 'duration_seconds', label: 'Duration', sortable: true, groupKey: 'timing', groupLabel: 'Timing' },
    { key: 'retry_count', label: 'Retries', sortable: true, groupKey: 'timing', groupLabel: 'Timing' },
    { key: 'error_message', label: 'Error', groupKey: 'details', groupLabel: 'Details' },
  ], [])

  const taskColumns: ColumnsType<UITask> = [
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
      render: (count: number, record) => `${count}/${record.max_retries}`,
    },
    {
      title: 'Error',
      dataIndex: 'error_message',
      key: 'error_message',
      render: (_error: string, record) => {
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
  ]

  const taskTable = useTableToolkit({
    tableId: 'operation_tasks',
    columns: taskColumns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 25,
  })

  const taskPageStart = (taskTable.pagination.page - 1) * taskTable.pagination.pageSize

  const { data: freshOperation, isFetching: tasksLoading } = useOperation(operationId ?? '', {
    enabled: visible && !!operationId,
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

  type UIBinding = {
    target_ref?: string
    source_ref?: string
    resolve_at?: string
    sensitive?: boolean
    status?: string
    reason?: string | null
  }

  const executionPlanText = useMemo(() => {
    if (!operationState || !isStaff) return null
    const plan = operationState.execution_plan as Record<string, unknown> | undefined
    if (!plan || typeof plan !== 'object') return null

    const kind = String(plan.kind ?? '')
    const argv = Array.isArray(plan.argv_masked) ? plan.argv_masked.filter((x) => typeof x === 'string') : []
    const stdinMasked = typeof plan.stdin_masked === 'string' ? plan.stdin_masked : null
    const workflowId = typeof plan.workflow_id === 'string' ? plan.workflow_id : null
    const inputContextMasked = plan.input_context_masked as unknown

    const lines: string[] = []
    if (kind) lines.push(`kind: ${kind}`)
    if (workflowId) lines.push(`workflow_id: ${workflowId}`)
    if (argv.length > 0) {
      lines.push('argv_masked:')
      lines.push(...argv.map((x) => `  ${x}`))
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

  const bindingColumns: ColumnsType<UIBinding> = [
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
  ]

  return (
    <Modal
      title={`Operation Details: ${operationState?.name}`}
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={null}
    >
      {operationState && (
        <div>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {/* Operation ID with Timeline button */}
            <div
              style={{
                padding: '12px',
                background: '#f0f2f5',
                borderRadius: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
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
              <Button
                type="primary"
                icon={<MonitorOutlined />}
                onClick={() => onTimeline(operationState.id)}
              >
                Timeline
              </Button>
            </div>

            {operationState.workflow_execution_id && (
              <div>
                <strong>Workflow Execution:</strong>{' '}
                <RouterLink to={`/workflows/executions/${operationState.workflow_execution_id}`}>
                  {operationState.workflow_execution_id}
                </RouterLink>
                {operationState.node_id && (
                  <Paragraph
                    copyable={{ text: operationState.node_id }}
                    style={{ marginBottom: 0, marginLeft: 8, display: 'inline' }}
                  >
                    <BranchesOutlined style={{ marginRight: 6 }} />
                    <code>{operationState.node_id}</code>
                  </Paragraph>
                )}
                <Button
                  size="small"
                  icon={<FilterOutlined />}
                  style={{ marginLeft: 8 }}
                  onClick={() => applyFilter('workflow_execution_id', operationState.workflow_execution_id)}
                >
                  Filter
                </Button>
                {operationState.node_id && (
                  <Button
                    size="small"
                    icon={<FilterOutlined />}
                    style={{ marginLeft: 8 }}
                    onClick={() => applyFilter('node_id', operationState.node_id)}
                  >
                    Node
                  </Button>
                )}
              </div>
            )}
            {operationState.trace_id && (
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
            )}

            <div>
              <strong>Description:</strong> {operationState.description || '-'}
            </div>
            <div>
              <strong>Type:</strong> {getOperationTypeLabel(operationState.operation_type)}
            </div>
            <div>
              <strong>Target Entity:</strong> {operationState.target_entity || '-'}
            </div>
            {isStaff && (
              <div>
                <strong>Execution Plan (staff):</strong>
                {executionPlanText ? (
                  <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{executionPlanText}</pre>
                ) : (
                  <div style={{ marginTop: 8, opacity: 0.7 }}>Not available</div>
                )}
              </div>
            )}
            {isStaff && bindings.length > 0 && (
              <div>
                <strong>Binding Provenance (staff):</strong>
                <Table
                  style={{ marginTop: 8 }}
                  size="small"
                  rowKey={(_, idx) => String(idx)}
                  pagination={false}
                  dataSource={bindings}
                  columns={bindingColumns}
                  scroll={{ x: 900 }}
                />
              </div>
            )}
            <div>
              <strong>Progress:</strong> <Progress percent={operationState.progress} />
            </div>
            <div>
              <strong>Statistics:</strong>{' '}
              {`${operationState.completed_tasks} completed, ${operationState.failed_tasks} failed, ${queuedTasks} queued, ${operationState.total_tasks} total`}
            </div>

            {/* Error message from metadata */}
            {operationState.status === 'failed' &&
            operationState.metadata &&
            (operationState.metadata as Record<string, unknown>).error ? (
              <Alert
                type="error"
                showIcon
                message="Operation Failed"
                description={String(
                  (operationState.metadata as Record<string, unknown>).error
                )}
              />
            ) : null}

            <h3>Tasks</h3>
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
        </div>
      )}
    </Modal>
  )
}
