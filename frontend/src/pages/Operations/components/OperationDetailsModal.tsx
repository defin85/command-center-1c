/**
 * Modal component for displaying operation details and task list.
 * Extracted from Operations.tsx.
 */

import { useEffect, useMemo, useState } from 'react'
import { Modal, Space, Table, Tag, Progress, Alert, Typography, Button, Tooltip } from 'antd'
import { MonitorOutlined, BranchesOutlined, FilterOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { OperationDetailsModalProps, UITask } from '../types'
import { getStatusColor, getOperationTypeLabel } from '../utils'
import { useOperation } from '../../../api/queries/operations'
import type { TimelineStreamEvent } from '../../../hooks/useOperationTimelineStream'

const { Paragraph, Link } = Typography

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
  const operationId = operation?.id ?? null
  const [operationState, setOperationState] = useState(operation)

  const { data: freshOperation } = useOperation(operationId ?? '', {
    enabled: visible && !!operationId,
  })

  useEffect(() => {
    if (!operationId) {
      setOperationState(null)
      return
    }
    setOperationState(operation)
  }, [operation, operationId])

  useEffect(() => {
    if (freshOperation) {
      setOperationState(freshOperation)
    }
  }, [freshOperation])

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
      key: 'duration',
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
      key: 'error',
      render: (error: string) =>
        error ? <span style={{ color: 'red' }}>{error}</span> : '-',
    },
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
                <Link href={`/workflows/executions/${operationState.workflow_execution_id}`}>
                  {operationState.workflow_execution_id}
                </Link>
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
            <Table
              columns={taskColumns}
              dataSource={operationState.tasks}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Space>
        </div>
      )}
    </Modal>
  )
}
