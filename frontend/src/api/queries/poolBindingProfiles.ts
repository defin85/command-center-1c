import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createBindingProfile,
  deactivateBindingProfile,
  getBindingProfileDetail,
  listBindingProfiles,
  reviseBindingProfile,
  type BindingProfileCreateRequest,
  type BindingProfileDetail,
  type BindingProfileListResponse,
  type BindingProfileMutationResponse,
  type BindingProfileRevisionCreateRequest,
  type BindingProfileSummary,
} from '../poolBindingProfiles'
import { queryKeys } from './queryKeys'
import { withQueryPolicy } from '../../lib/queryRuntime'

const toBindingProfileSummary = (profile: BindingProfileDetail): BindingProfileSummary => ({
  binding_profile_id: profile.binding_profile_id,
  code: profile.code,
  name: profile.name,
  description: profile.description,
  status: profile.status,
  latest_revision_number: profile.latest_revision_number,
  latest_revision: profile.latest_revision,
  created_by: profile.created_by,
  updated_by: profile.updated_by,
  deactivated_by: profile.deactivated_by,
  deactivated_at: profile.deactivated_at,
  created_at: profile.created_at,
  updated_at: profile.updated_at,
})

const upsertBindingProfileListEntry = (
  current: BindingProfileListResponse | undefined,
  profile: BindingProfileDetail,
): BindingProfileListResponse => {
  const nextSummary = toBindingProfileSummary(profile)
  const currentProfiles = current?.binding_profiles ?? []
  const filteredProfiles = currentProfiles.filter((item) => item.binding_profile_id !== profile.binding_profile_id)
  const bindingProfiles = [nextSummary, ...filteredProfiles]

  return {
    binding_profiles: bindingProfiles,
    count: bindingProfiles.length,
  }
}

export function useBindingProfiles(options?: { enabled?: boolean }) {
  return useQuery(withQueryPolicy('interactive', {
    queryKey: queryKeys.poolBindingProfiles.list(),
    queryFn: listBindingProfiles,
    placeholderData: (previousData: BindingProfileListResponse | undefined) => previousData,
    enabled: options?.enabled ?? true,
  }))
}

export function useBindingProfileDetail(bindingProfileId?: string, options?: { enabled?: boolean }) {
  return useQuery(withQueryPolicy('interactive', {
    queryKey: queryKeys.poolBindingProfiles.detail(bindingProfileId ?? ''),
    queryFn: () => getBindingProfileDetail(bindingProfileId as string),
    enabled: Boolean(bindingProfileId) && (options?.enabled ?? true),
  }))
}

export function useCreateBindingProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: BindingProfileCreateRequest) => createBindingProfile(request),
    onSuccess: (response: BindingProfileMutationResponse) => {
      const bindingProfileId = response.binding_profile.binding_profile_id
      queryClient.setQueryData(queryKeys.poolBindingProfiles.detail(bindingProfileId), response)
      queryClient.setQueryData<BindingProfileListResponse>(
        queryKeys.poolBindingProfiles.list(),
        (current) => upsertBindingProfileListEntry(current, response.binding_profile),
      )
      queryClient.invalidateQueries({ queryKey: queryKeys.poolBindingProfiles.all })
    },
  })
}

export function useReviseBindingProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      bindingProfileId,
      request,
    }: {
      bindingProfileId: string
      request: BindingProfileRevisionCreateRequest
    }) => reviseBindingProfile(bindingProfileId, request),
    onSuccess: (response: BindingProfileMutationResponse) => {
      const bindingProfileId = response.binding_profile.binding_profile_id
      queryClient.setQueryData(queryKeys.poolBindingProfiles.detail(bindingProfileId), response)
      queryClient.setQueryData<BindingProfileListResponse>(
        queryKeys.poolBindingProfiles.list(),
        (current) => upsertBindingProfileListEntry(current, response.binding_profile),
      )
      queryClient.invalidateQueries({ queryKey: queryKeys.poolBindingProfiles.all })
    },
  })
}

export function useDeactivateBindingProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (bindingProfileId: string) => deactivateBindingProfile(bindingProfileId),
    onSuccess: (response: BindingProfileMutationResponse) => {
      const bindingProfileId = response.binding_profile.binding_profile_id
      queryClient.setQueryData(queryKeys.poolBindingProfiles.detail(bindingProfileId), response)
      queryClient.setQueryData<BindingProfileListResponse>(
        queryKeys.poolBindingProfiles.list(),
        (current) => upsertBindingProfileListEntry(current, response.binding_profile),
      )
      queryClient.invalidateQueries({ queryKey: queryKeys.poolBindingProfiles.all })
    },
  })
}
