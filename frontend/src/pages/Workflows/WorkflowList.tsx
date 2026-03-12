/**
 * WorkflowList - Page for listing and managing workflow templates.
 *
 * Features:
 * - List all workflow templates
 * - Filter by type, status
 * - Create new workflow
 * - Clone/Delete workflows
 */

import { useCallback, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  App,
  Alert,
  Button,
  Space,
  Tag,
  Typography,
  Popconfirm,
  Tooltip
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getV2 } from '../../api/generated'
import type { WorkflowTemplateList } from '../../api/generated/model'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import './WorkflowList.css'

const api = getV2()

const { Title, Text } = Typography

const workflowTypeColors: Record<string, string> = {
  sequential: 'blue',
  parallel: 'green',
  conditional: 'orange',
  complex: 'purple'
}

const WORKFLOW_LIBRARY_SURFACE = 'workflow_library'
const WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE = 'runtime_diagnostics'

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

const WorkflowList = () => {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { message } = App.useApp()
  const queryClient = useQueryClient()
  const surface = searchParams.get('surface') === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
    ? WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
    : WORKFLOW_LIBRARY_SURFACE
  const decisionDatabaseId = String(searchParams.get('database_id') || '').trim()
  const isRuntimeDiagnosticsSurface = surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE
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
    } catch (_error) {
      message.error('Failed to delete workflow')
    }
  }, [message, queryClient])

  const handleClone = useCallback(async (id: string, name: string) => {
    try {
      const cloned = await api.postWorkflowsCloneWorkflow({
        workflow_id: id,
        new_name: `${name} (Copy)`
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
        <Space>
          <Link to={buildWorkflowHref(record.id, { isSystemManaged: record.is_system_managed, databaseId: decisionDatabaseId })}>{name}</Link>
          {record.is_system_managed ? (
            <Tag color="gold">System managed</Tag>
          ) : null}
        </Space>
      )
    },
    {
      title: 'Type',
      dataIndex: 'workflow_type',
      key: 'workflow_type',
      render: (type) => (
        <Tag color={workflowTypeColors[type] || 'default'}>{type}</Tag>
      )
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (_value, record) => (
        <Space>
          {record.is_valid ? (
            <Tooltip title="Valid">
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
            </Tooltip>
          ) : (
            <Tooltip title="Invalid">
              <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
            </Tooltip>
          )}
          <Tag color={record.is_active ? 'green' : 'default'}>
            {record.is_active ? 'Active' : 'Inactive'}
          </Tag>
          {record.visibility_surface === WORKFLOW_RUNTIME_DIAGNOSTICS_SURFACE ? (
            <Tag color="geekblue">Runtime diagnostics</Tag>
          ) : (
            <Tag color="blue">Analyst library</Tag>
          )}
        </Space>
      )
    },
    {
      title: 'Nodes',
      key: 'node_count',
      dataIndex: 'node_count',
      render: (count) => count ?? 0
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (date) => new Date(date).toLocaleDateString()
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
              onClick={() => openWorkflow(record.id, record.is_system_managed)}
            />
          </Tooltip>
          {!record.is_system_managed ? (
            <>
              <Tooltip title="Clone">
                <Button
                  icon={<CopyOutlined />}
                  size="small"
                  aria-label="Clone scheme"
                  onClick={() => handleClone(record.id, record.name)}
                />
              </Tooltip>
              <Tooltip title="Execute">
                <Button
                  icon={<PlayCircleOutlined />}
                  size="small"
                  aria-label="Execute workflow"
                  disabled={!record.is_valid}
                  onClick={() => navigate(buildWorkflowHref(record.id, { databaseId: decisionDatabaseId, execute: true }))}
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
                  <Button icon={<DeleteOutlined />} size="small" danger aria-label="Delete workflow" />
                </Tooltip>
              </Popconfirm>
            </>
          ) : null}
        </Space>
      )
    }
  ]), [decisionDatabaseId, handleClone, handleDelete, openWorkflow])

  const table = useTableToolkit({
    tableId: 'workflows',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const filtersParam = table.filtersPayload ? JSON.stringify(table.filtersPayload) : undefined
  const sortParam = table.sortPayload ? JSON.stringify(table.sortPayload) : undefined

  const workflowsQuery = useQuery({
    queryKey: [
      'workflows',
      surface,
      table.search,
      table.filtersPayload,
      table.sortPayload,
      table.pagination.page,
      table.pagination.pageSize
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

  const workflows = workflowsQuery.data?.workflows ?? []
  const authoringPhase = workflowsQuery.data?.authoring_phase
  const totalWorkflows = typeof workflowsQuery.data?.total === 'number'
    ? workflowsQuery.data.total
    : workflows.length

  return (
    <div className="workflow-list-page">
      <div className="page-header">
        <div className="page-header-copy">
          <Title level={3}>
            {isRuntimeDiagnosticsSurface ? 'Workflow Runtime Projections' : 'Workflow Scheme Library'}
          </Title>
          <Text type="secondary" className="page-header-subtitle">
            {isRuntimeDiagnosticsSurface
              ? 'Read-only generated projections compiled from pool bindings and analyst-authored definitions.'
              : 'Reusable analyst-authored workflow definitions for pool distribution and publication.'}
          </Text>
        </div>
        <Space>
          <Button
            icon={<ClockCircleOutlined />}
            onClick={() => navigate('/workflows/executions')}
          >
            Executions
          </Button>
          <Button
            onClick={() => {
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
      </div>

      {isRuntimeDiagnosticsSurface ? (
        <Alert
          showIcon
          type="warning"
          message="Runtime diagnostics surface"
          description="System-managed runtime workflow projections are listed separately and remain read-only."
          style={{ marginBottom: 16 }}
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
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <TableToolkit
        table={table}
        data={workflows}
        total={totalWorkflows}
        loading={workflowsQuery.isLoading}
        rowKey="id"
        columns={columns}
        searchPlaceholder="Search workflow schemes"
      />
    </div>
  )
}

export default WorkflowList
