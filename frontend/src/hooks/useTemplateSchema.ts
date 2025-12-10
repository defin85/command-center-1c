/**
 * Hook for fetching a workflow template's input schema.
 * Used by Operations Wizard to load schema for DynamicForm.
 */

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'
import type { ExtendedSchemaProperty } from '../components/DynamicForm/types'

/**
 * API response structure for get-template-schema
 */
interface GetTemplateSchemaResponse {
  success: boolean
  data: {
    workflow_id: string
    name: string
    input_schema: ExtendedSchemaProperty | null
  }
}

/**
 * Result returned by useTemplateSchema hook
 */
export interface UseTemplateSchemaResult {
  schema: ExtendedSchemaProperty | null
  workflowName: string | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Hook for fetching a workflow template's input schema.
 * Only fetches when templateId is provided (not null).
 *
 * @param templateId - UUID of the workflow template, or null to skip fetching
 * @returns Schema with loading/error states
 *
 * @example
 * ```tsx
 * const { schema, loading } = useTemplateSchema(selectedTemplateId)
 *
 * // Schema is null until templateId is set
 * if (templateId && schema) {
 *   return <DynamicForm schema={schema} ... />
 * }
 * ```
 */
export function useTemplateSchema(
  templateId: string | null
): UseTemplateSchemaResult {
  const [schema, setSchema] = useState<ExtendedSchemaProperty | null>(null)
  const [workflowName, setWorkflowName] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Refetch function for external use
  const refetch = useCallback(async () => {
    if (!templateId) return

    setLoading(true)
    setError(null)

    try {
      const url = `/api/v2/workflows/get-template-schema/?workflow_id=${encodeURIComponent(templateId)}`
      const response = await apiClient.get<GetTemplateSchemaResponse>(url)

      if (response.data.success) {
        const { input_schema, name } = response.data.data
        setSchema(input_schema)
        setWorkflowName(name)
      } else {
        setError('Failed to load template schema')
        setSchema(null)
        setWorkflowName(null)
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load template schema'
      setError(errorMessage)
      setSchema(null)
      setWorkflowName(null)
      console.error('Failed to fetch template schema:', err)
    } finally {
      setLoading(false)
    }
  }, [templateId])

  // Fetch when templateId changes with cleanup for race condition
  useEffect(() => {
    let cancelled = false

    const doFetch = async () => {
      // Skip fetch if no template ID
      if (!templateId) {
        setSchema(null)
        setWorkflowName(null)
        setLoading(false)
        setError(null)
        return
      }

      setLoading(true)
      setError(null)

      try {
        const url = `/api/v2/workflows/get-template-schema/?workflow_id=${encodeURIComponent(templateId)}`
        const response = await apiClient.get<GetTemplateSchemaResponse>(url)

        if (cancelled) return

        if (response.data.success) {
          const { input_schema, name } = response.data.data
          setSchema(input_schema)
          setWorkflowName(name)
        } else {
          setError('Failed to load template schema')
          setSchema(null)
          setWorkflowName(null)
        }
      } catch (err) {
        if (cancelled) return
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load template schema'
        setError(errorMessage)
        setSchema(null)
        setWorkflowName(null)
        console.error('Failed to fetch template schema:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    doFetch()
    return () => { cancelled = true }
  }, [templateId])

  return {
    schema,
    workflowName,
    loading,
    error,
    refetch,
  }
}

export default useTemplateSchema
