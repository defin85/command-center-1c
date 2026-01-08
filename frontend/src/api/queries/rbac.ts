import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { ClusterPermissionListResponse } from '../generated/model/clusterPermissionListResponse'
import type { DatabasePermissionListResponse } from '../generated/model/databasePermissionListResponse'
import type { EffectiveAccessResponse } from '../generated/model/effectiveAccessResponse'
import type { GrantClusterPermissionRequest } from '../generated/model/grantClusterPermissionRequest'
import type { GrantDatabasePermissionRequest } from '../generated/model/grantDatabasePermissionRequest'
import type { RevokeClusterPermissionRequest } from '../generated/model/revokeClusterPermissionRequest'
import type { RevokeDatabasePermissionRequest } from '../generated/model/revokeDatabasePermissionRequest'

import { queryKeys } from './index'
import { apiClient } from '../client'

const api = getV2()

export interface ClusterPermissionFilters {
  user_id?: number
  cluster_id?: string
  level?: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
  search?: string
  limit?: number
  offset?: number
}

export interface DatabasePermissionFilters {
  user_id?: number
  database_id?: string
  cluster_id?: string
  level?: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
  search?: string
  limit?: number
  offset?: number
}

export function useClusterPermissions(
  filters?: ClusterPermissionFilters,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.clusterPermissions(filters),
    queryFn: (): Promise<ClusterPermissionListResponse> => api.getRbacListClusterPermissions(filters),
    enabled: options?.enabled ?? true,
  })
}

export function useDatabasePermissions(
  filters?: DatabasePermissionFilters,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.databasePermissions(filters),
    queryFn: (): Promise<DatabasePermissionListResponse> => api.getRbacListDatabasePermissions(filters),
    enabled: options?.enabled ?? true,
  })
}

export function useEffectiveAccess(
  userId?: number,
  options?: {
    includeDatabases?: boolean
    includeClusters?: boolean
    includeTemplates?: boolean
    includeWorkflows?: boolean
    includeArtifacts?: boolean
    limit?: number
    offset?: number
    enabled?: boolean
  }
) {
  const includeDatabases = options?.includeDatabases ?? false
  const includeClusters = options?.includeClusters ?? true
  const includeTemplates = options?.includeTemplates ?? false
  const includeWorkflows = options?.includeWorkflows ?? false
  const includeArtifacts = options?.includeArtifacts ?? false
  const limit = options?.limit
  const offset = options?.offset
  return useQuery({
    queryKey: queryKeys.rbac.effectiveAccess({
      user_id: userId,
      include_databases: includeDatabases,
      include_clusters: includeClusters,
      include_templates: includeTemplates,
      include_workflows: includeWorkflows,
      include_artifacts: includeArtifacts,
      limit,
      offset,
    }),
    queryFn: (): Promise<EffectiveAccessResponse> =>
      api.getRbacGetEffectiveAccess({
        user_id: userId,
        include_databases: includeDatabases,
        include_clusters: includeClusters,
        include_templates: includeTemplates,
        include_workflows: includeWorkflows,
        include_artifacts: includeArtifacts,
        limit,
        offset,
      }),
    enabled: options?.enabled ?? true,
  })
}

export function useGrantClusterPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: GrantClusterPermissionRequest) => api.postRbacGrantClusterPermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeClusterPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: RevokeClusterPermissionRequest) => api.postRbacRevokeClusterPermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useGrantDatabasePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: GrantDatabasePermissionRequest) => api.postRbacGrantDatabasePermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeDatabasePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: RevokeDatabasePermissionRequest) => api.postRbacRevokeDatabasePermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type UserRef = {
  id: number
  username: string
}

export type UserListResponse = {
  users: UserRef[]
  count: number
  total: number
}

export function useRbacUsers(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.users(filters),
    queryFn: async (): Promise<UserListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-users/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useCanManageRbac(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.rbac.canManage(),
    queryFn: async (): Promise<boolean> => {
      try {
        await apiClient.get('/api/v2/rbac/list-roles/', { params: { limit: 1, offset: 0 } })
        return true
      } catch (error) {
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403) {
          return false
        }
        throw error
      }
    },
    staleTime: 60_000,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}

export type RbacGroupRef = {
  id: number
  name: string
}

export type RbacRole = {
  id: number
  name: string
  users_count: number
  permissions_count: number
  permission_codes: string[]
}

export type RoleListResponse = {
  roles: RbacRole[]
  count: number
  total: number
}

export function useRoles(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.roles(filters),
    queryFn: async (): Promise<RoleListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-roles/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useCreateRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { name: string; reason: string }): Promise<RbacGroupRef> => {
      const response = await apiClient.post('/api/v2/rbac/create-role/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useUpdateRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; name: string; reason: string }): Promise<RbacGroupRef> => {
      const response = await apiClient.post('/api/v2/rbac/update-role/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useDeleteRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/delete-role/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type Capability = {
  code: string
  name: string
  app_label: string
  codename: string
  exists: boolean
}

export type CapabilityListResponse = {
  capabilities: Capability[]
  count: number
}

export function useCapabilities(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.rbac.capabilities(),
    queryFn: async (): Promise<CapabilityListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-capabilities/')
      return response.data
    },
    staleTime: 60_000,
    enabled: options?.enabled ?? true,
  })
}

