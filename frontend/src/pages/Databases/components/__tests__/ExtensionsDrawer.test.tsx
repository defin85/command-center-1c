import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { App } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'

import { ExtensionsDrawer } from '../ExtensionsDrawer'

const mockPostExtensionsPlan = vi.fn()
const mockPostExtensionsApply = vi.fn()
const mockListOperationCatalogExposures = vi.fn()
const mockUseManualOperationBindings = vi.fn()
const mockUseUpsertManualOperationBinding = vi.fn()
const mockUseDeleteManualOperationBinding = vi.fn()
const mockTryShowIbcmdCliUiError = vi.fn()

vi.mock('../../../../api/generated', () => ({
  getV2: () => ({
    postExtensionsPlan: (...args: unknown[]) => mockPostExtensionsPlan(...args),
    postExtensionsApply: (...args: unknown[]) => mockPostExtensionsApply(...args),
  }),
}))

vi.mock('../../../../api/operationCatalog', () => ({
  listOperationCatalogExposures: (...args: unknown[]) => mockListOperationCatalogExposures(...args),
}))

vi.mock('../../../../api/queries/extensionsManualOperations', () => ({
  useManualOperationBindings: (...args: unknown[]) => mockUseManualOperationBindings(...args),
  useUpsertManualOperationBinding: (...args: unknown[]) => mockUseUpsertManualOperationBinding(...args),
  useDeleteManualOperationBinding: (...args: unknown[]) => mockUseDeleteManualOperationBinding(...args),
}))

vi.mock('../../../../components/ibcmd/ibcmdCliUiErrors', () => ({
  tryShowIbcmdCliUiError: (...args: unknown[]) => mockTryShowIbcmdCliUiError(...args),
}))

describe('ExtensionsDrawer', () => {
  beforeEach(() => {
    mockPostExtensionsPlan.mockReset()
    mockPostExtensionsApply.mockReset()
    mockListOperationCatalogExposures.mockReset()
    mockUseManualOperationBindings.mockReset()
    mockUseUpsertManualOperationBinding.mockReset()
    mockUseDeleteManualOperationBinding.mockReset()
    mockTryShowIbcmdCliUiError.mockReset()

    mockPostExtensionsPlan.mockResolvedValue({
      plan_id: 'plan-1',
      execution_plan: {
        kind: 'workflow',
        argv_masked: ['--database=db-1'],
      },
      bindings: [
        {
          target_ref: 'extensions.sync',
          source_ref: 'tpl-sync',
          resolve_at: 'template',
          sensitive: false,
          status: 'resolved',
          reason: null,
        },
      ],
    })
    mockPostExtensionsApply.mockResolvedValue({ operation_id: 'op-apply-1' })
    mockListOperationCatalogExposures.mockResolvedValue({
      exposures: [
        {
          surface: 'template',
          alias: 'tpl-sync',
          name: 'Sync Template',
          description: '',
          capability: 'extensions.sync',
        },
      ],
    })
    mockUseManualOperationBindings.mockReturnValue({
      data: [
        {
          manual_operation: 'extensions.sync',
          template_id: 'tpl-sync',
          updated_at: '2026-01-01T00:00:00Z',
          updated_by: 'admin',
        },
      ],
      isError: false,
    })
    mockUseUpsertManualOperationBinding.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
    mockUseDeleteManualOperationBinding.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
    mockTryShowIbcmdCliUiError.mockReturnValue(false)
  })

  it('renders manual operations controls and snapshot payload', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <App>
          <ExtensionsDrawer
            open={true}
            databaseId="db-1"
            databaseName="db-1"
            onClose={() => {}}
            onRefreshSnapshot={() => {}}
            snapshot={{
              database_id: 'db-1',
              snapshot: { extensions: [] },
              updated_at: '2026-01-01T00:00:00Z',
              source_operation_id: 'op-1',
            }}
          />
        </App>
      </QueryClientProvider>
    )

    expect(screen.getByText('Extensions: db-1')).toBeInTheDocument()
    expect(screen.getByText('Manual Operations')).toBeInTheDocument()
    expect(screen.getByText(/"extensions"/)).toBeInTheDocument()
  })

  it('renders binding provenance preview as compact summary rows when launching a manual operation', async () => {
    const user = userEvent.setup()

    render(
      <QueryClientProvider client={new QueryClient()}>
        <App>
          <ExtensionsDrawer
            open={true}
            databaseId="db-1"
            databaseName="db-1"
            onClose={() => {}}
            onRefreshSnapshot={() => {}}
            snapshot={{
              database_id: 'db-1',
              snapshot: { extensions: [] },
              updated_at: '2026-01-01T00:00:00Z',
              source_operation_id: 'op-1',
            }}
          />
        </App>
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(screen.queryByText('Template is not resolved')).not.toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      expect(mockPostExtensionsPlan).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByTestId('database-extensions-binding-provenance')).toBeInTheDocument()
    expect(screen.getByTestId('database-extensions-binding-provenance-row-0')).toBeInTheDocument()
    expect(screen.getByText('Target')).toBeInTheDocument()
    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
