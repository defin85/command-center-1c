import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createPoolTopologyTemplate,
  listPoolTopologyTemplates,
  revisePoolTopologyTemplate,
  type CreatePoolTopologyTemplatePayload,
  type CreatePoolTopologyTemplateRevisionPayload,
  type PoolTopologyTemplate,
  type PoolTopologyTemplateMutationResponse,
} from '../intercompanyPools'
import { queryKeys } from './queryKeys'
import { withQueryPolicy } from '../../lib/queryRuntime'

const sortTemplates = (templates: PoolTopologyTemplate[]) => (
  [...templates].sort((left, right) => (
    left.name.localeCompare(right.name, undefined, { sensitivity: 'base' })
  ))
)

const upsertTopologyTemplateListEntry = (
  current: PoolTopologyTemplate[] | undefined,
  template: PoolTopologyTemplate,
) => {
  const currentTemplates = current ?? []
  const filteredTemplates = currentTemplates.filter(
    (item) => item.topology_template_id !== template.topology_template_id
  )
  return sortTemplates([template, ...filteredTemplates])
}

export function usePoolTopologyTemplates(options?: { enabled?: boolean }) {
  return useQuery(withQueryPolicy('interactive', {
    queryKey: queryKeys.poolCatalog.topologyTemplates(),
    queryFn: listPoolTopologyTemplates,
    placeholderData: (previousData: PoolTopologyTemplate[] | undefined) => previousData,
    enabled: options?.enabled ?? true,
  }))
}

export function useCreatePoolTopologyTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: CreatePoolTopologyTemplatePayload) => createPoolTopologyTemplate(request),
    onSuccess: (response: PoolTopologyTemplateMutationResponse) => {
      queryClient.setQueryData<PoolTopologyTemplate[]>(
        queryKeys.poolCatalog.topologyTemplates(),
        (current) => upsertTopologyTemplateListEntry(current, response.topology_template),
      )
      queryClient.invalidateQueries({ queryKey: queryKeys.poolCatalog.topologyTemplates() })
    },
  })
}

export function useRevisePoolTopologyTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      topologyTemplateId,
      request,
    }: {
      topologyTemplateId: string
      request: CreatePoolTopologyTemplateRevisionPayload
    }) => revisePoolTopologyTemplate(topologyTemplateId, request),
    onSuccess: (response: PoolTopologyTemplateMutationResponse) => {
      queryClient.setQueryData<PoolTopologyTemplate[]>(
        queryKeys.poolCatalog.topologyTemplates(),
        (current) => upsertTopologyTemplateListEntry(current, response.topology_template),
      )
      queryClient.invalidateQueries({ queryKey: queryKeys.poolCatalog.topologyTemplates() })
    },
  })
}
