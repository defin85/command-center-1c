import { useState, useEffect, useCallback } from 'react'
import { Table, Button, Space, Tag, Select, Breadcrumb, Modal, Form, message } from 'antd'
import type { TableRowSelection } from 'antd/es/table/interface'
import { PlusOutlined, HomeOutlined, ClusterOutlined, RocketOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getV2 } from '../../api/generated'
import type { Cluster } from '../../api/generated/model/cluster'
import type { Database } from '../../api/generated/model/database'
import { customInstance } from '../../api/mutator'
import { extractInstallationFromStatus } from '../../utils/installationTransforms'
import { ExtensionFileSelector } from '../../components/Installation/ExtensionFileSelector'
import { InstallationProgressModal } from '../../components/Installation/InstallationProgressModal'
import type { ExtensionInstallation } from '../../types/installation'
import { DatabaseActionsMenu, BulkActionsToolbar, OperationConfirmModal } from '../../components/actions'
import { useDatabaseActions } from '../../hooks/useDatabaseActions'
import type { DatabaseActionKey } from '../../components/actions'
import type { RASOperationType } from '../../api/operations'

// Get generated API functions
const api = getV2()

// InstallSingle API response type (not in generated yet)
interface InstallSingleResponse {
  task_id: string
  operation_id: string
  message: string
  status: string
  queued_count?: number
}

