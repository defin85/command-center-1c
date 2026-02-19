import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import type { Organization } from '../../../api/intercompanyPools'
import { PoolCatalogPage } from '../PoolCatalogPage'

const mockListOrganizations = vi.fn()
const mockGetOrganization = vi.fn()
const mockListOrganizationPools = vi.fn()
const mockGetPoolGraph = vi.fn()
const mockUpsertOrganization = vi.fn()
const mockUpsertOrganizationPool = vi.fn()
const mockUpsertPoolTopologySnapshot = vi.fn()
const mockSyncOrganizationsCatalog = vi.fn()
const mockUseMe = vi.fn()
const mockUseDatabases = vi.fn()
const mockUseMyTenants = vi.fn()

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../api/queries/me', () => ({
  useMe: (...args: unknown[]) => mockUseMe(...args),
}))

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: (...args: unknown[]) => mockUseDatabases(...args),
}))

vi.mock('../../../api/queries/tenants', () => ({
  useMyTenants: (...args: unknown[]) => mockUseMyTenants(...args),
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizations: (...args: unknown[]) => mockListOrganizations(...args),
  getOrganization: (...args: unknown[]) => mockGetOrganization(...args),
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
  getPoolGraph: (...args: unknown[]) => mockGetPoolGraph(...args),
  upsertOrganization: (...args: unknown[]) => mockUpsertOrganization(...args),
  upsertOrganizationPool: (...args: unknown[]) => mockUpsertOrganizationPool(...args),
  upsertPoolTopologySnapshot: (...args: unknown[]) => mockUpsertPoolTopologySnapshot(...args),
  syncOrganizationsCatalog: (...args: unknown[]) => mockSyncOrganizationsCatalog(...args),
}))

const baseOrganization: Organization = {
  id: '11111111-1111-1111-1111-111111111111',
  tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  database_id: '22222222-2222-2222-2222-222222222222',
  name: 'Org One',
  full_name: 'Org One LLC',
  inn: '730000000001',
  kpp: '123456789',
  status: 'active',
  external_ref: '',
  metadata: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:01Z',
}

const secondOrganization: Organization = {
  ...baseOrganization,
  id: '77777777-7777-7777-7777-777777777777',
  database_id: '88888888-8888-8888-8888-888888888888',
  name: 'Org Two',
  full_name: 'Org Two LLC',
  inn: '730000000002',
}

function renderPage() {
  return render(
    <AntApp>
      <PoolCatalogPage />
    </AntApp>
  )
}

async function selectDropdownOption(label: string) {
  const matches = await screen.findAllByText(label)
  const option = [...matches]
    .reverse()
    .find((node) => node.closest('.ant-select-item-option'))
  expect(option).toBeTruthy()
  fireEvent.click(option as Element)
}

