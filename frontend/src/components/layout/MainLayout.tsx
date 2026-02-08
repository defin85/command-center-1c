import { Layout, Menu, Button, Dropdown, Tag, Tooltip, Space, Popover, Typography, Select } from 'antd'
import { DashboardOutlined, ThunderboltOutlined, DatabaseOutlined, ClusterOutlined, UserOutlined, LogoutOutlined, MonitorOutlined, ApartmentOutlined, DeploymentUnitOutlined, SafetyCertificateOutlined, FileTextOutlined, WarningOutlined, LoadingOutlined, SettingOutlined, InboxOutlined, AppstoreOutlined } from '@ant-design/icons'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useEffect, type ReactNode, type MouseEvent } from 'react'
import type { MenuProps } from 'antd'

import { useMe } from '../../api/queries/me'
import { useCanManageRbac } from '../../api/queries/rbac'
import { useCanManageDriverCatalogs } from '../../api/queries/commandSchemas'
import { useMyTenants, useSetActiveTenant } from '../../api/queries/tenants'
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
  const myTenantsQuery = useMyTenants({ enabled: hasToken })
  const setActiveTenantMutation = useSetActiveTenant()
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

  useEffect(() => {
    const data = myTenantsQuery.data
    if (!data) return

    const stored = localStorage.getItem('active_tenant_id')
    const preferred = data.active_tenant_id || data.tenants[0]?.id || null
    if (!stored && preferred) {
      localStorage.setItem('active_tenant_id', preferred)
    }
    if (stored && data.active_tenant_id && stored !== data.active_tenant_id) {
      localStorage.setItem('active_tenant_id', data.active_tenant_id)
    }
  }, [myTenantsQuery.data])

  const handleSkipToContent = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    const el = document.getElementById('main-content')
    if (el instanceof HTMLElement) {
      el.scrollIntoView({ block: 'start' })
      el.focus({ preventScroll: true })
    }
  }

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

  const tenants = myTenantsQuery.data?.tenants ?? []
  const activeTenantId = localStorage.getItem('active_tenant_id') || myTenantsQuery.data?.active_tenant_id || undefined

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
      <a href="#main-content" className="cc-skip-link" onClick={handleSkipToContent}>
        Skip to content
      </a>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space size="middle">
          <Link to="/" style={{ color: 'white', fontSize: '20px', fontWeight: 'bold', textDecoration: 'none' }}>
            CommandCenter1C
          </Link>
          <Popover
            trigger="click"
            placement="bottomLeft"
            content={(
              <Space direction="vertical" size={4}>
                <Typography.Text strong>Database stream</Typography.Text>
                <Tag color={isDatabaseStreamConnected ? 'green' : 'default'}>
                  {isDatabaseStreamConnecting
                    ? 'Connecting\u2026'
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
              <Button type="text" aria-label="Database stream status" style={{ padding: 0, height: 'auto' }}>
                <Tag color={isDatabaseStreamConnected ? 'green' : 'default'} style={{ cursor: 'pointer' }}>
                  {isDatabaseStreamConnecting && <LoadingOutlined style={{ marginRight: 6 }} spin />}
                  Stream: {isDatabaseStreamConnected ? 'Connected' : 'Fallback'}
                </Tag>
              </Button>
            </Tooltip>
          </Popover>
        </Space>
        <Space size="small">
          {tenants.length > 1 && (
            <Select
              size="small"
              loading={myTenantsQuery.isFetching}
              disabled={setActiveTenantMutation.isPending}
              value={activeTenantId}
              style={{ width: 220 }}
              options={tenants.map((t) => ({ value: t.id, label: t.name }))}
              onChange={(tenantId) => {
                setActiveTenantMutation.mutate(tenantId, {
                  onSuccess: () => {
                    localStorage.setItem('active_tenant_id', tenantId)
                    resetQueryClient()
                    window.location.reload()
                  },
                })
              }}
            />
          )}
          {meQuery.data?.is_staff && (
            <Tag color="blue">Staff</Tag>
          )}
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" icon={<UserOutlined />} style={{ color: 'white' }}>
              {meQuery.data?.username ?? '\u2026'}
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
            id="main-content"
            role="main"
            tabIndex={-1}
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
