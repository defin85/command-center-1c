/**
 * Operations data fetching with React Query.
 *
 * Provides hooks for:
 * - useOperations() - list with auto-polling
 * - useOperation(id) - single operation details
 * - useCancelOperation() - mutation to cancel operation
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '../client'
import type { BatchOperation } from '../generated/model/batchOperation'
import { transformBatchOperation } from '../../utils/operationTransforms'
import type { UIBatchOperation } from '../../utils/operationTransforms'

import { queryKeys, type OperationFilters } from './index'

// =============================================================================
// API Response Types
// =============================================================================

export interface OperationsListResponse {
  operations: BatchOperation[]
  count?: number
  total?: number
}

export interface OperationDetailResponse {
  operation: BatchOperation
}

// =============================================================================
// Fetch Functions
// =============================================================================

/**
 * Fetch operations list from API.
 * Transforms results to UI format.
 */
export async function fetchOperations(
  filters?: OperationFilters,
  signal?: AbortSignal
): Promise<UIBatchOperation[]> {
  const response = await apiClient.get<OperationsListResponse>(
    '/api/v2/operations/list-operations/',
    {
      signal,
      params: filters,
    }
  )
  return response.data.operations.map(transformBatchOperation)
}

/**
 * Fetch single operation by ID.
 */
export async function fetchOperation(
  id: string,
  signal?: AbortSignal
): Promise<UIBatchOperation> {
  const response = await apiClient.get<OperationDetailResponse>(
    `/api/v2/operations/get-operation/${id}/`,
    { signal }
  )
  return transformBatchOperation(response.data.operation)
}

/**
 * Cancel operation by ID.
 */
export async function cancelOperation(operationId: string): Promise<void> {
  await apiClient.post('/api/v2/operations/cancel-operation/', {
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
}

/**
 * React Query hook for single operation details.
 */
export function useOperation(id: string, options: UseOperationOptions = {}) {
  const { enabled = true, refetchInterval } = options

  return useQuery({
    queryKey: queryKeys.operations.detail(id),
    queryFn: ({ signal }) => fetchOperation(id, signal),
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
