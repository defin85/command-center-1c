import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import type { CommandSchemasEditorView } from '../../../api/commandSchemas'
import { useCommandSchemasState } from '../model/useCommandSchemasState'

const mockGetCommandSchemasEditorView = vi.fn()

vi.mock('@/i18n', () => ({
  useAdminSupportTranslation: () => ({
    t: (value: unknown) => (
      typeof value === 'function'
        ? 'Failed to load command schemas'
        : String(value)
    ),
  }),
}))

vi.mock('../../../api/commandSchemas', () => ({
  getCommandSchemasEditorView: (...args: unknown[]) => mockGetCommandSchemasEditorView(...args),
}))

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="command-schemas-location">{location.pathname}{location.search}</output>
}

function CommandSchemasStateProbe() {
  const state = useCommandSchemasState()
  return <output data-testid="command-schemas-selected">{state.selectedCommandId}</output>
}

const publishCommandCatalogEntry = {
  label: 'Publish infobase',
  description: 'Publishes the selected infobase.',
  argv: ['publish'],
  scope: 'global' as const,
  risk_level: 'safe' as const,
  params_by_name: {},
}

const commandCatalogEntry = {
  label: 'Catalog sync',
  description: 'Sync the command catalog',
  argv: ['catalog', 'sync'],
  scope: 'global' as const,
  risk_level: 'safe' as const,
  params_by_name: {},
}

describe('useCommandSchemasState', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('syncs the selected command into the URL without refetching the editor view', async () => {
    mockGetCommandSchemasEditorView.mockResolvedValue({
      driver: 'ibcmd',
      etag: 'etag-1',
      base: {
        approved_version: null,
        approved_version_id: null,
        latest_version: null,
        latest_version_id: null,
      },
      overrides: {
        active_version: null,
        active_version_id: null,
      },
      catalogs: {
        base: {
          catalog_version: 2,
          driver: 'ibcmd',
          driver_schema: {},
          commands_by_id: {
            'catalog.sync': commandCatalogEntry,
          },
        },
        overrides: {
          catalog_version: 2,
          driver: 'ibcmd',
          overrides: {
            driver_schema: {},
            commands_by_id: {},
          },
        },
        effective: {
          base_version: null,
          base_version_id: null,
          base_alias: null,
          overrides_version: null,
          overrides_version_id: null,
          source: 'effective',
          catalog: {
            catalog_version: 2,
            driver: 'ibcmd',
            driver_schema: {},
            commands_by_id: {
              'catalog.sync': commandCatalogEntry,
            },
          },
        },
      },
    })

    render(
      <MemoryRouter initialEntries={['/settings/command-schemas?driver=ibcmd&mode=guided']}>
        <Routes>
          <Route
            path="/settings/command-schemas"
            element={(
              <>
                <CommandSchemasStateProbe />
                <LocationProbe />
              </>
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('command-schemas-selected')).toHaveTextContent('catalog.sync')
    })

    await waitFor(() => {
      expect(screen.getByTestId('command-schemas-location')).toHaveTextContent('command=catalog.sync')
    })

    expect(mockGetCommandSchemasEditorView).toHaveBeenCalledTimes(1)
    expect(mockGetCommandSchemasEditorView).toHaveBeenCalledWith('ibcmd', 'guided')
  })

  it('keeps the route-selected command in the URL while the editor view is still loading', async () => {
    let resolveView!: (value: CommandSchemasEditorView) => void
    const pendingView = new Promise<CommandSchemasEditorView>((resolve) => {
      resolveView = resolve
    })
    mockGetCommandSchemasEditorView.mockReturnValue(pendingView)

    render(
      <MemoryRouter
        initialEntries={['/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish']}
      >
        <Routes>
          <Route
            path="/settings/command-schemas"
            element={(
              <>
                <CommandSchemasStateProbe />
                <LocationProbe />
              </>
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockGetCommandSchemasEditorView).toHaveBeenCalledTimes(1)
    })

    expect(screen.getByTestId('command-schemas-selected')).toHaveTextContent('ibcmd.publish')
    expect(screen.getByTestId('command-schemas-location')).toHaveTextContent(
      '/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish',
    )

    resolveView({
      driver: 'ibcmd',
      etag: 'etag-1',
      base: {
        approved_version: null,
        approved_version_id: null,
        latest_version: null,
        latest_version_id: null,
      },
      overrides: {
        active_version: null,
        active_version_id: null,
      },
      catalogs: {
        base: {
          catalog_version: 2,
          driver: 'ibcmd',
          driver_schema: {},
          commands_by_id: {
            'ibcmd.publish': publishCommandCatalogEntry,
          },
        },
        overrides: {
          catalog_version: 2,
          driver: 'ibcmd',
          overrides: {
            driver_schema: {},
            commands_by_id: {},
          },
        },
        effective: {
          base_version: null,
          base_version_id: null,
          base_alias: null,
          overrides_version: null,
          overrides_version_id: null,
          source: 'effective',
          catalog: {
            catalog_version: 2,
            driver: 'ibcmd',
            driver_schema: {},
            commands_by_id: {
              'ibcmd.publish': publishCommandCatalogEntry,
            },
          },
        },
      },
    })

    await waitFor(() => {
      expect(screen.getByTestId('command-schemas-selected')).toHaveTextContent('ibcmd.publish')
    })

    expect(screen.getByTestId('command-schemas-location')).toHaveTextContent(
      '/settings/command-schemas?driver=ibcmd&mode=guided&command=ibcmd.publish',
    )
  })
})
