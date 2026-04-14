import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { Artifact } from '../../../api/artifacts'
import { changeLanguage } from '@/i18n/runtime'

import { ArtifactsPage } from '../ArtifactsPage'

const {
  mockUseArtifacts,
  mockUseArtifact,
  mockDeleteArtifactMutateAsync,
  mockRestoreArtifactMutateAsync,
  mockConfirmWithTracking,
} = vi.hoisted(() => ({
  mockUseArtifacts: vi.fn(),
  mockUseArtifact: vi.fn(),
  mockDeleteArtifactMutateAsync: vi.fn(),
  mockRestoreArtifactMutateAsync: vi.fn(),
  mockConfirmWithTracking: vi.fn((_: unknown, config: { onOk?: () => unknown }) => config.onOk?.()),
}))

const buildArtifact = (overrides: Partial<Artifact> = {}): Artifact => ({
  id: 'artifact-1',
  name: 'Accounting config',
  kind: 'config_xml',
  tags: ['release'],
  purge_after: null,
  created_at: '2026-04-01T10:00:00Z',
  is_deleted: false,
  deleted_at: null,
  purge_state: 'scheduled',
  purge_blockers: [],
  is_versioned: true,
  ...overrides,
})

vi.mock('../../../api/queries', () => ({
  useArtifacts: mockUseArtifacts,
  useArtifact: mockUseArtifact,
  useDeleteArtifact: () => ({
    mutateAsync: mockDeleteArtifactMutateAsync,
    isPending: false,
  }),
  useRestoreArtifact: () => ({
    mutateAsync: mockRestoreArtifactMutateAsync,
    isPending: false,
  }),
  queryKeys: {
    artifacts: {
      all: ['artifacts'],
    },
  },
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
    search: '',
    filters: {},
    totalColumnsWidth: 960,
  }),
}))

vi.mock('../../../components/table/TableToolkit', () => ({
  TableToolkit: ({
    data,
    columns,
    searchPlaceholder,
  }: {
    data: Array<Record<string, unknown>>
    columns: Array<{
      key?: string
      render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
    }>
    searchPlaceholder?: string
  }) => {
    const actionsColumn = columns.find((column) => column.key === 'actions')

    return (
      <div data-testid="artifacts-table">
        {searchPlaceholder ? <div>{searchPlaceholder}</div> : null}
        {data.map((artifact, index) => (
          <div key={String(artifact.id)} data-testid={`artifact-row-actions-${String(artifact.id)}`}>
            {actionsColumn?.render?.(null, artifact, index) ?? null}
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
  PageHeader: ({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
      {actions}
    </div>
  ),
}))

vi.mock('../ArtifactsCreateModal', () => ({
  ArtifactsCreateModal: () => null,
}))

vi.mock('../ArtifactDetailsDrawer', () => ({
  ArtifactDetailsDrawer: () => null,
}))

vi.mock('../ArtifactsPurgeModal', () => ({
  ArtifactsPurgeModal: () => null,
}))

function renderArtifactsPage(initialEntry = '/artifacts') {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AntApp>
          <Routes>
            <Route path="/artifacts" element={<ArtifactsPage />} />
          </Routes>
        </AntApp>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ArtifactsPage observability', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    mockConfirmWithTracking.mockClear()
    mockDeleteArtifactMutateAsync.mockReset()
    mockRestoreArtifactMutateAsync.mockReset()
    mockUseArtifact.mockReturnValue({
      data: null,
      isLoading: false,
    })
    mockUseArtifacts.mockReturnValue({
      data: {
        artifacts: [],
        count: 0,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('tracks delete artifact actions through confirmWithTracking', async () => {
    const user = userEvent.setup()
    const artifact = buildArtifact()
    mockDeleteArtifactMutateAsync.mockResolvedValue({})
    mockUseArtifacts.mockReturnValue({
      data: {
        artifacts: [artifact],
        count: 1,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    renderArtifactsPage('/artifacts')

    await user.click(
      within(screen.getByTestId('artifact-row-actions-artifact-1')).getByRole('button', { name: 'Delete' })
    )

    expect(mockConfirmWithTracking).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        title: 'Delete artifact "Accounting config"?',
        okText: 'Delete',
      }),
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Delete artifact',
        context: {
          artifact_id: 'artifact-1',
          artifact_name: 'Accounting config',
        },
      }),
    )
    expect(mockDeleteArtifactMutateAsync).toHaveBeenCalledWith('artifact-1')
  })

  it('tracks restore artifact actions through confirmWithTracking', async () => {
    const user = userEvent.setup()
    const artifact = buildArtifact({
      is_deleted: true,
      deleted_at: '2026-04-05T10:00:00Z',
      purge_state: 'blocked',
    })
    mockRestoreArtifactMutateAsync.mockResolvedValue({})
    mockUseArtifacts.mockReturnValue({
      data: {
        artifacts: [artifact],
        count: 1,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    renderArtifactsPage('/artifacts?tab=deleted')

    await user.click(
      within(screen.getByTestId('artifact-row-actions-artifact-1')).getByRole('button', { name: 'Restore' })
    )

    expect(mockConfirmWithTracking).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        title: 'Restore artifact "Accounting config"?',
        okText: 'Restore',
      }),
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Restore artifact',
        context: {
          artifact_id: 'artifact-1',
          artifact_name: 'Accounting config',
        },
      }),
    )
    expect(mockRestoreArtifactMutateAsync).toHaveBeenCalledWith('artifact-1')
  })

  it('renders localized page chrome for the Russian artifacts workspace', async () => {
    await changeLanguage('ru')

    renderArtifactsPage('/artifacts?tab=deleted')

    expect(screen.getByRole('heading', { name: 'Артефакты' })).toBeInTheDocument()
    expect(
      screen.getByText('Рабочее место каталога с URL-backed tab/artifact context и canonical secondary surfaces.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Обновить' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Добавить артефакт/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Активные' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Удалённые' })).toBeInTheDocument()
    expect(screen.getByText('tab=Удалённые')).toBeInTheDocument()
    expect(screen.getByText('Поиск артефактов')).toBeInTheDocument()
  })
})
