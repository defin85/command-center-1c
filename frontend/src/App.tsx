import { useEffect, Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { Button, ConfigProvider, App as AntApp, Result, Spin } from 'antd'
import { MainLayout } from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { API_ERROR_EVENT } from './api/client'
import type { ApiErrorDetail } from './api/apiErrorPolicy'
import { useRealtimeInvalidation } from './hooks/useRealtimeInvalidation'
import { DatabaseStreamProvider } from './contexts/DatabaseStreamContext'
import { buildLoginRedirectPath } from './lib/authRedirect'
import { AuthzProvider } from './authz'
import { useCommonTranslation, useErrorsTranslation, useLocaleState, useShellTranslation } from './i18n'
import { useShellRuntime } from './shell/ShellRuntimeProvider'
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

function LoginRedirect() {
  const location = useLocation()

  return (
    <Navigate
      to={buildLoginRedirectPath(location)}
      replace
      state={{ from: location }}
    />
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

const ProtectedRoute = () => {
  const { authToken, shellBootstrapQuery } = useShellRuntime()

  if (!authToken) {
    return <LoginRedirect />
  }

  if (shellBootstrapQuery.isLoading) {
    return <RouteLoading />
  }

  if (shellBootstrapQuery.isError) {
    return <ShellBootstrapErrorState error={shellBootstrapQuery.error} />
  }

  return <Outlet />
}

const StaffRoute = ({ preload }: { preload?: () => Promise<unknown> }) => {
  const { authToken, shellBootstrapQuery } = useShellRuntime()
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <LoginRedirect />
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

  return <Outlet />
}

const RbacRoute = ({ preload }: { preload?: () => Promise<unknown> }) => {
  const { authToken, shellBootstrapQuery } = useShellRuntime()
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <LoginRedirect />
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

  return <Outlet />
}

const DriverCatalogsRoute = ({ preload }: { preload?: () => Promise<unknown> }) => {
  const { authToken, shellBootstrapQuery } = useShellRuntime()
  useEffect(() => {
    if (!authToken) return
    void preload?.()
  }, [authToken, preload])

  if (!authToken) {
    return <LoginRedirect />
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

  return <Outlet />
}

const SharedShellRoute = () => {
  const location = useLocation()

  return (
    <MainLayout>
      <Suspense key={location.pathname} fallback={<RouteLoading />}>
        <Outlet />
      </Suspense>
    </MainLayout>
  )
}

const NoShellRouteBoundary = () => {
  const location = useLocation()

  return (
    <Suspense key={location.pathname} fallback={<RouteLoading />}>
      <Outlet />
    </Suspense>
  )
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

function AppRouteTree() {
  return (
    <Routes>
      <Route path="/login" element={<LazyBoundary><Login /></LazyBoundary>} />
      <Route path="/forbidden" element={<LazyBoundary><ForbiddenPage /></LazyBoundary>} />
      <Route path="/installation-monitor" element={<Navigate to="/operations?tab=list" replace />} />
      <Route path="/operation-monitor" element={<Navigate to="/operations?tab=monitor" replace />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<SharedShellRoute />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="clusters" element={<Clusters />} />
          <Route path="operations" element={<Operations />} />
          <Route path="artifacts" element={<ArtifactsPage />} />
          <Route path="databases" element={<Databases />} />
          <Route path="extensions" element={<Extensions />} />
          <Route path="system-status" element={<SystemStatus />} />
          <Route path="workflows" element={<WorkflowList />} />
          <Route path="workflows/executions" element={<WorkflowExecutions />} />
          <Route path="templates" element={<TemplatesPage />} />
          <Route path="decisions" element={<DecisionsPage />} />
          <Route path="pools/templates" element={<PoolSchemaTemplatesPage />} />
          <Route path="pools/catalog" element={<PoolCatalogPage />} />
          <Route path="pools/topology-templates" element={<PoolTopologyTemplatesPage />} />
          <Route path="pools/execution-packs" element={<PoolBindingProfilesPage />} />
          <Route path="pools/master-data" element={<PoolMasterDataPage />} />
          <Route path="pools/factual" element={<PoolFactualPage />} />
          <Route path="pools/runs" element={<PoolRunsPage />} />
          <Route path="service-mesh" element={<ServiceMeshPage />} />
          <Route element={<RbacRoute preload={loadRBACPage} />}>
            <Route path="rbac" element={<RBACPage />} />
          </Route>
          <Route element={<StaffRoute preload={loadUsersPage} />}>
            <Route path="users" element={<UsersPage />} />
          </Route>
          <Route element={<StaffRoute preload={loadDLQPage} />}>
            <Route path="dlq" element={<DLQPage />} />
          </Route>
          <Route element={<StaffRoute preload={loadRuntimeSettingsPage} />}>
            <Route path="settings/runtime" element={<RuntimeSettingsPage />} />
          </Route>
          <Route element={<DriverCatalogsRoute preload={loadCommandSchemasPage} />}>
            <Route path="settings/command-schemas" element={<CommandSchemasPage />} />
          </Route>
          <Route element={<StaffRoute preload={loadTimelineSettingsPage} />}>
            <Route path="settings/timeline" element={<TimelineSettingsPage />} />
          </Route>
        </Route>
        <Route element={<NoShellRouteBoundary />}>
          <Route path="workflows/new" element={<WorkflowDesigner />} />
          <Route path="workflows/:id" element={<WorkflowDesigner />} />
          <Route path="workflows/executions/:executionId" element={<WorkflowMonitor />} />
          <Route element={<DriverCatalogsRoute preload={loadCommandSchemasPage} />}>
            <Route path="settings/driver-catalogs" element={<Navigate to="/settings/command-schemas?mode=raw" replace />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}

function App() {
  const { authToken } = useShellRuntime()
  const { antdLocale } = useLocaleState()
  // Enable real-time cache invalidation via WebSocket only for authenticated sessions
  useRealtimeInvalidation(Boolean(authToken))

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
              <BrowserRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
                <UiObservabilityBridge enabled={Boolean(authToken)} />
                <AppRouteTree />
              </BrowserRouter>
            </DatabaseStreamProvider>
          </AuthzProvider>
        </AntApp>
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
