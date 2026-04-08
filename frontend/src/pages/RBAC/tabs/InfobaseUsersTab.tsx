import { useCallback, useMemo, useState } from 'react'
import { App, Alert, Button, Card, Form, Input, Select, Space, Switch, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useInfobaseUsers, useCreateInfobaseUser, useDeleteInfobaseUser, useResetInfobaseUserPassword, useSetInfobaseUserPassword, useUpdateInfobaseUser, type InfobaseUserMapping } from '../../../api/queries/databases'
import { useRbacRefDatabases, useRbacUsers } from '../../../api/queries/rbac'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'
import { usePaginatedRefSelectOptions } from '../hooks/usePaginatedRefSelectOptions'

const { Text } = Typography

const IB_AUTH_TYPE_LABELS: Record<string, string> = {
  local: 'Локальная',
  ad: 'AD',
  service: 'Сервисная',
  other: 'Другая',
}

function getIbAuthTypeLabel(authType: string | undefined): string {
  const key = authType ?? 'local'
  return IB_AUTH_TYPE_LABELS[key] || key
}

export function InfobaseUsersTab(props: { enabled: boolean }) {
  const { enabled } = props
  const { modal } = App.useApp()

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
        title: 'Введите имя пользователя ИБ',
        content: 'Укажите ib_username перед сохранением.',
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
        title: 'Выберите базу',
        content: 'Укажите базу данных перед сохранением.',
      })
      return
    }
    createInfobaseUser.mutate(
      { database_id: values.database_id, ...payloadBase, ib_password: values.ib_password?.trim() || undefined },
      { onSuccess: handleResetForm }
    )
  }, [createInfobaseUser, editingIbUser, handleResetForm, ibUserForm, modal, updateInfobaseUser])

  const handleDelete = useCallback((record: InfobaseUserMapping) => {
    confirmWithTracking(modal, {
      title: `Удалить пользователя ИБ ${record.ib_username}?`,
      content: 'Запись будет удалена только в Command Center.',
      okText: 'Удалить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => deleteInfobaseUser.mutate({ id: record.id, databaseId: record.database_id }),
    })
  }, [deleteInfobaseUser, modal])

  const handlePasswordUpdate = useCallback(async () => {
    if (!editingIbUser) return
    const password = ibUserForm.getFieldValue('ib_password')?.trim()
    if (!password) {
      modal.warning({
        title: 'Введите пароль',
        content: 'Укажите новый пароль ИБ перед сохранением.',
      })
      return
    }
    setInfobaseUserPassword.mutate(
      { id: editingIbUser.id, password },
      { onSuccess: () => ibUserForm.setFieldsValue({ ib_password: '' }) }
    )
  }, [editingIbUser, ibUserForm, modal, setInfobaseUserPassword])

  const handlePasswordReset = useCallback(() => {
    if (!editingIbUser) return
    confirmWithTracking(modal, {
      title: `Сбросить пароль для ${editingIbUser.ib_username}?`,
      content: 'Пароль будет очищен.',
      okText: 'Сбросить',
      cancelText: 'Отмена',
      okButtonProps: { danger: true },
      onOk: () => resetInfobaseUserPassword.mutate({ id: editingIbUser.id, databaseId: editingIbUser.database_id }),
    })
  }, [editingIbUser, modal, resetInfobaseUserPassword])

  const columns: ColumnsType<InfobaseUserMapping> = useMemo(() => [
    {
      title: 'Пользователь ИБ',
      key: 'ib_username',
      render: (_: unknown, row) => <span>{row.ib_username}</span>,
    },
    {
      title: 'Имя в ИБ',
      key: 'ib_display_name',
      render: (_: unknown, row) => <span>{row.ib_display_name || '-'}</span>,
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
      title: 'Роли',
      key: 'roles',
      render: (_: unknown, row) => {
        const roles = row.ib_roles ?? []
        if (roles.length === 0) return '-'
        return (
          <Space size={4} wrap>
            {roles.slice(0, 6).map((role) => <Tag key={role}>{role}</Tag>)}
            {roles.length > 6 && <Text type="secondary">+{roles.length - 6}</Text>}
          </Space>
        )
      },
    },
    {
      title: 'Аутентификация',
      key: 'auth_type',
      render: (_: unknown, row) => <Tag>{getIbAuthTypeLabel(row.auth_type)}</Tag>,
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
        <Tag color={row.ib_password_configured ? 'green' : 'default'}>
          {row.ib_password_configured ? 'Задан' : 'Не задан'}
        </Tag>
      ),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_: unknown, row) => (
        <Space size="small">
          <Button size="small" onClick={() => handleEdit(row)}>
            Редактировать
          </Button>
          <Button
            danger
            size="small"
            loading={deleteInfobaseUser.isPending}
            onClick={() => handleDelete(row)}
          >
            Удалить
          </Button>
        </Space>
      ),
    },
  ], [deleteInfobaseUser.isPending, handleDelete, handleEdit])

  const table = useTableToolkit({
    tableId: 'rbac_ib_users',
    columns,
    fallbackColumns: [
      { key: 'ib_username', label: 'Пользователь ИБ', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'ib_display_name', label: 'Имя в ИБ', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'cc_user', label: 'Пользователь CC', groupKey: 'core', groupLabel: 'Основное' },
      { key: 'roles', label: 'Роли', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'auth_type', label: 'Аутентификация', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'is_service', label: 'Сервисный', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'password', label: 'Пароль', groupKey: 'meta', groupLabel: 'Метаданные' },
      { key: 'actions', label: 'Действия', groupKey: 'actions', groupLabel: 'Действия' },
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
      <Card title="Пользователи ИБ" size="small">
        {!selectedDatabaseId && (
          <Alert
            type="info"
            message="Выберите базу, чтобы посмотреть маппинги пользователей ИБ"
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
          searchPlaceholder="Поиск пользователей ИБ"
          toolbarActions={(
            <Space>
              <Select
                style={{ width: 320 }}
                placeholder="База"
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
                  { label: 'Аутентификация: любая', value: 'any' },
                  { label: 'Аутентификация: local', value: 'local' },
                  { label: 'Аутентификация: AD', value: 'ad' },
                  { label: 'Аутентификация: service', value: 'service' },
                  { label: 'Аутентификация: другое', value: 'other' },
                ]}
              />
              <Select
                style={{ width: 160 }}
                value={ibServiceFilter}
                onChange={setIbServiceFilter}
                options={[
                  { label: 'Сервисный: любой', value: 'any' },
                  { label: 'Сервисный: да', value: 'true' },
                  { label: 'Сервисный: нет', value: 'false' },
                ]}
              />
              <Select
                style={{ width: 180 }}
                value={ibHasUserFilter}
                onChange={setIbHasUserFilter}
                options={[
                  { label: 'CC пользователь: любой', value: 'any' },
                  { label: 'CC пользователь: привязан', value: 'true' },
                  { label: 'CC пользователь: не привязан', value: 'false' },
                ]}
              />
              <Button
                onClick={() => ibUsersQuery.refetch()}
                disabled={!selectedDatabaseId}
                loading={ibUsersQuery.isFetching}
              >
                Обновить
              </Button>
            </Space>
          )}
        />
      </Card>

      <Card title={editingIbUser ? 'Редактировать пользователя ИБ' : 'Добавить пользователя ИБ'} size="small">
        <Form
          form={ibUserForm}
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
              label="Логин ИБ"
              name="ib_username"
              rules={[{ required: true, message: 'Укажите логин ИБ' }]}
            >
              <Input placeholder="ib_user" />
            </Form.Item>
            <Form.Item label="Имя" name="ib_display_name">
              <Input placeholder="Имя (опционально)" />
            </Form.Item>
            <Form.Item label="Пользователь CC" name="user_id">
              <Select
                showSearch
                allowClear
                placeholder="Пользователь (опционально)"
                filterOption={false}
                onSearch={(value) => setUserSearch(value)}
                options={userOptions}
                loading={usersQuery.isFetching}
                style={{ width: 240 }}
              />
            </Form.Item>
            <Form.Item label="Тип аутентификации" name="auth_type">
              <Select
                style={{ width: 180 }}
                options={[
                  { label: 'Локальная', value: 'local' },
                  { label: 'AD', value: 'ad' },
                  { label: 'Сервисная', value: 'service' },
                  { label: 'Другая', value: 'other' },
                ]}
              />
            </Form.Item>
            <Form.Item label="Сервисный аккаунт" name="is_service" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item label="Роли (ИБ)" name="ib_roles">
            <Select mode="tags" tokenSeparators={[',']} placeholder="Роли (через запятую)" />
          </Form.Item>
          <Form.Item
            label={editingIbUser ? 'Новый пароль ИБ' : 'Пароль ИБ'}
            name="ib_password"
            help={(
              <Space size="small">
                {editingIbUser ? (
                  <span>Нажмите “Обновить пароль”, чтобы применить изменения.</span>
                ) : (
                  <span>Можно задать пароль при создании (опционально).</span>
                )}
                <Tag color={editingIbUser?.ib_password_configured ? 'green' : 'default'}>
                  {editingIbUser?.ib_password_configured ? 'Задан' : 'Не задан'}
                </Tag>
              </Space>
            )}
          >
            <Input.Password placeholder="Введите пароль" />
          </Form.Item>
          <Form.Item label="Комментарий" name="notes">
            <Input placeholder="Комментарий (опционально)" />
          </Form.Item>
          <Space>
            <Button
              type="primary"
              onClick={handleSave}
              loading={createInfobaseUser.isPending || updateInfobaseUser.isPending}
            >
              {editingIbUser ? 'Сохранить' : 'Добавить'}
            </Button>
            {editingIbUser && (
              <Button
                onClick={handlePasswordUpdate}
                loading={setInfobaseUserPassword.isPending}
              >
                Обновить пароль
              </Button>
            )}
            {editingIbUser && (
              <Button
                danger
                onClick={handlePasswordReset}
                loading={resetInfobaseUserPassword.isPending}
              >
                Сбросить пароль
              </Button>
            )}
            {editingIbUser && (
              <Button onClick={handleResetForm}>Отменить редактирование</Button>
            )}
          </Space>
        </Form>
      </Card>
    </Space>
  )
}
