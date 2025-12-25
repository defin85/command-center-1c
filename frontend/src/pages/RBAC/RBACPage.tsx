import { useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Table, Tabs, Typography } from 'antd'
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

  const [clusterFilterUserId, setClusterFilterUserId] = useState<number | undefined>(undefined)
  const [clusterFilterSearch, setClusterFilterSearch] = useState<string>('')

  const [dbFilterUserId, setDbFilterUserId] = useState<number | undefined>(undefined)
  const [dbFilterSearch, setDbFilterSearch] = useState<string>('')

  const clusterPermissionsQuery = useClusterPermissions({
    user_id: clusterFilterUserId,
    search: clusterFilterSearch || undefined,
  })
  const databasePermissionsQuery = useDatabasePermissions({
    user_id: dbFilterUserId,
    search: dbFilterSearch || undefined,
  })

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

  const clusterColumns: ColumnsType<ClusterPermission> = useMemo(
    () => [
      {
        title: 'User',
        key: 'user',
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
        key: 'action',
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
        key: 'user',
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
        key: 'action',
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
                  <Space style={{ marginBottom: 12 }}>
                    <InputNumber
                      min={1}
                      placeholder="Filter: User ID"
                      value={clusterFilterUserId}
                      onChange={(v) => setClusterFilterUserId(v ?? undefined)}
                    />
                    <Input
                      placeholder="Search (user/cluster)"
                      value={clusterFilterSearch}
                      onChange={(e) => setClusterFilterSearch(e.target.value)}
                      style={{ width: 260 }}
                      allowClear
                    />
                    <Button onClick={() => clusterPermissionsQuery.refetch()} loading={clusterPermissionsQuery.isFetching}>
                      Refresh
                    </Button>
                  </Space>

                  {clusterPermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="RBAC endpoints require staff access"
                      description="If you are not staff/superuser, listing/granting permissions is forbidden."
                      style={{ marginBottom: 12 }}
                    />
                  )}

                  <Table
                    rowKey={(row) => `${row.user?.id}:${row.cluster?.id}`}
                    loading={clusterPermissionsQuery.isLoading}
                    dataSource={clusterPermissionsQuery.data ?? []}
                    columns={clusterColumns}
                    pagination={{ pageSize: 50 }}
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
                  <Space style={{ marginBottom: 12 }}>
                    <InputNumber
                      min={1}
                      placeholder="Filter: User ID"
                      value={dbFilterUserId}
                      onChange={(v) => setDbFilterUserId(v ?? undefined)}
                    />
                    <Input
                      placeholder="Search (user/database)"
                      value={dbFilterSearch}
                      onChange={(e) => setDbFilterSearch(e.target.value)}
                      style={{ width: 260 }}
                      allowClear
                    />
                    <Button onClick={() => databasePermissionsQuery.refetch()} loading={databasePermissionsQuery.isFetching}>
                      Refresh
                    </Button>
                  </Space>

                  {databasePermissionsQuery.error && (
                    <Alert
                      type="warning"
                      message="RBAC endpoints require staff access"
                      description="If you are not staff/superuser, listing/granting permissions is forbidden."
                      style={{ marginBottom: 12 }}
                    />
                  )}

                  <Table
                    rowKey={(row) => `${row.user?.id}:${row.database?.id}`}
                    loading={databasePermissionsQuery.isLoading}
                    dataSource={databasePermissionsQuery.data ?? []}
                    columns={databaseColumns}
                    pagination={{ pageSize: 50 }}
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
