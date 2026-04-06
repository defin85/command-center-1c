import type {
  PoolBatch,
  PoolBatchCreateResponse,
  PoolBatchCreatePayload,
  PoolBatchListResponse,
  PoolBatchSettlement,
  PoolFactualEdgeBalance,
  PoolFactualRefreshResponse,
  PoolFactualReviewActionResponse,
  PoolFactualReviewQueue,
  PoolFactualReviewQueueItem,
  PoolFactualSummary,
  PoolFactualWorkspace,
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  CreatePoolRunPayload,
  DecisionTableRef,
  OrganizationPool,
  PoolGraph,
  PoolRun,
  PoolRunReport,
  PoolRunRetryAcceptedResponse,
  PoolRunSafeCommandConflict,
  PoolRunSafeCommandResponse,
  PoolSchemaTemplate,
  PoolTopologyTemplate,
  PoolTopologyTemplateRevision,
  PoolTopologyTemplateListResponse,
  PoolTopologyTemplateMutationResponse,
  UpsertPoolTopologySnapshotPayload,
  PoolWorkflowBinding,
  PoolWorkflowBindingInput,
  PoolWorkflowBindingSelector,
  RetryPoolRunPayload,
  UpsertOrganizationPoolPayload,
  WorkflowDefinitionRef,
} from './intercompanyPools'
import type { DecisionTableRef as GeneratedDecisionTableRef } from './generated/model/decisionTableRef'
import type { OrganizationPool as GeneratedOrganizationPool } from './generated/model/organizationPool'
import type { OrganizationPoolUpsertRequest as GeneratedOrganizationPoolUpsertRequest } from './generated/model/organizationPoolUpsertRequest'
import type { PoolGraphResponse as GeneratedPoolGraphResponse } from './generated/model/poolGraphResponse'
import type { PoolBatch as GeneratedPoolBatch } from './generated/model/poolBatch'
import type { PoolBatchCreateResponse as GeneratedPoolBatchCreateResponse } from './generated/model/poolBatchCreateResponse'
import type { PoolBatchCreateRequest as GeneratedPoolBatchCreateRequest } from './generated/model/poolBatchCreateRequest'
import type { PoolBatchListResponse as GeneratedPoolBatchListResponse } from './generated/model/poolBatchListResponse'
import type { PoolSaleClosingStartResponse as GeneratedPoolSaleClosingStartResponse } from './generated/model/poolSaleClosingStartResponse'
import type { PoolBatchSettlement as GeneratedPoolBatchSettlement } from './generated/model/poolBatchSettlement'
import type { PoolFactualBalanceSnapshot as GeneratedPoolFactualBalanceSnapshot } from './generated/model/poolFactualBalanceSnapshot'
import type { PoolFactualRefreshResponse as GeneratedPoolFactualRefreshResponse } from './generated/model/poolFactualRefreshResponse'
import type { PoolFactualReviewActionResponse as GeneratedPoolFactualReviewActionResponse } from './generated/model/poolFactualReviewActionResponse'
import type { PoolFactualReviewQueue as GeneratedPoolFactualReviewQueue } from './generated/model/poolFactualReviewQueue'
import type { PoolFactualReviewQueueItem as GeneratedPoolFactualReviewQueueItem } from './generated/model/poolFactualReviewQueueItem'
import type { PoolFactualSummary as GeneratedPoolFactualSummary } from './generated/model/poolFactualSummary'
import type { PoolFactualWorkspaceResponse as GeneratedPoolFactualWorkspaceResponse } from './generated/model/poolFactualWorkspaceResponse'
import type { PoolRun as GeneratedPoolRun } from './generated/model/poolRun'
import type { PoolRunCreateRequest as GeneratedPoolRunCreateRequest } from './generated/model/poolRunCreateRequest'
import type { PoolRunReportResponse as GeneratedPoolRunReportResponse } from './generated/model/poolRunReportResponse'
import type { PoolRunRetryAcceptedResponse as GeneratedPoolRunRetryAcceptedResponse } from './generated/model/poolRunRetryAcceptedResponse'
import type { PoolRunRetryRequest as GeneratedPoolRunRetryRequest } from './generated/model/poolRunRetryRequest'
import type { PoolRunSafeCommandConflict as GeneratedPoolRunSafeCommandConflict } from './generated/model/poolRunSafeCommandConflict'
import type { PoolRunSafeCommandResponse as GeneratedPoolRunSafeCommandResponse } from './generated/model/poolRunSafeCommandResponse'
import type { PoolSchemaTemplate as GeneratedPoolSchemaTemplate } from './generated/model/poolSchemaTemplate'
import type { PoolTopologySnapshotUpsertRequest as GeneratedPoolTopologySnapshotUpsertRequest } from './generated/model/poolTopologySnapshotUpsertRequest'
import type { TopologyTemplate as GeneratedPoolTopologyTemplate } from './generated/model/topologyTemplate'
import type { TopologyTemplateCreateRequest as GeneratedTopologyTemplateCreateRequest } from './generated/model/topologyTemplateCreateRequest'
import type { TopologyTemplateListResponse as GeneratedPoolTopologyTemplateListResponse } from './generated/model/topologyTemplateListResponse'
import type { TopologyTemplateMutationResponse as GeneratedTopologyTemplateMutationResponse } from './generated/model/topologyTemplateMutationResponse'
import type { TopologyTemplateRevision as GeneratedPoolTopologyTemplateRevision } from './generated/model/topologyTemplateRevision'
import type { TopologyTemplateRevisionCreateRequest as GeneratedTopologyTemplateRevisionCreateRequest } from './generated/model/topologyTemplateRevisionCreateRequest'
import type { PoolWorkflowBindingInput as GeneratedPoolWorkflowBindingInput } from './generated/model/poolWorkflowBindingInput'
import type { PoolWorkflowBindingRead as GeneratedPoolWorkflowBinding } from './generated/model/poolWorkflowBindingRead'
import type { PoolWorkflowBindingSelector as GeneratedPoolWorkflowBindingSelector } from './generated/model/poolWorkflowBindingSelector'
import type { WorkflowDefinitionRef as GeneratedWorkflowDefinitionRef } from './generated/model/workflowDefinitionRef'

