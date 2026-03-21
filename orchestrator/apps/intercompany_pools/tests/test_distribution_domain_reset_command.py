from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_workflow_template import (
    ensure_pool_master_data_sync_workflow_template,
)
from apps.intercompany_pools.models import (
    BindingProfile,
    BindingProfileRevision,
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterParty,
    PoolNodeVersion,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunCommandLog,
    PoolRunCommandOutbox,
    PoolRunCommandOutboxIntent,
    PoolRunCommandOutboxStatus,
    PoolRunCommandResultClass,
    PoolRunCommandType,
    PoolRuntimeStepIdempotencyLog,
    PoolSchemaTemplate,
    PoolWorkflowBinding,
)
from apps.operations.models import BatchOperation, Task, WorkflowEnqueueOutbox
from apps.templates.workflow.models import DecisionTable, WorkflowExecution, WorkflowStepResult, WorkflowTemplate
from apps.tenancy.models import Tenant


User = get_user_model()


@dataclass(frozen=True)
class DistributionFixture:
    tenant: Tenant
    database: Database
    organization_ids: tuple[UUID, UUID]
    pool_id: UUID
    binding_profile_id: UUID
    binding_profile_revision_id: str
    binding_id: str
    schema_template_id: UUID
    run_id: UUID
    execution_id: UUID
    workflow_template_id: UUID
    decision_table_row_id: UUID
    decision_table_id: str


def _token(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create_user(*, username: str) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="testpass123",
        is_staff=True,
    )


def _create_tenant(*, slug_prefix: str) -> Tenant:
    token = _token(slug_prefix)
    return Tenant.objects.create(
        slug=token,
        name=f"{token} tenant",
    )


def _create_database(*, tenant: Tenant, name_prefix: str) -> Database:
    token = _token(name_prefix)
    return Database.objects.create(
        tenant=tenant,
        name=token,
        description="test database",
        host="127.0.0.1",
        port=80,
        base_name=token,
        odata_url=f"http://example.test/{token}/odata",
        username="svc",
        password="secret",
    )


def _create_workflow_template(*, created_by: User, name_prefix: str) -> WorkflowTemplate:
    token = _token(name_prefix)
    return WorkflowTemplate.objects.create(
        name=token,
        description="distribution workflow",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "step-1",
                    "name": "Step 1",
                    "type": "operation",
                    "template_id": "pool.prepare_input",
                }
            ],
            "edges": [],
        },
        config={"timeout_seconds": 60},
        is_valid=True,
        is_active=True,
        created_by=created_by,
    )


def _create_decision_table(*, created_by: User, decision_table_id: str | None = None) -> DecisionTable:
    token = decision_table_id or _token("decision")
    return DecisionTable.objects.create(
        decision_table_id=token,
        decision_key="document_policy",
        name=f"{token} name",
        description="distribution decision",
        inputs=[],
        outputs=[],
        rules=[],
        hit_policy="first_match",
        validation_mode="fail_closed",
        is_active=True,
        version_number=1,
        created_by=created_by,
    )


def _build_decision_ref(*, decision: DecisionTable, slot_key: str = "sale") -> dict[str, object]:
    return {
        "decision_table_id": decision.decision_table_id,
        "decision_key": decision.decision_key,
        "decision_revision": decision.version_number,
        "slot_key": slot_key,
    }


