/**
 * WorkflowExecutions - Page for listing workflow executions.
 */

import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  Progress,
  Segmented,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  ApartmentOutlined,
  EyeOutlined,
  ReloadOutlined,
  StopOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useQuery } from '@tanstack/react-query'
import { getV2 } from '../../api/generated'
import type { WorkflowExecutionList } from '../../api/generated/model'
import { formatDuration } from '../../utils/timelineTransforms'
import './WorkflowExecutions.css'

const api = getV2()
const { Title, Text } = Typography

type ExecutionStatus = WorkflowExecutionList['status']
type StatusFilter = ExecutionStatus | 'all'

const EMPTY_EXECUTIONS: WorkflowExecutionList[] = []

const statusMeta: Record<ExecutionStatus, { color: string; label: string }> = {
  pending: { color: 'default', label: 'Pending' },
  running: { color: 'blue', label: 'Running' },
  completed: { color: 'green', label: 'Completed' },
  failed: { color: 'red', label: 'Failed' },
  cancelled: { color: 'orange', label: 'Cancelled' },
}

const statusOptions: Array<{ label: string; value: StatusFilter }> = [
  { label: 'All', value: 'all' },
  { label: 'Running', value: 'running' },
  { label: 'Pending', value: 'pending' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Cancelled', value: 'cancelled' },
]

const statusValues = new Set(statusOptions.map((option) => option.value))
const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const parsePercent = (value: string | null | undefined) => {
  if (!value) return 0
  const parsed = Number.parseFloat(value)
  if (Number.isNaN(parsed)) return 0
  return Math.min(100, Math.max(0, parsed))
}

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const formatDurationSeconds = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return formatDuration(value * 1000)
}

const progressStatusFor = (status: ExecutionStatus) => {
  if (status === 'failed') return 'exception'
  if (status === 'completed') return 'success'
  if (status === 'running') return 'active'
  return 'normal'
}

