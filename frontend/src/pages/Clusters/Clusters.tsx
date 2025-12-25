import { useState, useMemo, useEffect, useCallback } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, Popconfirm, Select, App } from 'antd'
import { PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined, DatabaseOutlined, SearchOutlined, UnlockOutlined, KeyOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'
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
    useUpdateClusterCredentials,
} from '../../api/queries/clusters'
import { useMe, useTableMetadata } from '../../api/queries'
import { TableToolbar } from '../../components/table/TableToolbar'
import { TablePagination } from '../../components/table/TablePagination'
import { TableFiltersRow } from '../../components/table/TableFiltersRow'
import { useTableState } from '../../components/table/hooks/useTableState'
import type { TableFilterConfig, TableFilterValue, TableFilters } from '../../components/table/types'
import { TablePreferencesModal } from '../../components/table/TablePreferencesModal'
import { useTablePreferences } from '../../components/table/hooks/useTablePreferences'

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
    const [preferencesOpen, setPreferencesOpen] = useState(false)

    // React Query hooks
    const { data: tableMetadata } = useTableMetadata('clusters')
    const {
        search,
        setSearch,
        filters,
        setFilter,
        setFilters,
        sort,
        setSort,
        pagination,
        setPage,
        setPageSize,
    } = useTableState<TableFilters>({
        initialFilters: {},
        initialPageSize: 20,
    })
    const { data: systemConfig } = useSystemConfig()
    const meQuery = useMe()
    const canResetSync = Boolean(meQuery.data?.is_staff)
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

    const columnConfigs = useMemo(() => {
        const metadataColumns = tableMetadata?.columns ?? []
        if (metadataColumns.length === 0) {
            return fallbackColumnConfigs
        }
        return metadataColumns.map((col) => ({
            key: col.key,
            label: col.label,
            sortable: col.sortable ?? false,
            groupKey: col.group_key ?? undefined,
            groupLabel: col.group_label ?? undefined,
        }))
    }, [fallbackColumnConfigs, tableMetadata?.columns])

    const filterConfigs = useMemo<TableFilterConfig[]>(() => {
        const metadataColumns = tableMetadata?.columns ?? []
        if (metadataColumns.length === 0) {
            return columnConfigs
                .filter((col) => col.key !== 'actions')
                .map((col) => ({
                    key: col.key,
                    label: col.label,
                    type: 'text',
                    placeholder: col.label,
                }))
        }
        return metadataColumns
            .filter((col) => col.filter && col.key !== 'actions')
            .map((col) => ({
                key: col.key,
                label: col.label,
                type: col.filter?.type === 'select' || col.filter?.type === 'boolean'
                    ? col.filter.type
                    : 'text',
                options: col.filter?.options,
                placeholder: col.filter?.placeholder ?? col.label,
            }))
    }, [columnConfigs, tableMetadata?.columns])

    const filterConfigByKey = useMemo(() => {
        return new Map(filterConfigs.map((config) => [config.key, config]))
    }, [filterConfigs])

    const defaultFilterState = useMemo<TableFilters>(() => {
        const state: Record<string, TableFilterValue> = {}
        filterConfigs.forEach((config) => {
            state[config.key] = null
        })
        return state
    }, [filterConfigs])

    const hasFilterValue = useCallback((value: TableFilterValue) => {
        if (value === null || value === undefined) return false
        if (typeof value === 'string') return value.trim().length > 0
        if (Array.isArray(value)) return value.length > 0
        return true
    }, [])

    useEffect(() => {
        setFilters(defaultFilterState)
    }, [defaultFilterState, setFilters])

    const {
        preferences,
        activePreset,
        setActivePreset,
        updatePreset,
        createPreset,
        deletePreset,
    } = useTablePreferences('clusters', columnConfigs, filterConfigs)

    const visibleColumns = useMemo(() => new Set(activePreset.visibleColumns), [activePreset.visibleColumns])
    const sortableColumns = useMemo(() => new Set(activePreset.sortableColumns), [activePreset.sortableColumns])

    const orderedFilters = useMemo(() => {
        const configs = filterConfigs.filter((filter) => activePreset.filterVisibility[filter.key] !== false)
        const order = activePreset.filterOrder
        return configs.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
    }, [activePreset.filterOrder, activePreset.filterVisibility, filterConfigs])

    useEffect(() => {
        const defaults = activePreset.defaultFilters || {}
        const nextFilters: TableFilters = { ...defaultFilterState }
        Object.entries(defaults).forEach(([key, value]) => {
            if (key in nextFilters) {
                nextFilters[key] = value
            }
        })
        setFilters(nextFilters)
        if (activePreset.defaultSort?.key && activePreset.defaultSort.order) {
            setSort(activePreset.defaultSort.key, activePreset.defaultSort.order)
        } else {
            setSort(null, null)
        }
        setPage(1)
    }, [activePreset.defaultFilters, activePreset.defaultSort, defaultFilterState, setFilters, setPage, setSort])

    const filterOperatorsByKey = useMemo<Record<string, string>>(() => {
        const metadataColumns = tableMetadata?.columns ?? []
        if (metadataColumns.length === 0) {
            return {}
        }
        const map: Record<string, string> = {}
        metadataColumns.forEach((col) => {
            if (!col.filter) return
            if (col.filter.operators?.includes('contains')) {
                map[col.key] = 'contains'
                return
            }
            map[col.key] = col.filter.operators?.[0] || 'eq'
        })
        return map
    }, [tableMetadata?.columns])

    const filtersPayload = useMemo(() => {
        const payload: Record<string, { op: string; value: TableFilterValue }> = {}
        filterConfigs.forEach((config) => {
            const value = filters[config.key]
            if (value === null || value === undefined || value === '') {
                return
            }
            const operator = filterOperatorsByKey[config.key]
                || (config.type === 'text' ? 'contains' : 'eq')
            payload[config.key] = { op: operator, value }
        })
        return Object.keys(payload).length > 0 ? payload : undefined
    }, [filterConfigs, filterOperatorsByKey, filters])

    const sortPayload = useMemo(() => {
        if (!sort.key || !sort.order) return undefined
        return { key: sort.key, order: sort.order }
    }, [sort.key, sort.order])

    const handleToggleFilterVisibility = useCallback((key: string, visible: boolean) => {
        if (!visible && hasFilterValue(filters[key])) {
            return
        }
        updatePreset({
            ...activePreset,
            filterVisibility: {
                ...activePreset.filterVisibility,
                [key]: visible,
            },
        })
    }, [activePreset, filters, hasFilterValue, updatePreset])

    const renderFilterTitle = useCallback((key: string, label: string) => {
        if (!filterConfigByKey.has(key)) {
            return label
        }
        const isVisible = activePreset.filterVisibility[key] !== false
        const disableHide = isVisible && hasFilterValue(filters[key])
        return (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span>{label}</span>
                <Button
                    type="text"
                    size="small"
                    icon={isVisible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                    disabled={disableHide}
                    onClick={(event) => {
                        event.stopPropagation()
                        handleToggleFilterVisibility(key, !isVisible)
                    }}
                />
            </span>
        )
    }, [activePreset.filterVisibility, filterConfigByKey, filters, handleToggleFilterVisibility, hasFilterValue])

    const pageStart = (pagination.page - 1) * pagination.pageSize

    const { data: clustersResponse, isLoading } = useClusters({
        search,
        filters: filtersPayload,
        sort: sortPayload,
        limit: pagination.pageSize,
        offset: pageStart,
    })
    const clusters = clustersResponse?.clusters ?? []
    const totalClusters = typeof clustersResponse?.total === 'number'
        ? clustersResponse.total
        : clusters.length

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
            ras_server: systemConfig?.ras_default_server ?? 'localhost:1545',
            cluster_service_url: systemConfig?.ras_adapter_url ?? 'http://localhost:8188',
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
            title: renderFilterTitle('name', 'Name'),
            dataIndex: 'name',
            key: 'name',
            width: 200,
            sorter: sortableColumns.has('name'),
        },
        {
            title: renderFilterTitle('ras_server', 'RAS Server'),
            dataIndex: 'ras_server',
            key: 'ras_server',
            width: 180,
            sorter: sortableColumns.has('ras_server'),
        },
        {
            title: renderFilterTitle('status', 'Status'),
            dataIndex: 'status',
            key: 'status',
            width: 120,
            render: (status: string, record: Cluster) => (
                <Tag color={getStatusColor(status)}>{record.status_display}</Tag>
            ),
            sorter: sortableColumns.has('status'),
        },
        {
            title: renderFilterTitle('databases_count', 'Databases'),
            dataIndex: 'databases_count',
            key: 'databases_count',
            width: 120,
            render: (count: number) => count || 0,
            sorter: sortableColumns.has('databases_count'),
        },
        {
            title: renderFilterTitle('last_sync', 'Last Sync'),
            dataIndex: 'last_sync',
            key: 'last_sync',
            width: 170,
            render: (date: string) => (date ? new Date(date).toLocaleString() : 'Never'),
            sorter: sortableColumns.has('last_sync'),
        },
        {
            title: renderFilterTitle('credentials', 'Credentials'),
            key: 'credentials',
            width: 130,
            render: (_: unknown, record: Cluster) => (
                <Tag color={record.cluster_pwd_configured ? 'green' : 'default'}>
                    {record.cluster_pwd_configured ? 'Configured' : 'Missing'}
                </Tag>
            ),
        },
        {
            title: renderFilterTitle('actions', 'Actions'),
            key: 'actions',
            width: 260,
            render: (_: unknown, record: Cluster) => (
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

    const columnsByKey = useMemo(() => {
        const map = new Map<string, (typeof columns)[number]>()
        columns.forEach((col) => {
            map.set(col.key, col)
        })
        return map
    }, [columns])

    const groupedTableColumns = useMemo(() => {
        const groups: Array<{ key: string; title: string; children: (typeof columns)[number][] }> = []
        const seen = new Map<string, number>()

        activePreset.columnOrder.forEach((key) => {
            if (!visibleColumns.has(key)) return
            const column = columnsByKey.get(key)
            if (!column) return
            const config = columnConfigs.find((item) => item.key === key)
            const groupKey = config?.groupKey || 'general'
            const groupLabel = config?.groupLabel || config?.groupKey || 'General'
            if (!seen.has(groupKey)) {
                seen.set(groupKey, groups.length)
                groups.push({ key: groupKey, title: groupLabel, children: [column] })
                return
            }
            const index = seen.get(groupKey) as number
            groups[index].children.push(column)
        })

        return groups.map((group) => ({
            title: group.title,
            key: group.key,
            children: group.children,
        }))
    }, [activePreset.columnOrder, columnConfigs, columnsByKey, visibleColumns])

    const filterColumns = useMemo(() => {
        return activePreset.columnOrder
            .filter((key) => visibleColumns.has(key))
            .map((key) => ({ key, width: columnsByKey.get(key)?.width }))
    }, [activePreset.columnOrder, columnsByKey, visibleColumns])

    const totalColumnsWidth = useMemo(() => {
        return filterColumns.reduce((sum, col) => sum + (col.width ?? 160), 0)
    }, [filterColumns])

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
                    >
                        Discover Clusters
                    </Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                        Add Cluster
                    </Button>
                </Space>
            </Space>

            <TableToolbar
                searchValue={search}
                searchPlaceholder="Search clusters"
                onSearchChange={setSearch}
                onReset={() => {
                    setSearch('')
                    const defaults = activePreset.defaultFilters || {}
                    const nextFilters: TableFilters = { ...defaultFilterState }
                    Object.entries(defaults).forEach(([key, value]) => {
                        if (key in nextFilters) {
                            nextFilters[key] = value
                        }
                    })
                    setFilters(nextFilters)
                }}
                actions={(
                    <Button onClick={() => setPreferencesOpen(true)}>Table settings</Button>
                )}
            />

            <TableFiltersRow
                columns={filterColumns}
                configs={orderedFilters}
                values={filters}
                visibility={activePreset.filterVisibility}
                onChange={setFilter}
            />

            <Table
                columns={groupedTableColumns}
                dataSource={clusters}
                loading={isLoading}
                rowKey="id"
                pagination={false}
                tableLayout="fixed"
                scroll={{ x: totalColumnsWidth }}
                rowSelection={{
                    selectedRowKeys: selectedClusterIds,
                    onChange: (keys) => setSelectedClusterIds(keys as string[]),
                }}
                onChange={(_, __, sorter) => {
                    if (Array.isArray(sorter)) {
                        setSort(null, null)
                        return
                    }
                    const key = sorter?.field ? String(sorter.field) : null
                    if (key && !sortableColumns.has(key)) {
                        setSort(null, null)
                        return
                    }
                    const order = sorter?.order === 'ascend'
                        ? 'asc'
                        : sorter?.order === 'descend'
                            ? 'desc'
                            : null
                    setSort(key, order)
                }}
            />

            <TablePagination
                total={totalClusters}
                page={pagination.page}
                pageSize={pagination.pageSize}
                onChange={(page, pageSize) => {
                    if (pageSize !== pagination.pageSize) {
                        setPageSize(pageSize)
                        return
                    }
                    setPage(page)
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

                    {editingCluster ? (
                        <Form.Item
                            label="Cluster Credentials"
                            extra="Use Credentials to update or reset username/password."
                        >
                            <Button
                                icon={<KeyOutlined />}
                                onClick={() => editingCluster && openCredentialsModal(editingCluster)}
                            >
                                Open Credentials
                            </Button>
                        </Form.Item>
                    ) : (
                        <>
                            <Form.Item label="Cluster Admin User" name="cluster_user">
                                <Input placeholder="Optional cluster admin username" />
                            </Form.Item>
                            <Form.Item label="Cluster Admin Password" name="cluster_pwd">
                                <Input.Password
                                    placeholder="Optional cluster admin password"
                                    autoComplete="new-password"
                                />
                            </Form.Item>
                        </>
                    )}

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
                    <Form.Item label="Cluster Admin User" name="username">
                        <Input placeholder="Optional cluster admin username" />
                    </Form.Item>
                    <Form.Item label="Cluster Admin Password" name="password">
                        <Input.Password
                            placeholder={credentialsCluster?.cluster_pwd_configured ? 'Configured' : 'Enter password'}
                        />
                    </Form.Item>
                </Form>
            </Modal>

            <DiscoverClustersModal
                visible={discoverModalVisible}
                onClose={() => setDiscoverModalVisible(false)}
            />

            <TablePreferencesModal
                open={preferencesOpen}
                onClose={() => setPreferencesOpen(false)}
                columns={columnConfigs}
                filters={filterConfigs}
                presets={preferences.presets}
                activePresetId={preferences.activePresetId}
                onSelectPreset={setActivePreset}
                onUpdatePreset={updatePreset}
                onCreatePreset={createPreset}
                onDeletePreset={deletePreset}
            />
        </div>
    )
}
