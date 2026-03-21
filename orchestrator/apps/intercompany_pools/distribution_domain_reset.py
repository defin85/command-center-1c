from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import UUID

from django.db.models import Q

from apps.intercompany_pools.master_data_sync_workflow_template import (
    POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME,
)
from apps.intercompany_pools.models import (
    BindingProfile,
    BindingProfileRevision,
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncOutbox,
    PoolMasterParty,
    PoolNodeVersion,
    PoolPublicationAttempt,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunCommandLog,
    PoolRunCommandOutbox,
    PoolRunCommandOutboxStatus,
    PoolRuntimeStepIdempotencyLog,
    PoolSchemaTemplate,
    PoolWorkflowBinding,
)
from apps.operations.models import BatchOperation, Task, WorkflowEnqueueOutbox
from apps.templates.workflow.models import DecisionTable, WorkflowExecution, WorkflowStepResult, WorkflowTemplate
from apps.tenancy.models import Tenant

SCHEMA_VERSION = "distribution_domain_reset.v1"
RESET_PROFILE = "full_distribution_reset"

BLOCKER_ACTIVE_RUNS = "DISTRIBUTION_RESET_ACTIVE_RUNS_PRESENT"
BLOCKER_PENDING_RUN_COMMAND_OUTBOX = "DISTRIBUTION_RESET_PENDING_RUN_COMMAND_OUTBOX_PRESENT"
BLOCKER_ACTIVE_WORKFLOW_EXECUTIONS = "DISTRIBUTION_RESET_ACTIVE_WORKFLOW_EXECUTIONS_PRESENT"
BLOCKER_PENDING_WORKFLOW_ENQUEUE_OUTBOX = "DISTRIBUTION_RESET_PENDING_WORKFLOW_ENQUEUE_OUTBOX_PRESENT"
BLOCKER_SHARED_WORKFLOW_TEMPLATES = "DISTRIBUTION_RESET_SHARED_WORKFLOW_TEMPLATES_PRESENT"
BLOCKER_SHARED_DECISION_TABLES = "DISTRIBUTION_RESET_SHARED_DECISION_TABLES_PRESENT"

RUN_TERMINAL_STATUSES = frozenset(
    {
        PoolRun.STATUS_PARTIAL_SUCCESS,
        PoolRun.STATUS_PUBLISHED,
        PoolRun.STATUS_FAILED,
    }
)
EXECUTION_TERMINAL_STATUSES = frozenset(
    {
        WorkflowExecution.STATUS_COMPLETED,
        WorkflowExecution.STATUS_FAILED,
        WorkflowExecution.STATUS_CANCELLED,
    }
)

DecisionRevisionKey = tuple[str, int]


@dataclass(frozen=True)
class DistributionDomainResetBlocker:
    code: str
    count: int
    detail: str
    sample_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "count": self.count,
            "detail": self.detail,
            "sample_ids": list(self.sample_ids),
        }


@dataclass
class DistributionDomainResetResult:
    tenant_id: str
    tenant_slug: str
    execution_mode: str
    overall_status: str
    candidate_counts: dict[str, int]
    preserved_counts: dict[str, int]
    deleted_counts: dict[str, int]
    blockers: list[DistributionDomainResetBlocker] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "capability": "distribution-domain-reset",
            "profile": RESET_PROFILE,
            "execution_mode": self.execution_mode,
            "overall_status": self.overall_status,
            "tenant": {
                "id": self.tenant_id,
                "slug": self.tenant_slug,
            },
            "candidate_counts": dict(self.candidate_counts),
            "preserved_counts": dict(self.preserved_counts),
            "deleted_counts": dict(self.deleted_counts),
            "blockers": [item.to_dict() for item in self.blockers],
        }


@dataclass(frozen=True)
class _DistributionScope:
    tenant_id: UUID
    pool_ids: tuple[UUID, ...]
    binding_profile_ids: tuple[UUID, ...]
    binding_profile_revision_ids: tuple[str, ...]
    binding_ids: tuple[str, ...]
    schema_template_ids: tuple[UUID, ...]
    run_ids: tuple[UUID, ...]
    execution_ids: tuple[UUID, ...]
    workflow_template_ids: tuple[UUID, ...]
    decision_table_row_ids: tuple[UUID, ...]
    decision_pairs_by_row_id: dict[UUID, DecisionRevisionKey]
    candidate_counts: dict[str, int]
    preserved_counts: dict[str, int]


