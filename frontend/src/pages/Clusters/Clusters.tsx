import { useState, useMemo } from 'react'
import { Button, Space, Tag, Modal, Form, Input, Popconfirm, Select, App } from 'antd'
import { PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined, DatabaseOutlined, SearchOutlined, UnlockOutlined, KeyOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { Cluster } from '../../api/generated/model/cluster'
import { DiscoverClustersModal } from '../../components/clusters/DiscoverClustersModal'
import {
    DEFAULT_CLUSTER_SERVICE_URL,
    DEFAULT_RAS_SERVER,
    useClusters,
    useSystemConfig,
    useCreateCluster,
    useUpdateCluster,
    useDeleteCluster,
    useSyncCluster,
    useResetClusterSyncStatus,
    useUpdateClusterCredentials,
} from '../../api/queries/clusters'
import { useAuthz } from '../../authz'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

const { TextArea } = Input

export const Clusters = () => {
    const navigate = useNavigate()
    const { message, modal } = App.useApp()

    // UI state
    const [modalVisible, setModalVisible] = useState(false)
    const [editingCluster, setEditingCluster] = useState<Cluster | null>(null)
    const [discoverModalVisible, setDiscoverModalVisible] = useState(false)
    const [credentialsModalVisible, setCredentialsModalVisible] = useState(false)
    const [credentialsCluster, setCredentialsCluster] = useState<Cluster | null>(null)
    const [selectedClusterIds, setSelectedClusterIds] = useState<string[]>([])
    const [resettingClusterId, setResettingClusterId] = useState<string | null>(null)
    const [form] = Form.useForm()
    const [credentialsForm] = Form.useForm()
    // React Query hooks
    const { data: systemConfig } = useSystemConfig()
    const authz = useAuthz()
    const canResetSync = authz.isStaff
    const canDiscover = authz.isStaff
    const canCreateCluster = authz.isStaff
    const getErrorStatus = (error: unknown): number | undefined => {
        const maybe = error as { response?: { status?: number } } | null
        return maybe?.response?.status
    }

    const fallbackColumnConfigs = useMemo(() => [
        { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
        { key: 'ras_server', label: 'RAS Server', sortable: true, groupKey: 'core', groupLabel: 'Core' },
        { key: 'status', label: 'Status', sortable: true, groupKey: 'status', groupLabel: 'Status' },
        { key: 'databases_count', label: 'Databases', sortable: true, groupKey: 'status', groupLabel: 'Status' },
        { key: 'last_sync', label: 'Last Sync', sortable: true, groupKey: 'status', groupLabel: 'Status' },
        { key: 'credentials', label: 'Credentials', groupKey: 'access', groupLabel: 'Access' },
        { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
    ], [])
    // Mutations
    const createCluster = useCreateCluster()
    const updateCluster = useUpdateCluster()
    const deleteCluster = useDeleteCluster()
    const syncCluster = useSyncCluster()
    const resetSyncStatus = useResetClusterSyncStatus()
    const updateClusterCredentials = useUpdateClusterCredentials()

    const handleCreate = () => {
        setEditingCluster(null)
        form.resetFields()
        form.setFieldsValue({
            ras_server: systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER,
            cluster_service_url: DEFAULT_CLUSTER_SERVICE_URL,
            status: 'active',
        })
        setModalVisible(true)
    }

    const handleEdit = (cluster: Cluster) => {
        setEditingCluster(cluster)
        form.resetFields()
        form.setFieldsValue({ ...cluster, cluster_pwd: '' })
        setModalVisible(true)
    }

    const openCredentialsModal = (cluster: Cluster) => {
        setCredentialsCluster(cluster)
        credentialsForm.setFieldsValue({
            username: cluster.cluster_user ?? '',
            password: '',
        })
        setCredentialsModalVisible(true)
    }

    const handleCredentialsSave = async () => {
        if (!credentialsCluster) return

        const values = await credentialsForm.validateFields()
        const username = (values.username ?? '').trim()
        const password = values.password ?? ''

        const payload: { cluster_id: string; username?: string; password?: string } = {
            cluster_id: credentialsCluster.id,
        }

        if (username) payload.username = username
        if (password) payload.password = password

        if (!payload.username && !payload.password) {
            message.info('Нет изменений для сохранения')
            return
        }

        updateClusterCredentials.mutate(payload, {
            onSuccess: (response) => {
                message.success(response.message || 'Креды кластера обновлены')
                setCredentialsModalVisible(false)
                setCredentialsCluster(null)
                credentialsForm.resetFields()
            },
            onError: (error: Error) => {
                message.error('Не удалось обновить креды: ' + error.message)
            },
        })
    }

    const handleCredentialsReset = () => {
        if (!credentialsCluster) return

        modal.confirm({
            title: 'Сбросить креды кластера?',
            content: 'Логин и пароль будут очищены.',
            okText: 'Сбросить',
            cancelText: 'Отмена',
            okButtonProps: { danger: true },
            onOk: async () => {
                updateClusterCredentials.mutate(
                    { cluster_id: credentialsCluster.id, reset: true },
                    {
                        onSuccess: (response) => {
                            message.success(response.message || 'Креды кластера сброшены')
                            setCredentialsModalVisible(false)
                            setCredentialsCluster(null)
                            credentialsForm.resetFields()
                        },
                        onError: (error: Error) => {
                            message.error('Не удалось сбросить креды: ' + error.message)
                        },
                    }
                )
            },
        })
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
        } catch (error: unknown) {
            const status = getErrorStatus(error)
            if (status === 403) {
                message.error('Reset sync status requires staff access')
                return
            }
            const errorMessage = error instanceof Error ? error.message : 'unknown error'
            message.error(`Reset sync status failed: ${errorMessage}`)
        } finally {
            setResettingClusterId(null)
        }
    }

    const handleBulkResetSyncStatus = () => {
        if (selectedClusterIds.length === 0) return

        modal.confirm({
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
            width: 200,
        },
        {
            title: 'RAS Server',
            dataIndex: 'ras_server',
            key: 'ras_server',
            width: 180,
        },
        {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            width: 120,
            render: (status: string, record: Cluster) => (
                <Tag color={getStatusColor(status)}>{record.status_display}</Tag>
            ),
        },
        {
            title: 'Databases',
            dataIndex: 'databases_count',
            key: 'databases_count',
            width: 120,
            render: (count: number) => count || 0,
        },
        {
            title: 'Last Sync',
            dataIndex: 'last_sync',
            key: 'last_sync',
            width: 170,
            render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
        },
        {
            title: 'Credentials',
            key: 'credentials',
            width: 130,
            render: (_: unknown, record: Cluster) => (
                <Tag color={record.cluster_pwd_configured ? 'green' : 'default'}>
                    {record.cluster_pwd_configured ? 'Configured' : 'Missing'}
                </Tag>
            ),
        },
        {
            title: 'Actions',
            key: 'actions',
            width: 260,
            render: (_: unknown, record: Cluster) => {
                const canView = authz.canCluster(record.id, 'VIEW')
                const canOperate = authz.canCluster(record.id, 'OPERATE')
                const canManage = authz.canCluster(record.id, 'MANAGE')
                const canAdmin = authz.canCluster(record.id, 'ADMIN')

                return (
                    <Space size="small">
                        <Button
                            size="small"
                            icon={<DatabaseOutlined />}
                            onClick={() => handleViewDatabases(record.id)}
                            title="View Databases"
                            disabled={!canView}
                        >
                            Databases
                        </Button>
                        <Button
                            size="small"
                            icon={<SyncOutlined spin={syncCluster.isPending} />}
                            onClick={() => handleSync(record.id, record.name)}
                            title="Sync with RAS"
                            disabled={!canOperate || syncCluster.isPending}
                        />
                        {canResetSync && (
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
                        )}
                        <Button
                            size="small"
                            icon={<KeyOutlined />}
                            onClick={() => openCredentialsModal(record)}
                            title="Credentials"
                            disabled={!canManage}
                        />
                        <Button
                            size="small"
                            icon={<EditOutlined />}
                            onClick={() => handleEdit(record)}
                            title="Edit"
                            disabled={!canManage}
                        />
                        <Popconfirm
                            title="Delete cluster?"
                            description="This will also delete all databases in this cluster."
                            onConfirm={() => handleDelete(record.id)}
                            okText="Yes"
                            cancelText="No"
                            disabled={!canAdmin}
                        >
                            <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                title="Delete"
                                loading={deleteCluster.isPending}
                                disabled={!canAdmin}
                            />
                        </Popconfirm>
                    </Space>
                )
            },
        },
    ]

    const table = useTableToolkit({
        tableId: 'clusters',
        columns,
        fallbackColumns: fallbackColumnConfigs,
        initialPageSize: 20,
    })

    const totalColumnsWidth = table.totalColumnsWidth

    const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

    const { data: clustersResponse, isLoading } = useClusters({
        search: table.search,
        filters: table.filtersPayload,
        sort: table.sortPayload,
        limit: table.pagination.pageSize,
        offset: pageStart,
    })
    const clusters = clustersResponse?.clusters ?? []
    const totalClusters = typeof clustersResponse?.total === 'number'
        ? clustersResponse.total
        : clusters.length

    return (
        <div>
            <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
                <h1>Clusters</h1>
                <Space>
                    {canResetSync && (
                        <Button
                            icon={<UnlockOutlined />}
                            onClick={handleBulkResetSyncStatus}
                            disabled={selectedClusterIds.length === 0 || resetSyncStatus.isPending}
                        >
                            Reset Sync ({selectedClusterIds.length})
                        </Button>
                    )}
                    <Button
                        icon={<SearchOutlined />}
                        onClick={() => setDiscoverModalVisible(true)}
                        disabled={!canDiscover}
                    >
                        Discover Clusters
                    </Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} disabled={!canCreateCluster}>
                        Add Cluster
                    </Button>
                </Space>
            </Space>

            <TableToolkit
                table={table}
                data={clusters}
                total={totalClusters}
                loading={isLoading}
                rowKey="id"
                columns={columns}
                rowSelection={canResetSync
                    ? {
                        selectedRowKeys: selectedClusterIds,
                        onChange: (keys: React.Key[]) => setSelectedClusterIds(keys as string[]),
                    }
                    : undefined
                }
                tableLayout="fixed"
                scroll={{ x: totalColumnsWidth }}
                searchPlaceholder="Search clusters"
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
                        htmlFor="cluster-name"
                    >
                        <Input id="cluster-name" placeholder="Production Cluster" />
                    </Form.Item>

                    <Form.Item label="Description" name="description" htmlFor="cluster-description">
                        <TextArea id="cluster-description" rows={3} placeholder="Optional description" />
                    </Form.Item>

                    <Form.Item
                        label="RAS Server"
                        name="ras_server"
                        rules={[{ required: true, message: 'Please enter RAS server address' }]}
                        htmlFor="cluster-ras-server"
                    >
                        <Input id="cluster-ras-server" placeholder={systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER} />
                    </Form.Item>

                    <Form.Item
                        label="Cluster Service URL"
                        name="cluster_service_url"
                        rules={[{ required: true, message: 'Please enter cluster service URL' }]}
                        htmlFor="cluster-service-url"
                    >
                        <Input id="cluster-service-url" placeholder={DEFAULT_CLUSTER_SERVICE_URL} />
                    </Form.Item>

                    {editingCluster ? (
                        <Form.Item
                            label="Cluster Credentials"
                            htmlFor="cluster-credentials-button"
                            extra="Use Credentials to update or reset username/password."
                        >
                            <Button
                                id="cluster-credentials-button"
                                icon={<KeyOutlined />}
                                onClick={() => editingCluster && openCredentialsModal(editingCluster)}
                            >
                                Open Credentials
                            </Button>
                        </Form.Item>
                    ) : (
                        <>
                            <Form.Item label="Cluster Admin User" name="cluster_user" htmlFor="cluster-admin-user">
                                <Input id="cluster-admin-user" placeholder="Optional cluster admin username" />
                            </Form.Item>
                            <Form.Item label="Cluster Admin Password" name="cluster_pwd" htmlFor="cluster-admin-password">
                                <Input.Password
                                    id="cluster-admin-password"
                                    placeholder="Optional cluster admin password"
                                    autoComplete="new-password"
                                />
                            </Form.Item>
                        </>
                    )}

                    <Form.Item label="Status" name="status" htmlFor="cluster-status">
                        <Select id="cluster-status">
                            <Select.Option value="active">Active</Select.Option>
                            <Select.Option value="inactive">Inactive</Select.Option>
                            <Select.Option value="maintenance">Maintenance</Select.Option>
                            <Select.Option value="error">Error</Select.Option>
                        </Select>
                    </Form.Item>
                </Form>
            </Modal>

            <Modal
                title={credentialsCluster ? `Credentials: ${credentialsCluster.name}` : 'Credentials'}
                open={credentialsModalVisible}
                onCancel={() => {
                    setCredentialsModalVisible(false)
                    setCredentialsCluster(null)
                    credentialsForm.resetFields()
                }}
                footer={[
                    <Button
                        key="reset"
                        danger
                        onClick={handleCredentialsReset}
                        disabled={!credentialsCluster?.cluster_pwd_configured}
                    >
                        Reset
                    </Button>,
                    <Button
                        key="cancel"
                        onClick={() => {
                            setCredentialsModalVisible(false)
                            setCredentialsCluster(null)
                            credentialsForm.resetFields()
                        }}
                    >
                        Cancel
                    </Button>,
                    <Button
                        key="save"
                        type="primary"
                        onClick={handleCredentialsSave}
                        loading={updateClusterCredentials.isPending}
                    >
                        Save
                    </Button>,
                ]}
            >
                <Form form={credentialsForm} layout="vertical">
                    <Form.Item label="Cluster Admin User" name="username" htmlFor="cluster-credentials-username">
                        <Input id="cluster-credentials-username" placeholder="Optional cluster admin username" />
                    </Form.Item>
                    <Form.Item label="Cluster Admin Password" name="password" htmlFor="cluster-credentials-password">
                        <Input.Password
                            id="cluster-credentials-password"
                            placeholder={credentialsCluster?.cluster_pwd_configured ? 'Configured' : 'Enter password'}
                        />
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
