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

vi.mock('./api/queries/me', () => ({
  useMe: () => ({
    data: {
      is_staff: true,
      username: 'tester',
    },
    isLoading: false,
  }),
}))

vi.mock('./api/queries/rbac', () => ({
  useCanManageRbac: () => ({
    data: true,
    isLoading: false,
  }),
}))

vi.mock('./api/queries/commandSchemas', () => ({
  useCanManageDriverCatalogs: () => ({
    data: false,
    isLoading: false,
  }),
}))

vi.mock('./api/queries/tenants', () => ({
  useMyTenants: () => ({
    data: {
      active_tenant_id: 'tenant-1',
      tenants: [{ id: 'tenant-1', name: 'Default', slug: 'default', role: 'admin' }],
    },
    isFetching: false,
  }),
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
  PoolBindingProfilesPage: () => <div data-testid="pool-binding-profiles-route-page">Binding Profiles Route</div>,
}))

describe('App pools binding profiles route', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('auth_token', 'token')
    localStorage.setItem('active_tenant_id', 'tenant-1')
    window.history.pushState({}, '', '/pools/binding-profiles')
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
    expect(screen.getByText('Pool Binding Profiles')).toBeInTheDocument()
  })
})
