import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import type {
  Kvo17GeneratedPurchasePreviewResponse,
  PoolMasterParty,
  PoolSchemaTemplate,
  PoolWorkflowBinding,
} from '../../../api/intercompanyPools'
import { PoolBatchIntakeDrawer } from '../PoolBatchIntakeDrawer'

const apiMocks = vi.hoisted(() => ({
  createPoolBatch: vi.fn(),
  previewKvo17GeneratedPurchase: vi.fn(),
  listMasterDataParties: vi.fn(),
}))

vi.mock('../../../api/intercompanyPools', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/intercompanyPools')>()
  return {
    ...actual,
    createPoolBatch: apiMocks.createPoolBatch,
    previewKvo17GeneratedPurchase: apiMocks.previewKvo17GeneratedPurchase,
    listMasterDataParties: apiMocks.listMasterDataParties,
  }
})

const schemaTemplate: PoolSchemaTemplate = {
  id: 'schema-kvo17',
  tenant_id: 'tenant-1',
  code: 'kvo17-purchase-split-intake',
  name: 'KVO17 Purchase Split',
  format: 'json',
  is_public: true,
  is_active: true,
  schema: {},
  metadata: { scheme_code: 'kvo17-purchase-split' },
  workflow_template_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const supplierOne: PoolMasterParty = {
  id: 'party-1',
  tenant_id: 'tenant-1',
  canonical_id: 'supplier-001',
  name: 'Supplier One',
  full_name: 'Supplier One',
  inn: '7701000001',
  kpp: '',
  is_our_organization: false,
  is_counterparty: true,
  metadata: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const compatibleBinding = {
  binding_id: 'binding-1',
  resolved_profile: {
    parameters: {
      generated_purchase_supported: true,
      generated_purchase_source_type: 'kvo17_generated_purchase',
    },
    decisions: [
      {
        decision_table_id: 'decision-kvo01',
        decision_key: 'purchase-kvo01',
        decision_revision: 1,
        slot_key: 'purchase_kvo01',
      },
      {
        decision_table_id: 'decision-kvo17',
        decision_key: 'purchase-kvo17',
        decision_revision: 1,
        slot_key: 'purchase_kvo17',
      },
      {
        decision_table_id: 'decision-generated-pair',
        decision_key: 'document_policy',
        decision_revision: 1,
        slot_key: 'kvo17_generated_purchase_pair',
      },
    ],
    topology_template_compatibility: {
      status: 'compatible',
      topology_aware_ready: true,
      covered_slot_keys: ['purchase_kvo01', 'purchase_kvo17', 'kvo17_generated_purchase_pair'],
      diagnostics: [],
    },
  },
} as unknown as PoolWorkflowBinding

const incompatibleBinding = {
  binding_id: 'binding-topdown',
  resolved_profile: {
    parameters: {
      publication_variant: 'full',
    },
    decisions: [
      {
        decision_table_id: 'receipt',
        decision_key: 'document-policy',
        decision_revision: 1,
        slot_key: 'receipt_leaf',
      },
    ],
    topology_template_compatibility: {
      status: 'compatible',
      topology_aware_ready: true,
      covered_slot_keys: ['receipt_leaf'],
      diagnostics: [],
    },
  },
} as unknown as PoolWorkflowBinding

const previewResponse: Kvo17GeneratedPurchasePreviewResponse = {
  request_hash: 'request-hash-1',
  content_hash: 'content-hash-1',
  diagnostics: [],
  document_plan: {
    compile_summary: {
      documents_count: 2,
    },
  },
  manifest: {
    request_schema_version: 'kvo17_generated_purchase_request.v1',
    manifest_version: 'kvo17_generated_purchase_manifest.v1',
    period: {
      start: '2026-01-01',
      end: '2026-01-31',
    },
    seed: 'kvo17-2026-01-01',
    currency: 'RUB',
    vat_rate: '20%',
    invoice_number_prefix: 'KVO17',
    request_hash: 'request-hash-1',
    content_hash: 'content-hash-1',
    counterparties: [
      { ref: 'supplier-001', name: 'Supplier One', inn: '7701000001' },
    ],
    amount_ranges: [
      { range_key: 'small', min_amount: '50.00', max_amount: '100.00', kvo: '17' },
      { range_key: 'large', min_amount: '200.00', max_amount: '300.00', kvo: '01' },
    ],
    rows: [
      {
        line_no: 1,
        counterparty_ref: 'supplier-001',
        counterparty_name: 'Supplier One',
        counterparty_inn: '7701000001',
        range_key: 'small',
        kvo: '17',
        amount: '75.00',
        vat_rate: '20%',
        vat_amount: '12.50',
        currency: 'RUB',
        source_document_number: 'KVO17-0001-ABCDEF12',
        source_document_date: '2026-01-15',
        row_id: 'supplier-001:small:17',
        row_fingerprint: 'fingerprint-small',
        idempotency_key: 'kvo17-generated-purchase:fingerprint-small',
      },
      {
        line_no: 2,
        counterparty_ref: 'supplier-001',
        counterparty_name: 'Supplier One',
        counterparty_inn: '7701000001',
        range_key: 'large',
        kvo: '01',
        amount: '250.00',
        vat_rate: '20%',
        vat_amount: '41.67',
        currency: 'RUB',
        source_document_number: 'KVO17-0001-ABCDEF12',
        source_document_date: '2026-01-15',
        row_id: 'supplier-001:large:01',
        row_fingerprint: 'fingerprint-large',
        idempotency_key: 'kvo17-generated-purchase:fingerprint-large',
      },
    ],
    summary: {
      selected_counterparties: 1,
      processed_rows: 2,
      total_amount: '325.00',
      total_vat_amount: '54.17',
      currency: 'RUB',
    },
  },
}

describe('PoolBatchIntakeDrawer KVO17 generated purchase mode', () => {
  beforeAll(async () => {
    await ensureNamespaces('en', 'pools')
    await changeLanguage('en')
  })

  beforeEach(() => {
    apiMocks.createPoolBatch.mockReset()
    apiMocks.createPoolBatch.mockResolvedValue({
      batch: { id: 'batch-1' },
      settlement: { id: 'settlement-1' },
      run: { id: 'run-1' },
      created: true,
    })
    apiMocks.previewKvo17GeneratedPurchase.mockReset()
    apiMocks.previewKvo17GeneratedPurchase.mockResolvedValue(previewResponse)
    apiMocks.listMasterDataParties.mockReset()
    apiMocks.listMasterDataParties.mockResolvedValue({
      parties: [supplierOne],
      meta: { count: 1, limit: 200, offset: 0 },
    })
  })

  it('previews and creates a generated receipt run from structured controls', async () => {
    const onCreated = vi.fn()
    renderDrawer({ onCreated })

    await switchToGeneratedMode()
    await selectOption('pool-runs-batch-intake-kvo17-generated-counterparties', 'Supplier One · 7701000001')
    fireEvent.click(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-preview'))

    await waitFor(() => {
      expect(apiMocks.previewKvo17GeneratedPurchase).toHaveBeenCalledTimes(1)
    })
    expect(apiMocks.previewKvo17GeneratedPurchase.mock.calls[0][0]).toMatchObject({
      pool_id: 'pool-1',
      pool_workflow_binding_id: 'binding-1',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      json_payload: {
        counterparties: [
          {
            counterparty_ref: 'supplier-001',
            counterparty_name: 'Supplier One',
            counterparty_inn: '7701000001',
          },
        ],
        amount_ranges: [
          { range_key: 'small', min_amount: '50.00', max_amount: '100.00', kvo: '17' },
          { range_key: 'large', min_amount: '200.00', max_amount: '300.00', kvo: '01' },
        ],
      },
    })
    expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-generated-preview-panel')).toHaveTextContent(
      'content-hash-1',
    )

    fireEvent.click(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-create'))

    await waitFor(() => {
      expect(apiMocks.createPoolBatch).toHaveBeenCalledTimes(1)
    })
    expect(apiMocks.createPoolBatch.mock.calls[0][0]).toMatchObject({
      source_type: 'kvo17_generated_purchase',
      batch_kind: 'receipt',
      pool_workflow_binding_id: 'binding-1',
      start_organization_id: 'org-1',
      source_metadata: {
        kvo17_generated_purchase: {
          accepted_manifest: previewResponse.manifest,
          accepted_request_hash: 'request-hash-1',
          accepted_content_hash: 'content-hash-1',
        },
      },
    })
    expect(onCreated).toHaveBeenCalledTimes(1)
  })

  it('keeps generated purchase controls full-width and grid-aligned', async () => {
    renderDrawer()

    await switchToGeneratedMode()

    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-counterparties')).toHaveStyle({
      width: '100%',
    })
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-ranges')).toHaveStyle({
      display: 'grid',
      width: '100%',
    })
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-range-small')).toHaveStyle({
      display: 'grid',
    })
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-small-kvo')).toHaveStyle({
      width: '100%',
    })
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-meta')).toHaveStyle({
      display: 'grid',
      width: '100%',
    })
  })

  it('blocks create when the accepted manifest is stale', async () => {
    renderDrawer()

    await switchToGeneratedMode()
    await selectOption('pool-runs-batch-intake-kvo17-generated-counterparties', 'Supplier One · 7701000001')
    fireEvent.click(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-preview'))
    expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-generated-preview-panel')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-small-min'), {
      target: { value: '60.00' },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-generated-stale-preview')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-create')).toBeDisabled()
  })

  it('auto-selects a compatible binding when switching to generated mode', async () => {
    renderDrawer({
      omitInitialPoolWorkflowBinding: true,
      workflowBindingOptions: [
        { value: 'binding-topdown', label: 'top_down_publication' },
        { value: 'binding-1', label: 'binding-1' },
      ],
      workflowBindings: [incompatibleBinding, compatibleBinding],
    })

    await switchToGeneratedMode()
    expect(screen.getByText('binding-1')).toBeInTheDocument()
    await selectOption('pool-runs-batch-intake-kvo17-generated-counterparties', 'Supplier One · 7701000001')
    fireEvent.click(screen.getByTestId('pool-runs-batch-intake-kvo17-generated-preview'))

    await waitFor(() => {
      expect(apiMocks.previewKvo17GeneratedPurchase).toHaveBeenCalledTimes(1)
    })
    expect(apiMocks.previewKvo17GeneratedPurchase.mock.calls[0][0]).toMatchObject({
      pool_workflow_binding_id: 'binding-1',
    })
  })
})

