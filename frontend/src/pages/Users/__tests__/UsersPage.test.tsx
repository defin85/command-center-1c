import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'

import { UsersPage } from '../UsersPage'

const {
  mockUseUsers,
  mockUseUser,
  mockUpdateUserMutate,
  mockConfirmWithTracking,
} = vi.hoisted(() => ({
  mockUseUsers: vi.fn(),
  mockUseUser: vi.fn(),
  mockUpdateUserMutate: vi.fn(),
  mockConfirmWithTracking: vi.fn((_: unknown, config: { onOk?: () => unknown }) => config.onOk?.()),
}))

const buildUser = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  username: 'alice',
  email: 'alice@example.com',
  first_name: 'Alice',
  last_name: 'Operator',
  is_staff: true,
  is_active: true,
  last_login: '2026-04-01T10:00:00Z',
  date_joined: '2026-03-01T10:00:00Z',
  ...overrides,
})

vi.mock('../../../api/queries', () => ({
  useUsers: mockUseUsers,
  useUser: mockUseUser,
  useCreateUser: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useUpdateUser: () => ({
    mutate: mockUpdateUserMutate,
    isPending: false,
  }),
  useSetUserPassword: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => ({
    isStaff: true,
  }),
}))

vi.mock('../../../observability/confirmWithTracking', () => ({
  confirmWithTracking: mockConfirmWithTracking,
}))

vi.mock('../../../components/table/hooks/useTableToolkit', () => ({
  useTableToolkit: () => ({
    pagination: { page: 1, pageSize: 50 },
    search: '',
    filters: {},
    totalColumnsWidth: 960,
  }),
}))

vi.mock('../../../components/table/TableToolkit', () => ({
  TableToolkit: ({
    data,
    columns,
  }: {
    data: Array<Record<string, unknown>>
    columns: Array<{
      key?: string
      render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
    }>
  }) => {
    const actionsColumn = columns.find((column) => column.key === 'actions')

    return (
      <div data-testid="users-table">
        {data.map((user, index) => (
          <div key={String(user.id)} data-testid={`users-row-actions-${String(user.id)}`}>
            {actionsColumn?.render?.(null, user, index) ?? null}
          </div>
        ))}
      </div>
    )
  },
}))

vi.mock('../../../components/platform', () => ({
  WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
    <div>
      {header}
      {children}
    </div>
  ),
  PageHeader: ({ title, actions }: { title: ReactNode; actions?: ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {actions}
    </div>
  ),
  EntityDetails: ({
    title,
    extra,
    children,
    empty,
  }: {
    title: ReactNode
    extra?: ReactNode
    children?: ReactNode
    empty?: boolean
  }) => (
    <div data-testid="users-details">
      <div>{title}</div>
      <div data-testid="users-detail-extra">{extra}</div>
      {empty ? null : children}
    </div>
  ),
  ModalFormShell: ({
    open,
    children,
  }: {
    open: boolean
    children: ReactNode
  }) => (
    open ? <div>{children}</div> : null
  ),
}))

function renderUsersPage(initialEntry = '/users') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AntApp>
        <Routes>
          <Route path="/users" element={<UsersPage />} />
        </Routes>
      </AntApp>
    </MemoryRouter>
  )
}

describe('UsersPage observability', () => {
  beforeEach(() => {
    mockConfirmWithTracking.mockClear()
    mockUpdateUserMutate.mockReset()
    mockUseUsers.mockReturnValue({
      data: {
        users: [buildUser()],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      refetch: vi.fn(),
    })
    mockUseUser.mockReturnValue({
      data: buildUser(),
      isLoading: false,
    })
  })

  it('tracks list-level activate/deactivate actions through confirmWithTracking', async () => {
    const user = userEvent.setup()

    renderUsersPage('/users')

    await user.click(
      within(screen.getByTestId('users-row-actions-1')).getByRole('button', { name: 'Deactivate' })
    )

    expect(mockConfirmWithTracking).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        title: 'Deactivate user?',
        okText: 'Deactivate',
      }),
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Deactivate user',
        context: {
          user_id: 1,
          next_is_active: false,
        },
      }),
    )
    expect(mockUpdateUserMutate).toHaveBeenCalledWith({ id: 1, is_active: false })
  })

  it('tracks detail-level activate/deactivate actions through confirmWithTracking', async () => {
    const user = userEvent.setup()

    renderUsersPage('/users?user=1&context=inspect')

    await user.click(
      within(screen.getByTestId('users-detail-extra')).getByRole('button', { name: 'Deactivate' })
    )

    expect(mockConfirmWithTracking).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        title: 'Deactivate user?',
      }),
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Deactivate user',
        context: {
          user_id: 1,
          next_is_active: false,
        },
      }),
    )
    expect(mockUpdateUserMutate).toHaveBeenCalledWith({ id: 1, is_active: false })
  })
})
