import { useEffect, useState } from 'react'
import { Alert, Form, Input, Modal } from 'antd'

import type {
  BindingProfileCreateRequest,
  BindingProfileDetail,
  BindingProfileRevisionCreateRequest,
} from '../../api/poolBindingProfiles'
import { resolveApiError } from './masterData/errorUtils'
import {
  buildBindingProfileCreateRequest,
  buildBindingProfileEditorInitialValues,
  buildBindingProfileRevisionCreateRequest,
  type BindingProfileEditorFormValues,
  type BindingProfileEditorMode,
} from './poolBindingProfilesForm'

const { TextArea } = Input

type BindingProfileFormFieldError = {
  name: keyof BindingProfileEditorFormValues
  errors: string[]
}

type PoolBindingProfilesEditorModalProps = {
  open: boolean
  mode: BindingProfileEditorMode
  profile?: BindingProfileDetail | null
  onCancel: () => void
  onSubmit: (
    request: BindingProfileCreateRequest | BindingProfileRevisionCreateRequest,
  ) => Promise<void>
}

const buildFieldTestId = (
  mode: BindingProfileEditorMode,
  field: keyof BindingProfileEditorFormValues | 'submit',
) => {
  const alias = (
    field === 'workflow_definition_key'
      ? 'workflow_key'
      : field
  )
  return `pool-binding-profiles-${mode}-${alias.replace(/_/g, '-')}`
}

const toFormFieldErrors = (fieldErrors: Record<string, string[]>) => (
  Object.entries(fieldErrors)
    .map(([name, errors]) => {
      if (!errors.length) return null
      return {
        name: name as keyof BindingProfileEditorFormValues,
        errors,
      }
    })
    .filter(Boolean) as BindingProfileFormFieldError[]
)

export function PoolBindingProfilesEditorModal({
  open,
  mode,
  profile,
  onCancel,
  onSubmit,
}: PoolBindingProfilesEditorModalProps) {
  const [form] = Form.useForm<BindingProfileEditorFormValues>()
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return

    form.setFieldsValue(
      buildBindingProfileEditorInitialValues(
        profile?.latest_revision,
        profile
          ? {
            code: profile.code,
            name: profile.name,
            description: profile.description ?? '',
          }
          : undefined,
      ),
    )
    setSubmitError(null)
  }, [form, open, profile])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const builtRequest = (
      mode === 'create'
        ? buildBindingProfileCreateRequest(values)
        : buildBindingProfileRevisionCreateRequest(values)
    )

    if (!builtRequest.request) {
      form.setFields(builtRequest.errors.map((item): BindingProfileFormFieldError => ({
        name: item.field,
        errors: [item.message],
      })))
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      await onSubmit(builtRequest.request)
      onCancel()
      form.resetFields()
    } catch (error) {
      const resolved = resolveApiError(error, 'Failed to save binding profile.')
      setSubmitError(resolved.message)
      form.setFields(toFormFieldErrors(resolved.fieldErrors))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      title={mode === 'create' ? 'Create reusable profile' : 'Publish immutable revision'}
      onCancel={onCancel}
      onOk={() => { void handleSubmit() }}
      okText={mode === 'create' ? 'Create profile' : 'Publish revision'}
      confirmLoading={submitting}
      destroyOnHidden
      okButtonProps={{ 'data-testid': buildFieldTestId(mode, 'submit') } as Record<string, string>}
      width={880}
    >
      {submitError ? (
        <Alert
          type="error"
          showIcon
          message={submitError}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Form form={form} layout="vertical">
        {mode === 'create' ? (
          <>
            <Form.Item
              name="code"
              label="Profile code"
              rules={[{ required: true, message: 'Profile code is required.' }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'code')} />
            </Form.Item>
            <Form.Item
              name="name"
              label="Profile name"
              rules={[{ required: true, message: 'Profile name is required.' }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'name')} />
            </Form.Item>
            <Form.Item name="description" label="Description">
              <Input data-testid={buildFieldTestId(mode, 'description')} />
            </Form.Item>
          </>
        ) : null}

        <Form.Item name="workflow_definition_key" label="Workflow definition key" rules={[{ required: true }]}>
          <Input data-testid={buildFieldTestId(mode, 'workflow_definition_key')} />
        </Form.Item>
        <Form.Item name="workflow_revision_id" label="Workflow revision ID" rules={[{ required: true }]}>
          <Input data-testid={buildFieldTestId(mode, 'workflow_revision_id')} />
        </Form.Item>
        <Form.Item name="workflow_revision" label="Workflow revision" rules={[{ required: true }]}>
          <Input type="number" min={1} data-testid={buildFieldTestId(mode, 'workflow_revision')} />
        </Form.Item>
        <Form.Item name="workflow_name" label="Workflow name" rules={[{ required: true }]}>
          <Input data-testid={buildFieldTestId(mode, 'workflow_name')} />
        </Form.Item>
        <Form.Item name="contract_version" label="Contract version">
          <Input placeholder="binding_profile.v1" data-testid={buildFieldTestId(mode, 'contract_version')} />
        </Form.Item>
        <Form.Item name="decisions_json" label="Decision refs JSON">
          <TextArea rows={6} data-testid={buildFieldTestId(mode, 'decisions_json')} />
        </Form.Item>
        <Form.Item name="parameters_json" label="Default parameters JSON">
          <TextArea rows={6} data-testid={buildFieldTestId(mode, 'parameters_json')} />
        </Form.Item>
        <Form.Item name="role_mapping_json" label="Role mapping JSON">
          <TextArea rows={6} data-testid={buildFieldTestId(mode, 'role_mapping_json')} />
        </Form.Item>
        <Form.Item name="metadata_json" label="Revision metadata JSON">
          <TextArea rows={6} data-testid={buildFieldTestId(mode, 'metadata_json')} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
