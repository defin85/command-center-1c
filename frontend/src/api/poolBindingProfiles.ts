import { getV2 } from './generated/v2/v2'

import type { BindingProfileCreateRequest } from './generated/model/bindingProfileCreateRequest'
import type { BindingProfileDetail } from './generated/model/bindingProfileDetail'
import type { BindingProfileDetailResponse } from './generated/model/bindingProfileDetailResponse'
import type { BindingProfileListResponse } from './generated/model/bindingProfileListResponse'
import type { BindingProfileMutationResponse } from './generated/model/bindingProfileMutationResponse'
import type { BindingProfileRevision } from './generated/model/bindingProfileRevision'
import type { BindingProfileRevisionCreateRequest } from './generated/model/bindingProfileRevisionCreateRequest'
import type { BindingProfileSummary } from './generated/model/bindingProfileSummary'

export type {
  BindingProfileCreateRequest,
  BindingProfileDetail,
  BindingProfileDetailResponse,
  BindingProfileListResponse,
  BindingProfileMutationResponse,
  BindingProfileRevision,
  BindingProfileRevisionCreateRequest,
  BindingProfileSummary,
}

export async function listBindingProfiles(): Promise<BindingProfileListResponse> {
  return getV2().getPoolsBindingProfiles()
}

export async function getBindingProfileDetail(bindingProfileId: string): Promise<BindingProfileDetailResponse> {
  return getV2().getPoolsBindingProfilesDetail(bindingProfileId)
}

export async function createBindingProfile(
  request: BindingProfileCreateRequest,
): Promise<BindingProfileMutationResponse> {
  return getV2().postPoolsBindingProfiles(request)
}

export async function reviseBindingProfile(
  bindingProfileId: string,
  request: BindingProfileRevisionCreateRequest,
): Promise<BindingProfileMutationResponse> {
  return getV2().postPoolsBindingProfilesRevise(bindingProfileId, request)
}

export async function deactivateBindingProfile(bindingProfileId: string): Promise<BindingProfileMutationResponse> {
  return getV2().postPoolsBindingProfilesDeactivate(bindingProfileId)
}
