import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  App,
  Button,
  Descriptions,
  Input,
  Progress,
  Segmented,
  Space,
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
import {
  EntityDetails,
  EntityTable,
  JsonBlock,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { formatDuration } from '../../utils/timelineTransforms'

const api = getV2()
const { Text } = Typography

type ExecutionStatus = WorkflowExecutionList['status']
type StatusFilter = ExecutionStatus | 'all'

const EMPTY_EXECUTIONS: WorkflowExecutionList[] = []

const statusMeta: Record<ExecutionStatus, { label: string }> = {
  pending: { label: 'Pending' },
  running: { label: 'Running' },
  completed: { label: 'Completed' },
  failed: { label: 'Failed' },
  cancelled: { label: 'Cancelled' },
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

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const parsePercent = (value: string | null | undefined) => {
  if (!value) return 0
  const parsed = Number.parseFloat(value)
  if (Number.isNaN(parsed)) return 0
  return Math.min(100, Math.max(0, parsed))
}

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

const formatDurationSeconds = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return formatDuration(value * 1000)
}

const progressStatusFor = (status: ExecutionStatus) => {
  if (status === 'failed') return 'exception'
  if (status === 'completed') return 'success'
  if (status === 'running') return 'active'
  return 'normal'
}

const buildExecutionStatusBadges = (execution: Pick<WorkflowExecutionList, 'status' | 'progress_percent'>) => (
  <Space wrap size={8}>
    <StatusBadge
      status={execution.status === 'failed' ? 'error' : execution.status === 'completed' ? 'active' : execution.status === 'cancelled' ? 'warning' : 'unknown'}
      label={statusMeta[execution.status]?.label || execution.status}
    />
    <StatusBadge
      status={parsePercent(execution.progress_percent) >= 100 ? 'active' : execution.status === 'failed' ? 'error' : 'unknown'}
      label={`${parsePercent(execution.progress_percent)}%`}
    />
  </Space>
)

const WorkflowExecutions = () => {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const rawStatus = searchParams.get('status') ?? 'all'
  const statusFilter: StatusFilter = statusValues.has(rawStatus as StatusFilter)
    ? (rawStatus as StatusFilter)
    : 'all'
  const workflowIdFilter = (searchParams.get('workflow_id') ?? '').trim()
  const selectedExecutionFromUrl = normalizeRouteParam(searchParams.get('execution'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const [workflowIdInput, setWorkflowIdInput] = useState(workflowIdFilter)
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null | undefined>(
    () => selectedExecutionFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  useEffect(() => {
    setWorkflowIdInput(workflowIdFilter)
  }, [workflowIdFilter])

  useEffect(() => {
    setPage(1)
  }, [statusFilter, workflowIdFilter])

  useEffect(() => {
    setSelectedExecutionId((current) => {
      if (selectedExecutionFromUrl) {
        return current === selectedExecutionFromUrl ? current : selectedExecutionFromUrl
      }
      return current === null ? current : null
    })
  }, [selectedExecutionFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    routeUpdateModeRef.current = 'push'
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

  const executions = useMemo(
    () => executionsQuery.data?.executions ?? EMPTY_EXECUTIONS,
    [executionsQuery.data?.executions]
  )
  const totalExecutions = useMemo(
    () => typeof executionsQuery.data?.total === 'number' ? executionsQuery.data.total : executions.length,
    [executions, executionsQuery.data?.total]
  )

  const selectedExecutionSummary = executions.find((execution) => execution.id === selectedExecutionId) ?? null
  const selectedExecutionDetailQuery = useQuery({
    queryKey: ['workflow-executions', 'detail', selectedExecutionId ?? ''],
    enabled: Boolean(selectedExecutionId),
    queryFn: () => api.getWorkflowsGetExecution({ execution_id: selectedExecutionId ?? '' }),
  })
  const selectedExecutionDetail = selectedExecutionDetailQuery.data?.execution ?? null
  const selectedExecution = selectedExecutionDetail ?? selectedExecutionSummary

  useEffect(() => {
    if (executionsQuery.isLoading) {
      return
    }
    if (executions.length === 0) {
      routeUpdateModeRef.current = 'replace'
      setSelectedExecutionId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedExecutionId) {
      if (executions.some((execution) => execution.id === selectedExecutionId)) {
        return
      }
      if (selectedExecutionDetail?.id === selectedExecutionId) {
        return
      }
      if (selectedExecutionFromUrl === selectedExecutionId && selectedExecutionDetailQuery.isLoading) {
        return
      }
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedExecutionId(executions[0]?.id ?? null)
  }, [
    executions,
    executionsQuery.isLoading,
    selectedExecutionDetail?.id,
    selectedExecutionDetailQuery.isLoading,
    selectedExecutionFromUrl,
    selectedExecutionId,
  ])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)

    if (selectedExecutionId !== undefined) {
      if (selectedExecutionId) {
        next.set('execution', selectedExecutionId)
      } else {
        next.delete('execution')
      }
    }

    if (selectedExecutionId !== undefined) {
      if (isDetailDrawerOpen && selectedExecutionId) {
        next.set('detail', '1')
      } else {
        next.delete('detail')
      }
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [isDetailDrawerOpen, searchParams, selectedExecutionId, setSearchParams])

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
      await executionsQuery.refetch()
      await selectedExecutionDetailQuery.refetch()
    } catch (_error) {
      message.error('Failed to cancel execution')
    }
  }, [executionsQuery, message, selectedExecutionDetailQuery])

  const columns: ColumnsType<WorkflowExecutionList> = useMemo(() => ([
    {
      title: 'Execution',
      key: 'execution',
      width: 320,
      render: (_value, record) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Space wrap size={8}>
            <Text strong>{record.template_name || 'Untitled workflow'}</Text>
            <StatusBadge status="unknown" label={`v${record.template_version}`} />
          </Space>
          <Text type="secondary" copyable={{ text: record.id }}>
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
        <Space direction="vertical" size={6}>
          {buildExecutionStatusBadges(record)}
          {record.error_message ? (
            <Text type="danger">{record.error_message}</Text>
          ) : record.error_node_id ? (
            <Text type="secondary">{`Error node: ${record.error_node_id}`}</Text>
          ) : null}
        </Space>
      ),
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 220,
      render: (_value, record) => {
        const percent = parsePercent(record.progress_percent)
        return (
          <div style={{ minWidth: 180 }}>
            <Progress
              percent={percent}
              size="small"
              status={progressStatusFor(record.status)}
              showInfo
            />
            <Text type="secondary">
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
        <Space direction="vertical" size={4}>
          <Text type="secondary">Started: {formatDateTime(record.started_at)}</Text>
          <Text type="secondary">Completed: {formatDateTime(record.completed_at)}</Text>
          <Text type="secondary">Duration: {formatDurationSeconds(record.duration)}</Text>
        </Space>
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
                onClick={(event) => {
                  event.stopPropagation()
                  navigate(`/workflows/executions/${record.id}`)
                }}
                aria-label="Open execution"
              />
            </Tooltip>
            <Tooltip title="Open workflow">
              <Button
                size="small"
                icon={<ApartmentOutlined />}
                onClick={(event) => {
                  event.stopPropagation()
                  navigate(`/workflows/${record.workflow_template}`)
                }}
                aria-label="Open workflow"
              />
            </Tooltip>
            <Tooltip title={canCancel ? 'Cancel execution' : 'Only pending or running executions can be cancelled'}>
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                disabled={!canCancel}
                onClick={(event) => {
                  event.stopPropagation()
                  void handleCancel(record.id)
                }}
                aria-label="Cancel execution"
              />
            </Tooltip>
          </Space>
        )
      },
    },
  ]), [handleCancel, navigate])

  const detailLoading = Boolean(selectedExecutionId) && !selectedExecution && (executionsQuery.isLoading || selectedExecutionDetailQuery.isLoading)
  const detailError = selectedExecutionId && !selectedExecution && selectedExecutionDetailQuery.isError
    ? 'Failed to load the selected execution.'
    : null
  const errorMessage = executionsQuery.error instanceof Error
    ? executionsQuery.error.message
    : 'Failed to load executions'
  const selectedExecutionCanCancel = selectedExecution
    ? selectedExecution.status === 'pending' || selectedExecution.status === 'running'
    : false

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Workflow Executions"
          subtitle={`Total: ${totalExecutions}`}
          actions={(
            <Space wrap>
              <Button icon={<ApartmentOutlined />} onClick={() => navigate('/workflows')}>
                Workflows
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => executionsQuery.refetch()}>
                Refresh
              </Button>
            </Space>
          )}
        />
      )}
    >
      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailDrawerOpen(false)
        }}
        detailDrawerTitle={selectedExecution?.template_name || 'Execution detail'}
        list={(
          <EntityTable
            title="Catalog"
            error={executionsQuery.isError ? errorMessage : null}
            loading={executionsQuery.isLoading}
            emptyDescription="No workflow executions found."
            dataSource={executions}
            columns={columns}
            rowKey="id"
            onRow={(record) => ({
              onClick: () => {
                routeUpdateModeRef.current = 'push'
                setSelectedExecutionId(record.id)
                setIsDetailDrawerOpen(true)
              },
              style: { cursor: 'pointer' },
            })}
            rowClassName={(record) => (
              record.id === selectedExecutionId ? 'ant-table-row-selected' : ''
            )}
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
            toolbar={(
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Space wrap size={[16, 12]} style={{ width: '100%' }}>
                  <Space direction="vertical" size={4}>
                    <Text type="secondary">Status</Text>
                    <Segmented
                      size="small"
                      options={statusOptions}
                      value={statusFilter}
                      onChange={handleStatusChange}
                    />
                  </Space>
                  <Space direction="vertical" size={4} style={{ minWidth: 320 }}>
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
                  </Space>
                  <Button onClick={handleReset}>Reset filters</Button>
                </Space>
                <Space wrap size={[8, 8]}>
                  <StatusBadge status="unknown" label={`Running ${statusCounts.running}`} />
                  <StatusBadge status="unknown" label={`Pending ${statusCounts.pending}`} />
                  <StatusBadge status="active" label={`Completed ${statusCounts.completed}`} />
                  <StatusBadge status="error" label={`Failed ${statusCounts.failed}`} />
                  <StatusBadge status="warning" label={`Cancelled ${statusCounts.cancelled}`} />
                </Space>
              </Space>
            )}
          />
        )}
        detail={(
          <EntityDetails
            title="Execution detail"
            loading={detailLoading}
            error={detailError}
            empty={!selectedExecutionId || (!selectedExecution && !detailLoading)}
            emptyDescription="Select a workflow execution from the diagnostics catalog."
            extra={selectedExecution ? (
              <Space wrap>
                <Button
                  data-testid="workflow-executions-detail-open"
                  onClick={() => navigate(`/workflows/executions/${selectedExecution.id}`)}
                >
                  Open execution
                </Button>
                <Button
                  data-testid="workflow-executions-detail-open-workflow"
                  onClick={() => navigate(`/workflows/${selectedExecution.workflow_template}`)}
                >
                  Open workflow
                </Button>
                <Button
                  danger
                  data-testid="workflow-executions-detail-cancel"
                  disabled={!selectedExecutionCanCancel}
                  onClick={() => void handleCancel(selectedExecution.id)}
                >
                  Cancel execution
                </Button>
              </Space>
            ) : undefined}
          >
            {selectedExecution ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="Execution ID">
                    <Text code data-testid="workflow-executions-selected-id">{selectedExecution.id}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Workflow template">
                    <Text code>{selectedExecution.workflow_template}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Template name">
                    <Text strong>{selectedExecution.template_name || 'Untitled workflow'}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Version">{selectedExecution.template_version}</Descriptions.Item>
                  <Descriptions.Item label="Status">
                    {buildExecutionStatusBadges(selectedExecution)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Current node">
                    {selectedExecution.current_node_id || '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Error message">
                    {selectedExecution.error_message || '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Error node">
                    {selectedExecution.error_node_id || '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Trace ID">
                    {selectedExecution.trace_id ? <Text code>{selectedExecution.trace_id}</Text> : '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Started at">
                    {formatDateTime(selectedExecution.started_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Completed at">
                    {formatDateTime(selectedExecution.completed_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Duration">
                    {formatDurationSeconds(selectedExecution.duration)}
                  </Descriptions.Item>
                </Descriptions>

                <JsonBlock
                  title="Input context"
                  value={selectedExecutionDetail?.input_context ?? {}}
                  dataTestId="workflow-executions-selected-input-context"
                  height={220}
                />
                <JsonBlock
                  title="Final result"
                  value={selectedExecutionDetail?.final_result ?? {}}
                  dataTestId="workflow-executions-selected-final-result"
                  height={220}
                />
                <JsonBlock
                  title="Node statuses"
                  value={selectedExecutionDetail?.node_statuses ?? {}}
                  dataTestId="workflow-executions-selected-node-statuses"
                  height={220}
                />
                <JsonBlock
                  title="Step results"
                  value={selectedExecutionDetail?.step_results ?? []}
                  dataTestId="workflow-executions-selected-step-results"
                  height={220}
                />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />
    </WorkspacePage>
  )
}

export default WorkflowExecutions