def run_distribution_domain_reset(*, tenant: Tenant, apply: bool) -> DistributionDomainResetResult:
    scope = _build_distribution_scope(tenant=tenant)
    blockers = _build_blockers(scope=scope)
    deleted_counts = _zero_counts(scope.candidate_counts)
    overall_status = "dry_run"
    execution_mode = "apply" if apply else "dry_run"

    if not apply:
        return DistributionDomainResetResult(
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            execution_mode=execution_mode,
            overall_status=overall_status,
            candidate_counts=scope.candidate_counts,
            preserved_counts=scope.preserved_counts,
            deleted_counts=deleted_counts,
            blockers=blockers,
        )

    if blockers:
        return DistributionDomainResetResult(
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            execution_mode=execution_mode,
            overall_status="blocked",
            candidate_counts=scope.candidate_counts,
            preserved_counts=scope.preserved_counts,
            deleted_counts=deleted_counts,
            blockers=blockers,
        )

    _delete_distribution_scope(scope=scope)
    return DistributionDomainResetResult(
        tenant_id=str(tenant.id),
        tenant_slug=tenant.slug,
        execution_mode=execution_mode,
        overall_status="applied",
        candidate_counts=scope.candidate_counts,
        preserved_counts=scope.preserved_counts,
        deleted_counts=dict(scope.candidate_counts),
        blockers=[],
    )


