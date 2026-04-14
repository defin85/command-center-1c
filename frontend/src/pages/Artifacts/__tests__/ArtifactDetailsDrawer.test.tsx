import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import type { ReactNode } from 'react'
import type { Artifact, ArtifactVersion } from '../../../api/artifacts'
import { changeLanguage } from '@/i18n/runtime'

const {
  mockUseArtifactVersions,
  mockUseArtifactAliases,
  mockAliasMutate,
  mockConfirmWithTracking,
  mockTrackUiAction,
} = vi.hoisted(() => ({
  mockUseArtifactVersions: vi.fn(),
  mockUseArtifactAliases: vi.fn(),
  mockAliasMutate: vi.fn(),
  mockConfirmWithTracking: vi.fn((_: unknown, config: { onOk?: () => unknown }) => config.onOk?.()),
  mockTrackUiAction: vi.fn((_: unknown, handler?: () => unknown) => handler?.()),
}))

vi.mock('../../../api/queries', () => ({
  useArtifactVersions: mockUseArtifactVersions,
  useArtifactAliases: mockUseArtifactAliases,
  useUpsertArtifactAlias: () => ({
    mutate: mockAliasMutate,
    isPending: false,
  }),
}))

vi.mock('../../../api/artifacts', () => ({
  downloadArtifactVersion: vi.fn(async () => new Blob(['<xml />'], { type: 'text/xml' })),
}))

vi.mock('../../../observability/confirmWithTracking', () => ({
  confirmWithTracking: mockConfirmWithTracking,
}))

vi.mock('../../../observability/uiActionJournal', () => ({
  trackUiAction: mockTrackUiAction,
}))

vi.mock('../../../components/platform', () => ({
  DrawerSurfaceShell: ({
    open,
    extra,
    children,
  }: {
    open: boolean
    extra?: ReactNode
    children: ReactNode
  }) => (
    open ? (
      <div>
        <div data-testid="artifact-drawer-extra">{extra}</div>
        {children}
      </div>
    ) : null
  ),
}))

import { ArtifactDetailsDrawer } from '../ArtifactDetailsDrawer'

const artifact: Artifact = {
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
}

const version: ArtifactVersion = {
  id: 'version-1',
  version: '1.0.0',
  filename: 'Accounting.xml',
  storage_key: 'artifacts/version-1.xml',
  size: 1024,
  checksum: 'abc123',
  content_type: 'text/xml',
  metadata: {},
  created_at: '2026-04-01T10:00:00Z',
}

function renderDrawer() {
  render(
    <AntApp>
      <ArtifactDetailsDrawer
        open
        artifact={artifact}
        catalogTab="active"
        isStaff={true}
        onClose={() => {}}
        onDeleteArtifact={() => {}}
        onRestoreArtifact={() => {}}
        onOpenPurgeModal={() => {}}
      />
    </AntApp>
  )
}

describe('ArtifactDetailsDrawer observability', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    mockConfirmWithTracking.mockClear()
    mockTrackUiAction.mockClear()
    mockAliasMutate.mockReset()
    mockUseArtifactVersions.mockReturnValue({
      data: {
        versions: [version],
      },
      isLoading: false,
    })
    mockUseArtifactAliases.mockReturnValue({
      data: {
        aliases: [],
      },
      isLoading: false,
    })
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('tracks stable/approved alias confirmation through confirmWithTracking', async () => {
    const user = userEvent.setup()

    renderDrawer()

    await user.click(screen.getByRole('button', { name: /Set alias/i }))
    await user.click(await screen.findByText('Set alias: stable'))

    expect(mockConfirmWithTracking).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        title: 'Set alias "stable"?',
      }),
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Set artifact alias',
        context: {
          artifact_id: 'artifact-1',
          alias: 'stable',
          version: '1.0.0',
        },
      }),
    )
    expect(mockAliasMutate).toHaveBeenCalledWith(
      { alias: 'stable', version: '1.0.0' },
      expect.any(Object),
    )
  })

  it('tracks custom alias apply actions through trackUiAction', async () => {
    const user = userEvent.setup()

    renderDrawer()

    await user.click(screen.getByRole('tab', { name: 'Aliases (0)' }))
    await user.type(screen.getByPlaceholderText('Custom alias'), 'release-candidate')
    await user.click(screen.getByRole('button', { name: 'Apply alias' }))

    expect(mockTrackUiAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionKind: 'operator.action',
        actionName: 'Set artifact alias',
        context: {
          artifact_id: 'artifact-1',
          alias: 'release-candidate',
          version: '1.0.0',
        },
      }),
      expect.any(Function),
    )
    expect(mockAliasMutate).toHaveBeenCalledWith(
      { alias: 'release-candidate', version: '1.0.0' },
      expect.any(Object),
    )
  })

  it('renders localized drawer controls for the Russian locale', async () => {
    const user = userEvent.setup()

    await changeLanguage('ru')
    renderDrawer()

    expect(screen.getByRole('button', { name: /Установить алиас/ })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Алиасы (0)' }))
    expect(screen.getByPlaceholderText('Произвольный алиас')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Применить алиас' })).toBeInTheDocument()
  })
})
