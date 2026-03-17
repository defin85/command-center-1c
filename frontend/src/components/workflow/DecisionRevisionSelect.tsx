import { Select } from 'antd'

import type { AvailableDecisionRevision } from '../../types/workflow'
import {
  buildDecisionRevisionOptions,
  buildDecisionRevisionValue,
  type CurrentDecisionSelection,
} from '../../features/authoringReferences/options'

type DecisionRevisionSelectProps = {
  availableDecisions: AvailableDecisionRevision[]
  currentDecision?: CurrentDecisionSelection
  disabled?: boolean
  loading?: boolean
  allowClear?: boolean
  placeholder?: string
  id?: string
  testId?: string
  onChange: (decision?: CurrentDecisionSelection) => void
}

export function DecisionRevisionSelect({
  availableDecisions,
  currentDecision,
  disabled,
  loading,
  allowClear,
  placeholder,
  id,
  testId,
  onChange,
}: DecisionRevisionSelectProps) {
  const decisionOptions = buildDecisionRevisionOptions({
    decisions: availableDecisions,
    currentDecision,
  })

  const value = currentDecision
    ? buildDecisionRevisionValue(currentDecision.decision_table_id, currentDecision.decision_revision)
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
      options={decisionOptions.map((option) => ({
        value: option.value,
        label: option.label,
      }))}
      onChange={(nextValue) => {
        const selected = decisionOptions.find((option) => option.value === nextValue)
        onChange(selected
          ? {
              decision_table_id: selected.decisionTableId,
              decision_key: selected.decisionKey,
              decision_revision: selected.decisionRevision,
            }
          : undefined)
      }}
    />
  )
}
