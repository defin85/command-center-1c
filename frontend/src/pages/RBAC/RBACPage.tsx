import { useMemo } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Tabs, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ClusterPermission } from '../../api/generated/model/clusterPermission'
import type { DatabasePermission } from '../../api/generated/model/databasePermission'
import { useClusters } from '../../api/queries/clusters'
import {
  useClusterPermissions,
  useDatabasePermissions,
  useGrantClusterPermission,
  useGrantDatabasePermission,
  useRevokeClusterPermission,
  useRevokeDatabasePermission,
} from '../../api/queries/rbac'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

const { Title, Text } = Typography

type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'

const LEVEL_OPTIONS: Array<{ label: PermissionLevelCode; value: PermissionLevelCode }> = [
  { label: 'VIEW', value: 'VIEW' },
  { label: 'OPERATE', value: 'OPERATE' },
  { label: 'MANAGE', value: 'MANAGE' },
  { label: 'ADMIN', value: 'ADMIN' },
]

export function RBACPage() {
  const { data: clustersResponse } = useClusters()
  const clusters = clustersResponse?.clusters ?? []

  const grantCluster = useGrantClusterPermission()
  const revokeCluster = useRevokeClusterPermission()
  const grantDatabase = useGrantDatabasePermission()
  const revokeDatabase = useRevokeDatabasePermission()

  const [grantClusterForm] = Form.useForm<{
    user_id: number
    cluster_id: string
    level: PermissionLevelCode
    notes?: string
  }>()

  const [grantDatabaseForm] = Form.useForm<{
    user_id: number
    database_id: string
    level: PermissionLevelCode
    notes?: string
  }>()

  const parseUserId = (value: unknown): number | undefined => {
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value !== 'string') return undefined
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? undefined : parsed
  }

  const normalizeString = (value: unknown): string | undefined => {
    if (typeof value !== 'string') return undefined
    const trimmed = value.trim()
    return trimmed ? trimmed : undefined
  }

  const clusterFallbackColumns = useMemo(() => [
    { key: 'user_id', label: 'User', groupKey: 'core', groupLabel: 'Core' },
    { key: 'cluster', label: 'Cluster', groupKey: 'core', groupLabel: 'Core' },
    { key: 'level', label: 'Level', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'granted_at', label: 'Granted At', groupKey: 'time', groupLabel: 'Time' },
    { key: 'granted_by', label: 'Granted By', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'notes', label: 'Notes', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const databaseFallbackColumns = useMemo(() => [
    { key: 'user_id', label: 'User', groupKey: 'core', groupLabel: 'Core' },
    { key: 'database', label: 'Database', groupKey: 'core', groupLabel: 'Core' },
    { key: 'database_id', label: 'Database ID', groupKey: 'core', groupLabel: 'Core' },
    { key: 'level', label: 'Level', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'granted_at', label: 'Granted At', groupKey: 'time', groupLabel: 'Time' },
    { key: 'granted_by', label: 'Granted By', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'notes', label: 'Notes', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const clusterColumns: ColumnsType<ClusterPermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'Cluster', dataIndex: ['cluster', 'name'], key: 'cluster' },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      { title: 'Granted At', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeCluster.isPending}
            onClick={() => {
              if (!row.user?.id || !row.cluster?.id) return
              revokeCluster.mutate({ user_id: row.user.id, cluster_id: row.cluster.id })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [revokeCluster]
  )

  const databaseColumns: ColumnsType<DatabasePermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user_id',
        render: (_, row) => (
          <span>
            {row.user?.username} <Text type="secondary">#{row.user?.id}</Text>
          </span>
        ),
      },
      { title: 'Database', dataIndex: ['database', 'name'], key: 'database' },
      { title: 'Database ID', dataIndex: ['database', 'id'], key: 'database_id' },
      { title: 'Level', dataIndex: 'level', key: 'level' },
      { title: 'Granted At', dataIndex: 'granted_at', key: 'granted_at' },
      {
        title: 'Granted By',
        key: 'granted_by',
        render: (_, row) => (row.granted_by ? `${row.granted_by.username} #${row.granted_by.id}` : '-'),
      },
      { title: 'Notes', dataIndex: 'notes', key: 'notes' },
      {
        title: 'Action',
        key: 'actions',
        render: (_, row) => (
          <Button
            danger
            size="small"
            loading={revokeDatabase.isPending}
            onClick={() => {
              if (!row.user?.id || !row.database?.id) return
              revokeDatabase.mutate({ user_id: row.user.id, database_id: row.database.id })
            }}
          >
            Revoke
          </Button>
        ),
      },
    ],
    [revokeDatabase]
  )

  const clusterTable = useTableToolkit({
    tableId: 'rbac_clusters',
    columns: clusterColumns,
    fallbackColumns: clusterFallbackColumns,
    initialPageSize: 50,
  })

  const databaseTable = useTableToolkit({
    tableId: 'rbac_databases',
    columns: databaseColumns,
    fallbackColumns: databaseFallbackColumns,
    initialPageSize: 50,
  })

  const clusterPageStart = (clusterTable.pagination.page - 1) * clusterTable.pagination.pageSize
  const databasePageStart = (databaseTable.pagination.page - 1) * databaseTable.pagination.pageSize

  const clusterPermissionsQuery = useClusterPermissions({
    user_id: parseUserId(clusterTable.filters.user_id),
    level: normalizeString(clusterTable.filters.level) as PermissionLevelCode | undefined,
    search: clusterTable.search || undefined,
    limit: clusterTable.pagination.pageSize,
    offset: clusterPageStart,
  })
  const databasePermissionsQuery = useDatabasePermissions({
    user_id: parseUserId(databaseTable.filters.user_id),
    database_id: normalizeString(databaseTable.filters.database_id),
    level: normalizeString(databaseTable.filters.level) as PermissionLevelCode | undefined,
    search: databaseTable.search || undefined,
    limit: databaseTable.pagination.pageSize,
    offset: databasePageStart,
  })

  const clusterPermissions = clusterPermissionsQuery.data?.permissions ?? []
  const totalClusterPermissions = typeof clusterPermissionsQuery.data?.total === 'number'
    ? clusterPermissionsQuery.data.total
    : clusterPermissions.length

  const databasePermissions = databasePermissionsQuery.data?.permissions ?? []
  const totalDatabasePermissions = typeof databasePermissionsQuery.data?.total === 'number'
    ? databasePermissionsQuery.data.total
    : databasePermissions.length

  return (
    <div>
      <Title level={2}>RBAC</Title>
      <Tabs
        items={[
          {
            key: 'clusters',
            label: 'Cluster Permissions',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Cluster Permission" size="small">
                  <Form
                    form={grantClusterForm}
                    layout="inline"
                    onFinish={(values) => grantCluster.mutate(values)}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user_id required' }]}>
                      <InputNumber min={1} placeholder="User ID" />
                    </Form.Item>
                    <Form.Item name="cluster_id" rules={[{ required: true, message: 'cluster_id required' }]}>
                      <Select
                        style={{ width: 320 }}
                        placeholder="Cluster"
                        options={clusters.map((c) => ({ label: c.name, value: c.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantCluster.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantCluster.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
                  )}
                </Card>

                <Card title="Cluster Permissions" size="small">
                  {clusterPermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="RBAC endpoints require staff access"
                      description="If you are not staff/superuser, listing/granting permissions is forbidden."
                      style={{ marginBottom: 12 }}
                    />
                  )}

                  <TableToolkit
                    table={clusterTable}
                    data={clusterPermissions}
                    total={totalClusterPermissions}
                    loading={clusterPermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user?.id}:${row.cluster?.id}`}
                    columns={clusterColumns}
                    searchPlaceholder="Search cluster permissions"
                    toolbarActions={(
                      <Button onClick={() => clusterPermissionsQuery.refetch()} loading={clusterPermissionsQuery.isFetching}>
                        Refresh
                      </Button>
                    )}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'databases',
            label: 'Database Permissions',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Grant Database Permission" size="small">
                  <Form
                    form={grantDatabaseForm}
                    layout="inline"
                    onFinish={(values) => grantDatabase.mutate(values)}
                    initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                  >
                    <Form.Item name="user_id" rules={[{ required: true, message: 'user_id required' }]}>
                      <InputNumber min={1} placeholder="User ID" />
                    </Form.Item>
                    <Form.Item name="database_id" rules={[{ required: true, message: 'database_id required' }]}>
                      <Input placeholder="Database ID" style={{ width: 240 }} />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={grantDatabase.isPending}>
                        Grant
                      </Button>
                    </Form.Item>
                  </Form>
                  {grantDatabase.error && (
                    <Alert style={{ marginTop: 12 }} type="error" message="Grant failed" />
                  )}
                </Card>

                <Card title="Database Permissions" size="small">
                  {databasePermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="RBAC endpoints require staff access"
                      description="If you are not staff/superuser, listing/granting permissions is forbidden."
                      style={{ marginBottom: 12 }}
                    />
                  )}

                  <TableToolkit
                    table={databaseTable}
                    data={databasePermissions}
                    total={totalDatabasePermissions}
                    loading={databasePermissionsQuery.isLoading}
                    rowKey={(row) => `${row.user?.id}:${row.database?.id}`}
                    columns={databaseColumns}
                    searchPlaceholder="Search database permissions"
                    toolbarActions={(
                      <Button onClick={() => databasePermissionsQuery.refetch()} loading={databasePermissionsQuery.isFetching}>
                        Refresh
                      </Button>
                    )}
                  />
                </Card>
              </Space>
            ),
          },
        ]}
      />
    </div>
  )
}