def _build_distribution_scope(*, tenant: Tenant) -> _DistributionScope:
    pool_ids = _sorted_uuid_tuple(OrganizationPool.objects.filter(tenant=tenant).values_list("id", flat=True))
    binding_profile_ids = _sorted_uuid_tuple(BindingProfile.objects.filter(tenant=tenant).values_list("id", flat=True))
    binding_profile_revision_rows = list(
        BindingProfileRevision.objects.filter(tenant=tenant).values(
            "binding_profile_revision_id",
            "workflow_revision_id",
            "decisions",
        )
    )
    binding_profile_revision_ids = tuple(
        sorted(
            (str(row["binding_profile_revision_id"]) for row in binding_profile_revision_rows),
            key=str,
        )
    )
    binding_rows = list(
        PoolWorkflowBinding.objects.filter(tenant=tenant).values(
            "binding_id",
            "workflow_revision_id",
            "decisions",
        )
    )
    binding_ids = tuple(sorted((str(row["binding_id"]) for row in binding_rows), key=str))
    schema_template_rows = list(
        PoolSchemaTemplate.objects.filter(tenant=tenant).values("id", "metadata")
    )
    schema_template_ids = _sorted_uuid_tuple(row["id"] for row in schema_template_rows)
    run_rows = list(
        PoolRun.objects.filter(tenant=tenant).values(
            "id",
            "workflow_execution_id",
            "workflow_binding_snapshot",
            "runtime_projection_snapshot",
        )
    )
    run_ids = _sorted_uuid_tuple(row["id"] for row in run_rows)
    run_id_tokens = {str(run_id) for run_id in run_ids}

    workflow_template_ids, decision_pairs = _collect_distribution_refs(
        binding_profile_revision_rows=binding_profile_revision_rows,
        binding_rows=binding_rows,
        run_rows=run_rows,
        schema_template_rows=schema_template_rows,
    )
    execution_rows = _collect_candidate_execution_rows(
        tenant_id=tenant.id,
        run_id_tokens=run_id_tokens,
        direct_execution_ids={
            execution_id
            for execution_id in (row.get("workflow_execution_id") for row in run_rows)
            if isinstance(execution_id, UUID)
        },
    )
    execution_ids = _sorted_uuid_tuple(execution_rows.keys())
    for row in execution_rows.values():
        workflow_template_id = row.get("workflow_template_id")
        if isinstance(workflow_template_id, UUID):
            workflow_template_ids.add(workflow_template_id)

    system_managed_template_ids = set(
        WorkflowTemplate.objects.filter(
            id__in=workflow_template_ids,
            name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME,
        ).values_list("id", flat=True)
    )
    workflow_template_ids.difference_update(system_managed_template_ids)
    workflow_template_id_tuple = _sorted_uuid_tuple(workflow_template_ids)

    decision_rows = _resolve_decision_rows(decision_pairs=decision_pairs)
    decision_table_row_ids = _sorted_uuid_tuple(row.id for row in decision_rows)
    decision_pairs_by_row_id = {
        row.id: (row.decision_table_id, row.version_number)
        for row in decision_rows
    }

    execution_id_tokens = [str(execution_id) for execution_id in execution_ids]
    candidate_counts = {
        "organization_pools": len(pool_ids),
        "pool_node_versions": PoolNodeVersion.objects.filter(pool_id__in=pool_ids).count(),
        "pool_edge_versions": PoolEdgeVersion.objects.filter(pool_id__in=pool_ids).count(),
        "pool_workflow_bindings": len(binding_ids),
        "pool_schema_templates": len(schema_template_ids),
        "pool_runs": len(run_ids),
        "pool_run_audit_events": PoolRunAuditEvent.objects.filter(run_id__in=run_ids).count(),
        "pool_run_command_logs": PoolRunCommandLog.objects.filter(run_id__in=run_ids).count(),
        "pool_runtime_step_idempotency_logs": PoolRuntimeStepIdempotencyLog.objects.filter(
            run_id__in=run_ids
        ).count(),
        "pool_run_command_outbox": PoolRunCommandOutbox.objects.filter(run_id__in=run_ids).count(),
        "pool_publication_attempts": PoolPublicationAttempt.objects.filter(run_id__in=run_ids).count(),
        "binding_profiles": len(binding_profile_ids),
        "binding_profile_revisions": len(binding_profile_revision_ids),
        "workflow_executions": len(execution_ids),
        "workflow_step_results": WorkflowStepResult.objects.filter(
            workflow_execution_id__in=execution_ids
        ).count(),
        "workflow_enqueue_outbox": WorkflowEnqueueOutbox.objects.filter(
            operation_id__in=execution_id_tokens
        ).count(),
        "batch_operations": BatchOperation.objects.filter(id__in=execution_id_tokens).count(),
        "tasks": Task.objects.filter(batch_operation_id__in=execution_id_tokens).count(),
        "workflow_templates": len(workflow_template_id_tuple),
        "decision_tables": len(decision_table_row_ids),
    }
    preserved_counts = _build_preserved_counts(
        tenant=tenant,
        candidate_execution_ids=set(execution_ids),
    )

    return _DistributionScope(
        tenant_id=tenant.id,
        pool_ids=pool_ids,
        binding_profile_ids=binding_profile_ids,
        binding_profile_revision_ids=binding_profile_revision_ids,
        binding_ids=binding_ids,
        schema_template_ids=schema_template_ids,
        run_ids=run_ids,
        execution_ids=execution_ids,
        workflow_template_ids=workflow_template_id_tuple,
        decision_table_row_ids=decision_table_row_ids,
        decision_pairs_by_row_id=decision_pairs_by_row_id,
        candidate_counts=candidate_counts,
        preserved_counts=preserved_counts,
    )


def _build_preserved_counts(*, tenant: Tenant, candidate_execution_ids: set[UUID]) -> dict[str, int]:
    preserved_execution_ids = list(
        WorkflowExecution.objects.filter(
            tenant=tenant,
            workflow_template__name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME,
        )
        .exclude(id__in=candidate_execution_ids)
        .values_list("id", flat=True)
    )
    return {
        "organizations": Organization.objects.filter(tenant=tenant).count(),
        "pool_master_parties": PoolMasterParty.objects.filter(tenant=tenant).count(),
        "pool_master_data_sync_checkpoints": PoolMasterDataSyncCheckpoint.objects.filter(tenant=tenant).count(),
        "pool_master_data_sync_outbox": PoolMasterDataSyncOutbox.objects.filter(tenant=tenant).count(),
        "pool_master_data_sync_conflicts": PoolMasterDataSyncConflict.objects.filter(tenant=tenant).count(),
        "pool_master_data_sync_jobs": PoolMasterDataSyncJob.objects.filter(tenant=tenant).count(),
        "system_managed_master_data_workflow_templates": WorkflowTemplate.objects.filter(
            name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME
        ).count(),
        "system_managed_master_data_workflow_executions": len(preserved_execution_ids),
        "system_managed_master_data_workflow_enqueue_outbox": WorkflowEnqueueOutbox.objects.filter(
            operation_id__in=[str(execution_id) for execution_id in preserved_execution_ids]
        ).count(),
    }


