/**
 * useSchemaValidation Hook
 *
 * Provides JSON Schema validation using Ajv library.
 * Returns validate function and errors state.
 */

import { useCallback, useMemo, useState } from 'react'
import Ajv from 'ajv'
import addFormats from 'ajv-formats'
import type { ExtendedSchemaProperty, ValidationError } from '../types'

/**
 * Custom error messages for common validation errors.
 */
const ERROR_MESSAGES: Record<string, (params: Record<string, unknown>) => string> = {
  required: () => 'This field is required',
  minLength: (params) => `Must be at least ${params.limit} characters`,
  maxLength: (params) => `Must be at most ${params.limit} characters`,
  minimum: (params) => `Must be at least ${params.limit}`,
  maximum: (params) => `Must be at most ${params.limit}`,
  pattern: () => 'Invalid format',
  format: (params) => `Must be a valid ${params.format}`,
  enum: () => 'Must be one of the allowed values',
  type: (params) => `Must be ${params.type}`,
}

/**
 * Convert Ajv error to ValidationError format.
 */
function formatAjvError(error: {
  keyword: string
  instancePath: string
  params: Record<string, unknown>
  message?: string
}): ValidationError {
  const field = error.instancePath
    ? error.instancePath.replace(/^\//, '').replace(/\//g, '.')
    : (error.params.missingProperty as string) || 'unknown'

  const messageFormatter = ERROR_MESSAGES[error.keyword]
  const message = messageFormatter
    ? messageFormatter(error.params)
    : error.message || 'Validation failed'

  return {
    field,
    message,
    code: error.keyword,
  }
}

export interface UseSchemaValidationResult {
  /** Validate values against schema */
  validate: (values: Record<string, unknown>) => boolean
  /** Current validation errors */
  errors: ValidationError[]
  /** Map of field names to error messages */
  errorMap: Record<string, string>
  /** Clear all errors */
  clearErrors: () => void
  /** Get error for specific field */
  getFieldError: (fieldName: string) => string | undefined
  /** Schema compilation error (if schema is invalid) */
  schemaError: string | null
}

/**
 * Hook for JSON Schema validation.
 *
 * @param schema - JSON Schema to validate against
 * @returns Validation functions and error state
 */
export function useSchemaValidation(
  schema: ExtendedSchemaProperty
): UseSchemaValidationResult {
  const [errors, setErrors] = useState<ValidationError[]>([])
  const [schemaError, setSchemaError] = useState<string | null>(null)

  // Create Ajv instance with formats
  const ajv = useMemo(() => {
    const instance = new Ajv({
      allErrors: true,
      verbose: true,
      strict: false,
    })
    addFormats(instance)
    return instance
  }, [])

  // Compile schema validator
  const validateFn = useMemo(() => {
    try {
      setSchemaError(null)
      return ajv.compile(schema)
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e)
      console.error('Failed to compile schema:', e)
      setSchemaError(`Invalid schema: ${errorMessage}`)
      return null
    }
  }, [ajv, schema])

  // Validate function
  const validate = useCallback(
    (values: Record<string, unknown>): boolean => {
      if (!validateFn) {
        console.warn('Schema validator not available')
        return true
      }

      const isValid = validateFn(values)

      if (!isValid && validateFn.errors) {
        const formattedErrors = validateFn.errors.map(formatAjvError)
        setErrors(formattedErrors)
        return false
      }

      setErrors([])
      return true
    },
    [validateFn]
  )

  // Clear errors
  const clearErrors = useCallback(() => {
    setErrors([])
  }, [])

  // Create error map for quick field lookup
  const errorMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const error of errors) {
      // Only keep first error per field
      if (!map[error.field]) {
        map[error.field] = error.message
      }
    }
    return map
  }, [errors])

  // Get error for specific field
  const getFieldError = useCallback(
    (fieldName: string): string | undefined => {
      return errorMap[fieldName]
    },
    [errorMap]
  )

  return {
    validate,
    errors,
    errorMap,
    clearErrors,
    getFieldError,
    schemaError,
  }
}

export default useSchemaValidation
