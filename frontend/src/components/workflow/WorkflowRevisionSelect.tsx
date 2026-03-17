import { Select } from 'antd'

import type { AvailableWorkflowRevision } from '../../types/workflow'
import {
  buildWorkflowRevisionOptions,
  buildWorkflowRevisionValue,
  type CurrentWorkflowSelection,
} from '../../features/authoringReferences/options'

type WorkflowRevisionSelectProps = {
  workflows: AvailableWorkflowRevision[]
  currentWorkflow?: CurrentWorkflowSelection
  disabled?: boolean
  loading?: boolean
  allowClear?: boolean
  placeholder?: string
  id?: string
  testId?: string
  onChange: (workflow?: AvailableWorkflowRevision) => void
}

export function WorkflowRevisionSelect({
  workflows,
  currentWorkflow,
  disabled,
  loading,
  allowClear,
  placeholder,
  id,
  testId,
  onChange,
}: WorkflowRevisionSelectProps) {
  const workflowOptions = buildWorkflowRevisionOptions({
    workflows,
    currentWorkflow,
  })
  const value = currentWorkflow?.workflowRevisionId
    ? buildWorkflowRevisionValue(currentWorkflow.workflowRevisionId)
    : undefined

  return (
    <Select
      id={id}
      data-testid={testId}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      loading={loading}
      showSearch
      allowClear={allowClear}
      optionFilterProp="label"
      options={workflowOptions.map((option) => ({
        value: option.value,
        label: option.label,
      }))}
      onChange={(nextValue) => {
        const selected = workflows.find((workflow) => workflow.workflowRevisionId === nextValue)
        onChange(selected)
      }}
    />
  )
}
