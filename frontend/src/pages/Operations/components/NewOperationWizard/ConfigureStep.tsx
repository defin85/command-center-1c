/**
 * ConfigureStep - Step 3 of NewOperationWizard
 * Dynamic configuration form based on operation type.
 * Supports both built-in operation forms and DynamicForm for custom templates.
 */

import { useCallback } from 'react'
import {
  Typography,
  Form,
  Input,
  AutoComplete,
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
import { DynamicForm } from '../../../../components/DynamicForm'
import { useTemplateSchema } from '../../../../hooks/useTemplateSchema'
import { useCliCommandCatalog } from '../../../../hooks/useCliCommandCatalog'

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
 * Form for designer_cli operation
 */
const DesignerCliForm = ({
  config,
  onChange,
}: {
  config: OperationConfig
  onChange: (updates: Partial<OperationConfig>) => void
}) => {
  const { commands, loading } = useCliCommandCatalog()
  const commandOptions = commands.map((cmd) => ({
    value: cmd.id,
    label: cmd.label,
  }))

  const disableStartupMessages = config.disable_startup_messages ?? true
  const disableStartupDialogs = config.disable_startup_dialogs ?? true

  return (
    <Form layout="vertical">
      <Form.Item
        label="Command"
        required
        help="DESIGNER batch command (e.g., LoadCfg, UpdateDBCfg)"
        htmlFor="wizard-designer-command"
      >
        <AutoComplete
          options={commandOptions}
          value={config.command || ''}
          onChange={(value) => onChange({ command: value })}
          placeholder="Enter command"
        >
          <Input id="wizard-designer-command" />
        </AutoComplete>
      </Form.Item>

      <Form.Item
        label="Arguments"
        help="One argument per line (will be appended after /<command>)"
        htmlFor="wizard-designer-args"
      >
        <TextArea
          id="wizard-designer-args"
          rows={6}
          placeholder="/path/to/file.cfe\n-Extension\nMyExtension"
          value={config.args || ''}
          onChange={(e) => onChange({ args: e.target.value })}
        />
      </Form.Item>

      <Form.Item label="Disable startup messages" htmlFor="wizard-designer-disable-messages">
        <Switch
          id="wizard-designer-disable-messages"
          checked={disableStartupMessages}
          onChange={(checked) => onChange({ disable_startup_messages: checked })}
        />
      </Form.Item>

      <Form.Item label="Disable startup dialogs" htmlFor="wizard-designer-disable-dialogs">
        <Switch
          id="wizard-designer-disable-dialogs"
          checked={disableStartupDialogs}
          onChange={(checked) => onChange({ disable_startup_dialogs: checked })}
        />
      </Form.Item>

      {loading && (
        <Alert
          message="Loading command catalog"
          type="info"
          showIcon
        />
      )}
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
      case 'designer_cli':
        return <DesignerCliForm config={config} onChange={handleChange} />
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
