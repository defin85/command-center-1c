import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App as AntApp } from 'antd'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mockGetDecisionsCollection = vi.fn()
const mockGetDecisionsDetail = vi.fn()
const mockPostDecisionsCollection = vi.fn()
const mockListOrganizationPools = vi.fn()
const mockGetPoolGraph = vi.fn()
const mockMigratePoolEdgeDocumentPolicy = vi.fn()
const mockUseDatabases = vi.fn()
const mockUseDatabaseMetadataManagement = vi.fn()

vi.mock('../../../api/generated/v2/v2', () => ({
  getV2: () => ({
    getDecisionsCollection: (...args: unknown[]) => mockGetDecisionsCollection(...args),
    getDecisionsDetail: (...args: unknown[]) => mockGetDecisionsDetail(...args),
    postDecisionsCollection: (...args: unknown[]) => mockPostDecisionsCollection(...args),
  }),
}))

vi.mock('../../../api/queries/databases', () => ({
  useDatabases: (...args: unknown[]) => mockUseDatabases(...args),
  useDatabaseMetadataManagement: (...args: unknown[]) => mockUseDatabaseMetadataManagement(...args),
}))

vi.mock('../../../api/intercompanyPools', () => ({
  listOrganizationPools: (...args: unknown[]) => mockListOrganizationPools(...args),
  getPoolGraph: (...args: unknown[]) => mockGetPoolGraph(...args),
  migratePoolEdgeDocumentPolicy: (...args: unknown[]) => mockMigratePoolEdgeDocumentPolicy(...args),
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

const defaultMetadataManagementState = {
  database_id: 'db-2',
  configuration_profile: {
    status: 'verified',
    config_name: 'shared-profile',
    config_version: '8.3.24',
    config_generation_id: 'cfg-gen-1',
    config_root_name: 'Accounting',
    config_vendor: '1C',
    config_name_source: 'manual',
    verification_operation_id: '',
    verified_at: '2026-03-10T11:00:00Z',
    generation_probe_requested_at: null,
    generation_probe_checked_at: null,
    observed_metadata_hash: 'a'.repeat(64),
    canonical_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
    reverify_available: true,
    reverify_blocker_code: '',
    reverify_blocker_message: '',
    reverify_blocking_action: '',
  },
  metadata_snapshot: {
    status: 'available',
    missing_reason: '',
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
    observed_metadata_hash: 'a'.repeat(64),
    publication_drift: false,
  },
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

const defaultPool = {
  id: 'pool-1',
  code: 'pool-hardening',
  name: 'Workflow Pool',
  description: 'Workflow-centric pool',
  is_active: true,
  metadata: {},
  updated_at: '2026-03-10T12:00:00Z',
}

const defaultPoolGraph = {
  pool_id: defaultPool.id,
  date: '2026-03-10',
  version: 'topology:v1',
  nodes: [
    {
      node_version_id: 'node-root',
      organization_id: 'org-root',
      inn: '730000000001',
      name: 'Root Org',
      is_root: true,
      metadata: {},
    },
    {
      node_version_id: 'node-target',
      organization_id: 'org-target',
      inn: '730000000002',
      name: 'Target Org',
      is_root: false,
      metadata: {},
    },
  ],
  edges: [
    {
      edge_version_id: 'edge-v1',
      parent_node_version_id: 'node-root',
      child_node_version_id: 'node-target',
      weight: '1.0',
      min_amount: null,
      max_amount: null,
      metadata: {
        document_policy: {
          version: 'document_policy.v1',
          chains: [],
        },
      },
    },
    {
      edge_version_id: 'edge-without-policy',
      parent_node_version_id: 'node-root',
      child_node_version_id: 'node-target',
      weight: '1.0',
      min_amount: null,
      max_amount: null,
      metadata: {},
    },
  ],
}

function makeApiError(message: string, code = 'POOL_METADATA_FETCH_FAILED', status = 400) {
  return {
    message,
    response: {
      status,
      data: {
        error: {
          code,
          message,
        },
      },
    },
  }
}

function openSelect(testId: string) {
  const select = screen.getByTestId(testId)
  const trigger = select.querySelector('.ant-select-selector') as HTMLElement | null
  fireEvent.mouseDown(trigger ?? select)
}

function clearSelect(testId: string) {
  const select = screen.getByTestId(testId)
  fireEvent.mouseEnter(select)
  const clearButton = select.querySelector('.ant-select-clear') as HTMLElement | null
  expect(clearButton).toBeTruthy()
  fireEvent.mouseDown(clearButton as HTMLElement)
  fireEvent.click(clearButton as HTMLElement)
}

async function selectDropdownOption(label: string | RegExp) {
  const matcher = typeof label === 'string' ? label : (content: string) => label.test(content)
  const matches = await screen.findAllByText(matcher)
  const option = [...matches]
    .reverse()
    .find((node) => node.closest('.ant-select-item-option'))
  expect(option).toBeTruthy()
  fireEvent.click(option as Element)
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
    mockListOrganizationPools.mockReset()
    mockGetPoolGraph.mockReset()
    mockMigratePoolEdgeDocumentPolicy.mockReset()
    mockUseDatabases.mockReset()
    mockUseDatabaseMetadataManagement.mockReset()

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
    mockUseDatabaseMetadataManagement.mockReturnValue({
      data: defaultMetadataManagementState,
      isLoading: false,
      isError: false,
      error: null,
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
    mockListOrganizationPools.mockResolvedValue([defaultPool])
    mockGetPoolGraph.mockResolvedValue(defaultPoolGraph)
    mockMigratePoolEdgeDocumentPolicy.mockResolvedValue({
      decision: {
        ...defaultDecision,
        id: 'decision-version-imported',
        decision_revision: 4,
        name: 'Imported policy',
      },
      metadata_context: defaultMetadataContext,
      migration: {
        created: true,
        reused_existing_revision: false,
        binding_update_required: false,
        source: {
          source_path: 'edge.metadata.document_policy',
          pool_id: defaultPool.id,
          pool_code: defaultPool.code,
          edge_version_id: 'edge-v1',
        },
        decision_ref: {
          decision_id: 'decision-version-imported',
          decision_table_id: 'policy-imported',
          decision_revision: 4,
        },
      },
    })
  })

  it('renders decision lifecycle list with metadata context and selected detail', async () => {
    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(screen.getByText('/decisions is the primary surface for document_policy authoring.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open workflow catalog' })).toHaveAttribute('href', '/workflows')
    expect(screen.getByRole('link', { name: 'Open binding profile catalog' })).toHaveAttribute('href', '/pools/binding-profiles')
    expect(screen.getByText('shared-profile')).toBeInTheDocument()
    expect(screen.getByText('shared_scope')).toBeInTheDocument()
    expect(screen.getByText('Services publication policy')).toBeInTheDocument()
    expect(screen.getByText('snapshot-1')).toBeInTheDocument()
    expect(screen.getAllByText('compatible').length).toBeGreaterThan(0)
    expect(screen.getByText('services-publication-policy')).toBeInTheDocument()
    expect(await screen.findByText('Structured policy view')).toBeInTheDocument()
    expect(screen.getByText('Chain 1: sale_chain')).toBeInTheDocument()
    expect(screen.getByText('Document_Sales')).toBeInTheDocument()
    expect(screen.getByText('Amount')).toBeInTheDocument()
    expect(screen.getByText('allocation.amount')).toBeInTheDocument()
  })

  it('does not perform an unscoped bootstrap read before the default database selection resolves', async () => {
    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockGetDecisionsCollection).toHaveBeenCalledWith(
        { database_id: 'db-2' },
        { errorPolicy: 'page' },
      )
    })

    expect(
      mockGetDecisionsCollection.mock.calls.filter(
        ([query]) => JSON.stringify(query) === JSON.stringify({})
      ).length
    ).toBe(0)
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
        { errorPolicy: 'page' },
      )
    })
  }, 30000)

  it('imports a legacy edge policy through the pool migration API on /decisions', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Decision Policy Library')
    expect(mockListOrganizationPools).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Import legacy edge' }))

    expect(await screen.findByText('Import legacy edge policy')).toBeInTheDocument()
    await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(mockGetPoolGraph).toHaveBeenCalledWith(defaultPool.id))

    openSelect('decision-legacy-import-pool-select')
    await selectDropdownOption('Workflow Pool (pool-hardening)')

    openSelect('decision-legacy-import-edge-select')
    await selectDropdownOption(/Root Org -> Target Org \(edge-v1\)/)

    fireEvent.change(screen.getByLabelText('Decision table ID'), { target: { value: 'policy-imported' } })
    fireEvent.change(screen.getByLabelText('Decision name'), { target: { value: 'Imported policy' } })
    fireEvent.change(screen.getByLabelText('Decision description'), { target: { value: 'Imported from legacy edge' } })

    await user.click(screen.getByRole('button', { name: 'Import to /decisions' }))

    await waitFor(() => {
      expect(mockMigratePoolEdgeDocumentPolicy).toHaveBeenCalledWith(
        defaultPool.id,
        {
          edge_version_id: 'edge-v1',
          decision_table_id: 'policy-imported',
          name: 'Imported policy',
          description: 'Imported from legacy edge',
        },
      )
    })
    expect(mockPostDecisionsCollection).not.toHaveBeenCalled()
    const importAlert = (await screen.findByText('Imported to /decisions')).closest('[role="alert"]')
    expect(importAlert).toBeTruthy()
    expect(within(importAlert as HTMLElement).getByText('Imported to /decisions')).toBeInTheDocument()
    expect(screen.getByText('Source: edge.metadata.document_policy (edge-v1)')).toBeInTheDocument()
    expect(screen.getByText('Decision ref: policy-imported r4')).toBeInTheDocument()
    expect(screen.getByText('Affected workflow bindings were updated automatically.')).toBeInTheDocument()
  }, 30000)

  it('falls back to unscoped decisions read when selected database metadata state is unavailable', async () => {
    mockUseDatabaseMetadataManagement.mockReturnValue({
      data: {
        ...defaultMetadataManagementState,
        configuration_profile: {
          ...defaultMetadataManagementState.configuration_profile,
          status: 'missing',
          config_name: '',
          config_version: '',
          reverify_available: false,
          reverify_blocker_code: 'IBCMD_CONNECTION_PROFILE_REQUIRED',
          reverify_blocker_message: 'Configure IBCMD connection profile',
          reverify_blocking_action: 'configure_ibcmd_connection_profile',
        },
        metadata_snapshot: {
          ...defaultMetadataManagementState.metadata_snapshot,
          status: 'missing',
          missing_reason: 'configuration_profile_unavailable',
          snapshot_id: '',
          source: '',
          fetched_at: null,
          catalog_version: '',
          config_name: '',
          config_version: '',
          metadata_hash: '',
          resolution_mode: '',
          is_shared_snapshot: false,
          provenance_database_id: '',
          provenance_confirmed_at: null,
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    mockGetDecisionsCollection.mockReset()
    mockGetDecisionsDetail.mockReset()
    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [defaultDecision],
      count: 1,
    })
    mockGetDecisionsDetail.mockResolvedValue({
      decision: defaultDecision,
    })

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockGetDecisionsCollection).toHaveBeenCalledWith(
        {},
        { errorPolicy: 'page' },
      )
    })
    expect(
      mockGetDecisionsCollection.mock.calls.some(
        ([query]) => JSON.stringify(query) === JSON.stringify({ database_id: 'db-2' })
      )
    ).toBe(false)

    await waitFor(() => {
      expect(mockGetDecisionsDetail).toHaveBeenCalledWith(
        'decision-version-2',
        {},
        { errorPolicy: 'page' },
      )
    })

    expect(await screen.findByText(
      'Metadata context недоступен для выбранной базы. Показываем глобальный список revisions без compatibility context этой базы; управлять configuration profile и metadata snapshot нужно через /databases.'
    )).toBeInTheDocument()
  })

  it('supports viewing and editing existing decisions through a new revision flow', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Decision Policy Library')

    await user.click(screen.getByRole('button', { name: 'Edit selected decision' }))

    expect(await screen.findByRole('heading', { name: 'Edit selected decision' })).toBeInTheDocument()
    expect(screen.getByLabelText('Decision table ID')).toHaveValue('services-publication-policy')
    expect(screen.getByLabelText('Decision name')).toHaveValue('Services publication policy')
    expect(screen.getByLabelText('Chain 1 ID')).toHaveValue('sale_chain')
    expect(screen.getByLabelText('Chain 1 document 1 entity')).toHaveValue('Document_Sales')
    expect(screen.getByLabelText('Chain 1 document 1 field mapping 1 target')).toHaveValue('Amount')
    expect(screen.getByLabelText('Chain 1 document 1 field mapping 1 source')).toHaveValue('allocation.amount')

    fireEvent.change(screen.getByLabelText('Decision name'), { target: { value: 'Services publication policy v3' } })
    fireEvent.change(screen.getByLabelText('Chain 1 document 1 field mapping 1 source'), {
      target: { value: 'allocation.total_amount' },
    })
    await user.click(screen.getByRole('button', { name: 'Save decision' }))

    await waitFor(() => {
      expect(mockPostDecisionsCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          parent_version_id: 'decision-version-2',
          decision_table_id: 'services-publication-policy',
          name: 'Services publication policy v3',
          is_active: true,
          rules: expect.arrayContaining([
            expect.objectContaining({
              outputs: expect.objectContaining({
                document_policy: expect.objectContaining({
                  chains: expect.arrayContaining([
                    expect.objectContaining({
                      chain_id: 'sale_chain',
                      documents: expect.arrayContaining([
                        expect.objectContaining({
                          entity_name: 'Document_Sales',
                          field_mapping: {
                            Amount: 'allocation.total_amount',
                          },
                        }),
                      ]),
                    }),
                  ]),
                }),
              }),
            }),
          ]),
        }),
        { errorPolicy: 'page' },
      )
    })
  }, 30000)

  it('keeps unbound non-document_policy revisions out of the default selection and edit flow', async () => {
    const user = userEvent.setup()
    const unsupportedDecision = {
      ...defaultDecision,
      id: 'decision-version-route',
      decision_table_id: 'route-documents-policy',
      decision_key: 'route_documents',
      name: 'Route documents policy',
      rules: [
        {
          ...defaultDecision.rules[0],
          outputs: {
            route_documents: {
              version: 'route_documents.v1',
              routes: [],
            },
          },
        },
      ],
    }

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [unsupportedDecision, defaultDecision],
      count: 2,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockImplementation(async (decisionId: string) => ({
      decision: decisionId === unsupportedDecision.id ? unsupportedDecision : defaultDecision,
      metadata_context: defaultMetadataContext,
    }))

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(mockListOrganizationPools).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(mockGetDecisionsDetail.mock.calls.some(([decisionId]) => decisionId === unsupportedDecision.id)).toBe(false)
      expect(mockGetDecisionsDetail).toHaveBeenCalledWith(
        defaultDecision.id,
        { database_id: 'db-2' },
        { errorPolicy: 'page' },
      )
    })

    expect(screen.queryByText('Route documents policy')).not.toBeInTheDocument()
    expect(screen.getAllByText('Services publication policy').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Edit selected decision' }))

    expect(await screen.findByRole('heading', { name: 'Edit selected decision' })).toBeInTheDocument()
    expect(screen.queryByText('decision_key должен быть "document_policy".')).not.toBeInTheDocument()
  })

  it('keeps binding-pinned legacy decisions visible but read-only', async () => {
    const user = userEvent.setup()
    const legacyBoundDecision = {
      ...defaultDecision,
      id: 'decision-version-sale-only',
      decision_table_id: 'sale-only-policy',
      decision_key: 'sale_only',
      name: 'Sale only policy',
      decision_revision: 5,
      rules: [
        {
          ...defaultDecision.rules[0],
          outputs: {
            sale_only: {
              version: 'sale_only.v1',
              routes: [],
            },
          },
        },
      ],
    }

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [legacyBoundDecision, defaultDecision],
      count: 2,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockImplementation(async (decisionId: string) => ({
      decision: decisionId === legacyBoundDecision.id ? legacyBoundDecision : defaultDecision,
      metadata_context: defaultMetadataContext,
    }))
    mockListOrganizationPools.mockResolvedValue([
      {
        ...defaultPool,
        workflow_bindings: [
          {
            binding_id: 'binding-sale-only',
            pool_id: defaultPool.id,
            revision: 3,
            status: 'active',
            effective_from: '2026-03-10',
            effective_to: null,
            workflow: {
              workflow_definition_key: 'wf-sale-only',
              workflow_revision_id: 'wf-sale-only-r3',
              workflow_revision: 3,
              workflow_name: 'Sale only workflow',
            },
            decisions: [
              {
                decision_table_id: legacyBoundDecision.decision_table_id,
                decision_key: legacyBoundDecision.decision_key,
                decision_revision: legacyBoundDecision.decision_revision,
              },
            ],
          },
        ],
      },
    ])

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(mockListOrganizationPools).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(mockGetDecisionsDetail).toHaveBeenCalledWith(
        defaultDecision.id,
        { database_id: 'db-2' },
        { errorPolicy: 'page' },
      )
    })

    await user.click(screen.getByRole('button', { name: 'Show all revisions' }))

    await waitFor(() => expect(mockListOrganizationPools).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Sale only policy')).toBeInTheDocument()
    expect(screen.getByText('Pinned in binding')).toBeInTheDocument()

    await user.click(screen.getByText('Sale only policy'))

    await waitFor(() => {
      expect(mockGetDecisionsDetail).toHaveBeenCalledWith(
        legacyBoundDecision.id,
        { database_id: 'db-2' },
        { errorPolicy: 'page' },
      )
    })

    expect(await screen.findByText('This revision is still pinned in workflow bindings, but /decisions editing supports only document_policy. Update the binding to a document_policy revision before editing here.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit selected decision' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Deactivate selected decision' })).toBeDisabled()
  })

  it('supports guided rollover from a revision outside the default compatible selection', async () => {
    const user = userEvent.setup()
    const previousReleaseDecision = {
      ...defaultDecision,
      id: 'decision-version-previous-release',
      decision_revision: 7,
      name: 'Previous release policy',
      metadata_context: {
        ...defaultDecision.metadata_context,
        config_version: '8.3.23',
      },
      metadata_compatibility: {
        status: 'incompatible',
        reason: 'configuration_scope_mismatch',
        is_compatible: false,
      },
    }

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [defaultDecision, previousReleaseDecision],
      count: 2,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockImplementation(async (decisionId: string) => ({
      decision: decisionId === previousReleaseDecision.id ? previousReleaseDecision : defaultDecision,
      metadata_context: defaultMetadataContext,
    }))

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show all revisions' }))
    expect(await screen.findByText('Previous release policy')).toBeInTheDocument()

    await user.click(screen.getByText('Previous release policy'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Edit selected decision' })).toBeDisabled()
    })

    await user.click(screen.getByRole('button', { name: 'Rollover selected revision' }))

    expect(await screen.findByRole('heading', { name: 'Rollover selected revision' })).toBeInTheDocument()
    expect(screen.getByText('Source revision')).toBeInTheDocument()
    expect(screen.getByText('Previous release policy (services-publication-policy r7)')).toBeInTheDocument()
    expect(screen.getByText('Target database')).toBeInTheDocument()
    expect(screen.getAllByText('Target DB (shared-profile)').length).toBeGreaterThan(0)
    expect(screen.getByText('Target metadata snapshot')).toBeInTheDocument()
    expect(screen.getByText('shared-profile 8.3.24')).toBeInTheDocument()
    expect(screen.getByText('Publishing a rollover creates a new revision only. Existing workflows, bindings, and runtime projections stay pinned until you update them explicitly.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Decision name'), {
      target: { value: 'Previous release policy for Target DB' },
    })
    await user.click(screen.getByRole('button', { name: 'Publish rollover revision' }))

    await waitFor(() => {
      expect(mockPostDecisionsCollection).toHaveBeenCalledWith(
        expect.objectContaining({
          database_id: 'db-2',
          decision_table_id: 'services-publication-policy',
          parent_version_id: 'decision-version-previous-release',
          name: 'Previous release policy for Target DB',
          is_active: true,
        }),
        { errorPolicy: 'page' },
      )
    })
  }, 30000)

  it('allows clearing the selected database without auto-restoring the first option', async () => {
    const user = userEvent.setup()
    mockGetDecisionsCollection.mockReset()
    mockGetDecisionsDetail.mockReset()
    mockGetDecisionsCollection
      .mockResolvedValueOnce({
        decisions: [defaultDecision],
        count: 1,
        metadata_context: defaultMetadataContext,
      })
      .mockResolvedValueOnce({
        decisions: [defaultDecision],
        count: 1,
      })
    mockGetDecisionsDetail
      .mockResolvedValueOnce({
        decision: defaultDecision,
        metadata_context: defaultMetadataContext,
      })
      .mockResolvedValueOnce({
        decision: defaultDecision,
      })

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(mockGetDecisionsCollection).toHaveBeenCalledWith(
      { database_id: 'db-2' },
      { errorPolicy: 'page' },
    )

    clearSelect('decisions-database-select')
    await user.click(document.body)

    await waitFor(() => {
      expect(mockGetDecisionsCollection).toHaveBeenCalledWith(
        {},
        { errorPolicy: 'page' },
      )
    })

    expect(
      mockGetDecisionsCollection.mock.calls.filter(
        ([query]) => JSON.stringify(query) === JSON.stringify({ database_id: 'db-2' })
      ).length
    ).toBe(1)

    await waitFor(() => {
      expect(mockGetDecisionsDetail).toHaveBeenLastCalledWith(
        'decision-version-2',
        {},
        { errorPolicy: 'page' },
      )
    })

    expect(screen.getByText('Select database')).toBeInTheDocument()
  })

  it('keeps publication drift revisions visible when business configuration still matches', async () => {
    const driftedDecision = {
      ...defaultDecision,
      id: 'decision-version-3',
      decision_table_id: 'transfer-publication-policy',
      decision_revision: 1,
      name: 'Transfer publication policy',
      metadata_context: {
        ...defaultDecision.metadata_context,
        metadata_hash: 'b'.repeat(64),
      },
      metadata_compatibility: {
        status: 'compatible',
        reason: 'metadata_surface_diverged',
        is_compatible: true,
      },
    }

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [defaultDecision, driftedDecision],
      count: 2,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockImplementation(async (decisionId: string) => ({
      decision: decisionId === driftedDecision.id ? driftedDecision : defaultDecision,
      metadata_context: defaultMetadataContext,
    }))

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(screen.getByText('Showing 2 of 2 revisions matching the selected configuration.')).toBeInTheDocument()
    expect(screen.getAllByText('services-publication-policy').length).toBeGreaterThan(0)
    expect(screen.getByText('Transfer publication policy')).toBeInTheDocument()
  })

  it('does not request decision detail for revisions hidden by the configuration filter', async () => {
    const incompatibleDecision = {
      ...defaultDecision,
      id: 'decision-version-hidden',
      decision_table_id: 'transfer-publication-policy',
      decision_revision: 1,
      name: 'Transfer publication policy',
      metadata_context: {
        ...defaultDecision.metadata_context,
        config_version: '3.0.200.1',
      },
      metadata_compatibility: {
        status: 'incompatible',
        reason: 'configuration_scope_mismatch',
        is_compatible: false,
      },
    }

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [incompatibleDecision],
      count: 1,
      metadata_context: defaultMetadataContext,
    })

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    expect(screen.getByText('Showing 0 of 1 revisions matching the selected configuration.')).toBeInTheDocument()
    expect(screen.getByText('No decision revisions match the selected configuration')).toBeInTheDocument()
    expect(screen.getByText('Select a decision revision to inspect metadata and output')).toBeInTheDocument()
    expect(mockGetDecisionsDetail).not.toHaveBeenCalled()
  })

  it('resets diagnostics mode back to matching configuration when the selected database changes', async () => {
    const user = userEvent.setup()
    const incompatibleDecision = {
      ...defaultDecision,
      id: 'decision-version-3',
      decision_table_id: 'transfer-publication-policy',
      decision_revision: 1,
      name: 'Transfer publication policy',
      metadata_context: {
        ...defaultDecision.metadata_context,
        config_version: '3.0.200.1',
      },
      metadata_compatibility: {
        status: 'incompatible',
        reason: 'configuration_scope_mismatch',
        is_compatible: false,
      },
    }

    mockUseDatabases.mockReturnValue({
      data: {
        databases: [
          {
            id: 'db-2',
            name: 'Target DB',
            base_name: 'shared-profile',
            version: '8.3.24',
          },
          {
            id: 'db-3',
            name: 'Sibling DB',
            base_name: 'shared-profile',
            version: '8.3.24',
          },
        ],
      },
      isLoading: false,
    })

    mockGetDecisionsCollection.mockReset()
    mockGetDecisionsDetail.mockReset()
    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [defaultDecision, incompatibleDecision],
      count: 2,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockImplementation(async (decisionId: string) => ({
      decision: decisionId === incompatibleDecision.id ? incompatibleDecision : defaultDecision,
      metadata_context: defaultMetadataContext,
    }))

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show all revisions' }))

    expect(await screen.findByText('Showing all 2 revisions for diagnostics. 1 revision is outside the selected configuration and not pinned in workflow bindings.')).toBeInTheDocument()
    expect(screen.getByText('Transfer publication policy')).toBeInTheDocument()

    openSelect('decisions-database-select')
    await selectDropdownOption('Sibling DB (shared-profile)')

    expect(await screen.findByText('Showing 1 of 2 revisions matching the selected configuration.')).toBeInTheDocument()
    expect(screen.queryByText('Transfer publication policy')).not.toBeInTheDocument()
    expect(mockGetDecisionsCollection).toHaveBeenCalledWith(
      { database_id: 'db-3' },
      { errorPolicy: 'page' },
    )
  })

  it('falls back to unscoped list and detail loading when database metadata context is unavailable', async () => {
    mockGetDecisionsCollection.mockReset()
    mockGetDecisionsDetail.mockReset()
    mockGetDecisionsCollection
      .mockRejectedValueOnce(makeApiError('Metadata context is unavailable for the selected database.'))
      .mockResolvedValueOnce({
        decisions: [defaultDecision],
        count: 1,
      })
    mockGetDecisionsDetail.mockResolvedValue({
      decision: defaultDecision,
    })

    renderPage()

    expect(await screen.findByText('Decision Policy Library')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockGetDecisionsCollection).toHaveBeenCalledWith(
        { database_id: 'db-2' },
        { errorPolicy: 'page' },
      )
      expect(
        mockGetDecisionsCollection.mock.calls.filter(
          ([query, options]) => JSON.stringify(query) === '{}' && JSON.stringify(options) === JSON.stringify({ errorPolicy: 'page' })
        ).length
      ).toBe(1)
    })

    await waitFor(() => {
      expect(mockGetDecisionsDetail).toHaveBeenCalledWith(
        'decision-version-2',
        {},
        { errorPolicy: 'page' },
      )
    })

    expect(await screen.findByText(
      'Metadata context недоступен для выбранной базы. Показываем глобальный список revisions без compatibility context этой базы; управлять configuration profile и metadata snapshot нужно через /databases.'
    )).toBeInTheDocument()
    expect(screen.getByTestId('decisions-warning-open-databases')).toBeInTheDocument()
    expect(screen.queryByText('Failed to load decision table revisions.')).not.toBeInTheDocument()
    expect(screen.queryByText('Failed to load decision detail.')).not.toBeInTheDocument()
    expect(screen.getAllByText('Services publication policy').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Edit selected decision' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Rollover selected revision' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Deactivate selected decision' })).toBeDisabled()
  })

  it('keeps legacy non-default rule_id decisions editable in builder mode', async () => {
    const user = userEvent.setup()
    const legacyRuleDecision = {
      ...defaultDecision,
      rules: [
        {
          ...defaultDecision.rules[0],
          rule_id: 'legacy_rule',
        },
      ],
    }

    mockGetDecisionsCollection.mockResolvedValue({
      decisions: [legacyRuleDecision],
      count: 1,
      metadata_context: defaultMetadataContext,
    })
    mockGetDecisionsDetail.mockResolvedValue({
      decision: legacyRuleDecision,
      metadata_context: defaultMetadataContext,
    })

    renderPage()

    await screen.findByText('Decision Policy Library')
    await user.click(screen.getByRole('button', { name: 'Edit selected decision' }))

    expect(await screen.findByRole('heading', { name: 'Edit selected decision' })).toBeInTheDocument()
    expect(screen.getByLabelText('Decision table ID')).toHaveValue('services-publication-policy')
    expect(screen.getByLabelText('Chain 1 ID')).toHaveValue('sale_chain')
    expect(screen.getByLabelText('Chain 1 document 1 entity')).toHaveValue('Document_Sales')
    expect(screen.getByRole('tab', { name: 'Builder' })).toHaveAttribute('aria-selected', 'true')
  })

  it('supports raw JSON compatibility import and deactivate flows through decision revisions', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Decision Policy Library')

    await user.click(screen.getByRole('button', { name: 'Import raw JSON' }))
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
        { errorPolicy: 'page' },
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
        { errorPolicy: 'page' },
      )
    })
  }, 30000)

  it('keeps guided rollover fail-closed when target metadata validation rejects publish', async () => {
    const user = userEvent.setup()
    mockPostDecisionsCollection.mockRejectedValueOnce(
      makeApiError(
        'Document policy references are invalid for the selected target metadata snapshot.',
        'POOL_METADATA_REFERENCE_INVALID',
        400,
      ),
    )

    renderPage()

    await screen.findByText('Decision Policy Library')
    await user.click(screen.getByRole('button', { name: 'Rollover selected revision' }))

    expect(await screen.findByRole('heading', { name: 'Rollover selected revision' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Publish rollover revision' }))

    expect(await screen.findByText('Document policy references are invalid for the selected target metadata snapshot.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Rollover selected revision' })).toBeInTheDocument()
  }, 30000)
})
