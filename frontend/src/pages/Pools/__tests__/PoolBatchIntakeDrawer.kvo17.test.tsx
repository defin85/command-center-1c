import { beforeAll, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'

import { changeLanguage, ensureNamespaces } from '../../../i18n/runtime'
import type { PoolSchemaTemplate } from '../../../api/intercompanyPools'
import { PoolBatchIntakeDrawer } from '../PoolBatchIntakeDrawer'

const kvo17Template: PoolSchemaTemplate = {
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

describe('PoolBatchIntakeDrawer KVO17 preview', () => {
  beforeAll(async () => {
    await ensureNamespaces('en', 'pools')
    await changeLanguage('en')
  })

  it('renders split preview with branch totals and provenance before submit', async () => {
    renderDrawer()

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo17-purchase-split-intake - KVO17 Purchase Split')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            {
              source_document_number: 'UT-42',
              source_document_date: '2026-01-15',
              source_supplier_ref: 'supplier-001',
              source_supplier_name: 'Supplier One',
              amount: '100.00',
              vat_amount: '20.00',
              vat_rate: '20%',
              currency: 'RUB',
              row_id: 'line-1',
            },
            {
              source_document_number: 'UT-42',
              source_document_date: '2026-01-15',
              source_supplier_ref: 'supplier-001',
              source_supplier_name: 'Supplier One',
              amount: '250.00',
              vat_amount: '50.00',
              vat_rate: '20%',
              currency: 'RUB',
              row_id: 'line-2',
            },
          ],
        }),
      },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-preview')).toBeInTheDocument()
    expect(screen.getByText('kvo17_purchase_split_classifier.v1')).toBeInTheDocument()
    expect(screen.getByText('UT-42 · 2026-01-15')).toBeInTheDocument()
    expect(screen.getByText('Supplier One · supplier-001')).toBeInTheDocument()
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-preview-kvo17')).toHaveTextContent(
      'KVO 17 · rows 1 · amount 100.00 · VAT 20.00',
    )
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-preview-kvo01')).toHaveTextContent(
      'KVO 01 · rows 1 · amount 250.00 · VAT 50.00',
    )
  })

  it('shows blocking diagnostics when required KVO17 fields are missing', async () => {
    renderDrawer()

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo17-purchase-split-intake - KVO17 Purchase Split')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            {
              source_document_number: '',
              source_document_date: '2026-01-15',
              source_supplier_ref: 'supplier-001',
              source_supplier_name: 'Supplier One',
              amount: '100.00',
              vat_amount: '20.00',
              vat_rate: '20%',
              currency: 'RUB',
              row_id: 'line-1',
            },
          ],
        }),
      },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-preview-error')).toHaveTextContent(
      'source_document_number required',
    )
    await waitFor(() => {
      expect(screen.getByTestId('pool-runs-batch-intake-submit')).toBeDisabled()
    })
  })

  it('renders duplicate-source diagnostics without hiding branch totals', async () => {
    renderDrawer()

    await selectOption('pool-runs-batch-intake-schema-template', 'kvo17-purchase-split-intake - KVO17 Purchase Split')
    fireEvent.change(screen.getByTestId('pool-runs-batch-intake-source-payload'), {
      target: {
        value: JSON.stringify({
          rows: [
            {
              source_document_number: 'UT-42',
              source_document_date: '2026-01-15',
              source_supplier_ref: 'supplier-001',
              source_supplier_name: 'Supplier One',
              amount: '100.00',
              vat_amount: '20.00',
              vat_rate: '20%',
              currency: 'RUB',
              row_id: 'line-1',
            },
            {
              source_document_number: 'UT-42',
              source_document_date: '2026-01-15',
              source_supplier_ref: 'supplier-001',
              source_supplier_name: 'Supplier One',
              amount: '250.00',
              vat_amount: '50.00',
              vat_rate: '20%',
              currency: 'RUB',
              row_id: 'line-1',
            },
          ],
        }),
      },
    })

    expect(await screen.findByTestId('pool-runs-batch-intake-kvo17-preview-diagnostics')).toHaveTextContent(
      'Duplicate KVO17 purchase split row_id.',
    )
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-preview-kvo17')).toHaveTextContent(
      'KVO 17 · rows 1 · amount 100.00 · VAT 20.00',
    )
    expect(screen.getByTestId('pool-runs-batch-intake-kvo17-preview-kvo01')).toHaveTextContent(
      'KVO 01 · rows 1 · amount 250.00 · VAT 50.00',
    )
  })
})

function renderDrawer() {
  return render(
    <ConfigProvider>
      <AntApp>
        <PoolBatchIntakeDrawer
          open
          poolId="pool-1"
          poolLabel="pool-1 - KVO17"
          schemaTemplates={[kvo17Template]}
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
          onCreated={vi.fn()}
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
