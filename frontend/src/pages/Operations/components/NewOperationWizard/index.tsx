/**
 * NewOperationWizard - Main wizard component for creating operations
 * Orchestrates 4-step wizard flow with validation.
 * Supports both built-in operations and custom workflow templates.
 */

import { useState, useCallback, useMemo, useEffect } from 'react'
import { App, Modal, Steps, Button, Space, Card, Tag, Typography } from 'antd'
import { getV2 } from '../../../../api/generated'
import type { Database } from '../../../../api/generated/model/database'
import { SelectTypeStep } from './SelectTypeStep'
import { SelectTargetStep } from './SelectTargetStep'
import { ConfigureStep } from './ConfigureStep'
import { ReviewStep } from './ReviewStep'
import type {
  NewOperationWizardProps,
  WizardState,
  OperationType,
  NewOperationData,
  OperationConfig,
  DynamicFormValidationError,
} from './types'
import { REQUIRED_CONFIG_FIELDS } from './types'
import { isSensitiveKey, maskDeep } from '../../../../lib/masking'

// Initialize API
const api = getV2()
const { Text } = Typography

/**
 * Step configuration
 */
const STEPS = [
  { title: 'Type', description: 'Select operation' },
  { title: 'Target', description: 'Choose databases' },
  { title: 'Configure', description: 'Set options' },
  { title: 'Review', description: 'Confirm & execute' },
]

/**
 * Initial wizard state
 */
const getInitialState = (preselectedDatabases?: string[]): WizardState => ({
  currentStep: 0,
  operationType: null,
  selectedTemplateId: null,
  selectedDatabases: preselectedDatabases || [],
  config: {},
  uploadedFiles: {},
})

/**
 * NewOperationWizard component
 * Modal-based 4-step wizard for creating batch operations.
 * Supports both built-in operations and custom workflow templates.
 */
