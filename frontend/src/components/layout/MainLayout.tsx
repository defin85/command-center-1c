import { Layout, Menu, Button, Dropdown, Tag, Tooltip, Space, Popover, Typography, Select, Grid } from 'antd'
import { DashboardOutlined, ThunderboltOutlined, DatabaseOutlined, ClusterOutlined, UserOutlined, LogoutOutlined, MonitorOutlined, ApartmentOutlined, DeploymentUnitOutlined, SafetyCertificateOutlined, FileTextOutlined, WarningOutlined, LoadingOutlined, SettingOutlined, InboxOutlined, AppstoreOutlined } from '@ant-design/icons'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import type { ReactNode, MouseEvent } from 'react'
import type { MenuProps } from 'antd'

import { useShellBootstrap } from '../../api/queries/shellBootstrap'
import { useSetActiveTenant } from '../../api/queries/tenants'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { setAuthToken } from '../../api/client'
import { notifyAuthChanged } from '../../lib/authState'
import { resetQueryClient } from '../../lib/queryClient'
import { POOL_BINDING_PROFILES_ROUTE } from '../../pages/Pools/routes'

const { Header, Content, Sider } = Layout
const { useBreakpoint } = Grid

interface MainLayoutProps {
  children: ReactNode
}

export const MainLayout = ({ children }: MainLayoutProps) => {
  const screens = useBreakpoint()
  const navigate = useNavigate()
  const location = useLocation()
  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const shellBootstrapQuery = useShellBootstrap({ enabled: hasToken })
  const setActiveTenantMutation = useSetActiveTenant()
  const {
    isConnected: isDatabaseStreamConnected,
    isConnecting: isDatabaseStreamConnecting,
    error: databaseStreamError,
    cooldownSeconds: databaseStreamCooldownSeconds,
    reconnect: reconnectDatabaseStream,
  } = useDatabaseStreamStatus()
  const me = shellBootstrapQuery.data?.me
  const tenantContext = shellBootstrapQuery.data?.tenant_context
  const capabilities = shellBootstrapQuery.data?.capabilities
  const canSeeArtifacts = Boolean(me?.is_staff)
  const canManageUsers = Boolean(me?.is_staff)
  const canManageAdmin = Boolean(me?.is_staff)
  const canManageRbac = Boolean(capabilities?.can_manage_rbac)
  const canManageDriverCatalogs = Boolean(capabilities?.can_manage_driver_catalogs)

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

  const tenants = tenantContext?.tenants ?? []
  const activeTenantId = localStorage.getItem('active_tenant_id') || tenantContext?.active_tenant_id || undefined

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
      key: '/decisions',
      icon: <FileTextOutlined />,
      label: 'Decisions',
    },
    {
      key: '/pools/catalog',
      icon: <FileTextOutlined />,
      label: 'Pool Catalog',
    },
    {
      key: POOL_BINDING_PROFILES_ROUTE,
      icon: <FileTextOutlined />,
      label: 'Pool Binding Profiles',
    },
    {
      key: '/pools/master-data',
      icon: <FileTextOutlined />,
      label: 'Pool Master Data',
    },
    {
      key: '/pools/runs',
      icon: <FileTextOutlined />,
      label: 'Pool Runs',
    },
    {
      key: '/pools/templates',
      icon: <FileTextOutlined />,
      label: 'Pool Templates',
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
      <Header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          rowGap: 12,
          columnGap: 16,
          height: 'auto',
          paddingBlock: 12,
        }}
      >
        <Space size="middle" wrap>
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
        <Space size="small" wrap>
          {tenants.length > 1 && (
            <Select
              aria-label="Active tenant"
              size="small"
              loading={shellBootstrapQuery.isFetching}
              disabled={setActiveTenantMutation.isPending}
              value={activeTenantId}
              style={{ width: screens.sm ? 220 : 'min(220px, 100%)' }}
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
          {me?.is_staff && (
            <Tag color="blue">Staff</Tag>
          )}
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" icon={<UserOutlined />} style={{ color: 'white' }}>
              {me?.username ?? '\u2026'}
            </Button>
          </Dropdown>
        </Space>
      </Header>
      <Layout>
        <Sider
          width={200}
          theme="light"
          breakpoint="lg"
          collapsedWidth={0}
        >
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => {
              const nextPath = String(key)
              if (nextPath === location.pathname) {
                return
              }
              navigate(nextPath)
            }}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>
        <Layout style={{ padding: screens.lg ? '24px' : '16px' }}>
          <Content
            id="main-content"
            role="main"
            tabIndex={-1}
            style={{
              padding: screens.lg ? 24 : 16,
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
