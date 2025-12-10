/**
 * Schema Parser Utilities
 *
 * Parses JSON Schema into field configurations for DynamicForm rendering.
 */

import type {
  ExtendedSchemaProperty,
  FieldConfig,
  FieldType,
} from '../types'

/**
 * Default field order when x-order is not specified.
 * High value to push unordered fields to the end.
 */
export const DEFAULT_FIELD_ORDER = 999

/**
 * Maximum allowed field name length for safety.
 */
const MAX_FIELD_NAME_LENGTH = 200

/**
 * Infer field type from JSON Schema property.
 * Uses schema type, format, and enum to determine the best field type.
 */
export function inferFieldType(schema: ExtendedSchemaProperty): FieldType {
  // Check for explicit x-field-type first
  if (schema['x-field-type']) {
    return schema['x-field-type']
  }

  // Check for enum - implies select
  if (schema.enum && Array.isArray(schema.enum)) {
    return 'select'
  }

  // Check format for dates
  if (schema.format === 'date') {
    return 'date'
  }
  if (schema.format === 'date-time') {
    return 'datetime'
  }

  // Check format for password
  if (schema.format === 'password') {
    return 'password'
  }

  // Check by type
  const schemaType = Array.isArray(schema.type) ? schema.type[0] : schema.type

  switch (schemaType) {
    case 'string':
      // Check for long text
      if (schema.maxLength && schema.maxLength > 255) {
        return 'textarea'
      }
      return 'text'

    case 'number':
    case 'integer':
      return 'number'

    case 'boolean':
      return 'boolean'

    case 'array':
      // Array of enums -> multi-select
      if (schema.items && (schema.items as ExtendedSchemaProperty).enum) {
        return 'multi-select'
      }
      // Default array handling
      return 'multi-select'

    default:
      return 'text'
  }
}

/**
 * Parse schema properties into field configurations.
 * Extracts all necessary information for rendering.
 */
export function parseSchemaProperties(
  schema: ExtendedSchemaProperty
): FieldConfig[] {
  const properties = schema.properties || {}
  const required = schema.required || []

  const fields: FieldConfig[] = []

  for (const [name, propSchema] of Object.entries(properties)) {
    const fieldSchema = propSchema as ExtendedSchemaProperty

    // Skip read-only fields
    if (fieldSchema.readOnly) {
      continue
    }

    const fieldType = inferFieldType(fieldSchema)

    fields.push({
      name,
      type: fieldType,
      schema: fieldSchema,
      order: fieldSchema['x-order'] ?? DEFAULT_FIELD_ORDER,
      required: required.includes(name),
      label: fieldSchema.title || formatFieldName(name),
      placeholder: fieldSchema['x-placeholder'],
      helpText: fieldSchema['x-help-text'] || fieldSchema.description,
      conditional: fieldSchema['x-conditional'],
    })
  }

  return fields
}

/**
 * Format field name into human-readable label.
 * Converts snake_case and camelCase to Title Case.
 */
export function formatFieldName(name: string): string {
  // Validate input
  if (typeof name !== 'string' || name.length === 0 || name.length > MAX_FIELD_NAME_LENGTH) {
    return 'Unknown Field'
  }

  return name
    // Split on underscores and camelCase
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    // Capitalize first letter of each word
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

/**
 * Get select options from schema enum.
 * Handles both simple enum arrays and oneOf with const values.
 */
export function getSelectOptions(
  schema: ExtendedSchemaProperty
): Array<{ label: string; value: unknown }> {
  // Handle enum array
  if (schema.enum && Array.isArray(schema.enum)) {
    // Check if we have enumNames for labels
    const enumNames = (schema as { enumNames?: string[] }).enumNames

    return schema.enum.map((value, index) => ({
      label: enumNames?.[index] || formatEnumValue(value),
      value,
    }))
  }

  // Handle oneOf with const
  if (schema.oneOf && Array.isArray(schema.oneOf)) {
    return schema.oneOf
      .filter((item) => item && typeof item === 'object' && 'const' in item)
      .map((item) => {
        const constItem = item as { const: unknown; title?: string }
        return {
          label: constItem.title || formatEnumValue(constItem.const),
          value: constItem.const,
        }
      })
  }

  // Handle items enum (for multi-select)
  if (schema.items) {
    const itemsSchema = schema.items as ExtendedSchemaProperty
    if (itemsSchema.enum && Array.isArray(itemsSchema.enum)) {
      const enumNames = (itemsSchema as { enumNames?: string[] }).enumNames

      return itemsSchema.enum.map((value, index) => ({
        label: enumNames?.[index] || formatEnumValue(value),
        value,
      }))
    }
  }

  return []
}

/**
 * Format enum value into human-readable label.
 */
function formatEnumValue(value: unknown): string {
  if (typeof value === 'string') {
    return formatFieldName(value)
  }
  return String(value)
}

/**
 * Check if a field should be visible based on conditional config.
 */
export function checkConditionalVisibility(
  fieldConfig: FieldConfig,
  values: Record<string, unknown>
): boolean {
  const conditional = fieldConfig.conditional
  if (!conditional) {
    return true
  }

  const dependentValue = values[conditional.field]
  const targetValue = conditional.value
  const operator = conditional.operator || 'eq'

  switch (operator) {
    case 'eq':
      return dependentValue === targetValue

    case 'neq':
      return dependentValue !== targetValue

    case 'in':
      if (Array.isArray(targetValue)) {
        return targetValue.includes(dependentValue)
      }
      return false

    case 'nin':
      if (Array.isArray(targetValue)) {
        return !targetValue.includes(dependentValue)
      }
      return true

    default:
      return true
  }
}

/**
 * Sort fields by x-order property.
 */
export function sortFieldsByOrder(fields: FieldConfig[]): FieldConfig[] {
  return [...fields].sort((a, b) => a.order - b.order)
}

/**
 * Get validation rules from schema for Ant Design Form.
 */
export function getValidationRules(
  fieldConfig: FieldConfig
): Array<Record<string, unknown>> {
  const rules: Array<Record<string, unknown>> = []
  const schema = fieldConfig.schema

  // Required rule
  if (fieldConfig.required) {
    rules.push({
      required: true,
      message: `${fieldConfig.label} is required`,
    })
  }

  // String validations
  if (schema.minLength !== undefined) {
    rules.push({
      min: schema.minLength,
      message: `${fieldConfig.label} must be at least ${schema.minLength} characters`,
    })
  }

  if (schema.maxLength !== undefined) {
    rules.push({
      max: schema.maxLength,
      message: `${fieldConfig.label} must be at most ${schema.maxLength} characters`,
    })
  }

  // Pattern validation
  if (schema.pattern) {
    rules.push({
      pattern: new RegExp(schema.pattern),
      message: `${fieldConfig.label} format is invalid`,
    })
  }

  // Number validations
  if (schema.minimum !== undefined) {
    rules.push({
      type: 'number',
      min: schema.minimum,
      message: `${fieldConfig.label} must be at least ${schema.minimum}`,
    })
  }

  if (schema.maximum !== undefined) {
    rules.push({
      type: 'number',
      max: schema.maximum,
      message: `${fieldConfig.label} must be at most ${schema.maximum}`,
    })
  }

  // Email validation
  if (schema.format === 'email') {
    rules.push({
      type: 'email',
      message: `${fieldConfig.label} must be a valid email`,
    })
  }

  // URL validation
  if (schema.format === 'uri' || schema.format === 'url') {
    rules.push({
      type: 'url',
      message: `${fieldConfig.label} must be a valid URL`,
    })
  }

  return rules
}
