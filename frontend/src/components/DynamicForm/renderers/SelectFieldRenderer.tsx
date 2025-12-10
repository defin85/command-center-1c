/**
 * SelectFieldRenderer Component
 *
 * Renders select and multi-select fields using Ant Design Select.
 */

import { Select } from 'antd'
import type { FieldRendererProps } from '../types'
import { getSelectOptions } from '../utils/schemaParser'

/**
 * Renderer for select fields.
 * Supports: select, multi-select
 */
export function SelectFieldRenderer({
  name,
  schema,
  value,
  onChange,
  disabled,
}: FieldRendererProps) {
  const placeholder = schema['x-placeholder'] || schema.title
  const fieldType = schema['x-field-type']

  // Get options from schema
  const options = getSelectOptions(schema)

  // Determine if multi-select
  const isMultiple = fieldType === 'multi-select' || schema.type === 'array'

  // For multi-select, ensure value is always an array
  const normalizedValue = isMultiple
    ? (Array.isArray(value) ? value : value ? [value] : [])
    : value

  return (
    <Select
      id={name}
      value={normalizedValue as string | string[]}
      placeholder={placeholder}
      disabled={disabled}
      mode={isMultiple ? 'multiple' : undefined}
      showSearch
      allowClear
      optionFilterProp="label"
      style={{ width: '100%' }}
      options={options}
      onChange={(val) => onChange(val)}
    />
  )
}

export default SelectFieldRenderer
