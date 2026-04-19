import { useEffect, useState, Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Button, ConfigProvider, App as AntApp, Result, Spin } from 'antd'
import { MainLayout } from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { API_ERROR_EVENT } from './api/client'
import type { ApiErrorDetail } from './api/apiErrorPolicy'
import { useRealtimeInvalidation } from './hooks/useRealtimeInvalidation'
import { DatabaseStreamProvider } from './contexts/DatabaseStreamContext'
import { useShellBootstrap } from './api/queries/shellBootstrap'
import { getAuthToken, subscribeAuthChange } from './lib/authState'
import { AuthzProvider } from './authz'
import { useCommonTranslation, useErrorsTranslation, useLocaleState, useShellTranslation } from './i18n'
import {
  captureUiRouteTransition,
  recordUiUnhandledRejection,
  recordUiWindowError,
  setUiActionJournalEnabled,
} from './observability/uiActionJournal'
import { setUiIncidentTelemetryEnabled } from './observability/uiIncidentTelemetry'

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
const DecisionsPage = lazy(() => import('./pages/Decisions/DecisionsPage').then((m) => ({ default: m.DecisionsPage })))
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
const PoolBindingProfilesPage = lazy(() => import('./pages/Pools/PoolBindingProfilesPage').then((m) => ({ default: m.PoolBindingProfilesPage })))
const PoolFactualPage = lazy(() => import('./pages/Pools/PoolFactualPage').then((m) => ({ default: m.PoolFactualPage })))
const PoolMasterDataPage = lazy(() => import('./pages/Pools/PoolMasterDataPage').then((m) => ({ default: m.PoolMasterDataPage })))
const PoolSchemaTemplatesPage = lazy(() => import('./pages/Pools/PoolSchemaTemplatesPage').then((m) => ({ default: m.PoolSchemaTemplatesPage })))
const PoolTopologyTemplatesPage = lazy(() => import('./pages/Pools/PoolTopologyTemplatesPage').then((m) => ({ default: m.PoolTopologyTemplatesPage })))
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

function getShellBootstrapErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  return ''
}

function ShellBootstrapErrorState({ error }: { error: unknown }) {
  const { t: tCommon } = useCommonTranslation()
  const { t: tShell } = useShellTranslation()
  const fallbackMessage = tShell(($) => $.bootstrap.fallbackMessage)

  return (
    <Result
      status="error"
      title={tShell(($) => $.bootstrap.failedTitle)}
      subTitle={getShellBootstrapErrorMessage(error) || fallbackMessage}
      extra={(
        <Button type="primary" onClick={() => window.location.reload()}>
          {tCommon(($) => $.actions.retry)}
        </Button>
      )}
    />
  )
}

// Компонент для защиты маршрутов
const ProtectedRoute = ({ children, authToken }: { children: React.ReactNode, authToken: string | null }) => {
  const shellBootstrapQuery = useShellBootstrap({ enabled: Boolean(authToken) })

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (shellBootstrapQuery.isLoading) {
    return <RouteLoading />
  }

  if (shellBootstrapQuery.isError) {
    return <ShellBootstrapErrorState error={shellBootstrapQuery.error} />
  }

  return <>{children}</>
}

