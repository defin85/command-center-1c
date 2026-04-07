import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Button, Checkbox, Form, Input, List, Pagination, Select, Space, Typography } from 'antd'
import {
  PlusOutlined,
  SearchOutlined,
  UnlockOutlined,
} from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'

import type { Cluster } from '../../api/generated/model/cluster'
import type { ClusterStatus } from '../../api/generated/model/clusterStatus'
import {
  DEFAULT_CLUSTER_SERVICE_URL,
  DEFAULT_RAS_PORT,
  DEFAULT_RAS_SERVER,
  DEFAULT_RAGENT_PORT,
  DEFAULT_RMNGR_PORT,
  DEFAULT_RPHOST_PORT_FROM,
  DEFAULT_RPHOST_PORT_TO,
  parseHostPort,
  useCluster,
  useClusters,
  useCreateCluster,
  useDeleteCluster,
  useResetClusterSyncStatus,
  useSyncCluster,
  useSystemConfig,
  useUpdateCluster,
  useUpdateClusterCredentials,
} from '../../api/queries/clusters'
import { useAuthz } from '../../authz/useAuthz'
import {
  EntityDetails,
  EntityList,
  MasterDetailShell,
  PageHeader,
  StatusBadge,
  WorkspacePage,
} from '../../components/platform'
import { DiscoverClustersModal } from '../../components/clusters/DiscoverClustersModal'

import { ClusterCredentialsModal } from './components/ClusterCredentialsModal'
import { ClusterUpsertModal } from './components/ClusterUpsertModal'
import { ClusterWorkspaceDetailPanel } from './components/ClusterWorkspaceDetailPanel'
import { resolveClusterWorkspaceContext } from './clusterWorkspaceState'

const { Text } = Typography

const PAGE_SIZE = 20
const CLUSTER_STATUS_OPTIONS: Array<{ value: ClusterStatus; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'error', label: 'Error' },
]

