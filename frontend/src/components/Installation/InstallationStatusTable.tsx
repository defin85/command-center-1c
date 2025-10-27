import React, { useState, useEffect } from 'react'
import { Table, Tag, Button, Input, Select, Space } from 'antd'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { ExtensionInstallation } from '../../types/installation'
import { installationApi } from '../../api/endpoints/installation'

const { Option } = Select

export const InstallationStatusTable: React.FC = () => {
  const [installations, setInstallations] = useState<ExtensionInstallation[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<string>('all')
  const [searchText, setSearchText] = useState('')

  const fetchInstallations = async () => {
    setLoading(true)
    try {
      const data = await installationApi.getAllInstallations()
      setInstallations(data)
    } catch (error) {
      console.error('Failed to fetch installations:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInstallations()
    const interval = setInterval(fetchInstallations, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleRetry = async (databaseId: number) => {
    try {
      await installationApi.retryInstallation(databaseId)
      fetchInstallations()
    } catch (error) {
      console.error('Failed to retry installation:', error)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'green'
      case 'failed':
        return 'red'
      case 'in_progress':
        return 'blue'
      case 'pending':
        return 'default'
      default:
        return 'default'
    }
  }

  const filteredData = installations.filter((item) => {
    if (filter !== 'all' && item.status !== filter) return false
    if (searchText && !item.database_name.toLowerCase().includes(searchText.toLowerCase()))
      return false
    return true
  })

  const columns = [
    {
      title: 'Database ID',
      dataIndex: 'database_id',
      key: 'database_id',
      width: 120,
    },
    {
      title: 'Database Name',
      dataIndex: 'database_name',
      key: 'database_name',
      width: 200,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 100,
      render: (seconds: number | null) => (seconds ? `${seconds}s` : '-'),
    },
    {
      title: 'Started At',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (date: string | null) => (date ? new Date(date).toLocaleString() : '-'),
    },
    {
      title: 'Error',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      render: (text: string | null) => text || '-',
    },
    {
      title: 'Action',
      key: 'action',
      width: 100,
      render: (_: any, record: ExtensionInstallation) =>
        record.status === 'failed' ? (
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => handleRetry(record.database_id)}
          >
            Retry
          </Button>
        ) : null,
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="Search database name"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 300 }}
        />
        <Select value={filter} onChange={setFilter} style={{ width: 150 }}>
          <Option value="all">All</Option>
          <Option value="completed">Completed</Option>
          <Option value="failed">Failed</Option>
          <Option value="in_progress">In Progress</Option>
          <Option value="pending">Pending</Option>
        </Select>
        <Button icon={<ReloadOutlined />} onClick={fetchInstallations}>
          Refresh
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={filteredData}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 50 }}
      />
    </div>
  )
}