const StaffRoute = ({ children, authToken, preload }: { children: React.ReactNode, authToken: string | null, preload?: () => Promise<unknown> }) => {
  const shellBootstrapQuery = useShellBootstrap({ enabled: Boolean(authToken) })
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (shellBootstrapQuery.isLoading) {
    return <RouteLoading />
  }

  if (shellBootstrapQuery.isError) {
    return <ShellBootstrapErrorState error={shellBootstrapQuery.error} />
  }

  if (!shellBootstrapQuery.data?.me.is_staff) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

const RbacRoute = ({ children, authToken, preload }: { children: React.ReactNode, authToken: string | null, preload?: () => Promise<unknown> }) => {
  const shellBootstrapQuery = useShellBootstrap({ enabled: Boolean(authToken) })
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (shellBootstrapQuery.isLoading) {
    return <RouteLoading />
  }

  if (shellBootstrapQuery.isError) {
    return <ShellBootstrapErrorState error={shellBootstrapQuery.error} />
  }

  if (!shellBootstrapQuery.data?.capabilities.can_manage_rbac) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

const DriverCatalogsRoute = ({ children, authToken, preload }: { children: React.ReactNode, authToken: string | null, preload?: () => Promise<unknown> }) => {
  const shellBootstrapQuery = useShellBootstrap({ enabled: Boolean(authToken) })
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <Navigate to="/login" replace />
  }

  if (shellBootstrapQuery.isLoading) {
    return <RouteLoading />
  }

  if (shellBootstrapQuery.isError) {
    return <ShellBootstrapErrorState error={shellBootstrapQuery.error} />
  }

  if (!shellBootstrapQuery.data?.capabilities.can_manage_driver_catalogs) {
    return <Navigate to="/forbidden" replace />
  }

  return <>{children}</>
}

// Global API error handler component
// Must be inside AntApp to access notification API
function GlobalApiErrorHandler() {
  const { notification } = AntApp.useApp()
  const { t } = useErrorsTranslation()

  useEffect(() => {
    const handleApiError = (event: CustomEvent<ApiErrorDetail>) => {
      const { message, status, code, dedupeKey } = event.detail

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
        message: t(($) => $.notification.title),
        description: message,
        placement: 'topRight',
        duration: 5,
        key: dedupeKey || code || 'api-error',
      })
    }

    window.addEventListener(API_ERROR_EVENT, handleApiError as EventListener)

    return () => {
      window.removeEventListener(API_ERROR_EVENT, handleApiError as EventListener)
    }
  }, [notification, t])

  return null
}

function UiObservabilityBridge({ enabled }: { enabled: boolean }) {
  const location = useLocation()

  useEffect(() => {
    setUiActionJournalEnabled(enabled)
    setUiIncidentTelemetryEnabled(enabled)
  }, [enabled])

  useEffect(() => {
    if (!enabled) {
      return
    }

    captureUiRouteTransition(location)
  }, [enabled, location])

  useEffect(() => {
    if (!enabled) {
      return
    }

    const handleWindowError = (event: ErrorEvent) => {
      recordUiWindowError(event.error ?? event.message, { error_source: 'window.onerror' })
    }
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      recordUiUnhandledRejection(event.reason)
    }

    window.addEventListener('error', handleWindowError)
    window.addEventListener('unhandledrejection', handleUnhandledRejection)
    return () => {
      window.removeEventListener('error', handleWindowError)
      window.removeEventListener('unhandledrejection', handleUnhandledRejection)
    }
  }, [enabled])

  return null
}

function App() {
  const [authToken, setAuthToken] = useState(() => getAuthToken())
  const { antdLocale } = useLocaleState()
  // Enable real-time cache invalidation via WebSocket only for authenticated sessions
  useRealtimeInvalidation(Boolean(authToken))

  useEffect(() => {
    return subscribeAuthChange(() => {
      setAuthToken(getAuthToken())
    })
  }, [])

  return (
    <ErrorBoundary>
      <ConfigProvider
        locale={antdLocale}
        theme={{
          token: {
            colorPrimary: '#0b5bd3',
            colorError: '#b42318',
            colorTextSecondary: '#4b5563',
          },
          components: {
            Menu: {
              itemSelectedBg: '#dbeafe',
              itemSelectedColor: '#0b3d91',
            },
          },
        }}
      >
        <AntApp>
          <GlobalApiErrorHandler />
          <AuthzProvider key={authToken ?? 'guest'}>
            <DatabaseStreamProvider>
              <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <UiObservabilityBridge enabled={Boolean(authToken)} />
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
                  <Route path="/decisions" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><DecisionsPage /></LazyBoundary>
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
                  <Route path="/pools/topology-templates" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolTopologyTemplatesPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/pools/execution-packs" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolBindingProfilesPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/pools/master-data" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolMasterDataPage /></LazyBoundary>
                      </MainLayout>
                    </ProtectedRoute>
                  } />
                  <Route path="/pools/factual" element={
                    <ProtectedRoute authToken={authToken}>
                      <MainLayout>
                        <LazyBoundary><PoolFactualPage /></LazyBoundary>
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
