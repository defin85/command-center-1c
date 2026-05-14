import { useEffect, useMemo, useState } from 'react'
import { Alert, App as AntApp, Button, Descriptions, Form, Input, Radio, Select, Space, Tag, Typography, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'

import {
  createPoolBatch,
  listMasterDataParties,
  previewKvo17GeneratedPurchase,
  type Kvo17GeneratedPurchasePreviewResponse,
  type Kvo17GeneratedPurchaseRequestPayload,
  type PoolBatchCreatePayload,
  type PoolBatchCreateResponse,
  type PoolBatchKind,
  type PoolMasterParty,
  type PoolSchemaTemplate,
  type PoolWorkflowBinding,
} from '../../api/intercompanyPools'
import { DrawerFormShell } from '../../components/platform/DrawerFormShell'
import { usePoolsTranslation } from '../../i18n'
import { resolveApiError } from './masterData/errorUtils'
import {
  PURCHASE_KVO01_SLOT,
  PURCHASE_KVO17_SLOT,
  buildKvo17PurchaseSplitPreview,
  isKvo17PurchaseSplitSchemaTemplate,
  type Kvo17PurchaseSplitPreview,
} from './kvo17PurchaseSplitPreview'
import {
  ADVANCE_INVOICE_KVO01_SLOT,
  ADVANCE_OFFSET_KVO18_SLOT,
  CASH_RECEIPT_ORDER_SLOT,
  DECLARATION_EVIDENCE_SLOT,
  buildKvo18AdvanceVatOffsetPreview,
  isKvo18AdvanceVatOffsetSchemaTemplate,
  type Kvo18AdvanceVatOffsetPreview,
  type Kvo18StageSlot,
} from './kvo18AdvanceVatOffsetPreview'
import { Kvo17GeneratedPurchaseIntake, type Kvo17GeneratedPurchaseCounterpartyOption } from './kvo17GeneratedPurchaseIntake'
import {
  KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
  SCHEMA_TEMPLATE_UPLOAD_SOURCE_TYPE,
  type PoolBatchIntakeSourceMode,
  resolveKvo17GeneratedPurchaseBindingCapability,
} from './schemeIntake/PoolIntakeSchemeRegistry'


const { Text } = Typography
const { TextArea } = Input

type SelectOption = {
  value: string
  label: string
}

type BatchIntakeFormValues = {
  batch_kind: PoolBatchKind
  source_mode?: PoolBatchIntakeSourceMode
  period_start: string
  period_end?: string
  schema_template_id?: string
  pool_workflow_binding_id?: string
  start_organization_id?: string
  source_reference?: string
  raw_payload_ref?: string
  source_payload_json?: string
  xlsx_base64?: string
  uploaded_file_name?: string
}

type BatchIntakeSubmitOptions = {
  kvo18StageIntent?: Kvo18StageSlot
  kvo18Preview?: Kvo18AdvanceVatOffsetPreview | null
}

type PoolsTranslate = ReturnType<typeof usePoolsTranslation>['t']

type PoolBatchIntakeDrawerProps = {
  open: boolean
  poolId: string | null
  poolLabel: string
  schemaTemplates: PoolSchemaTemplate[]
  loadingSchemaTemplates: boolean
  workflowBindingOptions: SelectOption[]
  workflowBindings?: PoolWorkflowBinding[]
  startOrganizationOptions: SelectOption[]
  initialValues: {
    batchKind: PoolBatchKind
    periodStart: string
    periodEnd?: string | null
    poolWorkflowBindingId?: string | null
    startOrganizationId?: string | null
  }
  onClose: () => void
  onCreated: (
    response: PoolBatchCreateResponse,
    context: {
      batchKind: PoolBatchKind
      periodStart: string
      periodEnd: string | null
      poolWorkflowBindingId: string | null
      startOrganizationId: string | null
    },
  ) => Promise<void> | void
}

const DEFAULT_JSON_PAYLOAD = JSON.stringify(
  [{ inn: '730000000001', amount: '100.00', external_id: 'batch-row-001' }],
  null,
  2,
)

function parseBatchPayloadJson(
  raw: string,
  t: PoolsTranslate
): Record<string, unknown> | Array<Record<string, unknown>> {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error(t('runs.batchIntake.validation.invalidJson'))
  }
  if (!parsed || (typeof parsed !== 'object' && !Array.isArray(parsed))) {
    throw new Error(t('runs.batchIntake.validation.objectOrArrayExpected'))
  }
  if (!Array.isArray(parsed)) {
    return parsed as Record<string, unknown>
  }
  return parsed.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new Error(t('runs.batchIntake.validation.arrayItemsMustBeObjects'))
    }
    return item as Record<string, unknown>
  })
}

