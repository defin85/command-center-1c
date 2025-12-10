/**
 * TextFieldRenderer Component
 *
 * Renders text, textarea, and password input fields.
 */

import { Input } from 'antd'
import type { FieldRendererProps } from '../types'

const { TextArea, Password } = Input

/**
 * Renderer for text-based fields.
 * Supports: text, textarea, password
 */
export function TextFieldRenderer({
  name,
  schema,
  value,
  onChange,
  disabled,
}: FieldRendererProps) {
  const placeholder = schema['x-placeholder'] || schema.title
  const maxLength = schema.maxLength
  const fieldType = schema['x-field-type']

  // Handle textarea
  if (fieldType === 'textarea') {
    return (
      <TextArea
        id={name}
        value={value as string}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        showCount={!!maxLength}
        autoSize={{ minRows: 3, maxRows: 6 }}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }

  // Handle password
  if (fieldType === 'password' || schema.format === 'password') {
    return (
      <Password
        id={name}
        value={value as string}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  }

  // Default text input
  return (
    <Input
      id={name}
      value={value as string}
      placeholder={placeholder}
      disabled={disabled}
      maxLength={maxLength}
      showCount={!!maxLength}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

export default TextFieldRenderer
