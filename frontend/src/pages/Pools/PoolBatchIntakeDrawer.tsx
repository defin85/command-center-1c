import { useEffect, useState } from 'react'
import { Alert, App as AntApp, Button, Form, Input, Radio, Select, Space, Typography, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'

import {
  createPoolBatch,
  type PoolBatchCreatePayload,
  type PoolBatchCreateResponse,
  type PoolBatchKind,
  type PoolSchemaTemplate,
} from '../../api/intercompanyPools'
import { DrawerFormShell } from '../../components/platform/DrawerFormShell'
import { resolveApiError } from './masterData/errorUtils'


const { Text } = Typography
const { TextArea } = Input

type SelectOption = {
  value: string
  label: string
}

type BatchIntakeFormValues = {
  batch_kind: PoolBatchKind
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

type PoolBatchIntakeDrawerProps = {
  open: boolean
  poolId: string | null
  poolLabel: string
  schemaTemplates: PoolSchemaTemplate[]
  loadingSchemaTemplates: boolean
  workflowBindingOptions: SelectOption[]
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

function parseBatchPayloadJson(raw: string): Record<string, unknown> | Array<Record<string, unknown>> {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('source_payload: invalid JSON')
  }
  if (!parsed || (typeof parsed !== 'object' && !Array.isArray(parsed))) {
    throw new Error('source_payload: object or array expected')
  }
  if (!Array.isArray(parsed)) {
    return parsed as Record<string, unknown>
  }
  return parsed.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new Error('source_payload: array items must be objects')
    }
    return item as Record<string, unknown>
  })
}

