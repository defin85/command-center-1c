import type {
  PoolRunRuntimeProjection,
  PoolWorkflowBinding,
  PoolWorkflowBindingDecisionRef,
  PoolWorkflowBindingProfileLifecycleWarning,
  WorkflowDefinitionRef,
} from '../../api/intercompanyPools'

type BindingLineageContext = {
  binding: PoolWorkflowBinding | null | undefined
  runtimeProjection: PoolRunRuntimeProjection | null | undefined
}

export const resolvePoolWorkflowBindingWorkflow = (
  binding: PoolWorkflowBinding | null | undefined
): WorkflowDefinitionRef | null => (
  binding?.resolved_profile?.workflow
  ?? binding?.workflow
  ?? null
)

export const resolvePoolWorkflowBindingDecisionRefs = (
  binding: PoolWorkflowBinding | null | undefined
): PoolWorkflowBindingDecisionRef[] => (
  binding?.resolved_profile?.decisions
  ?? binding?.decisions
  ?? []
)

export const resolvePoolWorkflowBindingProfileLabel = (
  binding: PoolWorkflowBinding | null | undefined
): string => {
  const profile = binding?.resolved_profile
  if (!profile) {
    return '-'
  }
  return [profile.code, profile.name].filter((value) => value && value.trim().length > 0).join(' · ') || '-'
}

export const resolvePoolWorkflowBindingProfileStatus = (
  binding: PoolWorkflowBinding | null | undefined
): string | null => binding?.resolved_profile?.status ?? null

export const resolvePoolWorkflowBindingLifecycleWarning = (
  binding: PoolWorkflowBinding | null | undefined
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
