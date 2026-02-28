import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import { PoolMasterDataPage } from '../PoolMasterDataPage'

const mockListMasterDataParties = vi.fn()
const mockUpsertMasterDataParty = vi.fn()
const mockListMasterDataItems = vi.fn()
const mockUpsertMasterDataItem = vi.fn()
const mockListMasterDataContracts = vi.fn()
const mockUpsertMasterDataContract = vi.fn()
const mockListMasterDataTaxProfiles = vi.fn()
const mockUpsertMasterDataTaxProfile = vi.fn()
const mockListMasterDataBindings = vi.fn()
const mockUpsertMasterDataBinding = vi.fn()
const mockListPoolTargetDatabases = vi.fn()

vi.mock('reactflow', () => ({
  default: ({ children }: { children?: ReactNode }) => <div data-testid="mock-reactflow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listMasterDataParties: (...args: unknown[]) => mockListMasterDataParties(...args),
  upsertMasterDataParty: (...args: unknown[]) => mockUpsertMasterDataParty(...args),
  listMasterDataItems: (...args: unknown[]) => mockListMasterDataItems(...args),
  upsertMasterDataItem: (...args: unknown[]) => mockUpsertMasterDataItem(...args),
  listMasterDataContracts: (...args: unknown[]) => mockListMasterDataContracts(...args),
  upsertMasterDataContract: (...args: unknown[]) => mockUpsertMasterDataContract(...args),
  listMasterDataTaxProfiles: (...args: unknown[]) => mockListMasterDataTaxProfiles(...args),
  upsertMasterDataTaxProfile: (...args: unknown[]) => mockUpsertMasterDataTaxProfile(...args),
  listMasterDataBindings: (...args: unknown[]) => mockListMasterDataBindings(...args),
  upsertMasterDataBinding: (...args: unknown[]) => mockUpsertMasterDataBinding(...args),
  listPoolTargetDatabases: (...args: unknown[]) => mockListPoolTargetDatabases(...args),
}))

function renderPage() {
  return render(
    <AntApp>
      <PoolMasterDataPage />
    </AntApp>
  )
}

describe('PoolMasterDataPage', () => {
  beforeEach(() => {
    mockListMasterDataParties.mockReset()
    mockUpsertMasterDataParty.mockReset()
    mockListMasterDataItems.mockReset()
    mockUpsertMasterDataItem.mockReset()
    mockListMasterDataContracts.mockReset()
    mockUpsertMasterDataContract.mockReset()
    mockListMasterDataTaxProfiles.mockReset()
    mockUpsertMasterDataTaxProfile.mockReset()
    mockListMasterDataBindings.mockReset()
    mockUpsertMasterDataBinding.mockReset()
    mockListPoolTargetDatabases.mockReset()

    mockListMasterDataParties.mockResolvedValue({
      parties: [
        {
          id: 'party-1',
          tenant_id: 'tenant-1',
          canonical_id: 'party-001',
          name: 'Party One',
          full_name: 'Party One LLC',
          inn: '730000000001',
          kpp: '',
          is_our_organization: true,
          is_counterparty: true,
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      meta: { limit: 100, offset: 0, total: 1 },
    })
    mockListMasterDataItems.mockResolvedValue({
      items: [],
      meta: { limit: 100, offset: 0, total: 0 },
    })
    mockListMasterDataContracts.mockResolvedValue({
      contracts: [],
      meta: { limit: 100, offset: 0, total: 0 },
    })
    mockListMasterDataTaxProfiles.mockResolvedValue({
      tax_profiles: [],
      meta: { limit: 100, offset: 0, total: 0 },
    })
    mockListMasterDataBindings.mockResolvedValue({
      bindings: [],
      meta: { limit: 200, offset: 0, total: 0 },
    })
    mockListPoolTargetDatabases.mockResolvedValue([
      { id: 'db-1', name: 'Main DB' },
    ])
  })

  it('renders workspace tabs and loads default Party tab list', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Pool Master Data')).toBeInTheDocument()
    expect(await screen.findByText('Party One')).toBeInTheDocument()
    expect(mockListMasterDataParties).toHaveBeenCalledWith({
      query: undefined,
      role: undefined,
      limit: 100,
      offset: 0,
    })

    await user.click(screen.getByRole('tab', { name: 'Item' }))
    await waitFor(() => expect(mockListMasterDataItems).toHaveBeenCalled())
  })

  it('blocks Party save when no role is selected', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Party One')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add Party' }))
    await user.type(screen.getByLabelText('Canonical ID'), 'party-002')
    await user.type(screen.getByLabelText('Name'), 'Party Two')
    await user.click(screen.getByRole('checkbox', { name: 'Role: counterparty' }))
    await user.click(screen.getByRole('button', { name: 'OK' }))

    expect(
      await screen.findByText('Party должен иметь минимум одну роль: organization или counterparty.')
    ).toBeInTheDocument()
    expect(mockUpsertMasterDataParty).not.toHaveBeenCalled()
  }, 15000)
})