type AssertAssignable<TActual extends TExpected, TExpected> = TActual

type GeneratedPoolBatchContractShape = Omit<GeneratedPoolBatch, 'settlement'> & {
  settlement?: GeneratedPoolBatchSettlement | null
}

type GeneratedPoolBatchListResponseContractShape = Omit<GeneratedPoolBatchListResponse, 'batches'> & {
  batches: GeneratedPoolBatchContractShape[]
}

type GeneratedPoolBatchCreateResponseContractShape = Omit<GeneratedPoolBatchCreateResponse, 'batch' | 'run' | 'sale_closing'> & {
  batch: GeneratedPoolBatchContractShape
  run?: GeneratedPoolRun | null
  sale_closing?: GeneratedPoolSaleClosingStartResponse | null
}

type GeneratedPoolFactualWorkspaceResponseContractShape = Omit<GeneratedPoolFactualWorkspaceResponse, 'settlements'> & {
  settlements: GeneratedPoolBatchContractShape[]
}

export type WorkflowDefinitionRefContract = AssertAssignable<WorkflowDefinitionRef, GeneratedWorkflowDefinitionRef>
export type DecisionTableRefContract = AssertAssignable<DecisionTableRef, GeneratedDecisionTableRef>
export type PoolWorkflowBindingSelectorContract = AssertAssignable<PoolWorkflowBindingSelector, GeneratedPoolWorkflowBindingSelector>
export type PoolWorkflowBindingContract = AssertAssignable<PoolWorkflowBinding, GeneratedPoolWorkflowBinding>
export type PoolWorkflowBindingInputContract = AssertAssignable<PoolWorkflowBindingInput, GeneratedPoolWorkflowBindingInput>
export type OrganizationPoolContract = AssertAssignable<OrganizationPool, GeneratedOrganizationPool>
export type PoolSchemaTemplateContract = AssertAssignable<PoolSchemaTemplate, GeneratedPoolSchemaTemplate>
export type PoolTopologyTemplateRevisionContract = AssertAssignable<
  PoolTopologyTemplateRevision,
  GeneratedPoolTopologyTemplateRevision
