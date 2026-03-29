import { Alert, Form, Select, Space, Typography } from 'antd'
import { useEffect, useMemo } from 'react'

import type { PoolBatch, PoolFactualEdgeBalance, PoolFactualWorkspace } from '../../api/intercompanyPools'
import { ModalFormShell } from '../../components/platform'
import type { PoolFactualReviewRow } from './poolFactualReviewQueue'

const { Text } = Typography

export type PoolFactualReviewAttributeValues = {
  batch_id?: string | null
  edge_id?: string | null
  organization_id?: string | null
}

type PoolFactualReviewRowWithTargets = PoolFactualReviewRow & {
  batchId: string | null
  edgeId: string | null
  organizationId: string | null
}

type PoolFactualReviewAttributeModalProps = {
  open: boolean
  reviewRow: PoolFactualReviewRowWithTargets | null
  workspace: PoolFactualWorkspace | null
  saving: boolean
  onCancel: () => void
  onSubmit: (values: PoolFactualReviewAttributeValues) => Promise<void>
}

type SelectOption = {
  value: string
  label: string
}

const shortId = (value: string | null | undefined) => {
  if (!value) {
    return '-'
  }
  return value.slice(0, 8)
}

const buildBatchLabel = (batch: PoolBatch) => (
  `${batch.source_reference} · ${batch.period_start}${batch.batch_kind ? ` · ${batch.batch_kind}` : ''}`
)

const buildEdgeLabel = (edge: PoolFactualEdgeBalance) => (
  `${edge.organization_name}${edge.edge_id ? ` · ${shortId(edge.edge_id)}` : ''}`
)

export function PoolFactualReviewAttributeModal({
  open,
  reviewRow,
  workspace,
  saving,
  onCancel,
  onSubmit,
}: PoolFactualReviewAttributeModalProps) {
  const [form] = Form.useForm<PoolFactualReviewAttributeValues>()

  useEffect(() => {
    if (!open || !reviewRow) {
      form.resetFields()
      return
    }

    form.setFieldsValue({
      batch_id: reviewRow.batchId ?? undefined,
      edge_id: reviewRow.edgeId ?? undefined,
      organization_id: reviewRow.organizationId ?? undefined,
    })
  }, [form, open, reviewRow])

  const batchOptions = useMemo<SelectOption[]>(() => {
    const seen = new Set<string>()
    return (workspace?.settlements ?? []).flatMap((batch) => {
      if (seen.has(batch.id)) {
        return []
      }
      seen.add(batch.id)
      return [{
        value: batch.id,
        label: buildBatchLabel(batch),
      }]
    })
  }, [workspace])

  const edgeOptions = useMemo<SelectOption[]>(() => {
    const seen = new Set<string>()
    return (workspace?.edge_balances ?? []).flatMap((edge) => {
      if (!edge.edge_id || seen.has(edge.edge_id)) {
        return []
      }
      seen.add(edge.edge_id)
      return [{
        value: edge.edge_id,
        label: buildEdgeLabel(edge),
      }]
    })
  }, [workspace])

  const organizationOptions = useMemo<SelectOption[]>(() => {
    const seen = new Set<string>()
    return (workspace?.edge_balances ?? []).flatMap((edge) => {
      if (seen.has(edge.organization_id)) {
        return []
      }
      seen.add(edge.organization_id)
      return [{
        value: edge.organization_id,
        label: edge.organization_name,
      }]
    })
  }, [workspace])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    await onSubmit({
      batch_id: values.batch_id ?? undefined,
      edge_id: values.edge_id ?? undefined,
      organization_id: values.organization_id ?? undefined,
    })
    form.resetFields()
  }

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={() => { void handleSubmit().catch(() => undefined) }}
      title="Confirm attribution"
      subtitle={reviewRow ? `Review item ${reviewRow.id}` : 'Choose attribution targets before confirming the review item.'}
      submitText="Confirm attribution"
      confirmLoading={saving}
      forceRender
      width={720}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message="Choose or confirm attribution targets"
          description={(
            <Space direction="vertical" size={4}>
              <Text>
                The review action requires at least one explicit target. You can keep the current values or change them
                before submitting.
              </Text>
              {reviewRow ? (
                <Text type="secondary">
                  Current row targets: batch {shortId(reviewRow.batchId)}, edge {shortId(reviewRow.edgeId)}, organization {shortId(reviewRow.organizationId)}.
                </Text>
              ) : null}
            </Space>
          )}
        />

        <Form form={form} layout="vertical">
          <Form.Item
            name="batch_id"
            label="Batch"
            extra="Optional. Select the batch that should own the attribution."
            rules={[
              {
                validator: async (_, value) => {
                  const edgeId = form.getFieldValue('edge_id') as string | undefined | null
                  const organizationId = form.getFieldValue('organization_id') as string | undefined | null
                  if (value || edgeId || organizationId) {
                    return
                  }
                  throw new Error('Select at least one attribution target.')
                },
              },
            ]}
          >
            <Select
              data-testid="pool-factual-attribute-batch-select"
              allowClear
              placeholder="Select batch"
              options={batchOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item
            name="edge_id"
            label="Edge"
            extra="Optional. Select the topology edge that should receive the attribution."
          >
            <Select
              data-testid="pool-factual-attribute-edge-select"
              allowClear
              placeholder="Select edge"
              options={edgeOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item
            name="organization_id"
            label="Organization"
            extra="Optional. Select the organization that should receive the attribution."
          >
            <Select
              data-testid="pool-factual-attribute-organization-select"
              allowClear
              placeholder="Select organization"
              options={organizationOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