function renderDrawer(
  overrides: {
    onCreated?: Parameters<typeof PoolBatchIntakeDrawer>[0]['onCreated']
    workflowBindingOptions?: { value: string; label: string }[]
    workflowBindings?: PoolWorkflowBinding[]
    omitInitialPoolWorkflowBinding?: boolean
  } = {},
) {
  return render(
    <ConfigProvider>
      <AntApp>
        <PoolBatchIntakeDrawer
          open
          poolId="pool-1"
          poolLabel="pool-1 - KVO17"
          schemaTemplates={[schemaTemplate]}
          loadingSchemaTemplates={false}
          workflowBindingOptions={overrides.workflowBindingOptions ?? [{ value: 'binding-1', label: 'binding-1' }]}
          workflowBindings={overrides.workflowBindings ?? [compatibleBinding]}
          startOrganizationOptions={[{ value: 'org-1', label: 'Org One' }]}
          initialValues={{
            batchKind: 'receipt',
            periodStart: '2026-01-01',
            periodEnd: '2026-01-31',
            poolWorkflowBindingId: overrides.omitInitialPoolWorkflowBinding ? undefined : 'binding-1',
            startOrganizationId: 'org-1',
          }}
          onClose={vi.fn()}
          onCreated={overrides.onCreated ?? vi.fn()}
        />
      </AntApp>
    </ConfigProvider>,
  )
}

async function switchToGeneratedMode() {
  await waitFor(() => {
    expect(screen.getByText('KVO17 generator').closest('label')).not.toHaveClass('ant-radio-button-wrapper-disabled')
  })
  fireEvent.click(screen.getByText('KVO17 generator'))
  expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-generated')).toBeInTheDocument()
}

async function selectOption(testId: string, label: string) {
  const select = await screen.findByTestId(testId)
  const selector = select.querySelector('.ant-select-selector')
  expect(selector).toBeTruthy()
  fireEvent.mouseDown(selector as Element)
  fireEvent.click(await screen.findByText(label))
}
