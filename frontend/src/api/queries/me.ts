import { useQuery } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { CurrentUser } from '../generated/model/currentUser'

import { queryKeys } from './queryKeys'

const api = getV2()

async function fetchMe(): Promise<CurrentUser> {
  return api.getSystemMe()
}

export function useMe(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.me.current(),
    queryFn: fetchMe,
    staleTime: 60_000,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}
