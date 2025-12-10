/**
 * Field Renderer Registry
 *
 * Maps field types to their respective renderer components.
 * Provides utility function to get appropriate renderer.
 */

import type { FC } from 'react'
import type { ExtendedSchemaProperty, FieldRendererProps, FieldType } from '../types'
import { inferFieldType } from '../utils/schemaParser'

// Import all renderers
import { TextFieldRenderer } from './TextFieldRenderer'
import { NumberFieldRenderer } from './NumberFieldRenderer'
import { BooleanFieldRenderer } from './BooleanFieldRenderer'
import { DateFieldRenderer } from './DateFieldRenderer'
import { SelectFieldRenderer } from './SelectFieldRenderer'
import { FileFieldRenderer } from './FileFieldRenderer'

/**
 * Map of field types to renderer components.
 */
const RENDERER_MAP: Record<FieldType, FC<FieldRendererProps>> = {
  text: TextFieldRenderer,
  textarea: TextFieldRenderer,
  password: TextFieldRenderer,
  number: NumberFieldRenderer,
  boolean: BooleanFieldRenderer,
  date: DateFieldRenderer,
  datetime: DateFieldRenderer,
  select: SelectFieldRenderer,
  'multi-select': SelectFieldRenderer,
  file: FileFieldRenderer,
}

/**
 * Custom renderer registry for extending default renderers.
 */
const customRenderers = new Map<string, FC<FieldRendererProps>>()

/**
 * Register a custom renderer for a specific component name.
 * Use with x-component schema property.
 *
 * @example
 * ```ts
 * registerRenderer('custom-color-picker', ColorPickerRenderer)
 * ```
 */
export function registerRenderer(
  componentName: string,
  renderer: FC<FieldRendererProps>
): void {
  customRenderers.set(componentName, renderer)
}

/**
 * Unregister a custom renderer.
 */
export function unregisterRenderer(componentName: string): void {
  customRenderers.delete(componentName)
}

/**
 * Get the appropriate renderer for a schema property.
 *
 * Priority:
 * 1. Custom renderer (x-component)
 * 2. Explicit field type (x-field-type)
 * 3. Inferred type from schema
 *
 * @param schema - Schema property to render
 * @returns Renderer component
 */
export function getFieldRenderer(
  schema: ExtendedSchemaProperty
): FC<FieldRendererProps> {
  // Check for custom component first
  const customComponent = schema['x-component']
  if (customComponent) {
    const customRenderer = customRenderers.get(customComponent)
    if (customRenderer) {
      return customRenderer
    }
  }

  // Get field type (explicit or inferred)
  const fieldType = inferFieldType(schema)

  // Return matching renderer or default to text
  return RENDERER_MAP[fieldType] || TextFieldRenderer
}

/**
 * Get all available field types.
 */
export function getAvailableFieldTypes(): FieldType[] {
  return Object.keys(RENDERER_MAP) as FieldType[]
}

/**
 * Check if a field type has a renderer.
 */
export function hasRenderer(fieldType: FieldType): boolean {
  return fieldType in RENDERER_MAP
}

// Re-export all renderers
export { TextFieldRenderer }
export { NumberFieldRenderer }
export { BooleanFieldRenderer }
export { DateFieldRenderer }
export { SelectFieldRenderer }
export { FileFieldRenderer }