const parsePositiveInt = (value: string | null, fallback: number) => {
  const parsed = Number.parseInt(value || '', 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

const buildCatalogButtonStyle = (selected: boolean) => ({
  width: '100%',
  justifyContent: 'flex-start',
  height: 'auto',
  paddingBlock: 12,
  paddingInline: 12,
  borderRadius: 8,
  border: selected ? '1px solid #91caff' : '1px solid #f0f0f0',
  borderInlineStart: selected ? '4px solid #1677ff' : '4px solid transparent',
  background: selected ? '#e6f4ff' : '#fff',
  boxShadow: selected ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
})

const formatLastSync = (value: string | null) => (
  value ? new Date(value).toLocaleString() : 'Never'
)

export const Clusters = () => {
  const { message } = App.useApp()
  const authz = useAuthz()
  const [searchParams, setSearchParams] = useSearchParams()
  const [form] = Form.useForm()
  const [credentialsForm] = Form.useForm()
  const [selectedClusterIds, setSelectedClusterIds] = useState<string[]>([])
  const [resettingClusterId, setResettingClusterId] = useState<string | null>(null)

  const canResetSync = authz.isStaff
  const canDiscover = authz.isStaff
  const canCreateCluster = authz.isStaff

  const page = parsePositiveInt(searchParams.get('page'), 1)
  const search = searchParams.get('q') ?? ''
  const status = (searchParams.get('status') || '').trim() || undefined
  const selectedClusterIdFromUrl = (searchParams.get('cluster') || '').trim() || undefined
  const requestedContextParam = searchParams.get('context')

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>, options?: { replace?: boolean }) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next, { replace: options?.replace ?? false })
    },
    [searchParams, setSearchParams],
  )

  const { data: systemConfig } = useSystemConfig()
  const createCluster = useCreateCluster()
  const updateCluster = useUpdateCluster()
  const deleteCluster = useDeleteCluster()
  const syncCluster = useSyncCluster()
  const resetSyncStatus = useResetClusterSyncStatus()
  const updateClusterCredentials = useUpdateClusterCredentials()

  const clusterFilters = useMemo(() => {
    if (!status) {
      return undefined
    }
    return {
      status: {
        op: 'eq',
        value: status,
      },
    }
  }, [status])

  const clustersQuery = useClusters({
    search: search.trim() || undefined,
    filters: clusterFilters,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  })
  const clusters = useMemo(
    () => clustersQuery.data?.clusters ?? [],
    [clustersQuery.data?.clusters],
  )
  const totalClusters = typeof clustersQuery.data?.total === 'number'
    ? clustersQuery.data.total
    : clusters.length

  const selectedClusterFromCatalog = useMemo(
    () => clusters.find((cluster) => cluster.id === selectedClusterIdFromUrl) ?? null,
    [clusters, selectedClusterIdFromUrl],
  )
  const selectedClusterQuery = useCluster(selectedClusterIdFromUrl, {
    enabled: Boolean(selectedClusterIdFromUrl),
  })
  const selectedCluster = selectedClusterFromCatalog ?? selectedClusterQuery.data?.cluster ?? null
  const selectedClusterStatistics = selectedClusterQuery.data?.statistics ?? null
  const selectedClusterDatabases = selectedClusterQuery.data?.databases ?? []
  const selectedClusterPermissionTargetId = selectedCluster?.id ?? selectedClusterIdFromUrl
  const selectedClusterLoading = Boolean(
    selectedClusterIdFromUrl
    && !selectedClusterQuery.data
    && !selectedClusterQuery.isError,
  )
  const selectedClusterError = selectedClusterIdFromUrl && selectedClusterQuery.isError
    ? (
      selectedCluster
        ? 'Failed to load selected cluster detail snapshot.'
        : 'Selected cluster is outside the current catalog slice.'
    )
    : null

  const defaultRasHostPlaceholder = parseHostPort(systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER).host

  const canOperateSelectedCluster = Boolean(
    selectedClusterPermissionTargetId
    && !authz.isLoading
    && authz.canCluster(selectedClusterPermissionTargetId, 'OPERATE'),
  )
  const canManageSelectedCluster = Boolean(
    selectedClusterPermissionTargetId
    && !authz.isLoading
    && authz.canCluster(selectedClusterPermissionTargetId, 'MANAGE'),
  )
  const canAdminSelectedCluster = Boolean(
    selectedClusterPermissionTargetId
    && !authz.isLoading
    && authz.canCluster(selectedClusterPermissionTargetId, 'ADMIN'),
  )
  const { activeContext, canonicalContextParam } = useMemo(
    () => resolveClusterWorkspaceContext({
      requestedContextParam,
      hasSelectedCluster: Boolean(selectedClusterIdFromUrl),
      authzResolved: !authz.isLoading,
      canCreateCluster,
      canDiscover,
      canManageSelectedCluster,
    }),
    [
      authz.isLoading,
      canCreateCluster,
      canDiscover,
      canManageSelectedCluster,
      requestedContextParam,
      selectedClusterIdFromUrl,
    ],
  )

  useEffect(() => {
    if (requestedContextParam === canonicalContextParam) {
      return
    }
    if (requestedContextParam === null && canonicalContextParam === null) {
      return
    }
    updateSearchParams({ context: canonicalContextParam }, { replace: true })
  }, [canonicalContextParam, requestedContextParam, updateSearchParams])

  useEffect(() => {
    if (activeContext === 'create') {
      const rasDefaults = parseHostPort(systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER)
      form.resetFields()
      form.setFieldsValue({
        ras_host: rasDefaults.host,
        ras_port: rasDefaults.port || DEFAULT_RAS_PORT,
        rmngr_host: rasDefaults.host,
        rmngr_port: DEFAULT_RMNGR_PORT,
        ragent_host: rasDefaults.host,
        ragent_port: DEFAULT_RAGENT_PORT,
        rphost_port_from: DEFAULT_RPHOST_PORT_FROM,
        rphost_port_to: DEFAULT_RPHOST_PORT_TO,
        cluster_service_url: DEFAULT_CLUSTER_SERVICE_URL,
        status: 'active',
      })
      return
    }

    if (activeContext === 'edit' && selectedCluster) {
      const rasDefaults = parseHostPort(selectedCluster.ras_server ?? systemConfig?.ras_default_server ?? DEFAULT_RAS_SERVER)
      form.resetFields()
      form.setFieldsValue({
        ...selectedCluster,
        ras_host: selectedCluster.ras_host || rasDefaults.host,
        ras_port: selectedCluster.ras_port || rasDefaults.port || DEFAULT_RAS_PORT,
        rmngr_host: selectedCluster.rmngr_host || rasDefaults.host,
        rmngr_port: selectedCluster.rmngr_port || DEFAULT_RMNGR_PORT,
        ragent_host: selectedCluster.ragent_host || rasDefaults.host,
        ragent_port: selectedCluster.ragent_port || DEFAULT_RAGENT_PORT,
        rphost_port_from: selectedCluster.rphost_port_from || DEFAULT_RPHOST_PORT_FROM,
        rphost_port_to: selectedCluster.rphost_port_to || DEFAULT_RPHOST_PORT_TO,
        cluster_pwd: '',
      })
    }
  }, [activeContext, form, selectedCluster, systemConfig])

  useEffect(() => {
    if (activeContext !== 'credentials' || !selectedCluster) {
      return
    }

    credentialsForm.setFieldsValue({
      username: selectedCluster.cluster_user ?? '',
      password: '',
    })
  }, [activeContext, credentialsForm, selectedCluster])

  const clearSecondaryContext = useCallback(() => {
    updateSearchParams({ context: null })
  }, [updateSearchParams])

  const handleSubmit = useCallback(async () => {
    try {
      const values = await form.validateFields()
      if (activeContext === 'edit' && selectedCluster) {
        updateCluster.mutate(
          { id: selectedCluster.id, data: values },
          {
            onSuccess: (response) => {
              message.success(response.cluster ? 'Cluster updated successfully' : 'Cluster updated successfully')
              updateSearchParams({ cluster: response.cluster.id, context: null })
              form.resetFields()
            },
            onError: (error: Error) => {
              message.error('Operation failed: ' + error.message)
            },
          },
        )
        return
      }

      createCluster.mutate(values, {
        onSuccess: (response) => {
          message.success(response.message || 'Cluster created successfully')
          updateSearchParams({ cluster: response.cluster.id, context: null, page: '1' })
          form.resetFields()
        },
        onError: (error: Error) => {
          message.error('Operation failed: ' + error.message)
        },
      })
    } catch {
      // validation errors are shown by antd form
    }
  }, [activeContext, createCluster, form, message, selectedCluster, updateCluster, updateSearchParams])

  const handleCredentialsSave = useCallback(async () => {
    if (!selectedCluster) return

    const values = await credentialsForm.validateFields()
    const username = (values.username ?? '').trim()
    const password = values.password ?? ''

    const payload: { cluster_id: string; username?: string; password?: string } = {
      cluster_id: selectedCluster.id,
    }

    if (username) payload.username = username
    if (password) payload.password = password

    if (!payload.username && !payload.password) {
      message.info('No credential changes to save')
      return
    }

    updateClusterCredentials.mutate(payload, {
      onSuccess: (response) => {
        message.success(response.message || 'Cluster credentials updated')
        credentialsForm.resetFields()
        clearSecondaryContext()
      },
      onError: (error: Error) => {
        message.error('Failed to update credentials: ' + error.message)
      },
    })
  }, [clearSecondaryContext, credentialsForm, message, selectedCluster, updateClusterCredentials])

  const handleCredentialsReset = useCallback(() => {
    if (!selectedCluster) return

    updateClusterCredentials.mutate(
      { cluster_id: selectedCluster.id, reset: true },
      {
        onSuccess: (response) => {
          message.success(response.message || 'Cluster credentials reset')
          credentialsForm.resetFields()
          clearSecondaryContext()
        },
        onError: (error: Error) => {
          message.error('Failed to reset credentials: ' + error.message)
        },
      },
    )
  }, [clearSecondaryContext, credentialsForm, message, selectedCluster, updateClusterCredentials])

  const getErrorStatus = (error: unknown): number | undefined => {
    const maybe = error as { response?: { status?: number } } | null
    return maybe?.response?.status
  }

  const handleResetSyncStatus = useCallback(async (clusterId: string, clusterName?: string) => {
    try {
      setResettingClusterId(clusterId)
      const result = await resetSyncStatus.mutateAsync({ cluster_id: clusterId })
      message.success(result.message || `Reset sync status for ${clusterName ?? clusterId}`)
    } catch (error: unknown) {
      if (getErrorStatus(error) === 403) {
        message.error('Reset sync status requires staff access')
        return
      }
      message.error(`Reset sync status failed: ${error instanceof Error ? error.message : 'unknown error'}`)
    } finally {
      setResettingClusterId(null)
    }
  }, [message, resetSyncStatus])

  const handleBulkResetSyncStatus = useCallback(async () => {
    if (selectedClusterIds.length === 0) {
      return
    }

    const ids = [...selectedClusterIds]
    const key = 'clusters-bulk-reset'
    let success = 0
    let failed = 0

    message.loading({ content: `Resetting ${ids.length} cluster(s)…`, key })

    for (let index = 0; index < ids.length; index += 1) {
      const clusterId = ids[index]
      try {
        await resetSyncStatus.mutateAsync({ cluster_id: clusterId })
        success += 1
      } catch {
        failed += 1
      }

      message.loading({ content: `Resetting… (${index + 1}/${ids.length})`, key })
    }

    if (failed === 0) {
      message.success({ content: `Reset sync status: ${success}/${ids.length} succeeded`, key })
    } else {
      message.warning({ content: `Reset sync status: ${success} ok, ${failed} failed`, key })
    }
  }, [message, resetSyncStatus, selectedClusterIds])

  const handleDelete = useCallback((clusterId: string) => {
    deleteCluster.mutate(clusterId, {
      onSuccess: () => {
        message.success('Cluster deleted successfully')
        setSelectedClusterIds((current) => current.filter((value) => value !== clusterId))
        if (selectedClusterIdFromUrl === clusterId) {
          updateSearchParams({ cluster: null, context: null })
        }
      },
      onError: (error: Error) => {
        message.error('Failed to delete cluster: ' + error.message)
      },
    })
  }, [deleteCluster, message, selectedClusterIdFromUrl, updateSearchParams])

  const handleSync = useCallback((clusterId: string, clusterName: string) => {
    message.loading({ content: `Syncing ${clusterName}…`, key: 'cluster-sync' })
    syncCluster.mutate(clusterId, {
      onSuccess: (result) => {
        const dbInfo = result.databases_found !== undefined
          ? `. Found ${result.databases_found} databases.`
          : ''
        message.success({
          content: `${result.message}${dbInfo}`,
          key: 'cluster-sync',
        })
      },
      onError: (error: Error) => {
        message.error({ content: 'Sync failed: ' + error.message, key: 'cluster-sync' })
      },
    })
  }, [message, syncCluster])

  const renderClusterListItem = useCallback((cluster: Cluster) => {
    const selected = cluster.id === selectedClusterIdFromUrl
    const checked = selectedClusterIds.includes(cluster.id)

    return (
      <List.Item key={cluster.id}>
        <Space align="start" size="middle" style={{ width: '100%' }}>
          {canResetSync ? (
            <Checkbox
              checked={checked}
              onClick={(event) => event.stopPropagation()}
              onChange={(event) => {
                const nextChecked = event.target.checked
                setSelectedClusterIds((current) => (
                  nextChecked
                    ? [...new Set([...current, cluster.id])]
                    : current.filter((value) => value !== cluster.id)
                ))
              }}
            />
          ) : null}
          <Button
            type="text"
            style={buildCatalogButtonStyle(selected)}
            onClick={() => updateSearchParams({ cluster: cluster.id, context: 'inspect' })}
          >
            <Space direction="vertical" size={4} style={{ width: '100%', alignItems: 'flex-start' }}>
              <Space wrap size={[8, 8]}>
                <Text strong>{cluster.name}</Text>
                <StatusBadge status={cluster.status ?? 'unknown'} label={cluster.status_display} />
              </Space>
              <Space wrap size={[8, 8]}>
                <Text type="secondary">{cluster.ras_server}</Text>
                <Text type="secondary">{cluster.databases_count} databases</Text>
                <Text type="secondary">Last sync: {formatLastSync(cluster.last_sync)}</Text>
              </Space>
            </Space>
          </Button>
        </Space>
      </List.Item>
    )
  }, [canResetSync, selectedClusterIdFromUrl, selectedClusterIds, updateSearchParams])

  const detailTitle = selectedCluster ? selectedCluster.name : 'Cluster context'
  const detailDrawerTitle = selectedCluster ? `${selectedCluster.name}` : 'Cluster context'
  const detailOpen = Boolean(selectedClusterIdFromUrl) && activeContext === 'inspect'

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title="Clusters"
          subtitle="Manage RAS clusters through the shared platform workspace."
          actions={(
            <Space wrap>
              {canResetSync ? (
                <Button
                  icon={<UnlockOutlined />}
                  onClick={() => {
                    void handleBulkResetSyncStatus()
                  }}
                  disabled={selectedClusterIds.length === 0 || resetSyncStatus.isPending}
                >
                  Reset Sync ({selectedClusterIds.length})
                </Button>
              ) : null}
              <Button
                icon={<SearchOutlined />}
                onClick={() => updateSearchParams({ context: 'discover' })}
                disabled={!canDiscover}
              >
                Discover Clusters
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => updateSearchParams({ context: 'create' })}
                disabled={!canCreateCluster}
              >
                Add Cluster
              </Button>
            </Space>
          )}
        />
      )}
    >
      <MasterDetailShell
        detailOpen={detailOpen}
        onCloseDetail={() => updateSearchParams({ cluster: null, context: null })}
        detailDrawerTitle={detailDrawerTitle}
        list={(
          <EntityList
            title="Cluster catalog"
            loading={clustersQuery.isLoading}
            error={clustersQuery.isError ? 'Failed to load clusters' : null}
            emptyDescription="No clusters match the current filters."
            dataSource={clusters}
            renderItem={renderClusterListItem}
            toolbar={(
              <Space direction="vertical" size="middle" style={{ width: '100%', marginBottom: 16 }}>
                <Space wrap style={{ width: '100%' }}>
                  <Input.Search
                    allowClear
                    placeholder="Search clusters"
                    value={search}
                    onChange={(event) => updateSearchParams({ q: event.target.value, page: '1' })}
                    style={{ minWidth: 240 }}
                  />
                  <Select
                    allowClear
                    placeholder="Filter by status"
                    value={status}
                    onChange={(value) => updateSearchParams({ status: value ?? null, page: '1' })}
                    options={CLUSTER_STATUS_OPTIONS}
                    style={{ minWidth: 200 }}
                  />
                </Space>
                <Pagination
                  current={page}
                  pageSize={PAGE_SIZE}
                  total={totalClusters}
                  showSizeChanger={false}
                  onChange={(nextPage) => updateSearchParams({ page: String(nextPage) })}
                />
              </Space>
            )}
          />
        )}
        detail={(
          <EntityDetails
            title={detailTitle}
            loading={selectedClusterLoading}
            error={selectedClusterError}
            empty={!selectedClusterIdFromUrl}
            emptyDescription="Select a cluster to inspect and manage it."
          >
            {selectedCluster ? (
              <ClusterWorkspaceDetailPanel
                cluster={selectedCluster}
                statistics={selectedClusterStatistics}
                databases={selectedClusterDatabases}
                canManage={canManageSelectedCluster}
                canOperate={canOperateSelectedCluster}
                canAdmin={canAdminSelectedCluster}
                canDiscover={canDiscover}
                canResetSync={canResetSync}
                syncing={syncCluster.isPending}
                resetting={resettingClusterId === selectedCluster.id}
                deleting={deleteCluster.isPending}
                onOpenEdit={() => updateSearchParams({ cluster: selectedCluster.id, context: 'edit' })}
                onOpenCredentials={() => updateSearchParams({ cluster: selectedCluster.id, context: 'credentials' })}
                onOpenDiscover={() => updateSearchParams({ context: 'discover' })}
                onSync={() => handleSync(selectedCluster.id, selectedCluster.name)}
                onResetSyncStatus={() => {
                  void handleResetSyncStatus(selectedCluster.id, selectedCluster.name)
                }}
                onDelete={() => handleDelete(selectedCluster.id)}
              />
            ) : null}
          </EntityDetails>
        )}
      />

      <ClusterUpsertModal
        open={activeContext === 'create' || (activeContext === 'edit' && Boolean(selectedCluster))}
        editingCluster={activeContext === 'edit' ? selectedCluster : null}
        form={form}
        confirmLoading={createCluster.isPending || updateCluster.isPending}
        defaultRasHostPlaceholder={defaultRasHostPlaceholder}
        onSubmit={() => {
          void handleSubmit()
        }}
        onOpenCredentials={(cluster) => updateSearchParams({ cluster: cluster.id, context: 'credentials' })}
        onCancel={() => {
          form.resetFields()
          clearSecondaryContext()
        }}
      />

      <ClusterCredentialsModal
        open={activeContext === 'credentials' && Boolean(selectedCluster)}
        cluster={selectedCluster}
        form={credentialsForm}
        saving={updateClusterCredentials.isPending}
        onSave={() => {
          void handleCredentialsSave()
        }}
        onReset={handleCredentialsReset}
        onCancel={() => {
          credentialsForm.resetFields()
          clearSecondaryContext()
        }}
      />

      <DiscoverClustersModal
        open={activeContext === 'discover'}
        onClose={clearSecondaryContext}
      />
    </WorkspacePage>
  )
}
