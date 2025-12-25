import React, { useMemo, useState, useEffect } from 'react'
import { App, Tag, Button, Space, Modal, Form, Input } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { ExtensionInstallation } from '../../types/installation'
import { getV2 } from '../../api/generated'
import { convertInstallationsToLegacy } from '../../utils/installationTransforms'
import { ExtensionFileSelector } from './ExtensionFileSelector'
import { TableToolkit } from '../table/TableToolkit'
import { useTableToolkit } from '../table/hooks/useTableToolkit'

// Get generated API functions
const api = getV2()

export const InstallationStatusTable: React.FC = () => {
  const { message } = App.useApp()
  const [installations, setInstallations] = useState<ExtensionInstallation[]>([])
  const [loading, setLoading] = useState(false)
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

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'database_id', label: 'Database ID', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'database_name', label: 'Database Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'status', groupLabel: 'Status' },
    { key: 'duration_seconds', label: 'Duration', sortable: true, groupKey: 'timing', groupLabel: 'Timing' },
    { key: 'started_at', label: 'Started At', sortable: true, groupKey: 'timing', groupLabel: 'Timing' },
    { key: 'error_message', label: 'Error', groupKey: 'details', groupLabel: 'Details' },
    { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const columns: ColumnsType<ExtensionInstallation> = useMemo(() => ([
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
      key: 'actions',
      width: 180,
      render: (_: unknown, record: ExtensionInstallation) => (
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
  ]), [handleInstallSingle, handleRetry])

  const table = useTableToolkit({
    tableId: 'extensions_installations',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const filteredInstallations = useMemo(() => {
    const searchValue = table.search.trim().toLowerCase()
    return installations.filter((item) => {
      if (searchValue) {
        const matchesSearch = [
          item.database_name,
          item.database_id,
          item.status,
          item.error_message ?? '',
        ].some((value) => String(value || '').toLowerCase().includes(searchValue))
        if (!matchesSearch) return false
      }

      for (const [key, value] of Object.entries(table.filters)) {
        if (value === null || value === undefined || value === '') {
          continue
        }
        const recordValue = (() => {
          switch (key) {
            case 'database_id':
              return item.database_id
            case 'database_name':
              return item.database_name
            case 'status':
              return item.status
            case 'duration_seconds':
              return item.duration_seconds
            case 'started_at':
              return item.started_at
            case 'error_message':
              return item.error_message
            default:
              return null
          }
        })()

        if (Array.isArray(value)) {
          if (!value.map(String).includes(String(recordValue ?? ''))) {
            return false
          }
          continue
        }

        if (typeof value === 'boolean') {
          if (Boolean(recordValue) !== value) return false
          continue
        }

        if (typeof value === 'number') {
          if (Number(recordValue) !== value) return false
          continue
        }

        const needle = String(value).toLowerCase()
        const haystack = String(recordValue ?? '').toLowerCase()
        if (!haystack.includes(needle)) return false
      }

      return true
    })
  }, [installations, table.filters, table.search])

  const sortedInstallations = useMemo(() => {
    if (!table.sort.key || !table.sort.order) {
      return filteredInstallations
    }
    const key = table.sort.key
    const direction = table.sort.order === 'asc' ? 1 : -1
    const getValue = (item: ExtensionInstallation) => {
      switch (key) {
        case 'database_id':
          return item.database_id
        case 'database_name':
          return item.database_name
        case 'status':
          return item.status
        case 'duration_seconds':
          return item.duration_seconds ?? -1
        case 'started_at':
          return item.started_at ? Date.parse(item.started_at) : -1
        case 'error_message':
          return item.error_message ?? ''
        default:
          return ''
      }
    }
    return [...filteredInstallations].sort((a, b) => {
      const left = getValue(a)
      const right = getValue(b)
      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * direction
      }
      return String(left).localeCompare(String(right)) * direction
    })
  }, [filteredInstallations, table.sort.key, table.sort.order])

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const pageItems = sortedInstallations.slice(pageStart, pageStart + table.pagination.pageSize)

  return (
    <div>
      <TableToolkit
        table={table}
        data={pageItems}
        total={sortedInstallations.length}
        loading={loading}
        rowKey="id"
        columns={columns}
        searchPlaceholder="Search installations"
        toolbarActions={(
          <Button icon={<ReloadOutlined />} onClick={fetchInstallations}>
            Refresh
          </Button>
        )}
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
