import { useEffect, useState } from 'react'
import { Alert, Button, Form, Grid, Input, Space, Switch, Typography } from 'antd'

import type {
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  PoolTopologyTemplate,
} from '../../api/intercompanyPools'
import { DrawerFormShell } from '../../components/platform'
import { usePoolsTranslation } from '../../i18n'
import { resolveApiError } from './masterData/errorUtils'
import {
  buildCreatePoolTopologyTemplateRequest,
  buildRevisePoolTopologyTemplateRequest,
  buildTopologyTemplateEditorInitialValues,
  createBlankTopologyTemplateEdgeFormValue,
  createBlankTopologyTemplateNodeFormValue,
  type TopologyTemplateEditorFormValues,
  type TopologyTemplateEditorMode,
} from './poolTopologyTemplatesForm'

const { Text } = Typography
const { TextArea } = Input
const { useBreakpoint } = Grid
const DESKTOP_BREAKPOINT_PX = 992

type PoolTopologyTemplatesEditorDrawerProps = {
  open: boolean
  mode: TopologyTemplateEditorMode
  template?: PoolTopologyTemplate | null
  onCancel: () => void
  onSubmit: (
    request: CreatePoolTopologyTemplatePayload | CreatePoolTopologyTemplateRevisionPayload,
  ) => Promise<void>
}

const buildFieldTestId = (
  mode: TopologyTemplateEditorMode,
  field: string,
  index?: number,
) => {
  const suffix = typeof index === 'number' ? `-${index}` : ''
  return `pool-topology-templates-${mode}-${field}${suffix}`
}

