import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { App as AntApp } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import type { AuthzContextValue } from '../../../authz/context'
import { AuthzContext } from '../../../authz/context'
import { TemplatesPage } from '../TemplatesPage'

const mockListOperationCatalogExposures = vi.fn()
const mockValidateOperationCatalogExposure = vi.fn()
const mockUseCreateTemplate = vi.fn()
const mockUseDeleteTemplate = vi.fn()
const mockUseSyncTemplatesFromRegistry = vi.fn()
const mockUseUpdateTemplate = vi.fn()
const mockUsePoolRuntimeRegistryInspect = vi.fn()

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

vi.mock('../../../api/operationCatalog', () => ({
  listOperationCatalogExposures: (...args: unknown[]) => mockListOperationCatalogExposures(...args),
  validateOperationCatalogExposure: (...args: unknown[]) => mockValidateOperationCatalogExposure(...args),
}))

vi.mock('../../../api/queries/templates', () => ({
  useCreateTemplate: (...args: unknown[]) => mockUseCreateTemplate(...args),
  useDeleteTemplate: (...args: unknown[]) => mockUseDeleteTemplate(...args),
  useSyncTemplatesFromRegistry: (...args: unknown[]) => mockUseSyncTemplatesFromRegistry(...args),
  useUpdateTemplate: (...args: unknown[]) => mockUseUpdateTemplate(...args),
  usePoolRuntimeRegistryInspect: (...args: unknown[]) => mockUsePoolRuntimeRegistryInspect(...args),
}))

const authzValue: AuthzContextValue = {
  isStaff: false,
  isLoading: false,
  canManageRuntimeControls: false,
  canDatabase: () => false,
  canCluster: () => false,
  canTemplate: () => false,
  canAnyDatabase: () => false,
  canAnyCluster: () => false,
  canAnyTemplate: () => false,
  getDatabaseLevel: () => null,
  getClusterLevel: () => null,
  getTemplateLevel: () => null,
}

function renderPage(initialEntries: string[] = ['/templates']) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={initialEntries}>
        <AuthzContext.Provider value={authzValue}>
          <AntApp>
            <TemplatesPage />
          </AntApp>
        </AuthzContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('TemplatesPage', () => {
  beforeEach(() => {
    mockListOperationCatalogExposures.mockReset()
    mockValidateOperationCatalogExposure.mockReset()
    mockUseCreateTemplate.mockReset()
    mockUseDeleteTemplate.mockReset()
    mockUseSyncTemplatesFromRegistry.mockReset()
    mockUseUpdateTemplate.mockReset()
    mockUsePoolRuntimeRegistryInspect.mockReset()

    mockListOperationCatalogExposures.mockResolvedValue({
      exposures: [
        {
          id: 'exposure-workflow-template',
          definition_id: 'definition-workflow-template',
          surface: 'template',
          alias: 'workflow-template-compat',
          name: 'Workflow Compatibility Template',
          description: 'Compatibility wrapper for a workflow executor',
          is_active: true,
          capability: 'workflow.compatibility',
          status: 'published',
          operation_type: 'workflow',
          target_entity: 'workflow',
          template_data: {
            workflow_id: 'workflow-template-v3',
          },
          executor_kind: 'workflow',
        },
      ],
      count: 1,
      total: 1,
    })
    mockUseCreateTemplate.mockReturnValue({ isPending: false, mutateAsync: vi.fn() })
    mockUseDeleteTemplate.mockReturnValue({ isPending: false, mutateAsync: vi.fn() })
    mockUseSyncTemplatesFromRegistry.mockReturnValue({ isPending: false, mutateAsync: vi.fn() })
    mockUseUpdateTemplate.mockReturnValue({ isPending: false, mutateAsync: vi.fn() })
    mockUsePoolRuntimeRegistryInspect.mockReturnValue({
      data: { contract_version: 'pool_runtime.v1', entries: [] },
      isError: false,
      isLoading: false,
    })
  })

  it('marks workflow executor templates as compatibility-only and redirects analyst authoring to workflows', async () => {
    renderPage()

    await waitFor(() => {
      expect(mockListOperationCatalogExposures).toHaveBeenCalledWith(expect.objectContaining({
        surface: 'template',
      }))
    })

    expect(screen.getByText('Atomic operations only')).toBeInTheDocument()
    expect(
      screen.getByText('Use /workflows to model analyst-facing schemes. workflow executor templates remain available here only as a compatibility/integration path.')
    ).toBeInTheDocument()
    expect(await screen.findByText('Workflow Compatibility Template')).toBeInTheDocument()
    expect(await screen.findByTestId('templates-executor-kind-compatibility-tag')).toHaveTextContent('compatibility')
  })

  it('restores selected template detail from the route state', async () => {
    renderPage(['/templates?template=workflow-template-compat&detail=1'])

    expect(await screen.findByTestId('templates-selected-id')).toHaveTextContent('workflow-template-compat')
    expect(await screen.findByTestId('templates-selected-status')).toHaveTextContent('published')
    expect(await screen.findByTestId('templates-selected-template-data')).toHaveTextContent('workflow-template-v3')
  })

  it('hydrates search, filters, and sort from URL-backed workspace state', async () => {
    const params = new URLSearchParams()
    params.set('q', 'compat')
    params.set('filters', JSON.stringify({ executor_kind: 'workflow' }))
    params.set('sort', JSON.stringify({ key: 'updated_at', order: 'desc' }))

    renderPage([`/templates?${params.toString()}`])

    await waitFor(() => {
      expect(mockListOperationCatalogExposures).toHaveBeenCalledWith(expect.objectContaining({
        surface: 'template',
        search: 'compat',
        filters: JSON.stringify({
          executor_kind: {
            op: 'contains',
            value: 'workflow',
          },
        }),
        sort: JSON.stringify({
          key: 'updated_at',
          order: 'desc',
        }),
      }))
    })
  })

  it('does not open compose=edit from the URL without manage permissions', async () => {
    renderPage(['/templates?template=workflow-template-compat&compose=edit'])

    expect(await screen.findByTestId('templates-selected-id')).toHaveTextContent('workflow-template-compat')
    await waitFor(() => {
      expect(screen.queryByTestId('operation-exposure-editor-name')).not.toBeInTheDocument()
    })
  })
})
