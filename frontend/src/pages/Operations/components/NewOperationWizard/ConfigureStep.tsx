/**
 * ConfigureStep - Step 3 of NewOperationWizard
 * Dynamic configuration form based on operation type.
 * Supports both built-in operation forms and DynamicForm for custom templates.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Typography,
  Form,
  Input,
  Select,
  DatePicker,
  InputNumber,
  Switch,
  Checkbox,
  Card,
  Alert,
  Space,
  Spin,
} from 'antd'
import {
  SettingOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { ConfigureStepProps, OperationType, OperationConfig, DynamicFormValidationError } from './types'
import { OPERATION_TYPES } from './types'
import type { ValidationError } from '../../../../components/DynamicForm/types'
import { formatFileSize } from '../../../../utils/formatters'
import { DynamicForm } from '../../../../components/DynamicForm'
import { useTemplateSchema } from '../../../../hooks/useTemplateSchema'
import { useArtifacts, useArtifactVersions, useArtifactAliases } from '../../../../api/queries'
import type { Artifact } from '../../../../api/artifacts'

const { Title, Text } = Typography
const { TextArea } = Input

/**
 * Configuration for operation types that don't require additional settings
 */
const NO_CONFIG_OPERATIONS: OperationType[] = [
  'lock_scheduled_jobs',
  'unlock_scheduled_jobs',
  'unblock_sessions',
  'sync_cluster',
  'health_check',
]

/**
 * Form for block_sessions operation
 */