async function readFileAsBase64(file: File): Promise<string> {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Failed to read ${file.name}`))
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      const base64 = result.includes(',') ? result.split(',')[1] : result
      resolve(base64)
    }
    reader.readAsDataURL(file)
  })
}

function requireTrimmedValue(value: string | undefined, fieldName: string): string {
  const normalized = value?.trim() || ''
  if (!normalized) {
    throw new Error(`${fieldName} required`)
  }
  return normalized
}

function buildPoolBatchCreatePayload(values: BatchIntakeFormValues, poolId: string): PoolBatchCreatePayload {
  const payloadBase = {
    pool_id: poolId,
    source_type: 'schema_template_upload' as const,
    schema_template_id: requireTrimmedValue(values.schema_template_id, 'schema_template_id'),
    period_start: values.period_start,
    period_end: values.period_end?.trim() || null,
    source_reference: values.source_reference?.trim() || '',
    raw_payload_ref: values.raw_payload_ref?.trim() || '',
  }
  const xlsxBase64 = values.xlsx_base64?.trim() || ''

  if (values.batch_kind === 'receipt') {
    const receiptScope = {
      pool_workflow_binding_id: requireTrimmedValue(values.pool_workflow_binding_id, 'pool_workflow_binding_id'),
      start_organization_id: requireTrimmedValue(values.start_organization_id, 'start_organization_id'),
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
      throw new Error('source_payload required')
    }
    return {
      ...payloadBase,
      ...receiptScope,
      batch_kind: 'receipt',
      json_payload: parseBatchPayloadJson(rawPayloadJson),
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
    throw new Error('source_payload required')
  }
  return {
    ...payloadBase,
    batch_kind: 'sale',
    json_payload: parseBatchPayloadJson(rawPayloadJson),
  }
}

export function PoolBatchIntakeDrawer({
  open,
  poolId,
  poolLabel,
  schemaTemplates,
  loadingSchemaTemplates,
  workflowBindingOptions,
  startOrganizationOptions,
  initialValues,
  onClose,
  onCreated,
}: PoolBatchIntakeDrawerProps) {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<BatchIntakeFormValues>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const batchKind = Form.useWatch('batch_kind', form) ?? initialValues.batchKind
  const uploadedFileName = Form.useWatch('uploaded_file_name', form)

  useEffect(() => {
    if (!open) {
      return
    }
    form.setFieldsValue({
      batch_kind: initialValues.batchKind,
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

  const handleUploadFile = async (file: File) => {
    if (file.name.toLowerCase().endsWith('.json')) {
      const payloadText = await file.text()
      form.setFieldsValue({
        source_payload_json: payloadText,
        xlsx_base64: undefined,
        uploaded_file_name: file.name,
        raw_payload_ref: form.getFieldValue('raw_payload_ref') || file.name,
      })
      message.success(`Loaded JSON payload from ${file.name}`)
      return false
    }

    const xlsxBase64 = await readFileAsBase64(file)
    form.setFieldsValue({
      xlsx_base64: xlsxBase64,
      source_payload_json: '',
      uploaded_file_name: file.name,
      raw_payload_ref: form.getFieldValue('raw_payload_ref') || file.name,
    })
    message.success(`Loaded binary payload from ${file.name}`)
    return false
  }

  const handleSubmit = async () => {
    if (!poolId) {
      setSubmitError('Select a pool before creating a canonical batch.')
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
      const payload = buildPoolBatchCreatePayload(values, poolId)
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
          ? 'Receipt batch accepted and linked run opened'
          : 'Sale batch accepted and closing workflow queued',
      )
    } catch (error) {
      const resolved = resolveApiError(error, 'Failed to create canonical pool batch.')
      setSubmitError(resolved.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <DrawerFormShell
      open={open}
      onClose={onClose}
      title="Create canonical pool batch"
      subtitle={`Pool context: ${poolLabel}`}
      drawerTestId="pool-runs-batch-intake-drawer"
      width={880}
      extra={(
        <Button
          type="primary"
          loading={submitting}
          onClick={() => { void handleSubmit() }}
          data-testid="pool-runs-batch-intake-submit"
        >
          Create batch
        </Button>
      )}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {submitError ? (
          <Alert
            type="error"
            showIcon
            message="Batch intake failed"
            description={submitError}
          />
        ) : null}
        <Alert
          type="info"
          showIcon
          message="Fail-closed canonical intake"
          description="This drawer creates canonical receipt/sale batches through the shipped schema-template path only. Unsupported source classes are rejected on the public boundary."
        />
        <Form form={form} layout="vertical">
          <Form.Item name="batch_kind" label="Batch kind" rules={[{ required: true }]}>
            <Radio.Group data-testid="pool-runs-batch-intake-kind" optionType="button" buttonStyle="solid">
              <Radio.Button value="receipt">receipt</Radio.Button>
              <Radio.Button value="sale">sale</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Space size={12} wrap style={{ width: '100%' }}>
            <Form.Item
              name="period_start"
              label="Period start"
              rules={[{ required: true, message: 'period_start required' }]}
              style={{ minWidth: 180 }}
            >
              <Input type="date" />
            </Form.Item>
            <Form.Item name="period_end" label="Period end" style={{ minWidth: 180 }}>
              <Input type="date" />
            </Form.Item>
          </Space>
          <Form.Item
            name="schema_template_id"
            label="Schema template"
            rules={[{ required: true, message: 'schema_template_id required' }]}
          >
            <Select
              data-testid="pool-runs-batch-intake-schema-template"
              loading={loadingSchemaTemplates}
              options={schemaTemplates.map((item) => ({
                value: item.id,
                label: `${item.code} - ${item.name}`,
              }))}
              placeholder="Select schema template"
            />
          </Form.Item>
          {batchKind === 'receipt' ? (
            <Space direction="vertical" size={0} style={{ width: '100%' }}>
              <Form.Item
                name="pool_workflow_binding_id"
                label="Workflow binding"
                rules={[{ required: true, message: 'pool_workflow_binding_id required' }]}
              >
                <Select
                  data-testid="pool-runs-batch-intake-binding"
                  options={workflowBindingOptions}
                  placeholder="Select workflow binding"
                />
              </Form.Item>
              <Form.Item
                name="start_organization_id"
                label="Start organization"
                rules={[{ required: true, message: 'start_organization_id required' }]}
              >
                <Select
                  data-testid="pool-runs-batch-intake-start-organization"
                  options={startOrganizationOptions}
                  placeholder="Select start organization"
                />
              </Form.Item>
            </Space>
          ) : null}
          <Form.Item name="source_reference" label="Source reference">
            <Input data-testid="pool-runs-batch-intake-source-reference" placeholder="receipt-q1 / sale-q1 / partner registry id" />
          </Form.Item>
          <Form.Item name="raw_payload_ref" label="Raw payload reference">
            <Input placeholder="files/receipt-q1.json" />
          </Form.Item>
          <Form.Item
            name="source_payload_json"
            label="Source payload JSON"
            extra="Leave JSON empty if you upload XLSX/CSV-compatible binary payload instead."
          >
            <TextArea
              data-testid="pool-runs-batch-intake-source-payload"
              autoSize={{ minRows: 6, maxRows: 14 }}
            />
          </Form.Item>
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
              <Button icon={<UploadOutlined />}>Load payload file</Button>
            </Upload>
            {uploadedFileName ? <Text type="secondary">Loaded file: {uploadedFileName}</Text> : null}
          </Space>
        </Form>
      </Space>
    </DrawerFormShell>
  )
}