def _create_distribution_fixture(
    *,
    tenant: Tenant,
    created_by: User,
    workflow: WorkflowTemplate | None = None,
    decision: DecisionTable | None = None,
    run_status: str = PoolRun.STATUS_FAILED,
    execution_status: str = WorkflowExecution.STATUS_COMPLETED,
    workflow_outbox_status: str = WorkflowEnqueueOutbox.STATUS_DISPATCHED,
    command_outbox_status: str = PoolRunCommandOutboxStatus.DISPATCHED,
) -> DistributionFixture:
    database = _create_database(tenant=tenant, name_prefix="dist-db")
    root_org = Organization.objects.create(
        tenant=tenant,
        name=_token("org-root"),
        inn=f"77{uuid4().int % 10**10:010d}"[:12],
    )
    child_org = Organization.objects.create(
        tenant=tenant,
        name=_token("org-child"),
        inn=f"78{uuid4().int % 10**10:010d}"[:12],
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=_token("pool"),
        name="Distribution Pool",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    child_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=child_org,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=child_node,
        weight="1.000000",
        effective_from=date(2026, 1, 1),
        metadata={"document_policy_key": "sale"},
    )

    workflow_template = workflow or _create_workflow_template(
        created_by=created_by,
        name_prefix="distribution-workflow",
    )
    decision_table = decision or _create_decision_table(created_by=created_by)

    binding_profile = BindingProfile.objects.create(
        tenant=tenant,
        code=_token("binding-profile"),
        name="Distribution Binding Profile",
        created_by=created_by.username,
        updated_by=created_by.username,
    )
    revision_id = f"bp-rev-{uuid4().hex[:12]}"
    binding_profile_revision = BindingProfileRevision.objects.create(
        binding_profile_revision_id=revision_id,
        tenant=tenant,
        profile=binding_profile,
        revision_number=1,
        workflow_definition_key=f"workflow:{workflow_template.id}",
        workflow_revision_id=str(workflow_template.id),
        workflow_revision=workflow_template.version_number,
        workflow_name=workflow_template.name,
        decisions=[_build_decision_ref(decision=decision_table)],
        parameters={"mode": "full"},
        role_mapping={"operator": "finance"},
        metadata={"source": "test"},
        created_by=created_by.username,
    )
    binding = PoolWorkflowBinding.objects.create(
        binding_id=f"binding-{uuid4().hex[:12]}",
        tenant=tenant,
        pool=pool,
        binding_profile=binding_profile,
        binding_profile_revision=binding_profile_revision,
        status="active",
        effective_from=date(2026, 1, 1),
        direction="top_down",
        mode="safe",
        selector_tags=["default"],
        workflow_definition_key=binding_profile_revision.workflow_definition_key,
        workflow_revision_id=binding_profile_revision.workflow_revision_id,
        workflow_revision=binding_profile_revision.workflow_revision,
        workflow_name=binding_profile_revision.workflow_name,
        decisions=[_build_decision_ref(decision=decision_table)],
        parameters={"mode": "full"},
        role_mapping={"operator": "finance"},
        created_by=created_by.username,
        updated_by=created_by.username,
    )
    schema_template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code=_token("schema"),
        name="Distribution Schema Template",
        format="json",
        schema={"fields": []},
        metadata={"workflow_template_id": str(workflow_template.id)},
    )
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        schema_template=schema_template,
        mode="safe",
        direction="top_down",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={"amount": 1000},
        idempotency_key=_token("run"),
        workflow_binding_snapshot={
            "binding_id": binding.binding_id,
            "workflow_revision_id": str(workflow_template.id),
            "decision_refs": [_build_decision_ref(decision=decision_table)],
            "binding_profile_revision_id": revision_id,
        },
        runtime_projection_snapshot={
            "workflow_binding": {
                "binding_id": binding.binding_id,
                "workflow_revision_id": str(workflow_template.id),
                "decision_refs": [_build_decision_ref(decision=decision_table)],
            },
            "document_policy_projection": {
                "compiled_document_policy_slots": {
                    "sale": {
                        "decision_table_id": decision_table.decision_table_id,
                        "decision_revision": decision_table.version_number,
                    }
                }
            },
        },
        workflow_template_name=workflow_template.name,
    )
    execution = workflow_template.create_execution(
        {"pool_run_id": str(run.id)},
        tenant=tenant,
        execution_consumer="pools",
    )
    WorkflowExecution.objects.filter(id=execution.id).update(status=execution_status)
    run.workflow_execution_id = execution.id
    run.workflow_status = execution_status
    run.save(update_fields=["workflow_execution_id", "workflow_status", "updated_at"])
    PoolRun.objects.filter(id=run.id).update(status=run_status)

    PoolRunAuditEvent.objects.create(
        run=run,
        tenant=tenant,
        event_type="run.created",
        status_before="",
        status_after=run_status,
        payload={"source": "test"},
        actor=created_by,
    )
    command_log = PoolRunCommandLog.objects.create(
        run=run,
        tenant=tenant,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key=_token("command"),
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_snapshot={"ok": True},
        created_by=created_by,
    )
    PoolRuntimeStepIdempotencyLog.objects.create(
        run=run,
        tenant=tenant,
        workflow_execution_id=execution.id,
        node_id="step-1",
        operation_type="execute_workflow",
        idempotency_key=_token("step"),
        request_fingerprint="fingerprint",
        response_snapshot={"status": "done"},
    )
    PoolRunCommandOutbox.objects.create(
        run=run,
        tenant=tenant,
        command_log=command_log,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        status=command_outbox_status,
        message_payload={"workflow_execution_id": str(execution.id)},
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=tenant,
        target_database=database,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_Sales",
        request_summary={"documents": 1},
        response_summary={"created": 1},
    )
    WorkflowStepResult.objects.create(
        workflow_execution=execution,
        node_id="step-1",
        node_name="Step 1",
        node_type="operation",
        status="completed",
        input_data={"pool_run_id": str(run.id)},
        output_data={"status": "done"},
    )
    BatchOperation.objects.create(
        id=str(execution.id),
        name=f"Workflow execution {execution.id}",
        description="Root workflow execution projection",
        operation_type="execute_workflow",
        target_entity="Workflow",
        status=BatchOperation.STATUS_COMPLETED,
        payload={"execution_id": str(execution.id)},
        config={},
        metadata={"workflow_execution_id": str(execution.id), "execution_consumer": "pools"},
    )
    Task.objects.create(
        id=f"task-{uuid4().hex[:10]}",
        batch_operation_id=str(execution.id),
        database=database,
        status=Task.STATUS_COMPLETED,
    )
    WorkflowEnqueueOutbox.objects.create(
        operation_id=str(execution.id),
        status=workflow_outbox_status,
        message_payload={
            "metadata": {
                "workflow_execution_id": str(execution.id),
                "execution_consumer": "pools",
                "pool_run_id": str(run.id),
            }
        },
    )

    return DistributionFixture(
        tenant=tenant,
        database=database,
        organization_ids=(root_org.id, child_org.id),
        pool_id=pool.id,
        binding_profile_id=binding_profile.id,
        binding_profile_revision_id=revision_id,
        binding_id=binding.binding_id,
        schema_template_id=schema_template.id,
        run_id=run.id,
        execution_id=execution.id,
        workflow_template_id=workflow_template.id,
        decision_table_row_id=decision_table.id,
        decision_table_id=decision_table.decision_table_id,
    )


