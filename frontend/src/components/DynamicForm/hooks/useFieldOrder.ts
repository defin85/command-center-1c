/**
 * useFieldOrder Hook
 *
 * Sorts and organizes fields based on x-order property.
 * Returns sorted field configurations.
 */

import { useMemo } from 'react'
import type { ExtendedSchemaProperty, FieldConfig } from '../types'
import { parseSchemaProperties, sortFieldsByOrder } from '../utils/schemaParser'

export interface UseFieldOrderResult {
  /** Sorted array of field configurations */
  fields: FieldConfig[]
  /** Get field config by name */
  getField: (name: string) => FieldConfig | undefined
  /** Total number of fields */
  fieldCount: number
}

/**
 * Hook for parsing and ordering schema fields.
 *
 * @param schema - JSON Schema with extended properties
 * @returns Sorted field configurations and helpers
 *
 * @example
 * ```tsx
 * const { fields, getField } = useFieldOrder(schema)
 *
 * // Render fields in order
 * {fields.map(field => (
 *   <FieldRenderer key={field.name} {...field} />
 * ))}
 *
 * // Get specific field
 * const nameField = getField('name')
 * ```
 */
export function useFieldOrder(
  schema: ExtendedSchemaProperty
): UseFieldOrderResult {
  // Parse and sort fields
  const fields = useMemo(() => {
    const parsed = parseSchemaProperties(schema)
    return sortFieldsByOrder(parsed)
  }, [schema])

  // Create lookup map for quick access
  const fieldMap = useMemo(() => {
    const map = new Map<string, FieldConfig>()
    for (const field of fields) {
      map.set(field.name, field)
    }
    return map
  }, [fields])

  // Get field by name
  const getField = useMemo(
    () => (name: string): FieldConfig | undefined => {
      return fieldMap.get(name)
    },
    [fieldMap]
  )

  return {
    fields,
    getField,
    fieldCount: fields.length,
  }
}

/**
 * Group fields by a custom grouping function.
 * Useful for creating field sections.
 */
export function groupFieldsBy<K>(
  fields: FieldConfig[],
  keyFn: (field: FieldConfig) => K
): Map<K, FieldConfig[]> {
  const groups = new Map<K, FieldConfig[]>()

  for (const field of fields) {
    const key = keyFn(field)
    const existing = groups.get(key) || []
    existing.push(field)
    groups.set(key, existing)
  }

  return groups
}

/**
 * Group fields by order ranges (for creating sections).
 * Fields with order 0-99 go to first section, 100-199 to second, etc.
 */
export function groupFieldsBySection(
  fields: FieldConfig[],
  sectionSize: number = 100
): FieldConfig[][] {
  const sections = new Map<number, FieldConfig[]>()

  for (const field of fields) {
    const sectionIndex = Math.floor(field.order / sectionSize)
    const existing = sections.get(sectionIndex) || []
    existing.push(field)
    sections.set(sectionIndex, existing)
  }

  // Convert to sorted array of arrays
  const sortedKeys = Array.from(sections.keys()).sort((a, b) => a - b)
  return sortedKeys.map((key) => sections.get(key) || [])
}

/**
 * Reorder fields by moving one field before/after another.
 * Returns new order values.
 */
export function calculateNewOrder(
  fields: FieldConfig[],
  sourceIndex: number,
  targetIndex: number
): Map<string, number> {
  const reordered = [...fields]
  const [moved] = reordered.splice(sourceIndex, 1)
  reordered.splice(targetIndex, 0, moved)

  const newOrders = new Map<string, number>()
  reordered.forEach((field, index) => {
    newOrders.set(field.name, index * 10) // Use multiples of 10 for flexibility
  })

  return newOrders
}

export default useFieldOrder
