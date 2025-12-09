/**
 * NewOperationWizard - Main wizard component for creating operations
 * Orchestrates 4-step wizard flow with validation.
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
  selectedDatabases: preselectedDatabases || [],
  config: {},
})

/**
 * NewOperationWizard component
 * Modal-based 4-step wizard for creating batch operations
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

  // Reset state when modal opens
  useEffect(() => {
    if (visible) {
      setState(getInitialState(preselectedDatabases))
    }
  }, [visible, preselectedDatabases])

  // Load databases for review step
  useEffect(() => {
    if (state.currentStep === 3 && state.selectedDatabases.length > 0) {
      const fetchDatabases = async () => {
        try {
          const response = await api.getDatabasesListDatabases()
          const allDatabases = response.databases ?? []
          const selectedSet = new Set(state.selectedDatabases)
          setDatabases(allDatabases.filter((db) => selectedSet.has(db.id)))
        } catch (error) {
          console.error('Failed to load databases:', error)
        }
      }
      fetchDatabases()
    }
  }, [state.currentStep, state.selectedDatabases])

  // Validate configuration based on operation type
  const validateConfig = useCallback(
    (operationType: OperationType | null, config: OperationConfig): boolean => {
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
      case 0: // Type selection
        return state.operationType !== null
      case 1: // Database selection
        return state.selectedDatabases.length > 0
      case 2: // Configuration
        return validateConfig(state.operationType, state.config)
      case 3: // Review
        return true
      default:
        return false
    }
  }, [state.currentStep, state.operationType, state.selectedDatabases.length, state.config, validateConfig])

  // Handlers
  const handleTypeSelect = useCallback((type: OperationType) => {
    setState((prev) => ({ ...prev, operationType: type }))
  }, [])

  const handleDatabasesChange = useCallback((ids: string[]) => {
    setState((prev) => ({ ...prev, selectedDatabases: ids }))
  }, [])

  const handleConfigChange = useCallback((config: OperationConfig) => {
    setState((prev) => ({ ...prev, config }))
  }, [])

  const handleNext = useCallback(() => {
    if (!canProceed) {
      // Show validation message
      if (state.currentStep === 0) {
        message.warning('Please select an operation type')
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
    if (!state.operationType) {
      message.error('Operation type is required')
      return
    }

    if (state.selectedDatabases.length === 0) {
      message.error('At least one database must be selected')
      return
    }

    const data: NewOperationData = {
      operationType: state.operationType,
      databaseIds: state.selectedDatabases,
      config: state.config,
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
  }, [state.operationType, state.selectedDatabases, state.config, onSubmit, onClose])

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
            onSelect={handleTypeSelect}
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
            config={state.config}
            onConfigChange={handleConfigChange}
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
                Execute Operation
              </Button>
            ) : (
              <Button type="primary" onClick={handleNext} disabled={!canProceed}>
                Next
              </Button>
            )}
          </Space>
        </Space>
      }
      destroyOnClose
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
