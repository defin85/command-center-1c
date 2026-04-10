import { App as AntApp } from 'antd'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const {
  mockGetRuntimeSettings,
  mockUpdateRuntimeSetting,
  mockTrackUiAction,
  mockUseAuthz,
} = vi.hoisted(() => ({
  mockGetRuntimeSettings: vi.fn(),
  mockUpdateRuntimeSetting: vi.fn(),
  mockTrackUiAction: vi.fn((_: unknown, handler?: () => unknown) => handler?.()),
  mockUseAuthz: vi.fn(() => ({
    isStaff: true,
    canManageRuntimeControls: true,
  })),
}))

vi.mock('../../../api/runtimeSettings', () => ({
  getRuntimeSettings: mockGetRuntimeSettings,
  updateRuntimeSetting: mockUpdateRuntimeSetting,
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: (...args: unknown[]) => mockUseAuthz(...args),
}))

vi.mock('../../../observability/uiActionJournal', () => ({
  trackUiAction: mockTrackUiAction,
}))

vi.mock('../../../components/table/hooks/useTableToolkit', () => ({
  useTableToolkit: () => ({
    search: '',
    filters: {},
    filtersPayload: {},
    sort: {},
    sortPayload: undefined,
    pagination: {
      page: 1,
      pageSize: 50,
    },
    totalColumnsWidth: 960,
  }),
}))

vi.mock('../../../components/table/TableToolkit', () => ({
  TableToolkit: () => <div data-testid="runtime-settings-table" />,
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
  DrawerSurfaceShell: ({
    open,
    extra,
    children,
    title,
  }: {
    open: boolean
    extra?: ReactNode
    children: ReactNode
    title?: ReactNode
  }) => (
    open ? (
      <div>
        <div>{title}</div>
        <div data-testid="runtime-settings-drawer-extra">{extra}</div>
        {children}
      </div>
    ) : null
  ),
}))

import { RuntimeSettingsPage } from '../RuntimeSettingsPage'

describe('RuntimeSettingsPage observability', () => {
  beforeEach(() => {
    mockGetRuntimeSettings.mockReset()
    mockUpdateRuntimeSetting.mockReset()
    mockTrackUiAction.mockClear()
    mockUseAuthz.mockReset()
    mockUseAuthz.mockReturnValue({
      isStaff: true,
      canManageRuntimeControls: true,
    })
  })

  it('tracks save actions for the selected runtime setting drawer', async () => {
    const user = userEvent.setup()

    mockGetRuntimeSettings.mockResolvedValue([{
      key: 'operations.feature_enabled',
      value: true,
      value_type: 'bool',
      description: 'Enable the operation',
      default: false,
      min_value: null,
      max_value: null,
    }])
    mockUpdateRuntimeSetting.mockResolvedValue({
      key: 'operations.feature_enabled',
      value: false,
      value_type: 'bool',
      description: 'Enable the operation',
      default: false,
    })

    render(
      <MemoryRouter initialEntries={['/settings/runtime?setting=operations.feature_enabled&context=setting']}>
        <AntApp>
          <Routes>
            <Route path="/settings/runtime" element={<RuntimeSettingsPage />} />
          </Routes>
        </AntApp>
      </MemoryRouter>,
    )

    await screen.findByText('operations.feature_enabled')
    await user.click(screen.getByRole('switch'))

    const saveButton = screen.getByRole('button', { name: 'Save' })
    expect(saveButton).toBeEnabled()

    await user.click(saveButton)

    await waitFor(() => {
      expect(mockTrackUiAction).toHaveBeenCalledWith(
        expect.objectContaining({
          actionKind: 'drawer.submit',
          actionName: 'Save runtime setting',
          context: {
            setting: 'operations.feature_enabled',
            manual_operation: 'settings.runtime.update',
          },
        }),
        expect.any(Function),
      )
    })
    expect(mockUpdateRuntimeSetting).toHaveBeenCalledWith('operations.feature_enabled', false)
  })

  it('keeps runtime-control keys read-only without runtime-control capability', async () => {
    mockUseAuthz.mockReturnValue({
      isStaff: true,
      canManageRuntimeControls: false,
    })
    mockGetRuntimeSettings.mockResolvedValue([{
      key: 'runtime.scheduler.enabled',
      value: true,
      value_type: 'bool',
      description: 'Enable scheduler control plane.',
      default: true,
      min_value: null,
      max_value: null,
    }])

    render(
      <MemoryRouter initialEntries={['/settings/runtime?setting=runtime.scheduler.enabled&context=setting']}>
        <AntApp>
          <Routes>
            <Route path="/settings/runtime" element={<RuntimeSettingsPage />} />
          </Routes>
        </AntApp>
      </MemoryRouter>,
    )

    await screen.findByText('runtime.scheduler.enabled')
    expect(screen.getByText('Runtime-control keys остаются read-only без отдельной runtime-control capability.')).toBeInTheDocument()
    expect(screen.getByText('Эта настройка требует runtime-control capability для изменения.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })
})