export const Databases = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const clusterIdFromUrl = searchParams.get('cluster')

  const [databases, setDatabases] = useState<Database[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedClusterId, setSelectedClusterId] = useState<string | undefined>(
    clusterIdFromUrl || undefined
  )
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null)
  const [modalVisible, setModalVisible] = useState(false)
  const [progressModalVisible, setProgressModalVisible] = useState(false)
  const [selectedDatabase, setSelectedDatabase] = useState<Database | null>(null)
  const [currentOperationId, setCurrentOperationId] = useState<string | null>(null)
  const [form] = Form.useForm()

  // Row selection state
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedDatabases, setSelectedDatabases] = useState<Database[]>([])

  // Confirm modal state
  const [confirmModal, setConfirmModal] = useState<{
    visible: boolean
    operation: string
    databases: Array<{ id: string; name: string }>
  }>({ visible: false, operation: '', databases: [] })

  // Hook for RAS operations
  const { execute: executeAction, loading: actionLoading } = useDatabaseActions()

  // Загрузка кластеров
  useEffect(() => {
    const fetchClusters = async () => {
      try {
        const response = await api.getClustersListClusters()
        const data = response.clusters ?? []
        setClusters(data)

        // Найти выбранный кластер
        if (clusterIdFromUrl) {
          const cluster = data.find((c) => c.id === clusterIdFromUrl)
          setSelectedCluster(cluster || null)
        }
      } catch (error) {
        console.error('Failed to load clusters:', error)
      }
    }
    fetchClusters()
  }, [clusterIdFromUrl])

  // Загрузка баз данных
  useEffect(() => {
    const fetchDatabases = async () => {
      try {
        setLoading(true)
        let data: Database[]

        if (selectedClusterId) {
          // Загрузить базы конкретного кластера
          const response = await api.getClustersGetClusterDatabases({ cluster_id: selectedClusterId })
          data = response.databases ?? []
        } else {
          // Загрузить все базы
          const response = await api.getDatabasesListDatabases()
          data = response.databases ?? []
        }

        setDatabases(data)
      } catch (error) {
        console.error('Failed to load databases:', error)
        setDatabases([])
      } finally {
        setLoading(false)
      }
    }

    fetchDatabases()
  }, [selectedClusterId])

  const handleClusterChange = (value: string | undefined) => {
    setSelectedClusterId(value)

    // Найти выбранный кластер (defensive: handle undefined clusters)
    const cluster = value ? (clusters ?? []).find((c) => c.id === value) : null
    setSelectedCluster(cluster ?? null)

    // Обновить URL
    if (value) {
      navigate(`/databases?cluster=${value}`, { replace: true })
    } else {
      navigate('/databases', { replace: true })
    }
  }

  const handleInstallExtension = (database: Database) => {
    setSelectedDatabase(database)
    setModalVisible(true)
  }

  const handleConfirmInstall = async () => {
    if (!selectedDatabase) return

    try {
      const values = await form.validateFields()

      if (!values.extension || !values.extension.name || !values.extension.path) {
        message.error('Vyberite fayl rasshireniya');
        return;
      }

      // installSingle endpoint not in generated API yet, use customInstance directly
      const response = await customInstance<InstallSingleResponse>({
        url: '/extensions/install-single/',
        method: 'POST',
        data: {
          database_id: selectedDatabase.id,
          extension_name: values.extension.name,
          extension_path: values.extension.path,
        },
      })

      // Сохранить Operation ID для мониторинга
      if (response.operation_id) {
        setCurrentOperationId(response.operation_id)
      }

      // Закрыть модалку выбора файла
      setModalVisible(false)
      form.resetFields()

      // Открыть модалку прогресса
      setProgressModalVisible(true)

      // Показать сообщение с Operation ID
      message.success({
        content: (
          <div>
            <div>{response.message}</div>
            {response.operation_id && (
              <div style={{ fontSize: '12px', marginTop: '4px', color: '#666' }}>
                Operation ID: {response.operation_id}
              </div>
            )}
          </div>
        ),
        duration: 5,
      })
    } catch (error) {
      console.error('Failed to start installation:', error)
      message.error('Failed to start installation')
    }
  }

  const handleProgressModalClose = () => {
    setProgressModalVisible(false)
    setSelectedDatabase(null)
    // Обновить список баз данных после завершения
    if (selectedClusterId) {
      api.getClustersGetClusterDatabases({ cluster_id: selectedClusterId })
        .then((response) => setDatabases(response.databases ?? []))
    } else {
      api.getDatabasesListDatabases()
        .then((response) => setDatabases(response.databases ?? []))
    }
  }

  // Row selection configuration
  const rowSelection: TableRowSelection<Database> = {
    selectedRowKeys,
    onChange: (keys, rows) => {
      setSelectedRowKeys(keys)
      setSelectedDatabases(rows)
    },
    getCheckboxProps: (record) => ({
      disabled: record.status === 'maintenance',
    }),
  }

  // Handler for single database action (context menu)
  const handleSingleAction = useCallback((action: DatabaseActionKey, database: Database) => {
    if (action === 'more') {
      // Open Operations Wizard with preselected database
      navigate(`/operations?wizard=true&databases=${database.id}`)
      return
    }

    if (action === 'health_check') {
      // Health check has separate flow - show confirm for single DB
      setConfirmModal({
        visible: true,
        operation: action,
        databases: [{ id: database.id, name: database.name }],
      })
      return
    }

    // Show confirm modal for other actions
    setConfirmModal({
      visible: true,
      operation: action,
      databases: [{ id: database.id, name: database.name }],
    })
  }, [navigate])

  // Handler for bulk action
  const handleBulkAction = useCallback((action: string) => {
    setConfirmModal({
      visible: true,
      operation: action,
      databases: selectedDatabases.map((db) => ({ id: db.id, name: db.name })),
    })
  }, [selectedDatabases])

  // Confirm operation handler
  const handleConfirmOperation = useCallback(async (config?: { message?: string }) => {
    const operationType = confirmModal.operation as RASOperationType
    const databases = confirmModal.databases

    const operationId = await executeAction(operationType, databases, config)

    setConfirmModal({ visible: false, operation: '', databases: [] })
    setSelectedRowKeys([])
    setSelectedDatabases([])

    if (operationId) {
      // Navigate to Operations Center to track the operation
      navigate(`/operations?operation=${operationId}`)
    }
  }, [confirmModal, executeAction, navigate])

  // Clear selection handler
  const handleClearSelection = useCallback(() => {
    setSelectedRowKeys([])
    setSelectedDatabases([])
  }, [])

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: Database, b: Database) => a.name.localeCompare(b.name),
    },
    {
      title: 'Host',
      dataIndex: 'host',
      key: 'host',
    },
    {
      title: 'Port',
      dataIndex: 'port',
      key: 'port',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status}
        </Tag>
      ),
      filters: [
        { text: 'Active', value: 'active' },
        { text: 'Inactive', value: 'inactive' },
      ],
      onFilter: (value: boolean | React.Key, record: Database) => record.status === value,
    },
    {
      title: 'Last Check',
      dataIndex: 'last_check',
      key: 'last_check',
      render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: Database) => (
        <Space size="small">
          <Button
            size="small"
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => handleInstallExtension(record)}
            disabled={record.status !== 'active'}
          >
            Install
          </Button>
          <DatabaseActionsMenu
            databaseId={record.id}
            databaseStatus={record.status}
            onAction={(action) => handleSingleAction(action, record)}
            disabled={record.status !== 'active'}
          />
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* Breadcrumbs если пришли из кластера */}
      {selectedCluster && (
        <Breadcrumb style={{ marginBottom: 16 }}>
          <Breadcrumb.Item href="/">
            <HomeOutlined />
          </Breadcrumb.Item>
          <Breadcrumb.Item href="/clusters">
            <ClusterOutlined />
            <span>Clusters</span>
          </Breadcrumb.Item>
          <Breadcrumb.Item>{selectedCluster.name}</Breadcrumb.Item>
          <Breadcrumb.Item>Databases</Breadcrumb.Item>
        </Breadcrumb>
      )}

      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Space>
          <h1>Databases</h1>
          <Select
            style={{ width: 250 }}
            placeholder="All Clusters"
            allowClear
            value={selectedClusterId}
            onChange={handleClusterChange}
            loading={!clusters || clusters.length === 0}
          >
            {(clusters ?? []).map((cluster) => (
              <Select.Option key={cluster.id} value={cluster.id}>
                {cluster.name} ({cluster.databases_count ?? 0} databases)
              </Select.Option>
            ))}
          </Select>
        </Space>
        <Button type="primary" icon={<PlusOutlined />}>
          Add Database
        </Button>
      </Space>

      <BulkActionsToolbar
        selectedCount={selectedRowKeys.length}
        onAction={handleBulkAction}
        onClearSelection={handleClearSelection}
        loading={actionLoading}
      />

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={databases}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 50 }}
      />

      <Modal
        title={`Install Extension on ${selectedDatabase?.name}`}
        open={modalVisible}
        onOk={handleConfirmInstall}
        onCancel={() => setModalVisible(false)}
        okText="Install"
        width={700}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="extension"
            rules={[{ required: true, message: 'Выберите файл расширения' }]}
          >
            <ExtensionFileSelector />
          </Form.Item>
        </Form>
      </Modal>

      {/* Progress Modal с Operation ID внутри */}
      {selectedDatabase && (
        <InstallationProgressModal
          visible={progressModalVisible}
          databaseId={selectedDatabase.id}
          databaseName={selectedDatabase.name}
          operationId={currentOperationId || undefined}
          onClose={handleProgressModalClose}
          fetchStatus={async (databaseId: string): Promise<ExtensionInstallation | null> => {
            try {
              const response = await api.getExtensionsGetInstallStatus({ database_id: databaseId })
              return extractInstallationFromStatus(response)
            } catch (error: unknown) {
              // If installation not found, return null
              if (
                error &&
                typeof error === 'object' &&
                'response' in error &&
                (error as { response?: { status?: number } }).response?.status === 404
              ) {
                return null
              }
              throw error
            }
          }}
        />
      )}

      {/* Operation Confirm Modal for RAS actions */}
      <OperationConfirmModal
        visible={confirmModal.visible}
        operation={confirmModal.operation}
        databases={confirmModal.databases}
        onConfirm={handleConfirmOperation}
        onCancel={() => setConfirmModal({ visible: false, operation: '', databases: [] })}
        loading={actionLoading}
      />
    </div>
  )
}

