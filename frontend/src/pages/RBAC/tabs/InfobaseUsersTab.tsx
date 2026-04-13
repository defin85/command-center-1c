import { useCallback, useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Select, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useCreateInfobaseUser, useDeleteInfobaseUser, useInfobaseUsers, useResetInfobaseUserPassword, useSetInfobaseUserPassword, useUpdateInfobaseUser, type InfobaseUserMapping } from '../../../api/queries/databases'
import { useRbacRefDatabases, useRbacUsers } from '../../../api/queries/rbac'
import { useRbacTranslation } from '../../../i18n'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'
import { usePaginatedRefSelectOptions } from '../hooks/usePaginatedRefSelectOptions'

const { Text } = Typography

export function InfobaseUsersTab(props: { enabled: boolean }) {
  const { enabled } = props
  const { modal } = App.useApp()
  const { t } = useRbacTranslation()

  const REF_PAGE_SIZE = 50

  const {
    setSearch: setDatabasesRefSearch,
    options: databasesSelectOptions,
    query: databasesRefQuery,
    handlePopupScroll: handleDatabasesPopupScroll,
  } = usePaginatedRefSelectOptions({
    enabled,
    pageSize: REF_PAGE_SIZE,
    queryHook: useRbacRefDatabases,
    buildFilters: ({ search, limit, offset }) => ({ search, limit, offset }),
    getItems: (data) => data?.databases,
    getId: (db) => db.id,
    getLabel: (db) => `${db.name} #${db.id}`,
  })

  const createInfobaseUser = useCreateInfobaseUser()
  const updateInfobaseUser = useUpdateInfobaseUser()
  const deleteInfobaseUser = useDeleteInfobaseUser()
  const setInfobaseUserPassword = useSetInfobaseUserPassword()
  const resetInfobaseUserPassword = useResetInfobaseUserPassword()

  const [selectedDatabaseId, setSelectedDatabaseId] = useState<string | undefined>()
  const [editingIbUser, setEditingIbUser] = useState<InfobaseUserMapping | null>(null)
  const [ibAuthFilter, setIbAuthFilter] = useState<string>('any')
  const [ibServiceFilter, setIbServiceFilter] = useState<string>('any')
  const [ibHasUserFilter, setIbHasUserFilter] = useState<string>('any')

  const [userSearch, setUserSearch] = useState<string>('')
  const usersQuery = useRbacUsers({
    search: userSearch.trim() || undefined,
    limit: 20,
    offset: 0,
  }, { enabled })

  const userOptions = useMemo(() => {
    const base = usersQuery.data?.users ?? []
    const extra = editingIbUser?.user ? [editingIbUser.user] : []
    const combined = [...base, ...extra]
    const map = new Map<number, { label: string; value: number }>()
    combined.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users, editingIbUser?.user])

  const [ibUserForm] = Form.useForm<{
    database_id?: string
    user_id?: number | null
    ib_username?: string
    ib_display_name?: string
    ib_roles?: string[]
    ib_password?: string
    auth_type?: InfobaseUserMapping['auth_type']
    is_service?: boolean
    notes?: string
  }>()

  const getIbAuthTypeLabel = useCallback((authType: string | undefined): string => {
    const key = (authType ?? 'local') as 'local' | 'ad' | 'service' | 'other'
    return t(($) => $.infobaseUsers.authTypes[key])
  }, [t])

  const handleEdit = useCallback((record: InfobaseUserMapping) => {
    setSelectedDatabaseId(record.database_id)
    setEditingIbUser(record)
    ibUserForm.setFieldsValue({
      database_id: record.database_id,
      user_id: record.user?.id ?? null,
      ib_username: record.ib_username,
      ib_display_name: record.ib_display_name ?? '',
      ib_roles: record.ib_roles ?? [],
      ib_password: '',
      auth_type: record.auth_type ?? 'local',
      is_service: Boolean(record.is_service),
      notes: record.notes ?? '',
    })
  }, [ibUserForm])

  const handleResetForm = useCallback(() => {
    setEditingIbUser(null)
    ibUserForm.resetFields()
    if (selectedDatabaseId) {
      ibUserForm.setFieldsValue({ database_id: selectedDatabaseId })
    }
  }, [ibUserForm, selectedDatabaseId])

  const handleSave = useCallback(async () => {
    const values = await ibUserForm.validateFields()
    const ibUsername = values.ib_username?.trim()
    if (!ibUsername) {
      modal.warning({
        title: t(($) => $.infobaseUsers.warnings.missingUsernameTitle),
        content: t(($) => $.infobaseUsers.warnings.missingUsernameDescription),
      })
      return
    }
    const payloadBase = {
      user_id: values.user_id ?? null,
      ib_username: ibUsername,
      ib_display_name: values.ib_display_name?.trim(),
      ib_roles: values.ib_roles ?? [],
      auth_type: values.auth_type,
      is_service: Boolean(values.is_service),
      notes: values.notes?.trim(),
    }

    if (editingIbUser) {
      updateInfobaseUser.mutate(
        { id: editingIbUser.id, ...payloadBase },
        { onSuccess: handleResetForm }
      )
      return
    }

    if (!values.database_id) {
      modal.warning({
        title: t(($) => $.infobaseUsers.warnings.missingDatabaseTitle),
        content: t(($) => $.infobaseUsers.warnings.missingDatabaseDescription),
      })
      return
    }
    createInfobaseUser.mutate(
      { database_id: values.database_id, ...payloadBase, ib_password: values.ib_password?.trim() || undefined },
      { onSuccess: handleResetForm }
    )
  }, [createInfobaseUser, editingIbUser, handleResetForm, ibUserForm, modal, t, updateInfobaseUser])

  const handleDelete = useCallback((record: InfobaseUserMapping) => {
    confirmWithTracking(modal, {
      title: t(($) => $.infobaseUsers.confirm.deleteTitle, { username: record.ib_username }),
      content: t(($) => $.infobaseUsers.confirm.deleteDescription),
      okText: t(($) => $.infobaseUsers.confirm.delete),
      cancelText: t(($) => $.infobaseUsers.confirm.cancel),
      okButtonProps: { danger: true },
      onOk: () => deleteInfobaseUser.mutate({ id: record.id, databaseId: record.database_id }),
    })
  }, [deleteInfobaseUser, modal, t])

  const handlePasswordUpdate = useCallback(async () => {
    if (!editingIbUser) return
    const password = ibUserForm.getFieldValue('ib_password')?.trim()
    if (!password) {
      modal.warning({
        title: t(($) => $.infobaseUsers.warnings.missingPasswordTitle),
        content: t(($) => $.infobaseUsers.warnings.missingPasswordDescription),
      })
      return
    }
    setInfobaseUserPassword.mutate(
      { id: editingIbUser.id, password },
      { onSuccess: () => ibUserForm.setFieldsValue({ ib_password: '' }) }
    )
  }, [editingIbUser, ibUserForm, modal, setInfobaseUserPassword, t])

  const handlePasswordReset = useCallback(() => {
    if (!editingIbUser) return
    confirmWithTracking(modal, {
      title: t(($) => $.infobaseUsers.confirm.resetPasswordTitle, { username: editingIbUser.ib_username }),
      content: t(($) => $.infobaseUsers.confirm.resetPasswordDescription),
      okText: t(($) => $.infobaseUsers.confirm.reset),
      cancelText: t(($) => $.infobaseUsers.confirm.cancel),
      okButtonProps: { danger: true },
      onOk: () => resetInfobaseUserPassword.mutate({ id: editingIbUser.id, databaseId: editingIbUser.database_id }),
    })
  }, [editingIbUser, modal, resetInfobaseUserPassword, t])

  const columns: ColumnsType<InfobaseUserMapping> = useMemo(() => [
    {
      title: t(($) => $.infobaseUsers.columns.infobaseUser),
      key: 'ib_username',
      render: (_: unknown, row) => <span>{row.ib_username}</span>,
    },
    {
      title: t(($) => $.infobaseUsers.columns.displayName),
      key: 'ib_display_name',
      render: (_: unknown, row) => <span>{row.ib_display_name || t(($) => $.infobaseUsers.values.empty)}</span>,
    },
    {
      title: t(($) => $.infobaseUsers.columns.commandCenterUser),
      key: 'cc_user',
      render: (_: unknown, row) => (
        row.user
          ? (
            <span>
              {row.user.username} <Text type="secondary">#{row.user.id}</Text>
            </span>
          )
          : t(($) => $.infobaseUsers.values.empty)
      ),
    },
    {
      title: t(($) => $.infobaseUsers.columns.roles),
      key: 'roles',
      render: (_: unknown, row) => {
        const roles = row.ib_roles ?? []
        if (roles.length === 0) return t(($) => $.infobaseUsers.values.empty)
        return (
          <Space size={4} wrap>
            {roles.slice(0, 6).map((role) => <Tag key={role}>{role}</Tag>)}
            {roles.length > 6 && <Text type="secondary">+{roles.length - 6}</Text>}
          </Space>
        )
      },
    },
    {
      title: t(($) => $.infobaseUsers.columns.authType),
      key: 'auth_type',
      render: (_: unknown, row) => <Tag>{getIbAuthTypeLabel(row.auth_type)}</Tag>,
    },
    {
      title: t(($) => $.infobaseUsers.columns.service),
      key: 'is_service',
      render: (_: unknown, row) => (
        <Tag color={row.is_service ? 'blue' : 'default'}>
          {row.is_service ? t(($) => $.infobaseUsers.values.yes) : t(($) => $.infobaseUsers.values.no)}
        </Tag>
      ),
    },
    {
      title: t(($) => $.infobaseUsers.columns.password),
      key: 'password',
      render: (_: unknown, row) => (
        <Tag color={row.ib_password_configured ? 'green' : 'default'}>
          {row.ib_password_configured ? t(($) => $.infobaseUsers.values.set) : t(($) => $.infobaseUsers.values.unset)}
        </Tag>
      ),
    },
    {
      title: t(($) => $.infobaseUsers.columns.actions),
      key: 'actions',
      render: (_: unknown, row) => (
        <Space size="small">
          <Button size="small" onClick={() => handleEdit(row)}>
            {t(($) => $.infobaseUsers.actions.edit)}
          </Button>
          <Button
            danger
            size="small"
            loading={deleteInfobaseUser.isPending}
            onClick={() => handleDelete(row)}
          >
            {t(($) => $.infobaseUsers.actions.delete)}
          </Button>
        </Space>
      ),
    },
  ], [deleteInfobaseUser.isPending, getIbAuthTypeLabel, handleDelete, handleEdit, t])

  const table = useTableToolkit({
    tableId: 'rbac_ib_users',
    columns,
    fallbackColumns: [
      { key: 'ib_username', label: t(($) => $.infobaseUsers.columns.infobaseUser), groupKey: 'core', groupLabel: t(($) => $.infobaseUsers.groups.core) },
      { key: 'ib_display_name', label: t(($) => $.infobaseUsers.columns.displayName), groupKey: 'core', groupLabel: t(($) => $.infobaseUsers.groups.core) },
      { key: 'cc_user', label: t(($) => $.infobaseUsers.columns.commandCenterUser), groupKey: 'core', groupLabel: t(($) => $.infobaseUsers.groups.core) },
      { key: 'roles', label: t(($) => $.infobaseUsers.columns.roles), groupKey: 'meta', groupLabel: t(($) => $.infobaseUsers.groups.metadata) },
      { key: 'auth_type', label: t(($) => $.infobaseUsers.columns.authType), groupKey: 'meta', groupLabel: t(($) => $.infobaseUsers.groups.metadata) },
      { key: 'is_service', label: t(($) => $.infobaseUsers.columns.service), groupKey: 'meta', groupLabel: t(($) => $.infobaseUsers.groups.metadata) },
      { key: 'password', label: t(($) => $.infobaseUsers.columns.password), groupKey: 'meta', groupLabel: t(($) => $.infobaseUsers.groups.metadata) },
      { key: 'actions', label: t(($) => $.infobaseUsers.columns.actions), groupKey: 'actions', groupLabel: t(($) => $.infobaseUsers.groups.actions) },
    ],
    initialPageSize: 25,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const ibUsersQuery = useInfobaseUsers({
    databaseId: selectedDatabaseId,
    search: table.search || undefined,
    authType: ibAuthFilter === 'any' ? undefined : (ibAuthFilter as 'local' | 'ad' | 'service' | 'other'),
    isService: ibServiceFilter === 'any' ? undefined : ibServiceFilter === 'true',
    hasUser: ibHasUserFilter === 'any' ? undefined : ibHasUserFilter === 'true',
    limit: table.pagination.pageSize,
    offset: pageStart,
  })

  const ibUsers = ibUsersQuery.data?.users ?? []
  const totalIbUsers = typeof ibUsersQuery.data?.total === 'number'
    ? ibUsersQuery.data.total
    : ibUsers.length

  if (!enabled) return null

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title={t(($) => $.infobaseUsers.title)} size="small">
        {!selectedDatabaseId && (
          <Alert
            type="info"
            message={t(($) => $.infobaseUsers.selectDatabaseInfo)}
            style={{ marginBottom: 12 }}
          />
        )}
        <TableToolkit
          table={table}
          data={selectedDatabaseId ? ibUsers : []}
          total={selectedDatabaseId ? totalIbUsers : 0}
          loading={ibUsersQuery.isLoading}
          rowKey="id"
          columns={columns}
          searchPlaceholder={t(($) => $.infobaseUsers.searchPlaceholder)}
          toolbarActions={(
            <Space>
              <Select
                style={{ width: 320 }}
                placeholder={t(($) => $.infobaseUsers.toolbar.databasePlaceholder)}
                allowClear
                value={selectedDatabaseId}
                onChange={(value) => {
                  setSelectedDatabaseId(value)
                  if (!editingIbUser) {
                    ibUserForm.setFieldsValue({ database_id: value })
                  }
                }}
                showSearch
                filterOption={false}
                onSearch={setDatabasesRefSearch}
                onPopupScroll={handleDatabasesPopupScroll}
                options={databasesSelectOptions}
                loading={databasesRefQuery.isFetching}
                optionFilterProp="label"
              />
              <Select
                style={{ width: 180 }}
                value={ibAuthFilter}
                onChange={setIbAuthFilter}
                options={[
                  { label: t(($) => $.infobaseUsers.toolbar.authAny), value: 'any' },
                  { label: t(($) => $.infobaseUsers.toolbar.authLocal), value: 'local' },
                  { label: t(($) => $.infobaseUsers.toolbar.authAd), value: 'ad' },
                  { label: t(($) => $.infobaseUsers.toolbar.authService), value: 'service' },
                  { label: t(($) => $.infobaseUsers.toolbar.authOther), value: 'other' },
                ]}
              />
              <Select
                style={{ width: 160 }}
                value={ibServiceFilter}
                onChange={setIbServiceFilter}
                options={[
                  { label: t(($) => $.infobaseUsers.toolbar.serviceAny), value: 'any' },
                  { label: t(($) => $.infobaseUsers.toolbar.serviceYes), value: 'true' },
                  { label: t(($) => $.infobaseUsers.toolbar.serviceNo), value: 'false' },
                ]}
              />
              <Select
                style={{ width: 180 }}
                value={ibHasUserFilter}
                onChange={setIbHasUserFilter}
                options={[
                  { label: t(($) => $.infobaseUsers.toolbar.userAny), value: 'any' },
                  { label: t(($) => $.infobaseUsers.toolbar.userAssigned), value: 'true' },
                  { label: t(($) => $.infobaseUsers.toolbar.userUnassigned), value: 'false' },
                ]}
              />
              <Button
                onClick={() => ibUsersQuery.refetch()}
                disabled={!selectedDatabaseId}
                loading={ibUsersQuery.isFetching}
              >
                {t(($) => $.infobaseUsers.toolbar.refresh)}
              </Button>
            </Space>
          )}
        />
      </Card>

      <Card title={editingIbUser ? t(($) => $.infobaseUsers.form.editTitle) : t(($) => $.infobaseUsers.form.createTitle)} size="small">
        <Form
          form={ibUserForm}
          layout="vertical"
          initialValues={{ auth_type: 'local', is_service: false }}
        >
          <Space size="large" align="start" wrap>
            <Form.Item
              label={t(($) => $.infobaseUsers.form.database)}
              name="database_id"
              rules={[{ required: true, message: t(($) => $.infobaseUsers.form.databaseRequired) }]}
            >
              <Select
                style={{ width: 320 }}
                placeholder={t(($) => $.infobaseUsers.form.databasePlaceholder)}
                showSearch
                filterOption={false}
                onSearch={setDatabasesRefSearch}
                onPopupScroll={handleDatabasesPopupScroll}
                options={databasesSelectOptions}
                loading={databasesRefQuery.isFetching}
                optionFilterProp="label"
                disabled={Boolean(editingIbUser)}
                onChange={(value) => setSelectedDatabaseId(value)}
              />
            </Form.Item>
            <Form.Item
              label={t(($) => $.infobaseUsers.form.username)}
              name="ib_username"
              rules={[{ required: true, message: t(($) => $.infobaseUsers.form.usernameRequired) }]}
            >
              <Input placeholder={t(($) => $.infobaseUsers.form.usernamePlaceholder)} />
            </Form.Item>
            <Form.Item label={t(($) => $.infobaseUsers.form.displayName)} name="ib_display_name">
              <Input placeholder={t(($) => $.infobaseUsers.form.displayNamePlaceholder)} />
            </Form.Item>
            <Form.Item label={t(($) => $.infobaseUsers.form.user)} name="user_id">
              <Select
                showSearch
                allowClear
                placeholder={t(($) => $.infobaseUsers.form.userPlaceholder)}
                filterOption={false}
                onSearch={setUserSearch}
                options={userOptions}
                loading={usersQuery.isFetching}
                style={{ width: 240 }}
              />
            </Form.Item>
            <Form.Item label={t(($) => $.infobaseUsers.form.authType)} name="auth_type">
              <Select
                style={{ width: 180 }}
                options={[
                  { label: t(($) => $.infobaseUsers.authTypes.local), value: 'local' },
                  { label: t(($) => $.infobaseUsers.authTypes.ad), value: 'ad' },
                  { label: t(($) => $.infobaseUsers.authTypes.service), value: 'service' },
                  { label: t(($) => $.infobaseUsers.authTypes.other), value: 'other' },
                ]}
              />
            </Form.Item>
            <Form.Item label={t(($) => $.infobaseUsers.form.serviceAccount)} name="is_service" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item label={t(($) => $.infobaseUsers.form.roles)} name="ib_roles">
            <Select mode="tags" tokenSeparators={[',']} placeholder={t(($) => $.infobaseUsers.form.rolesPlaceholder)} />
          </Form.Item>
          <Form.Item
            label={editingIbUser ? t(($) => $.infobaseUsers.form.passwordEdit) : t(($) => $.infobaseUsers.form.passwordCreate)}
            name="ib_password"
            help={(
              <Space size="small">
                {editingIbUser ? (
                  <span>{t(($) => $.infobaseUsers.form.passwordHelpEdit)}</span>
                ) : (
                  <span>{t(($) => $.infobaseUsers.form.passwordHelpCreate)}</span>
                )}
                <Tag color={editingIbUser?.ib_password_configured ? 'green' : 'default'}>
                  {editingIbUser?.ib_password_configured ? t(($) => $.infobaseUsers.values.set) : t(($) => $.infobaseUsers.values.unset)}
                </Tag>
              </Space>
            )}
          >
            <Input.Password placeholder={t(($) => $.infobaseUsers.form.passwordPlaceholder)} />
          </Form.Item>
          <Form.Item label={t(($) => $.infobaseUsers.form.notes)} name="notes">
            <Input placeholder={t(($) => $.infobaseUsers.form.notesPlaceholder)} />
          </Form.Item>
          <Space>
            <Button
              type="primary"
              onClick={handleSave}
              loading={createInfobaseUser.isPending || updateInfobaseUser.isPending}
            >
              {editingIbUser ? t(($) => $.infobaseUsers.form.save) : t(($) => $.infobaseUsers.form.add)}
            </Button>
            {editingIbUser && (
              <Button
                onClick={handlePasswordUpdate}
                loading={setInfobaseUserPassword.isPending}
              >
                {t(($) => $.infobaseUsers.form.updatePassword)}
              </Button>
            )}
            {editingIbUser && (
              <Button
                danger
                onClick={handlePasswordReset}
                loading={resetInfobaseUserPassword.isPending}
              >
                {t(($) => $.infobaseUsers.form.resetPassword)}
              </Button>
            )}
            {editingIbUser && (
              <Button onClick={handleResetForm}>{t(($) => $.infobaseUsers.form.cancelEdit)}</Button>
            )}
          </Space>
        </Form>
      </Card>
    </Space>
  )
}
