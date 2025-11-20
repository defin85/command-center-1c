import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import { MainLayout } from './components/layout/MainLayout'
import { Dashboard } from './pages/Dashboard/Dashboard'
import { Operations } from './pages/Operations/Operations'
import { Databases } from './pages/Databases/Databases'
import { Clusters } from './pages/Clusters/Clusters'
import { SystemStatus } from './pages/SystemStatus/SystemStatus'
import { InstallationMonitorPage } from './pages/InstallationMonitor/InstallationMonitorPage'
import { OperationMonitor } from './pages/OperationMonitor'
import { Login } from './pages/Login/Login'

// Компонент для защиты маршрутов
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <ConfigProvider theme={{
      token: {
        colorPrimary: '#1890ff',
      },
    }}>
      <BrowserRouter>
        <Routes>
          {/* Публичный маршрут - логин */}
          <Route path="/login" element={<Login />} />

          {/* Защищенные маршруты */}
          <Route path="/" element={
            <ProtectedRoute>
              <MainLayout>
                <Dashboard />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/clusters" element={
            <ProtectedRoute>
              <MainLayout>
                <Clusters />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/operations" element={
            <ProtectedRoute>
              <MainLayout>
                <Operations />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/databases" element={
            <ProtectedRoute>
              <MainLayout>
                <Databases />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/installation-monitor" element={
            <ProtectedRoute>
              <MainLayout>
                <InstallationMonitorPage />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/operation-monitor" element={
            <ProtectedRoute>
              <MainLayout>
                <OperationMonitor />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/system-status" element={
            <ProtectedRoute>
              <MainLayout>
                <SystemStatus />
              </MainLayout>
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