async function readFileAsBase64(
  file: File,
  t: PoolsTranslate
): Promise<string> {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(t('runs.batchIntake.messages.failedToReadFile', { fileName: file.name })))
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      const base64 = result.includes(',') ? result.split(',')[1] : result
      resolve(base64)
    }
    reader.readAsDataURL(file)
  })
}

function requireTrimmedValue(
  value: string | undefined,
  fieldName: string,
  t: PoolsTranslate
): string {
  const normalized = value?.trim() || ''
  if (!normalized) {
    throw new Error(t('runs.batchIntake.validation.fieldRequired', { fieldName }))
  }
  return normalized
}

function buildPoolBatchCreatePayload(
  values: BatchIntakeFormValues,
  poolId: string,
  t: PoolsTranslate,
  options: BatchIntakeSubmitOptions = {},
): PoolBatchCreatePayload {
  const sourceMetadata = buildKvo18StageSourceMetadata(options)
  const payloadBase = {
    pool_id: poolId,
    source_type: 'schema_template_upload' as const,
    schema_template_id: requireTrimmedValue(values.schema_template_id, 'schema_template_id', t),
    period_start: values.period_start,
    period_end: values.period_end?.trim() || null,
    source_reference: values.source_reference?.trim() || '',
    raw_payload_ref: values.raw_payload_ref?.trim() || '',
    ...(sourceMetadata ? { source_metadata: sourceMetadata } : {}),
  }
  const xlsxBase64 = values.xlsx_base64?.trim() || ''

  if (values.batch_kind === 'receipt') {
    const receiptScope = {
      pool_workflow_binding_id: requireTrimmedValue(values.pool_workflow_binding_id, 'pool_workflow_binding_id', t),
      start_organization_id: requireTrimmedValue(values.start_organization_id, 'start_organization_id', t),
    }
    if (xlsxBase64) {
      return {
        ...payloadBase,
        ...receiptScope,
        batch_kind: 'receipt',
        xlsx_base64: xlsxBase64,
      }
    }
    const rawPayloadJson = values.source_payload_json?.trim() || ''
    if (!rawPayloadJson) {
      throw new Error(t('runs.batchIntake.validation.sourcePayloadRequired'))
    }
    return {
      ...payloadBase,
      ...receiptScope,
      batch_kind: 'receipt',
      json_payload: parseBatchPayloadJson(rawPayloadJson, t),
    }
  }

  if (xlsxBase64) {
    return {
      ...payloadBase,
      batch_kind: 'sale',
      xlsx_base64: xlsxBase64,
    }
  }

  const rawPayloadJson = values.source_payload_json?.trim() || ''
  if (!rawPayloadJson) {
    throw new Error(t('runs.batchIntake.validation.sourcePayloadRequired'))
  }
  return {
    ...payloadBase,
    batch_kind: 'sale',
    json_payload: parseBatchPayloadJson(rawPayloadJson, t),
  }
}

function buildKvo18StageSourceMetadata(
  options: BatchIntakeSubmitOptions,
): Record<string, unknown> | null {
  if (!options.kvo18StageIntent) {
    return null
  }
  return {
    kvo18_stage_intent: options.kvo18StageIntent,
    kvo18_policy_revision: options.kvo18Preview?.policyRevision ?? '',
  }
}

