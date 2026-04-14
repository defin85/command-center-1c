import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { changeLanguage } from '@/i18n/runtime'

const {
  mockUseClusters,
  mockUseDatabases,
  mockUseExtensionsOverview,
  mockUseExtensionsOverviewDatabases,
  mockUseManualOperationBindings,
  mockUpsertBindingMutateAsync,
  mockDeleteBindingMutateAsync,
} = vi.hoisted(() => ({
  mockUseClusters: vi.fn(),
  mockUseDatabases: vi.fn(),
  mockUseExtensionsOverview: vi.fn(),
  mockUseExtensionsOverviewDatabases: vi.fn(),
  mockUseManualOperationBindings: vi.fn(),
  mockUpsertBindingMutateAsync: vi.fn(),
  mockDeleteBindingMutateAsync: vi.fn(),
}))

vi.mock('../../../api/queries/clusters', () => ({
  useClusters: mockUseClusters,
}))

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: mockUseDatabases,
}))

vi.mock('../../../api/queries/extensions', () => ({
  useExtensionsOverview: mockUseExtensionsOverview,
  useExtensionsOverviewDatabases: mockUseExtensionsOverviewDatabases,
}))

vi.mock('../../../api/queries/extensionsManualOperations', () => ({
  useManualOperationBindings: mockUseManualOperationBindings,
  useUpsertManualOperationBinding: () => ({
    mutateAsync: mockUpsertBindingMutateAsync,
    isPending: false,
  }),
  useDeleteManualOperationBinding: () => ({
    mutateAsync: mockDeleteBindingMutateAsync,
    isPending: false,
  }),
}))

vi.mock('../../../api/generated', () => ({
  getV2: () => ({
    postExtensionsFlagsPolicyAdopt: vi.fn(),
    getExtensionsOverviewDatabases: vi.fn(),
    postExtensionsPlan: vi.fn(),
    postExtensionsApply: vi.fn(),
  }),
}))

vi.mock('../../../api/operationCatalog', () => ({
  listOperationCatalogExposures: vi.fn(),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => ({
    isStaff: false,
  }),
}))

vi.mock('../../../observability/confirmWithTracking', () => ({
  confirmWithTracking: vi.fn(),
}))

vi.mock('../../../components/ibcmd/ibcmdCliUiErrors', () => ({
  tryShowIbcmdCliUiError: () => false,
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
    title,
    open,
    children,
  }: {
    title: ReactNode
    open: boolean
    children: ReactNode
  }) => (
    open ? (
      <div>
        <h3>{title}</h3>
        {children}
      </div>
    ) : null
  ),
}))

vi.mock('../ExtensionsTables', () => ({
  ExtensionsOverviewTable: ({
    columns,
  }: {
    columns: Array<{ title?: ReactNode }>
  }) => (
    <div data-testid="extensions-overview-columns">
      {columns.map((column, index) => (
        <div key={index}>{column.title}</div>
      ))}
    </div>
  ),
  ExtensionsDrilldownTable: () => <div data-testid="extensions-drilldown-table" />,
  ExtensionsBindingsTable: () => <div data-testid="extensions-bindings-table" />,
  ExtensionsDriftTable: () => <div data-testid="extensions-drift-table" />,
}))

import { Extensions } from '../Extensions'

function renderExtensionsPage(initialEntry = '/extensions') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <AntApp>
          <Routes>
            <Route path="/extensions" element={<Extensions />} />
          </Routes>
        </AntApp>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('Extensions i18n', () => {
  beforeEach(async () => {
    await changeLanguage('ru')
    localStorage.clear()

    mockUseClusters.mockReturnValue({
      data: { clusters: [] },
      isLoading: false,
    })
    mockUseDatabases.mockReturnValue({
      data: { databases: [] },
      isLoading: false,
    })
    mockUseExtensionsOverview.mockReturnValue({
      data: {
        extensions: [],
        total: 0,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      refetch: vi.fn(),
    })
    mockUseExtensionsOverviewDatabases.mockReturnValue({
      data: {
        databases: [],
        total: 0,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      refetch: vi.fn(),
    })
    mockUseManualOperationBindings.mockReturnValue({
      data: [],
      isError: false,
    })
    mockUpsertBindingMutateAsync.mockReset()
    mockDeleteBindingMutateAsync.mockReset()
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('renders localized page chrome and overview labels for the extensions workspace', () => {
    renderExtensionsPage()

    expect(screen.getByRole('heading', { name: 'Расширения' })).toBeInTheDocument()
    expect(
      screen.getByText('Рабочее место управления расширениями с URL-backed выбранным extension и secondary drill-down surface.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Обновить' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Поиск по имени расширения')).toBeInTheDocument()
    expect(screen.getByText('Всего БД: —')).toBeInTheDocument()
    expect(screen.getByText('Назначение')).toBeInTheDocument()
    expect(screen.getByText('Последний snapshot')).toBeInTheDocument()
  })

  it('renders localized load failure messaging for the overview query', () => {
    mockUseExtensionsOverview.mockReturnValue({
      data: {
        extensions: [],
        total: 0,
      },
      isLoading: false,
      isFetching: false,
      isError: true,
      refetch: vi.fn(),
    })

    renderExtensionsPage()

    expect(screen.getByText('Не удалось загрузить обзор extensions')).toBeInTheDocument()
  })
})