const BlockSessionsForm = ({
  config,
  onChange,
}: {
  config: OperationConfig
  onChange: (updates: Partial<OperationConfig>) => void
}) => {
  const deniedFromValue = config.denied_from ? dayjs(config.denied_from as string) : null
  const deniedToValue = config.denied_to ? dayjs(config.denied_to as string) : null

  const handleDateChange = (field: 'denied_from' | 'denied_to') => (value: Dayjs | null) => {
    const updates: Partial<OperationConfig> = {}
    updates[field] = value ? value.toISOString() : undefined
    onChange(updates)
  }

  return (
    <Form layout="vertical">
      <Form.Item
        label="Block start (optional)"
        help="Start time for blocking new sessions"
        htmlFor="wizard-block-start"
      >
        <DatePicker
          id="wizard-block-start"
          showTime={{ format: 'HH:mm' }}
          allowClear
          style={{ width: '100%' }}
          format="DD.MM.YYYY HH:mm"
          value={deniedFromValue}
          onChange={handleDateChange('denied_from')}
        />
      </Form.Item>

      <Form.Item
        label="Block end (optional)"
        help="End time for blocking new sessions"
        htmlFor="wizard-block-end"
      >
        <DatePicker
          id="wizard-block-end"
          showTime={{ format: 'HH:mm' }}
          allowClear
          style={{ width: '100%' }}
          format="DD.MM.YYYY HH:mm"
          value={deniedToValue}
          onChange={handleDateChange('denied_to')}
        />
      </Form.Item>

      <Form.Item
        label="Message for users"
        required
        help="This message will be shown to users trying to connect"
        htmlFor="wizard-block-message"
      >
        <TextArea
          id="wizard-block-message"
          rows={3}
          placeholder="Technical maintenance. Please wait..."
          value={config.message || ''}
          onChange={(e) => onChange({ message: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label="Permission code (optional)"
        help="Users with this code can still connect"
        htmlFor="wizard-block-permission-code"
      >
        <Input
          id="wizard-block-permission-code"
          placeholder="Enter permission code"
          value={config.permission_code || ''}
          onChange={(e) => onChange({ permission_code: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label="Block parameter (optional)"
        help="Additional block parameter for 1C"
        htmlFor="wizard-block-parameter"
      >
        <Input
          id="wizard-block-parameter"
          placeholder="Enter block parameter"
          value={config.parameter || ''}
          onChange={(e) => onChange({ parameter: e.target.value })}
        />
      </Form.Item>
    </Form>
  )
}

/**
 * Form for terminate_sessions operation
 */
const TerminateSessionsForm = ({
  config,
  onChange,
}: {
  config: OperationConfig
  onChange: (updates: Partial<OperationConfig>) => void
}) => (
  <Form layout="vertical">
    <Form.Item
      label="Filter by application (optional)"
      help="Only terminate sessions from this application (e.g., '1C:Enterprise', 'Designer')"
      htmlFor="wizard-terminate-filter-app"
    >
      <Input
        id="wizard-terminate-filter-app"
        placeholder="Application name filter"
        value={config.filter_by_app || ''}
        onChange={(e) => onChange({ filter_by_app: e.target.value })}
      />
    </Form.Item>

    <Form.Item>
      <Checkbox
        id="wizard-terminate-exclude-admin"
        checked={config.exclude_admin || false}
        onChange={(e) => onChange({ exclude_admin: e.target.checked })}
      >
        Exclude administrator sessions
      </Checkbox>
    </Form.Item>
  </Form>
)

/**
 * Form for install_extension operation
 */
const InstallExtensionForm = ({
  config,
  onChange,
}: {
  config: OperationConfig
  onChange: (updates: Partial<OperationConfig>) => void
}) => {
  const [searchValue, setSearchValue] = useState('')
  const artifactsQuery = useArtifacts({
    kind: 'extension',
    name: searchValue.trim() || undefined,
  })
  const selectedArtifactId = typeof config.artifact_id === 'string' ? config.artifact_id : undefined
  const versionsQuery = useArtifactVersions(selectedArtifactId)
  const aliasesQuery = useArtifactAliases(selectedArtifactId)
  const selectedVersion = versionsQuery.data?.versions.find(
    (version) => version.version === config.artifact_version
  )
  const selectedAlias = aliasesQuery.data?.aliases.find(
    (alias) => alias.alias === config.artifact_alias
  )

  useEffect(() => {
    if (!selectedArtifactId) {
      if (config.artifact_version || config.artifact_alias || config.artifact_name) {
        onChange({
          artifact_version: undefined,
          artifact_alias: undefined,
          artifact_name: undefined,
        })
      }
      return
    }
    const selected = artifactsQuery.data?.artifacts.find((item) => item.id === selectedArtifactId)
    if (selected && config.artifact_name !== selected.name) {
      onChange({ artifact_name: selected.name })
    }
  }, [
    selectedArtifactId,
    artifactsQuery.data?.artifacts,
    config.artifact_alias,
    config.artifact_name,
    config.artifact_version,
    onChange,
  ])

  const handleArtifactSelect = (value: string) => {
    const selected = artifactsQuery.data?.artifacts.find((item) => item.id === value)
    onChange({
      artifact_id: value,
      artifact_name: selected?.name,
      artifact_version: undefined,
      artifact_alias: undefined,
    })
  }

  const handleAliasSelect = (value?: string) => {
    onChange({
      artifact_alias: value || undefined,
      artifact_version: undefined,
    })
  }

  const handleVersionSelect = (value?: string) => {
    onChange({
      artifact_version: value || undefined,
      artifact_alias: undefined,
    })
  }

  const artifactOptions = (artifactsQuery.data?.artifacts ?? []).map((artifact: Artifact) => ({
    value: artifact.id,
    label: artifact.name,
  }))

  const aliasOptions = (aliasesQuery.data?.aliases ?? []).map((alias) => ({
    value: alias.alias,
    label: `${alias.alias} → ${alias.version}`,
  }))

  const versionOptions = (versionsQuery.data?.versions ?? []).map((version) => ({
    value: version.version,
    label: `${version.version} (${version.filename})`,
  }))

  return (
    <Form layout="vertical">
      {artifactsQuery.error && (
        <Alert
          type="error"
          message="Не удалось загрузить список артефактов"
          style={{ marginBottom: 16 }}
        />
      )}
      <Form.Item
        label="Artifact"
        required
        help="Choose an extension artifact from storage"
        htmlFor="wizard-extension-artifact"
      >
        <Select
          id="wizard-extension-artifact"
          value={config.artifact_id || undefined}
          placeholder="Select artifact"
          loading={artifactsQuery.isLoading}
          options={artifactOptions}
          showSearch
          allowClear
          filterOption={false}
          onSearch={setSearchValue}
          onChange={(value) => {
            if (value) {
              handleArtifactSelect(value as string)
            } else {
              onChange({
                artifact_id: undefined,
                artifact_name: undefined,
                artifact_version: undefined,
                artifact_alias: undefined,
              })
            }
          }}
        />
      </Form.Item>

      <Form.Item
        label="Alias"
        help="Prefer alias for stable/approved installs"
        htmlFor="wizard-extension-alias"
      >
        <Select
          id="wizard-extension-alias"
          value={config.artifact_alias || undefined}
          placeholder="Select alias (optional)"
          loading={aliasesQuery.isLoading}
          options={aliasOptions}
          allowClear
          disabled={!selectedArtifactId}
          onChange={(value) => handleAliasSelect(value as string | undefined)}
        />
      </Form.Item>

      <Form.Item
        label="Version"
        help="Select a specific version if no alias is chosen"
        htmlFor="wizard-extension-version"
      >
        <Select
          id="wizard-extension-version"
          value={config.artifact_version || undefined}
          placeholder="Select version (optional)"
          loading={versionsQuery.isLoading}
          options={versionOptions}
          allowClear
          disabled={!selectedArtifactId || Boolean(config.artifact_alias)}
          onChange={(value) => handleVersionSelect(value as string | undefined)}
        />
      </Form.Item>

      {(selectedAlias || selectedVersion) && (
        <Alert
          message={(
            <Space direction="vertical">
              {selectedAlias && (
                <Text>
                  Alias <Text code>{selectedAlias.alias}</Text> → {selectedAlias.version}
                </Text>
              )}
              {selectedVersion && (
                <Text>
                  {selectedVersion.filename} ({formatFileSize(selectedVersion.size)})
                </Text>
              )}
              {selectedVersion && (
                <Text type="secondary">Checksum: {selectedVersion.checksum}</Text>
              )}
            </Space>
          )}
          type="info"
          style={{ marginBottom: 16 }}
        />
      )}

      <Form.Item>
        <Switch
          id="wizard-install-safe-mode"
          checked={config.safe_mode || false}
          onChange={(checked) => onChange({ safe_mode: checked })}
        />
        <Text style={{ marginLeft: 8 }}>
          Safe mode (install without enabling)
        </Text>
      </Form.Item>
    </Form>
  )
}

/**
 * Form for query operation
 */
const QueryForm = ({
  config,
  onChange,
}: {
  config: OperationConfig
  onChange: (updates: Partial<OperationConfig>) => void
}) => (
  <Form layout="vertical">
    <Form.Item
      label="OData Entity"
      required
      help="Name of the OData entity to query (e.g., 'Catalog_Kontragenty', 'Document_RaskhodnyiOrder')"
      htmlFor="wizard-query-entity"
    >
      <Input
        id="wizard-query-entity"
        placeholder="Entity name"
        value={config.entity || ''}
        onChange={(e) => onChange({ entity: e.target.value })}
      />
    </Form.Item>

    <Form.Item
      label="Filter (optional)"
      help={'OData filter expression (e.g., "NeIspolzovat eq false")'}
      htmlFor="wizard-query-filter"
    >
      <TextArea
        id="wizard-query-filter"
        rows={2}
        placeholder="$filter expression"
        value={config.filter || ''}
        onChange={(e) => onChange({ filter: e.target.value })}
      />
    </Form.Item>

    <Form.Item
      label="Select fields (optional)"
      help="Comma-separated list of fields to return"
      htmlFor="wizard-query-select"
    >
      <Input
        id="wizard-query-select"
        placeholder="Field1,Field2,Field3"
        value={config.select || ''}
        onChange={(e) => onChange({ select: e.target.value })}
      />
    </Form.Item>

    <Form.Item
      label="Limit (optional)"
      help="Maximum number of records to return"
      htmlFor="wizard-query-limit"
    >
      <InputNumber
        id="wizard-query-limit"
        min={1}
        max={10000}
        placeholder="100"
        value={config.top}
        onChange={(value) => onChange({ top: value ?? undefined })}
        style={{ width: '100%' }}
      />
    </Form.Item>
  </Form>
)

/**
 * No configuration required placeholder
 */
const NoConfigRequired = ({ operationLabel }: { operationLabel: string }) => (
  <Card style={{ textAlign: 'center', padding: '40px 20px' }}>
    <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
    <Title level={5} style={{ marginBottom: 8 }}>
      No Additional Configuration Required
    </Title>
    <Text type="secondary">
      "{operationLabel}" operation is ready to execute.
      <br />
      Click "Next" to review and confirm.
    </Text>
  </Card>
)

/**
 * Custom template configuration using DynamicForm
 */
const CustomTemplateForm = ({
  templateId,
  config,
  onConfigChange,
  uploadedFiles,
  onFileUpload,
  onFileRemove,
  onValidationErrorsChange,
}: {
  templateId: string
  config: OperationConfig
  onConfigChange: (config: OperationConfig) => void
  uploadedFiles?: Record<string, string>
  onFileUpload?: (fieldName: string, fileId: string) => void
  onFileRemove?: (fieldName: string) => void
  onValidationErrorsChange?: (errors: DynamicFormValidationError[]) => void
}) => {
  // Fetch schema for this template
  const { schema, workflowName, loading, error } = useTemplateSchema(templateId)

  // Loading state
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
        <Text type="secondary" style={{ display: 'block', marginTop: 16 }}>
          Loading template configuration...
        </Text>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <Alert
        message="Failed to load template configuration"
        description={error}
        type="error"
        showIcon
      />
    )
  }

  // No schema means no configuration needed
  if (!schema) {
    return <NoConfigRequired operationLabel={workflowName || 'Custom Template'} />
  }

  // Handle DynamicForm value change - cast to OperationConfig
  const handleValuesChange = (values: Record<string, unknown>) => {
    onConfigChange(values as OperationConfig)
  }

  // Handle validation errors from DynamicForm
  const handleValidationError = (errors: ValidationError[]) => {
    onValidationErrorsChange?.(errors as DynamicFormValidationError[])
  }

  // Render DynamicForm with the schema
  return (
    <DynamicForm
      schema={schema}
      values={config as Record<string, unknown>}
      onChange={handleValuesChange}
      onValidationError={handleValidationError}
      uploadedFiles={uploadedFiles}
      onFileUpload={onFileUpload}
      onFileRemove={onFileRemove}
      layout="vertical"
    />
  )
}

/**
 * ConfigureStep component
 * Renders operation-specific configuration form.
 * For built-in operations, uses legacy forms.
 * For custom templates, uses DynamicForm with JSON Schema.
 */
export const ConfigureStep = ({
  operationType,
  templateId,
  config,
  onConfigChange,
  uploadedFiles,
  onFileUpload,
  onFileRemove,
  onValidationErrorsChange,
}: ConfigureStepProps) => {
  // Find operation config for built-in operations
  const operationConfig = OPERATION_TYPES.find((op) => op.type === operationType)

  // Handler for partial config updates (for legacy forms)
  const handleChange = useCallback(
    (updates: Partial<OperationConfig>) => {
      onConfigChange({ ...config, ...updates })
    },
    [config, onConfigChange]
  )

  // Check if this is a custom template
  const isCustomTemplate = templateId !== null

  // Check if this operation requires configuration
  const requiresConfig = operationType && !NO_CONFIG_OPERATIONS.includes(operationType)

  // Determine title and description
  const title = isCustomTemplate
    ? 'Configure Custom Template'
    : `Configure: ${operationConfig?.label || operationType || 'Operation'}`

  const description = isCustomTemplate
    ? 'Fill in the required fields for this template'
    : operationConfig?.description

  // Render appropriate form based on operation type or template
  const renderForm = () => {
    // Custom template - use DynamicForm
    if (isCustomTemplate && templateId) {
      return (
        <CustomTemplateForm
          templateId={templateId}
          config={config}
          onConfigChange={onConfigChange}
          uploadedFiles={uploadedFiles}
          onFileUpload={onFileUpload}
          onFileRemove={onFileRemove}
          onValidationErrorsChange={onValidationErrorsChange}
        />
      )
    }

    // No operation type selected
    if (!operationType) {
      return (
        <Alert
          message="No operation type selected"
          description="Please go back and select an operation type."
          type="warning"
          showIcon
        />
      )
    }

    // Built-in operation without configuration
    if (!requiresConfig) {
      return <NoConfigRequired operationLabel={operationConfig?.label || operationType} />
    }

    // Built-in operation with legacy form
    switch (operationType) {
      case 'block_sessions':
        return <BlockSessionsForm config={config} onChange={handleChange} />
      case 'terminate_sessions':
        return <TerminateSessionsForm config={config} onChange={handleChange} />
      case 'install_extension':
        return <InstallExtensionForm config={config} onChange={handleChange} />
      case 'query':
        return <QueryForm config={config} onChange={handleChange} />
      default:
        return (
          <Alert
            message="Configuration not available"
            description={`Configuration form for "${operationType}" is not implemented yet.`}
            type="info"
            showIcon
          />
        )
    }
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 8 }}>
        <Space>
          <SettingOutlined />
          {title}
        </Space>
      </Title>
      {description && (
        <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
          {description}
        </Text>
      )}

      {renderForm()}
    </div>
  )
}
