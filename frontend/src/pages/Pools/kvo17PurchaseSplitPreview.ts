export const KVO17_PURCHASE_SPLIT_SCHEME_CODE = 'kvo17-purchase-split'
export const KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE = 'kvo17-purchase-split-intake'
export const KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION = 'kvo17_purchase_split_classifier.v1'
export const KVO17_PURCHASE_SPLIT_THRESHOLD_AMOUNT = 100
export const PURCHASE_KVO01_SLOT = 'purchase_kvo01'
export const PURCHASE_KVO17_SLOT = 'purchase_kvo17'

export type Kvo17PurchaseSplitPreviewBranch = {
  slotKey: typeof PURCHASE_KVO01_SLOT | typeof PURCHASE_KVO17_SLOT
  kvo: '01' | '17'
  rowCount: number
  totalAmount: string
  totalVatAmount: string
}

export type Kvo17PurchaseSplitPreviewDiagnostic = {
  code: string
  field: string
  value: string
  lineNumbers: number[]
  detail: string
}

export type Kvo17PurchaseSplitPreview = {
  classifierRevision: string
  thresholdAmount: string
  sourceDocumentIdentity: {
    number: string
    date: string
  }
  sourceSupplierProvenance: {
    ref: string
    name: string
  }
  branches: Record<typeof PURCHASE_KVO01_SLOT | typeof PURCHASE_KVO17_SLOT, Kvo17PurchaseSplitPreviewBranch>
  diagnostics: Kvo17PurchaseSplitPreviewDiagnostic[]
}

type NormalizedRow = {
  lineNo: number
  sourceDocumentNumber: string
  sourceDocumentDate: string
  sourceSupplierRef: string
  sourceSupplierName: string
  amount: number
  vatAmount: number
  currency: string
  rowId: string
  sourceKvoOverride: '01' | '17' | null
}

export function isKvo17PurchaseSplitSchemaTemplate(template: {
  code: string
  metadata?: Record<string, unknown>
} | null | undefined): boolean {
  if (!template) {
    return false
  }
  return template.code === KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE
    || template.metadata?.scheme_code === KVO17_PURCHASE_SPLIT_SCHEME_CODE
}

export function buildKvo17PurchaseSplitPreview(payload: unknown): Kvo17PurchaseSplitPreview {
  const rows = normalizeRows(payload)
  const first = rows[0]
  const branches = {
    [PURCHASE_KVO01_SLOT]: buildEmptyBranch(PURCHASE_KVO01_SLOT, '01'),
    [PURCHASE_KVO17_SLOT]: buildEmptyBranch(PURCHASE_KVO17_SLOT, '17'),
  }

  for (const row of rows) {
    if (row.sourceDocumentNumber !== first.sourceDocumentNumber || row.sourceDocumentDate !== first.sourceDocumentDate) {
      throw new Error('source_document_identity must be the same for every KVO17 row')
    }
    if (row.sourceSupplierRef !== first.sourceSupplierRef || row.sourceSupplierName !== first.sourceSupplierName) {
      throw new Error('source_supplier_identity must be the same for every KVO17 row')
    }

    const targetSlot = classifyRow(row)
    const branch = branches[targetSlot]
    branch.rowCount += 1
    branch.totalAmount = formatAmount(Number(branch.totalAmount) + row.amount)
    branch.totalVatAmount = formatAmount(Number(branch.totalVatAmount) + row.vatAmount)
  }

  return {
    classifierRevision: KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
    thresholdAmount: formatAmount(KVO17_PURCHASE_SPLIT_THRESHOLD_AMOUNT),
    sourceDocumentIdentity: {
      number: first.sourceDocumentNumber,
      date: first.sourceDocumentDate,
    },
    sourceSupplierProvenance: {
      ref: first.sourceSupplierRef,
      name: first.sourceSupplierName,
    },
    branches,
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
    const sourceKvoOverride = normalizeOverride(row.source_kvo_override, lineNo)
    return {
      lineNo,
      sourceDocumentNumber: requiredText(row, 'source_document_number', lineNo),
      sourceDocumentDate: requiredText(row, 'source_document_date', lineNo),
      sourceSupplierRef: requiredText(row, 'source_supplier_ref', lineNo),
      sourceSupplierName: requiredText(row, 'source_supplier_name', lineNo),
      amount: requiredAmount(row, 'amount', lineNo),
      vatAmount: requiredAmount(row, 'vat_amount', lineNo),
      currency,
      rowId: requiredText(row, 'row_id', lineNo),
      sourceKvoOverride,
    }
  })
}

function classifyRow(row: NormalizedRow): typeof PURCHASE_KVO01_SLOT | typeof PURCHASE_KVO17_SLOT {
  if (row.sourceKvoOverride === '17') {
    return PURCHASE_KVO17_SLOT
  }
  if (row.sourceKvoOverride === '01') {
    return PURCHASE_KVO01_SLOT
  }
  return row.amount <= KVO17_PURCHASE_SPLIT_THRESHOLD_AMOUNT
    ? PURCHASE_KVO17_SLOT
    : PURCHASE_KVO01_SLOT
}

function buildEmptyBranch(
  slotKey: typeof PURCHASE_KVO01_SLOT | typeof PURCHASE_KVO17_SLOT,
  kvo: '01' | '17',
): Kvo17PurchaseSplitPreviewBranch {
  return {
    slotKey,
    kvo,
    rowCount: 0,
    totalAmount: '0.00',
    totalVatAmount: '0.00',
  }
}

function buildDuplicateRowDiagnostics(rows: NormalizedRow[]): Kvo17PurchaseSplitPreviewDiagnostic[] {
  const lineNumbersByRowId = new Map<string, number[]>()
  for (const row of rows) {
    lineNumbersByRowId.set(row.rowId, [...(lineNumbersByRowId.get(row.rowId) ?? []), row.lineNo])
  }
  return [...lineNumbersByRowId.entries()]
    .filter(([, lineNumbers]) => lineNumbers.length > 1)
    .map(([value, lineNumbers]) => ({
      code: 'KVO17_DUPLICATE_ROW_ID',
      field: 'row_id',
      value,
      lineNumbers,
      detail: 'Duplicate KVO17 purchase split row_id.',
    }))
}

function normalizeOverride(raw: unknown, lineNo: number): '01' | '17' | null {
  const value = String(raw ?? '').trim()
  if (!value) {
    return null
  }
  const normalized = value.padStart(2, '0')
  if (normalized === '01' || normalized === '17') {
    return normalized
  }
  throw new Error(`row ${lineNo}: unsupported source_kvo_override ${value}`)
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