export function useSetRoleCapabilities() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      permission_codes: string[]
      mode?: 'replace' | 'add' | 'remove'
      reason: string
    }): Promise<{ group: RbacGroupRef; permission_codes: string[] }> => {
      const response = await apiClient.post('/api/v2/rbac/set-role-capabilities/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type UserRolesResponse = {
  user: UserRef
  roles: RbacGroupRef[]
}

export function useUserRoles(userId?: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.rbac.userRoles(userId),
    queryFn: async (): Promise<UserRolesResponse> => {
      const response = await apiClient.get('/api/v2/rbac/get-user-roles/', { params: { user_id: userId } })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useSetUserRoles() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      group_ids: number[]
      mode?: 'replace' | 'add' | 'remove'
      reason: string
    }): Promise<UserRolesResponse> => {
      const response = await apiClient.post('/api/v2/rbac/set-user-roles/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

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

export type ClusterGroupPermission = {
  group: RbacGroupRef
  cluster: ClusterRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type DatabaseGroupPermission = {
  group: RbacGroupRef
  database: DatabaseRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type BulkUpsertResult = {
  created: number
  updated: number
  skipped: number
  total: number
}

export type BulkDeleteResult = {
  deleted: number
  skipped: number
  total: number
}

export function useClusterGroupPermissions(
  filters?: { group_id?: number; cluster_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.clusters(filters),
    queryFn: async (): Promise<{ permissions: ClusterGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-cluster-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      cluster_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: ClusterGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; cluster_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkGrantClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      cluster_ids: string[]
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<BulkUpsertResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-grant-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkRevokeClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; cluster_ids: string[]; reason: string }): Promise<BulkDeleteResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-revoke-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useDatabaseGroupPermissions(
  filters?: {
    group_id?: number
    database_id?: string
    cluster_id?: string
    level?: string
    search?: string
    limit?: number
    offset?: number
  },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.databases(filters),
    queryFn: async (): Promise<{ permissions: DatabaseGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-database-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      database_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: DatabaseGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; database_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkGrantDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      database_ids: string[]
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<BulkUpsertResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-grant-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkRevokeDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; database_ids: string[]; reason: string }): Promise<BulkDeleteResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-revoke-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type OperationTemplatePermission = {
  user: UserRef
  template: OperationTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type OperationTemplateGroupPermission = {
  group: RbacGroupRef
  template: OperationTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export function useOperationTemplatePermissions(
  filters?: { user_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.operationTemplatePermissions(filters),
    queryFn: async (): Promise<{ permissions: OperationTemplatePermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-operation-template-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantOperationTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: OperationTemplatePermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-operation-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeOperationTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { user_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-operation-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useOperationTemplateGroupPermissions(
  filters?: { group_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.operationTemplates(filters),
    queryFn: async (): Promise<{ permissions: OperationTemplateGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-operation-template-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantOperationTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: OperationTemplateGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-operation-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeOperationTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-operation-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type WorkflowTemplatePermission = {
  user: UserRef
  template: WorkflowTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type WorkflowTemplateGroupPermission = {
  group: RbacGroupRef
  template: WorkflowTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export function useWorkflowTemplatePermissions(
  filters?: { user_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.workflowTemplatePermissions(filters),
    queryFn: async (): Promise<{ permissions: WorkflowTemplatePermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-workflow-template-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantWorkflowTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: WorkflowTemplatePermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-workflow-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeWorkflowTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { user_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-workflow-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useWorkflowTemplateGroupPermissions(
  filters?: { group_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.workflowTemplates(filters),
    queryFn: async (): Promise<{ permissions: WorkflowTemplateGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-workflow-template-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantWorkflowTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: WorkflowTemplateGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-workflow-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeWorkflowTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-workflow-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type ArtifactPermission = {
  user: UserRef
  artifact: ArtifactRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type ArtifactGroupPermission = {
  group: RbacGroupRef
  artifact: ArtifactRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export function useArtifactPermissions(
  filters?: { user_id?: number; artifact_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.artifactPermissions(filters),
    queryFn: async (): Promise<{ permissions: ArtifactPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-artifact-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantArtifactPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      artifact_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: ArtifactPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-artifact-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeArtifactPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { user_id: number; artifact_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-artifact-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useArtifactGroupPermissions(
  filters?: { group_id?: number; artifact_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.artifacts(filters),
    queryFn: async (): Promise<{ permissions: ArtifactGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-artifact-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantArtifactGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      artifact_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: ArtifactGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-artifact-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeArtifactGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; artifact_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-artifact-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type AdminAuditLogItem = {
  id: number
  created_at: string
  action: string
  outcome: string
  actor_username: string
  actor_id: number | null
  target_type: string
  target_id: string
  metadata: Record<string, unknown>
  error_message: string
}

export function useAdminAuditLog(
  filters?: {
    action?: string
    outcome?: string
    actor?: string
    target_type?: string
    target_id?: string
    search?: string
    since?: string
    until?: string
    limit?: number
    offset?: number
  },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.audit(filters),
    queryFn: async (): Promise<{ items: AdminAuditLogItem[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-admin-audit/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}
