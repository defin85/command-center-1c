export const KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE = 'kvo18-advance-vat-offset'
export const KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE = 'kvo18-advance-vat-offset-intake'
export const KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION = 'kvo18_advance_vat_offset_policy.v1'

export const CASH_RECEIPT_ORDER_SLOT = 'cash_receipt_order'
export const ADVANCE_INVOICE_KVO01_SLOT = 'advance_invoice_kvo01'
export const ADVANCE_OFFSET_KVO18_SLOT = 'advance_offset_kvo18'
export const DECLARATION_EVIDENCE_SLOT = 'declaration_evidence'

export type Kvo18StageSlot =
  | typeof CASH_RECEIPT_ORDER_SLOT
  | typeof ADVANCE_INVOICE_KVO01_SLOT
  | typeof ADVANCE_OFFSET_KVO18_SLOT
  | typeof DECLARATION_EVIDENCE_SLOT

export type Kvo18AdvanceVatOffsetStage = {
  slotKey: Kvo18StageSlot
  label: string
  state: 'ready' | 'blocked'
  prerequisites: string[]
  produces: string[]
}

export type Kvo18AdvanceVatOffsetDiagnostic = {
  code: string
  field: string
  value: string
  lineNumbers: number[]
  detail: string
}

export type Kvo18AdvanceVatOffsetPreview = {
  policyRevision: string
  totalAmount: string
  totalVatAmount: string
  currency: string
  rowCount: number
  stages: Record<Kvo18StageSlot, Kvo18AdvanceVatOffsetStage>
  technicalRealizationPolicy: {
    documentStateAfterOffset: string
    confirmationGates: string[]
  }
  evidenceRequirements: {
    salesBookKvo01Required: boolean
    purchaseBookKvo18Required: boolean
    declarationProjectionRequired: boolean
    documentCreationAloneIsSuccess: boolean
  }
  diagnostics: Kvo18AdvanceVatOffsetDiagnostic[]
}

type NormalizedRow = {
  lineNo: number
  counterpartyRef: string
  counterpartyName: string
  contractRef: string
  contractName: string
  operationDate: string
  amount: number
  vatRate: string
  vatAmount: number
  currency: string
  rowId: string
  fingerprintKey: string
}

export function isKvo18AdvanceVatOffsetSchemaTemplate(template: {
  code: string
  metadata?: Record<string, unknown>
} | null | undefined): boolean {
  if (!template) {
    return false
  }
  return template.code === KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE
    || template.metadata?.scheme_code === KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE
}

export function buildKvo18AdvanceVatOffsetPreview(payload: unknown): Kvo18AdvanceVatOffsetPreview {
  const rows = normalizeRows(payload)
  const totalAmount = rows.reduce((sum, row) => sum + row.amount, 0)
  const totalVatAmount = rows.reduce((sum, row) => sum + row.vatAmount, 0)
  return {
    policyRevision: KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
    totalAmount: formatAmount(totalAmount),
    totalVatAmount: formatAmount(totalVatAmount),
    currency: rows[0]?.currency ?? 'RUB',
    rowCount: rows.length,
    stages: buildStages(),
    technicalRealizationPolicy: {
      documentStateAfterOffset: 'unposted_after_purchase_book_evidence',
      confirmationGates: [
        'operator_preview_confirmed',
        'cash_receipt_order_evidence',
        'advance_invoice_kvo01_evidence',
      ],
    },
    evidenceRequirements: {
      salesBookKvo01Required: true,
      purchaseBookKvo18Required: true,
      declarationProjectionRequired: true,
      documentCreationAloneIsSuccess: false,
    },
    diagnostics: buildDuplicateRowDiagnostics(rows),
  }
}

