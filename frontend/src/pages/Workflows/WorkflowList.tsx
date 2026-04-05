import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  App,
  Alert,
  Button,
  Descriptions,
  Popconfirm,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  ClockCircleOutlined,
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../../api/generated'
import type { WorkflowTemplateDetail, WorkflowTemplateList } from '../../api/generated/model'
import {
  EntityDetails,
  JsonBlock,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

const api = getV2()
const { Text } = Typography

const workflowTypeColors: Record<string, string> = {
  sequential: 'blue',
  parallel: 'green',
  conditional: 'orange',
  complex: 'purple',
}

const WORKFLOW_LIBRARY_SURFACE = 'workflow_library'
const WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE = 'runtime_diagnostics'

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const formatDateTime = (value: string | null | undefined) => (
  value ? new Date(value).toLocaleString() : '—'
)

const buildWorkflowHref = (
  id: string,
  {
    isSystemManaged,
    databaseId,
    execute,
  }: {
    isSystemManaged?: boolean
    databaseId?: string
    execute?: boolean
  } = {}
) => {
  const params = new URLSearchParams()
  if (isSystemManaged) {
    params.set('surface', WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE)
  }
  if (databaseId) {
    params.set('database_id', databaseId)
  }
  if (execute) {
    params.set('execute', 'true')
  }
  const query = params.toString()
  return query ? `/workflows/${id}?${query}` : `/workflows/${id}`
}

const renderStatusSummary = (workflow: Pick<WorkflowTemplateList, 'is_active' | 'is_valid' | 'visibility_surface'>) => (
  <Space wrap size={8}>
    <StatusBadge
      status={workflow.is_active ? 'active' : 'inactive'}
      label={workflow.is_active ? 'Active' : 'Inactive'}
    />
    <StatusBadge
      status={workflow.is_valid ? 'compatible' : 'error'}
      label={workflow.is_valid ? 'Valid' : 'Invalid'}
    />
    <StatusBadge
      status={workflow.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE ? 'warning' : 'unknown'}
      label={workflow.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE ? 'Runtime diagnostics' : 'Analyst library'}
    />
  </Space>
)

const resolveNodeCount = (
  workflowSummary: WorkflowTemplateList | null,
  workflowDetail: WorkflowTemplateDetail | null
) => {
  if (workflowSummary) {
    return workflowSummary.node_count ?? 0
  }
  const dag = workflowDetail?.dag_structure as { nodes?: unknown } | undefined
  return Array.isArray(dag?.nodes) ? dag.nodes.length : 0
}

const WorkflowList = () => {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const queryClient = useQueryClient()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const surface = searchParams.get('surface') === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
    ? WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
    : WORKFLOW_LIBRARY_SURFACE
  const decisionDatabaseId = String(searchParams.get('database_id') || '').trim()
  const searchFromUrl = searchParams.get('q') ?? ''
  const selectedWorkflowFromUrl = normalizeRouteParam(searchParams.get('workflow'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const isRuntimeDiagnosticsSurface = surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null | undefined>(
    () => selectedWorkflowFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'workflow_type', label: 'Type', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Status', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'node_count', label: 'Nodes', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'updated_at', label: 'Updated', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.postWorkflowsDeleteWorkflow({ workflow_id: id })
      message.success('Workflow deleted')
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      routeUpdateModeRef.current = 'push'
      if (selectedWorkflowId === id) {
        setSelectedWorkflowId(null)
        setIsDetailDrawerOpen(false)
      }
    } catch (_error) {
      message.error('Failed to delete workflow')
    }
  }, [message, queryClient, selectedWorkflowId])

  const handleClone = useCallback(async (id: string, name: string) => {
    try {
      const cloned = await api.postWorkflowsCloneWorkflow({
        workflow_id: id,
        new_name: `${name} (Copy)`,
      })
      message.success('Workflow cloned')
      navigate(buildWorkflowHref(cloned.workflow.id, { databaseId: decisionDatabaseId }))
    } catch (_error) {
      message.error('Failed to clone workflow')
    }
  }, [decisionDatabaseId, message, navigate])

  const openWorkflow = useCallback((id: string, isSystemManaged?: boolean) => {
    navigate(buildWorkflowHref(id, { isSystemManaged, databaseId: decisionDatabaseId }))
  }, [decisionDatabaseId, navigate])

  const columns: ColumnsType<WorkflowTemplateList> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <Space wrap size={8}>
          <Link to={buildWorkflowHref(record.id, { isSystemManaged: record.is_system_managed, databaseId: decisionDatabaseId })}>
            {name}
          </Link>
          {record.is_system_managed ? <Tag color="gold">System managed</Tag> : null}
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'workflow_type',
      key: 'workflow_type',
      render: (type) => <Tag color={workflowTypeColors[String(type)] || 'default'}>{String(type || 'unknown')}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (_value, record) => renderStatusSummary(record),
    },
    {
      title: 'Nodes',
      key: 'node_count',
      dataIndex: 'node_count',
      render: (count) => count ?? 0,
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (date) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_value, record) => (
        <Space>
          <Tooltip title={record.is_system_managed ? 'Inspect read-only runtime projection' : 'Edit'}>
            <Button
              icon={<EditOutlined />}
              size="small"
              aria-label={record.is_system_managed ? 'Inspect workflow' : 'Edit workflow'}
              onClick={(event) => {
                event.stopPropagation()
                openWorkflow(record.id, record.is_system_managed)
              }}
            />
          </Tooltip>
          {!record.is_system_managed ? (
            <>
              <Tooltip title="Clone">
                <Button
                  icon={<CopyOutlined />}
                  size="small"
                  aria-label="Clone scheme"
                  onClick={(event) => {
                    event.stopPropagation()
                    void handleClone(record.id, record.name)
                  }}
                />
              </Tooltip>
              <Tooltip title="Execute">
                <Button
                  icon={<PlayCircleOutlined />}
                  size="small"
                  aria-label="Execute workflow"
                  disabled={!record.is_valid}
                  onClick={(event) => {
                    event.stopPropagation()
                    navigate(buildWorkflowHref(record.id, { databaseId: decisionDatabaseId, execute: true }))
                  }}
                />
              </Tooltip>
              <Popconfirm
                title="Delete workflow?"
                description="This action cannot be undone."
                onConfirm={() => handleDelete(record.id)}
                okText="Delete"
                okButtonProps={{ danger: true }}
              >
                <Tooltip title="Delete">
                  <Button
                    icon={<DeleteOutlined />}
                    size="small"
                    danger
                    aria-label="Delete workflow"
                    onClick={(event) => {
                      event.stopPropagation()
                    }}
                  />
                </Tooltip>
              </Popconfirm>
            </>
          ) : null}
        </Space>
      ),
    },
  ]), [decisionDatabaseId, handleClone, handleDelete, navigate, openWorkflow])

  const table = useTableToolkit({
    tableId: 'workflows',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const filtersParam = table.filtersPayload ? JSON.stringify(table.filtersPayload) : undefined
  const sortParam = table.sortPayload ? JSON.stringify(table.sortPayload) : undefined

  useEffect(() => {
    if (table.search === searchFromUrl) return
    table.setSearch(searchFromUrl)
  }, [searchFromUrl, table])

  useEffect(() => {
    setSelectedWorkflowId((current) => {
      if (selectedWorkflowFromUrl) {
        return current === selectedWorkflowFromUrl ? current : selectedWorkflowFromUrl
      }
      return current === null ? current : null
    })
  }, [selectedWorkflowFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  const workflowsQuery = useQuery({
    queryKey: [
      'workflows',
      surface,
      table.search,
      table.filtersPayload,
      table.sortPayload,
      table.pagination.page,
      table.pagination.pageSize,
    ],
    queryFn: () => api.getWorkflowsListWorkflows({
      surface,
      search: table.search || undefined,
      filters: filtersParam,
      sort: sortParam,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const workflows = useMemo(
    () => workflowsQuery.data?.workflows ?? [],
    [workflowsQuery.data?.workflows]
  )
  const totalWorkflows = useMemo(
    () => workflowsQuery.data?.total ?? workflows.length,
    [workflows, workflowsQuery.data?.total]
  )
  const authoringPhase = useMemo(
    () => workflowsQuery.data?.authoring_phase ?? null,
    [workflowsQuery.data?.authoring_phase]
  )
  const selectedWorkflowSummary = workflows.find((workflow) => workflow.id === selectedWorkflowId) ?? null

  const selectedWorkflowDetailQuery = useQuery({
    queryKey: ['workflows', 'detail', selectedWorkflowId ?? ''],
    enabled: Boolean(selectedWorkflowId),
    queryFn: () => api.getWorkflowsGetWorkflow({ workflow_id: selectedWorkflowId ?? '' }),
  })

  const selectedWorkflowDetail = selectedWorkflowDetailQuery.data?.workflow ?? null
  const selectedWorkflow = selectedWorkflowDetail ?? selectedWorkflowSummary

  useEffect(() => {
    if (workflowsQuery.isLoading) {
      return
    }
    if (workflows.length === 0) {
      routeUpdateModeRef.current = 'replace'
      setSelectedWorkflowId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedWorkflowId) {
      if (workflows.some((workflow) => workflow.id === selectedWorkflowId)) {
        return
      }
      if (selectedWorkflowDetail?.id === selectedWorkflowId) {
        return
      }
      if (selectedWorkflowFromUrl === selectedWorkflowId && selectedWorkflowDetailQuery.isLoading) {
        return
      }
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedWorkflowId(workflows[0]?.id ?? null)
  }, [
    selectedWorkflowDetail?.id,
    selectedWorkflowFromUrl,
    selectedWorkflowId,
    selectedWorkflowDetailQuery.isLoading,
    workflows,
    workflowsQuery.isLoading,
  ])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    const normalizedSearch = table.search.trim()

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    } else {
      next.delete('q')
    }

    if (selectedWorkflowId !== undefined) {
      if (selectedWorkflowId) {
        next.set('workflow', selectedWorkflowId)
      } else {
        next.delete('workflow')
      }
    }

    if (selectedWorkflowId !== undefined) {
      if (isDetailDrawerOpen && selectedWorkflowId) {
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
  }, [isDetailDrawerOpen, searchParams, selectedWorkflowId, setSearchParams, table.search])

  const detailLoading = Boolean(selectedWorkflowId) && !selectedWorkflow && (workflowsQuery.isLoading || selectedWorkflowDetailQuery.isLoading)
  const detailError = selectedWorkflowId && !selectedWorkflow && selectedWorkflowDetailQuery.isError
    ? 'Failed to load the selected workflow.'
    : null
  const selectedWorkflowNodeCount = resolveNodeCount(selectedWorkflowSummary, selectedWorkflowDetail)
  const selectedWorkflowExecutionCount = selectedWorkflowDetail?.execution_count ?? selectedWorkflowSummary?.execution_count ?? 0

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={isRuntimeDiagnosticsSurface ? 'Workflow Runtime Diagnostics' : 'Workflow Scheme Library'}
          subtitle={isRuntimeDiagnosticsSurface
            ? 'Read-only generated projections compiled from pool bindings and analyst-authored definitions.'
            : 'Reusable analyst-authored workflow definitions for pool distribution and publication.'}
          actions={(
            <Space wrap>
              <Button
                icon={<ClockCircleOutlined />}
                onClick={() => navigate('/workflows/executions')}
              >
                Executions
              </Button>
              <Button
                onClick={() => {
                  routeUpdateModeRef.current = 'push'
                  const next = new URLSearchParams(searchParams)
                  if (isRuntimeDiagnosticsSurface) {
                    next.delete('surface')
                  } else {
                    next.set('surface', WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE)
                  }
                  setSearchParams(next)
                }}
              >
                {isRuntimeDiagnosticsSurface ? 'Analyst Library' : 'Runtime Diagnostics'}
              </Button>
              {!isRuntimeDiagnosticsSurface ? (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => navigate(buildWorkflowHref('new', { databaseId: decisionDatabaseId }))}
                >
                  New Scheme
                </Button>
              ) : null}
            </Space>
          )}
        />
      )}
    >
      {isRuntimeDiagnosticsSurface ? (
        <Alert
          showIcon
          type="warning"
          message="Runtime diagnostics surface"
          description="System-managed runtime workflow projections are listed separately and remain read-only."
        />
      ) : null}

      {authoringPhase ? (
        <Alert
          showIcon
          type={authoringPhase.is_prerequisite_platform_phase ? 'info' : 'success'}
          message={authoringPhase.label}
          description={(
            <Space direction="vertical" size={4}>
              <span>{authoringPhase.description}</span>
              <span>{`Primary analyst surface: ${authoringPhase.analyst_surface}`}</span>
              <span>
                Compose analyst-authored schemes in /workflows. Use /templates for atomic
                operations and /decisions for versioned decision resources.
              </span>
              <Space wrap size={[8, 8]}>
                {authoringPhase.rollout_scope.map((scope) => (
                  <Tag key={scope} color="blue">
                    {scope}
                  </Tag>
                ))}
                {authoringPhase.deferred_scope.map((scope) => (
                  <Tag key={scope} color="gold">
                    {`Deferred: ${scope}`}
                  </Tag>
                ))}
                {authoringPhase.follow_up_changes.map((changeId) => (
                  <Tag key={changeId} color="purple">
                    {`Follow-up: ${changeId}`}
                  </Tag>
                ))}
              </Space>
            </Space>
          )}
        />
      ) : null}

      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailDrawerOpen(false)
        }}
        detailDrawerTitle={selectedWorkflow?.name || 'Workflow detail'}
        list={(
          <EntityDetails title="Catalog">
            <div style={{ width: '100%', minWidth: 0, overflowX: 'auto' }}>
              <TableToolkit
                table={table}
                data={workflows}
                total={totalWorkflows}
                loading={workflowsQuery.isLoading}
                rowKey="id"
                columns={columns}
                searchPlaceholder="Search workflow schemes"
                onRow={(record) => ({
                  onClick: () => {
                    routeUpdateModeRef.current = 'push'
                    setSelectedWorkflowId(record.id)
                    setIsDetailDrawerOpen(true)
                  },
                  style: {
                    cursor: 'pointer',
                    background: record.id === selectedWorkflowId ? '#e6f4ff' : undefined,
                  },
                })}
              />
            </div>
          </EntityDetails>
        )}
        detail={(
          <EntityDetails
            title="Workflow detail"
            loading={detailLoading}
            error={detailError}
            empty={!selectedWorkflowId || (!selectedWorkflow && !detailLoading)}
            emptyDescription="Select a workflow from the library to inspect authoring context and runtime posture."
            extra={selectedWorkflow ? (
              <Space wrap>
                <Button
                  data-testid="workflow-list-detail-open"
                  onClick={() => openWorkflow(selectedWorkflow.id, selectedWorkflow.is_system_managed)}
                >
                  {selectedWorkflow.is_system_managed ? 'Inspect workflow' : 'Edit workflow'}
                </Button>
                {!selectedWorkflow.is_system_managed ? (
                  <>
                    <Button
                      data-testid="workflow-list-detail-clone"
                      onClick={() => void handleClone(selectedWorkflow.id, selectedWorkflow.name)}
                    >
                      Clone
                    </Button>
                    <Button
                      type="primary"
                      data-testid="workflow-list-detail-execute"
                      disabled={!selectedWorkflow.is_valid}
                      onClick={() => navigate(buildWorkflowHref(selectedWorkflow.id, { databaseId: decisionDatabaseId, execute: true }))}
                    >
                      Execute
                    </Button>
                    <Popconfirm
                      title="Delete workflow?"
                      description="This action cannot be undone."
                      onConfirm={() => handleDelete(selectedWorkflow.id)}
                      okText="Delete"
                      okButtonProps={{ danger: true }}
                    >
                      <Button danger data-testid="workflow-list-detail-delete">Delete</Button>
                    </Popconfirm>
                  </>
                ) : null}
              </Space>
            ) : undefined}
          >
            {selectedWorkflow ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                {selectedWorkflow.is_system_managed ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="System-managed runtime projection"
                    description={selectedWorkflow.read_only_reason || 'This workflow is generated for runtime diagnostics and remains read-only.'}
                  />
                ) : null}

                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label="Name">
                    <Text strong data-testid="workflow-list-selected-name">{selectedWorkflow.name}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Workflow ID">
                    <Text code data-testid="workflow-list-selected-id">{selectedWorkflow.id}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Status">
                    {renderStatusSummary(selectedWorkflow)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Category">{selectedWorkflow.category}</Descriptions.Item>
                  <Descriptions.Item label="Workflow type">
                    <Tag color={workflowTypeColors[String(selectedWorkflow.workflow_type)] || 'default'}>
                      {String(selectedWorkflow.workflow_type || 'unknown')}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Management mode">{selectedWorkflow.management_mode}</Descriptions.Item>
                  <Descriptions.Item label="Visibility surface">{selectedWorkflow.visibility_surface}</Descriptions.Item>
                  <Descriptions.Item label="Version">{selectedWorkflow.version_number}</Descriptions.Item>
                  <Descriptions.Item label="Nodes">{selectedWorkflowNodeCount}</Descriptions.Item>
                  <Descriptions.Item label="Executions">{selectedWorkflowExecutionCount}</Descriptions.Item>
                  <Descriptions.Item label="Created by">
                    {selectedWorkflow.created_by_username || '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Created at">{formatDateTime(selectedWorkflow.created_at)}</Descriptions.Item>
                  <Descriptions.Item label="Updated at">{formatDateTime(selectedWorkflow.updated_at)}</Descriptions.Item>
                  <Descriptions.Item label="Description">{selectedWorkflow.description || '—'}</Descriptions.Item>
                </Descriptions>

                {selectedWorkflowDetail ? (
                  <>
                    <JsonBlock
                      title="DAG structure"
                      value={selectedWorkflowDetail.dag_structure}
                      dataTestId="workflow-list-selected-dag"
                      height={260}
                    />
                    <JsonBlock
                      title="Workflow config"
                      value={selectedWorkflowDetail.config ?? {}}
                      dataTestId="workflow-list-selected-config"
                      height={220}
                    />
                  </>
                ) : null}
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />
    </WorkspacePage>
  )
}

export default WorkflowList
