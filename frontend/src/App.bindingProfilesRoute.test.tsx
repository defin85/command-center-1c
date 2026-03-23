import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './App'

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
  getAuthToken: () => 'token',
  subscribeAuthChange: () => () => undefined,
  notifyAuthChanged: vi.fn(),
}))

vi.mock('./pages/Pools/PoolBindingProfilesPage', () => ({
  PoolBindingProfilesPage: () => <div data-testid="pool-binding-profiles-route-page">Execution Packs Route</div>,
}))

describe('App pools binding profiles route', () => {
  beforeEach(() => {
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
        },
      },
      isLoading: false,
      isFetching: false,
      isError: false,
    })
    localStorage.clear()
    localStorage.setItem('auth_token', 'token')
    localStorage.setItem('active_tenant_id', 'tenant-1')
    window.history.pushState({}, '', '/pools/execution-packs')
  })

  it('mounts the dedicated route and exposes it in the main navigation', async () => {
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

    expect(await screen.findByTestId('pool-binding-profiles-route-page')).toBeInTheDocument()
    expect(screen.getByText('Pool Execution Packs')).toBeInTheDocument()
  })

  it('labels the tenant selector when multiple tenants are available', async () => {
    mockUseShellBootstrap.mockReturnValue({
      data: {
        me: {
          is_staff: true,
          username: 'tester',
        },
        tenant_context: {
          active_tenant_id: 'tenant-1',
          tenants: [
            { id: 'tenant-1', name: 'Default', slug: 'default', role: 'admin' },
            { id: 'tenant-2', name: 'Finance', slug: 'finance', role: 'admin' },
          ],
        },
        access: {
          clusters: [],
          databases: [],
          operation_templates: [],
        },
        capabilities: {
          can_manage_rbac: true,
          can_manage_driver_catalogs: false,
        },
      },
      isLoading: false,
      isFetching: false,
      isError: false,
    })

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

    expect(await screen.findByTestId('pool-binding-profiles-route-page')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Active tenant' })).toBeInTheDocument()
  })

  it('shows a stable shell error state when bootstrap fails', async () => {
    mockUseShellBootstrap.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: new Error('bootstrap unavailable'),
    })

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

    expect(await screen.findByText('Shell bootstrap failed')).toBeInTheDocument()
    expect(screen.queryByTestId('pool-binding-profiles-route-page')).not.toBeInTheDocument()
  })
})
