import { useMutation, useQuery } from '@tanstack/react-query'

import { apiClient } from '../client'
import { queryKeys } from './queryKeys'

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

export async function fetchMyTenants(): Promise<MyTenantsResponse> {
  const response = await apiClient.get('/api/v2/tenants/list-my-tenants/')
  return response.data as MyTenantsResponse
}

export async function setActiveTenant(tenantId: string): Promise<{ active_tenant_id: string }> {
  const response = await apiClient.post('/api/v2/tenants/set-active/', { tenant_id: tenantId })
  return response.data as { active_tenant_id: string }
}

export function useMyTenants(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.tenants.my(),
    queryFn: fetchMyTenants,
    enabled: options?.enabled,
  })
}

export function useSetActiveTenant() {
  return useMutation({
    mutationFn: (tenantId: string) => setActiveTenant(tenantId),
  })
}

