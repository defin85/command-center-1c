import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import { MainLayout } from './components/layout/MainLayout'
import { Dashboard } from './pages/Dashboard/Dashboard'
import { Operations } from './pages/Operations/Operations'
import { Databases } from './pages/Databases/Databases'
import { InstallationMonitorPage } from './pages/InstallationMonitor/InstallationMonitorPage'

function App() {
  return (
    <ConfigProvider theme={{
      token: {
        colorPrimary: '#1890ff',
      },
    }}>
      <BrowserRouter>
        <MainLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/operations" element={<Operations />} />
            <Route path="/databases" element={<Databases />} />
            <Route path="/installation-monitor" element={<InstallationMonitorPage />} />
          </Routes>
        </MainLayout>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
