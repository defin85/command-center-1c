import { useCallback, useEffect, useMemo } from 'react'
import { App, Button, Form, Input, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useSearchParams } from 'react-router-dom'

import { useAuthz } from '../../authz/useAuthz'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { EntityDetails, ModalFormShell, PageHeader, WorkspacePage } from '../../components/platform'
import { useUsers, useCreateUser, useUpdateUser, useSetUserPassword, type UserSummary } from '../../api/queries'

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
  const [searchParams, setSearchParams] = useSearchParams()
  const [form] = Form.useForm<UserFormValues>()
  const [passwordForm] = Form.useForm<{ password: string }>()

  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const setUserPassword = useSetUserPassword()

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
    modal.confirm({
      title: user.is_active ? 'Deactivate user?' : 'Activate user?',
      content: user.is_active
        ? 'User will not be able to log in.'
        : 'User will be able to log in again.',
      okText: user.is_active ? 'Deactivate' : 'Activate',
      cancelText: 'Cancel',
      okButtonProps: { danger: user.is_active },
      onOk: () => updateUser.mutate({ id: user.id, is_active: !user.is_active }),
    })
  }, [modal, updateUser])

  const fallbackColumns = useMemo(() => [
    { key: 'username', label: 'Username', groupKey: 'core', groupLabel: 'Core', sortable: true },
    { key: 'email', label: 'Email', groupKey: 'core', groupLabel: 'Core', sortable: true },
    { key: 'is_staff', label: 'Staff', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'is_active', label: 'Active', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'last_login', label: 'Last Login', groupKey: 'time', groupLabel: 'Time', sortable: true },
    { key: 'date_joined', label: 'Created', groupKey: 'time', groupLabel: 'Time', sortable: true },
    { key: 'actions', label: 'Action', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const columns: ColumnsType<UserSummary> = useMemo(() => [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (value: string) => value || '-',
    },
    {
      title: 'Staff',
      dataIndex: 'is_staff',
      key: 'is_staff',
      render: (value: boolean) => (
        <Text type={value ? 'success' : 'secondary'}>{value ? 'Yes' : 'No'}</Text>
      ),
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (value: boolean) => (
        <Text type={value ? 'success' : 'secondary'}>{value ? 'Yes' : 'No'}</Text>
      ),
    },
    {
      title: 'Last Login',
      dataIndex: 'last_login',
      key: 'last_login',
      render: (value: string | null) => value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: 'Created',
      dataIndex: 'date_joined',
      key: 'date_joined',
      render: (value: string) => value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openEditModal(record)}>
            Edit
          </Button>
          <Button size="small" onClick={() => openPasswordModal(record)}>
            Password
          </Button>
          <Button
            size="small"
            danger={!record.is_active}
            onClick={() => toggleActive(record)}
          >
            {record.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        </Space>
      ),
    },
  ], [openEditModal, openPasswordModal, toggleActive])

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
  const selectedUser = selectedUserId === null
    ? null
    : users.find((user) => user.id === selectedUserId) ?? null

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
        header={<PageHeader title="Users" subtitle="Каталог пользователей доступен только staff-операторам." />}
      >
        <Typography.Text type="warning">Users доступны только для staff пользователей.</Typography.Text>
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
      message.error('Password is required for new users')
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
          title="Users"
          subtitle="Catalog/detail workspace для staff-user management с URL-backed selected context."
          actions={(
            <Space wrap>
              <Button onClick={() => usersQuery.refetch()} loading={usersQuery.isFetching}>
                Refresh
              </Button>
              <Button type="primary" onClick={openCreateModal}>
                Add User
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
        searchPlaceholder="Search users"
        onRow={(record) => ({
          onClick: () => updateSearchParams({
            user: String(record.id),
            context: 'inspect',
          }),
          style: { cursor: 'pointer' },
        })}
      />

      <EntityDetails
        title={selectedUser ? `User: ${selectedUser.username}` : 'User details'}
        empty={!selectedUser}
        emptyDescription={selectedUserId
          ? 'Selected user is outside the current catalog slice. Refine search or reload the catalog.'
          : 'Select a user from the catalog or create a new one.'}
        extra={selectedUser ? (
          <Space wrap>
            <Button size="small" onClick={() => openEditModal(selectedUser)}>
              Edit
            </Button>
            <Button size="small" onClick={() => openPasswordModal(selectedUser)}>
              Password
            </Button>
            <Button
              size="small"
              danger={!selectedUser.is_active}
              onClick={() => toggleActive(selectedUser)}
            >
              {selectedUser.is_active ? 'Deactivate' : 'Activate'}
            </Button>
          </Space>
        ) : null}
      >
        {selectedUser ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text data-testid="users-selected-username"><strong>Username:</strong> {selectedUser.username}</Text>
            <Text><strong>Email:</strong> {selectedUser.email || '—'}</Text>
            <Text><strong>Name:</strong> {[selectedUser.first_name, selectedUser.last_name].filter(Boolean).join(' ') || '—'}</Text>
            <Text><strong>Staff:</strong> {selectedUser.is_staff ? 'Yes' : 'No'}</Text>
            <Text><strong>Active:</strong> {selectedUser.is_active ? 'Yes' : 'No'}</Text>
            <Text><strong>Last login:</strong> {selectedUser.last_login ? new Date(selectedUser.last_login).toLocaleString() : '—'}</Text>
            <Text><strong>Created:</strong> {selectedUser.date_joined ? new Date(selectedUser.date_joined).toLocaleString() : '—'}</Text>
          </Space>
        ) : null}
      </EntityDetails>

      <ModalFormShell
        open={activeContext === 'create' || activeContext === 'edit'}
        onClose={closeUserEditor}
        onSubmit={() => { void handleUserSave() }}
        title={activeContext === 'edit' && selectedUser ? `Edit User: ${selectedUser.username}` : 'Add User'}
        submitText={activeContext === 'edit' ? 'Save' : 'Create'}
        confirmLoading={createUser.isPending || updateUser.isPending}
        forceRender
      >
        <Form form={form} layout="vertical" initialValues={{ is_active: true, is_staff: false }}>
          <Form.Item label="Username" name="username" rules={[{ required: true, message: 'Username is required' }]}>
            <Input id="users-username" aria-label="Username" />
          </Form.Item>
          {activeContext !== 'edit' && (
            <Form.Item label="Password" name="password" rules={[{ required: true, message: 'Password is required' }]}>
              <Input.Password id="users-password" aria-label="Password" />
            </Form.Item>
          )}
          <Form.Item label="Email" name="email">
            <Input id="users-email" aria-label="Email" />
          </Form.Item>
          <Form.Item label="First Name" name="first_name">
            <Input id="users-first-name" aria-label="First Name" />
          </Form.Item>
          <Form.Item label="Last Name" name="last_name">
            <Input id="users-last-name" aria-label="Last Name" />
          </Form.Item>
          <Space size="large">
            <Form.Item label="Staff" name="is_staff" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="Active" name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </ModalFormShell>

      <ModalFormShell
        open={activeContext === 'password'}
        onClose={closePasswordEditor}
        onSubmit={() => { void handlePasswordSave() }}
        title={selectedUser ? `Set Password: ${selectedUser.username}` : 'Set Password'}
        submitText="Update"
        confirmLoading={setUserPassword.isPending}
        forceRender
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item label="New Password" name="password" rules={[{ required: true, message: 'Password is required' }]}>
            <Input.Password id="users-new-password" aria-label="New Password" />
          </Form.Item>
        </Form>
      </ModalFormShell>
    </WorkspacePage>
  )
}
