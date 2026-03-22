import type {
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
import type { PoolRun as GeneratedPoolRun } from './generated/model/poolRun'
import type { PoolRunCreateRequest as GeneratedPoolRunCreateRequest } from './generated/model/poolRunCreateRequest'
import type { PoolRunReportResponse as GeneratedPoolRunReportResponse } from './generated/model/poolRunReportResponse'
import type { PoolRunRetryAcceptedResponse as GeneratedPoolRunRetryAcceptedResponse } from './generated/model/poolRunRetryAcceptedResponse'
import type { PoolRunRetryRequest as GeneratedPoolRunRetryRequest } from './generated/model/poolRunRetryRequest'
import type { PoolRunSafeCommandConflict as GeneratedPoolRunSafeCommandConflict } from './generated/model/poolRunSafeCommandConflict'
import type { PoolRunSafeCommandResponse as GeneratedPoolRunSafeCommandResponse } from './generated/model/poolRunSafeCommandResponse'
import type { PoolSchemaTemplate as GeneratedPoolSchemaTemplate } from './generated/model/poolSchemaTemplate'
import type { PoolTopologySnapshotUpsertRequest as GeneratedPoolTopologySnapshotUpsertRequest } from './generated/model/poolTopologySnapshotUpsertRequest'
import type { PoolWorkflowBindingInput as GeneratedPoolWorkflowBindingInput } from './generated/model/poolWorkflowBindingInput'
import type { PoolWorkflowBindingRead as GeneratedPoolWorkflowBinding } from './generated/model/poolWorkflowBindingRead'
import type { PoolWorkflowBindingSelector as GeneratedPoolWorkflowBindingSelector } from './generated/model/poolWorkflowBindingSelector'
import type { WorkflowDefinitionRef as GeneratedWorkflowDefinitionRef } from './generated/model/workflowDefinitionRef'

type AssertAssignable<TActual extends TExpected, TExpected> = TActual

export type WorkflowDefinitionRefContract = AssertAssignable<WorkflowDefinitionRef, GeneratedWorkflowDefinitionRef>
export type DecisionTableRefContract = AssertAssignable<DecisionTableRef, GeneratedDecisionTableRef>
export type PoolWorkflowBindingSelectorContract = AssertAssignable<PoolWorkflowBindingSelector, GeneratedPoolWorkflowBindingSelector>
export type PoolWorkflowBindingContract = AssertAssignable<PoolWorkflowBinding, GeneratedPoolWorkflowBinding>
export type PoolWorkflowBindingInputContract = AssertAssignable<PoolWorkflowBindingInput, GeneratedPoolWorkflowBindingInput>
export type OrganizationPoolContract = AssertAssignable<OrganizationPool, GeneratedOrganizationPool>
export type PoolSchemaTemplateContract = AssertAssignable<PoolSchemaTemplate, GeneratedPoolSchemaTemplate>
export type PoolRunContract = AssertAssignable<PoolRun, GeneratedPoolRun>
export type PoolRunReportContract = AssertAssignable<PoolRunReport, GeneratedPoolRunReportResponse>
export type PoolGraphContract = AssertAssignable<PoolGraph, GeneratedPoolGraphResponse>
export type PoolRunSafeCommandResponseContract = AssertAssignable<PoolRunSafeCommandResponse, GeneratedPoolRunSafeCommandResponse>
export type PoolRunSafeCommandConflictContract = AssertAssignable<PoolRunSafeCommandConflict, GeneratedPoolRunSafeCommandConflict>
export type PoolRunRetryAcceptedResponseContract = AssertAssignable<PoolRunRetryAcceptedResponse, GeneratedPoolRunRetryAcceptedResponse>

export type CreatePoolRunPayloadContract = AssertAssignable<CreatePoolRunPayload, GeneratedPoolRunCreateRequest>
export type RetryPoolRunPayloadContract = AssertAssignable<RetryPoolRunPayload, GeneratedPoolRunRetryRequest>
export type UpsertOrganizationPoolPayloadContract = AssertAssignable<UpsertOrganizationPoolPayload, GeneratedOrganizationPoolUpsertRequest>
export type UpsertPoolTopologySnapshotPayloadContract = AssertAssignable<
  UpsertPoolTopologySnapshotPayload,
  GeneratedPoolTopologySnapshotUpsertRequest
>

export {}
