import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  listArtifacts,
  listArtifactVersions,
  listArtifactAliases,
  upsertArtifactAlias,
  deleteArtifact,
  restoreArtifact,
  type ArtifactAliasUpsertPayload,
  type ArtifactListParams,
} from '../artifacts'
import { queryKeys } from './index'

export const useArtifacts = (params: ArtifactListParams, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: queryKeys.artifacts.list(params),
    queryFn: ({ signal }) => listArtifacts(params, signal),
    keepPreviousData: true,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}

export const useArtifactVersions = (artifactId?: string) => {
  return useQuery({
    queryKey: queryKeys.artifacts.versions(artifactId ?? 'none'),
    queryFn: ({ signal }) => listArtifactVersions(artifactId as string, signal),
    enabled: Boolean(artifactId),
    retry: false,
  })
}

export const useArtifactAliases = (artifactId?: string) => {
  return useQuery({
    queryKey: queryKeys.artifacts.aliases(artifactId ?? 'none'),
    queryFn: ({ signal }) => listArtifactAliases(artifactId as string, signal),
    enabled: Boolean(artifactId),
    retry: false,
  })
}

export const useUpsertArtifactAlias = (artifactId?: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ArtifactAliasUpsertPayload) => {
      if (!artifactId) {
        throw new Error('artifactId is required')
      }
      return upsertArtifactAlias(artifactId, payload)
    },
    onSuccess: () => {
      if (artifactId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.aliases(artifactId) })
      }
    },
  })
}

export const useDeleteArtifact = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (artifactId: string) => deleteArtifact(artifactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
    },
  })
}

export const useRestoreArtifact = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (artifactId: string) => restoreArtifact(artifactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
    },
  })
}
