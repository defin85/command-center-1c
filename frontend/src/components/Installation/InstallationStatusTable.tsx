import React, { useState, useEffect } from 'react'
import { App, Table, Tag, Button, Input, Select, Space, Modal, Form } from 'antd'
import { ReloadOutlined, SearchOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { ExtensionInstallation } from '../../types/installation'
import { getV2 } from '../../api/generated'
import { convertInstallationsToLegacy } from '../../utils/installationTransforms'
import { ExtensionFileSelector } from './ExtensionFileSelector'

const { Option } = Select

// Get generated API functions
const api = getV2()

export const InstallationStatusTable: React.FC = () => {
  const { message } = App.useApp()
  const [installations, setInstallations] = useState<ExtensionInstallation[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<string>('all')
  const [searchText, setSearchText] = useState('')
  const [modalVisible, setModalVisible] = useState(false)
  const [selectedDatabase, setSelectedDatabase] = useState<{ id: string; name: string } | null>(null)
  const [form] = Form.useForm()

  const fetchInstallations = async () => {
    setLoading(true)
    try {
      const response = await api.getExtensionsListExtensions()
      // Transform generated response to legacy format
      setInstallations(convertInstallationsToLegacy(response.extensions))
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

  const handleRetry = async (databaseId: string) => {
    try {
      await api.postExtensionsRetryInstallation({ database_id: databaseId })
      message.success('Installation retry started')
      fetchInstallations()
    } catch (error) {
      console.error('Failed to retry installation:', error)
      message.error('Failed to retry installation')
    }
  }

  const handleInstallSingle = async (databaseId: string, databaseName: string) => {
    setSelectedDatabase({ id: databaseId, name: databaseName })
    setModalVisible(true)
  }

  const handleConfirmInstall = async () => {
    if (!selectedDatabase) return

    try {
      const values = await form.validateFields()
      const result = await api.postExtensionsBatchInstall({
        database_ids: [selectedDatabase.id],
        extension_name: values.extension_name,
        extension_path: values.extension_path,
      })
      message.success(`Installation queued: ${result.queued}, skipped: ${result.skipped}`)
      setModalVisible(false)
      form.resetFields()
      fetchInstallations()
    } catch (error) {
      console.error('Failed to start installation:', error)
      message.error('Failed to start installation')
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
      width: 180,
      render: (_: any, record: ExtensionInstallation) => (
        <Space>
          {record.status === 'failed' && (
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => handleRetry(record.database_id)}
            >
              Retry
            </Button>
          )}
          {!['in_progress', 'pending'].includes(record.status) && (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleInstallSingle(record.database_id, record.database_name)}
            >
              Install
            </Button>
          )}
        </Space>
      ),
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

      <Modal
        title={`Install Extension on ${selectedDatabase?.name}`}
        open={modalVisible}
        onOk={handleConfirmInstall}
        onCancel={() => setModalVisible(false)}
        okText="Install"
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
        >
          <ExtensionFileSelector
            value={form.getFieldValue('extension_file')}
            onChange={(fileInfo) => {
              // Update form fields when file selected
              form.setFieldsValue({
                extension_file: fileInfo,
                extension_name: fileInfo.name,
                extension_path: fileInfo.path,
              })
            }}
          />

          <Form.Item name="extension_name" hidden>
            <Input />
          </Form.Item>

          <Form.Item name="extension_path" hidden>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
