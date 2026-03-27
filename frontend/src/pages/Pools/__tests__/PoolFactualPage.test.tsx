import { StrictMode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter, useLocation } from 'react-router-dom'

import type { OrganizationPool } from '../../../api/intercompanyPools'
import { PoolFactualPage } from '../PoolFactualPage'
import { resetQueryClient } from '../../../lib/queryClient'
import { buildPoolFactualRoute } from '../routes'


const mockListOrganizationPools = vi.fn()

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
}))

function buildPool(overrides: Partial<OrganizationPool> = {}): OrganizationPool {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    code: 'pool-alpha',
    name: 'Pool Alpha',
    description: 'Primary factual pool',
    is_active: true,
    metadata: {},
    updated_at: '2026-03-27T00:00:00Z',
    ...overrides,
  }
}

function renderPage(initialEntry = '/pools/factual', options?: { strict?: boolean }) {
  const tree = (
    <MemoryRouter initialEntries={[initialEntry]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <AntApp>
        <PoolFactualPage />
        <LocationProbe />
      </AntApp>
    </MemoryRouter>
  )

  return render(options?.strict ? <StrictMode>{tree}</StrictMode> : tree)
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="pool-factual-location">{`${location.pathname}${location.search}`}</div>
}

describe('PoolFactualPage', () => {
  beforeEach(() => {
    resetQueryClient()
    mockListOrganizationPools.mockReset()
  })

  it('renders factual summary, settlement, drill-down, and review sections for the selected pool', async () => {
    mockListOrganizationPools.mockResolvedValue([
      buildPool(),
      buildPool({
        id: '22222222-2222-2222-2222-222222222222',
        code: 'pool-beta',
        name: 'Pool Beta',
      }),
    ])

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&run=run-001&focus=settlement&detail=1')

    await screen.findByText('Factual operator workspace')
    await waitFor(() => expect(screen.getByText('Quarter summary')).toBeInTheDocument())

    expect(screen.getByText('Batch settlement')).toBeInTheDocument()
    expect(screen.getByText('Edge drill-down')).toBeInTheDocument()
    expect(screen.getByText('Manual review queue')).toBeInTheDocument()
    expect(screen.getByText('Linked run: run-001')).toBeInTheDocument()
    expect(screen.getByText('Run-linked settlement handoff')).toBeInTheDocument()
    expect(screen.getByText("Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')")).toBeInTheDocument()
    expect(screen.getByText("Document_КорректировкаРеализации(guid'pool-alpha-late')")).toBeInTheDocument()
  })

  it('updates the factual route query when the operator selects a pool from the compact master pane', async () => {
    const user = userEvent.setup()
    mockListOrganizationPools.mockResolvedValue([
      buildPool(),
      buildPool({
        id: '22222222-2222-2222-2222-222222222222',
        code: 'pool-beta',
        name: 'Pool Beta',
      }),
    ])

    renderPage('/pools/factual')

    await screen.findByText('Pool Alpha')
    await user.click(screen.getByRole('button', { name: 'Open factual workspace for Pool Beta' }))

    await waitFor(() => {
      expect(screen.getByTestId('pool-factual-location').textContent).toContain('/pools/factual?pool=22222222-2222-2222-2222-222222222222&detail=1')
    })
    expect(screen.getByText('Quarter summary')).toBeInTheDocument()
  })

  it('keeps execution controls out of the factual workspace', async () => {
    mockListOrganizationPools.mockResolvedValue([buildPool()])

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&detail=1')

    await screen.findByText('Factual operator workspace')

    expect(screen.getByText('Quarter summary')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open Pool Runs' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create / Upsert Run' })).not.toBeInTheDocument()
    expect(screen.queryByText('Create Run')).not.toBeInTheDocument()
  })

  it('shows reason-specific review actions and updates queue state inside the factual workspace', async () => {
    const user = userEvent.setup()
    mockListOrganizationPools.mockResolvedValue([buildPool()])

    renderPage('/pools/factual?pool=11111111-1111-1111-1111-111111111111&focus=review&detail=1')

    await screen.findByText('Manual review queue')

    const unattributedRow = screen
      .getByText("Document_РеализацияТоваровУслуг(guid'pool-alpha-sale')")
      .closest('tr')
    expect(unattributedRow).not.toBeNull()
    expect(within(unattributedRow as HTMLElement).getByRole('button', { name: 'Attribute review item unattributed-pool-alpha' })).toBeInTheDocument()
    expect(within(unattributedRow as HTMLElement).queryByRole('button', { name: 'Reconcile review item unattributed-pool-alpha' })).not.toBeInTheDocument()

    const lateCorrectionRow = screen
      .getByText("Document_КорректировкаРеализации(guid'pool-alpha-late')")
      .closest('tr')
    expect(lateCorrectionRow).not.toBeNull()
    expect(within(lateCorrectionRow as HTMLElement).getByRole('button', { name: 'Reconcile review item late-correction-pool-alpha' })).toBeInTheDocument()
    expect(within(lateCorrectionRow as HTMLElement).queryByRole('button', { name: 'Attribute review item late-correction-pool-alpha' })).not.toBeInTheDocument()

    await user.click(within(unattributedRow as HTMLElement).getByRole('button', { name: 'Attribute review item unattributed-pool-alpha' }))
    await waitFor(() => {
      expect(within(unattributedRow as HTMLElement).getByText('attributed')).toBeInTheDocument()
    })

    await user.click(within(lateCorrectionRow as HTMLElement).getByRole('button', { name: 'Reconcile review item late-correction-pool-alpha' }))
    await waitFor(() => {
      expect(within(lateCorrectionRow as HTMLElement).getByText('reconciled')).toBeInTheDocument()
    })
  })

  it('builds a focus-aware factual route for settlement handoff from run report', () => {
    expect(
      buildPoolFactualRoute({
        poolId: 'pool-1',
        runId: 'run-1',
        focus: 'settlement',
        detail: true,
      })
    ).toBe('/pools/factual?pool=pool-1&run=run-1&focus=settlement&detail=1')
  })
})
