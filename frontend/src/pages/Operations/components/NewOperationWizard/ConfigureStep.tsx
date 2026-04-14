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
  DatePicker,
  InputNumber,
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
import { DriverCommandBuilder, type DriverCommandOperationConfig } from '../../../../components/driverCommands/DriverCommandBuilder'
import { useOperationsTranslation } from '../../../../i18n'
import { getOperationTypeDescription, getOperationTypeLabel } from '../../utils'

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
  const { t } = useOperationsTranslation()
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
        label={t(($) => $.wizard.configure.blockStart)}
        help={t(($) => $.wizard.configure.blockStartHelp)}
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
        label={t(($) => $.wizard.configure.blockEnd)}
        help={t(($) => $.wizard.configure.blockEndHelp)}
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
        label={t(($) => $.wizard.configure.userMessage)}
        required
        help={t(($) => $.wizard.configure.userMessageHelp)}
        htmlFor="wizard-block-message"
      >
        <TextArea
          id="wizard-block-message"
          rows={3}
          placeholder={t(($) => $.wizard.configure.userMessagePlaceholder)}
          value={config.message || ''}
          onChange={(e) => onChange({ message: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label={t(($) => $.wizard.configure.permissionCode)}
        help={t(($) => $.wizard.configure.permissionCodeHelp)}
        htmlFor="wizard-block-permission-code"
      >
        <Input
          id="wizard-block-permission-code"
          placeholder={t(($) => $.wizard.configure.permissionCodePlaceholder)}
          value={config.permission_code || ''}
          onChange={(e) => onChange({ permission_code: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label={t(($) => $.wizard.configure.blockParameter)}
        help={t(($) => $.wizard.configure.blockParameterHelp)}
        htmlFor="wizard-block-parameter"
      >
        <Input
          id="wizard-block-parameter"
          placeholder={t(($) => $.wizard.configure.blockParameterPlaceholder)}
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
}) => {
  const { t } = useOperationsTranslation()
  return (
    <Form layout="vertical">
      <Form.Item
        label={t(($) => $.wizard.configure.filterByApplication)}
        help={t(($) => $.wizard.configure.filterByApplicationHelp)}
        htmlFor="wizard-terminate-filter-app"
      >
        <Input
          id="wizard-terminate-filter-app"
          placeholder={t(($) => $.wizard.configure.filterByApplicationPlaceholder)}
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
          {t(($) => $.wizard.configure.excludeAdmins)}
        </Checkbox>
      </Form.Item>
    </Form>
  )
}

const DriverCommandsForm = ({
  driver,
  config,
  onChange,
  selectedDatabases,
  databaseNamesById,
}: {
  driver: 'cli' | 'ibcmd'
  config: OperationConfig
  onChange: (updates: Partial<OperationConfig>) => void
  selectedDatabases: string[]
  databaseNamesById?: Record<string, string>
}) => {
  const current: DriverCommandOperationConfig = (
    config.driver_command && config.driver_command.driver === driver
      ? config.driver_command
      : { driver, mode: 'guided', params: {} }
  )

  const handleDriverCommandChange = (updates: Partial<DriverCommandOperationConfig>) => {
    onChange({
      driver_command: {
        ...current,
        ...updates,
        driver,
      },
    })
  }

  return (
    <DriverCommandBuilder
      driver={driver}
      config={current}
      onChange={handleDriverCommandChange}
      availableDatabaseIds={selectedDatabases}
      databaseNamesById={databaseNamesById}
    />
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
}) => {
  const { t } = useOperationsTranslation()
  return (
    <Form layout="vertical">
      <Form.Item
        label={t(($) => $.wizard.configure.odataEntity)}
        required
        help={t(($) => $.wizard.configure.odataEntityHelp)}
        htmlFor="wizard-query-entity"
      >
        <Input
          id="wizard-query-entity"
          placeholder={t(($) => $.wizard.configure.odataEntityPlaceholder)}
          value={config.entity || ''}
          onChange={(e) => onChange({ entity: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label={t(($) => $.wizard.configure.filter)}
        help={t(($) => $.wizard.configure.filterHelp)}
        htmlFor="wizard-query-filter"
      >
        <TextArea
          id="wizard-query-filter"
          rows={2}
          placeholder={t(($) => $.wizard.configure.filterPlaceholder)}
          value={config.filter || ''}
          onChange={(e) => onChange({ filter: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label={t(($) => $.wizard.configure.selectFields)}
        help={t(($) => $.wizard.configure.selectFieldsHelp)}
        htmlFor="wizard-query-select"
      >
        <Input
          id="wizard-query-select"
          placeholder={t(($) => $.wizard.configure.selectFieldsPlaceholder)}
          value={config.select || ''}
          onChange={(e) => onChange({ select: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label={t(($) => $.wizard.configure.limit)}
        help={t(($) => $.wizard.configure.limitHelp)}
        htmlFor="wizard-query-limit"
      >
        <InputNumber
          id="wizard-query-limit"
          min={1}
          max={10000}
          placeholder={t(($) => $.wizard.configure.limitPlaceholder)}
          value={config.top}
          onChange={(value) => onChange({ top: value ?? undefined })}
          style={{ width: '100%' }}
        />
      </Form.Item>
    </Form>
  )
}

/**
 * No configuration required placeholder
 */
const NoConfigRequired = ({ operationLabel }: { operationLabel: string }) => {
  const { t } = useOperationsTranslation()
  return (
    <Card style={{ textAlign: 'center', padding: '40px 20px' }}>
      <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
      <Title level={5} style={{ marginBottom: 8 }}>
        {t(($) => $.wizard.configure.noAdditionalConfigTitle)}
      </Title>
      <Text type="secondary">
        {t(($) => $.wizard.configure.noAdditionalConfigDescription, { value: operationLabel })}
      </Text>
    </Card>
  )
}

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
  const { t } = useOperationsTranslation()
  // Fetch schema for this template
  const { schema, workflowName, loading, error } = useTemplateSchema(templateId)

  // Loading state
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
        <Text type="secondary" style={{ display: 'block', marginTop: 16 }}>
          {t(($) => $.wizard.configure.loadingTemplateConfiguration)}
        </Text>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <Alert
        message={t(($) => $.wizard.configure.failedToLoadTemplateConfiguration)}
        description={error}
        type="error"
        showIcon
      />
    )
  }

  // No schema means no configuration needed
  if (!schema) {
    return <NoConfigRequired operationLabel={workflowName || t(($) => $.wizard.configure.customTemplateFallback)} />
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
  selectedDatabases,
  databaseNamesById,
  config,
  onConfigChange,
  uploadedFiles,
  onFileUpload,
  onFileRemove,
  onValidationErrorsChange,
}: ConfigureStepProps) => {
  const { t } = useOperationsTranslation()
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
    ? t(($) => $.wizard.configure.configureCustomTemplate)
    : t(($) => $.wizard.configure.configureOperation, {
      value: operationType ? getOperationTypeLabel(operationType, t) : 'Operation',
    })

  const description = isCustomTemplate
    ? t(($) => $.wizard.configure.customTemplateDescription)
    : (operationType ? getOperationTypeDescription(operationType, t) : operationConfig?.description)

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
          message={t(($) => $.wizard.configure.noOperationSelectedTitle)}
          description={t(($) => $.wizard.configure.noOperationSelectedDescription)}
          type="warning"
          showIcon
        />
      )
    }

    // Built-in operation without configuration
    if (!requiresConfig) {
      return <NoConfigRequired operationLabel={operationType ? getOperationTypeLabel(operationType, t) : (operationConfig?.label || 'Operation')} />
    }

    // Built-in operation with legacy form
    switch (operationType) {
      case 'block_sessions':
        return <BlockSessionsForm config={config} onChange={handleChange} />
      case 'terminate_sessions':
        return <TerminateSessionsForm config={config} onChange={handleChange} />
      case 'designer_cli':
        return (
          <DriverCommandsForm
            driver="cli"
            config={config}
            selectedDatabases={selectedDatabases}
            databaseNamesById={databaseNamesById}
            onChange={handleChange}
          />
        )
      case 'ibcmd_cli':
        return (
          <DriverCommandsForm
            driver="ibcmd"
            config={config}
            selectedDatabases={selectedDatabases}
            databaseNamesById={databaseNamesById}
            onChange={handleChange}
          />
        )
      case 'query':
        return <QueryForm config={config} onChange={handleChange} />
      default:
        return (
          <Alert
            message={t(($) => $.wizard.configure.configurationUnavailableTitle)}
            description={t(($) => $.wizard.configure.configurationUnavailableDescription, { value: operationType })}
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
