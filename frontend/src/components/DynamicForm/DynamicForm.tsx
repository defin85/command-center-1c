/**
 * DynamicForm Component
 *
 * Renders a form dynamically from JSON Schema with extended properties.
 * Supports validation, conditional fields, and custom renderers.
 */

import { useCallback, useEffect } from 'react'
import { Form, Typography } from 'antd'
import type { DynamicFormProps, FieldConfig } from './types'
import { useSchemaValidation } from './hooks/useSchemaValidation'
import { useConditionalFields } from './hooks/useConditionalFields'
import { useFieldOrder } from './hooks/useFieldOrder'
import { getFieldRenderer } from './renderers'
import { getValidationRules } from './utils/schemaParser'

const { Text } = Typography

/**
 * DynamicForm - Main component for rendering JSON Schema-based forms.
 *
 * Features:
 * - Automatic field type inference from schema
 * - JSON Schema validation with Ajv
 * - Conditional field visibility (x-conditional)
 * - Custom field ordering (x-order)
 * - File upload support
 * - Ant Design integration
 *
 * @example
 * ```tsx
 * const schema = {
 *   type: 'object',
 *   properties: {
 *     name: { type: 'string', title: 'Name', 'x-order': 1 },
 *     email: { type: 'string', format: 'email', title: 'Email', 'x-order': 2 },
 *     type: { type: 'string', enum: ['user', 'admin'], title: 'Type', 'x-order': 3 },
 *     department: {
 *       type: 'string',
 *       title: 'Department',
 *       'x-order': 4,
 *       'x-conditional': { field: 'type', value: 'admin' }
 *     }
 *   },
 *   required: ['name', 'email']
 * }
 *
 * <DynamicForm
 *   schema={schema}
 *   values={formValues}
 *   onChange={setFormValues}
 *   onValidationError={handleErrors}
 * />
 * ```
 */
export function DynamicForm({
  schema,
  values,
  onChange,
  onValidationError,
  uploadedFiles = {},
  onFileUpload,
  onFileRemove,
  disabled = false,
  layout = 'vertical',
  labelCol,
  wrapperCol,
}: DynamicFormProps) {
  // Parse and order fields
  const { fields } = useFieldOrder(schema)

  // Conditional visibility
  const { getVisibleFields } = useConditionalFields(values)

  // Validation
  const { getFieldError, errors, clearErrors } = useSchemaValidation(schema)

  // Get visible fields
  const visibleFields = getVisibleFields(fields)

  // Notify parent of validation errors (including when errors are cleared)
  useEffect(() => {
    onValidationError?.(errors)
  }, [errors, onValidationError])

  /**
   * Handle field value change.
   */
  const handleFieldChange = useCallback(
    (fieldName: string, value: unknown) => {
      const newValues = { ...values, [fieldName]: value }
      onChange(newValues)

      // Clear errors when field changes
      clearErrors()
    },
    [values, onChange, clearErrors]
  )

  /**
   * Handle file upload for a field.
   */
  const handleFileUpload = useCallback(
    (fieldName: string, fileId: string) => {
      onFileUpload?.(fieldName, fileId)
    },
    [onFileUpload]
  )

  /**
   * Handle file removal for a field.
   */
  const handleFileRemove = useCallback(
    (fieldName: string) => {
      onFileRemove?.(fieldName)
    },
    [onFileRemove]
  )

  /**
   * Render a single field.
   */
  const renderField = (fieldConfig: FieldConfig) => {
    const { name, schema: fieldSchema, label, helpText, required } = fieldConfig

    // Get renderer component
    const FieldRenderer = getFieldRenderer(fieldSchema)

    // Get validation rules
    const rules = getValidationRules(fieldConfig)

    // Get error
    const error = getFieldError(name)

    return (
      <Form.Item
        key={name}
        label={label}
        name={name}
        rules={rules}
        required={required}
        help={error || helpText}
        validateStatus={error ? 'error' : undefined}
      >
        <FieldRenderer
          name={name}
          schema={fieldSchema}
          value={values[name]}
          onChange={(value) => handleFieldChange(name, value)}
          disabled={disabled}
          error={error}
          uploadedFileId={uploadedFiles[name]}
          onFileUpload={(fileId) => handleFileUpload(name, fileId)}
          onFileRemove={() => handleFileRemove(name)}
        />
      </Form.Item>
    )
  }

  // No fields to render
  if (visibleFields.length === 0) {
    return (
      <Text type="secondary">No fields to display</Text>
    )
  }

  return (
    <Form
      layout={layout}
      labelCol={layout === 'horizontal' ? labelCol || { span: 6 } : undefined}
      wrapperCol={layout === 'horizontal' ? wrapperCol || { span: 18 } : undefined}
      disabled={disabled}
    >
      {visibleFields.map(renderField)}
    </Form>
  )
}

export default DynamicForm
