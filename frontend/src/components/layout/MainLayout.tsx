import { Layout, Menu, Button, Dropdown, Tag, Tooltip, Space, Popover, Typography } from 'antd'
import { DashboardOutlined, ThunderboltOutlined, DatabaseOutlined, ClusterOutlined, UserOutlined, LogoutOutlined, MonitorOutlined, ApartmentOutlined, DeploymentUnitOutlined, SafetyCertificateOutlined, FileTextOutlined, WarningOutlined, LoadingOutlined, SettingOutlined, InboxOutlined, AppstoreOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { MenuProps } from 'antd'

import { useMe } from '../../api/queries/me'
import { useCanManageRbac } from '../../api/queries/rbac'
import { useCanManageDriverCatalogs } from '../../api/queries'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { setAuthToken } from '../../api/client'
import { notifyAuthChanged } from '../../lib/authState'
import { resetQueryClient } from '../../lib/queryClient'

const { Header, Content, Sider } = Layout

interface MainLayoutProps {
  children: ReactNode
}

export const MainLayout = ({ children }: MainLayoutProps) => {
  const navigate = useNavigate()
  const location = useLocation()
  const meQuery = useMe()
  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const canManageRbacQuery = useCanManageRbac({ enabled: hasToken })
  const canManageDriverCatalogsQuery = useCanManageDriverCatalogs({ enabled: hasToken })
  const {
    isConnected: isDatabaseStreamConnected,
    isConnecting: isDatabaseStreamConnecting,
    error: databaseStreamError,
    cooldownSeconds: databaseStreamCooldownSeconds,
    reconnect: reconnectDatabaseStream,
  } = useDatabaseStreamStatus()
  const canSeeArtifacts = Boolean(meQuery.data?.is_staff)
  const canManageUsers = Boolean(meQuery.data?.is_staff)
  const canManageAdmin = Boolean(meQuery.data?.is_staff)
  const canManageRbac = Boolean(canManageRbacQuery.data)
  const canManageDriverCatalogs = Boolean(canManageDriverCatalogsQuery.data)

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('refresh_token')
    setAuthToken(null)
    resetQueryClient()
    notifyAuthChanged()
    navigate('/login')
  }

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Выйти',
      onClick: handleLogout,
    },
  ]

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    {
      key: '/system-status',
      icon: <MonitorOutlined />,
      label: 'System Status',
    },
    {
      key: '/clusters',
      icon: <ClusterOutlined />,
      label: 'Clusters',
    },
    {
      key: '/databases',
      icon: <DatabaseOutlined />,
      label: 'Databases',
    },
    {
      key: '/extensions',
      icon: <AppstoreOutlined />,
      label: 'Extensions',
    },
    {
      key: '/operations',
      icon: <ThunderboltOutlined />,
      label: 'Operations',
    },
    ...(canSeeArtifacts
      ? [{
        key: '/artifacts',
        icon: <InboxOutlined />,
        label: 'Artifacts',
      }]
      : []),
    {
      key: '/workflows',
      icon: <ApartmentOutlined />,
      label: 'Workflows',
    },
    {
      key: '/templates',
      icon: <FileTextOutlined />,
      label: 'Templates',
    },
    {
      key: '/service-mesh',
      icon: <DeploymentUnitOutlined />,
      label: 'Service Mesh',
    },
    ...(canManageRbac
      ? [{
        key: '/rbac',
        icon: <SafetyCertificateOutlined />,
        label: 'RBAC',
      }]
      : []),
    ...(canManageUsers
      ? [{
        key: '/users',
        icon: <UserOutlined />,
        label: 'Users',
      }]
      : []),
    ...(canManageAdmin
      ? [
        {
          key: '/dlq',
          icon: <WarningOutlined />,
          label: 'DLQ',
        },
        {
          key: '/settings/runtime',
          icon: <SettingOutlined />,
          label: 'Runtime Settings',
        },
        {
          key: '/settings/action-catalog',
          icon: <SettingOutlined />,
          label: 'Action Catalog',
        },
        ...(canManageDriverCatalogs
          ? [
            {
              key: '/settings/command-schemas',
              icon: <SettingOutlined />,
              label: 'Command Schemas',
            },
          ]
          : []),
        {
          key: '/settings/timeline',
          icon: <SettingOutlined />,
          label: 'Timeline Settings',
        },
      ]
      : []),
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space size="middle">
          <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>
            CommandCenter1C
          </div>
          <Popover
            trigger="click"
            placement="bottomLeft"
            content={(
              <Space direction="vertical" size={4}>
                <Typography.Text strong>Database stream</Typography.Text>
                <Tag color={isDatabaseStreamConnected ? 'green' : 'default'}>
                  {isDatabaseStreamConnecting
                    ? 'Connecting...'
                    : isDatabaseStreamConnected
                      ? 'Connected'
                      : 'Fallback'}
                </Tag>
                {databaseStreamError && (
                  <Typography.Text type="secondary">{databaseStreamError}</Typography.Text>
                )}
                <Button
                  size="small"
                  onClick={reconnectDatabaseStream}
                  disabled={isDatabaseStreamConnecting || databaseStreamCooldownSeconds > 0}
                >
                  {databaseStreamCooldownSeconds > 0
                    ? `Retry in ${databaseStreamCooldownSeconds}s`
                    : 'Reconnect'}
                </Button>
              </Space>
            )}
          >
            <Tooltip title={isDatabaseStreamConnected ? 'Live updates enabled' : (databaseStreamError || 'Live stream unavailable')}>
              <Tag color={isDatabaseStreamConnected ? 'green' : 'default'} style={{ cursor: 'pointer' }}>
                {isDatabaseStreamConnecting && <LoadingOutlined style={{ marginRight: 6 }} spin />}
                Stream: {isDatabaseStreamConnected ? 'Connected' : 'Fallback'}
              </Tag>
            </Tooltip>
          </Popover>
        </Space>
        <Space size="small">
          {meQuery.data?.is_staff && (
            <Tag color="blue">Staff</Tag>
          )}
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" icon={<UserOutlined />} style={{ color: 'white' }}>
              {meQuery.data?.username ?? '...'}
            </Button>
          </Dropdown>
        </Space>
      </Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>
        <Layout style={{ padding: '24px' }}>
          <Content
            style={{
              padding: 24,
              margin: 0,
              minHeight: 280,
              background: '#fff',
            }}
          >
            {children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}
