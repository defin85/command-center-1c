/**
 * Default Values Utilities
 *
 * Extract default values from JSON Schema properties.
 */

import type { ExtendedSchemaProperty } from '../types'

/**
 * Extract default values from a JSON Schema.
 * Recursively processes nested objects.
 */
export function extractDefaults(
  schema: ExtendedSchemaProperty
): Record<string, unknown> {
  const defaults: Record<string, unknown> = {}

  if (!schema.properties) {
    return defaults
  }

  for (const [name, propSchema] of Object.entries(schema.properties)) {
    const fieldSchema = propSchema as ExtendedSchemaProperty
    const defaultValue = getDefaultValue(fieldSchema)

    if (defaultValue !== undefined) {
      defaults[name] = defaultValue
    }
  }

  return defaults
}

/**
 * Get default value for a single schema property.
 * Handles explicit defaults and type-based defaults.
 */
export function getDefaultValue(
  schema: ExtendedSchemaProperty
): unknown {
  // Explicit default
  if (schema.default !== undefined) {
    return schema.default
  }

  // For nested objects, extract nested defaults
  if (schema.type === 'object' && schema.properties) {
    const nestedDefaults = extractDefaults(schema)
    if (Object.keys(nestedDefaults).length > 0) {
      return nestedDefaults
    }
    return undefined
  }

  // For arrays with default items
  if (schema.type === 'array') {
    // Return empty array as default only if required
    return undefined
  }

  // No default - let field be undefined
  return undefined
}

/**
 * Merge schema defaults with provided values.
 * Provided values take precedence over defaults.
 */
export function mergeWithDefaults(
  schema: ExtendedSchemaProperty,
  values: Record<string, unknown>
): Record<string, unknown> {
  const defaults = extractDefaults(schema)
  return { ...defaults, ...values }
}

/**
 * Check if a value is empty (null, undefined, empty string, or empty array).
 */
export function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true
  }

  if (typeof value === 'string' && value.trim() === '') {
    return true
  }

  if (Array.isArray(value) && value.length === 0) {
    return true
  }

  return false
}

/**
 * Clean values by removing empty entries.
 * Useful before form submission.
 */
export function cleanValues(
  values: Record<string, unknown>
): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(values)) {
    if (!isEmptyValue(value)) {
      // Recursively clean nested objects
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        const cleanedNested = cleanValues(value as Record<string, unknown>)
        if (Object.keys(cleanedNested).length > 0) {
          cleaned[key] = cleanedNested
        }
      } else {
        cleaned[key] = value
      }
    }
  }

  return cleaned
}

/**
 * Convert form values to appropriate types based on schema.
 * Handles type coercion for numbers, booleans, etc.
 */
export function coerceValues(
  schema: ExtendedSchemaProperty,
  values: Record<string, unknown>
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...values }

  if (!schema.properties) {
    return result
  }

  for (const [name, propSchema] of Object.entries(schema.properties)) {
    const fieldSchema = propSchema as ExtendedSchemaProperty
    const value = result[name]

    if (value === undefined || value === null) {
      continue
    }

    const schemaType = Array.isArray(fieldSchema.type)
      ? fieldSchema.type[0]
      : fieldSchema.type

    switch (schemaType) {
      case 'integer':
        if (typeof value === 'string') {
          const parsed = parseInt(value, 10)
          if (!isNaN(parsed)) {
            result[name] = parsed
          } else {
            console.warn(`coerceValues: Failed to parse "${value}" as integer for field "${name}"`)
          }
        }
        break

      case 'number':
        if (typeof value === 'string') {
          const parsed = parseFloat(value)
          if (!isNaN(parsed)) {
            result[name] = parsed
          } else {
            console.warn(`coerceValues: Failed to parse "${value}" as number for field "${name}"`)
          }
        }
        break

      case 'boolean':
        if (typeof value === 'string') {
          result[name] = value === 'true' || value === '1'
        }
        break

      case 'array':
        // Ensure arrays stay as arrays
        if (!Array.isArray(value)) {
          result[name] = [value]
        }
        break
    }
  }

  return result
}