def _build_blockers(*, scope: _DistributionScope) -> list[DistributionDomainResetBlocker]:
    blockers: list[DistributionDomainResetBlocker] = []
    active_run_ids = list(
        PoolRun.objects.filter(id__in=scope.run_ids)
        .exclude(status__in=RUN_TERMINAL_STATUSES)
        .values_list("id", flat=True)
    )
    if active_run_ids:
        blockers.append(
            DistributionDomainResetBlocker(
                code=BLOCKER_ACTIVE_RUNS,
                count=len(active_run_ids),
                detail="Detected non-terminal pool runs inside the distribution reset scope.",
                sample_ids=_sample_ids(active_run_ids),
            )
        )

    pending_run_command_outbox_ids = list(
        PoolRunCommandOutbox.objects.filter(
            run_id__in=scope.run_ids,
            status=PoolRunCommandOutboxStatus.PENDING,
        ).values_list("id", flat=True)
    )
    if pending_run_command_outbox_ids:
        blockers.append(
            DistributionDomainResetBlocker(
                code=BLOCKER_PENDING_RUN_COMMAND_OUTBOX,
                count=len(pending_run_command_outbox_ids),
                detail="Detected pending pool run command outbox rows inside the distribution reset scope.",
                sample_ids=_sample_ids(pending_run_command_outbox_ids),
            )
        )

    active_execution_ids = list(
        WorkflowExecution.objects.filter(id__in=scope.execution_ids)
        .exclude(status__in=EXECUTION_TERMINAL_STATUSES)
        .values_list("id", flat=True)
    )
    if active_execution_ids:
        blockers.append(
            DistributionDomainResetBlocker(
                code=BLOCKER_ACTIVE_WORKFLOW_EXECUTIONS,
                count=len(active_execution_ids),
                detail="Detected non-terminal workflow executions linked to distribution pool runs.",
                sample_ids=_sample_ids(active_execution_ids),
            )
        )

    pending_workflow_outbox_ids = list(
        WorkflowEnqueueOutbox.objects.filter(
            operation_id__in=[str(execution_id) for execution_id in scope.execution_ids],
            status=WorkflowEnqueueOutbox.STATUS_PENDING,
        ).values_list("id", flat=True)
    )
    if pending_workflow_outbox_ids:
        blockers.append(
            DistributionDomainResetBlocker(
                code=BLOCKER_PENDING_WORKFLOW_ENQUEUE_OUTBOX,
                count=len(pending_workflow_outbox_ids),
                detail="Detected pending workflow enqueue outbox rows linked to distribution executions.",
                sample_ids=_sample_ids(pending_workflow_outbox_ids),
            )
        )

    shared_workflow_template_ids = _find_shared_workflow_template_ids(scope=scope)
    if shared_workflow_template_ids:
        blockers.append(
            DistributionDomainResetBlocker(
                code=BLOCKER_SHARED_WORKFLOW_TEMPLATES,
                count=len(shared_workflow_template_ids),
                detail=(
                    "Detected workflow templates that are also referenced outside the target tenant "
                    "distribution lineage."
                ),
                sample_ids=_sample_ids(shared_workflow_template_ids),
            )
        )

    shared_decision_table_ids = _find_shared_decision_table_row_ids(scope=scope)
    if shared_decision_table_ids:
        blockers.append(
            DistributionDomainResetBlocker(
                code=BLOCKER_SHARED_DECISION_TABLES,
                count=len(shared_decision_table_ids),
                detail=(
                    "Detected decision tables that are also referenced outside the target tenant "
                    "distribution lineage."
                ),
                sample_ids=_sample_ids(shared_decision_table_ids),
            )
        )

    return blockers


