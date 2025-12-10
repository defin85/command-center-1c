/**
 * DynamicForm Type Definitions
 *
 * Types for JSON Schema-based dynamic form generation with extended
 * properties for field ordering, conditional visibility, and custom rendering.
 */

import type { JSONSchema7 } from 'json-schema'

/**
 * Supported field types for rendering.
 * Maps to specific Ant Design components.
 */
export type FieldType =
  | 'text'
  | 'textarea'
  | 'password'
  | 'number'
  | 'boolean'
  | 'date'
  | 'datetime'
  | 'select'
  | 'multi-select'
  | 'file'

/**
 * Conditional visibility configuration.
 * Controls when a field should be shown based on another field's value.
 */
export interface ConditionalConfig {
  /** Name of the field to check */
  field: string
  /** Value(s) to compare against */
  value: unknown
  /** Comparison operator (default: 'eq') */
  operator?: 'eq' | 'neq' | 'in' | 'nin'
}

/**
 * Extended JSON Schema property with custom extensions.
 * Extends standard JSON Schema 7 with x-* properties for form rendering.
 */
export interface ExtendedSchemaProperty extends JSONSchema7 {
  /** Explicit field type override (auto-inferred if not set) */
  'x-field-type'?: FieldType
  /** Field order (lower values come first) */
  'x-order'?: number
  /** Placeholder text for input fields */
  'x-placeholder'?: string
  /** Help text displayed below the field */
  'x-help-text'?: string
  /** Conditional visibility configuration */
  'x-conditional'?: ConditionalConfig
  /** Accepted file types for file fields (e.g., '.pdf,.doc') */
  'x-file-accept'?: string
  /** Maximum file size in bytes */
  'x-file-max-size'?: number
  /** Field this depends on (for cascading selects) */
  'x-depends-on'?: string
  /** Custom component to use (for registry extension) */
  'x-component'?: string
  /** Nested properties (for object types) */
  properties?: Record<string, ExtendedSchemaProperty>
  /** Items schema (for array types) */
  items?: ExtendedSchemaProperty
}

/**
 * Validation error returned by schema validation.
 */
export interface ValidationError {
  /** Field path (dot-separated for nested fields) */
  field: string
  /** Human-readable error message */
  message: string
  /** Error code from Ajv (e.g., 'required', 'minLength') */
  code: string
}

/**
 * Props for the main DynamicForm component.
 */
export interface DynamicFormProps {
  /** JSON Schema with extended properties */
  schema: ExtendedSchemaProperty
  /** Current form values */
  values: Record<string, unknown>
  /** Callback when any value changes */
  onChange: (values: Record<string, unknown>) => void
  /** Callback when validation errors occur */
  onValidationError?: (errors: ValidationError[]) => void
  /** Map of field names to uploaded file IDs */
  uploadedFiles?: Record<string, string>
  /** Callback when a file is uploaded */
  onFileUpload?: (fieldName: string, fileId: string) => void
  /** Callback when a file is removed */
  onFileRemove?: (fieldName: string) => void
  /** Disable all form fields */
  disabled?: boolean
  /** Form layout direction */
  layout?: 'horizontal' | 'vertical'
  /** Custom label column span (for horizontal layout) */
  labelCol?: { span: number }
  /** Custom wrapper column span (for horizontal layout) */
  wrapperCol?: { span: number }
}

/**
 * Props passed to individual field renderers.
 */
export interface FieldRendererProps {
  /** Field name (used as form field key) */
  name: string
  /** Field schema with extended properties */
  schema: ExtendedSchemaProperty
  /** Current field value */
  value: unknown
  /** Callback when value changes */
  onChange: (value: unknown) => void
  /** Whether the field is disabled */
  disabled?: boolean
  /** Validation error message */
  error?: string
  /** Uploaded file ID (for file fields) */
  uploadedFileId?: string
  /** File upload callback (for file fields) */
  onFileUpload?: (fileId: string) => void
  /** File remove callback (for file fields) */
  onFileRemove?: () => void
}

/**
 * Field configuration parsed from schema.
 * Used internally by DynamicForm to render fields.
 */
export interface FieldConfig {
  /** Field name */
  name: string
  /** Parsed field type */
  type: FieldType
  /** Field schema */
  schema: ExtendedSchemaProperty
  /** Render order */
  order: number
  /** Whether field is required */
  required: boolean
  /** Field label (from title or name) */
  label: string
  /** Placeholder text */
  placeholder?: string
  /** Help text */
  helpText?: string
  /** Conditional visibility config */
  conditional?: ConditionalConfig
}

// Re-export file types from files API to avoid duplication
export type { FileUploadResponse } from '../../api/files'

/**
 * File upload options.
 */
export interface FileUploadOptions {
  /** Purpose/category of the file */
  purpose: string
  /** Hours until file expires (optional) */
  expiryHours?: number
}
