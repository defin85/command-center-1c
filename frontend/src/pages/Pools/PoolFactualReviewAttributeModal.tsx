import { Alert, Form, Select, Space, Typography } from 'antd'
import { useEffect, useMemo } from 'react'

import type { PoolFactualWorkspace } from '../../api/intercompanyPools'
import { ModalFormShell } from '../../components/platform'
import { usePoolFactualTranslation } from '../../i18n'
import { useLocaleFormatters } from '../../i18n/formatters'
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

export function PoolFactualReviewAttributeModal({
  open,
  reviewRow,
  workspace,
  saving,
  onCancel,
  onSubmit,
}: PoolFactualReviewAttributeModalProps) {
  const { t } = usePoolFactualTranslation()
  const formatters = useLocaleFormatters()
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
        label: [
          batch.source_reference,
          formatters.date(batch.period_start),
          batch.batch_kind || null,
        ].filter(Boolean).join(' · '),
      }]
    })
  }, [formatters, workspace])

  const edgeOptions = useMemo<SelectOption[]>(() => {
    const seen = new Set<string>()
    return (workspace?.edge_balances ?? []).flatMap((edge) => {
      if (!edge.edge_id || seen.has(edge.edge_id)) {
        return []
      }
      seen.add(edge.edge_id)
      return [{
        value: edge.edge_id,
        label: `${edge.organization_name}${edge.edge_id ? ` · ${shortId(edge.edge_id)}` : ''}`,
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
      title={t('modal.title')}
      subtitle={reviewRow ? t('modal.subtitle', { id: reviewRow.id }) : t('modal.emptySubtitle')}
      submitText={t('modal.submit')}
      confirmLoading={saving}
      forceRender
      width={720}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message={t('modal.infoTitle')}
          description={(
            <Space direction="vertical" size={4}>
              <Text>{t('modal.infoDescription')}</Text>
              {reviewRow ? (
                <Text type="secondary">
                  {t('modal.currentTargets', {
                    batch: shortId(reviewRow.batchId),
                    edge: shortId(reviewRow.edgeId),
                    organization: shortId(reviewRow.organizationId),
                  })}
                </Text>
              ) : null}
            </Space>
          )}
        />

        <Form form={form} layout="vertical">
          <Form.Item
            name="batch_id"
            label={t('modal.fields.batch.label')}
            extra={t('modal.fields.batch.extra')}
            rules={[
              {
                validator: async (_, value) => {
                  const edgeId = form.getFieldValue('edge_id') as string | undefined | null
                  const organizationId = form.getFieldValue('organization_id') as string | undefined | null
                  if (value || edgeId || organizationId) {
                    return
                  }
                  throw new Error(t('modal.validation.targetRequired'))
                },
              },
            ]}
          >
            <Select
              data-testid="pool-factual-attribute-batch-select"
              allowClear
              placeholder={t('modal.fields.batch.placeholder')}
              options={batchOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item
            name="edge_id"
            label={t('modal.fields.edge.label')}
            extra={t('modal.fields.edge.extra')}
          >
            <Select
              data-testid="pool-factual-attribute-edge-select"
              allowClear
              placeholder={t('modal.fields.edge.placeholder')}
              options={edgeOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item
            name="organization_id"
            label={t('modal.fields.organization.label')}
            extra={t('modal.fields.organization.extra')}
          >
            <Select
              data-testid="pool-factual-attribute-organization-select"
              allowClear
              placeholder={t('modal.fields.organization.placeholder')}
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
