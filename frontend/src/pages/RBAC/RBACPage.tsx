import { useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, InputNumber, Select, Space, Tabs, Typography, Tag, Switch } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ClusterPermission } from '../../api/generated/model/clusterPermission'
import type { DatabasePermission } from '../../api/generated/model/databasePermission'
import { useClusters } from '../../api/queries/clusters'
import { useDatabases } from '../../api/queries/databases'
import {
  useClusterPermissions,
  useDatabasePermissions,
  useGrantClusterPermission,
  useGrantDatabasePermission,
  useRevokeClusterPermission,
  useRevokeDatabasePermission,
  useRbacUsers,
} from '../../api/queries/rbac'
import {
  useInfobaseUsers,
  useCreateInfobaseUser,
  useUpdateInfobaseUser,
  useDeleteInfobaseUser,
  type InfobaseUserMapping,
} from '../../api/queries/databases'
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
  const { modal } = App.useApp()
  const { data: clustersResponse } = useClusters()
  const clusters = clustersResponse?.clusters ?? []
  const { data: databasesResponse } = useDatabases({
    filters: { limit: 1000, offset: 0 },
  })
  const databases = databasesResponse?.databases ?? []

  const grantCluster = useGrantClusterPermission()
  const revokeCluster = useRevokeClusterPermission()
  const grantDatabase = useGrantDatabasePermission()
  const revokeDatabase = useRevokeDatabasePermission()
  const createInfobaseUser = useCreateInfobaseUser()
  const updateInfobaseUser = useUpdateInfobaseUser()
  const deleteInfobaseUser = useDeleteInfobaseUser()

  const [selectedIbDatabaseId, setSelectedIbDatabaseId] = useState<string | undefined>()
  const [editingIbUser, setEditingIbUser] = useState<InfobaseUserMapping | null>(null)
  const [ibAuthFilter, setIbAuthFilter] = useState<string>('any')
  const [ibServiceFilter, setIbServiceFilter] = useState<string>('any')
  const [ibHasUserFilter, setIbHasUserFilter] = useState<string>('any')
  const [userSearch, setUserSearch] = useState<string>('')

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

  const [ibUserForm] = Form.useForm<{
    database_id: string
    user_id?: number | null
    ib_username: string
    ib_display_name?: string
    ib_roles?: string[]
    auth_type?: InfobaseUserMapping['auth_type']
    is_service?: boolean
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

  const handleIbUserEdit = (record: InfobaseUserMapping) => {
    setSelectedIbDatabaseId(record.database_id)
    setEditingIbUser(record)
    ibUserForm.setFieldsValue({
      database_id: record.database_id,
      user_id: record.user?.id ?? null,
      ib_username: record.ib_username,
      ib_display_name: record.ib_display_name ?? '',
      ib_roles: record.ib_roles ?? [],
      auth_type: record.auth_type,
      is_service: record.is_service,
      notes: record.notes ?? '',
    })
  }

  const handleIbUserResetForm = () => {
    setEditingIbUser(null)
    ibUserForm.resetFields()
    if (selectedIbDatabaseId) {
      ibUserForm.setFieldsValue({ database_id: selectedIbDatabaseId })
    }
  }

  const handleIbUserSave = async () => {
    const values = await ibUserForm.validateFields()
    const payloadBase = {
      user_id: values.user_id ?? null,
      ib_username: values.ib_username?.trim(),
      ib_display_name: values.ib_display_name?.trim(),
      ib_roles: (values.ib_roles ?? []).map((role: string) => role.trim()).filter(Boolean),
      auth_type: values.auth_type,
      is_service: Boolean(values.is_service),
      notes: values.notes?.trim(),
    }

    if (editingIbUser) {
      updateInfobaseUser.mutate(
        { id: editingIbUser.id, ...payloadBase },
        { onSuccess: handleIbUserResetForm }
      )
      return
    }

    createInfobaseUser.mutate(
      { database_id: values.database_id, ...payloadBase },
      { onSuccess: handleIbUserResetForm }
    )
  }

  const handleIbUserDelete = (record: InfobaseUserMapping) => {
    modal.confirm({
      title: `Удалить пользователя ИБ ${record.ib_username}?`,
      content: 'Запись будет удалена только в Command Center.',
      okText: 'Удалить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => deleteInfobaseUser.mutate({ id: record.id, databaseId: record.database_id }),
    })
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

  const ibAuthTypeLabels: Record<string, string> = {
    local: 'Local',
    ad: 'AD',
    service: 'Service',
    other: 'Other',
  }

  const ibUsersColumns: ColumnsType<InfobaseUserMapping> = useMemo(
    () => [
      {
        title: 'IB User',
        key: 'ib_user',
        render: (_: unknown, row) => (
          <span>
            {row.ib_username}{' '}
            <Text type="secondary">{row.ib_display_name || '-'}</Text>
          </span>
        ),
      },
      {
        title: 'CC User',
        key: 'cc_user',
        render: (_: unknown, row) => (
          row.user
            ? (
              <span>
                {row.user.username} <Text type="secondary">#{row.user.id}</Text>
              </span>
            )
            : '-'
        ),
      },
      {
        title: 'Roles',
        key: 'roles',
        render: (_: unknown, row) => (
          <Space size="small" wrap>
            {(row.ib_roles || []).length > 0
              ? row.ib_roles.map((role) => <Tag key={role}>{role}</Tag>)
              : <Tag color="default">-</Tag>}
          </Space>
        ),
      },
      {
        title: 'Auth',
        key: 'auth_type',
        render: (_: unknown, row) => (
          <Tag>{ibAuthTypeLabels[row.auth_type] || row.auth_type}</Tag>
        ),
      },
      {
        title: 'Service',
        key: 'is_service',
        render: (_: unknown, row) => (
          <Tag color={row.is_service ? 'blue' : 'default'}>
            {row.is_service ? 'Yes' : 'No'}
          </Tag>
        ),
      },
      {
        title: 'Action',
        key: 'actions',
        render: (_: unknown, row) => (
          <Space size="small">
            <Button size="small" onClick={() => handleIbUserEdit(row)}>
              Edit
            </Button>
            <Button
              danger
              size="small"
              loading={deleteInfobaseUser.isPending}
              onClick={() => handleIbUserDelete(row)}
            >
              Delete
            </Button>
          </Space>
        ),
      },
    ],
    [deleteInfobaseUser.isPending, handleIbUserDelete, handleIbUserEdit]
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

  const ibUsersTable = useTableToolkit({
    tableId: 'rbac_ib_users',
    columns: ibUsersColumns,
    fallbackColumns: [
      { key: 'ib_username', label: 'IB User', groupKey: 'core', groupLabel: 'Core' },
      { key: 'ib_display_name', label: 'Display Name', groupKey: 'core', groupLabel: 'Core' },
      { key: 'cc_user', label: 'CC User', groupKey: 'core', groupLabel: 'Core' },
      { key: 'roles', label: 'Roles', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'auth_type', label: 'Auth', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'is_service', label: 'Service', groupKey: 'meta', groupLabel: 'Meta' },
      { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
    ],
    initialPageSize: 25,
  })

  const clusterPageStart = (clusterTable.pagination.page - 1) * clusterTable.pagination.pageSize
  const databasePageStart = (databaseTable.pagination.page - 1) * databaseTable.pagination.pageSize
  const ibUsersPageStart = (ibUsersTable.pagination.page - 1) * ibUsersTable.pagination.pageSize

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

  const ibUsersQuery = useInfobaseUsers({
    databaseId: selectedIbDatabaseId,
    search: ibUsersTable.search || undefined,
    authType: ibAuthFilter === 'any' ? undefined : (ibAuthFilter as 'local' | 'ad' | 'service' | 'other'),
    isService: ibServiceFilter === 'any' ? undefined : ibServiceFilter === 'true',
    hasUser: ibHasUserFilter === 'any' ? undefined : ibHasUserFilter === 'true',
    limit: ibUsersTable.pagination.pageSize,
    offset: ibUsersPageStart,
  })

  const usersQuery = useRbacUsers({
    search: userSearch || undefined,
    limit: 20,
    offset: 0,
  })

  const clusterPermissions = clusterPermissionsQuery.data?.permissions ?? []
  const totalClusterPermissions = typeof clusterPermissionsQuery.data?.total === 'number'
    ? clusterPermissionsQuery.data.total
    : clusterPermissions.length

  const databasePermissions = databasePermissionsQuery.data?.permissions ?? []
  const totalDatabasePermissions = typeof databasePermissionsQuery.data?.total === 'number'
    ? databasePermissionsQuery.data.total
    : databasePermissions.length

  const ibUsers = ibUsersQuery.data?.users ?? []
  const totalIbUsers = typeof ibUsersQuery.data?.total === 'number'
    ? ibUsersQuery.data.total
    : ibUsers.length

  const userOptions = useMemo(() => {
    const base = usersQuery.data?.users ?? []
    const extra = editingIbUser?.user
      ? [editingIbUser.user]
      : []
    const combined = [...base, ...extra]
    const map = new Map<number, { label: string; value: number }>()
    combined.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users, editingIbUser?.user])

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
                      <InputNumber id="rbac-cluster-user-id" min={1} placeholder="User ID" />
                    </Form.Item>
                    <Form.Item name="cluster_id" rules={[{ required: true, message: 'cluster_id required' }]}>
                      <Select
                        id="rbac-cluster-id"
                        style={{ width: 320 }}
                        placeholder="Cluster"
                        options={clusters.map((c) => ({ label: c.name, value: c.id }))}
                        showSearch
                        optionFilterProp="label"
                      />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select id="rbac-cluster-level" style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input id="rbac-cluster-notes" placeholder="Notes (optional)" style={{ width: 260 }} />
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
                      <InputNumber id="rbac-database-user-id" min={1} placeholder="User ID" />
                    </Form.Item>
                    <Form.Item name="database_id" rules={[{ required: true, message: 'database_id required' }]}>
                      <Input id="rbac-database-id" placeholder="Database ID" style={{ width: 240 }} />
                    </Form.Item>
                    <Form.Item name="level" rules={[{ required: true }]}>
                      <Select id="rbac-database-level" style={{ width: 140 }} options={LEVEL_OPTIONS} />
                    </Form.Item>
                    <Form.Item name="notes">
                      <Input id="rbac-database-notes" placeholder="Notes (optional)" style={{ width: 260 }} />
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
          {
            key: 'ib-users',
            label: 'Infobase Users',
            children: (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Card title="Infobase Users" size="small">
                  {!selectedIbDatabaseId && (
                    <Alert
                      type="info"
                      message="Select a database to view infobase users"
                      style={{ marginBottom: 12 }}
                    />
                  )}
                  <TableToolkit
                    table={ibUsersTable}
                    data={selectedIbDatabaseId ? ibUsers : []}
                    total={selectedIbDatabaseId ? totalIbUsers : 0}
                    loading={ibUsersQuery.isLoading}
                    rowKey="id"
                    columns={ibUsersColumns}
                    searchPlaceholder="Search infobase users"
                    toolbarActions={(
                      <Space>
                        <Select
                          style={{ width: 320 }}
                          placeholder="Database"
                          allowClear
                          value={selectedIbDatabaseId}
                          onChange={(value) => {
                            setSelectedIbDatabaseId(value)
                            if (!editingIbUser) {
                              ibUserForm.setFieldsValue({ database_id: value })
                            }
                          }}
                          options={databases.map((db) => ({ label: db.name, value: db.id }))}
                          showSearch
                          optionFilterProp="label"
                        />
                        <Select
                          style={{ width: 160 }}
                          value={ibAuthFilter}
                          onChange={setIbAuthFilter}
                          options={[
                            { label: 'Auth: Any', value: 'any' },
                            { label: 'Auth: Local', value: 'local' },
                            { label: 'Auth: AD', value: 'ad' },
                            { label: 'Auth: Service', value: 'service' },
                            { label: 'Auth: Other', value: 'other' },
                          ]}
                        />
                        <Select
                          style={{ width: 160 }}
                          value={ibServiceFilter}
                          onChange={setIbServiceFilter}
                          options={[
                            { label: 'Service: Any', value: 'any' },
                            { label: 'Service: Yes', value: 'true' },
                            { label: 'Service: No', value: 'false' },
                          ]}
                        />
                        <Select
                          style={{ width: 160 }}
                          value={ibHasUserFilter}
                          onChange={setIbHasUserFilter}
                          options={[
                            { label: 'CC User: Any', value: 'any' },
                            { label: 'CC User: Linked', value: 'true' },
                            { label: 'CC User: Unlinked', value: 'false' },
                          ]}
                        />
                        <Button
                          onClick={() => ibUsersQuery.refetch()}
                          disabled={!selectedIbDatabaseId}
                          loading={ibUsersQuery.isFetching}
                        >
                          Refresh
                        </Button>
                      </Space>
                    )}
                  />
                </Card>

                <Card title={editingIbUser ? 'Edit Infobase User' : 'Add Infobase User'} size="small">
                  <Form
                    form={ibUserForm}
                    layout="vertical"
                    initialValues={{ auth_type: 'local', is_service: false }}
                  >
                    <Space size="large" align="start" wrap>
                      <Form.Item
                        label="Database"
                        name="database_id"
                        rules={[{ required: true, message: 'database_id required' }]}
                      >
                        <Select
                          style={{ width: 320 }}
                          placeholder="Database"
                          options={databases.map((db) => ({ label: db.name, value: db.id }))}
                          showSearch
                          optionFilterProp="label"
                          disabled={Boolean(editingIbUser)}
                          onChange={(value) => setSelectedIbDatabaseId(value)}
                        />
                      </Form.Item>
                      <Form.Item
                        label="IB Username"
                        name="ib_username"
                        rules={[{ required: true, message: 'ib_username required' }]}
                      >
                        <Input placeholder="ib_user" />
                      </Form.Item>
                      <Form.Item label="IB Display Name" name="ib_display_name">
                        <Input placeholder="Display name" />
                      </Form.Item>
                      <Form.Item label="CC User ID" name="user_id">
                        <Select
                          showSearch
                          allowClear
                          placeholder="Select user"
                          filterOption={false}
                          onSearch={(value) => setUserSearch(value)}
                          options={userOptions}
                          loading={usersQuery.isFetching}
                          style={{ width: 220 }}
                        />
                      </Form.Item>
                      <Form.Item label="Auth Type" name="auth_type">
                        <Select
                          style={{ width: 160 }}
                          options={[
                            { label: 'Local', value: 'local' },
                            { label: 'AD', value: 'ad' },
                            { label: 'Service', value: 'service' },
                            { label: 'Other', value: 'other' },
                          ]}
                        />
                      </Form.Item>
                      <Form.Item label="Service Account" name="is_service" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Space>
                    <Form.Item label="Roles" name="ib_roles">
                      <Select mode="tags" tokenSeparators={[',']} placeholder="Roles (comma separated)" />
                    </Form.Item>
                    <Form.Item label="Notes" name="notes">
                      <Input placeholder="Optional notes" />
                    </Form.Item>
                    <Space>
                      <Button
                        type="primary"
                        onClick={handleIbUserSave}
                        loading={createInfobaseUser.isPending || updateInfobaseUser.isPending}
                      >
                        {editingIbUser ? 'Update' : 'Add'}
                      </Button>
                      {editingIbUser && (
                        <Button onClick={handleIbUserResetForm}>Cancel edit</Button>
                      )}
                    </Space>
                  </Form>
                </Card>
              </Space>
            ),
          },
        ]}
      />
    </div>
  )
}
