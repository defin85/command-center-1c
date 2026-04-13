import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Select, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { DbmsUserMapping } from '../../../api/generated/model/dbmsUserMapping'
import { useCreateDbmsUser, useDbmsUsers, useDeleteDbmsUser, useResetDbmsUserPassword, useSetDbmsUserPassword, useUpdateDbmsUser } from '../../../api/queries/databases'
import { useRbacRefDatabases, useRbacUsers } from '../../../api/queries/rbac'
import { useRbacTranslation } from '../../../i18n'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'
import { usePaginatedRefSelectOptions } from '../hooks/usePaginatedRefSelectOptions'
import { validateDbmsUserId } from '../utils/dbmsUsers'

const { Text } = Typography

export function DbmsUsersTab(props: { enabled: boolean }) {
  const { enabled } = props
  const { modal, message } = App.useApp()
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

  const createDbmsUser = useCreateDbmsUser()
  const updateDbmsUser = useUpdateDbmsUser()
  const deleteDbmsUser = useDeleteDbmsUser()
  const setDbmsUserPassword = useSetDbmsUserPassword()
  const resetDbmsUserPassword = useResetDbmsUserPassword()

  const [selectedDatabaseId, setSelectedDatabaseId] = useState<string | undefined>()
  const [editingDbmsUser, setEditingDbmsUser] = useState<DbmsUserMapping | null>(null)
  const [dbmsAuthFilter, setDbmsAuthFilter] = useState<string>('any')
  const [dbmsServiceFilter, setDbmsServiceFilter] = useState<string>('any')
  const [dbmsHasUserFilter, setDbmsHasUserFilter] = useState<string>('any')

  const [userSearch, setUserSearch] = useState<string>('')
  const usersQuery = useRbacUsers({
    search: userSearch.trim() || undefined,
    limit: 20,
    offset: 0,
  }, { enabled })

  const userOptions = useMemo(() => {
    const base = usersQuery.data?.users ?? []
    const extra = editingDbmsUser?.user ? [editingDbmsUser.user] : []
    const combined = [...base, ...extra]
    const map = new Map<number, { label: string; value: number }>()
    combined.forEach((user) => {
      if (!map.has(user.id)) {
        map.set(user.id, { label: `${user.username} #${user.id}`, value: user.id })
      }
    })
    return Array.from(map.values())
  }, [usersQuery.data?.users, editingDbmsUser?.user])

  const [dbmsUserForm] = Form.useForm<{
    database_id?: string
    user_id?: number | null
    db_username?: string
    auth_type?: DbmsUserMapping['auth_type']
    is_service?: boolean
    notes?: string
  }>()

  const dbmsUserFormIsService = Form.useWatch('is_service', dbmsUserForm)

  useEffect(() => {
    if (!dbmsUserFormIsService) return
    dbmsUserForm.setFieldValue('user_id', null)
  }, [dbmsUserFormIsService, dbmsUserForm])

  const getDbmsAuthTypeLabel = useCallback((authType: string | undefined): string => {
    const key = (authType ?? 'local') as 'local' | 'service' | 'other'
    return t(($) => $.dbmsUsers.authTypes[key])
  }, [t])

  const getDbmsPasswordConfiguredLabel = useCallback((configured: boolean): string => (
    configured ? t(($) => $.dbmsUsers.values.set) : t(($) => $.dbmsUsers.values.unset)
  ), [t])

  const handleEdit = useCallback((record: DbmsUserMapping) => {
    setSelectedDatabaseId(record.database_id)
    setEditingDbmsUser(record)
    dbmsUserForm.setFieldsValue({
      database_id: record.database_id,
      user_id: record.user?.id ?? null,
      db_username: record.db_username,
      auth_type: record.auth_type ?? 'local',
      is_service: Boolean(record.is_service),
      notes: record.notes ?? '',
    })
  }, [dbmsUserForm])

  const handleResetForm = useCallback(() => {
    setEditingDbmsUser(null)
    dbmsUserForm.resetFields()
    if (selectedDatabaseId) {
      dbmsUserForm.setFieldsValue({ database_id: selectedDatabaseId })
    }
  }, [dbmsUserForm, selectedDatabaseId])

  const handleSave = useCallback(async () => {
    const values = await dbmsUserForm.validateFields()
    const dbUsername = values.db_username?.trim()
    if (!dbUsername) {
      message.error(t(($) => $.dbmsUsers.messages.usernameRequired))
      return
    }
    const isService = Boolean(values.is_service)
    const payloadBase = {
      user_id: isService ? null : (values.user_id ?? null),
      db_username: dbUsername,
      auth_type: values.auth_type,
      is_service: isService,
      notes: values.notes?.trim(),
    }

    if (editingDbmsUser) {
      updateDbmsUser.mutate(
        { id: editingDbmsUser.id, ...payloadBase },
        { onSuccess: handleResetForm }
      )
      return
    }

    if (!values.database_id) {
      message.error(t(($) => $.dbmsUsers.messages.databaseRequired))
      return
    }
    createDbmsUser.mutate(
      { database_id: values.database_id, ...payloadBase },
      { onSuccess: handleResetForm }
    )
  }, [createDbmsUser, dbmsUserForm, editingDbmsUser, handleResetForm, message, t, updateDbmsUser])

  const handleDelete = useCallback((record: DbmsUserMapping) => {
    confirmWithTracking(modal, {
      title: t(($) => $.dbmsUsers.confirm.deleteTitle, { username: record.db_username }),
      content: t(($) => $.dbmsUsers.confirm.deleteDescription),
      okText: t(($) => $.dbmsUsers.actions.delete),
      cancelText: t(($) => $.dbmsUsers.confirm.cancel),
      okButtonProps: { danger: true },
      onOk: () => deleteDbmsUser.mutate({ id: record.id, databaseId: record.database_id }),
    })
  }, [deleteDbmsUser, modal, t])

  const handlePasswordSet = useCallback((record: DbmsUserMapping) => {
    let password = ''
    confirmWithTracking(modal, {
      title: t(($) => $.dbmsUsers.confirm.setPasswordTitle, { username: record.db_username }),
      okText: t(($) => $.dbmsUsers.confirm.setPassword),
      cancelText: t(($) => $.dbmsUsers.confirm.cancel),
      okButtonProps: { 'data-testid': 'rbac-dbms-user-set-password-ok' },
      content: (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Text type="secondary">{t(($) => $.dbmsUsers.messages.setPasswordCurrentHidden)}</Text>
          <Input.Password
            data-testid="rbac-dbms-user-set-password-input"
            placeholder={t(($) => $.dbmsUsers.form.newPasswordPlaceholder)}
            onChange={(e) => {
              password = e.target.value
            }}
          />
        </Space>
      ),
      onOk: async () => {
        const trimmed = password.trim()
        if (!trimmed) {
          message.error(t(($) => $.dbmsUsers.messages.passwordRequired))
          throw new Error('Password is empty')
        }
        await setDbmsUserPassword.mutateAsync({ id: record.id, password: trimmed })
      },
    })
  }, [message, modal, setDbmsUserPassword, t])

  const handlePasswordReset = useCallback((record: DbmsUserMapping) => {
    confirmWithTracking(modal, {
      title: t(($) => $.dbmsUsers.confirm.resetPasswordTitle, { username: record.db_username }),
      content: t(($) => $.dbmsUsers.confirm.resetPasswordDescription),
      okText: t(($) => $.dbmsUsers.confirm.resetPassword),
      cancelText: t(($) => $.dbmsUsers.confirm.cancel),
      okButtonProps: { danger: true, 'data-testid': 'rbac-dbms-user-reset-password-ok' },
      onOk: async () => {
        await resetDbmsUserPassword.mutateAsync({ id: record.id, databaseId: record.database_id })
      },
    })
  }, [modal, resetDbmsUserPassword, t])

  const columns: ColumnsType<DbmsUserMapping> = useMemo(() => [
    {
      title: t(($) => $.dbmsUsers.columns.dbmsUser),
      key: 'db_username',
      render: (_: unknown, row) => <span>{row.db_username}</span>,
    },
    {
      title: t(($) => $.dbmsUsers.columns.commandCenterUser),
      key: 'cc_user',
      render: (_: unknown, row) => (
        row.user
          ? (
            <span>
              {row.user.username} <Text type="secondary">#{row.user.id}</Text>
            </span>
          )
          : t(($) => $.dbmsUsers.values.empty)
      ),
    },
    {
      title: t(($) => $.dbmsUsers.columns.authType),
      key: 'auth_type',
      render: (_: unknown, row) => <Tag>{getDbmsAuthTypeLabel(row.auth_type)}</Tag>,
    },
    {
      title: t(($) => $.dbmsUsers.columns.service),
      key: 'is_service',
      render: (_: unknown, row) => (
        <Tag color={row.is_service ? 'blue' : 'default'}>
          {row.is_service ? t(($) => $.dbmsUsers.values.yes) : t(($) => $.dbmsUsers.values.no)}
        </Tag>
      ),
    },
    {
      title: t(($) => $.dbmsUsers.columns.password),
      key: 'password',
      render: (_: unknown, row) => (
        <Tag color={row.db_password_configured ? 'green' : 'default'}>
          {getDbmsPasswordConfiguredLabel(Boolean(row.db_password_configured))}
        </Tag>
      ),
    },
    {
      title: t(($) => $.dbmsUsers.columns.actions),
      key: 'actions',
      render: (_: unknown, row) => (
        <Space size="small">
          <Button
            size="small"
            data-testid={`rbac-dbms-user-edit-${row.id}`}
            onClick={() => handleEdit(row)}
          >
            {t(($) => $.dbmsUsers.actions.edit)}
          </Button>
          <Button
            size="small"
            loading={setDbmsUserPassword.isPending}
            data-testid={`rbac-dbms-user-set-password-${row.id}`}
            onClick={() => handlePasswordSet(row)}
          >
            {t(($) => $.dbmsUsers.actions.setPassword)}
          </Button>
          <Button
            danger
            size="small"
            loading={resetDbmsUserPassword.isPending}
            data-testid={`rbac-dbms-user-reset-password-${row.id}`}
            onClick={() => handlePasswordReset(row)}
          >
            {t(($) => $.dbmsUsers.actions.resetPassword)}
          </Button>
          <Button
            danger
            size="small"
            loading={deleteDbmsUser.isPending}
            data-testid={`rbac-dbms-user-delete-${row.id}`}
            onClick={() => handleDelete(row)}
          >
            {t(($) => $.dbmsUsers.actions.delete)}
          </Button>
        </Space>
      ),
    },
  ], [
    deleteDbmsUser.isPending,
    getDbmsAuthTypeLabel,
    getDbmsPasswordConfiguredLabel,
    handleDelete,
    handleEdit,
    handlePasswordReset,
    handlePasswordSet,
    resetDbmsUserPassword.isPending,
    setDbmsUserPassword.isPending,
    t,
  ])

  const table = useTableToolkit({
    tableId: 'rbac_dbms_users',
    columns,
    fallbackColumns: [
      { key: 'db_username', label: t(($) => $.dbmsUsers.columns.dbmsUser), groupKey: 'core', groupLabel: t(($) => $.dbmsUsers.groups.core) },
      { key: 'cc_user', label: t(($) => $.dbmsUsers.columns.commandCenterUser), groupKey: 'core', groupLabel: t(($) => $.dbmsUsers.groups.core) },
      { key: 'auth_type', label: t(($) => $.dbmsUsers.columns.authType), groupKey: 'meta', groupLabel: t(($) => $.dbmsUsers.groups.metadata) },
      { key: 'is_service', label: t(($) => $.dbmsUsers.columns.service), groupKey: 'meta', groupLabel: t(($) => $.dbmsUsers.groups.metadata) },
      { key: 'password', label: t(($) => $.dbmsUsers.columns.password), groupKey: 'meta', groupLabel: t(($) => $.dbmsUsers.groups.metadata) },
      { key: 'actions', label: t(($) => $.dbmsUsers.columns.actions), groupKey: 'actions', groupLabel: t(($) => $.dbmsUsers.groups.actions) },
    ],
    initialPageSize: 25,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const dbmsUsersQuery = useDbmsUsers({
    databaseId: enabled ? selectedDatabaseId : undefined,
    search: table.search || undefined,
    authType: dbmsAuthFilter === 'any' ? undefined : (dbmsAuthFilter as 'local' | 'service' | 'other'),
    isService: dbmsServiceFilter === 'any' ? undefined : dbmsServiceFilter === 'true',
    hasUser: dbmsHasUserFilter === 'any' ? undefined : dbmsHasUserFilter === 'true',
    limit: table.pagination.pageSize,
    offset: pageStart,
  })

  const dbmsUsers = dbmsUsersQuery.data?.users ?? []
  const totalDbmsUsers = typeof dbmsUsersQuery.data?.total === 'number'
    ? dbmsUsersQuery.data.total
    : dbmsUsers.length

  const accessDenied = (() => {
    const status = (dbmsUsersQuery.error as { response?: { status?: number } } | null)?.response?.status
    return status === 401 || status === 403
  })()

  if (!enabled) {
    return null
  }

  return accessDenied ? (
    <Alert
      type="warning"
      showIcon
      message={t(($) => $.dbmsUsers.accessDenied)}
    />
  ) : (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title={t(($) => $.dbmsUsers.title)} size="small">
        {!selectedDatabaseId && (
          <Alert
            type="info"
            message={t(($) => $.dbmsUsers.selectDatabaseInfo)}
            style={{ marginBottom: 12 }}
          />
        )}
        <TableToolkit
          table={table}
          data={selectedDatabaseId ? dbmsUsers : []}
          total={selectedDatabaseId ? totalDbmsUsers : 0}
          loading={dbmsUsersQuery.isLoading}
          rowKey="id"
          columns={columns}
          searchPlaceholder={t(($) => $.dbmsUsers.searchPlaceholder)}
          toolbarActions={(
            <Space>
              <Select
                style={{ width: 320 }}
                placeholder={t(($) => $.dbmsUsers.toolbar.databasePlaceholder)}
                allowClear
                data-testid="rbac-dbms-users-toolbar-database"
                value={selectedDatabaseId}
                onChange={(value) => {
                  setSelectedDatabaseId(value)
                  if (!editingDbmsUser) {
                    dbmsUserForm.setFieldsValue({ database_id: value })
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
                value={dbmsAuthFilter}
                onChange={setDbmsAuthFilter}
                options={[
                  { label: t(($) => $.dbmsUsers.toolbar.authAny), value: 'any' },
                  { label: t(($) => $.dbmsUsers.toolbar.authLocal), value: 'local' },
                  { label: t(($) => $.dbmsUsers.toolbar.authService), value: 'service' },
                  { label: t(($) => $.dbmsUsers.toolbar.authOther), value: 'other' },
                ]}
              />
              <Select
                style={{ width: 160 }}
                value={dbmsServiceFilter}
                onChange={setDbmsServiceFilter}
                options={[
                  { label: t(($) => $.dbmsUsers.toolbar.serviceAny), value: 'any' },
                  { label: t(($) => $.dbmsUsers.toolbar.serviceYes), value: 'true' },
                  { label: t(($) => $.dbmsUsers.toolbar.serviceNo), value: 'false' },
                ]}
              />
              <Select
                style={{ width: 180 }}
                value={dbmsHasUserFilter}
                onChange={setDbmsHasUserFilter}
                options={[
                  { label: t(($) => $.dbmsUsers.toolbar.userAny), value: 'any' },
                  { label: t(($) => $.dbmsUsers.toolbar.userAssigned), value: 'true' },
                  { label: t(($) => $.dbmsUsers.toolbar.userUnassigned), value: 'false' },
                ]}
              />
              <Button
                data-testid="rbac-dbms-users-refresh"
                onClick={() => dbmsUsersQuery.refetch()}
                disabled={!selectedDatabaseId}
                loading={dbmsUsersQuery.isFetching}
              >
                {t(($) => $.dbmsUsers.toolbar.refresh)}
              </Button>
            </Space>
          )}
        />
      </Card>

      <Card title={editingDbmsUser ? t(($) => $.dbmsUsers.form.editTitle) : t(($) => $.dbmsUsers.form.createTitle)} size="small">
        <Form
          form={dbmsUserForm}
          layout="vertical"
          initialValues={{ auth_type: 'local', is_service: false }}
        >
          <Space size="large" align="start" wrap>
            <Form.Item
              label={t(($) => $.dbmsUsers.form.database)}
              name="database_id"
              rules={[{ required: true, message: t(($) => $.dbmsUsers.form.databaseRequired) }]}
            >
              <Select
                style={{ width: 320 }}
                placeholder={t(($) => $.dbmsUsers.form.databasePlaceholder)}
                data-testid="rbac-dbms-user-form-database"
                showSearch
                filterOption={false}
                onSearch={setDatabasesRefSearch}
                onPopupScroll={handleDatabasesPopupScroll}
                options={databasesSelectOptions}
                loading={databasesRefQuery.isFetching}
                optionFilterProp="label"
                disabled={Boolean(editingDbmsUser)}
                onChange={(value) => setSelectedDatabaseId(value)}
              />
            </Form.Item>
            <Form.Item
              label={t(($) => $.dbmsUsers.form.username)}
              name="db_username"
              rules={[{ required: true, message: t(($) => $.dbmsUsers.form.usernameRequired) }]}
            >
              <Input data-testid="rbac-dbms-user-form-db-username" placeholder={t(($) => $.dbmsUsers.form.usernamePlaceholder)} />
            </Form.Item>
            <Form.Item label={t(($) => $.dbmsUsers.form.serviceAccount)} name="is_service" valuePropName="checked">
              <Switch data-testid="rbac-dbms-user-form-is-service" />
            </Form.Item>
            <Form.Item
              label={t(($) => $.dbmsUsers.form.user)}
              name="user_id"
              rules={[
                ({ getFieldValue }) => ({
                  validator: (_rule, value) => {
                    const isService = Boolean(getFieldValue('is_service'))
                    const result = validateDbmsUserId(isService, value)
                    if (result === 'ok') return Promise.resolve()
                    if (result === 'must_be_empty') {
                      return Promise.reject(new Error(t(($) => $.dbmsUsers.form.userMustBeEmpty)))
                    }
                    return Promise.reject(new Error(t(($) => $.dbmsUsers.form.userRequired)))
                  },
                }),
              ]}
            >
              <Select
                showSearch
                allowClear
                data-testid="rbac-dbms-user-form-user-id"
                placeholder={dbmsUserFormIsService
                  ? t(($) => $.dbmsUsers.form.userDisabledPlaceholder)
                  : t(($) => $.dbmsUsers.form.userPlaceholder)}
                filterOption={false}
                onSearch={setUserSearch}
                options={userOptions}
                loading={usersQuery.isFetching}
                style={{ width: 240 }}
                disabled={Boolean(dbmsUserFormIsService)}
              />
            </Form.Item>
            <Form.Item label={t(($) => $.dbmsUsers.form.authType)} name="auth_type">
              <Select
                style={{ width: 180 }}
                options={[
                  { label: t(($) => $.dbmsUsers.authTypes.local), value: 'local' },
                  { label: t(($) => $.dbmsUsers.authTypes.service), value: 'service' },
                  { label: t(($) => $.dbmsUsers.authTypes.other), value: 'other' },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item label={t(($) => $.dbmsUsers.form.password)}>
            <Space size="small" wrap>
              <Tag color={editingDbmsUser?.db_password_configured ? 'green' : 'default'}>
                {getDbmsPasswordConfiguredLabel(Boolean(editingDbmsUser?.db_password_configured))}
              </Tag>
              <Text type="secondary">{t(($) => $.dbmsUsers.messages.setPasswordCurrentHidden)}</Text>
              {editingDbmsUser && (
                <Button
                  onClick={() => handlePasswordSet(editingDbmsUser)}
                  loading={setDbmsUserPassword.isPending}
                >
                  {t(($) => $.dbmsUsers.actions.setPassword)}
                </Button>
              )}
              {editingDbmsUser && (
                <Button
                  danger
                  onClick={() => handlePasswordReset(editingDbmsUser)}
                  loading={resetDbmsUserPassword.isPending}
                >
                  {t(($) => $.dbmsUsers.actions.resetPassword)}
                </Button>
              )}
            </Space>
          </Form.Item>
          <Form.Item label={t(($) => $.dbmsUsers.form.notes)} name="notes">
            <Input placeholder={t(($) => $.dbmsUsers.form.notesPlaceholder)} />
          </Form.Item>
          <Space>
            <Button
              type="primary"
              data-testid="rbac-dbms-user-form-save"
              onClick={handleSave}
              loading={createDbmsUser.isPending || updateDbmsUser.isPending}
            >
              {editingDbmsUser ? t(($) => $.dbmsUsers.form.save) : t(($) => $.dbmsUsers.form.add)}
            </Button>
            {editingDbmsUser && (
              <Button data-testid="rbac-dbms-user-form-cancel" onClick={handleResetForm}>
                {t(($) => $.dbmsUsers.form.cancelEdit)}
              </Button>
            )}
          </Space>
        </Form>
      </Card>
    </Space>
  )
}
