import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '../client'
import { queryKeys } from './queryKeys'
import { withQueryPolicy } from '../../lib/queryRuntime'

export type TenantSummary = {
  id: string
  slug: string
  name: string
  role: string
}

export type MyTenantsResponse = {
  active_tenant_id: string | null
  tenants: TenantSummary[]
}

type TenantContextLike = {
  active_tenant_id: string | null
  tenants: Array<{ id: string }>
}

export function syncActiveTenantLocalStorage<T extends TenantContextLike>(data: T): T {
  const stored = localStorage.getItem('active_tenant_id')
  const tenants = Array.isArray(data.tenants) ? data.tenants : []
  const preferred = data.active_tenant_id || tenants[0]?.id || null

  if (!stored && preferred) {
    localStorage.setItem('active_tenant_id', preferred)
  }

  if (stored && data.active_tenant_id && stored !== data.active_tenant_id) {
    localStorage.setItem('active_tenant_id', data.active_tenant_id)
  }

  return data
}

export async function fetchMyTenants(): Promise<MyTenantsResponse> {
  const response = await apiClient.get('/api/v2/tenants/list-my-tenants/', { errorPolicy: 'background' })
  return syncActiveTenantLocalStorage(response.data as MyTenantsResponse)
}

export async function setActiveTenant(tenantId: string): Promise<{ active_tenant_id: string }> {
  const response = await apiClient.post('/api/v2/tenants/set-active/', { tenant_id: tenantId })
  return response.data as { active_tenant_id: string }
}

export function useMyTenants(options?: { enabled?: boolean }) {
  return useQuery(withQueryPolicy('bootstrap', {
    queryKey: queryKeys.tenants.my(),
    queryFn: fetchMyTenants,
    enabled: options?.enabled,
  }))
}

export function useSetActiveTenant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (tenantId: string) => setActiveTenant(tenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shell.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.all })
    },
  })
}
