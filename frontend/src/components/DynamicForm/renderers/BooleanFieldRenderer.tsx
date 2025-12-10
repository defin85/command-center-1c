/**
 * BooleanFieldRenderer Component
 *
 * Renders boolean fields using Ant Design Switch.
 */

import { Switch } from 'antd'
import type { FieldRendererProps } from '../types'

/**
 * Renderer for boolean fields.
 * Uses Switch component for better UX.
 */
export function BooleanFieldRenderer({
  name,
  schema,
  value,
  onChange,
  disabled,
}: FieldRendererProps) {
  // Get custom labels from schema
  const trueLabel = (schema as { 'x-true-label'?: string })['x-true-label']
  const falseLabel = (schema as { 'x-false-label'?: string })['x-false-label']

  return (
    <Switch
      id={name}
      checked={!!value}
      disabled={disabled}
      checkedChildren={trueLabel}
      unCheckedChildren={falseLabel}
      onChange={(checked) => onChange(checked)}
      aria-label={schema.title || name}
    />
  )
}

export default BooleanFieldRenderer
