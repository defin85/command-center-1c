import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { GetTemplatesListTemplatesParams } from '../generated/model/getTemplatesListTemplatesParams'
import type { OperationTemplateListResponse } from '../generated/model/operationTemplateListResponse'
import type { OperationTemplateSyncRequest } from '../generated/model/operationTemplateSyncRequest'
import type { OperationTemplateSyncResponse } from '../generated/model/operationTemplateSyncResponse'

import { queryKeys } from './index'

const api = getV2()

async function fetchOperationTemplates(params?: GetTemplatesListTemplatesParams): Promise<OperationTemplateListResponse> {
  return api.getTemplatesListTemplates(params)
}

export function useOperationTemplates(params?: GetTemplatesListTemplatesParams) {
  return useQuery({
    queryKey: queryKeys.templates.list(params),
    queryFn: () => fetchOperationTemplates(params),
    select: (data) => data.templates ?? [],
  })
}

export function useSyncTemplatesFromRegistry() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: OperationTemplateSyncRequest): Promise<OperationTemplateSyncResponse> =>
      api.postTemplatesSyncFromRegistry(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.templates.all })
    },
  })
}

