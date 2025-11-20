import { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Select, Breadcrumb, Modal, Form, message } from 'antd'
import { PlusOutlined, HomeOutlined, ClusterOutlined, RocketOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { databasesApi, Database } from '../../api/endpoints/databases'
import { clustersApi, Cluster } from '../../api/endpoints/clusters'
import { installationApi } from '../../api/endpoints/installation'
import { ExtensionFileSelector } from '../../components/Installation/ExtensionFileSelector'
import { InstallationProgressModal } from '../../components/Installation/InstallationProgressModal'

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

  // Загрузка кластеров
  useEffect(() => {
    const fetchClusters = async () => {
      try {
        const data = await clustersApi.list()
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
          data = await clustersApi.getDatabases(selectedClusterId)
        } else {
          // Загрузить все базы
          data = await databasesApi.list()
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

    // Найти выбранный кластер
    const cluster = value ? clusters.find((c) => c.id === value) : null
    setSelectedCluster(cluster || null)

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
        message.error('Выберите файл расширения');
        return;
      }

      const response = await installationApi.installSingle(selectedDatabase.id, {
        name: values.extension.name,
        path: values.extension.path,
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
      clustersApi.getDatabases(selectedClusterId).then(setDatabases)
    } else {
      databasesApi.list().then(setDatabases)
    }
  }

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
      onFilter: (value: any, record: Database) => record.status === value,
    },
    {
      title: 'Last Check',
      dataIndex: 'last_check',
      key: 'last_check',
      render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
    },
    {
      title: 'Action',
      key: 'action',
      width: 150,
      render: (_: any, record: Database) => (
        <Button
          size="small"
          type="primary"
          icon={<RocketOutlined />}
          onClick={() => handleInstallExtension(record)}
          disabled={record.status !== 'active'}
        >
          Install Extension
        </Button>
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
            loading={clusters.length === 0}
          >
            {clusters.map((cluster) => (
              <Select.Option key={cluster.id} value={cluster.id}>
                {cluster.name} ({cluster.databases_count || 0} databases)
              </Select.Option>
            ))}
          </Select>
        </Space>
        <Button type="primary" icon={<PlusOutlined />}>
          Add Database
        </Button>
      </Space>

      <Table
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
          fetchStatus={installationApi.getDatabaseStatus}
        />
      )}
    </div>
  )
}

