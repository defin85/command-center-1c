import { useEffect, useState, Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, App as AntApp, Spin } from 'antd'
import { MainLayout } from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { API_ERROR_EVENT } from './api/client'
import { useRealtimeInvalidation } from './hooks/useRealtimeInvalidation'
import { DatabaseStreamProvider } from './contexts/DatabaseStreamContext'
import { useMe } from './api/queries/me'
import { useCanManageRbac } from './api/queries/rbac'
import { useCanManageDriverCatalogs } from './api/queries/commandSchemas'
import { getAuthToken, subscribeAuthChange } from './lib/authState'
import { AuthzProvider } from './authz'

const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard').then((m) => ({ default: m.Dashboard })))
const Operations = lazy(() => import('./pages/Operations/OperationsPage').then((m) => ({ default: m.OperationsPage })))
const Databases = lazy(() => import('./pages/Databases/Databases').then((m) => ({ default: m.Databases })))
const Extensions = lazy(() => import('./pages/Extensions/Extensions').then((m) => ({ default: m.Extensions })))
const Clusters = lazy(() => import('./pages/Clusters/Clusters').then((m) => ({ default: m.Clusters })))
const SystemStatus = lazy(() => import('./pages/SystemStatus/SystemStatus').then((m) => ({ default: m.SystemStatus })))
const WorkflowList = lazy(() => import('./pages/Workflows/WorkflowList'))
const WorkflowDesigner = lazy(() => import('./pages/Workflows/WorkflowDesigner'))
const WorkflowMonitor = lazy(() => import('./pages/Workflows/WorkflowMonitor'))
const WorkflowExecutions = lazy(() => import('./pages/Workflows/WorkflowExecutions'))
const ServiceMeshPage = lazy(() => import('./pages/ServiceMesh/ServiceMeshPage'))
const loadRBACPage = () => import('./pages/RBAC/RBACPage').then((m) => ({ default: m.RBACPage }))
const RBACPage = lazy(loadRBACPage)

const loadUsersPage = () => import('./pages/Users/UsersPage').then((m) => ({ default: m.UsersPage }))
const UsersPage = lazy(loadUsersPage)
const TemplatesPage = lazy(() => import('./pages/Templates/TemplatesPage').then((m) => ({ default: m.TemplatesPage })))

const loadCommandSchemasPage = () => import('./pages/CommandSchemas/CommandSchemasPage')
const CommandSchemasPage = lazy(loadCommandSchemasPage)

const loadDLQPage = () => import('./pages/DLQ/DLQPage').then((m) => ({ default: m.DLQPage }))
const DLQPage = lazy(loadDLQPage)

const loadRuntimeSettingsPage = () => import('./pages/Settings/RuntimeSettingsPage').then((m) => ({ default: m.RuntimeSettingsPage }))
const RuntimeSettingsPage = lazy(loadRuntimeSettingsPage)

const loadTimelineSettingsPage = () => import('./pages/Settings/TimelineSettingsPage').then((m) => ({ default: m.TimelineSettingsPage }))
const TimelineSettingsPage = lazy(loadTimelineSettingsPage)
const PoolCatalogPage = lazy(() => import('./pages/Pools/PoolCatalogPage').then((m) => ({ default: m.PoolCatalogPage })))
const PoolSchemaTemplatesPage = lazy(() => import('./pages/Pools/PoolSchemaTemplatesPage').then((m) => ({ default: m.PoolSchemaTemplatesPage })))
const PoolRunsPage = lazy(() => import('./pages/Pools/PoolRunsPage').then((m) => ({ default: m.PoolRunsPage })))

const Login = lazy(() => import('./pages/Login/Login').then((m) => ({ default: m.Login })))
const ArtifactsPage = lazy(() => import('./pages/Artifacts/ArtifactsPage').then((m) => ({ default: m.ArtifactsPage })))
const ForbiddenPage = lazy(() => import('./pages/Forbidden/ForbiddenPage').then((m) => ({ default: m.ForbiddenPage })))

function RouteLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 240 }}>
      <Spin size="large" />
    </div>
  )
}

function LazyBoundary({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<RouteLoading />}>
      {children}
    </Suspense>
  )
}

