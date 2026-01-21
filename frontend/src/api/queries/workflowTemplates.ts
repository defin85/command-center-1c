import { useQuery } from '@tanstack/react-query'

import type { GetWorkflowsListTemplatesParams } from '../generated/model/getWorkflowsListTemplatesParams'
import type { TemplateListResponse } from '../generated/model/templateListResponse'
import { getV2 } from '../generated'

const api = getV2()

export function useWorkflowTemplates(
  params?: GetWorkflowsListTemplatesParams,
  enabled = true
) {
  return useQuery<TemplateListResponse>({
    queryKey: ['workflows', 'list-templates', params],
    queryFn: () => api.getWorkflowsListTemplates(params),
    enabled,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  })
}

