/**
 * WorkflowList - Page for listing and managing workflow templates.
 *
 * Features:
 * - List all workflow templates
 * - Filter by type, status
 * - Create new workflow
 * - Clone/Delete workflows
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table,
  Button,
  Space,
  Tag,
  Typography,
  Card,
  Input,
  Select,
  Popconfirm,
  message,
  Tooltip
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SearchOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { getV2 } from '../../api/generated'
import type { WorkflowTemplateList } from '../../api/generated/model'
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
  const [templates, setTemplates] = useState<WorkflowTemplateList[]>([])
  const [loading, setLoading] = useState(true)
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0
  })
  const [filters, setFilters] = useState({
    search: '',
    workflow_type: '',
    is_active: undefined as boolean | undefined
  })
  const [searchValue, setSearchValue] = useState('')

  // Load templates
  const loadTemplates = async (page = 1) => {
    setLoading(true)
    try {
      const response = await api.getWorkflowsListWorkflows({
        limit: pagination.pageSize,
        offset: (page - 1) * pagination.pageSize,
        search: filters.search || undefined,
        workflow_type: filters.workflow_type || undefined,
        is_active: filters.is_active !== undefined ? String(filters.is_active) : undefined
      })
      setTemplates(response.workflows ?? [])
      setPagination((prev) => ({
        ...prev,
        current: page,
        total: response.total ?? 0
      }))
    } catch (_error) {
      message.error('Failed to load workflow templates')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTemplates()
  }, [filters])

  // Handle delete
  const handleDelete = async (id: string) => {
    try {
      await api.postWorkflowsDeleteWorkflow({ workflow_id: id })
      message.success('Workflow deleted')
      loadTemplates(pagination.current)
    } catch (_error) {
      message.error('Failed to delete workflow')
    }
  }

  // Handle clone
  const handleClone = async (id: string, name: string) => {
    try {
      const cloned = await api.postWorkflowsCloneWorkflow({
        workflow_id: id,
        new_name: `${name} (Copy)`
      })
      message.success('Workflow cloned')
      navigate(`/workflows/${cloned.id}`)
    } catch (_error) {
      message.error('Failed to clone workflow')
    }
  }

  const columns: ColumnsType<WorkflowTemplateList> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <a onClick={() => navigate(`/workflows/${record.id}`)}>{name}</a>
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
      key: 'status',
      render: (_, record) => (
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
      key: 'nodes',
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
      render: (_, record) => (
        <Space>
          <Tooltip title="Edit">
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => navigate(`/workflows/${record.id}`)}
            />
          </Tooltip>
          <Tooltip title="Clone">
            <Button
              icon={<CopyOutlined />}
              size="small"
              onClick={() => handleClone(record.id, record.name)}
            />
          </Tooltip>
          <Tooltip title="Execute">
            <Button
              icon={<PlayCircleOutlined />}
              size="small"
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
              <Button icon={<DeleteOutlined />} size="small" danger />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div className="workflow-list-page">
      <div className="page-header">
        <Title level={3}>Workflows</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/workflows/new')}
        >
          New Workflow
        </Button>
      </div>

      <Card className="filters-card">
        <Space wrap>
          <Space.Compact>
            <Input
              placeholder="Search workflows..."
              allowClear
              style={{ width: 200 }}
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onPressEnter={() => setFilters((prev) => ({ ...prev, search: searchValue }))}
            />
            <Button
              icon={<SearchOutlined />}
              onClick={() => setFilters((prev) => ({ ...prev, search: searchValue }))}
            />
          </Space.Compact>
          <Select
            placeholder="Workflow Type"
            allowClear
            style={{ width: 150 }}
            onChange={(value) => setFilters((prev) => ({ ...prev, workflow_type: value }))}
            options={[
              { value: 'sequential', label: 'Sequential' },
              { value: 'parallel', label: 'Parallel' },
              { value: 'conditional', label: 'Conditional' },
              { value: 'complex', label: 'Complex' }
            ]}
          />
          <Select
            placeholder="Status"
            allowClear
            style={{ width: 120 }}
            onChange={(value) => setFilters((prev) => ({ ...prev, is_active: value }))}
            options={[
              { value: true, label: 'Active' },
              { value: false, label: 'Inactive' }
            ]}
          />
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={templates}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            onChange: (page) => loadTemplates(page)
          }}
        />
      </Card>
    </div>
  )
}

export default WorkflowList