export const NewOperationWizard = ({
  visible,
  onClose,
  onSubmit,
  preselectedDatabases,
}: NewOperationWizardProps) => {
  const { message, modal } = App.useApp()
  // Wizard state
  const [state, setState] = useState<WizardState>(() =>
    getInitialState(preselectedDatabases)
  )
  const [submitting, setSubmitting] = useState(false)
  const [databases, setDatabases] = useState<Database[]>([])
  const [databaseNamesById, setDatabaseNamesById] = useState<Record<string, string>>({})
  const [templateValidationErrors, setTemplateValidationErrors] = useState<DynamicFormValidationError[]>([])

  const selectedTypeLabel = state.operationType ?? null
  const selectedTemplateLabel = state.selectedTemplateId ?? null

  const configSummary = useMemo(() => {
    const entries = Object.entries(state.config).filter(([, value]) => {
      if (value === undefined || value === null) return false
      if (typeof value === 'string' && value.trim() === '') return false
      if (Array.isArray(value) && value.length === 0) return false
      return true
    })

    const summarizeDriverCommand = (value: unknown): string | null => {
      if (!value || typeof value !== 'object') return null
      const dc = value as Record<string, unknown>

      const driver = typeof dc.driver === 'string' ? dc.driver.trim() : ''
      const commandId = typeof dc.command_id === 'string' ? dc.command_id.trim() : ''
      if (!driver && !commandId) return null

      const parts: string[] = []
      if (driver) parts.push(driver.toUpperCase())
      if (commandId) parts.push(commandId)

      const mode = typeof dc.mode === 'string' ? dc.mode.trim() : ''
      if (mode) parts.push(mode)

      const scope = typeof dc.command_scope === 'string' ? dc.command_scope.trim() : ''
      if (scope) parts.push(scope)

      const risk = typeof dc.command_risk_level === 'string' ? dc.command_risk_level.trim() : ''
      if (risk) parts.push(risk)

      if (dc.confirm_dangerous === true) parts.push('confirmed')

      return `driver_command: ${parts.join(' ')}`
    }

    return entries.map(([key, value]) => {
      if (key === 'driver_command') {
        return summarizeDriverCommand(value) ?? 'driver_command: [invalid]'
      }

      if (isSensitiveKey(key)) {
        return `${key}: ***`
      }

      if (value instanceof File) {
        return `${key}: ${value.name}`
      }

      if (typeof value === 'object') {
        try {
          return `${key}: ${JSON.stringify(maskDeep(value))}`
        } catch {
          return `${key}: [object]`
        }
      }

      return `${key}: ${String(value)}`
    })
  }, [state.config])

  const databaseSummary = useMemo(() => {
    const ids = state.selectedDatabases
    if (ids.length === 0) return []
    const preview = ids.slice(0, 3)
    const suffix = ids.length > preview.length ? ` +${ids.length - preview.length}` : ''
    return preview.map((id) => {
      const label = databaseNamesById[id] || id
      return `${label}${suffix && id === preview[preview.length - 1] ? suffix : ''}`
    })
  }, [databaseNamesById, state.selectedDatabases])

  // Reset state when modal opens
  useEffect(() => {
    if (visible) {
      setState(getInitialState(preselectedDatabases))
      setTemplateValidationErrors([])
      setDatabaseNamesById({})
    }
  }, [visible, preselectedDatabases])

  // Load databases for review step with cleanup for memory leak prevention
  useEffect(() => {
    let cancelled = false

    if (state.currentStep === 3 && state.selectedDatabases.length > 0) {
      const fetchDatabases = async () => {
        try {
          const response = await api.getDatabasesListDatabases()
          if (cancelled) return
          const allDatabases = response.databases ?? []
          const selectedSet = new Set(state.selectedDatabases)
          setDatabases(allDatabases.filter((db) => selectedSet.has(db.id)))
        } catch (error) {
          if (cancelled) return
          console.error('Failed to load databases:', error)
        }
      }
      fetchDatabases()
    }

    return () => { cancelled = true }
  }, [state.currentStep, state.selectedDatabases])

  // Validate configuration based on operation type or custom template
  const validateConfig = useCallback(
    (
      operationType: OperationType | null,
      templateId: string | null,
      selectedDatabases: string[],
      config: OperationConfig,
      validationErrors: DynamicFormValidationError[]
    ): boolean => {
      // Custom templates - check DynamicForm validation errors
      if (templateId !== null) {
        // Valid if no validation errors from DynamicForm
        return validationErrors.length === 0
      }

      // Built-in operations
      if (!operationType) return false

      // Schema-driven command builders (cli + ibcmd)
      if (operationType === 'designer_cli' || operationType === 'ibcmd_cli') {
        const dc = config.driver_command
        if (!dc || typeof dc !== 'object') {
          return false
        }

        if (operationType === 'designer_cli' && dc.driver !== 'cli') {
          return false
        }
        if (operationType === 'ibcmd_cli' && dc.driver !== 'ibcmd') {
          return false
        }

        const commandId = typeof dc.command_id === 'string' ? dc.command_id.trim() : ''
        if (!commandId) {
          return false
        }

        if (dc.command_risk_level === 'dangerous' && dc.confirm_dangerous !== true) {
          return false
        }

        if (operationType === 'ibcmd_cli' && dc.command_scope === 'global') {
          const authDb = typeof dc.auth_database_id === 'string' ? dc.auth_database_id : ''
          if (!authDb || !selectedDatabases.includes(authDb)) {
            return false
          }

          const connection = dc.connection
          const hasRemote = typeof connection?.remote === 'string' && connection.remote.trim().length > 0
          const hasPid = typeof connection?.pid === 'number'
          const offline = connection?.offline
          const hasOffline = Boolean(
            offline
            && typeof offline === 'object'
            && Object.values(offline).some((value) => typeof value === 'string' && value.trim().length > 0)
          )
          if (!hasRemote && !hasPid && !hasOffline) {
            return false
          }
        }

        // Guard: forbid --pid in raw args (must be provided via connection.pid)
        if (operationType === 'ibcmd_cli' && typeof dc.args_text === 'string') {
          const lines = dc.args_text
            .split('\n')
            .map((item) => item.trim().toLowerCase())
            .filter((item) => item.length > 0)
          if (lines.some((item) => item === '--pid' || item.startsWith('--pid='))) {
            return false
          }
        }

        return true
      }

      const requiredFields = REQUIRED_CONFIG_FIELDS[operationType]
      if (!requiredFields || requiredFields.length === 0) {
        return true // No required fields for this operation
      }

      return requiredFields.every((field) => {
        const value = config[field]
        if (value === undefined || value === null) return false
        if (typeof value === 'string' && value.trim() === '') return false
        return true
      })
    },
    []
  )

  // Validation for each step
  const canProceed = useMemo(() => {
    switch (state.currentStep) {
      case 0: // Type selection - need either operation type OR template
        return state.operationType !== null || state.selectedTemplateId !== null
      case 1: // Database selection
        return state.selectedDatabases.length > 0
      case 2: // Configuration
        return validateConfig(state.operationType, state.selectedTemplateId, state.selectedDatabases, state.config, templateValidationErrors)
      case 3: // Review
        return true
      default:
        return false
    }
  }, [
    state.currentStep,
    state.operationType,
    state.selectedTemplateId,
    state.selectedDatabases,
    state.config,
    templateValidationErrors,
    validateConfig,
  ])

  // Handlers
  const handleTypeSelect = useCallback((type: OperationType) => {
    setState((prev) => ({
      ...prev,
      operationType: type,
      selectedTemplateId: null, // Clear template when selecting built-in operation
      config: {}, // Reset config when changing type
      uploadedFiles: {},
    }))
  }, [])

  const handleTemplateSelect = useCallback((templateId: string | null) => {
    setState((prev) => ({
      ...prev,
      selectedTemplateId: templateId,
      operationType: null, // Clear operation type when selecting template
      config: {}, // Reset config when changing template
      uploadedFiles: {},
    }))
    setTemplateValidationErrors([]) // Reset validation errors when changing template
  }, [])

  const handleDatabasesChange = useCallback((ids: string[]) => {
    setState((prev) => ({ ...prev, selectedDatabases: ids }))
  }, [])

  const handleDatabaseMetadataChange = useCallback((next: Record<string, string>) => {
    setDatabaseNamesById((prev) => ({
      ...prev,
      ...next,
    }))
  }, [])

  const handleConfigChange = useCallback((config: OperationConfig) => {
    setState((prev) => ({ ...prev, config }))
  }, [])

  const handleValidationErrorsChange = useCallback((errors: DynamicFormValidationError[]) => {
    setTemplateValidationErrors(errors)
  }, [])

  const handleFileUpload = useCallback((fieldName: string, fileId: string) => {
    setState((prev) => ({
      ...prev,
      uploadedFiles: {
        ...prev.uploadedFiles,
        [fieldName]: fileId,
      },
    }))
  }, [])

  const handleFileRemove = useCallback((fieldName: string) => {
    setState((prev) => {
      const newUploadedFiles = { ...prev.uploadedFiles }
      delete newUploadedFiles[fieldName]
      return {
        ...prev,
        uploadedFiles: newUploadedFiles,
      }
    })
  }, [])

  const handleNext = useCallback(() => {
    if (!canProceed) {
      // Show validation message
      if (state.currentStep === 0) {
        message.warning('Please select an operation type or custom template')
      } else if (state.currentStep === 1) {
        message.warning('Please select at least one database')
      } else if (state.currentStep === 2) {
        message.warning('Please fill in all required configuration fields')
      }
      return
    }

    setState((prev) => ({
      ...prev,
      currentStep: Math.min(prev.currentStep + 1, STEPS.length - 1),
    }))
  }, [canProceed, state.currentStep, message])

  const handlePrevious = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(prev.currentStep - 1, 0),
    }))
  }, [])

  const handleSubmit = useCallback(async () => {
    // Validate: need either operation type or template
    if (!state.operationType && !state.selectedTemplateId) {
      message.error('Operation type or template is required')
      return
    }

    if (state.selectedDatabases.length === 0) {
      message.error('At least one database must be selected')
      return
    }

    // Build submission data
    const data: NewOperationData = {
      operationType: state.operationType,
      databaseIds: state.selectedDatabases,
      config: state.config,
    }

    // Add template info if using custom template
    if (state.selectedTemplateId) {
      data.templateId = state.selectedTemplateId
    }

    // Add uploaded files if any
    if (Object.keys(state.uploadedFiles).length > 0) {
      data.uploadedFiles = state.uploadedFiles
    }

    setSubmitting(true)
    try {
      await onSubmit(data)
      message.success('Operation created successfully')
      onClose()
    } catch (error) {
      console.error('Failed to create operation:', error)
      type ApiErrorShape = {
        success?: boolean
        error?: {
          code?: string
          message?: string
          details?: {
            missing?: Array<{
              database_id?: string
              database_name?: string
              missing_keys?: string[]
            }>
            missing_total?: number
            omitted?: number
          }
        }
      }

      const apiError = (error as { response?: { data?: ApiErrorShape } } | null)?.response?.data?.error
      const errorCode = typeof apiError?.code === 'string' ? apiError.code : ''
      const errorMessage = typeof apiError?.message === 'string' ? apiError.message : ''

      if (errorCode === 'OFFLINE_DB_METADATA_NOT_CONFIGURED') {
        const details = apiError?.details
        const missing = Array.isArray(details?.missing) ? details?.missing : []
        const missingTotal = typeof details?.missing_total === 'number' ? details.missing_total : missing.length
        const omitted = typeof details?.omitted === 'number' ? details.omitted : 0

        modal.error({
          title: 'Offline DBMS metadata не настроены',
          content: (
            <Space direction="vertical" size="small">
              <Text>
                Для offline-подключения нужны <Text code>dbms</Text>, <Text code>db_server</Text>, <Text code>db_name</Text>.
              </Text>
              <Text type="secondary">
                Исправьте DBMS metadata на странице <Text code>/databases</Text> (или задайте общий override в Configure через{' '}
                <Text code>connection.offline.*</Text>).
              </Text>
              {missing.length > 0 && (
                <div>
                  {missing.slice(0, 10).map((item) => {
                    const label = item.database_name || item.database_id || 'unknown'
                    const keys = Array.isArray(item.missing_keys) ? item.missing_keys.join(', ') : ''
                    return (
                      <div key={item.database_id || label}>
                        <Tag>{label}</Tag>
                        {keys ? <Text type="secondary">missing: {keys}</Text> : null}
                      </div>
                    )
                  })}
                  {(missingTotal > 10 || omitted > 0) ? (
                    <Text type="secondary">... and more (total: {missingTotal})</Text>
                  ) : null}
                </div>
              )}
            </Space>
          ),
        })
        return
      }

      if (errorMessage) {
        message.error(errorMessage)
        return
      }

      message.error('Failed to create operation')
    } finally {
      setSubmitting(false)
    }
  }, [
    state.operationType,
    state.selectedTemplateId,
    state.selectedDatabases,
    state.config,
    state.uploadedFiles,
    onSubmit,
    onClose,
    message,
    modal,
  ])

  const handleClose = useCallback(() => {
    if (submitting) return
    onClose()
  }, [submitting, onClose])

  // Render step content
  const renderStepContent = () => {
    switch (state.currentStep) {
      case 0:
        return (
          <SelectTypeStep
            selectedType={state.operationType}
            selectedTemplateId={state.selectedTemplateId}
            onSelect={handleTypeSelect}
            onSelectTemplate={handleTemplateSelect}
          />
        )
      case 1:
        return (
          <SelectTargetStep
            selectedDatabases={state.selectedDatabases}
            onSelectionChange={handleDatabasesChange}
            onSelectionMetadataChange={handleDatabaseMetadataChange}
            preselectedDatabases={preselectedDatabases}
          />
        )
      case 2:
        return (
          <ConfigureStep
            operationType={state.operationType}
            templateId={state.selectedTemplateId}
            selectedDatabases={state.selectedDatabases}
            databaseNamesById={databaseNamesById}
            config={state.config}
            onConfigChange={handleConfigChange}
            uploadedFiles={state.uploadedFiles}
            onFileUpload={handleFileUpload}
            onFileRemove={handleFileRemove}
            onValidationErrorsChange={handleValidationErrorsChange}
          />
        )
      case 3:
        return (
          <ReviewStep
            operationType={state.operationType}
            selectedDatabases={state.selectedDatabases}
            config={state.config}
            databases={databases}
          />
        )
      default:
        return null
    }
  }

  // Check if we're on the last step
  const isLastStep = state.currentStep === STEPS.length - 1

  // Determine submit button text based on type
  const submitButtonText = state.selectedTemplateId
    ? 'Execute Template'
    : 'Execute Operation'

  return (
    <Modal
      title="New Operation"
      open={visible}
      onCancel={handleClose}
      width={900}
      footer={
        <Space style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <Button onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Space>
            {state.currentStep > 0 && (
              <Button onClick={handlePrevious} disabled={submitting}>
                Previous
              </Button>
            )}
            {isLastStep ? (
              <Button
                type="primary"
                onClick={handleSubmit}
                loading={submitting}
                disabled={!canProceed}
              >
                {submitButtonText}
              </Button>
            ) : (
              <Button type="primary" onClick={handleNext} disabled={!canProceed}>
                Next
              </Button>
            )}
          </Space>
        </Space>
      }
      destroyOnHidden
      maskClosable={!submitting}
    >
      {/* Steps indicator */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div>
            <Text strong>Type:</Text>{' '}
            {selectedTemplateLabel
              ? <Tag color="blue">Template: {selectedTemplateLabel}</Tag>
              : selectedTypeLabel
                ? <Tag color="green">{selectedTypeLabel}</Tag>
                : <Text type="secondary">Not selected</Text>}
          </div>
          <div>
            <Text strong>Databases:</Text>{' '}
            {state.selectedDatabases.length > 0
              ? (
                <Space size={4} wrap>
                  {databaseSummary.map((id) => (
                    <Tag key={id}>{id}</Tag>
                  ))}
                </Space>
              )
              : <Text type="secondary">Not selected</Text>}
          </div>
          <div>
            <Text strong>Config:</Text>{' '}
            {configSummary.length > 0
              ? (
                <Space size={4} wrap>
                  {configSummary.map((entry) => (
                    <Tag key={entry}>{entry}</Tag>
                  ))}
                </Space>
              )
              : <Text type="secondary">Not set</Text>}
          </div>
        </Space>
      </Card>

      <Steps
        current={state.currentStep}
        items={STEPS.map((step, index) => ({
          title: step.title,
          description: step.description,
          status:
            index < state.currentStep
              ? 'finish'
              : index === state.currentStep
                ? 'process'
                : 'wait',
        }))}
        style={{ marginBottom: 24 }}
      />

      {/* Step content */}
      <div style={{ minHeight: 400 }}>{renderStepContent()}</div>
    </Modal>
  )
}

// Re-export types for convenience
export type {
  NewOperationWizardProps,
  NewOperationData,
  OperationType,
} from './types'
