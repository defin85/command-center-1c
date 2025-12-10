/**
 * useConditionalFields Hook
 *
 * Manages conditional field visibility based on x-conditional configuration.
 * Supports eq, neq, in, nin operators.
 */

import { useCallback } from 'react'
import type { ConditionalConfig, FieldConfig } from '../types'

export interface UseConditionalFieldsResult {
  /** Check if a field should be visible */
  isFieldVisible: (fieldConfig: FieldConfig) => boolean
  /** Get all visible fields */
  getVisibleFields: (fields: FieldConfig[]) => FieldConfig[]
}

/**
 * Evaluate conditional visibility for a field.
 */
function evaluateCondition(
  conditional: ConditionalConfig,
  values: Record<string, unknown>
): boolean {
  const dependentValue = values[conditional.field]
  const targetValue = conditional.value
  const operator = conditional.operator || 'eq'

  switch (operator) {
    case 'eq':
      // Strict equality
      return dependentValue === targetValue

    case 'neq':
      // Not equal
      return dependentValue !== targetValue

    case 'in':
      // Value is in target array
      if (Array.isArray(targetValue)) {
        return targetValue.includes(dependentValue)
      }
      // If target is not array, treat as eq
      return dependentValue === targetValue

    case 'nin':
      // Value is NOT in target array
      if (Array.isArray(targetValue)) {
        return !targetValue.includes(dependentValue)
      }
      // If target is not array, treat as neq
      return dependentValue !== targetValue

    default:
      // Unknown operator - show field by default
      console.warn(`Unknown conditional operator: ${operator}`)
      return true
  }
}

/**
 * Hook for managing conditional field visibility.
 *
 * @param values - Current form values
 * @returns Functions for checking and filtering field visibility
 *
 * @example
 * ```tsx
 * const { isFieldVisible, getVisibleFields } = useConditionalFields(formValues)
 *
 * // Check single field
 * if (isFieldVisible(fieldConfig)) {
 *   // render field
 * }
 *
 * // Filter all fields
 * const visibleFields = getVisibleFields(allFields)
 * ```
 */
export function useConditionalFields(
  values: Record<string, unknown>
): UseConditionalFieldsResult {
  /**
   * Check if a single field should be visible.
   */
  const isFieldVisible = useCallback(
    (fieldConfig: FieldConfig): boolean => {
      // No conditional - always visible
      if (!fieldConfig.conditional) {
        return true
      }

      return evaluateCondition(fieldConfig.conditional, values)
    },
    [values]
  )

  /**
   * Filter fields to only return visible ones.
   */
  const getVisibleFields = useCallback(
    (fields: FieldConfig[]): FieldConfig[] => {
      return fields.filter((field) => isFieldVisible(field))
    },
    [isFieldVisible]
  )

  return {
    isFieldVisible,
    getVisibleFields,
  }
}

/**
 * Check if any field depends on the given field.
 * Useful for determining if changing a value might hide/show other fields.
 */
export function getFieldDependents(
  fieldName: string,
  fields: FieldConfig[]
): string[] {
  return fields
    .filter((f) => f.conditional?.field === fieldName)
    .map((f) => f.name)
}

/**
 * Get the dependency chain for a field.
 * Returns all fields that this field depends on (directly and indirectly).
 */
export function getFieldDependencies(
  fieldName: string,
  fields: FieldConfig[]
): string[] {
  const dependencies: Set<string> = new Set()
  const visited: Set<string> = new Set()

  function traverse(name: string) {
    if (visited.has(name)) return
    visited.add(name)

    const field = fields.find((f) => f.name === name)
    if (field?.conditional?.field) {
      dependencies.add(field.conditional.field)
      traverse(field.conditional.field)
    }
  }

  traverse(fieldName)
  return Array.from(dependencies)
}

/**
 * Build a dependency graph for all fields.
 * Returns a map of field name -> fields that depend on it.
 */
export function buildDependencyGraph(
  fields: FieldConfig[]
): Map<string, string[]> {
  const graph = new Map<string, string[]>()

  for (const field of fields) {
    if (field.conditional?.field) {
      const dependsOn = field.conditional.field
      const existing = graph.get(dependsOn) || []
      existing.push(field.name)
      graph.set(dependsOn, existing)
    }
  }

  return graph
}

export default useConditionalFields
