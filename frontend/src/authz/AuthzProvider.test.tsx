import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { AuthzProvider } from './AuthzProvider'
import { useAuthz } from './useAuthz'

const mockUseShellBootstrap = vi.fn()

vi.mock('../api/queries/shellBootstrap', () => ({
  useShellBootstrap: (...args: unknown[]) => mockUseShellBootstrap(...args),
}))

function AuthzProbe() {
  const authz = useAuthz()

  return (
    <div data-testid="authz-summary">
      {[
        authz.isLoading ? 'loading' : 'ready',
        authz.isStaff ? 'staff' : 'nonstaff',
        authz.getDatabaseLevel('db-1') ?? 'none',
        authz.getClusterLevel('cluster-1') ?? 'none',
        authz.getTemplateLevel('template-1') ?? 'none',
        String(authz.canDatabase('db-1', 'VIEW')),
        String(authz.canAnyTemplate('VIEW')),
      ].join('|')}
    </div>
  )
}

describe('AuthzProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('auth_token', 'token')
    mockUseShellBootstrap.mockReset()
  })

  it('derives access levels from shell bootstrap access summary', () => {
    mockUseShellBootstrap.mockReturnValue({
      data: {
        me: {
          id: 7,
          username: 'operator',
          is_staff: false,
        },
        tenant_context: {
          active_tenant_id: 'tenant-1',
          tenants: [{ id: 'tenant-1', name: 'Default', slug: 'default', role: 'admin' }],
        },
        access: {
          user: {
            id: 7,
            username: 'operator',
          },
          clusters: [{
            cluster: { id: 'cluster-1', name: 'Cluster 1' },
            level: 'VIEW',
            sources: [],
          }],
          databases: [{
            database: { id: 'db-1', name: 'Database 1', cluster_id: 'cluster-1' },
            level: 'MANAGE',
            source: 'direct',
            via_cluster_id: null,
            sources: [],
          }],
          operation_templates: [{
            template: { id: 'template-1', name: 'Template 1' },
            level: 'OPERATE',
            source: 'direct',
            sources: [],
          }],
          workflow_templates: [],
          artifacts: [],
        },
        capabilities: {
          can_manage_rbac: false,
          can_manage_driver_catalogs: false,
          can_manage_runtime_controls: false,
        },
      },
      isLoading: false,
    })

    render(
      <AuthzProvider>
        <AuthzProbe />
      </AuthzProvider>
    )

    expect(screen.getByTestId('authz-summary')).toHaveTextContent(
      'ready|nonstaff|MANAGE|VIEW|OPERATE|true|true'
    )
  })
})
