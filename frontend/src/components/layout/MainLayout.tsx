import { Layout, Menu, Button, Dropdown, Tag, Tooltip, Space, Popover, Typography, Select, Grid, Spin } from 'antd'
import { DashboardOutlined, ThunderboltOutlined, DatabaseOutlined, ClusterOutlined, UserOutlined, LogoutOutlined, MonitorOutlined, ApartmentOutlined, DeploymentUnitOutlined, SafetyCertificateOutlined, FileTextOutlined, WarningOutlined, LoadingOutlined, SettingOutlined, InboxOutlined, AppstoreOutlined } from '@ant-design/icons'
import { flushSync } from 'react-dom'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useEffect, useState, type ReactNode, type MouseEvent } from 'react'
import type { MenuProps } from 'antd'

import { useSetActiveTenant } from '../../api/queries/tenants'
import { useDatabaseStreamStatus } from '../../contexts/DatabaseStreamContext'
import { setAuthToken } from '../../api/client'
import { notifyAuthChanged } from '../../lib/authState'
import { resetQueryClient } from '../../lib/queryClient'
import { POOL_EXECUTION_PACKS_ROUTE, POOL_FACTUAL_ROUTE, POOL_TOPOLOGY_TEMPLATES_ROUTE } from '../../pages/Pools/routes'
import { useShellRuntime } from '../../shell/ShellRuntimeProvider'
import { useCommonTranslation, useLocaleState, useShellTranslation } from '../../i18n'

const { Header, Content, Sider } = Layout
const { useBreakpoint } = Grid

const STREAM_TAG_STYLES = {
  connected: {
    backgroundColor: '#dcfce7',
    borderColor: '#86efac',
    color: '#166534',
  },
  fallback: {
    backgroundColor: '#f3f4f6',
    borderColor: '#d1d5db',
    color: '#374151',
  },
} as const

interface MainLayoutProps {
  children: ReactNode
}

