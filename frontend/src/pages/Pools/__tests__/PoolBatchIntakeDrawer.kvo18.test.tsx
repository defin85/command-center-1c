import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import type { PoolSchemaTemplate } from '../../../api/intercompanyPools'
import { PoolBatchIntakeDrawer } from '../PoolBatchIntakeDrawer'

const apiMocks = vi.hoisted(() => ({
  createPoolBatch: vi.fn(),
}))

vi.mock('../../../api/intercompanyPools', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/intercompanyPools')>()
  return {
    ...actual,
    createPoolBatch: apiMocks.createPoolBatch,
  }
})

const kvo18Template: PoolSchemaTemplate = {
  id: 'schema-kvo18',
  tenant_id: 'tenant-1',
  code: 'kvo18-advance-vat-offset-intake',
  name: 'KVO18 Advance VAT Offset',
  format: 'json',
  is_public: true,
  is_active: true,
  schema: {},
  metadata: { scheme_code: 'kvo18-advance-vat-offset' },
  workflow_template_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('PoolBatchIntakeDrawer KVO18 preview', () => {
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
  })

  it('renders staged controls, technical state, and KVO evidence before submit', async () => {
    renderDrawer()

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo18-advance-vat-offset-intake - KVO18 Advance VAT Offset')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            buildAdvanceRow({ row_id: 'advance-1', amount: '1200.00', vat_amount: '200.00' }),
            buildAdvanceRow({ row_id: 'advance-2', amount: '600.00', vat_amount: '100.00' }),
          ],
        }),
      },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo18-preview')).toBeInTheDocument()
    expect(screen.getByText('kvo18_advance_vat_offset_policy.v1')).toBeInTheDocument()
    expect(screen.getByText('1800.00 RUB · VAT 300.00')).toBeInTheDocument()
    expect(screen.getByText('unposted_after_purchase_book_evidence')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-stage-cash_receipt_order')).toHaveTextContent('Создать ПКО')
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-stage-cash_receipt_order')).toBeEnabled()
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-stage-advance_invoice_kvo01')).toBeDisabled()
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-stage-advance_offset_kvo18')).toHaveTextContent(
      'Сформировать зачет (КВО 18)',
    )
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-preview-summary')).toHaveTextContent(
      'rows 2 · amount 1800.00 · VAT 300.00',
    )
  })

  it('submits ready cash receipt stage with bounded KVO18 stage metadata', async () => {
    const onCreated = vi.fn()
    renderDrawer({ onCreated })

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo18-advance-vat-offset-intake - KVO18 Advance VAT Offset')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            buildAdvanceRow({ row_id: 'advance-1', amount: '1200.00', vat_amount: '200.00' }),
            buildAdvanceRow({ row_id: 'advance-2', amount: '600.00', vat_amount: '100.00' }),
          ],
        }),
      },
    })

    fireEvent.click(await screen.findByTestId('pool-runs-batch-intake-kvo18-stage-cash_receipt_order'))

    await waitFor(() => {
      expect(apiMocks.createPoolBatch).toHaveBeenCalledTimes(1)
    })
    expect(apiMocks.createPoolBatch.mock.calls[0][0]).toMatchObject({
      batch_kind: 'receipt',
      source_metadata: {
        kvo18_stage_intent: 'cash_receipt_order',
        kvo18_policy_revision: 'kvo18_advance_vat_offset_policy.v1',
      },
    })
    expect(onCreated).toHaveBeenCalledTimes(1)
  })

  it('blocks submit when required KVO18 fields are missing', async () => {
    renderDrawer()

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo18-advance-vat-offset-intake - KVO18 Advance VAT Offset')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            buildAdvanceRow({ contract_ref: '' }),
          ],
        }),
      },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo18-preview-error')).toHaveTextContent(
      'contract_ref required',
    )
    await waitFor(() => {
      expect(screen.getByTestId('pool-runs-batch-intake-submit')).toBeDisabled()
    })
  })

  it('blocks submit and stage action when duplicate row diagnostics are present', async () => {
    renderDrawer()

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo18-advance-vat-offset-intake - KVO18 Advance VAT Offset')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            buildAdvanceRow({ row_id: 'advance-1', amount: '1200.00', vat_amount: '200.00' }),
            buildAdvanceRow({ row_id: 'advance-1', amount: '600.00', vat_amount: '100.00' }),
          ],
        }),
      },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo18-preview-diagnostics')).toHaveTextContent(
      'Duplicate KVO18 advance VAT offset row_id.',
    )
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-stage-cash_receipt_order')).toBeDisabled()
    expect(screen.getByTestId('pool-runs-batch-intake-submit')).toBeDisabled()
    expect(screen.getByTestId('pool-runs-batch-intake-kvo18-preview-summary')).toHaveTextContent(
      'rows 2 · amount 1800.00 · VAT 300.00',
    )
  })
})

function buildAdvanceRow(overrides: Record<string, string> = {}) {
  return {
    counterparty_ref: 'counterparty-001',
    counterparty_name: 'Buyer One',
    contract_ref: 'contract-001',
    contract_name: 'Advance Contract',
    operation_date: '2026-01-15',
    amount: '1200.00',
    vat_rate: '20%',
    vat_amount: '200.00',
    currency: 'RUB',
    row_id: 'advance-1',
    ...overrides,
  }
}

function renderDrawer(overrides: { onCreated?: Parameters<typeof PoolBatchIntakeDrawer>[0]['onCreated'] } = {}) {
  return render(
    <ConfigProvider>
      <AntApp>
        <PoolBatchIntakeDrawer
          open
          poolId="pool-1"
          poolLabel="pool-1 - KVO18"
          schemaTemplates={[kvo18Template]}
          loadingSchemaTemplates={false}
          workflowBindingOptions={[{ value: 'binding-1', label: 'binding-1' }]}
          startOrganizationOptions={[{ value: 'org-1', label: 'Org One' }]}
          initialValues={{
            batchKind: 'receipt',
            periodStart: '2026-01-01',
            periodEnd: '2026-01-31',
            poolWorkflowBindingId: 'binding-1',
            startOrganizationId: 'org-1',
          }}
          onClose={vi.fn()}
          onCreated={overrides.onCreated ?? vi.fn()}
        />
      </AntApp>
    </ConfigProvider>,
  )
}

async function selectOption(testId: string, label: string) {
  const select = await screen.findByTestId(testId)
  const selector = select.querySelector('.ant-select-selector')
  expect(selector).toBeTruthy()
  fireEvent.mouseDown(selector as Element)
  fireEvent.click(await screen.findByText(label))
}
