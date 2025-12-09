import { Layout, Menu, Button, Dropdown } from 'antd'
import { DashboardOutlined, ThunderboltOutlined, DatabaseOutlined, ClusterOutlined, UserOutlined, LogoutOutlined, MonitorOutlined, ApartmentOutlined, DeploymentUnitOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { MenuProps } from 'antd'

const { Header, Content, Sider } = Layout

interface MainLayoutProps {
  children: ReactNode
}

export const MainLayout = ({ children }: MainLayoutProps) => {
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('refresh_token')
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
      key: '/operations',
      icon: <ThunderboltOutlined />,
      label: 'Operations',
    },
    {
      key: '/workflows',
      icon: <ApartmentOutlined />,
      label: 'Workflows',
    },
    {
      key: '/service-mesh',
      icon: <DeploymentUnitOutlined />,
      label: 'Service Mesh',
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>
          CommandCenter1C
        </div>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Button type="text" icon={<UserOutlined />} style={{ color: 'white' }}>
            admin
          </Button>
        </Dropdown>
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
