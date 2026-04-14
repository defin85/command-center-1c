import { useCallback, useEffect, useMemo } from 'react'
import { App, Button, Form, Input, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useSearchParams } from 'react-router-dom'

import { useAuthz } from '../../authz/useAuthz'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { EntityDetails, ModalFormShell, PageHeader, WorkspacePage } from '../../components/platform'
import { useAdminSupportTranslation, useCommonTranslation, useLocaleFormatters } from '../../i18n'
import { useUser, useUsers, useCreateUser, useUpdateUser, useSetUserPassword, type UserSummary } from '../../api/queries'
import { confirmWithTracking } from '../../observability/confirmWithTracking'

const { Text } = Typography

type UserFormValues = {
  username: string
  email?: string
  first_name?: string
  last_name?: string
  password?: string
  is_staff?: boolean
  is_active?: boolean
}

type UserContext = 'inspect' | 'create' | 'edit' | 'password'

const parseSelectedUserId = (value: string | null): number | null => {
  if (!value) return null
  const parsed = Number.parseInt(value, 10)
  return Number.isNaN(parsed) ? null : parsed
}

const parseUserContext = (value: string | null): UserContext => {
  if (value === 'create' || value === 'edit' || value === 'password') {
    return value
  }
  return 'inspect'
}

export function UsersPage() {
  const { message, modal } = App.useApp()
  const { isStaff } = useAuthz()
  const { t } = useAdminSupportTranslation()
  const { t: tCommon } = useCommonTranslation()
  const formatters = useLocaleFormatters()
  const [searchParams, setSearchParams] = useSearchParams()
  const [form] = Form.useForm<UserFormValues>()
  const [passwordForm] = Form.useForm<{ password: string }>()

  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const setUserPassword = useSetUserPassword()
  const unavailableShort = tCommon(($) => $.values.unavailableShort)
  const yesLabel = t(($) => $.shared.yes)
  const noLabel = t(($) => $.shared.no)

  const selectedUserId = parseSelectedUserId(searchParams.get('user'))
  const activeContext = parseUserContext(searchParams.get('context'))

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(updates).forEach(([key, value]) => {
        if (!value) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  const openCreateModal = useCallback(() => {
    form.resetFields()
    form.setFieldsValue({ is_active: true, is_staff: false })
    updateSearchParams({ user: null, context: 'create' })
  }, [form, updateSearchParams])

  const openEditModal = useCallback((user: UserSummary) => {
    form.setFieldsValue({
      username: user.username,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      is_staff: user.is_staff,
      is_active: user.is_active,
    })
    updateSearchParams({ user: String(user.id), context: 'edit' })
  }, [form, updateSearchParams])

  const openPasswordModal = useCallback((user: UserSummary) => {
    passwordForm.resetFields()
    updateSearchParams({ user: String(user.id), context: 'password' })
  }, [passwordForm, updateSearchParams])

  const toggleActive = useCallback((user: UserSummary) => {
    confirmWithTracking(modal, {
      title: user.is_active
        ? t(($) => $.users.confirm.deactivateTitle)
        : t(($) => $.users.confirm.activateTitle),
      content: user.is_active
        ? t(($) => $.users.confirm.deactivateContent)
        : t(($) => $.users.confirm.activateContent),
      okText: user.is_active
        ? t(($) => $.users.confirm.deactivateOk)
        : t(($) => $.users.confirm.activateOk),
      cancelText: t(($) => $.users.confirm.cancel),
      okButtonProps: { danger: user.is_active },
      onOk: () => updateUser.mutate({ id: user.id, is_active: !user.is_active }),
    }, {
      actionKind: 'operator.action',
      actionName: user.is_active ? 'Deactivate user' : 'Activate user',
      context: {
        user_id: user.id,
        next_is_active: !user.is_active,
      },
    })
  }, [modal, t, updateUser])

  const fallbackColumns = useMemo(() => [
    {
      key: 'username',
      label: t(($) => $.users.table.username),
      groupKey: 'core',
      groupLabel: t(($) => $.users.groups.core),
      sortable: true,
    },
    {
      key: 'email',
      label: t(($) => $.users.table.email),
      groupKey: 'core',
      groupLabel: t(($) => $.users.groups.core),
      sortable: true,
    },
    {
      key: 'is_staff',
      label: t(($) => $.users.table.staff),
      groupKey: 'meta',
      groupLabel: t(($) => $.users.groups.meta),
    },
    {
      key: 'is_active',
      label: t(($) => $.users.table.active),
      groupKey: 'meta',
      groupLabel: t(($) => $.users.groups.meta),
    },
    {
      key: 'last_login',
      label: t(($) => $.users.table.lastLogin),
      groupKey: 'time',
      groupLabel: t(($) => $.users.groups.time),
      sortable: true,
    },
    {
      key: 'date_joined',
      label: t(($) => $.users.table.created),
      groupKey: 'time',
      groupLabel: t(($) => $.users.groups.time),
      sortable: true,
    },
    {
      key: 'actions',
      label: t(($) => $.users.table.actions),
      groupKey: 'actions',
      groupLabel: t(($) => $.users.groups.actions),
    },
  ], [t])

  const columns: ColumnsType<UserSummary> = useMemo(() => [
    {
      title: t(($) => $.users.table.username),
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: t(($) => $.users.table.email),
      dataIndex: 'email',
      key: 'email',
      render: (value: string) => value || unavailableShort,
    },
    {
      title: t(($) => $.users.table.staff),
      dataIndex: 'is_staff',
      key: 'is_staff',
      render: (value: boolean) => (
        <Text type={value ? 'success' : 'secondary'}>{value ? yesLabel : noLabel}</Text>
      ),
    },
    {
      title: t(($) => $.users.table.active),
      dataIndex: 'is_active',
      key: 'is_active',
      render: (value: boolean) => (
        <Text type={value ? 'success' : 'secondary'}>{value ? yesLabel : noLabel}</Text>
      ),
    },
    {
      title: t(($) => $.users.table.lastLogin),
      dataIndex: 'last_login',
      key: 'last_login',
      render: (value: string | null) => formatters.dateTime(value, { fallback: unavailableShort }),
    },
    {
      title: t(($) => $.users.table.created),
      dataIndex: 'date_joined',
      key: 'date_joined',
      render: (value: string) => formatters.dateTime(value, { fallback: unavailableShort }),
    },
    {
      title: t(($) => $.users.table.actions),
      key: 'actions',
      render: (_: unknown, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openEditModal(record)}>
            {t(($) => $.users.actions.edit)}
          </Button>
          <Button size="small" onClick={() => openPasswordModal(record)}>
            {t(($) => $.users.actions.password)}
          </Button>
          <Button
            size="small"
            danger={!record.is_active}
            onClick={() => toggleActive(record)}
          >
            {record.is_active ? t(($) => $.users.actions.deactivate) : t(($) => $.users.actions.activate)}
          </Button>
        </Space>
      ),
    },
  ], [formatters, noLabel, openEditModal, openPasswordModal, t, toggleActive, unavailableShort, yesLabel])

  const table = useTableToolkit({
    tableId: 'users',
    columns,
    fallbackColumns,
    initialPageSize: 50,
  })

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize

  const usersQuery = useUsers({
    search: table.search || undefined,
    username: typeof table.filters.username === 'string' ? table.filters.username : undefined,
    email: typeof table.filters.email === 'string' ? table.filters.email : undefined,
    is_staff: typeof table.filters.is_staff === 'boolean' ? table.filters.is_staff : undefined,
    is_active: typeof table.filters.is_active === 'boolean' ? table.filters.is_active : undefined,
    limit: table.pagination.pageSize,
    offset: pageStart,
  }, { enabled: isStaff })

  const users = usersQuery.data?.users ?? []
  const totalUsers = typeof usersQuery.data?.total === 'number'
    ? usersQuery.data.total
    : users.length
  const selectedUserFromCatalog = selectedUserId === null
    ? null
    : users.find((user) => user.id === selectedUserId) ?? null
  const selectedUserQuery = useUser(selectedUserId, {
    enabled: isStaff && selectedUserId !== null && selectedUserFromCatalog === null,
  })
  const selectedUser = selectedUserFromCatalog ?? selectedUserQuery.data ?? null
  const selectedUserLoading = selectedUserId !== null
    && selectedUser === null
    && (usersQuery.isLoading || selectedUserQuery.isLoading)
  const selectedUserError = selectedUserId !== null
    && selectedUser === null
    && !selectedUserLoading
    ? t(($) => $.users.page.detailMissing)
    : null

  useEffect(() => {
    if (activeContext === 'create') {
      form.resetFields()
      form.setFieldsValue({ is_active: true, is_staff: false })
      return
    }

    if (activeContext === 'edit' && selectedUser) {
      form.setFieldsValue({
        username: selectedUser.username,
        email: selectedUser.email,
        first_name: selectedUser.first_name,
        last_name: selectedUser.last_name,
        is_staff: selectedUser.is_staff,
        is_active: selectedUser.is_active,
      })
      return
    }

    if (activeContext === 'password') {
      passwordForm.resetFields()
    }
  }, [activeContext, form, passwordForm, selectedUser])

  if (!isStaff) {
    return (
      <WorkspacePage
        header={(
          <PageHeader
            title={t(($) => $.users.page.title)}
            subtitle={t(($) => $.users.page.staffOnlySubtitle)}
          />
        )}
      >
        <Typography.Text type="warning">{t(($) => $.users.page.staffOnlyMessage)}</Typography.Text>
      </WorkspacePage>
    )
  }

  const closeUserEditor = () => {
    updateSearchParams({
      context: selectedUser ? 'inspect' : null,
      user: selectedUser ? String(selectedUser.id) : null,
    })
    form.resetFields()
  }

  const closePasswordEditor = () => {
    updateSearchParams({
      context: selectedUser ? 'inspect' : null,
      user: selectedUser ? String(selectedUser.id) : null,
    })
    passwordForm.resetFields()
  }

  const handleUserSave = async () => {
    const values = await form.validateFields()
    if (activeContext === 'edit' && selectedUser) {
      updateUser.mutate({
        id: selectedUser.id,
        username: values.username,
        email: values.email,
        first_name: values.first_name,
        last_name: values.last_name,
        is_staff: values.is_staff,
        is_active: values.is_active,
      }, {
        onSuccess: () => {
          closeUserEditor()
        },
      })
      return
    }

    if (!values.password) {
      message.error(t(($) => $.users.form.newUserPasswordRequired))
      return
    }

    createUser.mutate({
      username: values.username,
      password: values.password,
      email: values.email,
      first_name: values.first_name,
      last_name: values.last_name,
      is_staff: values.is_staff,
      is_active: values.is_active,
    }, {
      onSuccess: (createdUser) => {
        updateSearchParams({ user: String(createdUser.id), context: 'inspect' })
        form.resetFields()
      },
    })
  }

  const handlePasswordSave = async () => {
    if (!selectedUser) return
    const values = await passwordForm.validateFields()
    setUserPassword.mutate(
      { id: selectedUser.id, password: values.password },
      {
        onSuccess: () => {
          closePasswordEditor()
        },
      }
    )
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.users.page.title)}
          subtitle={t(($) => $.users.page.subtitle)}
          actions={(
            <Space wrap>
              <Button onClick={() => usersQuery.refetch()} loading={usersQuery.isFetching}>
                {t(($) => $.users.page.refresh)}
              </Button>
              <Button type="primary" onClick={openCreateModal}>
                {t(($) => $.users.page.addUser)}
              </Button>
            </Space>
          )}
        />
      )}
    >
      <TableToolkit
        table={table}
        data={users}
        total={totalUsers}
        loading={usersQuery.isLoading}
        rowKey="id"
        columns={columns}
        tableLayout="fixed"
        scroll={{ x: table.totalColumnsWidth }}
        searchPlaceholder={t(($) => $.users.page.searchPlaceholder)}
        onRow={(record) => ({
          onClick: () => updateSearchParams({
            user: String(record.id),
            context: 'inspect',
          }),
          style: { cursor: 'pointer' },
        })}
      />

      <EntityDetails
        title={selectedUser
          ? t(($) => $.users.page.detailTitleWithUsername, { username: selectedUser.username })
          : t(($) => $.users.page.detailTitle)}
        error={selectedUserError}
        loading={selectedUserLoading}
        empty={!selectedUser}
        emptyDescription={selectedUserId
          ? t(($) => $.users.page.detailMissing)
          : t(($) => $.users.page.detailEmpty)}
        extra={selectedUser ? (
          <Space wrap>
            <Button size="small" onClick={() => openEditModal(selectedUser)}>
              {t(($) => $.users.actions.edit)}
            </Button>
            <Button size="small" onClick={() => openPasswordModal(selectedUser)}>
              {t(($) => $.users.actions.password)}
            </Button>
            <Button
              size="small"
              danger={!selectedUser.is_active}
              onClick={() => toggleActive(selectedUser)}
            >
              {selectedUser.is_active ? t(($) => $.users.actions.deactivate) : t(($) => $.users.actions.activate)}
            </Button>
          </Space>
        ) : null}
      >
        {selectedUser ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text data-testid="users-selected-username"><strong>{t(($) => $.users.detailFields.username)}:</strong> {selectedUser.username}</Text>
            <Text><strong>{t(($) => $.users.detailFields.email)}:</strong> {selectedUser.email || unavailableShort}</Text>
            <Text><strong>{t(($) => $.users.detailFields.name)}:</strong> {[selectedUser.first_name, selectedUser.last_name].filter(Boolean).join(' ') || unavailableShort}</Text>
            <Text><strong>{t(($) => $.users.detailFields.staff)}:</strong> {selectedUser.is_staff ? yesLabel : noLabel}</Text>
            <Text><strong>{t(($) => $.users.detailFields.active)}:</strong> {selectedUser.is_active ? yesLabel : noLabel}</Text>
            <Text><strong>{t(($) => $.users.detailFields.lastLogin)}:</strong> {formatters.dateTime(selectedUser.last_login, { fallback: unavailableShort })}</Text>
            <Text><strong>{t(($) => $.users.detailFields.created)}:</strong> {formatters.dateTime(selectedUser.date_joined, { fallback: unavailableShort })}</Text>
          </Space>
        ) : null}
      </EntityDetails>

      <ModalFormShell
        open={activeContext === 'create' || (activeContext === 'edit' && Boolean(selectedUser))}
        onClose={closeUserEditor}
        onSubmit={() => { void handleUserSave() }}
        title={activeContext === 'edit' && selectedUser
          ? t(($) => $.users.form.editTitle, { username: selectedUser.username })
          : t(($) => $.users.form.addTitle)}
        submitText={activeContext === 'edit' ? t(($) => $.users.actions.save) : t(($) => $.users.actions.create)}
        confirmLoading={createUser.isPending || updateUser.isPending}
        forceRender
      >
        <Form form={form} layout="vertical" initialValues={{ is_active: true, is_staff: false }}>
          <Form.Item label={t(($) => $.users.form.username)} name="username" rules={[{ required: true, message: t(($) => $.users.form.usernameRequired) }]}>
            <Input id="users-username" aria-label={t(($) => $.users.form.username)} />
          </Form.Item>
          {activeContext !== 'edit' && (
            <Form.Item label={t(($) => $.users.form.password)} name="password" rules={[{ required: true, message: t(($) => $.users.form.passwordRequired) }]}>
              <Input.Password id="users-password" aria-label={t(($) => $.users.form.password)} />
            </Form.Item>
          )}
          <Form.Item label={t(($) => $.users.form.email)} name="email">
            <Input id="users-email" aria-label={t(($) => $.users.form.email)} />
          </Form.Item>
          <Form.Item label={t(($) => $.users.form.firstName)} name="first_name">
            <Input id="users-first-name" aria-label={t(($) => $.users.form.firstName)} />
          </Form.Item>
          <Form.Item label={t(($) => $.users.form.lastName)} name="last_name">
            <Input id="users-last-name" aria-label={t(($) => $.users.form.lastName)} />
          </Form.Item>
          <Space size="large">
            <Form.Item label={t(($) => $.users.form.staff)} name="is_staff" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label={t(($) => $.users.form.active)} name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </ModalFormShell>

      <ModalFormShell
        open={activeContext === 'password' && Boolean(selectedUser)}
        onClose={closePasswordEditor}
        onSubmit={() => { void handlePasswordSave() }}
        title={selectedUser
          ? t(($) => $.users.form.passwordTitle, { username: selectedUser.username })
          : t(($) => $.users.form.passwordTitleFallback)}
        submitText={t(($) => $.users.actions.update)}
        confirmLoading={setUserPassword.isPending}
        forceRender
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item label={t(($) => $.users.form.newPassword)} name="password" rules={[{ required: true, message: t(($) => $.users.form.passwordRequired) }]}>
            <Input.Password id="users-new-password" aria-label={t(($) => $.users.form.newPassword)} />
          </Form.Item>
        </Form>
      </ModalFormShell>
    </WorkspacePage>
  )
}
