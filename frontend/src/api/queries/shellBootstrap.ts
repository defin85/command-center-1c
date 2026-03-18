import { useQuery } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { SystemBootstrapResponse } from '../generated/model/systemBootstrapResponse'

import { queryKeys } from './queryKeys'
import { syncActiveTenantLocalStorage } from './tenants'
import { withQueryPolicy } from '../../lib/queryRuntime'

const api = getV2()
const SHELL_BOOTSTRAP_STALE_TIME_MS = 5 * 60_000

async function fetchShellBootstrap(): Promise<SystemBootstrapResponse> {
  const data = await api.getSystemBootstrap({ errorPolicy: 'page' })
  return {
    ...data,
    tenant_context: syncActiveTenantLocalStorage(data.tenant_context),
  }
}

export function useShellBootstrap(options?: { enabled?: boolean }) {
  return useQuery(withQueryPolicy('bootstrap', {
    queryKey: queryKeys.shell.bootstrap(),
    queryFn: fetchShellBootstrap,
    staleTime: SHELL_BOOTSTRAP_STALE_TIME_MS,
    enabled: options?.enabled ?? true,
  }))
}
