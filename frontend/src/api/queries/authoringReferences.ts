import { useQuery } from '@tanstack/react-query'

import { listAuthoringReferences } from '../authoringReferences'
import { queryKeys } from './queryKeys'

export function useAuthoringReferences(options?: {
  databaseId?: string
  enabled?: boolean
}) {
  const databaseId = typeof options?.databaseId === 'string' && options.databaseId.trim()
    ? options.databaseId.trim()
    : undefined

  return useQuery({
    queryKey: queryKeys.authoringReferences.list(databaseId),
    queryFn: () => listAuthoringReferences({ databaseId }),
    placeholderData: (previousData) => previousData,
    enabled: options?.enabled ?? true,
  })
}
