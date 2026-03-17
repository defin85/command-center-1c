import type {
  AvailableDecisionRevision,
  AvailableWorkflowRevision,
  DecisionRef,
} from '../../types/workflow'

const trimString = (value: unknown): string => (
  typeof value === 'string' ? value.trim() : ''
)

export const isDecisionAvailableByDefault = (
  decision: AvailableDecisionRevision
): boolean => decision.metadataCompatibility?.is_compatible !== false

export const formatAvailableDecisionLabel = (
  decision: AvailableDecisionRevision
): string => {
  const decisionKey = trimString(decision.decisionKey)
  const decisionIdentity = trimString(decision.decisionTableId)
  const decisionTypeSuffix = decisionKey && decisionKey !== 'document_policy'
    ? ` (${decisionKey})`
    : ''
  const baseLabel = `${decision.name} · ${decisionIdentity}${decisionTypeSuffix} · r${decision.decisionRevision}`
  const configName = trimString(decision.metadataContext?.config_name)
  const configVersion = trimString(decision.metadataContext?.config_version)
  const configLabel = configName && configVersion
    ? `${configName} ${configVersion}`
    : ''
  const hasPublicationDrift = decision.metadataContext?.publication_drift === true
    || decision.metadataCompatibility?.reason === 'metadata_surface_diverged'

  const suffixes = [configLabel]
  if (hasPublicationDrift) {
    suffixes.push('drift')
  }

  const normalizedSuffixes = suffixes.filter(Boolean)
  if (normalizedSuffixes.length === 0) {
    return baseLabel
  }

  return `${baseLabel} · ${normalizedSuffixes.join(' · ')}`
}

export const formatAvailableWorkflowLabel = (
  workflow: Pick<AvailableWorkflowRevision, 'name' | 'workflowRevision'>
): string => `${workflow.name} · r${workflow.workflowRevision}`

export type CurrentDecisionSelection = Pick<
  DecisionRef,
  'decision_table_id' | 'decision_key' | 'decision_revision'
>

export type CurrentWorkflowSelection = {
  workflowDefinitionKey?: string | null
  workflowRevisionId?: string | null
  workflowRevision?: number | null
  workflowName?: string | null
}

export type DecisionRevisionOption = {
  value: string
  label: string
  decisionTableId: string
  decisionKey: string
  decisionRevision: number
}

export type WorkflowRevisionOption = {
  value: string
  label: string
  workflowDefinitionKey: string
  workflowRevisionId: string
  workflowRevision: number
  workflowName: string
}

export const buildDecisionRevisionValue = (
  decisionTableId: string,
  decisionRevision: number | string,
): string => `${decisionTableId}:${decisionRevision}`

export const buildWorkflowRevisionValue = (
  workflowRevisionId: string,
): string => workflowRevisionId

export const formatInactiveDecisionLabel = (
  decision: CurrentDecisionSelection,
): string => `${decision.decision_table_id} (${decision.decision_key}) · r${decision.decision_revision} [inactive]`

export const formatInactiveWorkflowLabel = (
  workflow: CurrentWorkflowSelection,
): string => {
  const name = trimString(workflow.workflowName)
    || trimString(workflow.workflowDefinitionKey)
    || trimString(workflow.workflowRevisionId)
    || 'workflow'
  const revision = Number.isFinite(workflow.workflowRevision)
    ? ` · r${Number(workflow.workflowRevision)}`
    : ''
  return `${name}${revision} [inactive]`
}

export const buildDecisionRevisionOptions = (options: {
  decisions: AvailableDecisionRevision[]
  currentDecision?: CurrentDecisionSelection
}): DecisionRevisionOption[] => {
  const decisionOptions: DecisionRevisionOption[] = options.decisions.map((decision) => ({
    value: buildDecisionRevisionValue(decision.decisionTableId, decision.decisionRevision),
    label: formatAvailableDecisionLabel(decision),
    decisionTableId: decision.decisionTableId,
    decisionKey: decision.decisionKey,
    decisionRevision: decision.decisionRevision,
  }))

  if (!options.currentDecision) {
    return decisionOptions
  }

  const currentValue = buildDecisionRevisionValue(
    options.currentDecision.decision_table_id,
    options.currentDecision.decision_revision,
  )

  if (!decisionOptions.some((option) => option.value === currentValue)) {
    decisionOptions.unshift({
      value: currentValue,
      label: formatInactiveDecisionLabel(options.currentDecision),
      decisionTableId: options.currentDecision.decision_table_id,
      decisionKey: options.currentDecision.decision_key,
      decisionRevision: options.currentDecision.decision_revision,
    })
  }

  return decisionOptions
}

export const buildWorkflowRevisionOptions = (options: {
  workflows: AvailableWorkflowRevision[]
  currentWorkflow?: CurrentWorkflowSelection
}): WorkflowRevisionOption[] => {
  const workflowOptions: WorkflowRevisionOption[] = options.workflows.map((workflow) => ({
    value: buildWorkflowRevisionValue(workflow.workflowRevisionId),
    label: formatAvailableWorkflowLabel(workflow),
    workflowDefinitionKey: workflow.workflowDefinitionKey,
    workflowRevisionId: workflow.workflowRevisionId,
    workflowRevision: workflow.workflowRevision,
    workflowName: workflow.name,
  }))

  const workflowRevisionId = trimString(options.currentWorkflow?.workflowRevisionId)
  if (!workflowRevisionId) {
    return workflowOptions
  }

  if (!workflowOptions.some((option) => option.value === workflowRevisionId)) {
    workflowOptions.unshift({
      value: workflowRevisionId,
      label: formatInactiveWorkflowLabel(options.currentWorkflow ?? {}),
      workflowDefinitionKey: trimString(options.currentWorkflow?.workflowDefinitionKey),
      workflowRevisionId,
      workflowRevision: Number(options.currentWorkflow?.workflowRevision ?? 0),
      workflowName: trimString(options.currentWorkflow?.workflowName) || workflowRevisionId,
    })
  }

  return workflowOptions
}
