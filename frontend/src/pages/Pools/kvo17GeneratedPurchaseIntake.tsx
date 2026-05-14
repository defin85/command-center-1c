import { useMemo, useState } from 'react'
import { Alert, Button, Descriptions, Input, Select, Space, Tag, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

import type {
  Kvo17GeneratedPurchaseKvo,
  Kvo17GeneratedPurchasePreviewResponse,
  Kvo17GeneratedPurchaseRequestPayload,
} from '../../api/intercompanyPools'
import { usePoolsTranslation } from '../../i18n'
import { resolveApiError } from './masterData/errorUtils'
import type { SchemeIntakeBindingCapability } from './schemeIntake/PoolIntakeSchemeRegistry'

const { Text } = Typography

const fullWidthFieldStyle = { width: '100%', minWidth: 0 } as const

const rangeRowsStyle = {
  display: 'grid',
  gap: 12,
  width: '100%',
  minWidth: 0,
} as const

const rangeRowStyle = {
  display: 'grid',
  gap: 8,
  gridTemplateColumns: 'minmax(160px, 1.2fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 0.8fr)',
  alignItems: 'start',
  width: '100%',
  minWidth: 0,
} as const

const fieldStackStyle = {
  display: 'grid',
  gap: 2,
  minWidth: 0,
} as const

const metaFieldsGridStyle = {
  display: 'grid',
  gap: 8,
  gridTemplateColumns: 'minmax(220px, 1fr) minmax(260px, 1.4fr) auto',
  alignItems: 'end',
  width: '100%',
  minWidth: 0,
} as const

export type Kvo17GeneratedPurchaseCounterpartyOption = {
  value: string
  label: string
  counterparty: {
    counterparty_ref: string
    counterparty_name: string
    counterparty_inn?: string
  }
}

type Kvo17AmountRangeDraft = {
  range_key: 'small' | 'large'
  min_amount: string
  max_amount: string
  kvo: Kvo17GeneratedPurchaseKvo
}

type Kvo17GeneratedPurchaseIntakeProps = {
  poolId: string | null
  periodStart: string
  periodEnd: string
  poolWorkflowBindingId: string
  startOrganizationId: string
  bindingCapability: SchemeIntakeBindingCapability
  counterpartyOptions: Kvo17GeneratedPurchaseCounterpartyOption[]
  loadingCounterparties: boolean
  submitting: boolean
  onPreview: (request: Kvo17GeneratedPurchaseRequestPayload) => Promise<Kvo17GeneratedPurchasePreviewResponse>
  onCreate: (
    request: Kvo17GeneratedPurchaseRequestPayload,
    preview: Kvo17GeneratedPurchasePreviewResponse,
  ) => Promise<void>
}

const DEFAULT_RANGES: Kvo17AmountRangeDraft[] = [
  { range_key: 'small', min_amount: '50.00', max_amount: '100.00', kvo: '17' },
  { range_key: 'large', min_amount: '200.00', max_amount: '300.00', kvo: '01' },
]

function defaultSeed(): string {
  return `kvo17-${new Date().toISOString().slice(0, 10)}`
}

function stableRequestKey(request: Kvo17GeneratedPurchaseRequestPayload | null): string {
  return request ? JSON.stringify(request) : ''
}

function isPositiveAmount(value: string): boolean {
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric > 0
}

export function Kvo17GeneratedPurchaseIntake({
  poolId,
  periodStart,
  periodEnd,
  poolWorkflowBindingId,
  startOrganizationId,
  bindingCapability,
  counterpartyOptions,
  loadingCounterparties,
  submitting,
  onPreview,
  onCreate,
}: Kvo17GeneratedPurchaseIntakeProps) {
  const { t } = usePoolsTranslation()
  const [selectedCounterpartyRefs, setSelectedCounterpartyRefs] = useState<string[]>([])
  const [seed, setSeed] = useState(defaultSeed)
  const [invoiceNumberPrefix, setInvoiceNumberPrefix] = useState('KVO17')
  const [ranges, setRanges] = useState<Kvo17AmountRangeDraft[]>(DEFAULT_RANGES)
  const [preview, setPreview] = useState<Kvo17GeneratedPurchasePreviewResponse | null>(null)
  const [previewRequestKey, setPreviewRequestKey] = useState('')
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [creating, setCreating] = useState(false)

  const selectedCounterparties = useMemo(
    () => selectedCounterpartyRefs
      .map((ref) => counterpartyOptions.find((option) => option.value === ref)?.counterparty ?? null)
      .filter((counterparty): counterparty is Kvo17GeneratedPurchaseCounterpartyOption['counterparty'] => Boolean(counterparty)),
    [counterpartyOptions, selectedCounterpartyRefs],
  )

  const validationMessages = useMemo(() => {
    const messages: string[] = []
    if (!poolId) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.poolRequired'))
    }
    if (!periodStart || !periodEnd) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.periodRequired'))
    }
    if (!poolWorkflowBindingId) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.bindingRequired'))
    }
    if (!startOrganizationId) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.startOrganizationRequired'))
    }
    if (!bindingCapability.available) {
      messages.push(...bindingCapability.diagnostics.map((code) => (
        t(`runs.batchIntake.kvo17Generated.bindingDiagnostics.${code}`)
      )))
    }
    if (selectedCounterparties.length === 0) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.counterpartiesRequired'))
    }
    if (!seed.trim()) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.seedRequired'))
    }
    if (!invoiceNumberPrefix.trim()) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.invoicePrefixRequired'))
    }
    const kvoValues = new Set(ranges.map((range) => range.kvo))
    if (kvoValues.size !== ranges.length) {
      messages.push(t('runs.batchIntake.kvo17Generated.validation.kvoMustDiffer'))
    }
    for (const range of ranges) {
      if (!isPositiveAmount(range.min_amount) || !isPositiveAmount(range.max_amount)) {
        messages.push(t('runs.batchIntake.kvo17Generated.validation.amountPositive', {
          range: t(`runs.batchIntake.kvo17Generated.ranges.${range.range_key}`),
        }))
        continue
      }
      if (Number(range.max_amount) < Number(range.min_amount)) {
        messages.push(t('runs.batchIntake.kvo17Generated.validation.rangeBounds', {
          range: t(`runs.batchIntake.kvo17Generated.ranges.${range.range_key}`),
        }))
      }
    }
    return messages
  }, [
    bindingCapability,
    invoiceNumberPrefix,
    periodEnd,
    periodStart,
    poolId,
    poolWorkflowBindingId,
    ranges,
    seed,
    selectedCounterparties.length,
    startOrganizationId,
    t,
  ])

  const currentRequest = useMemo<Kvo17GeneratedPurchaseRequestPayload | null>(() => {
    if (validationMessages.length > 0) {
      return null
    }
    return {
      period_start: periodStart,
      period_end: periodEnd,
      seed: seed.trim(),
      currency: 'RUB',
      vat_rate: '20%',
      invoice_number_prefix: invoiceNumberPrefix.trim(),
      counterparties: selectedCounterparties,
      amount_ranges: ranges.map((range) => ({
        range_key: range.range_key,
        min_amount: range.min_amount,
        max_amount: range.max_amount,
        kvo: range.kvo,
      })),
    }
  }, [
    invoiceNumberPrefix,
    periodEnd,
    periodStart,
    ranges,
    seed,
    selectedCounterparties,
    validationMessages.length,
  ])
  const currentRequestKey = stableRequestKey(currentRequest)
  const previewIsStale = Boolean(preview && currentRequestKey !== previewRequestKey)
  const previewDisabled = previewing || submitting || creating || validationMessages.length > 0 || !currentRequest
  const createDisabled = submitting || creating || !preview || previewIsStale || !currentRequest

  const updateRange = (rangeKey: Kvo17AmountRangeDraft['range_key'], patch: Partial<Kvo17AmountRangeDraft>) => {
    setRanges((current) => current.map((range) => (
      range.range_key === rangeKey ? { ...range, ...patch } : range
    )))
  }

  const handlePreview = async () => {
    if (!currentRequest) {
      return
    }
    setPreviewing(true)
    setPreviewError(null)
    try {
      const response = await onPreview(currentRequest)
      setPreview(response)
      setPreviewRequestKey(stableRequestKey(currentRequest))
    } catch (error) {
      setPreview(null)
      setPreviewRequestKey('')
      setPreviewError(resolveApiError(error, t('runs.batchIntake.kvo17Generated.messages.previewFailed')).message)
    } finally {
      setPreviewing(false)
    }
  }

  const handleCreate = async () => {
    if (!currentRequest || !preview || previewIsStale) {
      return
    }
    setCreating(true)
    setPreviewError(null)
    try {
      await onCreate(currentRequest, preview)
    } catch (error) {
      setPreviewError(resolveApiError(error, t('runs.batchIntake.messages.failedToCreate')).message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }} data-testid="pool-runs-batch-intake-kvo17-generated">
      <Alert
        type="info"
        showIcon
        message={t('runs.batchIntake.kvo17Generated.title')}
        description={t('runs.batchIntake.kvo17Generated.description')}
      />

      {validationMessages.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          data-testid="pool-runs-batch-intake-kvo17-generated-validation"
          message={t('runs.batchIntake.kvo17Generated.validation.title')}
          description={validationMessages.join(' ')}
        />
      ) : null}

      {previewError ? (
        <Alert
          type="error"
          showIcon
          data-testid="pool-runs-batch-intake-kvo17-generated-error"
          message={t('runs.batchIntake.kvo17Generated.messages.previewFailed')}
          description={previewError}
        />
      ) : null}

      <Space direction="vertical" size="small" style={{ width: '100%' }} data-testid="pool-runs-batch-intake-kvo17-generated-counterparties-field">
        <Text strong>{t('runs.batchIntake.kvo17Generated.counterparties')}</Text>
        <Select
          mode="multiple"
          data-testid="pool-runs-batch-intake-kvo17-generated-counterparties"
          loading={loadingCounterparties}
          value={selectedCounterpartyRefs}
          options={counterpartyOptions}
          placeholder={t('runs.batchIntake.kvo17Generated.placeholders.counterparties')}
          onChange={setSelectedCounterpartyRefs}
          style={fullWidthFieldStyle}
        />
      </Space>

      <div data-testid="pool-runs-batch-intake-kvo17-generated-ranges" style={rangeRowsStyle}>
        {ranges.map((range) => (
          <div key={range.range_key} data-testid={`pool-runs-batch-intake-kvo17-generated-range-${range.range_key}`} style={rangeRowStyle}>
            <Text strong style={{ paddingTop: 24 }}>
              {t(`runs.batchIntake.kvo17Generated.ranges.${range.range_key}`)}
            </Text>
            <Space direction="vertical" size={2} style={fieldStackStyle}>
              <Text type="secondary">{t('runs.batchIntake.kvo17Generated.fields.minAmount')}</Text>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={range.min_amount}
                onChange={(event) => updateRange(range.range_key, { min_amount: event.target.value })}
                data-testid={`pool-runs-batch-intake-kvo17-generated-${range.range_key}-min`}
                style={fullWidthFieldStyle}
              />
            </Space>
            <Space direction="vertical" size={2} style={fieldStackStyle}>
              <Text type="secondary">{t('runs.batchIntake.kvo17Generated.fields.maxAmount')}</Text>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={range.max_amount}
                onChange={(event) => updateRange(range.range_key, { max_amount: event.target.value })}
                data-testid={`pool-runs-batch-intake-kvo17-generated-${range.range_key}-max`}
                style={fullWidthFieldStyle}
              />
            </Space>
            <Space direction="vertical" size={2} style={fieldStackStyle}>
              <Text type="secondary">KVO</Text>
              <Select
                value={range.kvo}
                onChange={(value) => updateRange(range.range_key, { kvo: value })}
                data-testid={`pool-runs-batch-intake-kvo17-generated-${range.range_key}-kvo`}
                options={[
                  { value: '01', label: 'KVO 01' },
                  { value: '17', label: 'KVO 17' },
                ]}
                style={fullWidthFieldStyle}
              />
            </Space>
          </div>
        ))}
      </div>

      <div data-testid="pool-runs-batch-intake-kvo17-generated-meta" style={metaFieldsGridStyle}>
        <Space direction="vertical" size={2} style={fieldStackStyle}>
          <Text type="secondary">{t('runs.batchIntake.kvo17Generated.fields.invoicePrefix')}</Text>
          <Input
            value={invoiceNumberPrefix}
            onChange={(event) => setInvoiceNumberPrefix(event.target.value)}
            data-testid="pool-runs-batch-intake-kvo17-generated-invoice-prefix"
            style={fullWidthFieldStyle}
          />
        </Space>
        <Space direction="vertical" size={2} style={fieldStackStyle}>
          <Text type="secondary">{t('runs.batchIntake.kvo17Generated.fields.seed')}</Text>
          <Input
            value={seed}
            onChange={(event) => setSeed(event.target.value)}
            data-testid="pool-runs-batch-intake-kvo17-generated-seed"
            style={fullWidthFieldStyle}
          />
        </Space>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => setSeed(`kvo17-${Date.now().toString(36)}`)}
          data-testid="pool-runs-batch-intake-kvo17-generated-regenerate"
        >
          {t('runs.batchIntake.kvo17Generated.actions.regenerate')}
        </Button>
      </div>

      <Space size={8} wrap>
        <Button
          type="primary"
          disabled={previewDisabled}
          loading={previewing}
          onClick={() => void handlePreview()}
          data-testid="pool-runs-batch-intake-kvo17-generated-preview"
        >
          {t('runs.batchIntake.kvo17Generated.actions.preview')}
        </Button>
        <Button
          disabled={createDisabled}
          loading={creating}
          onClick={() => void handleCreate()}
          data-testid="pool-runs-batch-intake-kvo17-generated-create"
        >
          {t('runs.batchIntake.kvo17Generated.actions.createRun')}
        </Button>
      </Space>

      {previewIsStale ? (
        <Alert
          type="warning"
          showIcon
          data-testid="pool-runs-batch-intake-kvo17-generated-stale-preview"
          message={t('runs.batchIntake.kvo17Generated.messages.stalePreview')}
        />
      ) : null}

      {preview ? (
        <Space direction="vertical" size="small" style={{ width: '100%' }} data-testid="pool-runs-batch-intake-kvo17-generated-preview-panel">
          <Alert
            type="success"
            showIcon
            message={t('runs.batchIntake.kvo17Generated.preview.title')}
            description={t('runs.batchIntake.kvo17Generated.preview.description')}
          />
          <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
            <Descriptions.Item label={t('runs.batchIntake.kvo17Generated.preview.rows')}>
              {String(preview.manifest.summary.processed_rows ?? preview.manifest.rows.length)}
            </Descriptions.Item>
            <Descriptions.Item label={t('runs.batchIntake.kvo17Generated.preview.counterparties')}>
              {String(preview.manifest.summary.selected_counterparties ?? preview.manifest.counterparties.length)}
            </Descriptions.Item>
            <Descriptions.Item label={t('runs.batchIntake.kvo17Generated.preview.requestHash')}>
              <Text code>{preview.request_hash}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t('runs.batchIntake.kvo17Generated.preview.contentHash')}>
              <Text code>{preview.content_hash}</Text>
            </Descriptions.Item>
          </Descriptions>
          <Space size={[8, 8]} wrap>
            {preview.manifest.amount_ranges.map((range) => (
              <Tag key={range.range_key} color={range.kvo === '17' ? 'green' : 'blue'}>
                {t('runs.batchIntake.kvo17Generated.preview.rangeSummary', {
                  range: t(`runs.batchIntake.kvo17Generated.ranges.${range.range_key}`),
                  kvo: range.kvo,
                  min: range.min_amount,
                  max: range.max_amount,
                })}
              </Tag>
            ))}
          </Space>
          <Text type="secondary">
            {t('runs.batchIntake.kvo17Generated.preview.invoiceIdentityNotice')}
          </Text>
        </Space>
      ) : null}
    </Space>
  )
}
