import { afterEach, describe, expect, it, vi } from 'vitest'

const mockApiClientGet = vi.fn()

vi.mock('../client', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockApiClientGet(...args),
  },
}))

import { getCommandSchemasEditorView } from '../commandSchemas'

const commandSchemasEditorViewFixture = {
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
      commands_by_id: {},
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
        commands_by_id: {},
      },
    },
  },
}

describe('getCommandSchemasEditorView', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('dedupes concurrent editor-view requests for the same driver and mode', async () => {
    let resolveRequest!: (value: { data: typeof commandSchemasEditorViewFixture }) => void
    mockApiClientGet.mockImplementation(
      () =>
        new Promise<{ data: typeof commandSchemasEditorViewFixture }>((resolve) => {
          resolveRequest = resolve
        }),
    )

    const firstRequest = getCommandSchemasEditorView('ibcmd', 'guided')
    const secondRequest = getCommandSchemasEditorView('ibcmd', 'guided')

    expect(mockApiClientGet).toHaveBeenCalledTimes(1)

    resolveRequest({ data: commandSchemasEditorViewFixture })
    const [firstResult, secondResult] = await Promise.all([firstRequest, secondRequest])

    expect(firstResult).toEqual(commandSchemasEditorViewFixture)
    expect(secondResult).toEqual(commandSchemasEditorViewFixture)
  })

  it('releases the in-flight slot after completion', async () => {
    mockApiClientGet.mockResolvedValue({ data: commandSchemasEditorViewFixture })

    await getCommandSchemasEditorView('ibcmd', 'guided')
    await getCommandSchemasEditorView('ibcmd', 'guided')

    expect(mockApiClientGet).toHaveBeenCalledTimes(2)
  })
})
