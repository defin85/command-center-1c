/**
 * NewOperationWizard - Main wizard component for creating operations
 * Orchestrates 4-step wizard flow with validation.
 * Supports both built-in operations and custom workflow templates.
 */

import { useState, useCallback, useMemo, useEffect } from 'react'
import { Modal, Steps, Button, Space, message } from 'antd'
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

// Initialize API
const api = getV2()

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
  // Wizard state
  const [state, setState] = useState<WizardState>(() =>
    getInitialState(preselectedDatabases)
  )
  const [submitting, setSubmitting] = useState(false)
  const [databases, setDatabases] = useState<Database[]>([])
  const [templateValidationErrors, setTemplateValidationErrors] = useState<DynamicFormValidationError[]>([])

  // Reset state when modal opens
  useEffect(() => {
    if (visible) {
      setState(getInitialState(preselectedDatabases))
      setTemplateValidationErrors([])
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
        return validateConfig(state.operationType, state.selectedTemplateId, state.config, templateValidationErrors)
      case 3: // Review
        return true
      default:
        return false
    }
  }, [
    state.currentStep,
    state.operationType,
    state.selectedTemplateId,
    state.selectedDatabases.length,
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
  }, [canProceed, state.currentStep])

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
            preselectedDatabases={preselectedDatabases}
          />
        )
      case 2:
        return (
          <ConfigureStep
            operationType={state.operationType}
            templateId={state.selectedTemplateId}
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
