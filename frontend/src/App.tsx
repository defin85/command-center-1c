import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, App as AntApp } from 'antd'
import { MainLayout } from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Dashboard } from './pages/Dashboard/Dashboard'
import { Operations } from './pages/Operations'
import { Databases } from './pages/Databases/Databases'
import { Extensions } from './pages/Extensions/Extensions'
import { Clusters } from './pages/Clusters/Clusters'
import { SystemStatus } from './pages/SystemStatus/SystemStatus'
import { WorkflowList, WorkflowDesigner, WorkflowMonitor, WorkflowExecutions } from './pages/Workflows'
import { ServiceMeshPage } from './pages/ServiceMesh'
import { RBACPage } from './pages/RBAC/RBACPage'
import { UsersPage } from './pages/Users/UsersPage'
import { TemplatesPage } from './pages/Templates/TemplatesPage'
import { CommandSchemasPage } from './pages/CommandSchemas/CommandSchemasPage'
import { DLQPage } from './pages/DLQ'
import { RuntimeSettingsPage, TimelineSettingsPage } from './pages/Settings'
import { Login } from './pages/Login/Login'
import { ArtifactsPage } from './pages/Artifacts'
import { ForbiddenPage } from './pages/Forbidden/ForbiddenPage'
import { API_ERROR_EVENT } from './api/client'
import { useRealtimeInvalidation } from './hooks/useRealtimeInvalidation'
import { DatabaseStreamProvider } from './contexts/DatabaseStreamContext'
import { useMe } from './api/queries/me'
import { useCanManageRbac } from './api/queries/rbac'
import { useCanManageDriverCatalogs } from './api/queries'
import { getAuthToken, subscribeAuthChange } from './lib/authState'
import { AuthzProvider } from './authz'

// Компонент для защиты маршрутов
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

const StaffRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token')
  const meQuery = useMe()

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (meQuery.isLoading) {
    return <div />
  }

  if (!meQuery.data?.is_staff) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

const RbacRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token')
  const canManageRbacQuery = useCanManageRbac({ enabled: Boolean(token) })

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (canManageRbacQuery.isLoading) {
    return <div />
  }

  if (!canManageRbacQuery.data) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

const DriverCatalogsRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token')
  const canManageDriverCatalogsQuery = useCanManageDriverCatalogs({ enabled: Boolean(token) })

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (canManageDriverCatalogsQuery.isLoading) {
    return <div />
  }

  if (!canManageDriverCatalogsQuery.data) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

// Global API error handler component
// Must be inside AntApp to access notification API
interface ApiErrorDetail {
  message: string
  status?: number
  code?: string
}

function GlobalApiErrorHandler() {
  const { notification } = AntApp.useApp()

  useEffect(() => {
    const handleApiError = (event: CustomEvent<ApiErrorDetail>) => {
      const { message, status, code } = event.detail

      // Don't show notification for 401 errors (handled by redirect)
      if (status === 401) {
        return
      }

      // Determine notification type based on status
      let type: 'error' | 'warning' | 'info' = 'error'
      if (status === 404) {
        type = 'warning'
      } else if (status && status >= 500) {
        type = 'error'
      }

      notification[type]({
        message: 'Request Error',
        description: message,
        placement: 'topRight',
        duration: 5,
        key: code || `api-error-${Date.now()}`, // Prevent duplicate notifications
      })
    }

    window.addEventListener(API_ERROR_EVENT, handleApiError as EventListener)

    return () => {
      window.removeEventListener(API_ERROR_EVENT, handleApiError as EventListener)
    }
  }, [notification])

  return null
}

function App() {
  // Enable real-time cache invalidation via WebSocket
  useRealtimeInvalidation()
  const [authToken, setAuthToken] = useState(() => getAuthToken())

  useEffect(() => {
    return subscribeAuthChange(() => {
      setAuthToken(getAuthToken())
    })
  }, [])

  return (
    <ErrorBoundary>
      <ConfigProvider theme={{
        token: {
          colorPrimary: '#1890ff',
        },
      }}>
        <AntApp>
          <GlobalApiErrorHandler />
          <AuthzProvider key={authToken ?? 'guest'}>
            <DatabaseStreamProvider>
              <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <Routes>
          {/* Публичный маршрут - логин */}
          <Route path="/login" element={<Login />} />
          <Route path="/forbidden" element={<ForbiddenPage />} />

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
          <Route path="/artifacts" element={
            <ProtectedRoute>
              <MainLayout>
                <ArtifactsPage />
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
          <Route path="/extensions" element={
            <ProtectedRoute>
              <MainLayout>
                <Extensions />
              </MainLayout>
            </ProtectedRoute>
          } />
          {/* Legacy routes - redirect to unified Operations page */}
          <Route path="/installation-monitor" element={<Navigate to="/operations?tab=list" replace />} />
          <Route path="/operation-monitor" element={<Navigate to="/operations?tab=monitor" replace />} />
          <Route path="/system-status" element={
            <ProtectedRoute>
              <MainLayout>
                <SystemStatus />
              </MainLayout>
            </ProtectedRoute>
          } />
          {/* Workflow routes */}
          <Route path="/workflows" element={
            <ProtectedRoute>
              <MainLayout>
                <WorkflowList />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/workflows/executions" element={
            <ProtectedRoute>
              <MainLayout>
                <WorkflowExecutions />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/workflows/new" element={
            <ProtectedRoute>
              <WorkflowDesigner />
            </ProtectedRoute>
          } />
          <Route path="/workflows/:id" element={
            <ProtectedRoute>
              <WorkflowDesigner />
            </ProtectedRoute>
          } />
          <Route path="/workflows/executions/:executionId" element={
            <ProtectedRoute>
              <WorkflowMonitor />
            </ProtectedRoute>
          } />
          <Route path="/templates" element={
            <ProtectedRoute>
              <MainLayout>
                <TemplatesPage />
              </MainLayout>
            </ProtectedRoute>
          } />
          {/* Service Mesh route */}
          <Route path="/service-mesh" element={
            <ProtectedRoute>
              <MainLayout>
                <ServiceMeshPage />
              </MainLayout>
            </ProtectedRoute>
          } />
          <Route path="/rbac" element={
            <RbacRoute>
              <MainLayout>
                <RBACPage />
              </MainLayout>
            </RbacRoute>
          } />
          <Route path="/users" element={
            <StaffRoute>
              <MainLayout>
                <UsersPage />
              </MainLayout>
            </StaffRoute>
          } />
          <Route path="/dlq" element={
            <StaffRoute>
              <MainLayout>
                <DLQPage />
              </MainLayout>
            </StaffRoute>
          } />
          <Route path="/settings/runtime" element={
            <StaffRoute>
              <MainLayout>
                <RuntimeSettingsPage />
              </MainLayout>
            </StaffRoute>
          } />
          <Route path="/settings/driver-catalogs" element={
            <DriverCatalogsRoute>
              <Navigate to="/settings/command-schemas?mode=raw" replace />
            </DriverCatalogsRoute>
          } />
          <Route path="/settings/command-schemas" element={
            <DriverCatalogsRoute>
              <MainLayout>
                <CommandSchemasPage />
              </MainLayout>
            </DriverCatalogsRoute>
          } />
          <Route path="/settings/timeline" element={
            <StaffRoute>
              <MainLayout>
                <TimelineSettingsPage />
              </MainLayout>
            </StaffRoute>
          } />
                </Routes>
              </BrowserRouter>
            </DatabaseStreamProvider>
          </AuthzProvider>
        </AntApp>
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
