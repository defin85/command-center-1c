import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Descriptions, Form, Input, Space, Typography } from 'antd'

import type {
  BindingProfileCreateRequest,
  BindingProfileDetail,
  BindingProfileRevisionCreateRequest,
} from '../../api/poolBindingProfiles'
import { useAuthoringReferences } from '../../api/queries/authoringReferences'
import { EntityDetails, ModalFormShell } from '../../components/platform'
import { WorkflowRevisionSelect } from '../../components/workflow/WorkflowRevisionSelect'
import { resolveApiError } from './masterData/errorUtils'
import { BindingProfileDecisionRefsEditor } from './BindingProfileDecisionRefsEditor'
import {
  buildBindingProfileCreateRequest,
  buildBindingProfileEditorInitialValues,
  buildBindingProfileRevisionCreateRequest,
  type BindingProfileEditorFormValues,
  type BindingProfileEditorMode,
} from './poolBindingProfilesForm'

const { TextArea } = Input
const { Text } = Typography

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
  const [advancedMode, setAdvancedMode] = useState(false)
  const authoringReferencesQuery = useAuthoringReferences({
    enabled: open,
  })
  const availableWorkflows = authoringReferencesQuery.data?.availableWorkflows ?? []
  const availableDecisions = authoringReferencesQuery.data?.availableDecisions ?? []
  const currentWorkflow = Form.useWatch([
    'workflow_revision_id',
  ], form)
  const currentWorkflowSelection = useMemo(() => ({
    workflowDefinitionKey: form.getFieldValue('workflow_definition_key'),
    workflowRevisionId: currentWorkflow,
    workflowRevision: form.getFieldValue('workflow_revision'),
    workflowName: form.getFieldValue('workflow_name'),
  }), [currentWorkflow, form])

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
    setAdvancedMode(false)
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
    <ModalFormShell
      open={open}
      title={mode === 'create' ? 'Create reusable profile' : 'Publish immutable revision'}
      onClose={onCancel}
      onSubmit={() => { void handleSubmit() }}
      submitText={mode === 'create' ? 'Create profile' : 'Publish revision'}
      confirmLoading={submitting}
      submitButtonTestId={buildFieldTestId(mode, 'submit')}
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
      <Alert
        type="info"
        showIcon
        message="Canonical reference catalogs"
        description={(
          <Space wrap size={[8, 8]}>
            <Text>
              Author workflow revisions in `/workflows` and decision revisions in `/decisions`, then pin them here without copying opaque ids manually.
            </Text>
            <Button href="/workflows">Open /workflows</Button>
            <Button href="/decisions">Open /decisions</Button>
          </Space>
        )}
        style={{ marginBottom: 16 }}
      />
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

        <Form.Item
          label="Workflow revision"
          required
          help="Select pinned workflow revision from /workflows. Reusable workflow fields are derived from the selected revision."
        >
          <WorkflowRevisionSelect
            workflows={availableWorkflows}
            currentWorkflow={currentWorkflowSelection}
            loading={authoringReferencesQuery.isLoading}
            disabled={submitting}
            placeholder="Select workflow revision from /workflows"
            testId={`pool-binding-profiles-${mode}-workflow-revision-select`}
            onChange={(workflow) => {
              form.setFieldsValue({
                workflow_definition_key: workflow?.workflowDefinitionKey ?? '',
                workflow_revision_id: workflow?.workflowRevisionId ?? '',
                workflow_revision: workflow?.workflowRevision ?? 1,
                workflow_name: workflow?.name ?? '',
              })
            }}
          />
        </Form.Item>
        <Form.Item name="workflow_definition_key" hidden rules={[{ required: true, message: 'Workflow definition key is required.' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="workflow_revision_id" hidden rules={[{ required: true, message: 'Workflow revision is required.' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="workflow_revision" hidden rules={[{ required: true, message: 'Workflow revision number is required.' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="workflow_name" hidden>
          <Input />
        </Form.Item>

        {currentWorkflowSelection.workflowRevisionId ? (
          <div style={{ marginBottom: 16 }}>
            <EntityDetails title="Pinned workflow lineage">
              <Descriptions
                size="small"
                column={1}
                items={[
                  {
                    key: 'workflow-name',
                    label: 'Workflow',
                    children: currentWorkflowSelection.workflowName || '—',
                  },
                  {
                    key: 'workflow-definition-key',
                    label: 'Definition key',
                    children: currentWorkflowSelection.workflowDefinitionKey || '—',
                  },
                  {
                    key: 'workflow-revision-id',
                    label: 'Revision ID',
                    children: currentWorkflowSelection.workflowRevisionId || '—',
                  },
                  {
                    key: 'workflow-revision',
                    label: 'Revision',
                    children: currentWorkflowSelection.workflowRevision || '—',
                  },
                ]}
              />
            </EntityDetails>
          </div>
        ) : null}

        <Form.Item name="contract_version" label="Contract version">
          <Input placeholder="binding_profile.v1" data-testid={buildFieldTestId(mode, 'contract_version')} />
        </Form.Item>

        <BindingProfileDecisionRefsEditor
          form={form}
          availableDecisions={availableDecisions}
          decisionsLoading={authoringReferencesQuery.isLoading}
          disabled={submitting}
          mode={mode}
        />

        <Space direction="vertical" size={4} style={{ width: '100%', marginTop: 16 }}>
          <Button
            type="link"
            onClick={() => setAdvancedMode((current) => !current)}
            style={{ paddingInline: 0 }}
            data-testid={`pool-binding-profiles-${mode}-advanced-toggle`}
          >
            {advancedMode ? 'Hide advanced JSON fields' : 'Show advanced JSON fields'}
          </Button>
          <Text type="secondary">
            Advanced mode keeps compatibility/debugging access to raw parameters, role mapping and metadata payloads.
          </Text>
        </Space>

        {advancedMode ? (
          <Space direction="vertical" size="middle" style={{ display: 'flex', marginTop: 12 }}>
            <Form.Item name="parameters_json" label="Default parameters JSON">
              <TextArea rows={6} data-testid={buildFieldTestId(mode, 'parameters_json')} />
            </Form.Item>
            <Form.Item name="role_mapping_json" label="Role mapping JSON">
              <TextArea rows={6} data-testid={buildFieldTestId(mode, 'role_mapping_json')} />
            </Form.Item>
            <Form.Item name="metadata_json" label="Revision metadata JSON">
              <TextArea rows={6} data-testid={buildFieldTestId(mode, 'metadata_json')} />
            </Form.Item>
          </Space>
        ) : null}
      </Form>
    </ModalFormShell>
  )
}
