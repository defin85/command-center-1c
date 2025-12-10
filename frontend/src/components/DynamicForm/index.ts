/**
 * DynamicForm Component Public API
 *
 * Exports all public types, components, hooks, and utilities
 * for the JSON Schema-based dynamic form.
 */

// Main component
export { DynamicForm, default } from './DynamicForm'

// Types
export type {
  FieldType,
  ConditionalConfig,
  ExtendedSchemaProperty,
  ValidationError,
  DynamicFormProps,
  FieldRendererProps,
  FieldConfig,
  FileUploadResponse,
  FileUploadOptions,
} from './types'

// Hooks
export { useSchemaValidation } from './hooks/useSchemaValidation'
export type { UseSchemaValidationResult } from './hooks/useSchemaValidation'

export { useConditionalFields, getFieldDependents, getFieldDependencies, buildDependencyGraph } from './hooks/useConditionalFields'
export type { UseConditionalFieldsResult } from './hooks/useConditionalFields'

export { useFieldOrder, groupFieldsBy, groupFieldsBySection, calculateNewOrder } from './hooks/useFieldOrder'
export type { UseFieldOrderResult } from './hooks/useFieldOrder'

// Renderers
export {
  getFieldRenderer,
  registerRenderer,
  unregisterRenderer,
  getAvailableFieldTypes,
  hasRenderer,
  TextFieldRenderer,
  NumberFieldRenderer,
  BooleanFieldRenderer,
  DateFieldRenderer,
  SelectFieldRenderer,
  FileFieldRenderer,
} from './renderers'

// Utils
export {
  inferFieldType,
  parseSchemaProperties,
  formatFieldName,
  getSelectOptions,
  checkConditionalVisibility,
  sortFieldsByOrder,
  getValidationRules,
} from './utils/schemaParser'

export {
  extractDefaults,
  getDefaultValue,
  mergeWithDefaults,
  isEmptyValue,
  cleanValues,
  coerceValues,
} from './utils/defaults'