// Компонент для защиты маршрутов
const ProtectedRoute = ({ children, authToken }: { children: React.ReactNode, authToken: string | null }) => {
  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

const StaffRoute = ({ children, authToken, preload }: { children: React.ReactNode, authToken: string | null, preload?: () => Promise<unknown> }) => {
  const meQuery = useMe({ enabled: Boolean(authToken) })
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (meQuery.isLoading) {
    return <RouteLoading />
  }

  if (!meQuery.data?.is_staff) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

const RbacRoute = ({ children, authToken, preload }: { children: React.ReactNode, authToken: string | null, preload?: () => Promise<unknown> }) => {
  const canManageRbacQuery = useCanManageRbac({ enabled: Boolean(authToken) })
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (canManageRbacQuery.isLoading) {
    return <RouteLoading />
  }

  if (!canManageRbacQuery.data) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

const DriverCatalogsRoute = ({ children, authToken, preload }: { children: React.ReactNode, authToken: string | null, preload?: () => Promise<unknown> }) => {
  const canManageDriverCatalogsQuery = useCanManageDriverCatalogs({ enabled: Boolean(authToken) })
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (canManageDriverCatalogsQuery.isLoading) {
    return <RouteLoading />
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
  const [authToken, setAuthToken] = useState(() => getAuthToken())
  // Enable real-time cache invalidation via WebSocket only for authenticated sessions
  useRealtimeInvalidation(Boolean(authToken))

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
                  <Route path="/login" element={<LazyBoundary><Login /></LazyBoundary>} />
                  <Route path="/forbidden" element={<LazyBoundary><ForbiddenPage /></LazyBoundary>} />

                  {/* Защищенные маршруты */}
                  <Route path="/" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><Dashboard /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/clusters" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><Clusters /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/operations" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><Operations /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/artifacts" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><ArtifactsPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/databases" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><Databases /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/extensions" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><Extensions /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  {/* Legacy routes - redirect to unified Operations page */}
                  <Route path="/installation-monitor" element={<Navigate to="/operations?tab=list" replace />} />
                  <Route path="/operation-monitor" element={<Navigate to="/operations?tab=monitor" replace />} />
                  <Route path="/system-status" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><SystemStatus /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  {/* Workflow routes */}
                  <Route path="/workflows" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><WorkflowList /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/workflows/executions" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><WorkflowExecutions /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/workflows/new" element={
                    <ProtectedRoute authToken={authToken}>
                      <LazyBoundary><WorkflowDesigner /></LazyBoundary>
                    </ProtectedRoute>
                  } />
                  <Route path="/workflows/:id" element={
                    <ProtectedRoute authToken={authToken}>
                      <LazyBoundary><WorkflowDesigner /></LazyBoundary>
                    </ProtectedRoute>
                  } />
                  <Route path="/workflows/executions/:executionId" element={
                    <ProtectedRoute authToken={authToken}>
                      <LazyBoundary><WorkflowMonitor /></LazyBoundary>
                    </ProtectedRoute>
                  } />
                  <Route path="/templates" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><TemplatesPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/pools/templates" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolSchemaTemplatesPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/pools/catalog" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolCatalogPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/pools/runs" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolRunsPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  {/* Service Mesh route */}
                  <Route path="/service-mesh" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><ServiceMeshPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/rbac" element={
                    <RbacRoute authToken={authToken} preload={loadRBACPage}>
                      <MainLayout>
                        <LazyBoundary><RBACPage /></LazyBoundary>
                      </MainLayout>
                    </RbacRoute>
                  } />
                  <Route path="/users" element={
                    <StaffRoute authToken={authToken} preload={loadUsersPage}>
                      <MainLayout>
                        <LazyBoundary><UsersPage /></LazyBoundary>
                      </MainLayout>
                    </StaffRoute>
                  } />
                  <Route path="/dlq" element={
                    <StaffRoute authToken={authToken} preload={loadDLQPage}>
                      <MainLayout>
                        <LazyBoundary><DLQPage /></LazyBoundary>
                      </MainLayout>
                    </StaffRoute>
                  } />
                  <Route path="/settings/runtime" element={
                    <StaffRoute authToken={authToken} preload={loadRuntimeSettingsPage}>
                      <MainLayout>
                        <LazyBoundary><RuntimeSettingsPage /></LazyBoundary>
                      </MainLayout>
                    </StaffRoute>
                  } />
                  <Route path="/settings/driver-catalogs" element={
                    <DriverCatalogsRoute authToken={authToken} preload={loadCommandSchemasPage}>
                      <Navigate to="/settings/command-schemas?mode=raw" replace />
                    </DriverCatalogsRoute>
                  } />
                  <Route path="/settings/command-schemas" element={
                    <DriverCatalogsRoute authToken={authToken} preload={loadCommandSchemasPage}>
                      <MainLayout>
                        <LazyBoundary><CommandSchemasPage /></LazyBoundary>
                      </MainLayout>
                    </DriverCatalogsRoute>
                  } />
                  <Route path="/settings/timeline" element={
                    <StaffRoute authToken={authToken} preload={loadTimelineSettingsPage}>
                      <MainLayout>
                        <LazyBoundary><TimelineSettingsPage /></LazyBoundary>
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
