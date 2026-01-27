import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'

export type ClusterRef = { id: string; name: string }
export type DatabaseRef = { id: string; name: string; cluster_id: string | null }
export type OperationTemplateRef = { id: string; name: string }
export type WorkflowTemplateRef = { id: string; name: string }
export type ArtifactRef = { id: string; name: string }

export function useRbacRefClusters(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.refs.clusters(filters),
    queryFn: async (): Promise<{ clusters: ClusterRef[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/ref-clusters/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useRbacRefDatabases(
  filters?: { search?: string; cluster_id?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.refs.databases(filters),
    queryFn: async (): Promise<{ databases: DatabaseRef[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/ref-databases/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useRbacRefOperationTemplates(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.refs.operationTemplates(filters),
    queryFn: async (): Promise<{ templates: OperationTemplateRef[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/ref-operation-templates/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useRbacRefWorkflowTemplates(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.refs.workflowTemplates(filters),
    queryFn: async (): Promise<{ templates: WorkflowTemplateRef[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/ref-workflow-templates/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useRbacRefArtifacts(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.refs.artifacts(filters),
    queryFn: async (): Promise<{ artifacts: ArtifactRef[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/ref-artifacts/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

