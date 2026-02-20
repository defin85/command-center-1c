/**
 * Operations data fetching with React Query.
 *
 * Provides hooks for:
 * - useOperations() - list with auto-polling
 * - useOperation(id) - single operation details
 * - useCancelOperation() - mutation to cancel operation
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { OperationListResponse } from '../generated/model/operationListResponse'
import { transformBatchOperation, transformTask } from '../../utils/operationTransforms'
import type { UIBatchOperation } from '../../utils/operationTransforms'

import { queryKeys } from './queryKeys'
import type { OperationFilters } from './types'

const api = getV2()

// =============================================================================
// Fetch Functions
// =============================================================================

/**
 * Fetch operations list from API.
 * Transforms results to UI format.
 */
export interface OperationListResult {
  operations: UIBatchOperation[]
  count: number
  total: number
}

export async function fetchOperations(
  filters?: OperationFilters,
  signal?: AbortSignal
): Promise<OperationListResult> {
  const filtersParam = filters?.filters ? JSON.stringify(filters.filters) : undefined
  const sortParam = filters?.sort ? JSON.stringify(filters.sort) : undefined
  const response: OperationListResponse = await api.getOperationsListOperations(
    {
      operation_id: filters?.operation_id,
      created_by: filters?.created_by,
      operation_type: filters?.operation_type,
      workflow_execution_id: filters?.workflow_execution_id,
      node_id: filters?.node_id,
      root_operation_id: filters?.root_operation_id,
      execution_consumer: filters?.execution_consumer,
      lane: filters?.lane,
      status: filters?.status,
      search: filters?.search,
      filters: filtersParam,
      sort: sortParam,
      limit: filters?.limit,
      offset: filters?.offset,
    },
    { signal }
  )
  return {
    ...response,
    operations: response.operations.map(transformBatchOperation),
  }
}

/**
 * Fetch single operation by ID.
 */
export interface TaskQueryParams {
  limit?: number
  offset?: number
  filters?: Record<string, { op?: string; value?: unknown } | unknown>
  sort?: { key: string; order: 'asc' | 'desc' }
}

export async function fetchOperation(
  id: string,
  taskParams?: TaskQueryParams,
  signal?: AbortSignal
): Promise<UIBatchOperation> {
  const filtersParam = taskParams?.filters ? JSON.stringify(taskParams.filters) : undefined
  const sortParam = taskParams?.sort ? JSON.stringify(taskParams.sort) : undefined
  const response = await api.getOperationsGetOperation(
    {
      operation_id: id,
      include_tasks: true,
      task_limit: taskParams?.limit,
      task_offset: taskParams?.offset,
      task_filters: filtersParam,
      task_sort: sortParam,
    },
    { signal }
  )
  const operation = transformBatchOperation(response.operation)
  const executionPlan = (response as unknown as { execution_plan?: unknown }).execution_plan
  const bindings = (response as unknown as { bindings?: unknown }).bindings
  return {
    ...operation,
    tasks: response.tasks ? response.tasks.map(transformTask) : operation.tasks,
    execution_plan: executionPlan,
    bindings,
  }
}

/**
 * Cancel operation by ID.
 */
export async function cancelOperation(operationId: string): Promise<void> {
  await api.postOperationsCancelOperation({
    operation_id: operationId,
  })
}

// =============================================================================
// React Query Hooks
// =============================================================================

export interface UseOperationsOptions {
  /** Filters for operations list */
  filters?: OperationFilters
  /** Refetch interval in milliseconds (default: 5000) */
  refetchInterval?: number
  /** Enable/disable the query */
  enabled?: boolean
}

/**
 * React Query hook for operations list with polling.
 *
 * Features:
 * - Auto-refetch every 5 seconds (configurable)
 * - Automatic AbortController handling
 * - Caching and background updates
 */
export function useOperations(options: UseOperationsOptions = {}) {
  const { filters, refetchInterval = 5000, enabled = true } = options

  return useQuery({
    queryKey: queryKeys.operations.list(filters),
    queryFn: ({ signal }) => fetchOperations(filters, signal),
    refetchInterval,
    enabled,
    // Keep previous data while refetching (prevents loading flicker)
    placeholderData: (previousData) => previousData,
    // Retry failed requests once
    retry: 1,
    // Don't refetch on window focus (we have interval)
    refetchOnWindowFocus: false,
  })
}

export interface UseOperationOptions {
  /** Enable/disable the query */
  enabled?: boolean
  /** Refetch interval in milliseconds (default: none) */
  refetchInterval?: number
  /** Task query params */
  taskParams?: TaskQueryParams
}

/**
 * React Query hook for single operation details.
 */
export function useOperation(id: string, options: UseOperationOptions = {}) {
  const { enabled = true, refetchInterval, taskParams } = options

  return useQuery({
    queryKey: [...queryKeys.operations.detail(id), taskParams],
    queryFn: ({ signal }) => fetchOperation(id, taskParams, signal),
    enabled: enabled && !!id,
    refetchInterval,
    retry: 1,
  })
}

/**
 * React Query mutation hook for cancelling an operation.
 *
 * Automatically invalidates operations queries on success.
 */
export function useCancelOperation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: cancelOperation,
    onSuccess: () => {
      // Invalidate operations queries to trigger refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.operations.all })
    },
  })
}