def _find_shared_workflow_template_ids(*, scope: _DistributionScope) -> tuple[UUID, ...]:
    candidate_ids = set(scope.workflow_template_ids)
    if not candidate_ids:
        return ()

    shared_ids: set[UUID] = set()
    other_binding_profile_rows = BindingProfileRevision.objects.exclude(tenant_id=scope.tenant_id).values(
        "workflow_revision_id"
    )
    other_binding_rows = PoolWorkflowBinding.objects.exclude(tenant_id=scope.tenant_id).values(
        "workflow_revision_id"
    )
    other_run_rows = PoolRun.objects.exclude(tenant_id=scope.tenant_id).values(
        "workflow_binding_snapshot",
        "runtime_projection_snapshot",
    )
    other_schema_template_rows = PoolSchemaTemplate.objects.exclude(tenant_id=scope.tenant_id).values(
        "metadata"
    )
    other_workflow_ids, _ = _collect_distribution_refs(
        binding_profile_revision_rows=other_binding_profile_rows,
        binding_rows=other_binding_rows,
        run_rows=other_run_rows,
        schema_template_rows=other_schema_template_rows,
    )
    shared_ids.update(candidate_ids.intersection(other_workflow_ids))

    referenced_by_other_executions = set(
        WorkflowExecution.objects.filter(workflow_template_id__in=candidate_ids)
        .exclude(id__in=scope.execution_ids)
        .values_list("workflow_template_id", flat=True)
    )
    shared_ids.update(referenced_by_other_executions)
    return _sorted_uuid_tuple(shared_ids)


def _find_shared_decision_table_row_ids(*, scope: _DistributionScope) -> tuple[UUID, ...]:
    if not scope.decision_pairs_by_row_id:
        return ()

    candidate_pairs = set(scope.decision_pairs_by_row_id.values())
    other_binding_profile_rows = BindingProfileRevision.objects.exclude(tenant_id=scope.tenant_id).values(
        "decisions"
    )
    other_binding_rows = PoolWorkflowBinding.objects.exclude(tenant_id=scope.tenant_id).values("decisions")
    other_run_rows = PoolRun.objects.exclude(tenant_id=scope.tenant_id).values(
        "workflow_binding_snapshot",
        "runtime_projection_snapshot",
    )
    shared_pairs = _collect_decision_pairs_from_distribution_rows(
        binding_profile_revision_rows=other_binding_profile_rows,
        binding_rows=other_binding_rows,
        run_rows=other_run_rows,
    )
    shared_pairs.update(_collect_decision_pairs_from_noncandidate_workflows(scope=scope))

    shared_row_ids = {
        row_id
        for row_id, pair in scope.decision_pairs_by_row_id.items()
        if pair in candidate_pairs and pair in shared_pairs
    }
    return _sorted_uuid_tuple(shared_row_ids)


def _collect_decision_pairs_from_noncandidate_workflows(*, scope: _DistributionScope) -> set[DecisionRevisionKey]:
    shared_pairs: set[DecisionRevisionKey] = set()
    candidate_pairs = set(scope.decision_pairs_by_row_id.values())
    if not candidate_pairs:
        return shared_pairs

    for row in WorkflowTemplate.objects.exclude(id__in=scope.workflow_template_ids).values("dag_structure").iterator():
        dag = _normalize_mapping(row.get("dag_structure"))
        for node in dag.get("nodes", []):
            if not isinstance(node, dict):
                continue
            decision_ref = _normalize_mapping(node.get("decision_ref"))
            pair = _extract_decision_pair(decision_ref)
            if pair is not None and pair in candidate_pairs:
                shared_pairs.add(pair)
    return shared_pairs