def _create_preserved_master_data_state(*, tenant: Tenant, database: Database, created_by: User) -> dict[str, object]:
    party = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id=_token("party"),
        name="Preserved Party",
        inn="770100000001",
        is_our_organization=True,
    )
    checkpoint = PoolMasterDataSyncCheckpoint.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        checkpoint_token="checkpoint-1",
    )
    outbox = PoolMasterDataSyncOutbox.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        dedupe_key=_token("dedupe"),
        payload={"party": party.canonical_id},
    )
    conflict = PoolMasterDataSyncConflict.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="CONFLICT",
        canonical_id=party.canonical_id,
    )
    workflow_template = ensure_pool_master_data_sync_workflow_template(created_by=created_by)
    execution = workflow_template.create_execution(
        {"sync_job_id": str(uuid4())},
        tenant=tenant,
        execution_consumer="pools",
    )
    job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncJobStatus.RUNNING,
        workflow_execution_id=execution.id,
        operation_id=execution.id,
    )
    BatchOperation.objects.create(
        id=str(execution.id),
        name=f"Workflow execution {execution.id}",
        description="Root workflow execution projection",
        operation_type="execute_workflow",
        target_entity="Workflow",
        status=BatchOperation.STATUS_PROCESSING,
        payload={"execution_id": str(execution.id)},
        config={},
        metadata={"workflow_execution_id": str(execution.id), "execution_consumer": "pools", "role": "inbound"},
    )
    Task.objects.create(
        id=f"task-{uuid4().hex[:10]}",
        batch_operation_id=str(execution.id),
        database=database,
        status=Task.STATUS_PROCESSING,
    )
    workflow_outbox = WorkflowEnqueueOutbox.objects.create(
        operation_id=str(execution.id),
        status=WorkflowEnqueueOutbox.STATUS_PENDING,
        message_payload={
            "metadata": {
                "workflow_execution_id": str(execution.id),
                "execution_consumer": "pools",
                "role": "inbound",
            }
        },
    )
    return {
        "party_id": party.id,
        "checkpoint_id": checkpoint.id,
        "outbox_id": outbox.id,
        "conflict_id": conflict.id,
        "job_id": job.id,
        "workflow_template_id": workflow_template.id,
        "execution_id": execution.id,
        "workflow_outbox_id": workflow_outbox.id,
    }


