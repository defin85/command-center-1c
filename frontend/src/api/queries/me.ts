import { useQuery } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { CurrentUser } from '../generated/model/currentUser'

import { queryKeys } from './queryKeys'

const api = getV2()

const ME_STALE_TIME_MS = 5 * 60_000

async function fetchMe(): Promise<CurrentUser> {
  return api.getSystemMe()
}

export function useMe(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.me.current(),
    queryFn: fetchMe,
    staleTime: ME_STALE_TIME_MS,
    refetchOnWindowFocus: false,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}