def _collect_distribution_refs(
    *,
    binding_profile_revision_rows: Iterable[dict[str, Any]],
    binding_rows: Iterable[dict[str, Any]],
    run_rows: Iterable[dict[str, Any]],
    schema_template_rows: Iterable[dict[str, Any]],
) -> tuple[set[UUID], set[DecisionRevisionKey]]:
    workflow_template_ids: set[UUID] = set()
    decision_pairs: set[DecisionRevisionKey] = set()

    for row in binding_profile_revision_rows:
        _append_uuid(workflow_template_ids, row.get("workflow_revision_id"))
        decision_pairs.update(_iter_decision_pairs(row.get("decisions")))

    for row in binding_rows:
        _append_uuid(workflow_template_ids, row.get("workflow_revision_id"))
        decision_pairs.update(_iter_decision_pairs(row.get("decisions")))

    for row in schema_template_rows:
        metadata = _normalize_mapping(row.get("metadata"))
        _append_uuid(workflow_template_ids, metadata.get("workflow_template_id"))

    for row in run_rows:
        workflow_binding_snapshot = _normalize_mapping(row.get("workflow_binding_snapshot"))
        runtime_projection_snapshot = _normalize_mapping(row.get("runtime_projection_snapshot"))
        runtime_workflow_binding = _normalize_mapping(runtime_projection_snapshot.get("workflow_binding"))
        document_policy_projection = _normalize_mapping(
            runtime_projection_snapshot.get("document_policy_projection")
        )
        compiled_slots = _normalize_mapping(document_policy_projection.get("compiled_document_policy_slots"))

        _append_uuid(workflow_template_ids, workflow_binding_snapshot.get("workflow_revision_id"))
        _append_uuid(workflow_template_ids, runtime_workflow_binding.get("workflow_revision_id"))
        decision_pairs.update(_iter_decision_pairs(workflow_binding_snapshot.get("decision_refs")))
        decision_pairs.update(_iter_decision_pairs(runtime_workflow_binding.get("decision_refs")))
        for slot in compiled_slots.values():
            pair = _extract_decision_pair(_normalize_mapping(slot))
            if pair is not None:
                decision_pairs.add(pair)

    return workflow_template_ids, decision_pairs


def _collect_decision_pairs_from_distribution_rows(
    *,
    binding_profile_revision_rows: Iterable[dict[str, Any]],
    binding_rows: Iterable[dict[str, Any]],
    run_rows: Iterable[dict[str, Any]],
) -> set[DecisionRevisionKey]:
    _, decision_pairs = _collect_distribution_refs(
        binding_profile_revision_rows=binding_profile_revision_rows,
        binding_rows=binding_rows,
        run_rows=run_rows,
        schema_template_rows=(),
    )
    return decision_pairs


def _collect_candidate_execution_rows(
    *,
    tenant_id: UUID,
    run_id_tokens: set[str],
    direct_execution_ids: set[UUID],
) -> dict[UUID, dict[str, Any]]:
    execution_rows: dict[UUID, dict[str, Any]] = {}
    if direct_execution_ids:
        for row in WorkflowExecution.objects.filter(id__in=direct_execution_ids).values(
            "id",
            "tenant_id",
            "status",
            "workflow_template_id",
            "input_context",
        ):
            execution_rows[row["id"]] = row

    if not run_id_tokens:
        return execution_rows

    for row in WorkflowExecution.objects.filter(execution_consumer="pools").values(
        "id",
        "tenant_id",
        "status",
        "workflow_template_id",
        "input_context",
    ).iterator():
        execution_id = row["id"]
        if execution_id in execution_rows:
            continue
        input_context = _normalize_mapping(row.get("input_context"))
        raw_pool_run_id = str(input_context.get("pool_run_id") or "").strip()
        if raw_pool_run_id not in run_id_tokens:
            continue
        if row.get("tenant_id") not in {tenant_id, None}:
            continue
        execution_rows[execution_id] = row

    return execution_rows


def _resolve_decision_rows(decision_pairs: set[DecisionRevisionKey]) -> list[DecisionTable]:
    if not decision_pairs:
        return []

    predicate = Q()
    for decision_table_id, decision_revision in decision_pairs:
        predicate |= Q(decision_table_id=decision_table_id, version_number=decision_revision)
    return list(DecisionTable.objects.filter(predicate).only("id", "decision_table_id", "version_number"))


