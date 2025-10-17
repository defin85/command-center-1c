import { Layout, Menu } from 'antd'
import { DashboardOutlined, ThunderboltOutlined, DatabaseOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

const { Header, Content, Sider } = Layout

interface MainLayoutProps {
  children: ReactNode
}

export const MainLayout = ({ children }: MainLayoutProps) => {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    {
      key: '/operations',
      icon: <ThunderboltOutlined />,
      label: 'Operations',
    },
    {
      key: '/databases',
      icon: <DatabaseOutlined />,
      label: 'Databases',
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>
          CommandCenter1C
        </div>
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
