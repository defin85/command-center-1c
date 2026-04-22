import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const {
  authListeners,
  mockCaptureUiRouteTransition,
  mockRecordUiErrorBoundary,
  mockRecordUiUnhandledRejection,
  mockRecordUiWindowError,
  mockSetUiActionJournalEnabled,
  mockSubscribeToUiActionJournal,
  mockAxiosPost,
} = vi.hoisted(() => ({
  authListeners: new Set<() => void>(),
  mockCaptureUiRouteTransition: vi.fn(),
  mockRecordUiErrorBoundary: vi.fn(),
  mockRecordUiUnhandledRejection: vi.fn(),
  mockRecordUiWindowError: vi.fn(),
  mockSetUiActionJournalEnabled: vi.fn(),
  mockSubscribeToUiActionJournal: vi.fn(() => () => undefined),
  mockAxiosPost: vi.fn(),
}))

import App from './App'

vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof import('axios')>('axios')
  const mockClient = {
    defaults: {
      headers: {
        common: {},
      },
    },
    interceptors: {
      request: {
        use: vi.fn(),
      },
      response: {
        use: vi.fn(),
      },
    },
  }

  return {
    ...actual,
    default: {
      ...actual.default,
      post: mockAxiosPost,
      create: vi.fn(() => mockClient),
    },
    post: mockAxiosPost,
  }
})

vi.mock('./hooks/useRealtimeInvalidation', () => ({
  useRealtimeInvalidation: vi.fn(),
}))

vi.mock('./contexts/DatabaseStreamContext', () => ({
  DatabaseStreamProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useDatabaseStreamStatus: () => ({
    isConnected: false,
    isConnecting: false,
    error: null,
    cooldownSeconds: 0,
    reconnect: vi.fn(),
  }),
}))

vi.mock('./authz', () => ({
  AuthzProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('./observability/uiActionJournal', () => ({
  captureUiRouteTransition: mockCaptureUiRouteTransition,
  recordUiErrorBoundary: mockRecordUiErrorBoundary,
  recordUiUnhandledRejection: mockRecordUiUnhandledRejection,
  recordUiWindowError: mockRecordUiWindowError,
  setUiActionJournalEnabled: mockSetUiActionJournalEnabled,
  subscribeToUiActionJournal: mockSubscribeToUiActionJournal,
}))

const mockUseShellBootstrap = vi.fn()

vi.mock('./api/queries/shellBootstrap', () => ({
  useShellBootstrap: (...args: unknown[]) => mockUseShellBootstrap(...args),
}))

vi.mock('./api/queries/tenants', () => ({
  useSetActiveTenant: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

vi.mock('./lib/authState', () => ({
  getAuthToken: () => localStorage.getItem('auth_token'),
  subscribeAuthChange: (callback: () => void) => {
    authListeners.add(callback)
    return () => authListeners.delete(callback)
  },
  notifyAuthChanged: () => {
    authListeners.forEach((callback) => callback())
  },
}))

vi.mock('./pages/Dashboard/Dashboard', () => ({
  Dashboard: () => <div data-testid="dashboard-route-page">Dashboard Route</div>,
}))

vi.mock('./pages/Pools/PoolMasterDataPage', () => ({
  PoolMasterDataPage: () => <div data-testid="pool-master-data-route-page">Pool Master Data Route</div>,
}))

describe('App auth redirect restore', () => {
  beforeEach(() => {
    authListeners.clear()
    mockAxiosPost.mockReset()
    mockCaptureUiRouteTransition.mockReset()
    mockRecordUiErrorBoundary.mockReset()
    mockRecordUiUnhandledRejection.mockReset()
    mockRecordUiWindowError.mockReset()
    mockSetUiActionJournalEnabled.mockReset()
    mockSubscribeToUiActionJournal.mockReset()
    mockSubscribeToUiActionJournal.mockReturnValue(() => undefined)
    mockUseShellBootstrap.mockReset()
    mockUseShellBootstrap.mockReturnValue({
      data: {
        me: {
          is_staff: true,
          username: 'tester',
        },
        tenant_context: {
          active_tenant_id: 'tenant-1',
          tenants: [{ id: 'tenant-1', name: 'Default', slug: 'default', role: 'admin' }],
        },
        access: {
          clusters: [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: true,
          can_manage_driver_catalogs: false,
          can_manage_runtime_controls: false,
        },
      },
      isLoading: false,
      isFetching: false,
      isError: false,
    })
    mockAxiosPost.mockResolvedValue({
      data: {
        access: 'access-token',
        refresh: 'refresh-token',
      },
    })

    localStorage.clear()
    window.history.pushState({}, '', '/pools/master-data?tab=bindings&detail=1')
  })

  it('restores the original protected route after successful login', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <AntApp>
          <App />
        </AntApp>
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(window.location.pathname).toBe('/login')
    })
    expect(new URLSearchParams(window.location.search).get('next')).toBe('/pools/master-data?tab=bindings&detail=1')

    await screen.findByRole('button', { name: 'Войти' })

    fireEvent.change(screen.getByLabelText('Имя пользователя'), {
      target: { value: 'admin' },
    })
    fireEvent.change(screen.getByLabelText('Пароль'), {
      target: { value: 'p-123456' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByTestId('pool-master-data-route-page')).toBeInTheDocument()
    expect(window.location.pathname + window.location.search).toBe('/pools/master-data?tab=bindings&detail=1')
    expect(localStorage.getItem('auth_token')).toBe('access-token')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-token')
    expect(mockAxiosPost).toHaveBeenCalledTimes(1)
  })
})
