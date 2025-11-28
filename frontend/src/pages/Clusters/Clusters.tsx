import { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, Popconfirm, Select, App } from 'antd'
import { PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined, DatabaseOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { clustersApi, Cluster, ClusterCreateRequest } from '../../api/endpoints/clusters'

const { TextArea } = Input

export const Clusters = () => {
    const navigate = useNavigate()
    const { message } = App.useApp()
    const [clusters, setClusters] = useState<Cluster[]>([])
    const [loading, setLoading] = useState(false)
    const [modalVisible, setModalVisible] = useState(false)
    const [editingCluster, setEditingCluster] = useState<Cluster | null>(null)
    const [form] = Form.useForm()

    const fetchClusters = async () => {
        try {
            setLoading(true)
            const data = await clustersApi.list()
            setClusters(data)
        } catch (error: any) {
            message.error('Failed to load clusters: ' + error.message)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchClusters()
    }, [])

    const handleCreate = () => {
        setEditingCluster(null)
        form.resetFields()
        form.setFieldsValue({
            ras_server: 'localhost:1545',
            cluster_service_url: 'http://localhost:8188',
            status: 'active',
        })
        setModalVisible(true)
    }

    const handleEdit = (cluster: Cluster) => {
        setEditingCluster(cluster)
        form.setFieldsValue(cluster)
        setModalVisible(true)
    }

    const handleDelete = async (id: string) => {
        try {
            await clustersApi.delete(id)
            message.success('Cluster deleted successfully')
            fetchClusters()
        } catch (error: any) {
            message.error('Failed to delete cluster: ' + error.message)
        }
    }

    const handleSync = async (id: string, name: string) => {
        try {
            message.loading({ content: `Syncing ${name}...`, key: 'sync' })
            const result = await clustersApi.sync(id)
            // databases_found may be undefined if sync is async (Celery task)
            const dbInfo = result.databases_found !== undefined
                ? `. Found ${result.databases_found} databases.`
                : ''
            message.success({
                content: `${result.message}${dbInfo}`,
                key: 'sync',
            })
            // Refresh cluster list after short delay to allow async sync to complete
            setTimeout(() => fetchClusters(), 1000)
        } catch (error: any) {
            message.error({ content: 'Sync failed: ' + error.message, key: 'sync' })
        }
    }

    const handleViewDatabases = (clusterId: string) => {
        navigate(`/databases?cluster=${clusterId}`)
    }

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields()
            const requestData: ClusterCreateRequest = values

            if (editingCluster) {
                await clustersApi.update(editingCluster.id, requestData)
                message.success('Cluster updated successfully')
            } else {
                await clustersApi.create(requestData)
                message.success('Cluster created successfully')
            }

            setModalVisible(false)
            form.resetFields()
            fetchClusters()
        } catch (error: any) {
            message.error('Operation failed: ' + error.message)
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
                        icon={<SyncOutlined />}
                        onClick={() => handleSync(record.id, record.name)}
                        title="Sync with RAS"
                    />
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
                        <Button size="small" danger icon={<DeleteOutlined />} title="Delete" />
                    </Popconfirm>
                </Space>
            ),
        },
    ]

    return (
        <div>
            <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
                <h1>Clusters</h1>
                <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                    Add Cluster
                </Button>
            </Space>

            <Table
                columns={columns}
                dataSource={clusters}
                loading={loading}
                rowKey="id"
                pagination={{ pageSize: 20 }}
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
                        <Input placeholder="localhost:1545" />
                    </Form.Item>

                    <Form.Item
                        label="Cluster Service URL"
                        name="cluster_service_url"
                        rules={[{ required: true, message: 'Please enter cluster service URL' }]}
                    >
                        <Input placeholder="http://localhost:8188" />
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
        </div>
    )
}