export function PoolBatchIntakeDrawer({
  open,
  poolId,
  poolLabel,
  schemaTemplates,
  loadingSchemaTemplates,
  workflowBindingOptions,
  workflowBindings = [],
  startOrganizationOptions,
  initialValues,
  onClose,
  onCreated,
}: PoolBatchIntakeDrawerProps) {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const [form] = Form.useForm<BatchIntakeFormValues>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [counterparties, setCounterparties] = useState<PoolMasterParty[]>([])
  const [loadingCounterparties, setLoadingCounterparties] = useState(false)
  const batchKind = Form.useWatch('batch_kind', form) ?? initialValues.batchKind
  const sourceMode = Form.useWatch('source_mode', form) ?? SCHEMA_TEMPLATE_UPLOAD_SOURCE_TYPE
  const uploadedFileName = Form.useWatch('uploaded_file_name', form)
  const selectedSchemaTemplateId = Form.useWatch('schema_template_id', form)
  const selectedWorkflowBindingId = Form.useWatch('pool_workflow_binding_id', form)
  const periodStart = Form.useWatch('period_start', form) ?? initialValues.periodStart
  const periodEnd = Form.useWatch('period_end', form) ?? (initialValues.periodEnd ?? '')
  const selectedStartOrganizationId = Form.useWatch('start_organization_id', form) ?? (initialValues.startOrganizationId ?? '')
  const sourcePayloadJson = Form.useWatch('source_payload_json', form)
  const selectedSchemaTemplate = useMemo(
    () => schemaTemplates.find((item) => item.id === selectedSchemaTemplateId) ?? null,
    [schemaTemplates, selectedSchemaTemplateId],
  )
  const kvo17PreviewState = useMemo(() => {
    if (!isKvo17PurchaseSplitSchemaTemplate(selectedSchemaTemplate)) {
      return null
    }
    const rawPayloadJson = sourcePayloadJson?.trim() || ''
    if (!rawPayloadJson) {
      return { preview: null, error: t('runs.batchIntake.validation.sourcePayloadRequired') }
    }
    try {
      return {
        preview: buildKvo17PurchaseSplitPreview(parseBatchPayloadJson(rawPayloadJson, t)),
        error: null,
      }
    } catch (error) {
      return {
        preview: null,
        error: error instanceof Error ? error.message : String(error),
      }
    }
  }, [selectedSchemaTemplate, sourcePayloadJson, t])
  const kvo18PreviewState = useMemo(() => {
    if (!isKvo18AdvanceVatOffsetSchemaTemplate(selectedSchemaTemplate)) {
      return null
    }
    const rawPayloadJson = sourcePayloadJson?.trim() || ''
    if (!rawPayloadJson) {
      return { preview: null, error: t('runs.batchIntake.validation.sourcePayloadRequired') }
    }
    try {
      return {
        preview: buildKvo18AdvanceVatOffsetPreview(parseBatchPayloadJson(rawPayloadJson, t)),
        error: null,
      }
    } catch (error) {
      return {
        preview: null,
        error: error instanceof Error ? error.message : String(error),
      }
    }
  }, [selectedSchemaTemplate, sourcePayloadJson, t])
  const kvo18HasBlockingDiagnostics = Boolean(kvo18PreviewState?.preview?.diagnostics.length)
  const isGeneratedPurchaseMode = batchKind === 'receipt' && sourceMode === KVO17_GENERATED_PURCHASE_SOURCE_TYPE
  const selectedWorkflowBinding = useMemo(
    () => workflowBindings.find((binding) => binding.binding_id === selectedWorkflowBindingId) ?? null,
    [selectedWorkflowBindingId, workflowBindings],
  )
  const generatedPurchaseBindingCapability = useMemo(
    () => resolveKvo17GeneratedPurchaseBindingCapability(selectedWorkflowBinding),
    [selectedWorkflowBinding],
  )
  const compatibleGeneratedPurchaseBinding = useMemo(
    () => workflowBindings.find((binding) => resolveKvo17GeneratedPurchaseBindingCapability(binding).available) ?? null,
    [workflowBindings],
  )
  const generatedPurchaseSourceModeAvailable = (
    generatedPurchaseBindingCapability.available || compatibleGeneratedPurchaseBinding !== null
  )
  const counterpartyOptions = useMemo<Kvo17GeneratedPurchaseCounterpartyOption[]>(
    () => counterparties.map((counterparty) => ({
      value: counterparty.canonical_id,
      label: `${counterparty.name}${counterparty.inn ? ` · ${counterparty.inn}` : ''}`,
      counterparty: {
        counterparty_ref: counterparty.canonical_id,
        counterparty_name: counterparty.name,
        counterparty_inn: counterparty.inn,
      },
    })),
    [counterparties],
  )

  useEffect(() => {
    if (!open) {
      return
    }
    form.setFieldsValue({
      batch_kind: initialValues.batchKind,
      source_mode: SCHEMA_TEMPLATE_UPLOAD_SOURCE_TYPE,
      period_start: initialValues.periodStart,
      period_end: initialValues.periodEnd ?? '',
      pool_workflow_binding_id: initialValues.poolWorkflowBindingId ?? undefined,
      start_organization_id: initialValues.startOrganizationId ?? undefined,
      source_reference: '',
      raw_payload_ref: '',
      source_payload_json: DEFAULT_JSON_PAYLOAD,
      xlsx_base64: undefined,
      uploaded_file_name: '',
    })
    setSubmitError(null)
  }, [form, initialValues, open])

  useEffect(() => {
    if (!open || !isGeneratedPurchaseMode) {
      return
    }
    if (!generatedPurchaseBindingCapability.available && compatibleGeneratedPurchaseBinding) {
      form.setFields([
        {
          name: 'pool_workflow_binding_id',
          value: compatibleGeneratedPurchaseBinding.binding_id,
        },
      ])
    }
    let cancelled = false
    setLoadingCounterparties(true)
    listMasterDataParties({ role: 'counterparty', limit: 200, offset: 0 })
      .then((response) => {
        if (!cancelled) {
          setCounterparties(response.parties)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          const resolved = resolveApiError(error, t('runs.batchIntake.kvo17Generated.messages.counterpartiesFailed'))
          setSubmitError(resolved.message)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingCounterparties(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [
    compatibleGeneratedPurchaseBinding,
    form,
    generatedPurchaseBindingCapability.available,
    isGeneratedPurchaseMode,
    open,
    t,
  ])

  const handleUploadFile = async (file: File) => {
    if (file.name.toLowerCase().endsWith('.json')) {
      const payloadText = await file.text()
      form.setFieldsValue({
        source_payload_json: payloadText,
        xlsx_base64: undefined,
        uploaded_file_name: file.name,
        raw_payload_ref: form.getFieldValue('raw_payload_ref') || file.name,
      })
      message.success(t('runs.batchIntake.messages.loadedJsonPayload', { fileName: file.name }))
      return false
    }

    const xlsxBase64 = await readFileAsBase64(file, t)
    form.setFieldsValue({
      xlsx_base64: xlsxBase64,
      source_payload_json: '',
      uploaded_file_name: file.name,
      raw_payload_ref: form.getFieldValue('raw_payload_ref') || file.name,
    })
    message.success(t('runs.batchIntake.messages.loadedBinaryPayload', { fileName: file.name }))
    return false
  }

  const handleSubmit = async (options: BatchIntakeSubmitOptions = {}) => {
    if (!poolId) {
      setSubmitError(t('runs.batchIntake.messages.selectPoolBeforeCreate'))
      return
    }

    let values: BatchIntakeFormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      const payload = buildPoolBatchCreatePayload(values, poolId, t, options)
      const response = await createPoolBatch(payload)
      await onCreated(response, {
        batchKind: values.batch_kind,
        periodStart: values.period_start,
        periodEnd: values.period_end?.trim() || null,
        poolWorkflowBindingId: values.pool_workflow_binding_id?.trim() || null,
        startOrganizationId: values.start_organization_id?.trim() || null,
      })
      message.success(
        values.batch_kind === 'receipt'
          ? t('runs.batchIntake.messages.receiptAccepted')
          : t('runs.batchIntake.messages.saleAccepted')
      )
    } catch (error) {
      const resolved = resolveApiError(error, t('runs.batchIntake.messages.failedToCreate'))
      setSubmitError(resolved.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleGeneratedPreview = async (
    requestPayload: Kvo17GeneratedPurchaseRequestPayload,
  ): Promise<Kvo17GeneratedPurchasePreviewResponse> => {
    if (!poolId) {
      throw new Error(t('runs.batchIntake.messages.selectPoolBeforeCreate'))
    }
    const values = await form.validateFields([
      'period_start',
      'period_end',
      'pool_workflow_binding_id',
    ])
    const periodEndValue = values.period_end?.trim() || ''
    if (!periodEndValue) {
      throw new Error(t('runs.batchIntake.kvo17Generated.validation.periodRequired'))
    }
    return previewKvo17GeneratedPurchase({
      pool_id: poolId,
      pool_workflow_binding_id: requireTrimmedValue(
        values.pool_workflow_binding_id,
        'pool_workflow_binding_id',
        t,
      ),
      period_start: values.period_start,
      period_end: periodEndValue,
      json_payload: requestPayload,
    })
  }

  const handleGeneratedCreate = async (
    requestPayload: Kvo17GeneratedPurchaseRequestPayload,
    preview: Kvo17GeneratedPurchasePreviewResponse,
  ) => {
    if (!poolId) {
      throw new Error(t('runs.batchIntake.messages.selectPoolBeforeCreate'))
    }
    let values: BatchIntakeFormValues
    try {
      values = await form.validateFields([
        'period_start',
        'period_end',
        'pool_workflow_binding_id',
        'start_organization_id',
        'source_reference',
        'raw_payload_ref',
      ])
    } catch {
      return
    }
    const periodEndValue = values.period_end?.trim() || ''
    if (!periodEndValue) {
      throw new Error(t('runs.batchIntake.kvo17Generated.validation.periodRequired'))
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      const payload: PoolBatchCreatePayload = {
        pool_id: poolId,
        source_type: KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
        batch_kind: 'receipt',
        pool_workflow_binding_id: requireTrimmedValue(
          values.pool_workflow_binding_id,
          'pool_workflow_binding_id',
          t,
        ),
        start_organization_id: requireTrimmedValue(
          values.start_organization_id,
          'start_organization_id',
          t,
        ),
        period_start: values.period_start,
        period_end: periodEndValue,
        source_reference: values.source_reference?.trim() || `kvo17-generated-${preview.content_hash.slice(0, 12)}`,
        raw_payload_ref: values.raw_payload_ref?.trim() || '',
        source_metadata: {
          kvo17_generated_purchase: {
            accepted_manifest: preview.manifest,
            accepted_request_hash: preview.request_hash,
            accepted_content_hash: preview.content_hash,
          },
        },
        json_payload: requestPayload,
      }
      const response = await createPoolBatch(payload)
      await onCreated(response, {
        batchKind: 'receipt',
        periodStart: values.period_start,
        periodEnd: periodEndValue,
        poolWorkflowBindingId: values.pool_workflow_binding_id?.trim() || null,
        startOrganizationId: values.start_organization_id?.trim() || null,
      })
      message.success(t('runs.batchIntake.messages.receiptAccepted'))
      onClose()
    } catch (error) {
      const resolved = resolveApiError(error, t('runs.batchIntake.messages.failedToCreate'))
      setSubmitError(resolved.message)
      throw error
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <DrawerFormShell
      open={open}
      onClose={onClose}
      onSubmit={isGeneratedPurchaseMode ? undefined : () => handleSubmit()}
      title={t('runs.batchIntake.title')}
      subtitle={t('runs.batchIntake.subtitle', { poolLabel })}
      submitText={t('runs.batchIntake.submit')}
      confirmLoading={submitting}
      submitDisabled={Boolean(kvo17PreviewState?.error || kvo18PreviewState?.error || kvo18HasBlockingDiagnostics)}
      submitButtonTestId="pool-runs-batch-intake-submit"
      drawerTestId="pool-runs-batch-intake-drawer"
      width={880}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {submitError ? (
          <Alert
            type="error"
            showIcon
            message={t('runs.batchIntake.alerts.failedTitle')}
            description={submitError}
          />
        ) : null}
        <Alert
          type="info"
          showIcon
          message={t('runs.batchIntake.alerts.failClosedTitle')}
          description={t('runs.batchIntake.alerts.failClosedDescription')}
        />
        <Form form={form} layout="vertical">
          <Form.Item name="batch_kind" label={t('runs.batchIntake.fields.batchKind')} rules={[{ required: true }]}>
            <Radio.Group data-testid="pool-runs-batch-intake-kind" optionType="button" buttonStyle="solid">
              <Radio.Button value="receipt">{t('runs.batchIntake.options.receipt')}</Radio.Button>
              <Radio.Button value="sale">{t('runs.batchIntake.options.sale')}</Radio.Button>
            </Radio.Group>
          </Form.Item>
          {batchKind === 'receipt' ? (
            <Form.Item name="source_mode" label={t('runs.batchIntake.fields.sourceMode')} rules={[{ required: true }]}>
              <Radio.Group
                data-testid="pool-runs-batch-intake-source-mode"
                optionType="button"
                buttonStyle="solid"
              >
                <Radio.Button value={SCHEMA_TEMPLATE_UPLOAD_SOURCE_TYPE}>
                  {t('runs.batchIntake.options.schemaTemplateUpload')}
                </Radio.Button>
                <Radio.Button
                  value={KVO17_GENERATED_PURCHASE_SOURCE_TYPE}
                  disabled={!generatedPurchaseSourceModeAvailable}
                >
                  {t('runs.batchIntake.options.kvo17GeneratedPurchase')}
                </Radio.Button>
              </Radio.Group>
            </Form.Item>
          ) : null}
          <Space size={12} wrap style={{ width: '100%' }}>
            <Form.Item
              name="period_start"
              label={t('runs.create.fields.periodStart')}
              rules={[{ required: true, message: t('runs.batchIntake.validation.periodStartRequired') }]}
              style={{ minWidth: 180 }}
            >
              <Input type="date" />
            </Form.Item>
            <Form.Item name="period_end" label={t('runs.create.fields.periodEnd')} style={{ minWidth: 180 }}>
              <Input type="date" />
            </Form.Item>
          </Space>
          {!isGeneratedPurchaseMode ? (
            <Form.Item
              name="schema_template_id"
              label={t('runs.create.fields.schemaTemplate')}
              rules={[{ required: true, message: t('runs.batchIntake.validation.schemaTemplateRequired') }]}
            >
              <Select
                data-testid="pool-runs-batch-intake-schema-template"
                loading={loadingSchemaTemplates}
                options={schemaTemplates.map((item) => ({
                  value: item.id,
                  label: `${item.code} - ${item.name}`,
                }))}
                placeholder={t('runs.batchIntake.placeholders.selectSchemaTemplate')}
              />
            </Form.Item>
          ) : null}
          {batchKind === 'receipt' ? (
            <Space direction="vertical" size={0} style={{ width: '100%' }}>
              <Form.Item
                name="pool_workflow_binding_id"
                label={t('runs.create.fields.workflowBinding')}
                rules={[{ required: true, message: t('runs.batchIntake.validation.workflowBindingRequired') }]}
              >
                <Select
                  data-testid="pool-runs-batch-intake-binding"
                  options={workflowBindingOptions}
                  placeholder={t('runs.create.placeholders.selectBinding')}
                />
              </Form.Item>
              <Form.Item
                name="start_organization_id"
                label={t('runs.create.fields.startOrganization')}
                rules={[{ required: true, message: t('runs.batchIntake.validation.startOrganizationRequired') }]}
              >
                <Select
                  data-testid="pool-runs-batch-intake-start-organization"
                  options={startOrganizationOptions}
                  placeholder={t('runs.create.placeholders.selectStartOrganization')}
                />
              </Form.Item>
            </Space>
          ) : null}
          <Form.Item name="source_reference" label={t('runs.batchIntake.fields.sourceReference')}>
            <Input data-testid="pool-runs-batch-intake-source-reference" placeholder={t('runs.batchIntake.placeholders.sourceReference')} />
          </Form.Item>
          <Form.Item name="raw_payload_ref" label={t('runs.batchIntake.fields.rawPayloadReference')}>
            <Input placeholder={t('runs.batchIntake.placeholders.rawPayloadReference')} />
          </Form.Item>
          {isGeneratedPurchaseMode ? (
            <Kvo17GeneratedPurchaseIntake
              poolId={poolId}
              periodStart={periodStart}
              periodEnd={periodEnd}
              poolWorkflowBindingId={selectedWorkflowBindingId ?? ''}
              startOrganizationId={selectedStartOrganizationId}
              bindingCapability={generatedPurchaseBindingCapability}
              counterpartyOptions={counterpartyOptions}
              loadingCounterparties={loadingCounterparties}
              submitting={submitting}
              onPreview={handleGeneratedPreview}
              onCreate={handleGeneratedCreate}
            />
          ) : (
            <>
              <Form.Item
                name="source_payload_json"
                label={t('runs.batchIntake.fields.sourcePayloadJson')}
                extra={t('runs.batchIntake.fields.sourcePayloadExtra')}
              >
                <TextArea
                  data-testid="pool-runs-batch-intake-source-payload"
                  autoSize={{ minRows: 6, maxRows: 14 }}
                />
              </Form.Item>
              {kvo17PreviewState ? (
            <Kvo17PurchaseSplitPreviewPanel
              preview={kvo17PreviewState.preview}
              error={kvo17PreviewState.error}
              t={t}
            />
              ) : null}
              {kvo18PreviewState ? (
            <Kvo18AdvanceVatOffsetPreviewPanel
              preview={kvo18PreviewState.preview}
              error={kvo18PreviewState.error}
              t={t}
              stageActionsDisabled={submitting || kvo18HasBlockingDiagnostics}
              onStageSubmit={(slotKey) => {
                void handleSubmit({
                  kvo18StageIntent: slotKey,
                  kvo18Preview: kvo18PreviewState.preview,
                })
              }}
            />
              ) : null}
              <Form.Item name="xlsx_base64" hidden>
                <Input />
              </Form.Item>
              <Form.Item name="uploaded_file_name" hidden>
                <Input />
              </Form.Item>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Upload
                  accept=".json,.xlsx,.xls,.csv"
                  maxCount={1}
                  showUploadList={false}
                  beforeUpload={(file) => {
                    void handleUploadFile(file)
                    return false
                  }}
                >
                  <Button icon={<UploadOutlined />}>{t('runs.batchIntake.actions.loadPayloadFile')}</Button>
                </Upload>
                {uploadedFileName ? <Text type="secondary">{t('runs.batchIntake.fields.loadedFile', { fileName: uploadedFileName })}</Text> : null}
              </Space>
            </>
          )}
        </Form>
      </Space>
    </DrawerFormShell>
  )
}

function Kvo17PurchaseSplitPreviewPanel({
  preview,
  error,
  t,
}: {
  preview: Kvo17PurchaseSplitPreview | null
  error: string | null
  t: PoolsTranslate
}) {
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        data-testid="pool-runs-batch-intake-kvo17-preview-error"
        message={t('runs.batchIntake.kvo17Preview.blockedTitle')}
        description={error}
      />
    )
  }
  if (!preview) {
    return null
  }
  const kvo01 = preview.branches[PURCHASE_KVO01_SLOT]
  const kvo17 = preview.branches[PURCHASE_KVO17_SLOT]

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }} data-testid="pool-runs-batch-intake-kvo17-preview">
      <Alert
        type={preview.diagnostics.length > 0 ? 'warning' : 'success'}
        showIcon
        message={t('runs.batchIntake.kvo17Preview.title')}
        description={t('runs.batchIntake.kvo17Preview.description')}
      />
      <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
        <Descriptions.Item label={t('runs.batchIntake.kvo17Preview.classifierRevision')}>
          <Text code>{preview.classifierRevision}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t('runs.batchIntake.kvo17Preview.threshold')}>
          <Text>{preview.thresholdAmount} RUB</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t('runs.batchIntake.kvo17Preview.sourceDocument')}>
          <Text>{preview.sourceDocumentIdentity.number} · {preview.sourceDocumentIdentity.date}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t('runs.batchIntake.kvo17Preview.sourceSupplier')}>
          <Text>{preview.sourceSupplierProvenance.name} · {preview.sourceSupplierProvenance.ref}</Text>
        </Descriptions.Item>
      </Descriptions>
      <Space size={[8, 8]} wrap>
        <Tag color="blue" data-testid="pool-runs-batch-intake-kvo17-preview-kvo01">
          {t('runs.batchIntake.kvo17Preview.branchSummary', {
            kvo: kvo01.kvo,
            rows: kvo01.rowCount,
            amount: kvo01.totalAmount,
            vat: kvo01.totalVatAmount,
          })}
        </Tag>
        <Tag color="green" data-testid="pool-runs-batch-intake-kvo17-preview-kvo17">
          {t('runs.batchIntake.kvo17Preview.branchSummary', {
            kvo: kvo17.kvo,
            rows: kvo17.rowCount,
            amount: kvo17.totalAmount,
            vat: kvo17.totalVatAmount,
          })}
        </Tag>
      </Space>
      {preview.diagnostics.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          data-testid="pool-runs-batch-intake-kvo17-preview-diagnostics"
          message={t('runs.batchIntake.kvo17Preview.diagnosticsTitle')}
          description={preview.diagnostics.map((item) => item.detail).join(' ')}
        />
      ) : (
        <Text type="secondary">{t('runs.batchIntake.kvo17Preview.noDiagnostics')}</Text>
      )}
    </Space>
  )
}

