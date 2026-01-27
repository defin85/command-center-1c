import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { RBACPage } from '../RBACPage'

let mockIsStaff = true

function makeQuery<TData>(data: TData) {
  return {
    data,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }
}

function makeMutation() {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }
}

vi.mock('../../../api/queries/me', () => ({
  useMe: () => makeQuery({ id: 1, username: 'u1', is_staff: mockIsStaff }),
}))

vi.mock('../../../api/queries/rbac', () => ({
  useCanManageRbac: () => makeQuery(true),
  useCapabilities: () => makeQuery({ capabilities: [] }),
  useClusterPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useClusterGroupPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useEffectiveAccess: () => makeQuery({ items: [], total: 0 }),
  useBulkGrantClusterGroupPermission: () => makeMutation(),
  useBulkRevokeClusterGroupPermission: () => makeMutation(),
  useCreateRole: () => makeMutation(),
  useDeleteRole: () => makeMutation(),
  useDatabasePermissions: () => makeQuery({ permissions: [], total: 0 }),
  useDatabaseGroupPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useBulkGrantDatabaseGroupPermission: () => makeMutation(),
  useBulkRevokeDatabaseGroupPermission: () => makeMutation(),
  useGrantClusterPermission: () => makeMutation(),
  useGrantClusterGroupPermission: () => makeMutation(),
  useGrantDatabasePermission: () => makeMutation(),
  useGrantDatabaseGroupPermission: () => makeMutation(),
  useGrantOperationTemplateGroupPermission: () => makeMutation(),
  useGrantOperationTemplatePermission: () => makeMutation(),
  useGrantWorkflowTemplateGroupPermission: () => makeMutation(),
  useGrantWorkflowTemplatePermission: () => makeMutation(),
  useGrantArtifactGroupPermission: () => makeMutation(),
  useGrantArtifactPermission: () => makeMutation(),
  useOperationTemplateGroupPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useOperationTemplatePermissions: () => makeQuery({ permissions: [], total: 0 }),
  useWorkflowTemplateGroupPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useWorkflowTemplatePermissions: () => makeQuery({ permissions: [], total: 0 }),
  useArtifactGroupPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useArtifactPermissions: () => makeQuery({ permissions: [], total: 0 }),
  useRbacRefClusters: () => makeQuery({ clusters: [] }),
  useRbacRefDatabases: () => makeQuery({ databases: [] }),
  useRbacRefOperationTemplates: () => makeQuery({ templates: [] }),
  useRbacRefWorkflowTemplates: () => makeQuery({ templates: [] }),
  useRbacRefArtifacts: () => makeQuery({ artifacts: [] }),
  useRevokeClusterPermission: () => makeMutation(),
  useRevokeClusterGroupPermission: () => makeMutation(),
  useRevokeDatabasePermission: () => makeMutation(),
  useRevokeDatabaseGroupPermission: () => makeMutation(),
  useRevokeOperationTemplateGroupPermission: () => makeMutation(),
  useRevokeOperationTemplatePermission: () => makeMutation(),
  useRevokeWorkflowTemplateGroupPermission: () => makeMutation(),
  useRevokeWorkflowTemplatePermission: () => makeMutation(),
  useRevokeArtifactGroupPermission: () => makeMutation(),
  useRevokeArtifactPermission: () => makeMutation(),
  useRbacUsers: () => makeQuery({ users: [] }),
  useRbacUsersWithRoles: () => makeQuery({ users: [], total: 0 }),
  useRoles: () => makeQuery({ roles: [] }),
  useSetRoleCapabilities: () => makeMutation(),
  useSetUserRoles: () => makeMutation(),
  useUpdateRole: () => makeMutation(),
}))

vi.mock('../../../api/queries/databases', () => ({
  useInfobaseUsers: () => makeQuery({ users: [], count: 0, total: 0 }),
  useCreateInfobaseUser: () => makeMutation(),
  useUpdateInfobaseUser: () => makeMutation(),
  useDeleteInfobaseUser: () => makeMutation(),
  useSetInfobaseUserPassword: () => makeMutation(),
  useResetInfobaseUserPassword: () => makeMutation(),
  useDbmsUsers: () => makeQuery({ users: [], count: 0, total: 0 }),
  useCreateDbmsUser: () => makeMutation(),
  useUpdateDbmsUser: () => makeMutation(),
  useDeleteDbmsUser: () => makeMutation(),
  useSetDbmsUserPassword: () => makeMutation(),
  useResetDbmsUserPassword: () => makeMutation(),
}))

vi.mock('../../../api/queries', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../../api/queries')
  return {
    ...actual,
    useTableMetadata: () => makeQuery({ columns: [] }),
  }
})

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AntApp>
        <RBACPage />
      </AntApp>
    </QueryClientProvider>
  )
}

describe('RBACPage: DBMS users tab', () => {
  beforeEach(() => {
    localStorage.setItem('auth_token', 'test-token')
  })

  it('shows DBMS users tab for staff users', async () => {
    mockIsStaff = true

    renderPage()

    const tabLabel = screen.getByTestId('rbac-tab-dbms-users')
    const tab = tabLabel.closest('[role="tab"]') ?? tabLabel
    fireEvent.click(tab)
    expect(await screen.findByTestId('rbac-dbms-users-toolbar-database')).toBeInTheDocument()
  })

  it('hides DBMS users tab for non-staff users', () => {
    mockIsStaff = false

    renderPage()

    expect(screen.queryByTestId('rbac-tab-dbms-users')).toBeNull()
  })
})
