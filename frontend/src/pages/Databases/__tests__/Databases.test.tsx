import { isValidElement, type ReactNode } from 'react'
import { afterAll, beforeAll, beforeEach, describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { changeLanguage, ensureNamespaces } from '@/i18n/runtime'

import type { Database } from '../../../api/generated/model/database'
import { Databases } from '../Databases'

const {
  mockUseDatabases,
  mockUseDatabase,
  mockSetFilter,
  mockConfirmWithTracking,
  mockUpdateDatabaseCredentialsMutate,
  mockUpdateDatabaseDbmsMetadataMutate,
  mockUpdateDatabaseIbcmdConnectionProfileMutate,
} = vi.hoisted(() => ({
  mockUseDatabases: vi.fn(),
  mockUseDatabase: vi.fn(),
  mockSetFilter: vi.fn(),
  mockConfirmWithTracking: vi.fn((_: unknown, config: { onOk?: () => unknown }) => config.onOk?.()),
  mockUpdateDatabaseCredentialsMutate: vi.fn(),
  mockUpdateDatabaseDbmsMetadataMutate: vi.fn(),
  mockUpdateDatabaseIbcmdConnectionProfileMutate: vi.fn(),
}))

function buildDatabase(overrides: Partial<Database> = {}): Database {
  return {
    id: 'db-1',
    name: 'Accounting DB',
    host: 'localhost',
    port: 1541,
    odata_url: 'http://localhost/odata',
    username: 'odata',
    password: '',
    password_configured: true,
    server_address: 'localhost',
    server_port: 1540,
    infobase_name: 'Accounting',
    status: 'active',
    status_display: 'Active',
    version: '8.3.24',
    last_check: '2026-03-19T10:00:00Z',
    last_check_status: 'ok',
    consecutive_failures: 0,
    avg_response_time: 12,
    cluster_id: 'cluster-1',
    is_healthy: true,
    sessions_deny: false,
    scheduled_jobs_deny: false,
    dbms: 'PostgreSQL',
    db_server: 'pg-db',
    db_name: 'accounting',
    ibcmd_connection: {
      remote: 'srv/Accounting',
      pid: 1001,
      offline: {
        path: '/srv/ibcmd',
      },
    },
    denied_from: null,
    denied_to: null,
    denied_message: null,
    permission_code: null,
    denied_parameter: null,
    last_health_error: null,
    last_health_error_code: null,
    created_at: '2026-03-13T00:00:00Z',
    updated_at: '2026-03-13T00:00:00Z',
    ...overrides,
  }
}

const databases = [
  buildDatabase(),
  buildDatabase({
    id: 'db-2',
    name: 'Warehouse DB',
    infobase_name: 'Warehouse',
    cluster_id: 'cluster-1',
  }),
]

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: mockUseDatabases,
  useDatabase: mockUseDatabase,
  useExecuteRasOperation: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useHealthCheckDatabase: () => ({
    mutateAsync: vi.fn(async () => ({ operation_id: 'operation-1' })),
    isPending: false,
  }),
  useBulkHealthCheckDatabases: () => ({
    mutateAsync: vi.fn(async () => ({ operation_id: 'operation-1' })),
    isPending: false,
  }),
  useSetDatabaseStatus: () => ({
    mutateAsync: vi.fn(async () => ({ status: 'active', updated: 1, not_found: [] })),
    isPending: false,
  }),
  useUpdateDatabaseCredentials: () => ({
    mutate: mockUpdateDatabaseCredentialsMutate,
    isPending: false,
  }),
  useUpdateDatabaseDbmsMetadata: () => ({
    mutate: mockUpdateDatabaseDbmsMetadataMutate,
    isPending: false,
  }),
  useUpdateDatabaseIbcmdConnectionProfile: () => ({
    mutate: mockUpdateDatabaseIbcmdConnectionProfileMutate,
    isPending: false,
  }),
  useDatabaseExtensionsSnapshot: () => ({
    data: null,
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('../../../api/queries/clusters', () => ({
  useClusters: () => ({
    data: {
      clusters: [
        {
          id: 'cluster-1',
          name: 'Main Cluster',
          databases_count: 2,
        },
      ],
    },
    isLoading: false,
  }),
}))

vi.mock('../../../authz/useAuthz', () => ({
  useAuthz: () => ({
    isStaff: true,
    canAnyDatabase: () => true,
    canDatabase: () => true,
  }),
}))

vi.mock('../../../contexts/DatabaseStreamContext', () => ({
  useDatabaseStreamStatus: () => ({
    isConnected: true,
  }),
}))

vi.mock('../../../components/actions', () => ({
  BulkActionsToolbar: () => null,
  OperationConfirmModal: () => null,
  DatabaseActionsMenu: () => null,
}))

vi.mock('../../../components/table/hooks/useTableToolkit', () => ({
  useTableToolkit: () => ({
    pagination: { page: 1, pageSize: 50 },
    search: '',
    filtersPayload: undefined,
    sortPayload: undefined,
    setFilter: mockSetFilter,
    totalColumnsWidth: 960,
  }),
}))

vi.mock('../../../observability/confirmWithTracking', () => ({
  confirmWithTracking: mockConfirmWithTracking,
}))

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const { createDatabasesAntdTestDouble } = await import('./databasesAntdTestDouble')
  return createDatabasesAntdTestDouble(actual)
})

vi.mock('../../../components/platform', () => ({
  WorkspacePage: ({
    header,
    children,
  }: {
    header?: ReactNode
    children?: ReactNode
  }) => (
    <div>
      {header}
      {children}
    </div>
  ),
  PageHeader: ({
    title,
    subtitle,
    actions,
  }: {
    title?: ReactNode
    subtitle?: ReactNode
    actions?: ReactNode
  }) => (
    <header>
      <h2>{title}</h2>
      {subtitle ? <div>{subtitle}</div> : null}
      {actions}
    </header>
  ),
  MasterDetailShell: ({
    list,
    detail,
  }: {
    list?: ReactNode
    detail?: ReactNode
  }) => (
    <div>
      <section>{list}</section>
      <aside>{detail}</aside>
    </div>
  ),
  EntityList: ({
    title,
    extra,
    toolbar,
    emptyDescription,
    dataSource,
    renderItem,
  }: {
    title?: ReactNode
    extra?: ReactNode
    toolbar?: ReactNode
    emptyDescription?: ReactNode
    dataSource?: Database[]
    renderItem: (database: Database) => ReactNode
  }) => (
    <section>
      {title ? <h3>{title}</h3> : null}
      {extra}
      {toolbar}
      {(dataSource?.length ?? 0) > 0
        ? dataSource?.map((database) => renderItem(database))
        : <div>{emptyDescription}</div>}
    </section>
  ),
  EntityDetails: ({
    title,
    error,
    emptyDescription,
  }: {
    title?: ReactNode
    error?: ReactNode
    emptyDescription?: ReactNode
  }) => (
    <section>
      {title ? <h3>{title}</h3> : null}
      {error ?? emptyDescription}
    </section>
  ),
}))

const toReactNode = (value: unknown): ReactNode => {
  if (isValidElement(value) || value == null) {
    return value
  }
  if (typeof value === 'object' && 'children' in (value as Record<string, unknown>)) {
    return (value as { children?: ReactNode }).children ?? null
  }
  return value as ReactNode
}

vi.mock('../../../components/table/TableToolkit', () => ({
  TableToolkit: ({
    data,
    columns,
  }: {
    data: Database[]
    columns: Array<{
      key?: string
      render?: (value: unknown, record: Database, index: number) => ReactNode
    }>
  }) => {
    const nameColumn = columns.find((column) => column.key === 'name')
    return (
      <div data-testid="databases-table">
        {data.map((database, index) => (
          <div key={database.id}>
            {nameColumn?.render
              ? toReactNode(nameColumn.render(database.name, database, index))
              : database.name
            }
          </div>
        ))}
      </div>
    )
  },
}))

vi.mock('../components/DatabaseCredentialsModal', () => ({
  DatabaseCredentialsModal: ({
    open,
    database,
    onCancel,
    onReset,
  }: {
    open: boolean
    database: Database | null
    onCancel: () => void
    onReset: () => void
  }) => (
    open ? (
      <div data-testid="database-credentials-modal">
        <div>Credentials {database?.name}</div>
        <button type="button" onClick={onReset}>
          Reset credentials
        </button>
        <button type="button" onClick={onCancel}>
          Close credentials
        </button>
      </div>
    ) : null
  ),
}))

vi.mock('../components/DatabaseDbmsMetadataModal', () => ({
  DatabaseDbmsMetadataModal: ({
    open,
    database,
    onCancel,
    onReset,
  }: {
    open: boolean
    database: Database | null
    onCancel: () => void
    onReset: () => void
  }) => (
    open ? (
      <div data-testid="database-dbms-modal">
        <div>DBMS {database?.name}</div>
        <button type="button" onClick={onReset}>
          Reset DBMS metadata
        </button>
        <button type="button" onClick={onCancel}>
          Close DBMS metadata
        </button>
      </div>
    ) : null
  ),
}))

vi.mock('../components/DatabaseIbcmdConnectionProfileModal', () => ({
  DatabaseIbcmdConnectionProfileModal: ({
    open,
    database,
    onCancel,
    onReset,
  }: {
    open: boolean
    database: Database | null
    onCancel: () => void
    onReset: () => void
  }) => (
    open ? (
      <div data-testid="database-ibcmd-modal">
        <div>IBCMD {database?.name}</div>
        <button type="button" onClick={onReset}>
          Reset IBCMD profile
        </button>
        <button type="button" onClick={onCancel}>
          Close IBCMD profile
        </button>
      </div>
    ) : null
  ),
}))

vi.mock('../components/DatabaseMetadataManagementDrawer', () => ({
  DatabaseMetadataManagementDrawer: ({
    open,
    databaseName,
    onClose,
  }: {
    open: boolean
    databaseName?: string
    onClose: () => void
  }) => (
    open ? (
      <div data-testid="database-metadata-drawer">
        <div>Metadata {databaseName}</div>
        <button type="button" onClick={onClose}>
          Close metadata management
        </button>
      </div>
    ) : null
  ),
}))

vi.mock('../components/ExtensionsDrawer', () => ({
  ExtensionsDrawer: ({
    open,
    databaseName,
    onClose,
  }: {
    open: boolean
    databaseName?: string
    onClose: () => void
  }) => (
    open ? (
      <div data-testid="database-extensions-drawer">
        <div>Extensions {databaseName}</div>
        <button type="button" onClick={onClose}>
          Close extensions
        </button>
      </div>
    ) : null
  ),
}))

vi.mock('../components/DatabaseWorkspaceDetailPanel', () => ({
  DatabaseWorkspaceDetailPanel: ({
    database,
    onOpenContext,
  }: {
    database: Database
    onOpenContext: (context: 'credentials' | 'dbms' | 'ibcmd' | 'metadata' | 'extensions') => void
  }) => (
    <div data-testid="database-workspace-detail-panel">
      <h3>{`Database Workspace: ${database.name}`}</h3>
      <output data-testid="database-workspace-selected-id">{database.id}</output>
      <button
        type="button"
        data-testid="database-workspace-open-credentials"
        onClick={() => onOpenContext('credentials')}
      >
        Open credentials
      </button>
      <button
        type="button"
        data-testid="database-workspace-open-dbms"
        onClick={() => onOpenContext('dbms')}
      >
        Open DBMS metadata
      </button>
      <button
        type="button"
        data-testid="database-workspace-open-ibcmd"
        onClick={() => onOpenContext('ibcmd')}
      >
        Open IBCMD profile
      </button>
      <button
        type="button"
        data-testid="database-workspace-open-metadata"
        onClick={() => onOpenContext('metadata')}
      >
        Open metadata management
      </button>
      <button
        type="button"
        data-testid="database-workspace-open-extensions"
        onClick={() => onOpenContext('extensions')}
      >
        Open extensions
      </button>
    </div>
  ),
}))

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="databases-location">{location.pathname}{location.search}</output>
}

