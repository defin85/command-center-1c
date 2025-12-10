/**
 * Hook for fetching workflow templates from the backend.
 * Used by Operations Wizard to load custom templates.
 */

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'

/**
 * Options for filtering workflow templates
 */
export interface UseWorkflowTemplatesOptions {
  /** Filter by template status (is_template=true for custom templates) */
  is_template?: boolean
  /** Filter by category */
  category?: string
  /** Search by name/description */
  search?: string
  /** Only fetch active templates */
  is_active?: boolean
}

/**
 * Workflow template from the backend
 */
export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  icon: string
  category: string
  input_schema: Record<string, unknown> | null
  is_active: boolean
  is_template: boolean
  created_at: string
  updated_at: string
}

/**
 * API response structure for list-templates
 */
interface ListTemplatesResponse {
  success: boolean
  data: {
    templates: WorkflowTemplate[]
    count: number
  }
}

/**
 * Result returned by useWorkflowTemplates hook
 */
export interface UseWorkflowTemplatesResult {
  templates: WorkflowTemplate[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Hook for fetching workflow templates.
 *
 * @param options - Filter options
 * @returns Templates list with loading/error states
 *
 * @example
 * ```tsx
 * const { templates, loading } = useWorkflowTemplates({ is_template: true })
 * ```
 */
export function useWorkflowTemplates(
  options: UseWorkflowTemplatesOptions = {}
): UseWorkflowTemplatesResult {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Refetch function for external use
  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      // Build query params
      const params = new URLSearchParams()
      if (options.is_template !== undefined) {
        params.append('is_template', String(options.is_template))
      }
      if (options.category) {
        params.append('category', options.category)
      }
      if (options.search) {
        params.append('search', options.search)
      }
      if (options.is_active !== undefined) {
        params.append('is_active', String(options.is_active))
      }

      const queryString = params.toString()
      const url = `/api/v2/workflows/list-templates/${queryString ? `?${queryString}` : ''}`

      const response = await apiClient.get<ListTemplatesResponse>(url)

      if (response.data.success) {
        setTemplates(response.data.data.templates)
      } else {
        setError('Failed to load templates')
        setTemplates([])
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load templates'
      setError(errorMessage)
      setTemplates([])
      console.error('Failed to fetch workflow templates:', err)
    } finally {
      setLoading(false)
    }
  }, [options.is_template, options.category, options.search, options.is_active])

  // Fetch on mount and when options change with cleanup for race condition
  useEffect(() => {
    let cancelled = false

    const doFetch = async () => {
      setLoading(true)
      setError(null)

      try {
        // Build query params
        const params = new URLSearchParams()
        if (options.is_template !== undefined) {
          params.append('is_template', String(options.is_template))
        }
        if (options.category) {
          params.append('category', options.category)
        }
        if (options.search) {
          params.append('search', options.search)
        }
        if (options.is_active !== undefined) {
          params.append('is_active', String(options.is_active))
        }

        const queryString = params.toString()
        const url = `/api/v2/workflows/list-templates/${queryString ? `?${queryString}` : ''}`

        const response = await apiClient.get<ListTemplatesResponse>(url)

        if (cancelled) return

        if (response.data.success) {
          setTemplates(response.data.data.templates)
        } else {
          setError('Failed to load templates')
          setTemplates([])
        }
      } catch (err) {
        if (cancelled) return
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load templates'
        setError(errorMessage)
        setTemplates([])
        console.error('Failed to fetch workflow templates:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    doFetch()
    return () => { cancelled = true }
  }, [options.is_template, options.category, options.search, options.is_active])

  return {
    templates,
    loading,
    error,
    refetch,
  }
}

export default useWorkflowTemplates
