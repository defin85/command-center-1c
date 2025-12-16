import { useState } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, Popconfirm, Select, App } from 'antd'
import { PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined, DatabaseOutlined, SearchOutlined, UnlockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { Cluster } from '../../api/generated/model/cluster'
import { DiscoverClustersModal } from '../../components/clusters/DiscoverClustersModal'
import {
    useClusters,
    useSystemConfig,
    useCreateCluster,
    useUpdateCluster,
    useDeleteCluster,
    useSyncCluster,
    useResetClusterSyncStatus,
} from '../../api/queries/clusters'

const { TextArea } = Input

export const Clusters = () => {
    const navigate = useNavigate()
    const { message } = App.useApp()

    // UI state
    const [modalVisible, setModalVisible] = useState(false)
    const [editingCluster, setEditingCluster] = useState<Cluster | null>(null)
    const [discoverModalVisible, setDiscoverModalVisible] = useState(false)
    const [selectedClusterIds, setSelectedClusterIds] = useState<string[]>([])
    const [resettingClusterId, setResettingClusterId] = useState<string | null>(null)
    const [form] = Form.useForm()

    // React Query hooks
    const { data: clusters = [], isLoading } = useClusters()
    const { data: systemConfig } = useSystemConfig()

    // Mutations
    const createCluster = useCreateCluster()
    const updateCluster = useUpdateCluster()
    const deleteCluster = useDeleteCluster()
    const syncCluster = useSyncCluster()
    const resetSyncStatus = useResetClusterSyncStatus()

    const handleCreate = () => {
        setEditingCluster(null)
        form.resetFields()
        form.setFieldsValue({
            ras_server: systemConfig?.ras_default_server ?? 'localhost:1545',
            cluster_service_url: systemConfig?.ras_adapter_url ?? 'http://localhost:8188',
            status: 'active',
        })
        setModalVisible(true)
    }

    const handleEdit = (cluster: Cluster) => {
        setEditingCluster(cluster)
        form.setFieldsValue(cluster)
        setModalVisible(true)
    }

    const handleDelete = (id: string) => {
        deleteCluster.mutate(id, {
            onSuccess: () => {
                message.success('Cluster deleted successfully')
            },
            onError: (error: Error) => {
                message.error('Failed to delete cluster: ' + error.message)
            },
        })
    }

    const handleSync = (id: string, name: string) => {
        message.loading({ content: `Syncing ${name}...`, key: 'sync' })

        syncCluster.mutate(id, {
            onSuccess: (result) => {
                // databases_found may be undefined if sync is async
                const dbInfo = result.databases_found !== undefined
                    ? `. Found ${result.databases_found} databases.`
                    : ''
                message.success({
                    content: `${result.message}${dbInfo}`,
                    key: 'sync',
                })
            },
            onError: (error: Error) => {
                message.error({ content: 'Sync failed: ' + error.message, key: 'sync' })
            },
        })
    }

    const handleResetSyncStatus = async (clusterId: string, clusterName?: string) => {
        try {
            setResettingClusterId(clusterId)
            const result = await resetSyncStatus.mutateAsync({ cluster_id: clusterId })
            message.success(result.message || `Reset sync status for ${clusterName ?? clusterId}`)
        } catch (error: any) {
            message.error(`Reset sync status failed: ${error?.message ?? 'unknown error'}`)
        } finally {
            setResettingClusterId(null)
        }
    }

    const handleBulkResetSyncStatus = () => {
        if (selectedClusterIds.length === 0) return

        Modal.confirm({
            title: 'Reset sync status?',
            content: `Reset sync status for ${selectedClusterIds.length} selected cluster(s).`,
            okText: 'Reset',
            cancelText: 'Cancel',
            onOk: async () => {
                const ids = [...selectedClusterIds]
                const key = 'bulk-reset'
                let success = 0
                let failed = 0

                message.loading({ content: `Resetting ${ids.length} cluster(s)...`, key })
                for (let i = 0; i < ids.length; i++) {
                    const id = ids[i]
                    try {
                        // sequential to avoid bursts
                        await resetSyncStatus.mutateAsync({ cluster_id: id })
                        success++
                    } catch {
                        failed++
                    }
                    message.loading({ content: `Resetting... (${i + 1}/${ids.length})`, key })
                }

                if (failed === 0) {
                    message.success({ content: `Reset sync status: ${success}/${ids.length} succeeded`, key })
                } else {
                    message.warning({ content: `Reset sync status: ${success} ok, ${failed} failed`, key })
                }
            },
        })
    }

    const handleViewDatabases = (clusterId: string) => {
        navigate(`/databases?cluster=${clusterId}`)
    }

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields()

            if (editingCluster) {
                updateCluster.mutate(
                    { id: editingCluster.id, data: values },
                    {
                        onSuccess: () => {
                            message.success('Cluster updated successfully')
                            setModalVisible(false)
                            form.resetFields()
                        },
                        onError: (error: Error) => {
                            message.error('Operation failed: ' + error.message)
                        },
                    }
                )
            } else {
                createCluster.mutate(values, {
                    onSuccess: () => {
                        message.success('Cluster created successfully')
                        setModalVisible(false)
                        form.resetFields()
                    },
                    onError: (error: Error) => {
                        message.error('Operation failed: ' + error.message)
                    },
                })
            }
        } catch {
            // Form validation failed - errors shown automatically
        }
    }

    const getStatusColor = (status: string) => {
        const colors: Record<string, string> = {
            active: 'green',
            inactive: 'default',
            error: 'red',
            maintenance: 'orange',
        }
        return colors[status] || 'default'
    }

    const columns = [
        {
            title: 'Name',
            dataIndex: 'name',
            key: 'name',
            sorter: (a: Cluster, b: Cluster) => a.name.localeCompare(b.name),
        },
        {
            title: 'RAS Server',
            dataIndex: 'ras_server',
            key: 'ras_server',
        },
        {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            render: (status: string, record: Cluster) => (
                <Tag color={getStatusColor(status)}>{record.status_display}</Tag>
            ),
            filters: [
                { text: 'Active', value: 'active' },
                { text: 'Inactive', value: 'inactive' },
                { text: 'Error', value: 'error' },
                { text: 'Maintenance', value: 'maintenance' },
            ],
            onFilter: (value: any, record: Cluster) => record.status === value,
        },
        {
            title: 'Databases',
            dataIndex: 'databases_count',
            key: 'databases_count',
            render: (count: number) => count || 0,
            sorter: (a: Cluster, b: Cluster) => (a.databases_count || 0) - (b.databases_count || 0),
        },
        {
            title: 'Last Sync',
            dataIndex: 'last_sync',
            key: 'last_sync',
            render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
        },
        {
            title: 'Actions',
            key: 'actions',
            render: (_: any, record: Cluster) => (
                <Space size="small">
                    <Button
                        size="small"
                        icon={<DatabaseOutlined />}
                        onClick={() => handleViewDatabases(record.id)}
                        title="View Databases"
                    >
                        Databases
                    </Button>
                    <Button
                        size="small"
                        icon={<SyncOutlined spin={syncCluster.isPending} />}
                        onClick={() => handleSync(record.id, record.name)}
                        title="Sync with RAS"
                        disabled={syncCluster.isPending}
                    />
                    <Popconfirm
                        title="Reset sync status?"
                        description="Use this if cluster sync is stuck."
                        onConfirm={() => handleResetSyncStatus(record.id, record.name)}
                        okText="Reset"
                        cancelText="Cancel"
                    >
                        <Button
                            size="small"
                            icon={<UnlockOutlined />}
                            title="Reset sync status"
                            loading={resettingClusterId === record.id}
                        />
                    </Popconfirm>
                    <Button
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => handleEdit(record)}
                        title="Edit"
                    />
                    <Popconfirm
                        title="Delete cluster?"
                        description="This will also delete all databases in this cluster."
                        onConfirm={() => handleDelete(record.id)}
                        okText="Yes"
                        cancelText="No"
                    >
                        <Button
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            title="Delete"
                            loading={deleteCluster.isPending}
                        />
                    </Popconfirm>
                </Space>
            ),
        },
    ]

    return (
        <div>
            <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
                <h1>Clusters</h1>
                <Space>
                    <Button
                        icon={<UnlockOutlined />}
                        onClick={handleBulkResetSyncStatus}
                        disabled={selectedClusterIds.length === 0 || resetSyncStatus.isPending}
                    >
                        Reset Sync ({selectedClusterIds.length})
                    </Button>
                    <Button
                        icon={<SearchOutlined />}
                        onClick={() => setDiscoverModalVisible(true)}
                    >
                        Discover Clusters
                    </Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                        Add Cluster
                    </Button>
                </Space>
            </Space>

            <Table
                columns={columns}
                dataSource={clusters}
                loading={isLoading}
                rowKey="id"
                pagination={{ pageSize: 20 }}
                rowSelection={{
                    selectedRowKeys: selectedClusterIds,
                    onChange: (keys) => setSelectedClusterIds(keys as string[]),
                }}
            />

            <Modal
                title={editingCluster ? 'Edit Cluster' : 'Add New Cluster'}
                open={modalVisible}
                onOk={handleSubmit}
                onCancel={() => {
                    setModalVisible(false)
                    form.resetFields()
                }}
                width={600}
                okText={editingCluster ? 'Update' : 'Create'}
                confirmLoading={createCluster.isPending || updateCluster.isPending}
            >
                <Form form={form} layout="vertical">
                    <Form.Item
                        label="Cluster Name"
                        name="name"
                        rules={[{ required: true, message: 'Please enter cluster name' }]}
                    >
                        <Input placeholder="Production Cluster" />
                    </Form.Item>

                    <Form.Item label="Description" name="description">
                        <TextArea rows={3} placeholder="Optional description" />
                    </Form.Item>

                    <Form.Item
                        label="RAS Server"
                        name="ras_server"
                        rules={[{ required: true, message: 'Please enter RAS server address' }]}
                    >
                        <Input placeholder={systemConfig?.ras_default_server ?? 'localhost:1545'} />
                    </Form.Item>

                    <Form.Item
                        label="Cluster Service URL"
                        name="cluster_service_url"
                        rules={[{ required: true, message: 'Please enter cluster service URL' }]}
                    >
                        <Input placeholder={systemConfig?.ras_adapter_url ?? 'http://localhost:8188'} />
                    </Form.Item>

                    <Form.Item label="Cluster Admin User" name="cluster_user">
                        <Input placeholder="Optional cluster admin username" />
                    </Form.Item>

                    <Form.Item label="Cluster Admin Password" name="cluster_pwd">
                        <Input.Password placeholder="Optional cluster admin password" />
                    </Form.Item>

                    <Form.Item label="Status" name="status">
                        <Select>
                            <Select.Option value="active">Active</Select.Option>
                            <Select.Option value="inactive">Inactive</Select.Option>
                            <Select.Option value="maintenance">Maintenance</Select.Option>
                            <Select.Option value="error">Error</Select.Option>
                        </Select>
                    </Form.Item>
                </Form>
            </Modal>

            <DiscoverClustersModal
                visible={discoverModalVisible}
                onClose={() => setDiscoverModalVisible(false)}
            />
        </div>
    )
}
