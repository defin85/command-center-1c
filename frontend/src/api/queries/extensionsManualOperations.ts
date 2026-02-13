import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { ManualOperationBinding } from '../generated/model/manualOperationBinding'
import { queryKeys } from './queryKeys'

const api = getV2()

export type ManualOperationKey = 'extensions.sync' | 'extensions.set_flags'

export function useManualOperationBindings() {
  return useQuery({
    queryKey: queryKeys.extensions.manualOperationBindings(),
    queryFn: async () => {
      const response = await api.getExtensionsManualOperationBindings()
      return Array.isArray(response.bindings) ? response.bindings : []
    },
    staleTime: 30_000,
  })
}

export function useUpsertManualOperationBinding() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      manualOperation,
      templateId,
    }: {
      manualOperation: ManualOperationKey
      templateId: string
    }): Promise<ManualOperationBinding> => {
      const response = await api.putExtensionsManualOperationBindings(manualOperation, {
        template_id: templateId,
      })
      return response.binding
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.extensions.manualOperationBindings() })
    },
  })
}

export function useDeleteManualOperationBinding() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (manualOperation: ManualOperationKey) => {
      await api.delExtensionsManualOperationBindings(manualOperation)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.extensions.manualOperationBindings() })
    },
  })
}
