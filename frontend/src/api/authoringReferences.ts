import { getV2 } from './generated/v2/v2'
import type { DecisionTable, DecisionTableListResponse } from './generated/model'
import { isDecisionAvailableByDefault } from '../features/authoringReferences/options'
import type {
  AvailableDecisionRevision,
  AvailableWorkflowRevision,
} from '../types/workflow'

type V2Api = ReturnType<typeof getV2>
type WorkflowsListResponse = Awaited<ReturnType<V2Api['getWorkflowsListWorkflows']>>
type WorkflowSummary = NonNullable<WorkflowsListResponse['workflows']>[number]
type DecisionsCollectionResponse = Awaited<ReturnType<V2Api['getDecisionsCollection']>>
type DecisionSummary = DecisionTable

const expectDecisionListResponse = (
  response: DecisionsCollectionResponse,
): DecisionTableListResponse => {
  if ('decisions' in response) {
    return response
  }
  throw new Error('Expected DecisionTableListResponse from GET /api/v2/decisions/.')
}

export type AuthoringReferences = {
  availableWorkflows: AvailableWorkflowRevision[]
  availableDecisions: AvailableDecisionRevision[]
}

export function buildAvailableWorkflowRevisions(
  workflows: readonly WorkflowSummary[] | undefined,
): AvailableWorkflowRevision[] {
  const workflowRows = workflows ?? []
  const workflowsById = new Map(
    workflowRows.map((workflow) => [workflow.id, workflow])
  )
  const workflowDefinitionKeyCache = new Map<string, string>()

  const resolveWorkflowDefinitionKey = (workflowId: string): string => {
    const cached = workflowDefinitionKeyCache.get(workflowId)
    if (cached) {
      return cached
    }

    const workflow = workflowsById.get(workflowId)
    if (!workflow?.parent_version) {
      workflowDefinitionKeyCache.set(workflowId, workflowId)
      return workflowId
    }

    if (!workflowsById.has(workflow.parent_version)) {
      workflowDefinitionKeyCache.set(workflowId, workflow.parent_version)
      return workflow.parent_version
    }

    const resolved = resolveWorkflowDefinitionKey(workflow.parent_version)
    workflowDefinitionKeyCache.set(workflowId, resolved)
    return resolved
  }

  return workflowRows
    .filter((workflow) => workflow.is_system_managed !== true)
    .map((workflow) => ({
      id: workflow.id,
      name: workflow.name,
      workflowDefinitionKey: resolveWorkflowDefinitionKey(workflow.id),
      workflowRevisionId: workflow.id,
      workflowRevision: workflow.version_number,
    }))
    .sort((left, right) => (
      left.name.localeCompare(right.name) || left.workflowRevision - right.workflowRevision
    ))
}

export function buildAvailableDecisionRevisions(
  decisions: readonly DecisionSummary[] | undefined,
): AvailableDecisionRevision[] {
  return (decisions ?? [])
    .filter((decision) => decision.is_active !== false)
    .map((decision) => ({
      id: decision.id,
      name: decision.name,
      decisionTableId: decision.decision_table_id,
      decisionKey: decision.decision_key,
      decisionRevision: decision.decision_revision,
      metadataContext: decision.metadata_context,
      metadataCompatibility: decision.metadata_compatibility,
    }))
    .filter(isDecisionAvailableByDefault)
    .sort((left, right) => (
      left.name.localeCompare(right.name) || left.decisionRevision - right.decisionRevision
    ))
}

export async function listAuthoringReferences(options?: {
  databaseId?: string
}): Promise<AuthoringReferences> {
  const api = getV2()
  const databaseId = typeof options?.databaseId === 'string' && options.databaseId.trim()
    ? options.databaseId.trim()
    : undefined

  const [workflowResponse, decisionResponse] = await Promise.all([
    api.getWorkflowsListWorkflows({ surface: 'workflow_library', limit: 1000 }),
    api.getDecisionsCollection(
      databaseId
        ? { database_id: databaseId }
        : undefined
    ),
  ])
  const decisions = expectDecisionListResponse(decisionResponse)

  return {
    availableWorkflows: buildAvailableWorkflowRevisions(workflowResponse.workflows),
    availableDecisions: buildAvailableDecisionRevisions(decisions.decisions),
  }
}
