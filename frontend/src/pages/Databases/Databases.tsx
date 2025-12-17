import { useState, useCallback, useMemo } from 'react'
import { App, Table, Button, Space, Tag, Select, Breadcrumb, Modal, Form, Typography, Dropdown } from 'antd'
import type { TableRowSelection } from 'antd/es/table/interface'
import { PlusOutlined, HomeOutlined, ClusterOutlined, RocketOutlined, HeartOutlined, EditOutlined, DownOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { getV2 } from '../../api/generated'
import type { Database } from '../../api/generated/model/database'
import { SetDatabaseStatusRequestStatus } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import type { SetDatabaseStatusRequestStatus as SetDatabaseStatusValue } from '../../api/generated/model/setDatabaseStatusRequestStatus'
import { extractInstallationFromStatus } from '../../utils/installationTransforms'
import { ExtensionFileSelector } from '../../components/Installation/ExtensionFileSelector'
import { InstallationProgressModal } from '../../components/Installation/InstallationProgressModal'
import type { ExtensionInstallation } from '../../types/installation'
import { DatabaseActionsMenu, BulkActionsToolbar, OperationConfirmModal } from '../../components/actions'
import type { DatabaseActionKey } from '../../components/actions'
import type { RASOperationType } from '../../api/operations'
import { queryKeys } from '../../api/queries'
import { useDatabases, useExecuteRasOperation, useInstallExtension, useHealthCheckDatabase, useBulkHealthCheckDatabases, useSetDatabaseStatus } from '../../api/queries/databases'
import { useClusters } from '../../api/queries/clusters'

// Get generated API functions (for fetchStatus in InstallationProgressModal)
const api = getV2()

export const Databases = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message, modal } = App.useApp()
  const [searchParams] = useSearchParams()
  const clusterIdFromUrl = searchParams.get('cluster')

  // UI State
  const [selectedClusterId, setSelectedClusterId] = useState<string | undefined>(
    clusterIdFromUrl || undefined
  )
  const [modalVisible, setModalVisible] = useState(false)
  const [progressModalVisible, setProgressModalVisible] = useState(false)
  const [selectedDatabase, setSelectedDatabase] = useState<Database | null>(null)
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

  // React Query hooks
  const { data: clusters = [], isLoading: clustersLoading } = useClusters()
  const { data: databases = [], isLoading: databasesLoading } = useDatabases({
    filters: selectedClusterId ? { cluster_id: selectedClusterId } : undefined,
  })

  // Mutations
  const executeRasOperation = useExecuteRasOperation()
  const installExtension = useInstallExtension()
  const healthCheck = useHealthCheckDatabase()
  const bulkHealthCheck = useBulkHealthCheckDatabases()
  const setDatabaseStatus = useSetDatabaseStatus()

  // Derived state: selected cluster object
  const selectedCluster = useMemo(() => {
    if (!selectedClusterId || !clusters.length) return null
    return clusters.find((c) => c.id === selectedClusterId) || null
  }, [selectedClusterId, clusters])

  type AxiosErrorLike = { response?: { status?: number }; message?: string }

  const getErrorStatus = (error: unknown): number | undefined => {
    const maybe = error as AxiosErrorLike | null
    return maybe?.response?.status
  }

  const getErrorMessage = (error: unknown): string => {
    const maybe = error as AxiosErrorLike | null
    return maybe?.message || 'unknown error'
  }

  const handleClusterChange = (value: string | undefined) => {
    setSelectedClusterId(value)

    // Update URL
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
        message.error('Vyberite fayl rasshireniya')
        return
      }

      installExtension.mutate(
        {
          databaseId: selectedDatabase.id,
          extensionName: values.extension.name,
          extensionPath: values.extension.path,
        },
        {
          onSuccess: (response) => {
            // Close file selection modal
            setModalVisible(false)
            form.resetFields()

            // Open progress modal
            setProgressModalVisible(true)

            // Show message
            message.success({
              content: (
                <div>
                  <div>{response.message}</div>
                </div>
              ),
              duration: 5,
            })
          },
        }
      )
    } catch (error) {
      console.error('Failed to validate form:', error)
    }
  }

  const handleProgressModalClose = () => {
    setProgressModalVisible(false)
    setSelectedDatabase(null)
    // Invalidate databases query to refresh data
    queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
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

  const runBulkHealthCheck = useCallback(async (ids: string[]) => {
    const chunks: string[][] = []
    for (let i = 0; i < ids.length; i += 50) chunks.push(ids.slice(i, i + 50))

    let ok = 0
    let degraded = 0
    let down = 0

    for (let i = 0; i < chunks.length; i++) {
      const res = await bulkHealthCheck.mutateAsync({ databaseIds: chunks[i] })
      ok += res.summary.healthy
      degraded += res.summary.degraded
      down += res.summary.down
    }

    modal.info({
      title: 'Health check completed',
      content: `ok=${ok}, degraded=${degraded}, down=${down}`,
    })
  }, [bulkHealthCheck, modal])

  const runSetStatus = useCallback(async (ids: string[], status: SetDatabaseStatusValue) => {
    const res = await setDatabaseStatus.mutateAsync({ databaseIds: ids, status })
    message.success(res.message)
  }, [setDatabaseStatus, message])

  // Handler for single database action (context menu)
  const handleSingleAction = useCallback((action: DatabaseActionKey, database: Database) => {
    if (action === 'more') {
      // Open Operations Wizard with preselected database
      navigate(`/operations?wizard=true&databases=${database.id}`)
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
    const dbs = confirmModal.databases

    executeRasOperation.mutate(
      {
        operationType,
        databaseIds: dbs.map((db) => db.id),
        config,
      },
      {
        onSuccess: (data) => {
          setConfirmModal({ visible: false, operation: '', databases: [] })
          setSelectedRowKeys([])
          setSelectedDatabases([])

          if (data.operation_id) {
            // Navigate to Operations Center to track the operation
            navigate(`/operations?operation=${data.operation_id}`)
          }
        },
      }
    )
  }, [confirmModal, executeRasOperation, navigate])

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
        <Tag color={status === 'active' ? 'green' : status === 'maintenance' ? 'orange' : status === 'inactive' ? 'default' : 'red'}>
          {status}
        </Tag>
      ),
      filters: [
        { text: 'Active', value: 'active' },
        { text: 'Inactive', value: 'inactive' },
        { text: 'Maintenance', value: 'maintenance' },
        { text: 'Error', value: 'error' },
      ],
      onFilter: (value: boolean | React.Key, record: Database) => record.status === value,
    },
    {
      title: 'Health',
      dataIndex: 'last_check_status',
      key: 'last_check_status',
      render: (status: string) => (
        <Tag color={status === 'ok' ? 'green' : status === 'degraded' ? 'orange' : status === 'down' ? 'red' : 'default'}>
          {status}
        </Tag>
      ),
      filters: [
        { text: 'OK', value: 'ok' },
        { text: 'Degraded', value: 'degraded' },
        { text: 'Down', value: 'down' },
        { text: 'Unknown', value: 'unknown' },
      ],
      onFilter: (value: boolean | React.Key, record: Database) => record.last_check_status === value,
      width: 120,
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
      width: 260,
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
          <Button
            size="small"
            icon={<HeartOutlined />}
            onClick={async () => {
              try {
                const res = await healthCheck.mutateAsync(record.id)
                message.success(`${record.name}: ${res.status} (${res.response_time_ms}ms)`)
              } catch (e: unknown) {
                message.error(`Health check failed: ${getErrorMessage(e)}`)
              }
            }}
            loading={healthCheck.isPending}
          >
            Check
          </Button>
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                { key: SetDatabaseStatusRequestStatus.active, label: 'Set Active' },
                { key: SetDatabaseStatusRequestStatus.inactive, label: 'Set Inactive' },
                { key: SetDatabaseStatusRequestStatus.maintenance, label: 'Set Maintenance' },
              ],
              onClick: async ({ key }) => {
                try {
                  await runSetStatus([record.id], key as SetDatabaseStatusValue)
                } catch (e: unknown) {
                  const status = getErrorStatus(e)
                  if (status === 403) {
                    message.error('Set status requires staff access')
                    return
                  }
                  message.error(`Set status failed: ${getErrorMessage(e)}`)
                }
              },
            }}
          >
            <Button size="small" icon={<EditOutlined />}>
              Status <DownOutlined />
            </Button>
          </Dropdown>
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
            loading={clustersLoading}
          >
            {clusters.map((cluster) => (
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
        loading={executeRasOperation.isPending || bulkHealthCheck.isPending || setDatabaseStatus.isPending}
      />

      {selectedRowKeys.length > 0 && (
        <Space style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary">Ops:</Typography.Text>
          <Button
            icon={<HeartOutlined />}
            onClick={async () => {
              try {
                await runBulkHealthCheck(selectedDatabases.map((d) => d.id))
              } catch (e: unknown) {
                message.error(`Bulk health check failed: ${getErrorMessage(e)}`)
              }
            }}
            loading={bulkHealthCheck.isPending}
          >
            Health check
          </Button>
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                { key: SetDatabaseStatusRequestStatus.active, label: 'Set Active' },
                { key: SetDatabaseStatusRequestStatus.inactive, label: 'Set Inactive' },
                { key: SetDatabaseStatusRequestStatus.maintenance, label: 'Set Maintenance' },
              ],
              onClick: async ({ key }) => {
                try {
                  await runSetStatus(selectedDatabases.map((d) => d.id), key as SetDatabaseStatusValue)
                } catch (e: unknown) {
                  const status = getErrorStatus(e)
                  if (status === 403) {
                    message.error('Set status requires staff access')
                    return
                  }
                  message.error(`Set status failed: ${getErrorMessage(e)}`)
                }
              },
            }}
          >
            <Button icon={<EditOutlined />} loading={setDatabaseStatus.isPending}>
              Set status <DownOutlined />
            </Button>
          </Dropdown>
        </Space>
      )}

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={databases}
        loading={databasesLoading}
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
        confirmLoading={installExtension.isPending}
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
        loading={executeRasOperation.isPending}
      />
    </div>
  )
}
