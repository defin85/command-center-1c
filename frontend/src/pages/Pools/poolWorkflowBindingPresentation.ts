import type {
  PoolRunRuntimeProjection,
  PoolWorkflowBindingDecisionRef,
  PoolWorkflowBindingProfileLifecycleWarning,
  PoolWorkflowBindingResolvedProfile,
  PoolWorkflowBindingSelector,
  WorkflowDefinitionRef,
} from '../../api/intercompanyPools'

export type PoolWorkflowBindingPresentationValue = {
  binding_id?: string | null
  revision?: number | null
  status?: string | null
  selector?: PoolWorkflowBindingSelector | null
  workflow?: WorkflowDefinitionRef | null
  decisions?: PoolWorkflowBindingDecisionRef[] | null
  binding_profile_id?: string | null
  binding_profile_revision_id?: string | null
  binding_profile_revision_number?: number | null
  resolved_profile?: Partial<PoolWorkflowBindingResolvedProfile> | null
  profile_lifecycle_warning?: PoolWorkflowBindingProfileLifecycleWarning | null
}

type BindingLineageContext = {
  binding: PoolWorkflowBindingPresentationValue | null | undefined
  runtimeProjection: PoolRunRuntimeProjection | null | undefined
}

export const resolvePoolWorkflowBindingWorkflow = (
  binding: PoolWorkflowBindingPresentationValue | null | undefined
): WorkflowDefinitionRef | null => (
  binding?.resolved_profile?.workflow
  ?? binding?.workflow
  ?? null
)

export const resolvePoolWorkflowBindingDecisionRefs = (
  binding: PoolWorkflowBindingPresentationValue | null | undefined
): PoolWorkflowBindingDecisionRef[] => (
  binding?.resolved_profile?.decisions
  ?? binding?.decisions
  ?? []
)

export const resolvePoolWorkflowBindingProfileLabel = (
  binding: PoolWorkflowBindingPresentationValue | null | undefined
): string => {
  const profile = binding?.resolved_profile
  if (!profile) {
    return '-'
  }
  return [profile.code, profile.name].filter((value) => value && value.trim().length > 0).join(' · ') || '-'
}

export const resolvePoolWorkflowBindingProfileStatus = (
  binding: PoolWorkflowBindingPresentationValue | null | undefined
): string | null => binding?.resolved_profile?.status ?? null

export const resolvePoolWorkflowBindingLifecycleWarning = (
  binding: PoolWorkflowBindingPresentationValue | null | undefined
): PoolWorkflowBindingProfileLifecycleWarning | null => (
  binding?.profile_lifecycle_warning
  ?? null
)

export const resolvePoolWorkflowBindingProfileId = ({
  binding,
  runtimeProjection,
}: BindingLineageContext): string | null => (
  binding?.binding_profile_id
  ?? binding?.resolved_profile?.binding_profile_id
  ?? runtimeProjection?.workflow_binding.binding_profile_id
  ?? null
)

export const resolvePoolWorkflowBindingProfileRevisionId = ({
  binding,
  runtimeProjection,
}: BindingLineageContext): string | null => (
  binding?.binding_profile_revision_id
  ?? binding?.resolved_profile?.binding_profile_revision_id
  ?? runtimeProjection?.workflow_binding.binding_profile_revision_id
  ?? null
)

export const resolvePoolWorkflowBindingProfileRevisionNumber = ({
  binding,
  runtimeProjection,
}: BindingLineageContext): number | null => (
  binding?.binding_profile_revision_number
  ?? binding?.resolved_profile?.binding_profile_revision_number
  ?? runtimeProjection?.workflow_binding.binding_profile_revision_number
  ?? null
)

export const resolvePoolWorkflowBindingAttachmentRevision = ({
  binding,
  runtimeProjection,
}: BindingLineageContext): number | null => (
  binding?.revision
  ?? runtimeProjection?.workflow_binding.attachment_revision
  ?? null
)