describe('PoolCatalogPage', () => {
  beforeEach(() => {
    localStorage.clear()

    mockListOrganizations.mockReset()
    mockGetOrganization.mockReset()
    mockListOrganizationPools.mockReset()
    mockGetPoolGraph.mockReset()
    mockUpsertOrganization.mockReset()
    mockUpsertOrganizationPool.mockReset()
    mockUpsertPoolTopologySnapshot.mockReset()
    mockSyncOrganizationsCatalog.mockReset()
    mockUseMe.mockReset()
    mockUseDatabases.mockReset()
    mockUseMyTenants.mockReset()

    mockUseMe.mockReturnValue({ data: { is_staff: false } })
    mockUseMyTenants.mockReturnValue({
      data: { active_tenant_id: null, tenants: [] },
    })
    mockUseDatabases.mockReturnValue({
      data: {
        databases: [
          { id: '22222222-2222-2222-2222-222222222222', name: 'db1' },
          { id: '33333333-3333-3333-3333-333333333333', name: 'db2' },
        ],
      },
      isLoading: false,
    })

    mockListOrganizations.mockResolvedValue([baseOrganization])
    mockGetOrganization.mockResolvedValue({
      organization: baseOrganization,
      pool_bindings: [],
    })
    mockListOrganizationPools.mockResolvedValue([
      {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
    ])
    mockGetPoolGraph.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      date: '2026-01-01',
      version: 'v1:topology-initial',
      nodes: [],
      edges: [],
    })
    mockUpsertOrganization.mockResolvedValue({
      organization: baseOrganization,
      created: false,
    })
    mockUpsertOrganizationPool.mockResolvedValue({
      pool: {
        id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One',
        description: 'Main pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
      created: false,
    })
    mockUpsertPoolTopologySnapshot.mockResolvedValue({
      pool_id: '44444444-4444-4444-4444-444444444444',
      version: 'v1:topology-updated',
      effective_from: '2026-01-01',
      effective_to: null,
      nodes_count: 0,
      edges_count: 0,
    })
    mockSyncOrganizationsCatalog.mockResolvedValue({
      stats: { created: 1, updated: 0, skipped: 0 },
      total_rows: 1,
    })
  })

  it('disables mutating controls for staff without active tenant', async () => {
    mockUseMe.mockReturnValue({ data: { is_staff: true } })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(screen.getByText('Mutating actions are disabled')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-add-org')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-edit-org')).toBeDisabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeDisabled()
  })

  it('keeps mutating controls enabled for non-staff without active tenant', async () => {
    mockUseMe.mockReturnValue({ data: { is_staff: false } })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-add-org')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeEnabled()
  })

  it('keeps mutating controls enabled for staff with tenant from server context', async () => {
    mockUseMe.mockReturnValue({ data: { is_staff: true } })
    mockUseMyTenants.mockReturnValue({
      data: {
        active_tenant_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        tenants: [{ id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', slug: 'default', name: 'Default', role: 'owner' }],
      },
    })

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(screen.getByTestId('pool-catalog-add-org')).toBeEnabled()
    expect(screen.getByTestId('pool-catalog-sync-orgs')).toBeEnabled()
  })

  it('creates organization via drawer and reloads catalog', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockResolvedValueOnce({
      organization: {
        ...baseOrganization,
        id: '55555555-5555-5555-5555-555555555555',
        inn: '730000000999',
        name: 'Created Org',
      },
      created: true,
    })
    mockListOrganizations
      .mockResolvedValueOnce([baseOrganization])
      .mockResolvedValueOnce([
        baseOrganization,
        {
          ...baseOrganization,
          id: '55555555-5555-5555-5555-555555555555',
          inn: '730000000999',
          name: 'Created Org',
        },
      ])

    renderPage()

    expect(await screen.findByText('Org One')).toBeInTheDocument()
    await user.click(screen.getByTestId('pool-catalog-add-org'))

    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000999')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Created Org')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(mockUpsertOrganization).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganization).toHaveBeenCalledWith(
      expect.objectContaining({
        inn: '730000000999',
        name: 'Created Org',
      })
    )
    await waitFor(() => expect(mockListOrganizations).toHaveBeenCalledTimes(2))
  }, 15000)

  it('creates pool via drawer and reloads pools list', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganizationPool.mockResolvedValueOnce({
      pool: {
        id: '66666666-6666-6666-6666-666666666666',
        code: 'pool-2',
        name: 'Pool Two',
        description: 'Second pool',
        is_active: true,
        metadata: {},
        updated_at: '2026-01-01T00:00:00Z',
      },
      created: true,
    })
    mockListOrganizationPools
      .mockResolvedValueOnce([
        {
          id: '44444444-4444-4444-4444-444444444444',
          code: 'pool-1',
          name: 'Pool One',
          description: 'Main pool',
          is_active: true,
          metadata: {},
          updated_at: '2026-01-01T00:00:00Z',
        },
      ])
      .mockResolvedValueOnce([
        {
          id: '44444444-4444-4444-4444-444444444444',
          code: 'pool-1',
          name: 'Pool One',
          description: 'Main pool',
          is_active: true,
          metadata: {},
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: '66666666-6666-6666-6666-666666666666',
          code: 'pool-2',
          name: 'Pool Two',
          description: 'Second pool',
          is_active: true,
          metadata: {},
          updated_at: '2026-01-01T00:00:00Z',
        },
      ])

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-pool'))
    await user.type(screen.getByLabelText('Code'), 'pool-2')
    await user.type(screen.getByLabelText('Name'), 'Pool Two')
    await user.type(screen.getByLabelText('Description'), 'Second pool')
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'pool-2',
        name: 'Pool Two',
      })
    )
    await waitFor(() => expect(mockListOrganizationPools.mock.calls.length).toBeGreaterThanOrEqual(2))
  }, 15000)

  it('edits selected pool via drawer and sends pool_id in upsert payload', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-edit-pool'))
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Pool One Updated')
    await user.click(screen.getByTestId('pool-catalog-save-pool'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: '44444444-4444-4444-4444-444444444444',
        code: 'pool-1',
        name: 'Pool One Updated',
      })
    )
  }, 15000)

  it('deactivates selected pool via toggle action', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-toggle-pool-active'))

    await waitFor(() => expect(mockUpsertOrganizationPool).toHaveBeenCalledTimes(1))
    expect(mockUpsertOrganizationPool).toHaveBeenCalledWith(
      expect.objectContaining({
        pool_id: '44444444-4444-4444-4444-444444444444',
        is_active: false,
      })
    )
  }, 15000)

  it('blocks topology save when preflight validation fails and keeps form input', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    expect(await screen.findByText('Preflight validation failed')).toBeInTheDocument()
    expect(await screen.findByText('Добавьте хотя бы один topology node.')).toBeInTheDocument()
    expect(mockUpsertPoolTopologySnapshot).not.toHaveBeenCalled()
  }, 15000)

  it('blocks topology save when edge document_policy JSON is invalid', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(await screen.findByText('Org Two')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    await user.click(screen.getByTestId('pool-catalog-topology-add-edge'))

    const topologyCard = screen.getByText('Topology snapshot editor').closest('.ant-card')
    expect(topologyCard).toBeTruthy()

    const selectors = topologyCard?.querySelectorAll('.ant-select .ant-select-selector')
    expect(selectors?.length).toBeGreaterThanOrEqual(4)
    fireEvent.mouseDown(selectors?.[0] as Element)
    await selectDropdownOption('Org One (730000000001)')

    fireEvent.mouseDown(selectors?.[1] as Element)
    await selectDropdownOption('Org Two (730000000002)')

    const rootSwitch = topologyCard?.querySelector('button[role="switch"]')
    expect(rootSwitch).toBeTruthy()
    fireEvent.click(rootSwitch as Element)

    fireEvent.mouseDown(selectors?.[2] as Element)
    await selectDropdownOption('Org One (730000000001)')
    fireEvent.mouseDown(selectors?.[3] as Element)
    await selectDropdownOption('Org Two (730000000002)')

    const edgePolicyInput = screen.getByTestId('pool-catalog-topology-edge-policy-0')
    await user.click(edgePolicyInput)
    await user.clear(edgePolicyInput)
    await user.paste('{invalid-json')
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    expect(await screen.findByText('Preflight validation failed')).toBeInTheDocument()
    expect(
      await screen.findByText('Edge #1: document_policy должен быть валидным JSON.')
    ).toBeInTheDocument()
    expect(mockUpsertPoolTopologySnapshot).not.toHaveBeenCalled()
  }, 15000)

  it('includes edge document_policy in topology upsert payload after preflight', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockListOrganizations.mockResolvedValue([baseOrganization, secondOrganization])

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()
    expect(await screen.findByText('Org Two')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))
    await user.click(screen.getByTestId('pool-catalog-topology-add-edge'))

    const topologyCard = screen.getByText('Topology snapshot editor').closest('.ant-card')
    expect(topologyCard).toBeTruthy()

    const selectors = topologyCard?.querySelectorAll('.ant-select .ant-select-selector')
    expect(selectors?.length).toBeGreaterThanOrEqual(4)
    fireEvent.mouseDown(selectors?.[0] as Element)
    await selectDropdownOption('Org One (730000000001)')
    fireEvent.mouseDown(selectors?.[1] as Element)
    await selectDropdownOption('Org Two (730000000002)')

    const rootSwitch = topologyCard?.querySelector('button[role="switch"]')
    expect(rootSwitch).toBeTruthy()
    fireEvent.click(rootSwitch as Element)

    fireEvent.mouseDown(selectors?.[2] as Element)
    await selectDropdownOption('Org One (730000000001)')
    fireEvent.mouseDown(selectors?.[3] as Element)
    await selectDropdownOption('Org Two (730000000002)')

    const edgePolicyInput = screen.getByTestId('pool-catalog-topology-edge-policy-0')
    await user.click(edgePolicyInput)
    await user.clear(edgePolicyInput)
    await user.paste(
      '{"version":"document_policy.v1","chains":[{"chain_id":"sale_chain","documents":[{"document_id":"sale","entity_name":"Document_Sales","document_role":"sale"}]}]}'
    )
    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-initial',
        edges: [
          expect.objectContaining({
            parent_organization_id: '11111111-1111-1111-1111-111111111111',
            child_organization_id: '77777777-7777-7777-7777-777777777777',
            metadata: {
              document_policy: expect.objectContaining({
                version: 'document_policy.v1',
              }),
            },
          }),
        ],
      })
    )
  }, 15000)

  it('sends topology version token and shows conflict error without clearing form data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertPoolTopologySnapshot.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Topology Version Conflict',
          status: 409,
          detail: 'stale version token',
          code: 'TOPOLOGY_VERSION_CONFLICT',
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-topology-add-node'))

    const topologyCard = screen.getByText('Topology snapshot editor').closest('.ant-card')
    expect(topologyCard).toBeTruthy()

    const nodeSelector = topologyCard?.querySelector('.ant-select .ant-select-selector')
    expect(nodeSelector).toBeTruthy()
    fireEvent.mouseDown(nodeSelector as Element)
    fireEvent.click(await screen.findByText('Org One (730000000001)'))

    const rootSwitch = topologyCard?.querySelector('button[role="switch"]')
    expect(rootSwitch).toBeTruthy()
    fireEvent.click(rootSwitch as Element)

    await user.click(screen.getByTestId('pool-catalog-topology-save'))

    await waitFor(() => expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledTimes(1))
    expect(mockUpsertPoolTopologySnapshot).toHaveBeenCalledWith(
      '44444444-4444-4444-4444-444444444444',
      expect.objectContaining({
        version: 'v1:topology-initial',
      })
    )
    expect(
      await screen.findByText(
        'Топология уже была изменена другим оператором. Обновите граф и повторите сохранение.'
      )
    ).toBeInTheDocument()
    expect(screen.getAllByText('Org One (730000000001)').length).toBeGreaterThan(0)
  }, 15000)

  it('shows mapped backend domain error for organization upsert and keeps form data', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockRejectedValueOnce({
      response: {
        data: {
          success: false,
          error: {
            code: 'DATABASE_ALREADY_LINKED',
            message: 'Database is already linked',
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-org'))
    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000111')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Mapped Error Org')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Выбранная база уже привязана к другой организации.')).toBeInTheDocument()
    expect(screen.getByLabelText('INN')).toHaveValue('730000000111')
    expect(screen.getByLabelText('Name')).toHaveValue('Mapped Error Org')
  }, 15000)

  it('applies field-level serializer errors to form fields on upsert', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockRejectedValueOnce({
      response: {
        data: {
          success: false,
          error: {
            inn: ['ИНН уже существует'],
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-org'))
    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000001')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Duplicate Org')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Проверьте корректность заполнения полей.')).toBeInTheDocument()
    expect(await screen.findByText('ИНН уже существует')).toBeInTheDocument()
    expect(screen.getByLabelText('INN')).toHaveValue('730000000001')
  }, 15000)

  it('applies field-level validation errors from problem+json payload on upsert', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockUpsertOrganization.mockRejectedValueOnce({
      response: {
        data: {
          type: 'about:blank',
          title: 'Validation Error',
          status: 400,
          detail: 'Organization payload validation failed.',
          code: 'VALIDATION_ERROR',
          errors: {
            inn: ['ИНН уже существует'],
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-add-org'))
    await user.clear(screen.getByLabelText('INN'))
    await user.type(screen.getByLabelText('INN'), '730000000001')
    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Duplicate Org')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Проверьте корректность данных.')).toBeInTheDocument()
    expect(await screen.findByText('ИНН уже существует')).toBeInTheDocument()
    expect(screen.getByLabelText('INN')).toHaveValue('730000000001')
  }, 15000)

  it('blocks sync submit when preflight validation fails', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"name":"No inn"}]}' },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Строка 1: поле inn обязательно.')).toBeInTheDocument()
    expect(mockSyncOrganizationsCatalog).not.toHaveBeenCalled()
  }, 15000)

  it('blocks sync submit when payload exceeds 1000 rows', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    const payload = JSON.stringify({
      rows: Array.from({ length: 1001 }, (_, index) => ({
        inn: `7300${String(index).padStart(8, '0')}`.slice(0, 12),
        name: `Org ${index + 1}`,
      })),
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: payload },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Превышен лимит batch: максимум 1000 строк.')).toBeInTheDocument()
    expect(mockSyncOrganizationsCatalog).not.toHaveBeenCalled()
  }, 15000)

  it('shows field-level backend validation errors in sync modal', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    mockSyncOrganizationsCatalog.mockRejectedValueOnce({
      response: {
        data: {
          success: false,
          error: {
            rows: ['Некорректный формат строки'],
          },
        },
      },
    })

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"inn":"730000000123","name":"Org"}]}' },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    expect(await screen.findByText('Проверьте корректность заполнения полей.')).toBeInTheDocument()
    expect(await screen.findByText('rows: Некорректный формат строки')).toBeInTheDocument()
  }, 15000)

  it('runs sync with valid payload and shows stats', async () => {
    localStorage.setItem('active_tenant_id', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    const user = userEvent.setup()

    renderPage()
    expect(await screen.findByText('Org One')).toBeInTheDocument()

    await user.click(screen.getByTestId('pool-catalog-sync-orgs'))
    fireEvent.change(screen.getByTestId('pool-catalog-sync-input'), {
      target: { value: '{"rows":[{"inn":"730000000123","name":"Synced Org","status":"ACTIVE"}]}' },
    })
    await user.click(screen.getByRole('button', { name: 'Run sync' }))

    await waitFor(() => expect(mockSyncOrganizationsCatalog).toHaveBeenCalledTimes(1))
    expect(mockSyncOrganizationsCatalog).toHaveBeenCalledWith({
      rows: [
        {
          inn: '730000000123',
          name: 'Synced Org',
          status: 'active',
        },
      ],
    })
    expect(await screen.findByText('Sync completed')).toBeInTheDocument()
    expect(screen.getByText('total_rows:')).toBeInTheDocument()
  }, 15000)
})
