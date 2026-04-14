import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Form, Input, Space, Typography } from 'antd'

import type {
  BindingProfileCreateRequest,
  BindingProfileDetail,
  BindingProfileRevisionCreateRequest,
} from '../../api/poolBindingProfiles'
import { useAuthoringReferences } from '../../api/queries/authoringReferences'
import { EntityDetails, ModalFormShell, RouteButton } from '../../components/platform'
import { WorkflowRevisionSelect } from '../../components/workflow/WorkflowRevisionSelect'
import { usePoolsTranslation } from '../../i18n'
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
  const { t } = usePoolsTranslation()
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
  const workflowLineageItems = useMemo(() => ([
    {
      key: 'workflow-name',
      label: t('executionPacks.editor.workflowLabel'),
      value: currentWorkflowSelection.workflowName || t('common.noValue'),
    },
    {
      key: 'workflow-definition-key',
      label: t('executionPacks.editor.definitionKey'),
      value: currentWorkflowSelection.workflowDefinitionKey || t('common.noValue'),
    },
    {
      key: 'workflow-revision-id',
      label: t('executionPacks.editor.revisionId'),
      value: currentWorkflowSelection.workflowRevisionId || t('common.noValue'),
    },
    {
      key: 'workflow-revision',
      label: t('executionPacks.editor.revisionLabel'),
      value: currentWorkflowSelection.workflowRevision || t('common.noValue'),
    },
  ]), [currentWorkflowSelection, t])

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
      const resolved = resolveApiError(error, t('executionPacks.messages.failedToSave'))
      setSubmitError(resolved.message)
      form.setFields(toFormFieldErrors(resolved.fieldErrors))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <ModalFormShell
      open={open}
      title={mode === 'create'
        ? t('executionPacks.editor.createTitle')
        : t('executionPacks.editor.reviseTitle')}
      onClose={onCancel}
      onSubmit={() => { void handleSubmit() }}
      submitText={mode === 'create'
        ? t('executionPacks.editor.createSubmit')
        : t('executionPacks.editor.reviseSubmit')}
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
        message={t('executionPacks.editor.referencesTitle')}
        description={(
          <Space wrap size={[8, 8]}>
            <Text>
              {t('executionPacks.editor.referencesDescription')}
            </Text>
            <RouteButton to="/workflows">{t('common.openWorkflows')}</RouteButton>
            <RouteButton to="/decisions">{t('common.openDecisions')}</RouteButton>
          </Space>
        )}
        style={{ marginBottom: 16 }}
      />
      <Form form={form} layout="vertical">
        {mode === 'create' ? (
          <>
            <Form.Item
              name="code"
              label={t('executionPacks.editor.code')}
              rules={[{ required: true, message: t('executionPacks.editor.validation.codeRequired') }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'code')} />
            </Form.Item>
            <Form.Item
              name="name"
              label={t('executionPacks.editor.name')}
              rules={[{ required: true, message: t('executionPacks.editor.validation.nameRequired') }]}
            >
              <Input data-testid={buildFieldTestId(mode, 'name')} />
            </Form.Item>
            <Form.Item name="description" label={t('common.description')}>
              <Input data-testid={buildFieldTestId(mode, 'description')} />
            </Form.Item>
          </>
        ) : null}

        <Form.Item
          label={t('executionPacks.editor.workflowRevision')}
          required
          help={t('executionPacks.editor.workflowRevisionHelp')}
        >
          <WorkflowRevisionSelect
            workflows={availableWorkflows}
            currentWorkflow={currentWorkflowSelection}
            loading={authoringReferencesQuery.isLoading}
            disabled={submitting}
            placeholder={t('executionPacks.editor.workflowRevisionPlaceholder')}
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
        <Form.Item name="workflow_definition_key" hidden rules={[{ required: true, message: t('executionPacks.editor.validation.workflowDefinitionKeyRequired') }]}>
          <Input />
        </Form.Item>
        <Form.Item name="workflow_revision_id" hidden rules={[{ required: true, message: t('executionPacks.editor.validation.workflowRevisionRequired') }]}>
          <Input />
        </Form.Item>
        <Form.Item name="workflow_revision" hidden rules={[{ required: true, message: t('executionPacks.editor.validation.workflowRevisionNumberRequired') }]}>
          <Input />
        </Form.Item>
        <Form.Item name="workflow_name" hidden>
          <Input />
        </Form.Item>

        {currentWorkflowSelection.workflowRevisionId ? (
          <div style={{ marginBottom: 16 }}>
            <EntityDetails title={t('executionPacks.editor.pinnedWorkflowLineage')}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {workflowLineageItems.map((item) => (
                  <div
                    key={item.key}
                    data-testid={`pool-binding-profiles-${mode}-workflow-lineage-${item.key}`}
                    style={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                  >
                    <Text type="secondary">{item.label}</Text>
                    <Text>{item.value}</Text>
                  </div>
                ))}
              </div>
            </EntityDetails>
          </div>
        ) : null}

        <Form.Item name="contract_version" label={t('executionPacks.editor.contractVersion')}>
          <Input placeholder={t('executionPacks.editor.contractVersionPlaceholder')} data-testid={buildFieldTestId(mode, 'contract_version')} />
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
            {advancedMode
              ? t('executionPacks.editor.advancedToggleHide')
              : t('executionPacks.editor.advancedToggleShow')}
          </Button>
          <Text type="secondary">
            {t('executionPacks.editor.advancedHint')}
          </Text>
        </Space>

        {advancedMode ? (
          <Space direction="vertical" size="middle" style={{ display: 'flex', marginTop: 12 }}>
            <Form.Item name="parameters_json" label={t('executionPacks.editor.defaultParametersJson')}>
              <TextArea rows={6} data-testid={buildFieldTestId(mode, 'parameters_json')} />
            </Form.Item>
            <Form.Item name="role_mapping_json" label={t('executionPacks.editor.roleMappingJson')}>
              <TextArea rows={6} data-testid={buildFieldTestId(mode, 'role_mapping_json')} />
            </Form.Item>
            <Form.Item name="metadata_json" label={t('executionPacks.editor.revisionMetadataJson')}>
              <TextArea rows={6} data-testid={buildFieldTestId(mode, 'metadata_json')} />
            </Form.Item>
          </Space>
        ) : null}
      </Form>
    </ModalFormShell>
  )
}
