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
import { Link, useNavigate } from 'react-router-dom'
import {
  App,
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

const { Title } = Typography

const workflowTypeColors: Record<string, string> = {
  sequential: 'blue',
  parallel: 'green',
  conditional: 'orange',
  complex: 'purple'
}

const WorkflowList = () => {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const queryClient = useQueryClient()
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
      navigate(`/workflows/${cloned.workflow.id}`)
    } catch (_error) {
      message.error('Failed to clone workflow')
    }
  }, [message, navigate])

  const columns: ColumnsType<WorkflowTemplateList> = useMemo(() => ([
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <Link to={`/workflows/${record.id}`}>{name}</Link>
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
          <Tooltip title="Edit">
            <Button
              icon={<EditOutlined />}
              size="small"
              aria-label="Edit workflow"
              onClick={() => navigate(`/workflows/${record.id}`)}
            />
          </Tooltip>
          <Tooltip title="Clone">
            <Button
              icon={<CopyOutlined />}
              size="small"
              aria-label="Clone workflow"
              onClick={() => handleClone(record.id, record.name)}
            />
          </Tooltip>
          <Tooltip title="Execute">
            <Button
              icon={<PlayCircleOutlined />}
              size="small"
              aria-label="Execute workflow"
              disabled={!record.is_valid}
              onClick={() => navigate(`/workflows/${record.id}?execute=true`)}
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
        </Space>
      )
    }
  ]), [handleClone, handleDelete, navigate])

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
      table.search,
      table.filtersPayload,
      table.sortPayload,
      table.pagination.page,
      table.pagination.pageSize
    ],
    queryFn: () => api.getWorkflowsListWorkflows({
      search: table.search || undefined,
      filters: filtersParam,
      sort: sortParam,
      limit: table.pagination.pageSize,
      offset: pageStart,
    }),
  })

  const workflows = workflowsQuery.data?.workflows ?? []
  const totalWorkflows = typeof workflowsQuery.data?.total === 'number'
    ? workflowsQuery.data.total
    : workflows.length

  return (
    <div className="workflow-list-page">
      <div className="page-header">
        <Title level={3}>Workflows</Title>
        <Space>
          <Button
            icon={<ClockCircleOutlined />}
            onClick={() => navigate('/workflows/executions')}
          >
            Executions
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/workflows/new')}
          >
            New Workflow
          </Button>
        </Space>
      </div>

      <TableToolkit
        table={table}
        data={workflows}
        total={totalWorkflows}
        loading={workflowsQuery.isLoading}
        rowKey="id"
        columns={columns}
        searchPlaceholder="Search workflows"
      />
    </div>
  )
}

export default WorkflowList