export const MainLayout = ({ children }: MainLayoutProps) => {
  const { t: tCommon } = useCommonTranslation()
  const { t: tShell } = useShellTranslation()
  const { locale, setLocale, supportedLocales } = useLocaleState()
  const screens = useBreakpoint()
  const navigate = useNavigate()
  const location = useLocation()
  const [pendingNavigationPath, setPendingNavigationPath] = useState<string | null>(null)
  const { shellBootstrapQuery } = useShellRuntime()
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
  const databaseStreamLabel = isDatabaseStreamConnecting
    ? tShell(($) => $.stream.buttonLabel.connecting)
    : isDatabaseStreamConnected
      ? tShell(($) => $.stream.buttonLabel.connected)
      : tShell(($) => $.stream.buttonLabel.fallback)
  const streamTagStyle = isDatabaseStreamConnected
    ? STREAM_TAG_STYLES.connected
    : STREAM_TAG_STYLES.fallback
  const isRouteSwitchPending = Boolean(pendingNavigationPath && pendingNavigationPath !== location.pathname)

  useEffect(() => {
    if (pendingNavigationPath === location.pathname) {
      setPendingNavigationPath(null)
    }
  }, [location.pathname, pendingNavigationPath])

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
      label: tCommon(($) => $.actions.logout),
      onClick: handleLogout,
    },
  ]

  const tenants = tenantContext?.tenants ?? []
  const activeTenantId = localStorage.getItem('active_tenant_id') || tenantContext?.active_tenant_id || undefined

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: tShell(($) => $.navigation.dashboard),
    },
    {
      key: '/system-status',
      icon: <MonitorOutlined />,
      label: tShell(($) => $.navigation.systemStatus),
    },
    {
      key: '/clusters',
      icon: <ClusterOutlined />,
      label: tShell(($) => $.navigation.clusters),
    },
    {
      key: '/databases',
      icon: <DatabaseOutlined />,
      label: tShell(($) => $.navigation.databases),
    },
    {
      key: '/extensions',
      icon: <AppstoreOutlined />,
      label: tShell(($) => $.navigation.extensions),
    },
    {
      key: '/operations',
      icon: <ThunderboltOutlined />,
      label: tShell(($) => $.navigation.operations),
    },
    ...(canSeeArtifacts
      ? [{
        key: '/artifacts',
        icon: <InboxOutlined />,
        label: tShell(($) => $.navigation.artifacts),
      }]
      : []),
    {
      key: '/workflows',
      icon: <ApartmentOutlined />,
      label: tShell(($) => $.navigation.workflows),
    },
    {
      key: '/templates',
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.templates),
    },
    {
      key: '/decisions',
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.decisions),
    },
    {
      key: '/pools/catalog',
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolCatalog),
    },
    {
      key: POOL_TOPOLOGY_TEMPLATES_ROUTE,
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolTopologyTemplates),
    },
    {
      key: POOL_EXECUTION_PACKS_ROUTE,
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolExecutionPacks),
    },
    {
      key: '/pools/master-data',
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolMasterData),
    },
    {
      key: '/pools/runs',
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolRuns),
    },
    {
      key: POOL_FACTUAL_ROUTE,
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolFactual),
    },
    {
      key: '/pools/templates',
      icon: <FileTextOutlined />,
      label: tShell(($) => $.navigation.poolTemplates),
    },
    {
      key: '/service-mesh',
      icon: <DeploymentUnitOutlined />,
      label: tShell(($) => $.navigation.serviceMesh),
    },
    ...(canManageRbac
      ? [{
        key: '/rbac',
        icon: <SafetyCertificateOutlined />,
        label: tShell(($) => $.navigation.rbac),
      }]
      : []),
    ...(canManageUsers
      ? [{
        key: '/users',
        icon: <UserOutlined />,
        label: tShell(($) => $.navigation.users),
      }]
      : []),
    ...(canManageAdmin
      ? [
        {
          key: '/dlq',
          icon: <WarningOutlined />,
          label: tShell(($) => $.navigation.dlq),
        },
        {
          key: '/settings/runtime',
          icon: <SettingOutlined />,
          label: tShell(($) => $.navigation.runtimeSettings),
        },
        ...(canManageDriverCatalogs
          ? [
            {
              key: '/settings/command-schemas',
              icon: <SettingOutlined />,
              label: tShell(($) => $.navigation.commandSchemas),
            },
          ]
          : []),
        {
          key: '/settings/timeline',
          icon: <SettingOutlined />,
          label: tShell(($) => $.navigation.timelineSettings),
        },
      ]
      : []),
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <a href="#main-content" className="cc-skip-link" onClick={handleSkipToContent}>
        {tShell(($) => $.skipToContent)}
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
            {tShell(($) => $.appName)}
          </Link>
          <Popover
            trigger="click"
            placement="bottomLeft"
            content={(
              <Space direction="vertical" size={4}>
                <Typography.Text strong>{tShell(($) => $.stream.title)}</Typography.Text>
                <Tag
                  style={{
                    backgroundColor: streamTagStyle.backgroundColor,
                    borderColor: streamTagStyle.borderColor,
                    color: streamTagStyle.color,
                  }}
                >
                  {isDatabaseStreamConnecting
                    ? tShell(($) => $.stream.tag.connecting)
                    : isDatabaseStreamConnected
                      ? tShell(($) => $.stream.tag.connected)
                      : tShell(($) => $.stream.tag.fallback)}
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
                    ? tShell(($) => $.stream.retryIn, { seconds: String(databaseStreamCooldownSeconds) })
                    : tCommon(($) => $.actions.reconnect)}
                </Button>
              </Space>
            )}
          >
            <Tooltip title={isDatabaseStreamConnected ? tShell(($) => $.stream.tooltip.connected) : (databaseStreamError || tShell(($) => $.stream.tooltip.unavailable))}>
              <Button type="text" aria-label={databaseStreamLabel} style={{ padding: 0, height: 'auto' }}>
                <Tag
                  style={{
                    cursor: 'pointer',
                    backgroundColor: streamTagStyle.backgroundColor,
                    borderColor: streamTagStyle.borderColor,
                    color: streamTagStyle.color,
                  }}
                >
                  {isDatabaseStreamConnecting && <LoadingOutlined style={{ marginRight: 6 }} spin />}
                  {databaseStreamLabel}
                </Tag>
              </Button>
            </Tooltip>
          </Popover>
        </Space>
        <Space size="small" wrap>
          <Select
            data-testid="shell-locale-select"
            aria-label={tShell(($) => $.locale.label)}
            size="small"
            value={locale}
            style={{ width: screens.sm ? 136 : 'min(136px, 100%)' }}
            options={supportedLocales.map((value) => ({
              value,
              label: value === 'ru'
                ? tShell(($) => $.locale.options.ru)
                : tShell(($) => $.locale.options.en),
            }))}
            onChange={(value) => {
              void setLocale(value)
            }}
          />
          {tenants.length > 1 && (
            <Select
              aria-label={tShell(($) => $.tenant.activeLabel)}
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
            <Tag color="blue">{tShell(($) => $.tenant.staffBadge)}</Tag>
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
              const navigationTarget = nextPath === '/pools/master-data'
                ? '/pools/master-data?tab=party'
                : nextPath

              flushSync(() => {
                setPendingNavigationPath(nextPath)
              })
              navigate(navigationTarget)
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
            {isRouteSwitchPending ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 240 }}>
                <Spin size="large" />
              </div>
            ) : children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}