def _delete_distribution_scope(*, scope: _DistributionScope) -> None:
    execution_id_tokens = [str(execution_id) for execution_id in scope.execution_ids]

    if scope.run_ids:
        PoolRunCommandOutbox.objects.filter(run_id__in=scope.run_ids).delete()
        PoolRuntimeStepIdempotencyLog.objects.filter(run_id__in=scope.run_ids).delete()
        PoolRunCommandLog.objects.filter(run_id__in=scope.run_ids).delete()
        PoolRunAuditEvent.objects.filter(run_id__in=scope.run_ids).delete()
        PoolPublicationAttempt.objects.filter(run_id__in=scope.run_ids).delete()

    if scope.execution_ids:
        WorkflowStepResult.objects.filter(workflow_execution_id__in=scope.execution_ids).delete()
        WorkflowEnqueueOutbox.objects.filter(operation_id__in=execution_id_tokens).delete()
        Task.objects.filter(batch_operation_id__in=execution_id_tokens).delete()
        BatchOperation.objects.filter(id__in=execution_id_tokens).delete()
        WorkflowExecution.objects.filter(id__in=scope.execution_ids).delete()

    if scope.run_ids:
        PoolRun.objects.filter(id__in=scope.run_ids).delete()
    if scope.binding_ids:
        PoolWorkflowBinding.objects.filter(binding_id__in=scope.binding_ids).delete()
    if scope.schema_template_ids:
        PoolSchemaTemplate.objects.filter(id__in=scope.schema_template_ids).delete()
    if scope.binding_profile_revision_ids:
        BindingProfileRevision.objects.filter(
            binding_profile_revision_id__in=scope.binding_profile_revision_ids
        ).delete()
    if scope.binding_profile_ids:
        BindingProfile.objects.filter(id__in=scope.binding_profile_ids).delete()
    if scope.pool_ids:
        PoolEdgeVersion.objects.filter(pool_id__in=scope.pool_ids).delete()
        PoolNodeVersion.objects.filter(pool_id__in=scope.pool_ids).delete()
        OrganizationPool.objects.filter(id__in=scope.pool_ids).delete()
    if scope.workflow_template_ids:
        WorkflowTemplate.objects.filter(id__in=scope.workflow_template_ids).delete()
    if scope.decision_table_row_ids:
        DecisionTable.objects.filter(id__in=scope.decision_table_row_ids).delete()


def _iter_decision_pairs(raw_refs: object) -> Iterable[DecisionRevisionKey]:
    if not isinstance(raw_refs, list):
        return ()
    return tuple(
        pair
        for item in raw_refs
        if isinstance(item, dict)
        if (pair := _extract_decision_pair(item)) is not None
    )


def _extract_decision_pair(raw_ref: dict[str, Any]) -> DecisionRevisionKey | None:
    decision_table_id = str(raw_ref.get("decision_table_id") or "").strip()
    try:
        decision_revision = int(raw_ref.get("decision_revision"))
    except (TypeError, ValueError):
        return None
    if not decision_table_id or decision_revision < 1:
        return None
    return decision_table_id, decision_revision


def _append_uuid(target: set[UUID], raw_value: object) -> None:
    parsed = _parse_uuid(raw_value)
    if parsed is not None:
        target.add(parsed)


def _parse_uuid(raw_value: object) -> UUID | None:
    try:
        token = str(raw_value or "").strip()
    except Exception:
        return None
    if not token:
        return None
    try:
        return UUID(token)
    except (ValueError, TypeError, AttributeError):
        return None


def _normalize_mapping(raw_value: object) -> dict[str, Any]:
    if hasattr(raw_value, "model_dump"):
        dumped = raw_value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(raw_value, dict):
        return raw_value
    return {}


def _sample_ids(values: Iterable[object], *, limit: int = 5) -> tuple[str, ...]:
    return tuple(sorted((str(value) for value in values), key=str)[:limit])


def _sorted_uuid_tuple(values: Iterable[object]) -> tuple[UUID, ...]:
    unique_values = {
        value
        for value in values
        if isinstance(value, UUID)
    }
    return tuple(sorted(unique_values, key=str))


def _zero_counts(candidate_counts: dict[str, int]) -> dict[str, int]:
    return {key: 0 for key in candidate_counts}