function Kvo18AdvanceVatOffsetPreviewPanel({
  preview,
  error,
  t,
  stageActionsDisabled,
  onStageSubmit,
}: {
  preview: Kvo18AdvanceVatOffsetPreview | null
  error: string | null
  t: PoolsTranslate
  stageActionsDisabled: boolean
  onStageSubmit: (slotKey: Kvo18StageSlot) => void
}) {
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        data-testid="pool-runs-batch-intake-kvo18-preview-error"
        message={t('runs.batchIntake.kvo18Preview.blockedTitle')}
        description={error}
      />
    )
  }
  if (!preview) {
    return null
  }
  const stageOrder: Kvo18StageSlot[] = [
    CASH_RECEIPT_ORDER_SLOT,
    ADVANCE_INVOICE_KVO01_SLOT,
    ADVANCE_OFFSET_KVO18_SLOT,
    DECLARATION_EVIDENCE_SLOT,
  ]

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }} data-testid="pool-runs-batch-intake-kvo18-preview">
      <Alert
        type={preview.diagnostics.length > 0 ? 'warning' : 'success'}
        showIcon
        message={t('runs.batchIntake.kvo18Preview.title')}
        description={t('runs.batchIntake.kvo18Preview.description')}
      />
      <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
        <Descriptions.Item label={t('runs.batchIntake.kvo18Preview.policyRevision')}>
          <Text code>{preview.policyRevision}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t('runs.batchIntake.kvo18Preview.total')}>
          <Text>{preview.totalAmount} {preview.currency} · VAT {preview.totalVatAmount}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t('runs.batchIntake.kvo18Preview.technicalState')}>
          <Text>{preview.technicalRealizationPolicy.documentStateAfterOffset}</Text>
        </Descriptions.Item>
        <Descriptions.Item label={t('runs.batchIntake.kvo18Preview.evidence')}>
          <Text>
            {preview.evidenceRequirements.salesBookKvo01Required ? 'KVO 01' : ''}
            {' / '}
            {preview.evidenceRequirements.purchaseBookKvo18Required ? 'KVO 18' : ''}
          </Text>
        </Descriptions.Item>
      </Descriptions>
      <Space size={[8, 8]} wrap>
        {stageOrder.map((slotKey) => {
          const stage = preview.stages[slotKey]
          return (
            <Button
              key={slotKey}
              size="small"
              type={stage.state === 'ready' ? 'primary' : 'default'}
              disabled={stage.state !== 'ready' || stageActionsDisabled}
              onClick={() => onStageSubmit(slotKey)}
              data-testid={`pool-runs-batch-intake-kvo18-stage-${slotKey}`}
            >
              {stage.label}
            </Button>
          )
        })}
      </Space>
      <Tag color="purple" data-testid="pool-runs-batch-intake-kvo18-preview-summary">
        {t('runs.batchIntake.kvo18Preview.summary', {
          rows: preview.rowCount,
          amount: preview.totalAmount,
          vat: preview.totalVatAmount,
        })}
      </Tag>
      {preview.diagnostics.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          data-testid="pool-runs-batch-intake-kvo18-preview-diagnostics"
          message={t('runs.batchIntake.kvo18Preview.diagnosticsTitle')}
          description={preview.diagnostics.map((item) => item.detail).join(' ')}
        />
      ) : (
        <Text type="secondary">{t('runs.batchIntake.kvo18Preview.noDiagnostics')}</Text>
      )}
    </Space>
  )
}
