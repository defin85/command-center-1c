import { getV2 } from './generated/v2/v2'

import type { BindingProfileCreateRequest } from './generated/model/bindingProfileCreateRequest'
import type { BindingProfileDetail } from './generated/model/bindingProfileDetail'
import type { BindingProfileDetailResponse } from './generated/model/bindingProfileDetailResponse'
import type { BindingProfileListResponse } from './generated/model/bindingProfileListResponse'
import type { BindingProfileMutationResponse } from './generated/model/bindingProfileMutationResponse'
import type { BindingProfileRevisionRead as BindingProfileRevision } from './generated/model/bindingProfileRevisionRead'
import type { BindingProfileRevisionCreateRequest } from './generated/model/bindingProfileRevisionCreateRequest'
import type { BindingProfileSummary } from './generated/model/bindingProfileSummary'
import type { BindingProfileUsageAttachment } from './generated/model/bindingProfileUsageAttachment'
import type { BindingProfileUsageRevisionSummary } from './generated/model/bindingProfileUsageRevisionSummary'
import type { BindingProfileUsageSummary } from './generated/model/bindingProfileUsageSummary'

export type {
  BindingProfileCreateRequest,
  BindingProfileDetail,
  BindingProfileDetailResponse,
  BindingProfileListResponse,
  BindingProfileMutationResponse,
  BindingProfileRevision,
  BindingProfileRevisionCreateRequest,
  BindingProfileSummary,
  BindingProfileUsageAttachment,
  BindingProfileUsageRevisionSummary,
  BindingProfileUsageSummary,
}

export async function listBindingProfiles(): Promise<BindingProfileListResponse> {
  return getV2().getPoolsBindingProfiles({ errorPolicy: 'page' })
}

export async function getBindingProfileDetail(bindingProfileId: string): Promise<BindingProfileDetailResponse> {
  return getV2().getPoolsBindingProfilesDetail(bindingProfileId, { errorPolicy: 'page' })
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
