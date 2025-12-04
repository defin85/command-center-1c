import { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Progress, Modal, Typography } from 'antd'
import { ReloadOutlined, EyeOutlined, StopOutlined, MonitorOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { operationsApi, BatchOperation, Task } from '../../api/adapters/operations'
import type { ColumnsType } from 'antd/es/table'

const { Paragraph } = Typography

export const Operations = () => {
  const navigate = useNavigate()
  const [operations, setOperations] = useState<BatchOperation[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedOperation, setSelectedOperation] = useState<BatchOperation | null>(null)
  const [detailsVisible, setDetailsVisible] = useState(false)

  const fetchOperations = async () => {
    try {
      setLoading(true)
      const data = await operationsApi.list()
      setOperations(data)
    } catch (error) {
      console.error('Failed to load operations:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOperations()

    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchOperations, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleCancel = async (id: string) => {
    try {
      await operationsApi.cancel(id)
      fetchOperations()
    } catch (error) {
      console.error('Failed to cancel operation:', error)
    }
  }

  const showDetails = (operation: BatchOperation) => {
    setSelectedOperation(operation)
    setDetailsVisible(true)
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'default',
      queued: 'blue',
      processing: 'processing',
      completed: 'success',
      failed: 'error',
      cancelled: 'default'
    }
    return colors[status] || 'default'
  }

  const getOperationTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      create: 'Create',
      update: 'Update',
      delete: 'Delete',
      query: 'Query',
      install_extension: 'Install Extension'
    }
    return labels[type] || type
  }

  const columns: ColumnsType<BatchOperation> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 250,
    },
    {
      title: 'Operation ID',
      dataIndex: 'id',
      key: 'id',
      width: 200,
      render: (id: string) => (
        <Paragraph
          copyable={{ text: id, tooltips: ['Copy ID', 'Copied!'] }}
          style={{ marginBottom: 0, fontSize: '12px' }}
        >
          <code>{id.substring(0, 8)}...</code>
        </Paragraph>
      )
    },
    {
      title: 'Type',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 150,
      render: (type: string) => <Tag color="blue">{getOperationTypeLabel(type)}</Tag>
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 200,
      render: (_, record) => (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Progress percent={record.progress} size="small" />
          <span style={{ fontSize: '12px' }}>
            {record.completed_tasks}/{record.total_tasks} tasks
            {record.failed_tasks > 0 && ` (${record.failed_tasks} failed)`}
          </span>
        </Space>
      )
    },
    {
      title: 'Databases',
      dataIndex: 'database_names',
      key: 'databases',
      width: 150,
      render: (names: string[]) => `${names.length} db(s)`
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => new Date(date).toLocaleString()
    },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration',
      width: 100,
      render: (seconds: number | null) => {
        if (!seconds) return '-'
        return `${Math.round(seconds)}s`
      }
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => showDetails(record)}
          >
            Details
          </Button>
          {record.status === 'processing' && (
            <Button
              type="link"
              danger
              icon={<StopOutlined />}
              onClick={() => handleCancel(record.id)}
            >
              Cancel
            </Button>
          )}
        </Space>
      )
    }
  ]

  const taskColumns: ColumnsType<Task> = [
    {
      title: 'Database',
      dataIndex: 'database_name',
      key: 'database_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{status}</Tag>
    },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration',
      render: (seconds: number | null) => seconds ? `${seconds.toFixed(2)}s` : '-'
    },
    {
      title: 'Retries',
      dataIndex: 'retry_count',
      key: 'retry_count',
      render: (count: number, record) => `${count}/${record.max_retries}`
    },
    {
      title: 'Error',
      dataIndex: 'error_message',
      key: 'error',
      render: (error: string) => error ? <span style={{ color: 'red' }}>{error}</span> : '-'
    }
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <h1>Operations Monitor</h1>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={fetchOperations}
          loading={loading}
        >
          Refresh
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={operations}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={`Operation Details: ${selectedOperation?.name}`}
        open={detailsVisible}
        onCancel={() => setDetailsVisible(false)}
        width={1000}
        footer={null}
      >
        {selectedOperation && (
          <div>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {/* Operation ID с кнопкой Monitor Workflow */}
              <div style={{
                padding: '12px',
                background: '#f0f2f5',
                borderRadius: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <strong>Operation ID:</strong>
                  <Paragraph
                    copyable={{ text: selectedOperation.id }}
                    style={{ marginBottom: 0, marginLeft: 8, display: 'inline' }}
                  >
                    <code>{selectedOperation.id}</code>
                  </Paragraph>
                </div>
                <Button
                  type="primary"
                  icon={<MonitorOutlined />}
                  onClick={() => {
                    navigate(`/operation-monitor?operation=${selectedOperation.id}`)
                    setDetailsVisible(false)
                  }}
                >
                  Monitor Workflow
                </Button>
              </div>

              <div>
                <strong>Description:</strong> {selectedOperation.description}
              </div>
              <div>
                <strong>Type:</strong> {getOperationTypeLabel(selectedOperation.operation_type)}
              </div>
              <div>
                <strong>Target Entity:</strong> {selectedOperation.target_entity}
              </div>
              <div>
                <strong>Progress:</strong> <Progress percent={selectedOperation.progress} />
              </div>
              <div>
                <strong>Statistics:</strong> {selectedOperation.completed_tasks} completed, {selectedOperation.failed_tasks} failed, {selectedOperation.total_tasks} total
              </div>

              <h3>Tasks</h3>
              <Table
                columns={taskColumns}
                dataSource={selectedOperation.tasks}
                rowKey="id"
                pagination={false}
                size="small"
              />
            </Space>
          </div>
        )}
      </Modal>
    </div>
  )
}