const WorkflowExecutions = () => {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawStatus = searchParams.get('status') ?? 'all'
  const statusFilter: StatusFilter = statusValues.has(rawStatus as StatusFilter)
    ? (rawStatus as StatusFilter)
    : 'all'
  const workflowIdFilter = (searchParams.get('workflow_id') ?? '').trim()
  const [workflowIdInput, setWorkflowIdInput] = useState(workflowIdFilter)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  useEffect(() => {
    setWorkflowIdInput(workflowIdFilter)
  }, [workflowIdFilter])

  useEffect(() => {
    setPage(1)
  }, [statusFilter, workflowIdFilter])

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) {
        next.delete(key)
      } else {
        next.set(key, value)
      }
    })
    setSearchParams(next)
  }, [searchParams, setSearchParams])

  const handleStatusChange = useCallback((value: string | number) => {
    const next = String(value) as StatusFilter
    updateParams({ status: next === 'all' ? null : next })
  }, [updateParams])

  const applyWorkflowFilter = useCallback((value: string) => {
    const trimmed = value.trim()
    if (trimmed && !uuidRegex.test(trimmed)) {
      message.error('Workflow ID must be a valid UUID')
      return
    }
    updateParams({ workflow_id: trimmed || null })
  }, [message, updateParams])

  const handleWorkflowInputChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value
    setWorkflowIdInput(value)
    if (!value) {
      applyWorkflowFilter('')
    }
  }, [applyWorkflowFilter])

  const handleReset = useCallback(() => {
    setWorkflowIdInput('')
    updateParams({ status: null, workflow_id: null })
  }, [updateParams])

  const executionsQuery = useQuery({
    queryKey: ['workflow-executions', statusFilter, workflowIdFilter, page, pageSize],
    queryFn: () => api.getWorkflowsListExecutions({
      status: statusFilter === 'all' ? undefined : statusFilter,
      workflow_id: workflowIdFilter || undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }),
  })

  const executions = executionsQuery.data?.executions ?? EMPTY_EXECUTIONS
  const totalExecutions = typeof executionsQuery.data?.total === 'number'
    ? executionsQuery.data.total
    : executions.length

  const statusCounts = useMemo(() => {
    const counts: Record<ExecutionStatus, number> = {
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0,
      cancelled: 0,
    }
    executions.forEach((execution) => {
      counts[execution.status] += 1
    })
    return counts
  }, [executions])

  const handleCancel = useCallback(async (executionId: string) => {
    try {
      await api.postWorkflowsCancelExecution({ execution_id: executionId })
      message.success('Execution cancelled')
      executionsQuery.refetch()
    } catch (_error) {
      message.error('Failed to cancel execution')
    }
  }, [executionsQuery, message])

  const columns: ColumnsType<WorkflowExecutionList> = useMemo(() => ([
    {
      title: 'Execution',
      key: 'execution',
      width: 320,
      render: (_value, record) => (
        <div className="execution-cell">
          <div className="execution-title">
            <Text strong>{record.template_name || 'Untitled workflow'}</Text>
            <Tag color="blue">v{record.template_version}</Tag>
          </div>
          <Text
            type="secondary"
            className="execution-id"
            copyable={{ text: record.id }}
          >
            {record.id}
          </Text>
        </div>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      width: 240,
      render: (_value, record) => (
        <div className="execution-status">
          <Tag color={statusMeta[record.status]?.color || 'default'}>
            {statusMeta[record.status]?.label || record.status}
          </Tag>
          {record.error_message ? (
            <Tooltip title={record.error_message}>
              <Text type="danger" className="execution-error">
                {record.error_message}
              </Text>
            </Tooltip>
          ) : record.error_node_id ? (
            <Text type="secondary" className="execution-error">
              Error node: {record.error_node_id}
            </Text>
          ) : null}
        </div>
      ),
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 220,
      render: (_value, record) => {
        const percent = parsePercent(record.progress_percent)
        return (
          <div className="execution-progress">
            <Progress
              percent={percent}
              size="small"
              status={progressStatusFor(record.status)}
              showInfo
            />
            <Text type="secondary" className="execution-node">
              {record.current_node_id ? `Node: ${record.current_node_id}` : 'No active node'}
            </Text>
          </div>
        )
      },
    },
    {
      title: 'Timing',
      key: 'timing',
      width: 220,
      render: (_value, record) => (
        <div className="execution-timing">
          <Text type="secondary">Started: {formatDateTime(record.started_at)}</Text>
          <Text type="secondary">Completed: {formatDateTime(record.completed_at)}</Text>
          <Text type="secondary">Duration: {formatDurationSeconds(record.duration)}</Text>
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 170,
      render: (_value, record) => {
        const canCancel = record.status === 'pending' || record.status === 'running'
        return (
          <Space size="small">
            <Tooltip title="Open execution">
              <Button
                size="small"
                icon={<EyeOutlined />}
                onClick={() => navigate(`/workflows/executions/${record.id}`)}
                aria-label="Open execution"
              />
            </Tooltip>
            <Tooltip title="Open workflow">
              <Button
                size="small"
                icon={<ApartmentOutlined />}
                onClick={() => navigate(`/workflows/${record.workflow_template}`)}
                aria-label="Open workflow"
              />
            </Tooltip>
            <Tooltip title={canCancel ? 'Cancel execution' : 'Only pending or running executions can be cancelled'}>
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                disabled={!canCancel}
                onClick={() => handleCancel(record.id)}
                aria-label="Cancel execution"
              />
            </Tooltip>
          </Space>
        )
      },
    },
  ]), [handleCancel, navigate])

  const errorMessage = executionsQuery.error instanceof Error
    ? executionsQuery.error.message
    : 'Failed to load executions'

  return (
    <div className="workflow-executions-page">
      <div className="page-header">
        <div>
          <Title level={3}>Workflow Executions</Title>
          <Text type="secondary">Total: {totalExecutions}</Text>
        </div>
        <Space>
          <Button icon={<ApartmentOutlined />} onClick={() => navigate('/workflows')}>
            Workflows
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => executionsQuery.refetch()}>
            Refresh
          </Button>
        </Space>
      </div>

      <Card className="execution-filters-card">
        <div className="execution-filters">
          <div className="execution-filter">
            <Text type="secondary">Status</Text>
            <Segmented
              size="small"
              options={statusOptions}
              value={statusFilter}
              onChange={handleStatusChange}
            />
          </div>
          <div className="execution-filter">
            <Text type="secondary">Workflow ID</Text>
            <Space.Compact block>
              <Input
                allowClear
                placeholder="Workflow template UUID"
                value={workflowIdInput}
                onChange={handleWorkflowInputChange}
                onPressEnter={() => applyWorkflowFilter(workflowIdInput)}
                aria-label="Workflow ID filter"
              />
              <Button type="primary" onClick={() => applyWorkflowFilter(workflowIdInput)}>
                Apply
              </Button>
            </Space.Compact>
          </div>
          <div className="execution-filter execution-filter-actions">
            <Button onClick={handleReset}>Reset filters</Button>
          </div>
          <div className="execution-summary">
            <Text type="secondary">This page</Text>
            <div className="execution-summary-tags">
              <Tag color={statusMeta.running.color}>Running {statusCounts.running}</Tag>
              <Tag color={statusMeta.pending.color}>Pending {statusCounts.pending}</Tag>
              <Tag color={statusMeta.completed.color}>Completed {statusCounts.completed}</Tag>
              <Tag color={statusMeta.failed.color}>Failed {statusCounts.failed}</Tag>
              <Tag color={statusMeta.cancelled.color}>Cancelled {statusCounts.cancelled}</Tag>
            </div>
          </div>
        </div>
      </Card>

      {executionsQuery.isError && (
        <Alert
          type="error"
          showIcon
          message="Failed to load executions"
          description={errorMessage}
          className="execution-error-alert"
        />
      )}

      <Table
        dataSource={executions}
        columns={columns}
        rowKey="id"
        loading={executionsQuery.isLoading}
        pagination={{
          current: page,
          pageSize,
          total: totalExecutions,
          showSizeChanger: true,
          pageSizeOptions: [20, 50, 100, 200],
          onChange: (nextPage, nextPageSize) => {
            if (nextPageSize && nextPageSize !== pageSize) {
              setPageSize(nextPageSize)
              setPage(1)
              return
            }
            setPage(nextPage)
          },
        }}
        scroll={{ x: 1100 }}
        size="middle"
      />
    </div>
  )
}

export default WorkflowExecutions
