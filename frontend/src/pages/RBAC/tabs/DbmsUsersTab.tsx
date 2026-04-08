import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Select, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { DbmsUserMapping } from '../../../api/generated/model/dbmsUserMapping'
import { useDbmsUsers, useCreateDbmsUser, useDeleteDbmsUser, useResetDbmsUserPassword, useSetDbmsUserPassword, useUpdateDbmsUser } from '../../../api/queries/databases'
import { useRbacRefDatabases, useRbacUsers } from '../../../api/queries/rbac'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'
import { usePaginatedRefSelectOptions } from '../hooks/usePaginatedRefSelectOptions'
import { getDbmsAuthTypeLabel, getDbmsPasswordConfiguredLabel, validateDbmsUserId } from '../utils/dbmsUsers'

const { Text } = Typography

export function DbmsUsersTab(props: { enabled: boolean }) {
  const { enabled } = props
  const { modal, message } = App.useApp()

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
      message.error('Введите DBMS username')
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
      message.error('Выберите базу')
      return
    }
    createDbmsUser.mutate(
      { database_id: values.database_id, ...payloadBase },
      { onSuccess: handleResetForm }
    )
  }, [createDbmsUser, dbmsUserForm, editingDbmsUser, handleResetForm, message, updateDbmsUser])

  const handleDelete = useCallback((record: DbmsUserMapping) => {
    confirmWithTracking(modal, {
      title: `Удалить DBMS mapping ${record.db_username}?`,
      content: 'Запись будет удалена только в Command Center.',
      okText: 'Удалить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => deleteDbmsUser.mutate({ id: record.id, databaseId: record.database_id }),
    })
  }, [deleteDbmsUser, modal])

  const handlePasswordSet = useCallback((record: DbmsUserMapping) => {
    let password = ''
    confirmWithTracking(modal, {
      title: `Установить пароль для ${record.db_username}?`,
      okText: 'Установить',
      cancelText: 'Отмена',
      okButtonProps: { 'data-testid': 'rbac-dbms-user-set-password-ok' },
      content: (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Text type="secondary">Текущий пароль не отображается.</Text>
          <Input.Password
            data-testid="rbac-dbms-user-set-password-input"
            placeholder="Новый пароль"
            onChange={(e) => {
              password = e.target.value
            }}
          />
        </Space>
      ),
      onOk: async () => {
        const trimmed = password.trim()
        if (!trimmed) {
          message.error('Введите пароль')
          throw new Error('Password is empty')
        }
        await setDbmsUserPassword.mutateAsync({ id: record.id, password: trimmed })
      },
    })
  }, [message, modal, setDbmsUserPassword])

  const handlePasswordReset = useCallback((record: DbmsUserMapping) => {
    confirmWithTracking(modal, {
      title: `Сбросить пароль для ${record.db_username}?`,
      content: 'Пароль будет очищен.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true, 'data-testid': 'rbac-dbms-user-reset-password-ok' },
      onOk: async () => {
        await resetDbmsUserPassword.mutateAsync({ id: record.id, databaseId: record.database_id })
      },
    })
  }, [modal, resetDbmsUserPassword])

  const columns: ColumnsType<DbmsUserMapping> = useMemo(() => [
    {
      title: 'Пользователь DBMS',
      key: 'db_username',
      render: (_: unknown, row) => <span>{row.db_username}</span>,
    },
    {
      title: 'Пользователь CC',
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
      title: 'Аутентификация',
      key: 'auth_type',
      render: (_: unknown, row) => <Tag>{getDbmsAuthTypeLabel(row.auth_type)}</Tag>,
    },
    {
      title: 'Сервисный',
      key: 'is_service',
      render: (_: unknown, row) => (
        <Tag color={row.is_service ? 'blue' : 'default'}>
          {row.is_service ? 'Да' : 'Нет'}
        </Tag>
      ),
    },
    {
      title: 'Пароль',
      key: 'password',
      render: (_: unknown, row) => (
        <Tag color={row.db_password_configured ? 'green' : 'default'}>
          {getDbmsPasswordConfiguredLabel(row.db_password_configured)}
        </Tag>
      ),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, row) => (
        <Space size="small">
          <Button
            size="small"
            data-testid={`rbac-dbms-user-edit-${row.id}`}
            onClick={() => handleEdit(row)}
          >
            Редактировать
          </Button>
          <Button
            size="small"
            loading={setDbmsUserPassword.isPending}
            data-testid={`rbac-dbms-user-set-password-${row.id}`}
            onClick={() => handlePasswordSet(row)}
          >
            Установить пароль
          </Button>
          <Button
            danger
            size="small"
            loading={resetDbmsUserPassword.isPending}
            data-testid={`rbac-dbms-user-reset-password-${row.id}`}
            onClick={() => handlePasswordReset(row)}
          >
            Сбросить пароль
          </Button>
          <Button
            danger
            size="small"
            loading={deleteDbmsUser.isPending}
            data-testid={`rbac-dbms-user-delete-${row.id}`}
            onClick={() => handleDelete(row)}
          >
            Удалить
          </Button>
        </Space>
      ),
    },
  ], [
    deleteDbmsUser.isPending,
    handleDelete,
    handleEdit,
    handlePasswordReset,
    handlePasswordSet,
    resetDbmsUserPassword.isPending,
    setDbmsUserPassword.isPending,
  ])

  const table = useTableToolkit({
    tableId: 'rbac_dbms_users',
    columns,
    fallbackColumns: [
      { key: 'db_username', label: 'Пользователь DBMS', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'cc_user', label: 'Пользователь CC', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'auth_type', label: 'Аутентификация', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'is_service', label: 'Сервисный', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'password', label: 'Пароль', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'actions', label: 'Действия', groupKey: 'actions', groupLabel: 'Действия' },
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
      message="Недостаточно прав для управления DBMS mappings"
    />
  ) : (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="Пользователи DBMS" size="small">
        {!selectedDatabaseId && (
          <Alert
            type="info"
            message="Выберите базу, чтобы посмотреть DBMS mappings"
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
          searchPlaceholder="Поиск пользователей DBMS"
          toolbarActions={(
            <Space>
              <Select
                style={{ width: 320 }}
                placeholder="База"
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
                  { label: 'Аутентификация: любая', value: 'any' },
                  { label: 'Аутентификация: local', value: 'local' },
                  { label: 'Аутентификация: service', value: 'service' },
                  { label: 'Аутентификация: другое', value: 'other' },
                ]}
              />
              <Select
                style={{ width: 160 }}
                value={dbmsServiceFilter}
                onChange={setDbmsServiceFilter}
                options={[
                  { label: 'Сервисный: любой', value: 'any' },
                  { label: 'Сервисный: да', value: 'true' },
                  { label: 'Сервисный: нет', value: 'false' },
                ]}
              />
              <Select
                style={{ width: 180 }}
                value={dbmsHasUserFilter}
                onChange={setDbmsHasUserFilter}
                options={[
                  { label: 'CC пользователь: любой', value: 'any' },
                  { label: 'CC пользователь: привязан', value: 'true' },
                  { label: 'CC пользователь: не привязан', value: 'false' },
                ]}
              />
              <Button
                data-testid="rbac-dbms-users-refresh"
                onClick={() => dbmsUsersQuery.refetch()}
                disabled={!selectedDatabaseId}
                loading={dbmsUsersQuery.isFetching}
              >
                Обновить
              </Button>
            </Space>
          )}
        />
      </Card>

      <Card title={editingDbmsUser ? 'Редактировать DBMS mapping' : 'Добавить DBMS mapping'} size="small">
        <Form
          form={dbmsUserForm}
          layout="vertical"
          initialValues={{ auth_type: 'local', is_service: false }}
        >
          <Space size="large" align="start" wrap>
            <Form.Item
              label="База"
              name="database_id"
              rules={[{ required: true, message: 'Выберите базу' }]}
            >
              <Select
                style={{ width: 320 }}
                placeholder="База"
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
              label="Логин DBMS"
              name="db_username"
              rules={[{ required: true, message: 'Укажите логин DBMS' }]}
            >
              <Input data-testid="rbac-dbms-user-form-db-username" placeholder="db_user" />
            </Form.Item>
            <Form.Item label="Сервисный аккаунт" name="is_service" valuePropName="checked">
              <Switch data-testid="rbac-dbms-user-form-is-service" />
            </Form.Item>
            <Form.Item
              label="Пользователь CC"
              name="user_id"
              rules={[
                ({ getFieldValue }) => ({
                  validator: (_rule, value) => {
                    const isService = Boolean(getFieldValue('is_service'))
                    const result = validateDbmsUserId(isService, value)
                    if (result === 'ok') return Promise.resolve()
                    if (result === 'must_be_empty') {
                      return Promise.reject(new Error('Для сервисного аккаунта пользователь CC не должен быть указан'))
                    }
                    return Promise.reject(new Error('Выберите пользователя CC'))
                  },
                }),
              ]}
            >
              <Select
                showSearch
                allowClear
                data-testid="rbac-dbms-user-form-user-id"
                placeholder={dbmsUserFormIsService ? 'Недоступно для service mapping' : 'Выберите пользователя'}
                filterOption={false}
                onSearch={(value) => setUserSearch(value)}
                options={userOptions}
                loading={usersQuery.isFetching}
                style={{ width: 240 }}
                disabled={Boolean(dbmsUserFormIsService)}
              />
            </Form.Item>
            <Form.Item label="Тип аутентификации" name="auth_type">
              <Select
                style={{ width: 180 }}
                options={[
                  { label: 'Локальная', value: 'local' },
                  { label: 'Сервисная', value: 'service' },
                  { label: 'Другая', value: 'other' },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item label="Пароль">
            <Space size="small" wrap>
              <Tag color={editingDbmsUser?.db_password_configured ? 'green' : 'default'}>
                {getDbmsPasswordConfiguredLabel(Boolean(editingDbmsUser?.db_password_configured))}
              </Tag>
              <Text type="secondary">Текущий пароль не отображается.</Text>
              {editingDbmsUser && (
                <Button
                  onClick={() => handlePasswordSet(editingDbmsUser)}
                  loading={setDbmsUserPassword.isPending}
                >
                  Установить пароль
                </Button>
              )}
              {editingDbmsUser && (
                <Button
                  danger
                  onClick={() => handlePasswordReset(editingDbmsUser)}
                  loading={resetDbmsUserPassword.isPending}
                >
                  Сбросить пароль
                </Button>
              )}
            </Space>
          </Form.Item>
          <Form.Item label="Комментарий" name="notes">
            <Input placeholder="Комментарий (опционально)" />
          </Form.Item>
          <Space>
            <Button
              type="primary"
              data-testid="rbac-dbms-user-form-save"
              onClick={handleSave}
              loading={createDbmsUser.isPending || updateDbmsUser.isPending}
            >
              {editingDbmsUser ? 'Сохранить' : 'Добавить'}
            </Button>
            {editingDbmsUser && (
              <Button data-testid="rbac-dbms-user-form-cancel" onClick={handleResetForm}>
                Отменить редактирование
              </Button>
            )}
          </Space>
        </Form>
      </Card>
    </Space>
  )
}