@pytest.mark.django_db
def test_distribution_domain_reset_dry_run_reports_counts_without_mutation() -> None:
    tenant = _create_tenant(slug_prefix="reset-dry-run")
    user = _create_user(username=_token("user"))
    fixture = _create_distribution_fixture(tenant=tenant, created_by=user)

    stdout = io.StringIO()
    call_command(
        "reset_distribution_domain",
        "--tenant-id",
        str(tenant.id),
        "--dry-run",
        "--json",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert payload["schema_version"] == "distribution_domain_reset.v1"
    assert payload["execution_mode"] == "dry_run"
    assert payload["overall_status"] == "dry_run"
    assert payload["tenant"]["id"] == str(tenant.id)
    assert payload["blockers"] == []
    assert payload["candidate_counts"]["organization_pools"] == 1
    assert payload["candidate_counts"]["pool_runs"] == 1
    assert payload["candidate_counts"]["binding_profiles"] == 1
    assert payload["candidate_counts"]["workflow_templates"] == 1
    assert payload["candidate_counts"]["decision_tables"] == 1

    assert OrganizationPool.objects.filter(id=fixture.pool_id).exists()
    assert BindingProfile.objects.filter(id=fixture.binding_profile_id).exists()
    assert PoolRun.objects.filter(id=fixture.run_id).exists()
    assert WorkflowExecution.objects.filter(id=fixture.execution_id).exists()
    assert WorkflowTemplate.objects.filter(id=fixture.workflow_template_id).exists()
    assert DecisionTable.objects.filter(id=fixture.decision_table_row_id).exists()


@pytest.mark.django_db
def test_distribution_domain_reset_apply_deletes_distribution_and_preserves_master_data() -> None:
    tenant = _create_tenant(slug_prefix="reset-apply")
    user = _create_user(username=_token("user"))
    fixture = _create_distribution_fixture(tenant=tenant, created_by=user)
    preserved = _create_preserved_master_data_state(
        tenant=tenant,
        database=fixture.database,
        created_by=user,
    )

    stdout = io.StringIO()
    call_command(
        "reset_distribution_domain",
        "--tenant-id",
        str(tenant.id),
        "--apply",
        "--json",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert payload["execution_mode"] == "apply"
    assert payload["overall_status"] == "applied"
    assert payload["blockers"] == []
    assert payload["deleted_counts"]["organization_pools"] == 1
    assert payload["deleted_counts"]["pool_runs"] == 1
    assert payload["deleted_counts"]["workflow_templates"] == 1
    assert payload["deleted_counts"]["decision_tables"] == 1

    assert not OrganizationPool.objects.filter(id=fixture.pool_id).exists()
    assert not PoolNodeVersion.objects.filter(pool_id=fixture.pool_id).exists()
    assert not PoolEdgeVersion.objects.filter(pool_id=fixture.pool_id).exists()
    assert not BindingProfile.objects.filter(id=fixture.binding_profile_id).exists()
    assert not BindingProfileRevision.objects.filter(
        binding_profile_revision_id=fixture.binding_profile_revision_id
    ).exists()
    assert not PoolWorkflowBinding.objects.filter(binding_id=fixture.binding_id).exists()
    assert not PoolSchemaTemplate.objects.filter(id=fixture.schema_template_id).exists()
    assert not PoolRun.objects.filter(id=fixture.run_id).exists()
    assert not WorkflowExecution.objects.filter(id=fixture.execution_id).exists()
    assert not WorkflowStepResult.objects.filter(workflow_execution_id=fixture.execution_id).exists()
    assert not WorkflowEnqueueOutbox.objects.filter(operation_id=str(fixture.execution_id)).exists()
    assert not BatchOperation.objects.filter(id=str(fixture.execution_id)).exists()
    assert not WorkflowTemplate.objects.filter(id=fixture.workflow_template_id).exists()
    assert not DecisionTable.objects.filter(id=fixture.decision_table_row_id).exists()

    assert Organization.objects.filter(id__in=fixture.organization_ids).count() == 2
    assert PoolMasterParty.objects.filter(id=preserved["party_id"]).exists()
    assert PoolMasterDataSyncCheckpoint.objects.filter(id=preserved["checkpoint_id"]).exists()
    assert PoolMasterDataSyncOutbox.objects.filter(id=preserved["outbox_id"]).exists()
    assert PoolMasterDataSyncConflict.objects.filter(id=preserved["conflict_id"]).exists()
    assert PoolMasterDataSyncJob.objects.filter(id=preserved["job_id"]).exists()
    assert WorkflowTemplate.objects.filter(id=preserved["workflow_template_id"]).exists()
    assert WorkflowExecution.objects.filter(id=preserved["execution_id"]).exists()
    assert WorkflowEnqueueOutbox.objects.filter(id=preserved["workflow_outbox_id"]).exists()


@pytest.mark.django_db
def test_distribution_domain_reset_apply_blocks_on_active_distribution_runtime() -> None:
    tenant = _create_tenant(slug_prefix="reset-blockers")
    user = _create_user(username=_token("user"))
    fixture = _create_distribution_fixture(
        tenant=tenant,
        created_by=user,
        run_status=PoolRun.STATUS_DRAFT,
        execution_status=WorkflowExecution.STATUS_PENDING,
        workflow_outbox_status=WorkflowEnqueueOutbox.STATUS_PENDING,
        command_outbox_status=PoolRunCommandOutboxStatus.PENDING,
    )

    stdout = io.StringIO()
    call_command(
        "reset_distribution_domain",
        "--tenant-id",
        str(tenant.id),
        "--apply",
        "--json",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    blocker_codes = {item["code"] for item in payload["blockers"]}
    assert payload["overall_status"] == "blocked"
    assert "DISTRIBUTION_RESET_ACTIVE_RUNS_PRESENT" in blocker_codes
    assert "DISTRIBUTION_RESET_PENDING_RUN_COMMAND_OUTBOX_PRESENT" in blocker_codes
    assert "DISTRIBUTION_RESET_ACTIVE_WORKFLOW_EXECUTIONS_PRESENT" in blocker_codes
    assert "DISTRIBUTION_RESET_PENDING_WORKFLOW_ENQUEUE_OUTBOX_PRESENT" in blocker_codes

    assert OrganizationPool.objects.filter(id=fixture.pool_id).exists()
    assert PoolRun.objects.filter(id=fixture.run_id).exists()
    assert WorkflowExecution.objects.filter(id=fixture.execution_id).exists()
    assert WorkflowEnqueueOutbox.objects.filter(operation_id=str(fixture.execution_id)).exists()


@pytest.mark.django_db
def test_distribution_domain_reset_apply_blocks_when_global_artifacts_are_shared() -> None:
    shared_workflow_owner = _create_user(username=_token("shared-owner"))
    shared_workflow = _create_workflow_template(
        created_by=shared_workflow_owner,
        name_prefix="shared-workflow",
    )
    shared_decision = _create_decision_table(
        created_by=shared_workflow_owner,
        decision_table_id=_token("shared-decision"),
    )

    tenant_a = _create_tenant(slug_prefix="reset-shared-a")
    tenant_b = _create_tenant(slug_prefix="reset-shared-b")
    user_a = _create_user(username=_token("user-a"))
    user_b = _create_user(username=_token("user-b"))
    _create_distribution_fixture(
        tenant=tenant_a,
        created_by=user_a,
        workflow=shared_workflow,
        decision=shared_decision,
    )
    fixture_b = _create_distribution_fixture(
        tenant=tenant_b,
        created_by=user_b,
        workflow=shared_workflow,
        decision=shared_decision,
    )

    stdout = io.StringIO()
    call_command(
        "reset_distribution_domain",
        "--tenant-id",
        str(tenant_a.id),
        "--apply",
        "--json",
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    blocker_codes = {item["code"] for item in payload["blockers"]}
    assert payload["overall_status"] == "blocked"
    assert "DISTRIBUTION_RESET_SHARED_WORKFLOW_TEMPLATES_PRESENT" in blocker_codes
    assert "DISTRIBUTION_RESET_SHARED_DECISION_TABLES_PRESENT" in blocker_codes

    assert WorkflowTemplate.objects.filter(id=shared_workflow.id).exists()
    assert DecisionTable.objects.filter(id=shared_decision.id).exists()
    assert BindingProfile.objects.filter(id=fixture_b.binding_profile_id).exists()
    assert PoolRun.objects.filter(id=fixture_b.run_id).exists()


@pytest.mark.django_db
def test_distribution_domain_reset_repeat_apply_is_idempotent() -> None:
    tenant = _create_tenant(slug_prefix="reset-idempotent")
    user = _create_user(username=_token("user"))
    fixture = _create_distribution_fixture(tenant=tenant, created_by=user)

    first_stdout = io.StringIO()
    call_command(
        "reset_distribution_domain",
        "--tenant-id",
        str(tenant.id),
        "--apply",
        "--json",
        stdout=first_stdout,
    )
    first_payload = json.loads(first_stdout.getvalue())
    assert first_payload["overall_status"] == "applied"

    second_stdout = io.StringIO()
    call_command(
        "reset_distribution_domain",
        "--tenant-id",
        str(tenant.id),
        "--apply",
        "--json",
        stdout=second_stdout,
    )
    second_payload = json.loads(second_stdout.getvalue())
    assert second_payload["overall_status"] == "applied"
    assert second_payload["candidate_counts"]["organization_pools"] == 0
    assert second_payload["candidate_counts"]["pool_runs"] == 0
    assert second_payload["candidate_counts"]["workflow_templates"] == 0
    assert second_payload["candidate_counts"]["decision_tables"] == 0
    assert second_payload["deleted_counts"]["organization_pools"] == 0
    assert second_payload["deleted_counts"]["pool_runs"] == 0
    assert second_payload["deleted_counts"]["workflow_templates"] == 0
    assert second_payload["deleted_counts"]["decision_tables"] == 0

    assert not OrganizationPool.objects.filter(id=fixture.pool_id).exists()