function normalizeRows(payload: unknown): NormalizedRow[] {
  const rawRows = Array.isArray(payload)
    ? payload
    : (isRecord(payload) && Array.isArray(payload.rows) ? payload.rows : null)
  if (!rawRows || rawRows.length === 0) {
    throw new Error('rows must be a non-empty list')
  }
  return rawRows.map((row, index) => {
    if (!isRecord(row)) {
      throw new Error(`row ${index + 1}: object expected`)
    }
    const lineNo = index + 1
    const currency = requiredText(row, 'currency', lineNo).toUpperCase()
    if (currency !== 'RUB') {
      throw new Error(`row ${lineNo}: unsupported currency ${currency}`)
    }
    const counterpartyRef = requiredText(row, 'counterparty_ref', lineNo)
    const contractRef = requiredText(row, 'contract_ref', lineNo)
    const operationDate = requiredText(row, 'operation_date', lineNo)
    const rowId = requiredText(row, 'row_id', lineNo)
    const amount = requiredAmount(row, 'amount', lineNo)
    const vatAmount = requiredAmount(row, 'vat_amount', lineNo)
    const vatRate = requiredText(row, 'vat_rate', lineNo)
    return {
      lineNo,
      counterpartyRef,
      counterpartyName: requiredText(row, 'counterparty_name', lineNo),
      contractRef,
      contractName: requiredText(row, 'contract_name', lineNo),
      operationDate,
      amount,
      vatRate,
      vatAmount,
      currency,
      rowId,
      fingerprintKey: [
        counterpartyRef,
        contractRef,
        operationDate,
        rowId,
        formatAmount(amount),
        vatRate,
        formatAmount(vatAmount),
        currency,
      ].join('|'),
    }
  })
}

function buildStages(): Record<Kvo18StageSlot, Kvo18AdvanceVatOffsetStage> {
  return {
    [CASH_RECEIPT_ORDER_SLOT]: {
      slotKey: CASH_RECEIPT_ORDER_SLOT,
      label: 'Создать ПКО',
      state: 'ready',
      prerequisites: [],
      produces: ['cash_receipt_order_ref'],
    },
    [ADVANCE_INVOICE_KVO01_SLOT]: {
      slotKey: ADVANCE_INVOICE_KVO01_SLOT,
      label: 'Создать СФ на аванс',
      state: 'blocked',
      prerequisites: [CASH_RECEIPT_ORDER_SLOT],
      produces: ['advance_invoice_ref', 'sales_book_kvo01_evidence'],
    },
    [ADVANCE_OFFSET_KVO18_SLOT]: {
      slotKey: ADVANCE_OFFSET_KVO18_SLOT,
      label: 'Сформировать зачет (КВО 18)',
      state: 'blocked',
      prerequisites: [ADVANCE_INVOICE_KVO01_SLOT, 'operator_preview_confirmation'],
      produces: ['technical_realization_ref', 'technical_realization_final_state', 'purchase_book_kvo18_evidence'],
    },
    [DECLARATION_EVIDENCE_SLOT]: {
      slotKey: DECLARATION_EVIDENCE_SLOT,
      label: 'Проверить декларацию',
      state: 'blocked',
      prerequisites: [ADVANCE_OFFSET_KVO18_SLOT],
      produces: ['declaration_projection_kvo01_kvo18'],
    },
  }
}

function buildDuplicateRowDiagnostics(rows: NormalizedRow[]): Kvo18AdvanceVatOffsetDiagnostic[] {
  const lineNumbersByRowId = new Map<string, number[]>()
  for (const row of rows) {
    lineNumbersByRowId.set(row.rowId, [...(lineNumbersByRowId.get(row.rowId) ?? []), row.lineNo])
  }
  return [...lineNumbersByRowId.entries()]
    .filter(([, lineNumbers]) => lineNumbers.length > 1)
    .map(([value, lineNumbers]) => ({
      code: 'KVO18_DUPLICATE_ROW_ID',
      field: 'row_id',
      value,
      lineNumbers,
      detail: 'Duplicate KVO18 advance VAT offset row_id.',
    }))
}

function requiredText(row: Record<string, unknown>, key: string, lineNo: number): string {
  const value = String(row[key] ?? '').trim()
  if (!value) {
    throw new Error(`row ${lineNo}: ${key} required`)
  }
  return value
}

function requiredAmount(row: Record<string, unknown>, key: string, lineNo: number): number {
  const value = Number.parseFloat(String(row[key] ?? '').trim().replace(',', '.'))
  if (!Number.isFinite(value)) {
    throw new Error(`row ${lineNo}: ${key} required`)
  }
  return value
}

function formatAmount(value: number): string {
  return value.toFixed(2)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
