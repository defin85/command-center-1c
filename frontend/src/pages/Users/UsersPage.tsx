import { useCallback, useMemo, useState } from 'react'
import { App, Button, Card, Form, Input, Modal, Space, Switch, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { useUsers, useCreateUser, useUpdateUser, useSetUserPassword, type UserSummary, useMe } from '../../api/queries'

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

export function UsersPage() {
  const { message, modal } = App.useApp()
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)
  const [editingUser, setEditingUser] = useState<UserSummary | null>(null)
  const [userModalVisible, setUserModalVisible] = useState(false)
  const [passwordModalVisible, setPasswordModalVisible] = useState(false)
  const [passwordUser, setPasswordUser] = useState<UserSummary | null>(null)
  const [form] = Form.useForm<UserFormValues>()
  const [passwordForm] = Form.useForm<{ password: string }>()

  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const setUserPassword = useSetUserPassword()

  const openCreateModal = useCallback(() => {
    setEditingUser(null)
    form.resetFields()
    form.setFieldsValue({ is_active: true, is_staff: false })
    setUserModalVisible(true)
  }, [form])

  const openEditModal = useCallback((user: UserSummary) => {
    setEditingUser(user)
    form.setFieldsValue({
      username: user.username,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      is_staff: user.is_staff,
      is_active: user.is_active,
    })
    setUserModalVisible(true)
  }, [form])

  const openPasswordModal = useCallback((user: UserSummary) => {
    setPasswordUser(user)
    passwordForm.resetFields()
    setPasswordModalVisible(true)
  }, [passwordForm])

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

  if (!isStaff) {
    return (
      <div>
        <Typography.Title level={2}>Users</Typography.Title>
        <Typography.Text type="warning">Users доступны только для staff пользователей.</Typography.Text>
      </div>
    )
  }

  const handleUserSave = async () => {
    const values = await form.validateFields()
    if (editingUser) {
      updateUser.mutate({
        id: editingUser.id,
        username: values.username,
        email: values.email,
        first_name: values.first_name,
        last_name: values.last_name,
        is_staff: values.is_staff,
        is_active: values.is_active,
      }, {
        onSuccess: () => {
          setUserModalVisible(false)
          setEditingUser(null)
          form.resetFields()
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
      onSuccess: () => {
        setUserModalVisible(false)
        form.resetFields()
      },
    })
  }

  const handlePasswordSave = async () => {
    if (!passwordUser) return
    const values = await passwordForm.validateFields()
    setUserPassword.mutate(
      { id: passwordUser.id, password: values.password },
      {
        onSuccess: () => {
          setPasswordModalVisible(false)
          setPasswordUser(null)
          passwordForm.resetFields()
        },
      }
    )
  }

  return (
    <div>
      <Typography.Title level={2}>Users</Typography.Title>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Button type="primary" onClick={openCreateModal}>
            Add User
          </Button>
          <Button onClick={() => usersQuery.refetch()} loading={usersQuery.isFetching}>
            Refresh
          </Button>
        </Space>
      </Card>

      <TableToolkit
        table={table}
        data={users}
        total={totalUsers}
        loading={usersQuery.isLoading}
        rowKey="id"
        columns={columns}
        searchPlaceholder="Search users"
      />

      <Modal
        title={editingUser ? `Edit User: ${editingUser.username}` : 'Add User'}
        open={userModalVisible}
        onCancel={() => {
          setUserModalVisible(false)
          setEditingUser(null)
          form.resetFields()
        }}
        onOk={handleUserSave}
        okText={editingUser ? 'Save' : 'Create'}
        confirmLoading={createUser.isPending || updateUser.isPending}
      >
        <Form form={form} layout="vertical" initialValues={{ is_active: true, is_staff: false }}>
          <Form.Item label="Username" name="username" rules={[{ required: true, message: 'Username is required' }]}>
            <Input id="users-username" />
          </Form.Item>
          {!editingUser && (
            <Form.Item label="Password" name="password" rules={[{ required: true, message: 'Password is required' }]}>
              <Input.Password id="users-password" />
            </Form.Item>
          )}
          <Form.Item label="Email" name="email">
            <Input id="users-email" />
          </Form.Item>
          <Form.Item label="First Name" name="first_name">
            <Input id="users-first-name" />
          </Form.Item>
          <Form.Item label="Last Name" name="last_name">
            <Input id="users-last-name" />
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
      </Modal>

      <Modal
        title={passwordUser ? `Set Password: ${passwordUser.username}` : 'Set Password'}
        open={passwordModalVisible}
        onCancel={() => {
          setPasswordModalVisible(false)
          setPasswordUser(null)
          passwordForm.resetFields()
        }}
        onOk={handlePasswordSave}
        okText="Update"
        confirmLoading={setUserPassword.isPending}
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item label="New Password" name="password" rules={[{ required: true, message: 'Password is required' }]}>
            <Input.Password id="users-new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