export function PoolTopologyTemplatesEditorDrawer({
  open,
  mode,
  template,
  onCancel,
  onSubmit,
}: PoolTopologyTemplatesEditorDrawerProps) {
  const { t } = usePoolsTranslation()
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )
  const [form] = Form.useForm<TopologyTemplateEditorFormValues>()
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    form.setFieldsValue(buildTopologyTemplateEditorInitialValues(template))
    setSubmitError(null)
  }, [form, open, template])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const builtRequest = (
      mode === 'create'
        ? buildCreatePoolTopologyTemplateRequest(values)
        : buildRevisePoolTopologyTemplateRequest(values)
    )

    if (!builtRequest.request) {
      form.setFields(builtRequest.errors)
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      await onSubmit(builtRequest.request)
      onCancel()
      form.resetFields()
    } catch (error) {
      const resolved = resolveApiError(error, t('topologyTemplates.messages.failedToSave'))
      setSubmitError(resolved.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <DrawerFormShell
      open={open}
      onClose={onCancel}
      onSubmit={() => handleSubmit()}
      title={mode === 'create'
        ? t('topologyTemplates.editor.createTitle')
        : t('topologyTemplates.editor.reviseTitle')}
      subtitle={mode === 'create'
        ? t('topologyTemplates.editor.createSubtitle')
        : t('topologyTemplates.editor.reviseSubtitle')}
      submitText={mode === 'create'
        ? t('topologyTemplates.editor.createSubmit')
        : t('topologyTemplates.editor.reviseSubmit')}
      confirmLoading={submitting}
      submitButtonTestId={buildFieldTestId(mode, 'submit')}
      drawerTestId={`pool-topology-templates-${mode}-drawer`}
      width={960}
    >
      {submitError ? (
        <Alert
          type="error"
          showIcon
          message={submitError}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Alert
        type="info"
        showIcon
        message={t('topologyTemplates.editor.infoTitle')}
        description={(
          <Text>
            {t('topologyTemplates.editor.infoDescription')}
          </Text>
        )}
        style={{ marginBottom: 16 }}
      />
      <Form form={form} layout="vertical">
        {mode === 'create' ? (
          <>
            <Form.Item
              name="code"
              label={t('topologyTemplates.editor.templateCode')}
              rules={[{ required: true, message: t('topologyTemplates.editor.validation.templateCodeRequired') }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'code')} />
            </Form.Item>
            <Form.Item
              name="name"
              label={t('topologyTemplates.editor.templateName')}
              rules={[{ required: true, message: t('topologyTemplates.editor.validation.templateNameRequired') }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'name')} />
            </Form.Item>
            <Form.Item name="description" label={t('common.description')}>
              <Input data-testid={buildFieldTestId(mode, 'description')} />
            </Form.Item>
            <Form.Item name="metadata_json" label={t('topologyTemplates.editor.templateMetadataJson')} initialValue="{}">
              <TextArea autoSize={{ minRows: 3, maxRows: 8 }} />
            </Form.Item>
          </>
        ) : null}

        <Form.Item name="revision_metadata_json" label={t('topologyTemplates.editor.revisionMetadataJson')} initialValue="{}">
          <TextArea autoSize={{ minRows: 3, maxRows: 8 }} />
        </Form.Item>

        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div
            style={{
              border: '1px solid #f0f0f0',
              borderRadius: 8,
              padding: 16,
            }}
          >
            <Space align="center" style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
              <Text strong>{t('topologyTemplates.editor.abstractNodes')}</Text>
              <Button
                onClick={() => {
                  const current = form.getFieldValue('nodes') ?? []
                  form.setFieldValue('nodes', [...current, createBlankTopologyTemplateNodeFormValue()])
                }}
                data-testid={buildFieldTestId(mode, 'add-node')}
              >
                {t('topologyTemplates.editor.addNode')}
              </Button>
            </Space>
            <Form.List name="nodes">
              {(fields) => (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {fields.map((field, index) => (
                    <div
                      key={field.key}
                      style={{
                        border: '1px solid #f0f0f0',
                        borderRadius: 8,
                        padding: 16,
                      }}
                    >
                      <Text strong style={{ display: 'block', marginBottom: 12 }}>
                        {t('topologyTemplates.editor.nodeLabel', { value: index + 1 })}
                      </Text>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: isNarrow
                            ? 'minmax(0, 1fr)'
                            : 'minmax(0, 1fr) minmax(0, 1fr) auto auto',
                          gap: 12,
                          alignItems: 'end',
                        }}
                      >
                        <Form.Item
                          name={[field.name, 'slot_key']}
                          label={t('topologyTemplates.editor.slotKey')}
                          rules={[{ required: true, message: t('topologyTemplates.editor.validation.slotKeyRequired') }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'node-slot-key', index)} />
                        </Form.Item>
                        <Form.Item name={[field.name, 'label']} label={t('topologyTemplates.editor.label')}>
                          <Input data-testid={buildFieldTestId(mode, 'node-label', index)} />
                        </Form.Item>
                        <Form.Item name={[field.name, 'is_root']} label={t('topologyTemplates.editor.root')} valuePropName="checked">
                          <Switch data-testid={buildFieldTestId(mode, 'node-root', index)} />
                        </Form.Item>
                        <Button
                          danger
                          onClick={() => {
                            const nextNodes = [...(form.getFieldValue('nodes') ?? [])]
                            nextNodes.splice(index, 1)
                            form.setFieldValue('nodes', nextNodes)
                          }}
                        >
                          {t('common.remove')}
                        </Button>
                      </div>
                      <Form.Item name={[field.name, 'metadata_json']} label={t('topologyTemplates.editor.nodeMetadataJson')} initialValue="{}">
                        <TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                      </Form.Item>
                    </div>
                  ))}
                </Space>
              )}
            </Form.List>
          </div>

          <div
            style={{
              border: '1px solid #f0f0f0',
              borderRadius: 8,
              padding: 16,
            }}
          >
            <Space align="center" style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
              <Text strong>{t('topologyTemplates.editor.edges')}</Text>
              <Button
                onClick={() => {
                  const current = form.getFieldValue('edges') ?? []
                  form.setFieldValue('edges', [...current, createBlankTopologyTemplateEdgeFormValue()])
                }}
                data-testid={buildFieldTestId(mode, 'add-edge')}
              >
                {t('topologyTemplates.editor.addEdge')}
              </Button>
            </Space>
            <Form.List name="edges">
              {(fields) => (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {fields.length === 0 ? (
                    <Text type="secondary">
                      {t('topologyTemplates.editor.noEdges')}
                    </Text>
                  ) : null}
                  {fields.map((field, index) => (
                    <div
                      key={field.key}
                      style={{
                        border: '1px solid #f0f0f0',
                        borderRadius: 8,
                        padding: 16,
                      }}
                    >
                      <Text strong style={{ display: 'block', marginBottom: 12 }}>
                        {t('topologyTemplates.editor.edgeLabel', { value: index + 1 })}
                      </Text>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: isNarrow
                            ? 'minmax(0, 1fr)'
                            : 'minmax(0, 1fr) minmax(0, 1fr) 120px minmax(0, 1fr) auto',
                          gap: 12,
                          alignItems: 'end',
                        }}
                      >
                        <Form.Item
                          name={[field.name, 'parent_slot_key']}
                          label={t('topologyTemplates.editor.parentSlotKey')}
                          rules={[{ required: true, message: t('topologyTemplates.editor.validation.parentSlotKeyRequired') }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'edge-parent-slot-key', index)} />
                        </Form.Item>
                        <Form.Item
                          name={[field.name, 'child_slot_key']}
                          label={t('topologyTemplates.editor.childSlotKey')}
                          rules={[{ required: true, message: t('topologyTemplates.editor.validation.childSlotKeyRequired') }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'edge-child-slot-key', index)} />
                        </Form.Item>
                        <Form.Item
                          name={[field.name, 'weight']}
                          label={t('topologyTemplates.editor.weight')}
                          rules={[{ required: true, message: t('topologyTemplates.editor.validation.weightRequired') }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'edge-weight', index)} />
                        </Form.Item>
                        <Form.Item name={[field.name, 'document_policy_key']} label={t('topologyTemplates.editor.documentPolicyKey')}>
                          <Input data-testid={buildFieldTestId(mode, 'edge-document-policy-key', index)} />
                        </Form.Item>
                        <Button
                          danger
                          onClick={() => {
                            const nextEdges = [...(form.getFieldValue('edges') ?? [])]
                            nextEdges.splice(index, 1)
                            form.setFieldValue('edges', nextEdges)
                          }}
                        >
                          {t('common.remove')}
                        </Button>
                      </div>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: isNarrow
                            ? 'minmax(0, 1fr)'
                            : 'minmax(0, 1fr) minmax(0, 1fr)',
                          gap: 12,
                        }}
                      >
                        <Form.Item name={[field.name, 'min_amount']} label={t('topologyTemplates.editor.minimumAmount')}>
                          <Input />
                        </Form.Item>
                        <Form.Item name={[field.name, 'max_amount']} label={t('topologyTemplates.editor.maximumAmount')}>
                          <Input />
                        </Form.Item>
                      </div>
                      <Form.Item name={[field.name, 'metadata_json']} label={t('topologyTemplates.editor.edgeMetadataJson')} initialValue="{}">
                        <TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                      </Form.Item>
                    </div>
                  ))}
                </Space>
              )}
            </Form.List>
          </div>
        </Space>
      </Form>
    </DrawerFormShell>
  )
}
