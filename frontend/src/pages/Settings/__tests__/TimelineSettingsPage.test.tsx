import { App as AntApp } from 'antd'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { changeLanguage } from '@/i18n/runtime'

const {
  mockGetRuntimeSettings,
  mockGetStreamMuxStatus,
  mockUseAuthz,
} = vi.hoisted(() => ({
  mockGetRuntimeSettings: vi.fn(),
  mockGetStreamMuxStatus: vi.fn(),
  mockUseAuthz: vi.fn(() => ({
    isStaff: true,
  })),
}))

vi.mock('../../../api/runtimeSettings', () => ({
  getRuntimeSettings: mockGetRuntimeSettings,
  updateRuntimeSetting: vi.fn(),
}))

vi.mock('../../../api/operations', () => ({
  getStreamMuxStatus: mockGetStreamMuxStatus,
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => mockUseAuthz(),
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
  TableToolkit: ({ searchPlaceholder }: { searchPlaceholder?: string }) => (
    <div data-testid="timeline-settings-table">{searchPlaceholder}</div>
  ),
}))

vi.mock('../../../components/platform', () => ({
  WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
    <div>
      {header}
      {children}
    </div>
  ),
  PageHeader: ({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
      {actions}
    </div>
  ),
  DrawerSurfaceShell: ({
    open,
    title,
    subtitle,
    extra,
    children,
  }: {
    open: boolean
    title?: ReactNode
    subtitle?: ReactNode
    extra?: ReactNode
    children: ReactNode
  }) => (
    open ? (
      <div>
        <h3>{title}</h3>
        {subtitle ? <p>{subtitle}</p> : null}
        <div>{extra}</div>
        {children}
      </div>
    ) : null
  ),
}))

import { TimelineSettingsPage } from '../TimelineSettingsPage'

describe('TimelineSettingsPage i18n', () => {
  beforeEach(async () => {
    await changeLanguage('ru')
    mockUseAuthz.mockReset()
    mockUseAuthz.mockReturnValue({
      isStaff: true,
    })
    mockGetRuntimeSettings.mockReset()
    mockGetStreamMuxStatus.mockReset()
    mockGetRuntimeSettings.mockResolvedValue([{
      key: 'observability.timeline.max_events',
      value: 500,
      value_type: 'int',
      description: 'Maximum buffered events.',
      default: 250,
      min_value: 100,
      max_value: 1000,
    }])
    mockGetStreamMuxStatus.mockResolvedValue({
      active_streams: 2,
      max_streams: 5,
      active_subscriptions: 3,
      max_subscriptions: 10,
    })
  })

  it('renders localized timeline page chrome and diagnostics drawer copy', async () => {
    render(
      <MemoryRouter initialEntries={['/settings/timeline?context=diagnostics']}>
        <AntApp>
          <Routes>
            <Route path="/settings/timeline" element={<TimelineSettingsPage />} />
          </Routes>
        </AntApp>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Настройки timeline' })).toBeInTheDocument()
    expect(
      screen.getByText('Рабочее место настроек timeline с secondary diagnostics/remediation внутри того же platform shell.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Диагностика' })).toBeInTheDocument()
    expect(screen.getByTestId('timeline-settings-table')).toHaveTextContent('Поиск по настройкам timeline')

    expect(await screen.findByRole('heading', { name: 'Диагностика timeline' })).toBeInTheDocument()
    expect(
      screen.getByText('Runtime controls остаются primary path, а diagnostics/remediation живут в том же workspace shell.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Пересоздать очередь' })).toBeInTheDocument()
    expect(await screen.findByText('Активные mux streams: 2/5')).toBeInTheDocument()
    expect(screen.getByText('Активные подписки: 3/10')).toBeInTheDocument()
  })
})
