import { useEffect, useState } from 'react'
import { Alert, Button, Form, Grid, Input, Space, Switch, Typography } from 'antd'

import type {
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  PoolTopologyTemplate,
} from '../../api/intercompanyPools'
import { DrawerFormShell } from '../../components/platform'
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
      const resolved = resolveApiError(error, 'Failed to save topology template.')
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
      title={mode === 'create' ? 'Create reusable topology template' : 'Publish topology template revision'}
      subtitle={mode === 'create'
        ? 'Author the reusable abstract graph here, then materialize a selected revision in /pools/catalog.'
        : 'Publish the next immutable revision for the selected reusable template.'}
      submitText={mode === 'create' ? 'Create template' : 'Publish revision'}
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
        message="Reusable producer surface"
        description={(
          <Text>
            Use this drawer to author reusable topology templates and publish revisions. Use `/pools/catalog`
            {' '}
            only to instantiate a selected revision inside a concrete pool context.
          </Text>
        )}
        style={{ marginBottom: 16 }}
      />
      <Form form={form} layout="vertical">
        {mode === 'create' ? (
          <>
            <Form.Item
              name="code"
              label="Template code"
              rules={[{ required: true, message: 'Template code is required.' }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'code')} />
            </Form.Item>
            <Form.Item
              name="name"
              label="Template name"
              rules={[{ required: true, message: 'Template name is required.' }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'name')} />
            </Form.Item>
            <Form.Item name="description" label="Description">
              <Input data-testid={buildFieldTestId(mode, 'description')} />
            </Form.Item>
            <Form.Item name="metadata_json" label="Template metadata JSON" initialValue="{}">
              <TextArea autoSize={{ minRows: 3, maxRows: 8 }} />
            </Form.Item>
          </>
        ) : null}

        <Form.Item name="revision_metadata_json" label="Revision metadata JSON" initialValue="{}">
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
              <Text strong>Abstract nodes</Text>
              <Button
                onClick={() => {
                  const current = form.getFieldValue('nodes') ?? []
                  form.setFieldValue('nodes', [...current, createBlankTopologyTemplateNodeFormValue()])
                }}
                data-testid={buildFieldTestId(mode, 'add-node')}
              >
                Add node
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
                      <Text strong style={{ display: 'block', marginBottom: 12 }}>{`Node ${index + 1}`}</Text>
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
                          label="Slot key"
                          rules={[{ required: true, message: 'Slot key is required.' }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'node-slot-key', index)} />
                        </Form.Item>
                        <Form.Item name={[field.name, 'label']} label="Label">
                          <Input data-testid={buildFieldTestId(mode, 'node-label', index)} />
                        </Form.Item>
                        <Form.Item name={[field.name, 'is_root']} label="Root" valuePropName="checked">
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
                          Remove
                        </Button>
                      </div>
                      <Form.Item name={[field.name, 'metadata_json']} label="Node metadata JSON" initialValue="{}">
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
              <Text strong>Edges</Text>
              <Button
                onClick={() => {
                  const current = form.getFieldValue('edges') ?? []
                  form.setFieldValue('edges', [...current, createBlankTopologyTemplateEdgeFormValue()])
                }}
                data-testid={buildFieldTestId(mode, 'add-edge')}
              >
                Add edge
              </Button>
            </Space>
            <Form.List name="edges">
              {(fields) => (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {fields.length === 0 ? (
                    <Text type="secondary">
                      Add an edge when the reusable topology needs an explicit abstract relationship.
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
                      <Text strong style={{ display: 'block', marginBottom: 12 }}>{`Edge ${index + 1}`}</Text>
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
                          label="Parent slot key"
                          rules={[{ required: true, message: 'Parent slot key is required.' }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'edge-parent-slot-key', index)} />
                        </Form.Item>
                        <Form.Item
                          name={[field.name, 'child_slot_key']}
                          label="Child slot key"
                          rules={[{ required: true, message: 'Child slot key is required.' }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'edge-child-slot-key', index)} />
                        </Form.Item>
                        <Form.Item
                          name={[field.name, 'weight']}
                          label="Weight"
                          rules={[{ required: true, message: 'Weight is required.' }]}
                        >
                          <Input data-testid={buildFieldTestId(mode, 'edge-weight', index)} />
                        </Form.Item>
                        <Form.Item name={[field.name, 'document_policy_key']} label="Document policy key">
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
                          Remove
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
                        <Form.Item name={[field.name, 'min_amount']} label="Minimum amount">
                          <Input />
                        </Form.Item>
                        <Form.Item name={[field.name, 'max_amount']} label="Maximum amount">
                          <Input />
                        </Form.Item>
                      </div>
                      <Form.Item name={[field.name, 'metadata_json']} label="Edge metadata JSON" initialValue="{}">
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