function renderDatabasesPage(initialEntry = '/databases') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AntApp>
        <Routes>
          <Route
            path="/databases"
            element={(
              <>
                <Databases />
                <LocationProbe />
              </>
            )}
          />
        </Routes>
      </AntApp>
    </MemoryRouter>
  )
}

describe('Databases', () => {
  beforeAll(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'databases')
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockConfirmWithTracking.mockClear()
    mockUpdateDatabaseCredentialsMutate.mockReset()
    mockUpdateDatabaseDbmsMetadataMutate.mockReset()
    mockUpdateDatabaseIbcmdConnectionProfileMutate.mockReset()
    localStorage.setItem('active_tenant_id', 'tenant-1')
    mockUseDatabases.mockReturnValue({
      data: {
        databases,
        count: databases.length,
        total: databases.length,
      },
      isLoading: false,
    })
    mockUseDatabase.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    })
  })

  afterAll(async () => {
    await ensureNamespaces('ru', 'databases')
    await changeLanguage('ru')
  })

  it('restores selected database and active management context from query params', async () => {
    renderDatabasesPage('/databases?cluster=cluster-1&database=db-1&context=metadata')

    expect(await screen.findByRole('heading', { name: 'Databases', level: 2 })).toBeVisible()
    expect(screen.getByTestId('database-workspace-selected-id')).toHaveTextContent('db-1')
    expect(screen.getByTestId('database-metadata-drawer')).toHaveTextContent('Metadata Accounting DB')
    expect(screen.getByTestId('databases-location')).toHaveTextContent('/databases?cluster=cluster-1&database=db-1&context=metadata')

    fireEvent.click(screen.getByRole('button', { name: 'Close metadata management' }))

    await waitFor(() => {
      expect(screen.getByTestId('databases-location')).toHaveTextContent('/databases?cluster=cluster-1&database=db-1&context=inspect')
    })
    expect(screen.queryByTestId('database-metadata-drawer')).not.toBeInTheDocument()
  })

  it('keeps selected database and active management context in the URL when the operator switches workspace surfaces', async () => {
    renderDatabasesPage('/databases')

    expect(await screen.findByRole('heading', { name: 'Databases', level: 2 })).toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: 'Open database Accounting DB' }))

    await waitFor(() => {
      expect(screen.getByTestId('databases-location')).toHaveTextContent('/databases?database=db-1&context=inspect')
    })
    expect(screen.getByTestId('database-workspace-selected-id')).toHaveTextContent('db-1')

    fireEvent.click(screen.getByTestId('database-workspace-open-credentials'))

    await waitFor(() => {
      expect(screen.getByTestId('databases-location')).toHaveTextContent('/databases?database=db-1&context=credentials')
    })
    expect(screen.getByTestId('database-credentials-modal')).toHaveTextContent('Credentials Accounting DB')

    fireEvent.click(screen.getByRole('button', { name: 'Close credentials' }))

    await waitFor(() => {
      expect(screen.getByTestId('databases-location')).toHaveTextContent('/databases?database=db-1&context=inspect')
    })
    expect(screen.queryByTestId('database-credentials-modal')).not.toBeInTheDocument()
  })

  it.each([
    {
      context: 'credentials',
      modalTestId: 'database-credentials-modal',
      resetLabel: 'Reset credentials',
      actionName: 'Reset database credentials',
      expectedPayload: { database_id: 'db-1', reset: true },
      expectedMutate: mockUpdateDatabaseCredentialsMutate,
    },
    {
      context: 'dbms',
      modalTestId: 'database-dbms-modal',
      resetLabel: 'Reset DBMS metadata',
      actionName: 'Reset DBMS metadata',
      expectedPayload: { database_id: 'db-1', reset: true },
      expectedMutate: mockUpdateDatabaseDbmsMetadataMutate,
    },
    {
      context: 'ibcmd',
      modalTestId: 'database-ibcmd-modal',
      resetLabel: 'Reset IBCMD profile',
      actionName: 'Reset IBCMD connection profile',
      expectedPayload: { database_id: 'db-1', reset: true },
      expectedMutate: mockUpdateDatabaseIbcmdConnectionProfileMutate,
    },
  ])('tracks %s reset action through confirmWithTracking', async ({
    context,
    modalTestId,
    resetLabel,
    actionName,
    expectedPayload,
    expectedMutate,
  }) => {
    renderDatabasesPage(`/databases?database=db-1&context=${context}`)

    expect(await screen.findByTestId(modalTestId)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: resetLabel }))

    expect(mockConfirmWithTracking).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        okText: 'Reset',
        cancelText: 'Cancel',
      }),
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName,
        context: {
          database_id: 'db-1',
        },
      }),
    )
    expect(expectedMutate).toHaveBeenCalledWith(
      expectedPayload,
      expect.any(Object),
    )
  })
})