>
export type PoolTopologyTemplateContract = AssertAssignable<
  PoolTopologyTemplate,
  GeneratedPoolTopologyTemplate
>
export type PoolTopologyTemplateListResponseContract = AssertAssignable<
  PoolTopologyTemplateListResponse,
  GeneratedPoolTopologyTemplateListResponse
>
export type PoolTopologyTemplateMutationResponseContract = AssertAssignable<
  PoolTopologyTemplateMutationResponse,
  GeneratedTopologyTemplateMutationResponse
>
export type PoolRunContract = AssertAssignable<PoolRun, GeneratedPoolRun>
export type PoolRunReportContract = AssertAssignable<PoolRunReport, GeneratedPoolRunReportResponse>
export type PoolGraphContract = AssertAssignable<PoolGraph, GeneratedPoolGraphResponse>
export type PoolBatchSettlementContract = AssertAssignable<PoolBatchSettlement, GeneratedPoolBatchSettlement>
export type PoolBatchContract = AssertAssignable<PoolBatch, GeneratedPoolBatchContractShape>
export type PoolBatchListResponseContract = AssertAssignable<PoolBatchListResponse, GeneratedPoolBatchListResponseContractShape>
export type PoolBatchCreateResponseContract = AssertAssignable<PoolBatchCreateResponse, GeneratedPoolBatchCreateResponseContractShape>
export type PoolFactualSummaryContract = AssertAssignable<PoolFactualSummary, GeneratedPoolFactualSummary>
export type PoolFactualEdgeBalanceContract = AssertAssignable<PoolFactualEdgeBalance, GeneratedPoolFactualBalanceSnapshot>
export type PoolFactualRefreshResponseContract = AssertAssignable<PoolFactualRefreshResponse, GeneratedPoolFactualRefreshResponse>
export type PoolFactualReviewQueueItemContract = AssertAssignable<PoolFactualReviewQueueItem, GeneratedPoolFactualReviewQueueItem>
export type PoolFactualReviewQueueContract = AssertAssignable<PoolFactualReviewQueue, GeneratedPoolFactualReviewQueue>
export type PoolFactualWorkspaceContract = AssertAssignable<PoolFactualWorkspace, GeneratedPoolFactualWorkspaceResponseContractShape>
export type PoolFactualReviewActionResponseContract = AssertAssignable<PoolFactualReviewActionResponse, GeneratedPoolFactualReviewActionResponse>
export type PoolRunSafeCommandResponseContract = AssertAssignable<PoolRunSafeCommandResponse, GeneratedPoolRunSafeCommandResponse>
export type PoolRunSafeCommandConflictContract = AssertAssignable<PoolRunSafeCommandConflict, GeneratedPoolRunSafeCommandConflict>
export type PoolRunRetryAcceptedResponseContract = AssertAssignable<PoolRunRetryAcceptedResponse, GeneratedPoolRunRetryAcceptedResponse>

export type PoolBatchCreatePayloadContract = AssertAssignable<PoolBatchCreatePayload, GeneratedPoolBatchCreateRequest>
export type GeneratedPoolBatchCreateRequestContract = AssertAssignable<
  GeneratedPoolBatchCreateRequest,
  PoolBatchCreatePayload
>
export type CreatePoolTopologyTemplatePayloadContract = AssertAssignable<
  CreatePoolTopologyTemplatePayload,
  GeneratedTopologyTemplateCreateRequest
>
export type CreatePoolTopologyTemplateRevisionPayloadContract = AssertAssignable<
  CreatePoolTopologyTemplateRevisionPayload,
  GeneratedTopologyTemplateRevisionCreateRequest
>
export type CreatePoolRunPayloadContract = AssertAssignable<CreatePoolRunPayload, GeneratedPoolRunCreateRequest>
export type RetryPoolRunPayloadContract = AssertAssignable<RetryPoolRunPayload, GeneratedPoolRunRetryRequest>
export type UpsertOrganizationPoolPayloadContract = AssertAssignable<UpsertOrganizationPoolPayload, GeneratedOrganizationPoolUpsertRequest>
export type UpsertPoolTopologySnapshotPayloadContract = AssertAssignable<
  UpsertPoolTopologySnapshotPayload,
  GeneratedPoolTopologySnapshotUpsertRequest
>

export {}
