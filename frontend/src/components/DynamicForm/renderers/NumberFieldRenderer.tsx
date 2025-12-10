/**
 * NumberFieldRenderer Component
 *
 * Renders number and integer input fields using Ant Design InputNumber.
 */

import { InputNumber } from 'antd'
import type { FieldRendererProps } from '../types'

/**
 * Renderer for numeric fields.
 * Supports: number, integer
 */
export function NumberFieldRenderer({
  name,
  schema,
  value,
  onChange,
  disabled,
}: FieldRendererProps) {
  const placeholder = schema['x-placeholder'] || schema.title

  // Determine step based on type
  const schemaType = Array.isArray(schema.type) ? schema.type[0] : schema.type
  const isInteger = schemaType === 'integer'
  const step = isInteger ? 1 : 0.01

  // Get min/max from schema
  const min = schema.minimum
  const max = schema.maximum

  // Handle exclusive bounds
  const exclusiveMin = schema.exclusiveMinimum
  const exclusiveMax = schema.exclusiveMaximum

  // Calculate effective bounds
  let effectiveMin = min
  let effectiveMax = max

  if (typeof exclusiveMin === 'number') {
    effectiveMin = exclusiveMin + (isInteger ? 1 : 0.001)
  }
  if (typeof exclusiveMax === 'number') {
    effectiveMax = exclusiveMax - (isInteger ? 1 : 0.001)
  }

  return (
    <InputNumber
      id={name}
      value={value as number}
      placeholder={placeholder}
      disabled={disabled}
      min={effectiveMin}
      max={effectiveMax}
      step={step}
      precision={isInteger ? 0 : undefined}
      style={{ width: '100%' }}
      onChange={(val) => onChange(val)}
    />
  )
}

export default NumberFieldRenderer
