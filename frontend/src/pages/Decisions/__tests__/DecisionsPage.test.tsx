import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockGetDecisionsCollection = vi.fn()
const mockGetDecisionsDetail = vi.fn()
const mockPostDecisionsCollection = vi.fn()
const mockUseDatabases = vi.fn()

vi.mock('../../../api/generated/v2/v2', () => ({
  getV2: () => ({
    getDecisionsCollection: (...args: unknown[]) => mockGetDecisionsCollection(...args),
    getDecisionsDetail: (...args: unknown[]) => mockGetDecisionsDetail(...args),
    postDecisionsCollection: (...args: unknown[]) => mockPostDecisionsCollection(...args),
  }),
}))

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: (...args: unknown[]) => mockUseDatabases(...args),
}))

vi.mock('../../../components/code/LazyJsonCodeEditor', () => ({
  LazyJsonCodeEditor: ({ value }: { value?: string }) => (
    <pre data-testid="json-editor-preview">{value}</pre>
  ),
  LazyJsonCodeEditorFormField: ({
    value,
    onChange,
  }: {
    value?: string
    onChange?: (value: string) => void
  }) => (
    <textarea
      aria-label="document-policy-json"
      value={value ?? ''}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}))

const defaultMetadataContext = {
  database_id: 'db-2',
  snapshot_id: 'snapshot-1',
  source: 'db',
  fetched_at: '2026-03-10T12:00:00Z',
  catalog_version: 'v1:shared',
  config_name: 'shared-profile',
  config_version: '8.3.24',
  extensions_fingerprint: '',
  metadata_hash: 'a'.repeat(64),
  resolution_mode: 'shared_scope',
  is_shared_snapshot: true,
  provenance_database_id: 'db-1',
  provenance_confirmed_at: '2026-03-10T11:00:00Z',
  documents: [],
}

const defaultDecision = {
  id: 'decision-version-2',
  decision_table_id: 'services-publication-policy',
  decision_key: 'document_policy',
  decision_revision: 2,
  name: 'Services publication policy',
  description: 'Publishes service documents',
  inputs: [],
  outputs: [],
  rules: [
    {
      rule_id: 'default',
      priority: 0,
      conditions: {},
      outputs: {
        document_policy: {
          version: 'document_policy.v1',
          chains: [
            {
              chain_id: 'sale_chain',
              documents: [
                {
                  document_id: 'sale',
                  entity_name: 'Document_Sales',
                  document_role: 'base',
                  invoice_mode: 'required',
                  field_mapping: {
                    Amount: 'allocation.amount',
                  },
                  table_parts_mapping: {},
                  link_rules: {},
                },
              ],
            },
          ],
        },
      },
    },
  ],
  hit_policy: 'first_match',
  validation_mode: 'fail_closed',
  is_active: true,
  parent_version: 'decision-version-1',
  metadata_context: {
    snapshot_id: 'snapshot-1',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    extensions_fingerprint: '',
    metadata_hash: 'a'.repeat(64),
    resolution_mode: 'shared_scope',
    is_shared_snapshot: true,
    provenance_database_id: 'db-1',
    provenance_confirmed_at: '2026-03-10T11:00:00Z',
  },
  metadata_compatibility: {
    status: 'compatible',
    reason: null,
    is_compatible: true,
  },
  created_at: '2026-03-10T12:00:00Z',
  updated_at: '2026-03-10T12:00:00Z',
}

const { DecisionsPage } = await import('../DecisionsPage')

function renderPage(path = '/decisions') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <Routes>
        <Route
          path="/decisions"
          element={(
            <AntApp>
              <DecisionsPage />
            </AntApp>
          )}
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('DecisionsPage', () => {
  beforeEach(() => {
    mockGetDecisionsCollection.mockReset()
    mockGetDecisionsDetail.mockReset()
    mockPostDecisionsCollection.mockReset()
    mockUseDatabases.mockReset()

    mockUseDatabases.mockReturnValue({
      data: {
        databases: [
          {
            id: 'db-2',
            name: 'Target DB',
            base_name: 'shared-profile',
            version: '8.3.24',
          },
        ],
      },
      isLoading: false,
    })

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [defaultDecision],
      count: 1,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockResolvedValue({
      decision: defaultDecision,
      metadata_context: defaultMetadataContext,
    })
    mockPostDecisionsCollection.mockResolvedValue({
      decision: {
        ...defaultDecision,
        id: 'decision-version-3',
        decision_revision: 3,
        parent_version: defaultDecision.id,
      },
      metadata_context: defaultMetadataContext,
    })
  })

  it('renders decision lifecycle list with metadata context and selected detail', async () => {
    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(screen.getByText('/decisions is the primary surface for document_policy authoring.')).toBeInTheDocument()
    expect(screen.getByText('shared-profile')).toBeInTheDocument()
    expect(screen.getByText('shared_scope')).toBeInTheDocument()
    expect(screen.getByText('Services publication policy')).toBeInTheDocument()
    expect(screen.getByText('snapshot-1')).toBeInTheDocument()
    expect(screen.getAllByText('compatible').length).toBeGreaterThan(0)
    expect(screen.getByText('services-publication-policy')).toBeInTheDocument()
  })

  it('creates document policy revision from structured builder fields', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Decision Policy Library')
    await user.click(screen.getByRole('button', { name: 'New policy' }))
    fireEvent.change(screen.getByLabelText('Decision table ID'), { target: { value: 'policy-new' } })
    fireEvent.change(screen.getByLabelText('Decision name'), { target: { value: 'New policy' } })

    await user.click(screen.getByRole('button', { name: 'Add chain' }))
    fireEvent.change(screen.getByLabelText('Chain 1 ID'), { target: { value: 'sale_chain' } })
    await user.click(screen.getByRole('button', { name: 'Add document to chain 1' }))
    fireEvent.change(screen.getByLabelText('Chain 1 document 1 ID'), { target: { value: 'sale' } })
    fireEvent.change(screen.getByLabelText('Chain 1 document 1 entity'), { target: { value: 'Document_Sales' } })
    fireEvent.change(screen.getByLabelText('Chain 1 document 1 role'), { target: { value: 'base' } })
    await user.click(screen.getByRole('button', { name: 'Add field mapping to chain 1 document 1' }))
    fireEvent.change(screen.getByLabelText('Chain 1 document 1 field mapping 1 target'), { target: { value: 'Amount' } })
    fireEvent.change(screen.getByLabelText('Chain 1 document 1 field mapping 1 source'), { target: { value: 'allocation.amount' } })

    await user.click(screen.getByRole('button', { name: 'Save decision' }))

    await waitFor(() => {
      expect(mockPostDecisionsCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          database_id: 'db-2',
          decision_key: 'document_policy',
          decision_table_id: 'policy-new',
          name: 'New policy',
          is_active: true,
          rules: [
            expect.objectContaining({
              outputs: {
                document_policy: {
                  version: 'document_policy.v1',
                  chains: [
                    {
                      chain_id: 'sale_chain',
                      documents: [
                        expect.objectContaining({
                          document_id: 'sale',
                          entity_name: 'Document_Sales',
                          document_role: 'base',
                          field_mapping: {
                            Amount: 'allocation.amount',
                          },
                        }),
                      ],
                    },
                  ],
                },
              },
            }),
          ],
        }),
        expect.anything(),
      )
    })
  }, 10000)

  it('supports raw import, revise and deactivate flows through decision revisions', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Decision Policy Library')

    await user.click(screen.getByRole('button', { name: 'Import legacy policy' }))
    fireEvent.change(screen.getByLabelText('Decision table ID'), { target: { value: 'policy-imported' } })
    fireEvent.change(screen.getByLabelText('Decision name'), { target: { value: 'Imported policy' } })
    await user.click(screen.getByRole('tab', { name: 'Raw JSON' }))
    fireEvent.change(screen.getByLabelText('document-policy-json'), {
      target: {
        value: '{"version":"document_policy.v1","chains":[{"chain_id":"imported","documents":[{"document_id":"sale","entity_name":"Document_Sales","document_role":"base","field_mapping":{"Amount":"allocation.amount"},"table_parts_mapping":{},"link_rules":{}}]}]}',
      },
    })
    await user.click(screen.getByRole('button', { name: 'Save decision' }))

    await waitFor(() => {
      expect(mockPostDecisionsCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          decision_table_id: 'policy-imported',
          name: 'Imported policy',
          parent_version_id: undefined,
        }),
        expect.anything(),
      )
    })

    mockPostDecisionsCollection.mockClear()

    await user.click(screen.getByRole('button', { name: 'Revise selected decision' }))
    const reviseNameInput = screen.getByLabelText('Decision name')
    fireEvent.change(reviseNameInput, { target: { value: 'Services publication policy v3' } })
    await user.click(screen.getByRole('button', { name: 'Save decision' }))

    await waitFor(() => {
      expect(mockPostDecisionsCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          parent_version_id: 'decision-version-2',
          name: 'Services publication policy v3',
          is_active: true,
        }),
        expect.anything(),
      )
    })

    mockPostDecisionsCollection.mockClear()

    await user.click(screen.getByRole('button', { name: 'Deactivate selected decision' }))

    await waitFor(() => {
      expect(mockPostDecisionsCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          parent_version_id: 'decision-version-2',
          is_active: false,
        }),
        expect.anything(),
      )
    })
  }, 10000)
})
