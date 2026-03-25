from __future__ import annotations

import base64
from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabasePermission, InfobaseUserMapping, PermissionLevel
from apps.intercompany_pools.metadata_catalog import (
    ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS,
    MetadataCatalogError,
    refresh_metadata_catalog_snapshot,
)
from apps.intercompany_pools.document_plan_artifact_contract import (
    POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
    POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
    POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY,
)
from apps.intercompany_pools.document_policy_topology_aliases import (
    MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
    MASTER_DATA_PARTY_ROLE_MISSING,
    POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
)
from apps.intercompany_pools.document_policy_contract import resolve_document_policy_from_edge_metadata
from apps.intercompany_pools.binding_profiles_store import create_canonical_binding_profile
from apps.intercompany_pools.models import (
    Organization,
    OrganizationStatus,
    OrganizationPool,
    PoolWorkflowBinding,
    PoolMasterParty,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshotSource,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunCommandLog,
    PoolRunCommandOutbox,
    PoolRunCommandType,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
    TopologyTemplate,
    TopologyTemplateRevision,
)
from apps.intercompany_pools.runtime_projection_contract import POOL_RUNTIME_PROJECTION_CONTEXT_KEY
from apps.intercompany_pools.workflow_binding_attachments_store import (
    list_pool_workflow_binding_attachments,
    upsert_pool_workflow_binding_attachment,
)
from apps.intercompany_pools.workflow_runtime import POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY
from apps.operations.models import BatchOperation
from apps.operations.services import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.templates.workflow.models import DecisionTable, WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant, TenantMember


def _create_validated_run(*, tenant: Tenant, pool: OrganizationPool) -> PoolRun:
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save()
    run.confirm_publication()
    run.save(update_fields=["publication_confirmed_at", "publication_confirmed_by", "updated_at"])
    return run


def _grant_database_permission(client: APIClient, user: User, codename: str) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))


def _grant_database_access(
    client: APIClient,
    user: User,
    *,
    database: Database,
    codename: str,
    level: int,
) -> None:
    _grant_database_permission(client, user, codename)
    DatabasePermission.objects.update_or_create(
        user=user,
        database=database,
        defaults={"level": level},
    )


def _attach_workflow_execution_to_run(
    *,
    run: PoolRun,
    status: str,
    input_context: dict[str, object] | None = None,
    link_run: bool = True,
) -> WorkflowExecution:
    template = WorkflowTemplate.objects.create(
        name=f"pool-run-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-test",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        input_context or {"pool_run_id": str(run.id)},
        tenant=run.tenant,
        execution_consumer="pools",
    )
    update_fields = ["workflow_execution_id", "workflow_status", "execution_backend", "workflow_template_name", "updated_at"]
    if status == WorkflowExecution.STATUS_RUNNING:
        execution.start()
        execution.save(update_fields=["status", "started_at"])
    elif status == WorkflowExecution.STATUS_COMPLETED:
        execution.start()
        execution.complete({"ok": True})
        execution.save(update_fields=["status", "started_at", "completed_at", "final_result"])
    elif status == WorkflowExecution.STATUS_FAILED:
        execution.start()
        execution.fail("failed")
        execution.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "error_message",
                "error_node_id",
            ]
        )
    elif status == WorkflowExecution.STATUS_CANCELLED:
        execution.cancel()
        execution.save(update_fields=["status", "completed_at"])

    if link_run:
        run.workflow_execution_id = execution.id
        run.workflow_status = execution.status
        run.execution_backend = "workflow_core"
        run.workflow_template_name = template.name
        run.save(update_fields=update_fields)
    return execution


def _create_database(
    *,
    tenant: Tenant,
    name: str,
    base_name: str | None = None,
    version: str = "",
) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        base_name=base_name or name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
        version=version,
    )


def _create_service_infobase_mapping(*, database: Database, username: str = "svc-user", password: str = "svc-pass") -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=username,
        ib_password=password,
        is_service=True,
    )


def _set_business_configuration_profile(
    *,
    database: Database,
    config_name: str | None = None,
    config_version: str | None = None,
) -> None:
    metadata = dict(database.metadata or {})
    resolved_name = str(
        config_name
        or database.base_name
        or database.infobase_name
        or database.name
        or database.id
        or ""
    ).strip()
    resolved_version = str(
        config_version if config_version is not None else (database.version or "8.3.24")
    ).strip()
    database.base_name = database.base_name or resolved_name
    database.version = resolved_version
    metadata["business_configuration_profile"] = {
        "config_name": resolved_name,
        "config_root_name": resolved_name,
        "config_version": resolved_version,
        "config_vendor": 'Фирма "1С"',
        "config_generation_id": "1f53b85eba259b43bf2c696c614fc1d900000000",
        "config_name_source": "synonym_ru",
        "verification_status": "verified",
        "verified_at": "2026-03-12T00:00:00+00:00",
    }
    database.metadata = metadata
    database.save(update_fields=["base_name", "version", "metadata", "updated_at"])


def _create_actor_infobase_mapping(
    *,
    database: Database,
    user: User,
    username: str = "actor-user",
    password: str = "actor-pass",
) -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username=username,
        ib_password=password,
        is_service=False,
    )


def _attach_pool_target_database(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    period_start: date,
) -> Database:
    database = _create_database(tenant=tenant, name=f"pool-api-target-{uuid4().hex[:8]}")
    organization = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Org {uuid4().hex[:6]}",
        inn=f"73{uuid4().hex[:10]}",
        status=OrganizationStatus.ACTIVE,
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=period_start,
        is_root=True,
    )
    return database


def _attach_pool_slot_edge(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    database: Database,
    period_start: date,
    slot_key: str = "document_policy",
) -> None:
    root_node = PoolNodeVersion.objects.get(
        pool=pool,
        effective_from=period_start,
        is_root=True,
    )
    if root_node.organization.database_id == database.id:
        root_node.organization.database = None
        root_node.organization.save(update_fields=["database", "updated_at"])
    child_org = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Org Leaf {uuid4().hex[:6]}",
        inn=f"74{uuid4().hex[:10]}",
        status=OrganizationStatus.ACTIVE,
    )
    child_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=child_org,
        effective_from=period_start,
        is_root=False,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=child_node,
        effective_from=period_start,
        metadata={"document_policy_key": slot_key},
    )


def _create_run_with_execution_state(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    mode: str = PoolRunMode.SAFE,
    workflow_status: str = WorkflowExecution.STATUS_COMPLETED,
    approval_required: bool = True,
    approval_state: str = "awaiting_approval",
    approved_at: str | None = None,
    publication_step_state: str = "not_enqueued",
    terminal_reason: str | None = None,
    input_context_overrides: dict[str, object] | None = None,
) -> PoolRun:
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=mode,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])

    input_context: dict[str, object] = {
        "pool_run_id": str(run.id),
        "approval_required": approval_required,
        "approval_state": approval_state,
        "approved_at": approved_at,
        "publication_step_state": publication_step_state,
    }
    if terminal_reason:
        input_context["terminal_reason"] = terminal_reason
    if input_context_overrides:
        input_context.update(input_context_overrides)

    _attach_workflow_execution_to_run(
        run=run,
        status=workflow_status,
        input_context=input_context,
    )
    return run


def _assert_safe_command_conflict_payload(
    payload: dict[str, object],
    *,
    run_id: UUID,
    expected_code: str,
    expected_reason: str,
    expected_retryable: bool,
) -> None:
    assert payload["success"] is False
    assert payload["error_code"] == expected_code
    assert isinstance(payload["error_message"], str)
    assert payload["error_message"]
    assert payload["conflict_reason"] == expected_reason
    assert payload["retryable"] is expected_retryable
    assert payload["run_id"] == str(run_id)


def _assert_problem_details_response(response, *, status_code: int, code: str) -> dict[str, object]:
    assert response.status_code == status_code
    assert response["Content-Type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["status"] == status_code
    assert payload["code"] == code
    assert payload["type"] == "about:blank"
    assert isinstance(payload["title"], str) and payload["title"]
    assert isinstance(payload["detail"], str) and payload["detail"]
    return payload


def _build_document_policy_payload() -> dict[str, object]:
    return {
        "version": "document_policy.v1",
        "chains": [
            {
                "chain_id": "sale_chain",
                "documents": [
                    {
                        "document_id": "sale",
                        "entity_name": "Document_Sales",
                        "document_role": "sale",
                        "field_mapping": {"Amount": "allocation.amount"},
                        "table_parts_mapping": {},
                        "link_rules": {},
                        "invoice_mode": "required",
                    },
                    {
                        "document_id": "invoice",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "field_mapping": {"BaseDocument": "sale.ref"},
                        "table_parts_mapping": {},
                        "link_rules": {"depends_on": "sale"},
                        "link_to": "sale",
                    },
                ],
            }
        ],
    }


def _build_document_policy_decision_payload(*, decision_table_id: str) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id,
        "decision_key": "document_policy",
        "name": "API Test Document Policy",
        "inputs": [
            {"name": "direction", "value_type": "string", "required": True},
            {"name": "mode", "value_type": "string", "required": True},
        ],
        "outputs": [
            {"name": "document_policy", "value_type": "json", "required": True},
        ],
        "rules": [
            {
                "rule_id": "default",
                "priority": 0,
                "conditions": {},
                "outputs": {
                    "document_policy": _build_document_policy_payload(),
                },
            }
        ],
    }


def _build_pool_workflow_binding_payload(
    *,
    pool: OrganizationPool,
    workflow_definition_key: str,
    workflow_revision: int,
    direction: str | None = None,
    mode: str | None = None,
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    status: str = "active",
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "binding_id": str(uuid4()),
        "pool_id": str(pool.id),
        "workflow": {
            "workflow_definition_key": workflow_definition_key,
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": workflow_revision,
            "workflow_name": workflow_definition_key.replace("-", "_"),
        },
        "selector": {
            "direction": direction,
            "mode": mode,
            "tags": list(tags or []),
        },
        "effective_from": effective_from,
        "effective_to": effective_to,
        "status": status,
    }


def list_pool_workflow_bindings(*, pool: OrganizationPool) -> list[dict[str, object]]:
    return list_pool_workflow_binding_attachments(pool=pool)


def _build_binding_profile_revision_payload(
    *,
    workflow_definition_key: str,
    workflow_revision: int,
    workflow_revision_id: str | None = None,
    workflow_name: str | None = None,
    decisions: list[dict[str, object]] | None = None,
    parameters: dict[str, object] | None = None,
    role_mapping: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "workflow": {
            "workflow_definition_key": workflow_definition_key,
            "workflow_revision_id": workflow_revision_id or str(uuid4()),
            "workflow_revision": workflow_revision,
            "workflow_name": workflow_name or workflow_definition_key.replace("-", "_"),
        },
        "decisions": list(decisions or []),
        "parameters": dict(parameters or {}),
        "role_mapping": dict(role_mapping or {}),
        "metadata": {
            "source": "test",
        },
    }


def _create_binding_profile_revision(
    *,
    tenant: Tenant,
    workflow_definition_key: str,
    workflow_revision: int,
    direction: str | None = None,
    materialize_runtime_workflow: bool = False,
    decisions: list[dict[str, object]] | None = None,
    parameters: dict[str, object] | None = None,
    role_mapping: dict[str, str] | None = None,
) -> dict[str, object]:
    workflow_revision_id: str | None = None
    workflow_name: str | None = None
    if materialize_runtime_workflow:
        materialized_workflow_name = f"{workflow_definition_key.replace('-', '_')}_{uuid4().hex[:8]}"
        workflow_root, workflow = _create_pool_runtime_workflow_revision(
            workflow_name=materialized_workflow_name,
            direction=direction,
            workflow_revision=workflow_revision,
        )
        workflow_definition_key = str(workflow_root.id)
        workflow_revision_id = str(workflow.id)
        workflow_name = workflow.name
    profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": f"{workflow_definition_key}-{uuid4().hex[:8]}",
            "name": (workflow_name or workflow_definition_key).replace("-", " ").title(),
            "revision": _build_binding_profile_revision_payload(
                workflow_definition_key=workflow_definition_key,
                workflow_revision=workflow_revision,
                workflow_revision_id=workflow_revision_id,
                workflow_name=workflow_name,
                decisions=decisions,
                parameters=parameters,
                role_mapping=role_mapping,
            ),
        },
        actor_username="binding-profile-test",
    )
    latest_revision = profile["latest_revision"]
    assert isinstance(latest_revision, dict)
    return latest_revision


def _build_pool_workflow_binding_attachment_payload(
    *,
    binding_profile_revision_id: str,
    direction: str | None = None,
    mode: str | None = None,
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    status: str = "active",
    tags: list[str] | None = None,
    binding_id: str | None = None,
    revision: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "binding_profile_revision_id": binding_profile_revision_id,
        "selector": {
            "direction": direction,
            "mode": mode,
            "tags": list(tags or []),
        },
        "effective_from": effective_from,
        "effective_to": effective_to,
        "status": status,
    }
    if binding_id is not None:
        payload["binding_id"] = binding_id
    if revision is not None:
        payload["revision"] = revision
    return payload


def _attachment_payload_from_read_model(
    binding: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    selector = binding.get("selector")
    payload = _build_pool_workflow_binding_attachment_payload(
        binding_profile_revision_id=str(binding["binding_profile_revision_id"]),
        direction=selector.get("direction") if isinstance(selector, dict) else None,
        mode=selector.get("mode") if isinstance(selector, dict) else None,
        effective_from=str(binding["effective_from"]),
        effective_to=str(binding.get("effective_to") or "") or None,
        status=str(binding["status"]),
        tags=list(selector.get("tags") or []) if isinstance(selector, dict) else [],
        binding_id=str(binding["binding_id"]),
        revision=int(binding["revision"]),
    )
    payload.update(overrides)
    return payload


def upsert_canonical_pool_workflow_binding(
    *,
    pool: OrganizationPool,
    workflow_binding: dict[str, object],
    actor_username: str = "",
) -> tuple[dict[str, object], bool]:
    workflow_payload = (
        dict(workflow_binding.get("workflow"))
        if isinstance(workflow_binding.get("workflow"), dict)
        else {}
    )
    selector = (
        dict(workflow_binding.get("selector"))
        if isinstance(workflow_binding.get("selector"), dict)
        else {}
    )
    profile = create_canonical_binding_profile(
        tenant=pool.tenant,
        binding_profile={
            "code": f"binding-fixture-{uuid4().hex[:8]}",
            "name": f"Binding Fixture {workflow_payload.get('workflow_name') or 'workflow'}",
            "revision": _build_binding_profile_revision_payload(
                workflow_definition_key=str(
                    workflow_payload.get("workflow_definition_key") or "workflow-definition"
                ),
                workflow_revision=int(workflow_payload.get("workflow_revision") or 1),
                workflow_revision_id=str(workflow_payload.get("workflow_revision_id") or uuid4()),
                workflow_name=str(workflow_payload.get("workflow_name") or "workflow"),
                decisions=(
                    list(workflow_binding.get("decisions"))
                    if isinstance(workflow_binding.get("decisions"), list)
                    else []
                ),
                parameters=(
                    dict(workflow_binding.get("parameters"))
                    if isinstance(workflow_binding.get("parameters"), dict)
                    else {}
                ),
                role_mapping=(
                    dict(workflow_binding.get("role_mapping"))
                    if isinstance(workflow_binding.get("role_mapping"), dict)
                    else {}
                ),
            ),
        },
        actor_username=actor_username or "binding-fixture-test",
    )
    latest_revision = profile["latest_revision"]
    assert isinstance(latest_revision, dict)
    return upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding=_build_pool_workflow_binding_attachment_payload(
            binding_profile_revision_id=str(latest_revision["binding_profile_revision_id"]),
            direction=str(selector.get("direction") or "").strip() or None,
            mode=str(selector.get("mode") or "").strip() or None,
            effective_from=str(workflow_binding.get("effective_from") or "2026-01-01"),
            effective_to=str(workflow_binding.get("effective_to") or "").strip() or None,
            status=str(workflow_binding.get("status") or "active"),
            tags=list(selector.get("tags") or []) if isinstance(selector.get("tags"), list) else [],
            binding_id=str(workflow_binding.get("binding_id") or "").strip() or None,
            revision=(
                int(workflow_binding["revision"])
                if workflow_binding.get("revision") not in {None, ""}
                else None
            ),
        ),
        actor_username=actor_username or "binding-fixture-test",
    )


def _create_legacy_pool_workflow_binding_without_profile_refs(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    binding_id: str | None = None,
    direction: str = PoolRunDirection.BOTTOM_UP,
    mode: str = PoolRunMode.SAFE,
) -> PoolWorkflowBinding:
    return PoolWorkflowBinding.objects.create(
        binding_id=binding_id or str(uuid4()),
        tenant=tenant,
        pool=pool,
        contract_version="pool_workflow_binding.v1",
        status="active",
        effective_from="2026-01-01",
        effective_to=None,
        direction=direction,
        mode=mode,
        selector_tags=[],
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=3,
        workflow_name="services_publication",
        decisions=[],
        parameters={"publication_variant": "full"},
        role_mapping={"initiator": "finance"},
        revision=1,
        created_by="legacy-import",
        updated_by="legacy-import",
    )


def _create_pool_runtime_workflow_revision(
    *,
    workflow_name: str,
    direction: str | None,
    workflow_revision: int,
) -> tuple[WorkflowTemplate, WorkflowTemplate]:
    normalized_direction = direction or PoolRunDirection.BOTTOM_UP
    distribution_alias = (
        "pool.distribution_calculation.top_down"
        if normalized_direction == PoolRunDirection.TOP_DOWN
        else "pool.distribution_calculation.bottom_up"
    )
    root = WorkflowTemplate.objects.create(
        name=workflow_name,
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "prepare_input",
                    "name": "Prepare Input",
                    "type": "operation",
                    "template_id": "pool.prepare_input",
                },
                {
                    "id": "distribution",
                    "name": "Distribution",
                    "type": "operation",
                    "template_id": distribution_alias,
                },
                {
                    "id": "reconciliation",
                    "name": "Reconciliation",
                    "type": "operation",
                    "template_id": "pool.reconciliation_report",
                },
                {
                    "id": "approval_gate",
                    "name": "Approval Gate",
                    "type": "operation",
                    "template_id": "pool.approval_gate",
                },
                {
                    "id": "publication",
                    "name": "Publication",
                    "type": "operation",
                    "template_id": "pool.publication_odata",
                },
            ],
            "edges": [
                {"from": "prepare_input", "to": "distribution"},
                {"from": "distribution", "to": "reconciliation"},
                {"from": "reconciliation", "to": "approval_gate"},
                {"from": "approval_gate", "to": "publication", "condition": "{{approved_at}}"},
            ],
        },
        config={"timeout_seconds": 86400, "max_retries": 0},
        is_valid=True,
        is_active=True,
        version_number=1,
    )
    revision = root
    for version_number in range(2, max(int(workflow_revision), 1) + 1):
        revision = WorkflowTemplate.objects.create(
            name=workflow_name,
            description="",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=revision,
            version_number=version_number,
        )
    return root, revision


def _prepare_pool_runtime_bindings(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    bindings: list[dict[str, object]],
    period_start: date,
    actor: User | None = None,
) -> tuple[list[dict[str, object]], Database]:
    database = _attach_pool_target_database(
        tenant=tenant,
        pool=pool,
        period_start=period_start,
    )
    decision = create_decision_table_revision(
        contract=_build_document_policy_decision_payload(
            decision_table_id=f"pool-api-doc-policy-{uuid4().hex[:8]}"
        )
    )
    decision_ref = {
        "decision_table_id": decision.decision_table_id,
        "decision_key": decision.decision_key,
        "slot_key": decision.decision_key,
        "decision_revision": decision.version_number,
    }

    hydrated_bindings: list[dict[str, object]] = []
    for binding in bindings:
        binding_decisions = binding.get("decisions")
        workflow_payload = binding.get("workflow") if isinstance(binding.get("workflow"), dict) else {}
        workflow_name = str(workflow_payload.get("workflow_name") or f"workflow-{uuid4().hex[:8]}")
        workflow_revision_number = int(workflow_payload.get("workflow_revision") or 1)
        root_workflow, revision_workflow = _create_pool_runtime_workflow_revision(
            workflow_name=workflow_name,
            direction=str(binding.get("selector", {}).get("direction") or "") if isinstance(binding.get("selector"), dict) else None,
            workflow_revision=workflow_revision_number,
        )
        hydrated_bindings.append(
            {
                **binding,
                "workflow": {
                    **workflow_payload,
                    "workflow_definition_key": str(root_workflow.id),
                    "workflow_revision_id": str(revision_workflow.id),
                    "workflow_revision": revision_workflow.version_number,
                    "workflow_name": revision_workflow.name,
                },
                "decisions": (
                    list(binding_decisions)
                    if isinstance(binding_decisions, list) and binding_decisions
                    else [decision_ref]
                ),
            }
        )

    metadata = dict(pool.metadata) if isinstance(pool.metadata, dict) else {}
    metadata.pop("workflow_bindings", None)
    pool.metadata = metadata
    pool.save(update_fields=["metadata", "updated_at"])

    actor_username = actor.username if actor is not None else "pool-runtime-bindings-test"
    for binding in hydrated_bindings:
        upsert_canonical_pool_workflow_binding(
            pool=pool,
            workflow_binding=binding,
            actor_username=actor_username,
        )

    if actor is not None:
        _create_actor_infobase_mapping(
            database=database,
            user=actor,
            username=f"actor-{actor.username}",
        )

    return hydrated_bindings, database


def _prepare_single_pool_runtime_binding(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    workflow_definition_key: str,
    workflow_revision: int,
    direction: str | None,
    mode: str | None,
    period_start: date,
    actor: User | None = None,
) -> tuple[dict[str, object], Database]:
    bindings, database = _prepare_pool_runtime_bindings(
        tenant=tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key=workflow_definition_key,
                workflow_revision=workflow_revision,
                direction=direction,
                mode=mode,
            )
        ],
        period_start=period_start,
        actor=actor,
    )
    return bindings[0], database


def _build_metadata_catalog_payload() -> dict[str, object]:
    return {
        "documents": [
            {
                "entity_name": "Document_Sales",
                "display_name": "Sales",
                "fields": [
                    {"name": "Amount", "type": "Edm.Decimal", "nullable": False},
                ],
                "table_parts": [
                    {
                        "name": "Items",
                        "row_fields": [
                            {"name": "LineAmount", "type": "Edm.Decimal", "nullable": False},
                        ],
                    }
                ],
            },
            {
                "entity_name": "Document_Invoice",
                "display_name": "Invoice",
                "fields": [
                    {"name": "BaseDocument", "type": "Edm.String", "nullable": False},
                ],
                "table_parts": [],
            },
        ]
    }


def _create_current_metadata_catalog_snapshot(
    *,
    tenant: Tenant,
    database: Database,
    payload: dict[str, object] | None = None,
    extensions_fingerprint: str = "",
) -> PoolODataMetadataCatalogSnapshot:
    config_name = str(
        database.base_name
        or database.infobase_name
        or database.name
        or database.id
        or ""
    ).strip()
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=tenant,
        database=database,
        config_name=config_name,
        config_version=str(database.version or "").strip(),
        extensions_fingerprint=extensions_fingerprint,
        metadata_hash="a" * 64,
        catalog_version=f"v1:{uuid4().hex[:16]}",
        payload=payload or _build_metadata_catalog_payload(),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant=tenant,
        database=database,
        snapshot=snapshot,
        config_name=config_name,
        config_version=str(database.version or "").strip(),
        extensions_fingerprint=extensions_fingerprint,
        confirmed_at=snapshot.fetched_at,
    )
    return snapshot


def _create_topology_template_via_api(
    authenticated_client: APIClient,
    *,
    code: str,
    name: str,
    revision: dict[str, object],
) -> dict[str, object]:
    response = authenticated_client.post(
        "/api/v2/pools/topology-templates/",
        {
            "code": code,
            "name": name,
            "revision": revision,
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    topology_template = payload["topology_template"]
    assert isinstance(topology_template, dict)
    return topology_template


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username="pool-api-user", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.fixture
def authenticated_client(user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


@pytest.fixture
def pool(default_tenant: Tenant) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=default_tenant,
        code="pool-api",
        name="Pool API",
    )


@pytest.mark.django_db
def test_pool_run_endpoints_require_authentication(pool: OrganizationPool) -> None:
    client = APIClient()
    create_response = client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": []},
        },
        format="json",
    )
    assert create_response.status_code in [401, 403]


@pytest.mark.django_db
def test_list_organizations_endpoint_filters_by_status_and_query(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    db = _create_database(tenant=default_tenant, name="pool-org-list-db")
    party = PoolMasterParty.objects.create(
        tenant=default_tenant,
        canonical_id="party-org-list",
        name="Party Org List",
        inn="710000000001",
        is_our_organization=True,
    )
    Organization.objects.create(
        tenant=default_tenant,
        database=db,
        master_party=party,
        name="Alpha Org",
        full_name="Alpha Organization",
        inn="710000000001",
        status=OrganizationStatus.ACTIVE,
    )
    Organization.objects.create(
        tenant=default_tenant,
        name="Beta Org",
        full_name="Beta Organization",
        inn="710000000002",
        status=OrganizationStatus.INACTIVE,
    )

    response = authenticated_client.get("/api/v2/pools/organizations/?status=active&query=alpha")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["organizations"][0]["inn"] == "710000000001"
    assert payload["organizations"][0]["database_id"] == str(db.id)
    assert payload["organizations"][0]["master_party_id"] == str(party.id)


@pytest.mark.django_db
def test_get_organization_returns_pool_bindings(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    party = PoolMasterParty.objects.create(
        tenant=default_tenant,
        canonical_id="party-binding-org",
        name="Party Binding Org",
        inn="720000000001",
        is_our_organization=True,
    )
    organization = Organization.objects.create(
        tenant=default_tenant,
        name="Binding Org",
        inn="720000000001",
        master_party=party,
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )

    response = authenticated_client.get(f"/api/v2/pools/organizations/{organization.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["organization"]["id"] == str(organization.id)
    assert payload["organization"]["inn"] == "720000000001"
    assert payload["organization"]["master_party_id"] == str(party.id)
    assert len(payload["pool_bindings"]) == 1
    assert payload["pool_bindings"][0]["pool_id"] == str(pool.id)
    assert payload["pool_bindings"][0]["pool_code"] == pool.code


@pytest.mark.django_db
def test_upsert_organization_creates_updates_and_enforces_database_uniqueness(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    db1 = _create_database(tenant=default_tenant, name="pool-org-upsert-db-1")
    db2 = _create_database(tenant=default_tenant, name="pool-org-upsert-db-2")

    create_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730000000001",
            "name": "Create Org",
            "status": "active",
            "database_id": str(db1.id),
        },
        format="json",
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["created"] is True
    created_id = create_payload["organization"]["id"]

    update_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "organization_id": created_id,
            "inn": "730000000001",
            "name": "Updated Org",
            "status": "inactive",
            "database_id": str(db1.id),
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["created"] is False
    assert update_payload["organization"]["name"] == "Updated Org"
    assert update_payload["organization"]["status"] == "inactive"

    Organization.objects.create(
        tenant=default_tenant,
        database=db2,
        name="DB2 owner",
        inn="730000000002",
    )
    conflict_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730000000003",
            "name": "Conflict Org",
            "status": "active",
            "database_id": str(db2.id),
        },
        format="json",
    )
    _assert_problem_details_response(
        conflict_response,
        status_code=400,
        code="DATABASE_ALREADY_LINKED",
    )


@pytest.mark.django_db
def test_upsert_organization_validates_master_party_binding_invariants(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    valid_party = PoolMasterParty.objects.create(
        tenant=default_tenant,
        canonical_id="party-org-valid",
        name="Party Org Valid",
        inn="730100000001",
        is_our_organization=True,
    )
    counterparty_only = PoolMasterParty.objects.create(
        tenant=default_tenant,
        canonical_id="party-counterparty-only",
        name="Counterparty Only",
        inn="730100000002",
        is_our_organization=False,
        is_counterparty=True,
    )
    foreign_tenant = Tenant.objects.create(
        slug=f"pool-org-foreign-{uuid4().hex[:8]}",
        name="Pool Org Foreign",
    )
    foreign_party = PoolMasterParty.objects.create(
        tenant=foreign_tenant,
        canonical_id="party-foreign-org",
        name="Party Foreign Org",
        inn="730100000003",
        is_our_organization=True,
    )

    create_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730100000010",
            "name": "Master Party Bound Org",
            "status": "active",
            "master_party_id": str(valid_party.id),
        },
        format="json",
    )
    assert create_response.status_code == 201
    assert create_response.json()["organization"]["master_party_id"] == str(valid_party.id)

    conflict_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730100000011",
            "name": "Master Party Conflict Org",
            "status": "active",
            "master_party_id": str(valid_party.id),
        },
        format="json",
    )
    _assert_problem_details_response(
        conflict_response,
        status_code=400,
        code="MASTER_PARTY_ALREADY_LINKED",
    )

    invalid_role_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730100000012",
            "name": "Invalid Role Org",
            "status": "active",
            "master_party_id": str(counterparty_only.id),
        },
        format="json",
    )
    _assert_problem_details_response(
        invalid_role_response,
        status_code=400,
        code="MASTER_PARTY_ROLE_INVALID",
    )

    foreign_party_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730100000013",
            "name": "Foreign Party Org",
            "status": "active",
            "master_party_id": str(foreign_party.id),
        },
        format="json",
    )
    _assert_problem_details_response(
        foreign_party_response,
        status_code=404,
        code="MASTER_PARTY_NOT_FOUND",
    )


@pytest.mark.django_db
def test_upsert_organization_validation_error_returns_problem_details_with_field_errors(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "name": "Missing INN",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert isinstance(payload.get("errors"), dict)
    assert "inn" in payload["errors"]


@pytest.mark.django_db
def test_sync_organizations_catalog_endpoint_returns_stats(
    authenticated_client: APIClient,
) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/organizations/sync/",
        {
            "rows": [
                {"inn": "740000000001", "name": "Sync Org A"},
                {"inn": "740000000002", "name": "Sync Org B", "status": "inactive"},
            ]
        },
        format="json",
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["stats"] == {"created": 2, "updated": 0, "skipped": 0}
    assert create_payload["total_rows"] == 2

    update_response = authenticated_client.post(
        "/api/v2/pools/organizations/sync/",
        {
            "rows": [
                {"inn": "740000000001", "name": "Sync Org A Updated"},
                {"inn": "740000000002", "name": "Sync Org B", "status": "inactive"},
            ]
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["stats"] == {"created": 0, "updated": 1, "skipped": 1}


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_returns_current_snapshot(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-get-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    _set_business_configuration_profile(database=database)
    snapshot = _create_current_metadata_catalog_snapshot(
        tenant=default_tenant,
        database=database,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="view_database",
        level=PermissionLevel.VIEW,
    )

    response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={database.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_id"] == str(database.id)
    assert payload["snapshot_id"] == str(snapshot.id)
    assert payload["catalog_version"] == snapshot.catalog_version
    assert payload["config_name"] == snapshot.config_name
    assert payload["extensions_fingerprint"] == snapshot.extensions_fingerprint
    assert payload["metadata_hash"] == snapshot.metadata_hash
    assert payload["resolution_mode"] == "database_scope"
    assert payload["is_shared_snapshot"] is False
    assert payload["provenance_database_id"] == str(database.id)
    assert payload["provenance_confirmed_at"] == snapshot.fetched_at.isoformat().replace("+00:00", "Z")
    assert payload["source"] in {"db", "redis"}
    assert isinstance(payload["documents"], list)
    entity_names = {str(item.get("entity_name") or "") for item in payload["documents"]}
    assert "Document_Sales" in entity_names


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_reports_shared_snapshot_provenance(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_database = _create_database(
        tenant=default_tenant,
        name=f"metadata-shared-a-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"metadata-shared-b-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)
    _set_business_configuration_profile(database=first_database, config_name="shared-profile", config_version="8.3.24")
    _set_business_configuration_profile(database=second_database, config_name="shared-profile", config_version="8.3.24")
    shared_payload = {
        "documents": [
            {
                "entity_name": "Document_Sales",
                "display_name": "Sales",
                "fields": [
                    {"name": "Amount", "type": "Edm.Decimal", "nullable": False},
                ],
                "table_parts": [],
            }
        ]
    }
    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        lambda **_: shared_payload,
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)
    snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="pool-api-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=second_database,
        codename="view_database",
        level=PermissionLevel.VIEW,
    )

    response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={second_database.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_id"] == str(second_database.id)
    assert payload["snapshot_id"] == str(snapshot.id)
    assert payload["config_name"] == "shared-profile"
    assert payload["config_version"] == "8.3.24"
    assert payload["source"] == "db"
    assert payload["resolution_mode"] == "shared_scope"
    assert payload["is_shared_snapshot"] is True
    assert payload["provenance_database_id"] == str(first_database.id)


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_rejects_missing_mapping_without_legacy_fallback_even_with_snapshot(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-get-nomapping-db-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=database)
    _create_current_metadata_catalog_snapshot(
        tenant=default_tenant,
        database=database,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="view_database",
        level=PermissionLevel.VIEW,
    )

    with patch("apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata") as metadata_fetch:
        response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={database.id}")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_NOT_CONFIGURED",
    )
    assert problem["title"] == "Metadata Catalog Auth Configuration Error"
    assert "/rbac" in problem["detail"]
    metadata_fetch.assert_not_called()


@pytest.mark.django_db
def test_refresh_pool_odata_metadata_catalog_rejects_missing_mapping_without_legacy_fallback(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-refresh-db-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=database)
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="operate_database",
        level=PermissionLevel.OPERATE,
    )

    with patch("apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata") as metadata_fetch:
        response = authenticated_client.post(
            "/api/v2/pools/odata-metadata/catalog/refresh/",
            {"database_id": str(database.id)},
            format="json",
        )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_NOT_CONFIGURED",
    )
    assert problem["title"] == "Metadata Catalog Auth Configuration Error"
    assert "/rbac" in problem["detail"]
    metadata_fetch.assert_not_called()


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_sends_utf8_basic_for_cyrillic_mapping_credentials(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-nonlatin-db-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=database)
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="ГлавБух",
        ib_password="пароль",
        is_service=True,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="view_database",
        level=PermissionLevel.VIEW,
    )

    class _Response:
        status_code = 401
        text = '{"error":{"message":{"value":"Unauthorized"}}}'
        headers = {"Content-Type": "application/json; charset=utf-8"}

    with patch("apps.databases.odata.metadata_adapter.requests.get", return_value=_Response()) as requests_get:
        response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={database.id}")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_METADATA_SNAPSHOT_UNAVAILABLE",
    )
    assert "snapshot" in problem["detail"].lower()
    requests_get.assert_not_called()


@pytest.mark.django_db
def test_refresh_pool_odata_metadata_catalog_sends_utf8_basic_for_cyrillic_mapping_credentials(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-refresh-nonlatin-db-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=database)
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="ГлавБух",
        ib_password="пароль",
        is_service=True,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="operate_database",
        level=PermissionLevel.OPERATE,
    )

    class _Response:
        status_code = 401
        text = '{"error":{"message":{"value":"Unauthorized"}}}'
        headers = {"Content-Type": "application/json; charset=utf-8"}

    with patch("apps.databases.odata.metadata_adapter.requests.get", return_value=_Response()) as requests_get:
        response = authenticated_client.post(
            "/api/v2/pools/odata-metadata/catalog/refresh/",
            {"database_id": str(database.id)},
            format="json",
        )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_NOT_CONFIGURED",
    )
    assert "latin-1" not in problem["detail"].lower()
    assert "rejected" in problem["detail"].lower()

    requests_get.assert_called_once()
    kwargs = requests_get.call_args.kwargs
    assert "auth" not in kwargs
    assert kwargs["headers"]["Accept"] == "application/xml"
    expected_auth = "Basic " + base64.b64encode("ГлавБух:пароль".encode("utf-8")).decode("ascii")
    assert kwargs["headers"]["Authorization"] == expected_auth


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_keeps_ascii_basic_auth_compatibility(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-ascii-db-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=database)
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="svc-user",
        ib_password="svc-pass",
        is_service=True,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="view_database",
        level=PermissionLevel.VIEW,
    )

    class _Response:
        status_code = 401
        text = '{"error":{"message":{"value":"Unauthorized"}}}'
        headers = {"Content-Type": "application/json; charset=utf-8"}

    with patch("apps.databases.odata.metadata_adapter.requests.get", return_value=_Response()) as requests_get:
        response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={database.id}")

    _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_METADATA_SNAPSHOT_UNAVAILABLE",
    )
    requests_get.assert_not_called()


@pytest.mark.django_db
def test_refresh_pool_odata_metadata_catalog_returns_serialized_snapshot(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-refresh-ok-db-{uuid4().hex[:8]}")
    snapshot = _create_current_metadata_catalog_snapshot(
        tenant=default_tenant,
        database=database,
    )
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="operate_database",
        level=PermissionLevel.OPERATE,
    )

    with patch(
        "apps.api_v2.views.intercompany_pools.refresh_metadata_catalog_snapshot",
        return_value=snapshot,
    ) as refresh_snapshot:
        response = authenticated_client.post(
            "/api/v2/pools/odata-metadata/catalog/refresh/",
            {"database_id": str(database.id)},
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_id"] == str(database.id)
    assert payload["snapshot_id"] == str(snapshot.id)
    assert payload["source"] == "live_refresh"
    assert payload["catalog_version"] == snapshot.catalog_version
    assert payload["config_name"] == snapshot.config_name
    assert payload["extensions_fingerprint"] == snapshot.extensions_fingerprint
    assert payload["metadata_hash"] == snapshot.metadata_hash
    assert payload["resolution_mode"] == "database_scope"
    assert payload["is_shared_snapshot"] is False
    assert payload["provenance_database_id"] == str(database.id)
    assert payload["provenance_confirmed_at"] == snapshot.fetched_at.isoformat().replace("+00:00", "Z")

    refresh_snapshot.assert_called_once()
    kwargs = refresh_snapshot.call_args.kwargs
    assert kwargs["tenant_id"] == str(default_tenant.id)
    assert kwargs["database"].id == database.id
    assert kwargs["requested_by_username"] == "pool-api-user"
    assert kwargs["source"] == "live_refresh"


@pytest.mark.django_db
def test_refresh_pool_odata_metadata_catalog_returns_conflict_when_lock_is_busy(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-refresh-lock-db-{uuid4().hex[:8]}")
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="operate_database",
        level=PermissionLevel.OPERATE,
    )

    with patch(
        "apps.api_v2.views.intercompany_pools.refresh_metadata_catalog_snapshot",
        side_effect=MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS,
            title="Metadata Refresh In Progress",
            detail="Metadata refresh already in progress for selected database.",
            status_code=409,
        ),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/odata-metadata/catalog/refresh/",
            {"database_id": str(database.id)},
            format="json",
        )

    payload = _assert_problem_details_response(
        response,
        status_code=409,
        code=ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS,
    )
    assert payload["title"] == "Metadata Refresh In Progress"
    assert "already in progress" in payload["detail"].lower()


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_requires_database_view_permission(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-view-rbac-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    _set_business_configuration_profile(database=database)
    _create_current_metadata_catalog_snapshot(tenant=default_tenant, database=database)
    _grant_database_permission(authenticated_client, user, "view_database")

    response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={database.id}")

    payload = _assert_problem_details_response(
        response,
        status_code=403,
        code="PERMISSION_DENIED",
    )
    assert "permission" in payload["detail"].lower()


@pytest.mark.django_db
def test_get_pool_odata_metadata_catalog_does_not_hidden_bootstrap_when_profile_is_missing(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-no-bootstrap-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="view_database",
        level=PermissionLevel.VIEW,
    )

    with patch("apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata") as metadata_fetch:
        response = authenticated_client.get(f"/api/v2/pools/odata-metadata/catalog/?database_id={database.id}")

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_METADATA_PROFILE_UNAVAILABLE",
    )
    assert "profile" in payload["detail"].lower()
    assert PoolODataMetadataCatalogSnapshot.objects.count() == 0
    assert PoolODataMetadataCatalogScopeResolution.objects.count() == 0
    assert BatchOperation.objects.count() == 0
    metadata_fetch.assert_not_called()


@pytest.mark.django_db
def test_refresh_pool_odata_metadata_catalog_requires_database_operate_permission(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"metadata-operate-rbac-db-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=database)
    _grant_database_access(
        authenticated_client,
        user,
        database=database,
        codename="operate_database",
        level=PermissionLevel.VIEW,
    )

    with patch("apps.api_v2.views.intercompany_pools.refresh_metadata_catalog_snapshot") as refresh_snapshot:
        response = authenticated_client.post(
            "/api/v2/pools/odata-metadata/catalog/refresh/",
            {"database_id": str(database.id)},
            format="json",
        )

    payload = _assert_problem_details_response(
        response,
        status_code=403,
        code="PERMISSION_DENIED",
    )
    assert "permission" in payload["detail"].lower()
    refresh_snapshot.assert_not_called()


@pytest.mark.django_db
def test_upsert_pool_metadata_creates_updates_and_enforces_tenant_boundary(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "code": "pool-meta",
            "name": "Pool Metadata",
            "description": "Initial pool metadata",
            "is_active": True,
            "metadata": {"domain": "intercompany"},
        },
        format="json",
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["created"] is True
    pool_id = create_payload["pool"]["id"]

    update_response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": pool_id,
            "code": "pool-meta",
            "name": "Pool Metadata Updated",
            "description": "Updated pool metadata",
            "is_active": False,
            "metadata": {"domain": "intercompany", "version": 2},
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["created"] is False
    assert update_payload["pool"]["name"] == "Pool Metadata Updated"
    assert update_payload["pool"]["description"] == "Updated pool metadata"
    assert update_payload["pool"]["is_active"] is False

    pools_response = authenticated_client.get("/api/v2/pools/")
    assert pools_response.status_code == 200
    pools_payload = pools_response.json()
    assert any(
        item["id"] == pool_id
        and item["description"] == "Updated pool metadata"
        for item in pools_payload["pools"]
    )

    another_tenant = Tenant.objects.create(slug="pool-meta-other", name="Pool Meta Other")
    another_user = User.objects.create_user(username="pool-meta-other-user", password="pass")
    TenantMember.objects.create(
        tenant=another_tenant,
        user=another_user,
        role=TenantMember.ROLE_ADMIN,
    )
    another_client = APIClient()
    another_client.force_authenticate(user=another_user)
    another_client.credentials(HTTP_X_CC1C_TENANT_ID=str(another_tenant.id))
    cross_tenant_response = another_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": pool_id,
            "code": "pool-meta",
            "name": "Cross tenant update",
        },
        format="json",
    )
    assert cross_tenant_response.status_code == 404
    assert cross_tenant_response.json()["code"] == "POOL_NOT_FOUND"


@pytest.mark.django_db
def test_upsert_pool_metadata_rejects_legacy_workflow_bindings_write_path(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "code": "pool-bindings",
            "name": "Pool Bindings",
            "workflow_bindings": [
                {
                    "workflow": {
                        "workflow_definition_key": "services-publication",
                        "workflow_revision_id": "11111111-1111-1111-1111-111111111111",
                        "workflow_revision": 3,
                        "workflow_name": "services_publication",
                    },
                    "effective_from": "2026-01-01",
                    "effective_to": "2025-01-01",
                    "status": "active",
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert "workflow_bindings" in payload["detail"]
    assert "/api/v2/pools/workflow-bindings/" in payload["detail"]


@pytest.mark.django_db
def test_upsert_pool_metadata_rejects_workflow_bindings_nested_inside_metadata(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "code": "pool-bindings-metadata",
            "name": "Pool Bindings Metadata",
            "metadata": {
                "workflow_bindings": [
                    {
                        "workflow": {
                            "workflow_definition_key": "services-publication",
                            "workflow_revision_id": "11111111-1111-1111-1111-111111111111",
                            "workflow_revision": 3,
                            "workflow_name": "services_publication",
                        },
                        "effective_from": "2026-01-01",
                        "status": "active",
                    }
                ]
            },
        },
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert "metadata" in payload["detail"]
    assert "/api/v2/pools/workflow-bindings/" in payload["detail"]


@pytest.mark.django_db
def test_upsert_pool_metadata_rejects_legacy_document_policy_write_path(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    pool.metadata = {"owner": "finance"}
    pool.save(update_fields=["metadata", "updated_at"])

    response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": str(pool.id),
            "code": pool.code,
            "name": pool.name,
            "metadata": {
                "owner": "ops",
                "document_policy": _build_document_policy_payload(),
            },
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
    )
    assert "metadata.document_policy" in payload["detail"]

    pool.refresh_from_db()
    assert pool.metadata == {"owner": "finance"}


@pytest.mark.django_db
def test_upsert_pool_metadata_preserves_existing_workflow_bindings(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=binding,
        actor_username="pool-upsert-test",
    )
    pool.metadata = {"owner": "ops"}
    pool.save(update_fields=["metadata", "updated_at"])

    response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": str(pool.id),
            "code": pool.code,
            "name": "Pool API",
            "metadata": {
                "owner": "finance",
            },
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pool"]["metadata"]["owner"] == "finance"
    assert len(payload["pool"]["workflow_bindings"]) == 1
    assert payload["pool"]["workflow_bindings"][0]["binding_id"] == binding["binding_id"]
    assert payload["pool"]["workflow_bindings"][0]["binding_profile_revision_id"]
    assert payload["pool"]["workflow_bindings"][0]["resolved_profile"]["workflow"]["workflow_revision"] == 3

    pool.refresh_from_db()
    assert pool.metadata["owner"] == "finance"
    assert "workflow_bindings" not in pool.metadata


@pytest.mark.django_db
def test_upsert_pool_metadata_drops_transient_workflow_bindings_read_error(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": str(pool.id),
            "code": pool.code,
            "name": pool.name,
            "metadata": {
                "owner": "finance",
                "workflow_bindings_read_error": {
                    "code": "POOL_WORKFLOW_BINDING_INVALID",
                    "detail": "synthetic",
                },
            },
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pool"]["metadata"]["owner"] == "finance"
    assert "workflow_bindings_read_error" not in payload["pool"]["metadata"]

    pool.refresh_from_db()
    assert pool.metadata["owner"] == "finance"
    assert "workflow_bindings_read_error" not in pool.metadata


@pytest.mark.django_db
def test_pool_workflow_bindings_list_exposes_multiple_pinned_bindings(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    first_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
    )
    second_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="bottom-up-import",
        workflow_revision=5,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=first_binding,
        actor_username="pool-list-test",
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=second_binding,
        actor_username="pool-list-test",
    )

    response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pool_id"] == str(pool.id)
    assert isinstance(payload["collection_etag"], str)
    assert payload["collection_etag"]
    assert [item["binding_id"] for item in payload["workflow_bindings"]] == [
        first_binding["binding_id"],
        second_binding["binding_id"],
    ]
    assert payload["workflow_bindings"][0]["revision"] == 1
    assert payload["workflow_bindings"][1]["revision"] == 1
    assert payload["workflow_bindings"][0]["binding_profile_revision_id"]
    assert payload["workflow_bindings"][1]["binding_profile_revision_id"]
    assert payload["workflow_bindings"][0]["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert payload["workflow_bindings"][1]["resolved_profile"]["workflow"]["workflow_revision"] == 5


@pytest.mark.django_db
def test_pool_workflow_bindings_collection_put_applies_atomic_replace_and_returns_new_etag(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    first_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_pool_workflow_binding_payload(
            pool=pool,
            workflow_definition_key="services-publication",
            workflow_revision=3,
            direction=PoolRunDirection.TOP_DOWN,
            mode=PoolRunMode.SAFE,
        ),
        actor_username="collection-put-test",
    )
    second_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_pool_workflow_binding_payload(
            pool=pool,
            workflow_definition_key="bottom-up-import",
            workflow_revision=5,
            direction=PoolRunDirection.BOTTOM_UP,
            mode=PoolRunMode.SAFE,
        ),
        actor_username="collection-put-test",
    )
    initial_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    first_attachment = initial_payload["workflow_bindings"][0]
    updated_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=4,
    )
    replacement_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication-v2",
        workflow_revision=8,
    )

    put_response = authenticated_client.put(
        "/api/v2/pools/workflow-bindings/",
        {
            "pool_id": str(pool.id),
            "expected_collection_etag": initial_payload["collection_etag"],
            "workflow_bindings": [
                _attachment_payload_from_read_model(
                    first_attachment,
                    binding_profile_revision_id=updated_revision["binding_profile_revision_id"],
                    status="inactive",
                ),
                _build_pool_workflow_binding_attachment_payload(
                    binding_profile_revision_id=str(replacement_revision["binding_profile_revision_id"]),
                    binding_id="replacement-binding",
                    direction=PoolRunDirection.TOP_DOWN,
                    mode=PoolRunMode.UNSAFE,
                ),
            ],
        },
        format="json",
    )

    assert put_response.status_code == 200
    payload = put_response.json()
    assert payload["pool_id"] == str(pool.id)
    assert payload["collection_etag"] != initial_payload["collection_etag"]
    assert [item["binding_id"] for item in payload["workflow_bindings"]] == [
        first_binding["binding_id"],
        "replacement-binding",
    ]
    assert payload["workflow_bindings"][0]["revision"] == 2
    assert payload["workflow_bindings"][0]["status"] == "inactive"
    assert payload["workflow_bindings"][0]["binding_profile_revision_id"] == (
        updated_revision["binding_profile_revision_id"]
    )
    assert payload["workflow_bindings"][0]["resolved_profile"]["workflow"]["workflow_revision"] == 4
    assert payload["workflow_bindings"][1]["revision"] == 1

    stored_bindings = list_pool_workflow_bindings(pool=pool)
    assert [item["binding_id"] for item in stored_bindings] == [
        first_binding["binding_id"],
        "replacement-binding",
    ]
    assert stored_bindings[0]["resolved_profile"]["workflow"]["workflow_revision"] == 4
    assert second_binding["binding_id"] not in {item["binding_id"] for item in stored_bindings}


@pytest.mark.django_db
def test_pool_workflow_bindings_collection_put_returns_conflict_without_partial_apply(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    created_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_pool_workflow_binding_payload(
            pool=pool,
            workflow_definition_key="services-publication",
            workflow_revision=3,
            direction=PoolRunDirection.TOP_DOWN,
            mode=PoolRunMode.SAFE,
        ),
        actor_username="collection-conflict-test",
    )
    stale_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert stale_response.status_code == 200
    stale_payload = stale_response.json()
    stale_attachment = stale_payload["workflow_bindings"][0]

    winner_response = authenticated_client.put(
        "/api/v2/pools/workflow-bindings/",
        {
            "pool_id": str(pool.id),
            "expected_collection_etag": stale_payload["collection_etag"],
            "workflow_bindings": [_attachment_payload_from_read_model(stale_attachment, status="inactive")],
        },
        format="json",
    )
    assert winner_response.status_code == 200
    winner_payload = winner_response.json()
    late_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="late-binding",
        workflow_revision=9,
    )

    conflict_response = authenticated_client.put(
        "/api/v2/pools/workflow-bindings/",
        {
            "pool_id": str(pool.id),
            "expected_collection_etag": stale_payload["collection_etag"],
            "workflow_bindings": [
                _attachment_payload_from_read_model(stale_attachment, status="draft"),
                _build_pool_workflow_binding_attachment_payload(
                    binding_profile_revision_id=str(late_revision["binding_profile_revision_id"]),
                    binding_id="late-binding",
                    direction=PoolRunDirection.TOP_DOWN,
                    mode=PoolRunMode.UNSAFE,
                ),
            ],
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        conflict_response,
        status_code=409,
        code="POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT",
    )
    assert payload["errors"] == [
        {
            "expected_collection_etag": stale_payload["collection_etag"],
            "actual_collection_etag": winner_payload["collection_etag"],
        }
    ]

    current_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert current_response.status_code == 200
    assert current_response.json() == winner_payload


@pytest.mark.django_db
def test_pool_workflow_bindings_collection_put_rejects_inline_workflow_override_without_partial_apply(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_pool_workflow_binding_payload(
            pool=pool,
            workflow_definition_key="services-publication",
            workflow_revision=3,
            direction=PoolRunDirection.TOP_DOWN,
            mode=PoolRunMode.SAFE,
        ),
        actor_username="collection-duplicate-slot-test",
    )
    initial_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert initial_response.status_code == 200
    initial_payload = initial_response.json()

    response = authenticated_client.put(
        "/api/v2/pools/workflow-bindings/",
        {
            "pool_id": str(pool.id),
            "expected_collection_etag": initial_payload["collection_etag"],
            "workflow_bindings": [
                {
                    **_attachment_payload_from_read_model(initial_payload["workflow_bindings"][0]),
                    "workflow": {
                        "workflow_definition_key": "services-publication",
                        "workflow_revision_id": str(uuid4()),
                        "workflow_revision": 9,
                        "workflow_name": "services_publication",
                    },
                }
            ],
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "workflow" in payload["detail"]

    current_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert current_response.status_code == 200
    assert current_response.json() == initial_payload


@pytest.mark.django_db
def test_pool_workflow_bindings_collection_put_rejects_inline_decisions_override_without_partial_apply(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_pool_workflow_binding_payload(
            pool=pool,
            workflow_definition_key="services-publication",
            workflow_revision=3,
            direction=PoolRunDirection.TOP_DOWN,
            mode=PoolRunMode.SAFE,
        ),
        actor_username="collection-slot-required-test",
    )
    initial_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert initial_response.status_code == 200
    initial_payload = initial_response.json()

    response = authenticated_client.put(
        "/api/v2/pools/workflow-bindings/",
        {
            "pool_id": str(pool.id),
            "expected_collection_etag": initial_payload["collection_etag"],
            "workflow_bindings": [
                {
                    **_attachment_payload_from_read_model(initial_payload["workflow_bindings"][0]),
                    "decisions": [
                        {
                            "decision_table_id": "decision-a",
                            "decision_key": "document_policy",
                            "slot_key": "document_policy",
                            "decision_revision": 1,
                        }
                    ],
                }
            ],
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "decisions" in payload["detail"]

    current_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    assert current_response.status_code == 200
    assert current_response.json() == initial_payload


@pytest.mark.django_db
def test_pool_workflow_binding_upsert_creates_and_updates_first_class_binding(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    initial_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        parameters={"publication_variant": "full"},
        role_mapping={"initiator": "finance"},
    )
    create_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(initial_revision["binding_profile_revision_id"]),
                direction="top_down",
                mode="safe",
                tags=["baseline"],
            ),
        },
        format="json",
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["created"] is True
    binding_id = created_payload["workflow_binding"]["binding_id"]
    assert binding_id
    assert created_payload["workflow_binding"]["pool_id"] == str(pool.id)
    assert created_payload["workflow_binding"]["revision"] == 1
    assert created_payload["workflow_binding"]["binding_profile_revision_id"] == (
        initial_revision["binding_profile_revision_id"]
    )
    assert created_payload["workflow_binding"]["resolved_profile"]["workflow"]["workflow_definition_key"] == (
        "services-publication"
    )
    updated_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=4,
        parameters={"publication_variant": "delta"},
        role_mapping={"initiator": "ops"},
    )

    update_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(updated_revision["binding_profile_revision_id"]),
                binding_id=binding_id,
                revision=created_payload["workflow_binding"]["revision"],
                direction="top_down",
                mode="safe",
                tags=["baseline", "monthly"],
                effective_to="2026-12-31",
                status="inactive",
            ),
        },
        format="json",
    )

    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["created"] is False
    assert updated_payload["workflow_binding"]["binding_id"] == binding_id
    assert updated_payload["workflow_binding"]["revision"] == 2
    assert updated_payload["workflow_binding"]["binding_profile_revision_id"] == (
        updated_revision["binding_profile_revision_id"]
    )
    assert updated_payload["workflow_binding"]["resolved_profile"]["workflow"]["workflow_revision"] == 4
    assert updated_payload["workflow_binding"]["effective_to"] == "2026-12-31"
    assert updated_payload["workflow_binding"]["status"] == "inactive"

    pool.refresh_from_db()
    bindings = list_pool_workflow_bindings(pool=pool)
    assert len(bindings) == 1
    assert bindings[0]["binding_id"] == binding_id
    assert bindings[0]["revision"] == 2
    assert bindings[0]["selector"]["tags"] == ["baseline", "monthly"]
    assert bindings[0]["resolved_profile"]["workflow"]["workflow_revision"] == 4


@pytest.mark.django_db
def test_pool_workflow_binding_upsert_rejects_inline_workflow_override_payload(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    profile_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=3,
    )
    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": {
                "binding_profile_revision_id": profile_revision["binding_profile_revision_id"],
                "workflow": {
                    "workflow_definition_key": "services-publication",
                    "workflow_revision_id": str(uuid4()),
                    "workflow_revision": 9,
                    "workflow_name": "services_publication",
                },
                "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
                "effective_from": "2026-01-01",
                "status": "active",
            },
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "workflow" in payload["detail"]
    assert list_pool_workflow_bindings(pool=pool) == []


@pytest.mark.django_db
def test_pool_workflow_binding_upsert_rejects_inline_decisions_override_payload(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    profile_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=3,
    )
    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": {
                "binding_profile_revision_id": profile_revision["binding_profile_revision_id"],
                "decisions": [
                    {
                        "decision_table_id": "decision-a",
                        "decision_key": "document_policy",
                        "slot_key": "document_policy",
                        "decision_revision": 1,
                    }
                ],
                "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
                "effective_from": "2026-01-01",
                "status": "active",
            },
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "decisions" in payload["detail"]
    assert list_pool_workflow_bindings(pool=pool) == []


@pytest.mark.django_db
def test_pool_workflow_binding_upsert_requires_revision_for_update(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    profile_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=3,
    )
    create_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(profile_revision["binding_profile_revision_id"]),
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
            ),
        },
        format="json",
    )
    assert create_response.status_code == 201
    created_binding = create_response.json()["workflow_binding"]

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(profile_revision["binding_profile_revision_id"]),
                binding_id=created_binding["binding_id"],
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
                status="inactive",
            ),
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "revision is required" in payload["detail"]


@pytest.mark.django_db
def test_pool_workflow_binding_upsert_returns_conflict_for_stale_revision(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    initial_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=3,
    )
    create_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(initial_revision["binding_profile_revision_id"]),
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
            ),
        },
        format="json",
    )
    assert create_response.status_code == 201
    created_binding = create_response.json()["workflow_binding"]
    winner_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=4,
    )
    winner_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(winner_revision["binding_profile_revision_id"]),
                binding_id=created_binding["binding_id"],
                revision=created_binding["revision"],
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
                status="inactive",
            ),
        },
        format="json",
    )
    assert winner_response.status_code == 200

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(winner_revision["binding_profile_revision_id"]),
                binding_id=created_binding["binding_id"],
                revision=created_binding["revision"],
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
                status="draft",
            ),
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=409,
        code="POOL_WORKFLOW_BINDING_REVISION_CONFLICT",
    )
    assert "latest revision" in payload["detail"]
    assert payload["errors"] == [
        {
            "binding_id": created_binding["binding_id"],
            "expected_revision": 1,
            "actual_revision": 2,
            "operation": "update",
        }
    ]


@pytest.mark.django_db
def test_pool_workflow_binding_delete_removes_binding_from_pool(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=binding,
        actor_username="pool-delete-test",
    )
    stored_binding = list_pool_workflow_bindings(pool=pool)[0]

    response = authenticated_client.delete(
        f"/api/v2/pools/workflow-bindings/{binding['binding_id']}/?pool_id={pool.id}&revision={stored_binding['revision']}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert payload["workflow_binding"]["revision"] == 1
    assert payload["workflow_binding"]["binding_profile_revision_id"]

    pool.refresh_from_db()
    assert list_pool_workflow_bindings(pool=pool) == []


@pytest.mark.django_db
def test_pool_workflow_binding_delete_requires_revision_query_param(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=binding,
        actor_username="pool-delete-missing-revision-test",
    )

    response = authenticated_client.delete(
        f"/api/v2/pools/workflow-bindings/{binding['binding_id']}/?pool_id={pool.id}"
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "revision" in payload["detail"]


@pytest.mark.django_db
def test_pool_workflow_binding_delete_returns_conflict_for_stale_revision(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    initial_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=3,
    )
    create_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(initial_revision["binding_profile_revision_id"]),
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
            ),
        },
        format="json",
    )
    assert create_response.status_code == 201
    created_binding = create_response.json()["workflow_binding"]
    updated_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=4,
    )
    update_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(updated_revision["binding_profile_revision_id"]),
                binding_id=created_binding["binding_id"],
                revision=created_binding["revision"],
                direction=PoolRunDirection.TOP_DOWN,
                mode=PoolRunMode.SAFE,
                status="inactive",
            ),
        },
        format="json",
    )
    assert update_response.status_code == 200
    updated_binding = update_response.json()["workflow_binding"]

    response = authenticated_client.delete(
        f"/api/v2/pools/workflow-bindings/{created_binding['binding_id']}/?pool_id={pool.id}&revision={created_binding['revision']}"
    )

    payload = _assert_problem_details_response(
        response,
        status_code=409,
        code="POOL_WORKFLOW_BINDING_REVISION_CONFLICT",
    )
    assert "latest revision" in payload["detail"]
    assert payload["errors"] == [
        {
            "binding_id": created_binding["binding_id"],
            "expected_revision": 1,
            "actual_revision": updated_binding["revision"],
            "operation": "delete",
        }
    ]


@pytest.mark.django_db
def test_pool_workflow_binding_detail_reads_first_class_binding(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=binding,
        actor_username="pool-detail-test",
    )

    response = authenticated_client.get(
        f"/api/v2/pools/workflow-bindings/{binding['binding_id']}/?pool_id={pool.id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert payload["workflow_binding"]["pool_id"] == str(pool.id)
    assert payload["workflow_binding"]["revision"] == 1
    assert payload["workflow_binding"]["binding_profile_revision_id"]
    assert payload["workflow_binding"]["resolved_profile"]["workflow"]["workflow_revision"] == 3


@pytest.mark.django_db
def test_pool_workflow_bindings_list_ignores_invalid_legacy_metadata_after_cutover(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    pool.metadata = {
        "workflow_bindings": [
            {
                "binding_id": "broken-binding",
                "pool_id": str(pool.id),
                "workflow": {
                    "workflow_definition_key": "services-publication",
                    "workflow_revision_id": "11111111-1111-1111-1111-111111111111",
                    "workflow_revision": 3,
                    "workflow_name": "services_publication",
                },
                "effective_from": "2026-01-01",
                "effective_to": "2025-01-01",
                "status": "active",
            }
        ]
    }
    pool.save(update_fields=["metadata", "updated_at"])

    response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_bindings"] == []
    assert isinstance(payload["collection_etag"], str)
    assert payload["blocking_remediation"] == {
        "code": "LEGACY_METADATA_WORKFLOW_BINDINGS_PRESENT",
        "title": "Legacy workflow bindings remediation required",
        "detail": (
            "Canonical binding collection is empty while legacy pool.metadata.workflow_bindings "
            "payload is still present. Run explicit remediation before using the default workspace."
        ),
    }


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_creates_graph_for_date(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Root Org", inn="741000000001")
    middle_org = Organization.objects.create(tenant=default_tenant, name="Middle Org", inn="741000000002")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Leaf Org", inn="741000000003")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "effective_to": None,
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(middle_org.id), "is_root": False},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(middle_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(middle_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pool_id"] == str(pool.id)
    assert payload["nodes_count"] == 3
    assert payload["edges_count"] == 2
    assert isinstance(payload["version"], str) and payload["version"]

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert isinstance(graph_payload["version"], str) and graph_payload["version"]
    assert len(graph_payload["nodes"]) == 3
    assert len(graph_payload["edges"]) == 2
    assert any(node["is_root"] for node in graph_payload["nodes"])


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_preserves_node_and_edge_order_in_graph_response(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Order Root", inn="741010000001")
    child_z_org = Organization.objects.create(tenant=default_tenant, name="Z Child", inn="741010000002")
    child_a_org = Organization.objects.create(tenant=default_tenant, name="A Child", inn="741010000003")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    save_response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "effective_to": None,
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(child_z_org.id), "is_root": False},
                {"organization_id": str(child_a_org.id), "is_root": False},
            ],
            # Intentionally keep non-alphabetical order to ensure API response
            # does not auto-sort by organization name.
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(child_z_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(child_a_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert save_response.status_code == 200

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()

    node_order = [node["organization_id"] for node in graph_payload["nodes"]]
    assert node_order == [
        str(root_org.id),
        str(child_z_org.id),
        str(child_a_org.id),
    ]

    node_org_by_node_version = {
        node["node_version_id"]: node["organization_id"]
        for node in graph_payload["nodes"]
    }
    edge_order = [
        (
            node_org_by_node_version[edge["parent_node_version_id"]],
            node_org_by_node_version[edge["child_node_version_id"]],
        )
        for edge in graph_payload["edges"]
    ]
    assert edge_order == [
        (str(root_org.id), str(child_z_org.id)),
        (str(root_org.id), str(child_a_org.id)),
    ]


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_legacy_document_policy_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Policy Root", inn="741100000001")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Policy Leaf", inn="741100000002")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    graph_before_payload = graph_before.json()
    current_version = graph_before_payload["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                    "metadata": {
                        "document_policy": _build_document_policy_payload(),
                    },
                },
            ],
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
    )
    assert "edges[0].metadata.document_policy" in payload["detail"]

    graph_after = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_after.status_code == 200
    assert graph_after.json() == graph_before_payload
    assert not PoolEdgeVersion.objects.filter(
        pool=pool,
        effective_from=date(2026, 1, 1),
        parent_node__organization=root_org,
        child_node__organization=leaf_org,
    ).exists()


@pytest.mark.django_db
def test_get_pool_graph_returns_node_and_edge_metadata_including_document_policy_key(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Graph Metadata Root", inn="741100000031")
    leaf_org = Organization.objects.create(
        tenant=default_tenant,
        name="Graph Metadata Leaf",
        inn="741100000032",
    )
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {
                    "organization_id": str(root_org.id),
                    "is_root": True,
                    "metadata": {"node_tag": "root-tag"},
                },
                {
                    "organization_id": str(leaf_org.id),
                    "is_root": False,
                    "metadata": {"node_tag": "leaf-tag"},
                },
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                    "metadata": {
                        "edge_tag": "edge-tag",
                        "document_policy_key": "sale",
                    },
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 200

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_response.status_code == 200
    payload = graph_response.json()

    nodes_by_org = {item["organization_id"]: item for item in payload["nodes"]}
    assert nodes_by_org[str(root_org.id)]["metadata"] == {"node_tag": "root-tag"}
    assert nodes_by_org[str(leaf_org.id)]["metadata"] == {"node_tag": "leaf-tag"}

    assert len(payload["edges"]) == 1
    edge_metadata = payload["edges"][0]["metadata"]
    assert edge_metadata["edge_tag"] == "edge-tag"
    assert edge_metadata["document_policy_key"] == "sale"


@pytest.mark.django_db
def test_topology_templates_collection_creates_revision_without_concrete_organizations(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/topology-templates/",
        {
            "code": "branching-topology",
            "name": "Branching Topology",
            "revision": {
                "nodes": [
                    {"slot_key": "root", "label": "Root", "is_root": True},
                    {"slot_key": "branch_a", "label": "Branch A"},
                    {"slot_key": "leaf_receipt", "label": "Leaf Receipt"},
                ],
                "edges": [
                    {
                        "parent_slot_key": "root",
                        "child_slot_key": "branch_a",
                        "document_policy_key": "realization",
                    },
                    {
                        "parent_slot_key": "branch_a",
                        "child_slot_key": "leaf_receipt",
                        "document_policy_key": "receipt",
                    },
                ],
            },
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()["topology_template"]
    assert payload["code"] == "branching-topology"
    assert payload["latest_revision_number"] == 1
    assert payload["latest_revision"]["nodes"][0]["slot_key"] == "root"
    assert "organization_id" not in payload["latest_revision"]["nodes"][0]

    template = TopologyTemplate.objects.get(tenant=default_tenant, code="branching-topology")
    revision = TopologyTemplateRevision.objects.get(template=template, revision_number=1)
    assert revision.nodes[0]["slot_key"] == "root"
    assert "organization_id" not in revision.nodes[0]


@pytest.mark.django_db
def test_topology_templates_collection_rejects_non_object_revision_metadata_without_orphan_template(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/topology-templates/",
        {
            "code": "invalid-metadata-template",
            "name": "Invalid Metadata Template",
            "revision": {
                "nodes": [
                    {"slot_key": "root", "label": "Root", "is_root": True},
                ],
                "metadata": ["invalid"],
            },
        },
        format="json",
    )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "metadata must be an object" in problem["detail"]
    assert not TopologyTemplate.objects.filter(
        tenant=default_tenant,
        code="invalid-metadata-template",
    ).exists()


@pytest.mark.django_db
def test_topology_template_revision_create_rejects_non_object_metadata(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    topology_template = _create_topology_template_via_api(
        authenticated_client,
        code="revision-invalid-metadata-template",
        name="Revision Invalid Metadata Template",
        revision={
            "nodes": [
                {"slot_key": "root", "is_root": True},
            ],
        },
    )

    response = authenticated_client.post(
        f"/api/v2/pools/topology-templates/{topology_template['topology_template_id']}/revisions/",
        {
            "revision": {
                "nodes": [
                    {"slot_key": "root", "is_root": True},
                ],
                "metadata": ["invalid"],
            }
        },
        format="json",
    )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="VALIDATION_ERROR",
    )
    assert "metadata must be an object" in problem["detail"]

    template = TopologyTemplate.objects.get(
        tenant=default_tenant,
        id=UUID(topology_template["topology_template_id"]),
    )
    assert TopologyTemplateRevision.objects.filter(template=template).count() == 1


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_materializes_template_revision_into_concrete_graph(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    topology_template = _create_topology_template_via_api(
        authenticated_client,
        code="linear-topology",
        name="Linear Topology",
        revision={
            "nodes": [
                {"slot_key": "root", "label": "Root", "is_root": True},
                {"slot_key": "leaf", "label": "Leaf"},
            ],
            "edges": [
                {
                    "parent_slot_key": "root",
                    "child_slot_key": "leaf",
                    "document_policy_key": "receipt",
                }
            ],
        },
    )
    revision = topology_template["latest_revision"]
    root_org = Organization.objects.create(tenant=default_tenant, name="Template Root", inn="741200000001")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Template Leaf", inn="741200000002")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "topology_template_revision_id": revision["topology_template_revision_id"],
            "slot_assignments": [
                {"slot_key": "root", "organization_id": str(root_org.id)},
                {"slot_key": "leaf", "organization_id": str(leaf_org.id)},
            ],
        },
        format="json",
    )

    assert response.status_code == 200
    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert [node["organization_id"] for node in graph_payload["nodes"]] == [
        str(root_org.id),
        str(leaf_org.id),
    ]
    assert graph_payload["edges"][0]["metadata"]["document_policy_key"] == "receipt"

    pool.refresh_from_db()
    instantiation = pool.metadata["topology_template_instantiation"]
    assert instantiation["topology_template_revision_id"] == revision["topology_template_revision_id"]
    assert instantiation["slot_assignments"] == [
        {"slot_key": "root", "organization_id": str(root_org.id)},
        {"slot_key": "leaf", "organization_id": str(leaf_org.id)},
    ]


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_applies_edge_selector_override_for_template_edge(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    topology_template = _create_topology_template_via_api(
        authenticated_client,
        code="override-topology",
        name="Override Topology",
        revision={
            "nodes": [
                {"slot_key": "root", "is_root": True},
                {"slot_key": "leaf"},
            ],
            "edges": [
                {
                    "parent_slot_key": "root",
                    "child_slot_key": "leaf",
                    "document_policy_key": "receipt",
                }
            ],
        },
    )
    revision = topology_template["latest_revision"]
    root_org = Organization.objects.create(tenant=default_tenant, name="Override Root", inn="741200000011")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Override Leaf", inn="741200000012")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "topology_template_revision_id": revision["topology_template_revision_id"],
            "slot_assignments": [
                {"slot_key": "root", "organization_id": str(root_org.id)},
                {"slot_key": "leaf", "organization_id": str(leaf_org.id)},
            ],
            "edge_selector_overrides": [
                {
                    "parent_slot_key": "root",
                    "child_slot_key": "leaf",
                    "document_policy_key": "sale",
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 200
    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["edges"][0]["metadata"]["document_policy_key"] == "sale"


@pytest.mark.django_db
def test_new_topology_template_revision_does_not_retroactively_change_pinned_pool_graph(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    topology_template = _create_topology_template_via_api(
        authenticated_client,
        code="pinned-topology",
        name="Pinned Topology",
        revision={
            "nodes": [
                {"slot_key": "root", "is_root": True},
                {"slot_key": "leaf"},
            ],
            "edges": [
                {
                    "parent_slot_key": "root",
                    "child_slot_key": "leaf",
                    "document_policy_key": "realization",
                }
            ],
        },
    )
    revision_v1 = topology_template["latest_revision"]
    root_org = Organization.objects.create(tenant=default_tenant, name="Pinned Root", inn="741200000021")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Pinned Leaf", inn="741200000022")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    current_version = graph_before.json()["version"]
    save_response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "topology_template_revision_id": revision_v1["topology_template_revision_id"],
            "slot_assignments": [
                {"slot_key": "root", "organization_id": str(root_org.id)},
                {"slot_key": "leaf", "organization_id": str(leaf_org.id)},
            ],
        },
        format="json",
    )
    assert save_response.status_code == 200

    revision_response = authenticated_client.post(
        f"/api/v2/pools/topology-templates/{topology_template['topology_template_id']}/revisions/",
        {
            "revision": {
                "nodes": [
                    {"slot_key": "root", "is_root": True},
                    {"slot_key": "leaf"},
                ],
                "edges": [
                    {
                        "parent_slot_key": "root",
                        "child_slot_key": "leaf",
                        "document_policy_key": "receipt",
                    }
                ],
            }
        },
        format="json",
    )

    assert revision_response.status_code == 201
    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    assert graph_response.json()["edges"][0]["metadata"]["document_policy_key"] == "realization"

    pool.refresh_from_db()
    assert (
        pool.metadata["topology_template_instantiation"]["topology_template_revision_id"]
        == revision_v1["topology_template_revision_id"]
    )


@pytest.mark.django_db
def test_migrate_pool_edge_document_policy_updates_canonical_binding_runtime_path(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    leaf_db = _create_database(
        tenant=default_tenant,
        name=f"migration-leaf-db-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    snapshot = _create_current_metadata_catalog_snapshot(
        tenant=default_tenant,
        database=leaf_db,
    )
    _create_service_infobase_mapping(database=leaf_db)
    _create_actor_infobase_mapping(
        database=leaf_db,
        user=user,
        username="migration-leaf-actor",
    )
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=default_tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication-safe",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            ),
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication-unsafe",
                workflow_revision=4,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.UNSAFE,
            ),
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    initial_bindings_by_id = {
        str(binding["binding_id"]): binding
        for binding in list_pool_workflow_bindings(pool=pool)
    }
    root_node = PoolNodeVersion.objects.get(
        pool=pool,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    root_org = root_node.organization
    leaf_org = Organization.objects.create(
        tenant=default_tenant,
        database=leaf_db,
        name="Migration Leaf",
        inn="741100000062",
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf_org,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    policy = _build_document_policy_payload()
    policy["chains"][0]["chain_id"] = "migrated_sale_chain"
    normalized_policy = resolve_document_policy_from_edge_metadata(
        metadata={"document_policy": policy}
    )
    assert normalized_policy is not None
    edge = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        metadata={"document_policy": policy},
    )

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/document-policy-migrations/",
        {"edge_version_id": str(edge.id)},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    decision_payload = payload["decision"]
    migration = payload["migration"]
    migrated_slot_key = str(migration["slot_key"])
    assert decision_payload["decision_key"] == "document_policy"
    assert decision_payload["decision_revision"] == 1
    assert decision_payload["rules"][0]["outputs"]["document_policy"] == normalized_policy
    assert migration["created"] is True
    assert migration["binding_update_required"] is False
    assert migrated_slot_key
    assert migrated_slot_key != "document_policy"
    assert migration["legacy_payload_removed"] is True
    assert migration["source"]["pool_id"] == str(pool.id)
    assert migration["source"]["edge_version_id"] == str(edge.id)
    assert migration["source"]["source_path"] == "edge.metadata.document_policy"
    assert migration["decision_ref"]["decision_table_id"] == decision_payload["decision_table_id"]
    assert migration["decision_ref"]["decision_revision"] == decision_payload["decision_revision"]
    assert {item["binding_id"] for item in migration["affected_bindings"]} == {
        str(binding["binding_id"]) for binding in bindings
    }

    decision = DecisionTable.objects.get(id=decision_payload["id"])
    assert decision.metadata_context["snapshot_id"] == str(snapshot.id)
    assert decision.source_provenance["kind"] == "legacy_edge_document_policy"
    assert decision.source_provenance["edge_version_id"] == str(edge.id)
    assert decision.source_provenance["parent_organization_id"] == str(root_org.id)
    assert decision.source_provenance["child_organization_id"] == str(leaf_org.id)
    assert decision.source_provenance["child_database_id"] == str(leaf_db.id)

    migrated_decision_ref = {
        "decision_table_id": decision_payload["decision_table_id"],
        "decision_key": "document_policy",
        "slot_key": migrated_slot_key,
        "decision_revision": decision_payload["decision_revision"],
    }
    updated_bindings_by_id = {
        str(binding["binding_id"]): binding
        for binding in list_pool_workflow_bindings(pool=pool)
    }
    assert set(updated_bindings_by_id) == {str(binding["binding_id"]) for binding in bindings}
    for binding in bindings:
        binding_id = str(binding["binding_id"])
        initial_binding = initial_bindings_by_id[binding_id]
        updated_binding = updated_bindings_by_id[binding_id]
        assert updated_binding["revision"] == initial_binding["revision"] + 1
        assert updated_binding["resolved_profile"]["decisions"] == [migrated_decision_ref]

    edge.refresh_from_db()
    assert edge.metadata["document_policy_key"] == migrated_slot_key
    assert "document_policy" not in edge.metadata

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["edges"][0]["metadata"]["document_policy_key"] == migrated_slot_key
    assert "document_policy" not in graph_payload["edges"][0]["metadata"]

    with patch(
        "apps.intercompany_pools.metadata_catalog.read_metadata_catalog_snapshot",
        side_effect=AssertionError("post-cutover runtime must not reread metadata snapshots"),
    ):
        preview_response = authenticated_client.post(
            "/api/v2/pools/workflow-bindings/preview/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": bindings[0]["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
                "mode": PoolRunMode.SAFE,
            },
            format="json",
        )

        assert preview_response.status_code == 200, preview_response.json()
        preview_payload = preview_response.json()
        assert preview_payload["workflow_binding"]["resolved_profile"]["decisions"] == [migrated_decision_ref]
        assert "decisions" not in preview_payload["workflow_binding"]
        assert preview_payload["compiled_document_policy"]["chains"][0]["chain_id"] == "migrated_sale_chain"
        assert preview_payload["runtime_projection"]["workflow_binding"]["decision_refs"] == [
            migrated_decision_ref
        ]
        assert (
            preview_payload["runtime_projection"]["document_policy_projection"]["slot_coverage_summary"]["counts"]["resolved"]
            == 1
        )

        with patch(
            "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
            return_value=EnqueueResult(success=True, operation_id="migration-runtime-op", status="queued"),
        ):
            create_response = authenticated_client.post(
                "/api/v2/pools/runs/",
                {
                    "pool_id": str(pool.id),
                    "pool_workflow_binding_id": bindings[1]["binding_id"],
                    "direction": PoolRunDirection.BOTTOM_UP,
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-31",
                    "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
                    "mode": PoolRunMode.UNSAFE,
                },
                format="json",
            )

    assert create_response.status_code == 201, create_response.json()
    create_payload = create_response.json()
    workflow_execution = WorkflowExecution.objects.get(id=create_payload["run"]["workflow_execution_id"])
    assert workflow_execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)["binding_id"] == (
        bindings[1]["binding_id"]
    )
    assert workflow_execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)["decisions"] == [
        migrated_decision_ref
    ]
    assert workflow_execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["workflow_binding"][
        "decision_refs"
    ] == [migrated_decision_ref]
    assert workflow_execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["document_policy_projection"][
        "slot_coverage_summary"
    ]["counts"]["resolved"] == 1
    assert workflow_execution.input_context.get(
        POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY
    )["chains"][0]["chain_id"] == "migrated_sale_chain"
    assert workflow_execution.input_context.get(POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY) == (
        "workflow_binding.decision_table:"
        f"{decision_payload['decision_table_id']}:v{decision_payload['decision_revision']}"
    )


@pytest.mark.django_db
def test_migrate_pool_edge_document_policy_reuses_existing_revision_for_same_edge(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    leaf_db = _create_database(
        tenant=default_tenant,
        name=f"migration-reuse-db-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_current_metadata_catalog_snapshot(
        tenant=default_tenant,
        database=leaf_db,
    )
    _create_service_infobase_mapping(database=leaf_db)
    root_org = Organization.objects.create(
        tenant=default_tenant,
        name="Migration Reuse Root",
        inn="741100000063",
    )
    leaf_org = Organization.objects.create(
        tenant=default_tenant,
        database=leaf_db,
        name="Migration Reuse Leaf",
        inn="741100000064",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf_org,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    edge = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        metadata={"document_policy": _build_document_policy_payload()},
    )

    first_response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/document-policy-migrations/",
        {"edge_version_id": str(edge.id)},
        format="json",
    )
    assert first_response.status_code == 201
    first_payload = first_response.json()

    second_response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/document-policy-migrations/",
        {"edge_version_id": str(edge.id)},
        format="json",
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["migration"]["created"] is False
    assert second_payload["migration"]["reused_existing_revision"] is True
    assert second_payload["decision"]["id"] == first_payload["decision"]["id"]
    assert second_payload["decision"]["decision_revision"] == first_payload["decision"]["decision_revision"]
    assert DecisionTable.objects.filter(decision_key="document_policy").count() == 1


@pytest.mark.django_db
def test_migrate_pool_edge_document_policy_rejects_edge_without_policy(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(
        tenant=default_tenant,
        name="Migration No Policy Root",
        inn="741100000065",
    )
    leaf_org = Organization.objects.create(
        tenant=default_tenant,
        name="Migration No Policy Leaf",
        inn="741100000066",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf_org,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    edge = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        metadata={"edge_tag": "legacy-only"},
    )

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/document-policy-migrations/",
        {"edge_version_id": str(edge.id)},
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_DOCUMENT_POLICY_NOT_FOUND",
    )
    assert "edge.metadata.document_policy" in str(payload["detail"])


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_invalid_cycle(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    left_org = Organization.objects.create(tenant=default_tenant, name="Cycle Left", inn="742000000001")
    right_org = Organization.objects.create(tenant=default_tenant, name="Cycle Right", inn="742000000002")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(left_org.id), "is_root": True},
                {"organization_id": str(right_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(left_org.id),
                    "child_organization_id": str(right_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(right_org.id),
                    "child_organization_id": str(left_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_stale_version_with_problem_details(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Version Root", inn="742000000011")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Version Leaf", inn="742000000012")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    stale_version = graph_before.json()["version"]

    first_save = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": stale_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert first_save.status_code == 200

    conflict = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": stale_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "0.8",
                },
            ],
        },
        format="json",
    )
    payload = _assert_problem_details_response(
        conflict,
        status_code=409,
        code="TOPOLOGY_VERSION_CONFLICT",
    )
    assert "latest version token" in payload["detail"]


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rolls_over_previous_open_period(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Legacy Root", inn="742100000001")
    middle_org = Organization.objects.create(tenant=default_tenant, name="Legacy Middle", inn="742100000002")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Legacy Leaf", inn="742100000003")
    head_org = Organization.objects.create(tenant=default_tenant, name="New Head", inn="742100000004")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    version_jan = graph_before.json()["version"]

    first_save = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": version_jan,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(middle_org.id), "is_root": False},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(middle_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(middle_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert first_save.status_code == 200

    graph_feb_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-02-24")
    assert graph_feb_before.status_code == 200
    version_feb = graph_feb_before.json()["version"]

    second_save = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": version_feb,
            "effective_from": "2026-02-24",
            "nodes": [
                {"organization_id": str(head_org.id), "is_root": True},
                {"organization_id": str(root_org.id), "is_root": False},
                {"organization_id": str(middle_org.id), "is_root": False},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(head_org.id),
                    "child_organization_id": str(root_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(middle_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(middle_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert second_save.status_code == 200

    jan_graph = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert jan_graph.status_code == 200
    jan_payload = jan_graph.json()
    assert len(jan_payload["nodes"]) == 3
    assert len(jan_payload["edges"]) == 2
    assert str(head_org.id) not in {item["organization_id"] for item in jan_payload["nodes"]}

    feb_graph = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-02-24")
    assert feb_graph.status_code == 200
    feb_payload = feb_graph.json()
    assert len(feb_payload["nodes"]) == 4
    assert len(feb_payload["edges"]) == 3
    feb_nodes = {item["organization_id"]: item for item in feb_payload["nodes"]}
    assert feb_nodes[str(head_org.id)]["is_root"] is True

    historical_nodes = PoolNodeVersion.objects.filter(pool=pool, effective_from=date(2026, 1, 1)).order_by("organization_id")
    assert historical_nodes.count() == 3
    assert all(item.effective_to == date(2026, 2, 23) for item in historical_nodes)

    historical_edges = PoolEdgeVersion.objects.filter(pool=pool, effective_from=date(2026, 1, 1))
    assert historical_edges.count() == 2
    assert all(item.effective_to == date(2026, 2, 23) for item in historical_edges)


@pytest.mark.django_db
def test_list_pool_topology_snapshots_returns_periods_with_counts(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="List Root", inn="742200000001")
    child_org = Organization.objects.create(tenant=default_tenant, name="List Child", inn="742200000002")
    head_org = Organization.objects.create(tenant=default_tenant, name="List Head", inn="742200000003")

    jan_root = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 2, 23),
        is_root=True,
    )
    jan_child = PoolNodeVersion.objects.create(
        pool=pool,
        organization=child_org,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 2, 23),
        is_root=False,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=jan_root,
        child_node=jan_child,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 2, 23),
        weight=1,
    )

    feb_head = PoolNodeVersion.objects.create(
        pool=pool,
        organization=head_org,
        effective_from=date(2026, 2, 24),
        effective_to=None,
        is_root=True,
    )
    feb_root = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 2, 24),
        effective_to=None,
        is_root=False,
    )
    feb_child = PoolNodeVersion.objects.create(
        pool=pool,
        organization=child_org,
        effective_from=date(2026, 2, 24),
        effective_to=None,
        is_root=False,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=feb_head,
        child_node=feb_root,
        effective_from=date(2026, 2, 24),
        effective_to=None,
        weight=1,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=feb_root,
        child_node=feb_child,
        effective_from=date(2026, 2, 24),
        effective_to=None,
        weight=1,
    )

    response = authenticated_client.get(f"/api/v2/pools/{pool.id}/topology-snapshots/")
    assert response.status_code == 200
    payload = response.json()

    assert payload["pool_id"] == str(pool.id)
    assert payload["count"] == 2
    snapshots = payload["snapshots"]
    assert len(snapshots) == 2

    assert snapshots[0]["effective_from"] == "2026-02-24"
    assert snapshots[0]["effective_to"] is None
    assert snapshots[0]["nodes_count"] == 3
    assert snapshots[0]["edges_count"] == 2

    assert snapshots[1]["effective_from"] == "2026-01-01"
    assert snapshots[1]["effective_to"] == "2026-02-23"
    assert snapshots[1]["nodes_count"] == 2
    assert snapshots[1]["edges_count"] == 1


@pytest.mark.django_db
def test_create_pool_run_rejects_missing_binding_reference_when_selector_is_ambiguous(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    first_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication-a",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    second_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication-b",
        workflow_revision=4,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=first_binding,
        actor_username="pool-run-ambiguous-test",
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=second_binding,
        actor_username="pool-run-ambiguous-test",
    )

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_REQUIRED",
    )
    assert payload["detail"] == "pool_workflow_binding_id is required."
    assert payload.get("errors", []) == []
    assert not PoolRun.objects.filter(pool=pool).exists()


@pytest.mark.django_db
def test_create_pool_run_rejects_missing_binding_reference_even_with_single_candidate(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="bottom-up-only",
        workflow_revision=2,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=binding,
        actor_username="pool-run-selector-test",
    )
    assert len(list_pool_workflow_bindings(pool=pool)) == 1

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_REQUIRED",
    )
    assert payload["detail"] == "pool_workflow_binding_id is required."
    assert payload.get("errors", []) == []
    assert not PoolRun.objects.filter(pool=pool).exists()


@pytest.mark.django_db
def test_preview_pool_workflow_binding_returns_not_found_for_unknown_attachment_reference(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    missing_binding_id = f"missing-{uuid4().hex[:8]}"

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": missing_binding_id,
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_NOT_FOUND",
    )
    assert payload["detail"] == (
        f"Requested pool_workflow_binding_id '{missing_binding_id}' was not found."
    )
    assert payload["errors"] == [{"binding_id": missing_binding_id}]


@pytest.mark.django_db
def test_create_pool_run_does_not_fallback_to_legacy_metadata_workflow_bindings(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    legacy_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="legacy-only-binding",
        workflow_revision=2,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    pool.metadata = {"workflow_bindings": [legacy_binding]}
    pool.save(update_fields=["metadata", "updated_at"])
    assert list_pool_workflow_bindings(pool=pool) == []

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": legacy_binding["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_NOT_FOUND",
    )
    assert payload["detail"] == (
        f"Requested pool_workflow_binding_id '{legacy_binding['binding_id']}' was not found."
    )
    assert payload.get("errors", []) == [{"binding_id": legacy_binding["binding_id"]}]
    assert not PoolRun.objects.filter(pool=pool).exists()


@pytest.mark.django_db
def test_create_pool_run_fails_closed_for_attachment_without_profile_refs(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    legacy_binding = _create_legacy_pool_workflow_binding_without_profile_refs(
        tenant=default_tenant,
        pool=pool,
    )

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": legacy_binding.binding_id,
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING",
    )
    assert payload["title"] == "Pool Runtime Configuration Error"
    assert legacy_binding.binding_id in payload["detail"]
    assert not PoolRun.objects.filter(pool=pool).exists()


@pytest.mark.django_db
def test_create_pool_run_does_not_fallback_from_out_of_scope_attachment_to_matching_candidate(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    out_of_scope_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="out-of-scope-binding",
        workflow_revision=1,
        direction=PoolRunDirection.BOTTOM_UP,
    )
    matching_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="matching-binding",
        workflow_revision=1,
        direction=PoolRunDirection.BOTTOM_UP,
    )

    out_of_scope_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(out_of_scope_revision["binding_profile_revision_id"]),
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
                effective_from="2025-01-01",
                effective_to="2025-12-31",
            ),
        },
        format="json",
    )
    assert out_of_scope_response.status_code == 201
    requested_binding_id = out_of_scope_response.json()["workflow_binding"]["binding_id"]

    matching_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _build_pool_workflow_binding_attachment_payload(
                binding_profile_revision_id=str(matching_revision["binding_profile_revision_id"]),
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
                effective_from="2026-01-01",
            ),
        },
        format="json",
    )
    assert matching_response.status_code == 201

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": requested_binding_id,
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_NOT_RESOLVED",
    )
    assert payload["detail"] == (
        f"Requested pool_workflow_binding_id '{requested_binding_id}' is inactive "
        "or outside the effective period."
    )
    assert payload["errors"] == [
        {
            "binding_id": requested_binding_id,
            "pool_id": str(pool.id),
            "workflow_definition_key": str(out_of_scope_revision["workflow"]["workflow_definition_key"]),
            "workflow_revision": int(out_of_scope_revision["workflow"]["workflow_revision"]),
            "status": "active",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "selector": {
                "direction": PoolRunDirection.BOTTOM_UP,
                "mode": PoolRunMode.SAFE,
                "tags": [],
            },
        }
    ]
    assert not PoolRun.objects.filter(pool=pool).exists()


@pytest.mark.django_db
def test_create_pool_run_accepts_explicit_workflow_binding_id_when_selector_is_ambiguous(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    first_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication-a",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    second_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication-b",
        workflow_revision=4,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[first_binding, second_binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    first_binding = bindings[0]

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="binding-op", status="queued"),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": first_binding["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
                "mode": PoolRunMode.SAFE,
            },
            format="json",
        )

    assert response.status_code == 201
    run_id = response.json()["run"]["id"]
    execution_id = response.json()["run"]["workflow_execution_id"]
    assert run_id
    assert execution_id

    execution = WorkflowExecution.objects.get(id=execution_id)
    assert execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)["binding_id"] == first_binding["binding_id"]
    assert execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["workflow_binding"]["binding_id"] == (
        first_binding["binding_id"]
    )
    run = PoolRun.objects.get(id=run_id)
    assert run.workflow_binding_snapshot["binding_id"] == first_binding["binding_id"]
    assert run.runtime_projection_snapshot["workflow_binding"]["binding_id"] == first_binding["binding_id"]


@pytest.mark.django_db
def test_create_pool_run_rejects_top_down_without_starting_amount(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": "binding-required-top-down",
            "direction": PoolRunDirection.TOP_DOWN,
            "period_start": "2026-01-01",
            "run_input": {},
            "mode": "safe",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "run_input" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_rejects_bottom_up_without_source_input(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": "binding-required-bottom-up",
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {},
            "mode": "safe",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "run_input" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_rejects_legacy_source_hash_field_as_problem_details(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": "binding-required-source-hash",
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "source_hash": "legacy-hash",
            "mode": "safe",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "source_hash" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_endpoint_requires_explicit_binding_and_reuses_idempotency_key(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    binding = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )[0][0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        "mode": "safe",
        "validation_summary": {"rows": 3},
        "diagnostics": [],
    }
    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-1", status="queued"),
    ) as enqueue:
        first = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")
        second = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert first_payload["run"]["workflow_execution_id"] is not None
    assert first_payload["run"]["workflow_status"] == "pending"
    assert first_payload["run"]["approval_state"] == "preparing"
    assert first_payload["run"]["publication_step_state"] == "not_enqueued"
    assert first_payload["run"]["execution_backend"] == "workflow_core"

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["run"]["id"] == first_payload["run"]["id"]
    assert second_payload["run"]["workflow_execution_id"] == first_payload["run"]["workflow_execution_id"]
    enqueue.assert_called_once()

    run = PoolRun.objects.get(id=first_payload["run"]["id"])
    assert run.idempotency_key
    assert run.workflow_execution_id is not None
    assert run.publication_confirmed_at is None
    workflow_execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert workflow_execution.execution_consumer == "pools"
    assert workflow_execution.tenant_id == run.tenant_id
    assert workflow_execution.input_context.get("approved_at") is None
    assert workflow_execution.input_context.get("approval_state") == "preparing"
    assert workflow_execution.input_context.get("publication_step_state") == "not_enqueued"
    assert workflow_execution.input_context.get("run_input") == payload["run_input"]
    assert workflow_execution.input_context.get("pool_run_idempotency_key") == run.idempotency_key
    binding_lineage = workflow_execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)
    assert binding_lineage["binding_id"] == binding["binding_id"]
    assert binding_lineage["binding_profile_revision_id"]
    assert binding_lineage["binding_profile_revision_number"] >= 1
    assert binding_lineage["revision"] >= 1
    assert binding_lineage["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert workflow_execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert workflow_execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["workflow_binding"][
        "binding_profile_revision_id"
    ] == binding_lineage["binding_profile_revision_id"]
    assert workflow_execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["workflow_binding"][
        "attachment_revision"
    ] == binding_lineage["revision"]
    assert workflow_execution.input_context.get("workflow_run_id") == str(workflow_execution.id)
    assert workflow_execution.input_context.get("root_workflow_run_id") == str(workflow_execution.id)
    assert workflow_execution.input_context.get("parent_workflow_run_id") is None
    assert workflow_execution.input_context.get("attempt_number") == 1
    assert workflow_execution.input_context.get("attempt_kind") == "initial"
    assert first_payload["run"]["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert (
        first_payload["run"]["workflow_binding"]["binding_profile_revision_id"]
        == binding_lineage["binding_profile_revision_id"]
    )
    assert first_payload["run"]["workflow_binding"]["revision"] == binding_lineage["revision"]
    assert (
        first_payload["run"]["workflow_binding"]["resolved_profile"]["workflow"]["workflow_revision"]
        == 3
    )


@pytest.mark.django_db
def test_create_pool_run_endpoint_uses_binding_in_idempotency_key(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    first_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication-a",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    second_binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication-b",
        workflow_revision=4,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[first_binding, second_binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    first_binding, second_binding = bindings

    base_payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        "mode": PoolRunMode.SAFE,
    }

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-binding-key", status="queued"),
    ):
        first = authenticated_client.post(
            "/api/v2/pools/runs/",
            {**base_payload, "pool_workflow_binding_id": first_binding["binding_id"]},
            format="json",
        )
        second = authenticated_client.post(
            "/api/v2/pools/runs/",
            {**base_payload, "pool_workflow_binding_id": second_binding["binding_id"]},
            format="json",
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["run"]["id"] != second.json()["run"]["id"]


@pytest.mark.django_db
def test_create_pool_run_endpoint_uses_attachment_revision_in_idempotency_key(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]
    list_response = authenticated_client.get(
        "/api/v2/pools/workflow-bindings/",
        {"pool_id": str(pool.id)},
    )
    assert list_response.status_code == 200
    created_binding = next(
        item
        for item in list_response.json()["workflow_bindings"]
        if item["binding_id"] == binding["binding_id"]
    )
    base_payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": created_binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        "mode": PoolRunMode.SAFE,
    }

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-attachment-key", status="queued"),
    ):
        first = authenticated_client.post("/api/v2/pools/runs/", base_payload, format="json")

    assert first.status_code == 201

    update_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _attachment_payload_from_read_model(
                created_binding,
                selector={
                    "direction": PoolRunDirection.BOTTOM_UP,
                    "mode": PoolRunMode.SAFE,
                    "tags": ["attachment-rev-2"],
                },
            ),
        },
        format="json",
    )
    assert update_response.status_code == 200

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-attachment-key-2", status="queued"),
    ):
        second = authenticated_client.post("/api/v2/pools/runs/", base_payload, format="json")

    assert second.status_code == 201
    assert first.json()["run"]["id"] != second.json()["run"]["id"]


@pytest.mark.django_db
def test_create_pool_run_endpoint_uses_pinned_profile_revision_in_idempotency_key(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]
    list_response = authenticated_client.get(
        "/api/v2/pools/workflow-bindings/",
        {"pool_id": str(pool.id)},
    )
    assert list_response.status_code == 200
    created_binding = next(
        item
        for item in list_response.json()["workflow_bindings"]
        if item["binding_id"] == binding["binding_id"]
    )
    base_payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": created_binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        "mode": PoolRunMode.SAFE,
    }

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-profile-key", status="queued"),
    ):
        first = authenticated_client.post("/api/v2/pools/runs/", base_payload, format="json")

    assert first.status_code == 201

    replacement_revision = _create_binding_profile_revision(
        tenant=pool.tenant,
        workflow_definition_key="services-publication",
        workflow_revision=4,
        direction=PoolRunDirection.BOTTOM_UP,
        materialize_runtime_workflow=True,
        decisions=list(created_binding["resolved_profile"]["decisions"]),
        parameters=dict(created_binding["resolved_profile"]["parameters"]),
        role_mapping=dict(created_binding["resolved_profile"]["role_mapping"]),
    )
    repin_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": _attachment_payload_from_read_model(
                created_binding,
                binding_profile_revision_id=str(replacement_revision["binding_profile_revision_id"]),
            ),
        },
        format="json",
    )
    assert repin_response.status_code == 200

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-profile-key-2", status="queued"),
    ):
        second = authenticated_client.post("/api/v2/pools/runs/", base_payload, format="json")

    assert second.status_code == 201
    assert first.json()["run"]["id"] != second.json()["run"]["id"]


@pytest.mark.django_db
def test_create_pool_run_endpoint_keeps_workflow_link_when_enqueue_fails(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    binding = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )[0][0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }
    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=False,
            operation_id="",
            status="error",
            error="redis down",
            error_code="REDIS_UNAVAILABLE",
        ),
    ):
        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert response.status_code == 201
    data = response.json()
    assert data["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert data["run"]["workflow_execution_id"] is not None
    assert data["run"]["workflow_status"] == "pending"

    run = PoolRun.objects.get(id=data["run"]["id"])
    assert run.workflow_status == "pending"
    assert run.workflow_execution_id is not None
    assert PoolRunAuditEvent.objects.filter(run=run, event_type="run.workflow_execution_enqueue_failed").exists()


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_pool_runtime_fail_closed_error(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    with patch(
        "apps.api_v2.views.intercompany_pools.start_pool_run_workflow_execution",
        side_effect=ValueError(
            "POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED: alias 'pool.prepare_input' is not configured"
        ),
    ):
        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED",
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "pool.prepare_input" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_missing_topology_party_role(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]

    with patch(
        "apps.api_v2.views.intercompany_pools.start_pool_run_workflow_execution",
        side_effect=ValueError(
            f"{MASTER_DATA_PARTY_ROLE_MISSING}: child organization is not marked as counterparty"
        ),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": binding["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
                "mode": PoolRunMode.SAFE,
            },
            format="json",
        )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=MASTER_DATA_PARTY_ROLE_MISSING,
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "counterparty" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_missing_topology_party_binding(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]

    with patch(
        "apps.api_v2.views.intercompany_pools.start_pool_run_workflow_execution",
        side_effect=ValueError(
            f"{MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING}: parent organization has no bound master party"
        ),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": binding["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
                "mode": PoolRunMode.SAFE,
            },
            format="json",
        )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "master party" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_missing_actor_mapping(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=default_tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
    )
    binding = bindings[0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_NOT_CONFIGURED",
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert f"actor_username={user.username}" in problem["detail"]
    assert f"target_database_ids={target_database.id}" in problem["detail"]
    assert "/rbac" in problem["detail"]


@pytest.mark.django_db
def test_preview_pool_workflow_binding_uses_managed_default_schema_template_on_default_path(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    _attach_pool_slot_edge(
        tenant=pool.tenant,
        pool=pool,
        database=target_database,
        period_start=date(2026, 1, 1),
        slot_key="document_policy",
    )
    binding = bindings[0]

    assert not PoolSchemaTemplate.objects.filter(
        tenant=pool.tenant,
        code="__runtime-default__",
    ).exists()

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": binding["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert payload["workflow_binding"]["binding_profile_revision_id"]
    assert payload["workflow_binding"]["binding_profile_revision_number"] >= 1
    assert payload["workflow_binding"]["revision"] >= 1
    assert payload["workflow_binding"]["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert set(payload["compiled_document_policy_slots"]) == {"document_policy"}
    assert payload["compiled_document_policy_slots"]["document_policy"]["document_policy"]["version"] == (
        "document_policy.v1"
    )
    assert payload["slot_coverage_summary"]["total_edges"] == 1
    assert payload["slot_coverage_summary"]["counts"]["resolved"] == 1
    assert payload["slot_coverage_summary"]["items"][0]["slot_key"] == "document_policy"
    assert payload["slot_coverage_summary"]["items"][0]["coverage"]["code"] is None
    assert payload["runtime_projection"]["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert (
        payload["runtime_projection"]["workflow_binding"]["binding_profile_revision_id"]
        == payload["workflow_binding"]["binding_profile_revision_id"]
    )
    assert (
        payload["runtime_projection"]["workflow_binding"]["attachment_revision"]
        == payload["workflow_binding"]["revision"]
    )
    assert payload["runtime_projection"]["document_policy_projection"]["compiled_document_policy_slots"] == (
        payload["compiled_document_policy_slots"]
    )
    assert payload["runtime_projection"]["document_policy_projection"]["slot_coverage_summary"] == (
        payload["slot_coverage_summary"]
    )
    assert payload["compiled_document_policy"]["version"] == "document_policy.v1"
    assert PoolSchemaTemplate.objects.filter(
        tenant=pool.tenant,
        code="__runtime-default__",
    ).exists()


@pytest.mark.django_db
def test_preview_pool_workflow_binding_surfaces_missing_selector_in_slot_coverage_summary(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    _attach_pool_slot_edge(
        tenant=pool.tenant,
        pool=pool,
        database=target_database,
        period_start=date(2026, 1, 1),
        slot_key="",
    )

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": bindings[0]["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["slot_coverage_summary"]["counts"]["missing_selector"] == 1
    assert payload["slot_coverage_summary"]["items"][0]["coverage"]["code"] == (
        POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING
    )


@pytest.mark.django_db
def test_preview_pool_workflow_binding_returns_topology_alias_invalid_problem_code_on_default_path(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )

    with patch(
        "apps.api_v2.views.intercompany_pools.build_pool_workflow_binding_preview",
        side_effect=ValueError(
            f"{POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID}: unsupported participant side 'middle'"
        ),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/workflow-bindings/preview/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": bindings[0]["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
                "mode": PoolRunMode.SAFE,
            },
            format="json",
        )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
    )
    assert problem["title"] == "Pool Workflow Binding Preview Failed"
    assert "middle" in problem["detail"]


@pytest.mark.django_db
def test_preview_pool_workflow_binding_template_instantiation_keeps_missing_selector_fail_closed(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    topology_template = _create_topology_template_via_api(
        authenticated_client,
        code="missing-selector-template",
        name="Missing Selector Template",
        revision={
            "nodes": [
                {"slot_key": "root", "is_root": True},
                {"slot_key": "leaf"},
            ],
            "edges": [
                {
                    "parent_slot_key": "root",
                    "child_slot_key": "leaf",
                }
            ],
        },
    )
    revision = topology_template["latest_revision"]
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    root_org = Organization.objects.create(tenant=pool.tenant, name="Template Missing Root", inn="741200000031")
    leaf_org = Organization.objects.get(database=target_database)
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    current_version = graph_before.json()["version"]
    save_response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "topology_template_revision_id": revision["topology_template_revision_id"],
            "slot_assignments": [
                {"slot_key": "root", "organization_id": str(root_org.id)},
                {"slot_key": "leaf", "organization_id": str(leaf_org.id)},
            ],
        },
        format="json",
    )
    assert save_response.status_code == 200

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": bindings[0]["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["slot_coverage_summary"]["counts"]["missing_selector"] == 1
    assert payload["slot_coverage_summary"]["items"][0]["coverage"]["code"] == (
        POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING
    )


@pytest.mark.django_db
def test_create_pool_run_template_instantiation_keeps_missing_selector_fail_closed(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    topology_template = _create_topology_template_via_api(
        authenticated_client,
        code="missing-selector-create-run-template",
        name="Missing Selector Create Run Template",
        revision={
            "nodes": [
                {"slot_key": "root", "is_root": True},
                {"slot_key": "leaf"},
            ],
            "edges": [
                {
                    "parent_slot_key": "root",
                    "child_slot_key": "leaf",
                }
            ],
        },
    )
    revision = topology_template["latest_revision"]
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    root_org = Organization.objects.create(
        tenant=pool.tenant,
        name="Template Missing Selector Root",
        inn="741200000041",
    )
    leaf_org = Organization.objects.get(database=target_database)
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    current_version = graph_before.json()["version"]
    save_response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "topology_template_revision_id": revision["topology_template_revision_id"],
            "slot_assignments": [
                {"slot_key": "root", "organization_id": str(root_org.id)},
                {"slot_key": "leaf", "organization_id": str(leaf_org.id)},
            ],
        },
        format="json",
    )
    assert save_response.status_code == 200

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": bindings[0]["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
    )
    assert "metadata.document_policy_key" in problem["detail"]


@pytest.mark.django_db
def test_preview_pool_workflow_binding_rejects_legacy_edge_document_policy_after_cutover(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    decision = create_decision_table_revision(
        contract=_build_document_policy_decision_payload(
            decision_table_id=f"preview-legacy-cutover-{uuid4().hex[:8]}"
        )
    )
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    binding["decisions"] = [
        {
            "decision_table_id": decision.decision_table_id,
            "decision_key": decision.decision_key,
            "slot_key": "sale",
            "decision_revision": decision.version_number,
        }
    ]
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    _attach_pool_slot_edge(
        tenant=pool.tenant,
        pool=pool,
        database=target_database,
        period_start=date(2026, 1, 1),
        slot_key="sale",
    )
    edge = PoolEdgeVersion.objects.filter(pool=pool, effective_from=date(2026, 1, 1)).order_by("created_at").last()
    assert edge is not None
    edge.metadata = {
        "document_policy_key": "sale",
        "document_policy": _build_document_policy_payload(),
    }
    edge.save(update_fields=["metadata", "updated_at"])

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": bindings[0]["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
    )
    assert "legacy topology document_policy" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_slot_not_bound_problem_code_on_default_path(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    with patch(
        "apps.api_v2.views.intercompany_pools.start_pool_run_workflow_execution",
        side_effect=ValueError(
            "POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND: binding slot 'sale' is not bound for edge node-parent->node-child"
        ),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": bindings[0]["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
                "mode": PoolRunMode.SAFE,
            },
            format="json",
        )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "sale" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_rejects_legacy_pool_document_policy_after_cutover(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    decision = create_decision_table_revision(
        contract=_build_document_policy_decision_payload(
            decision_table_id=f"run-legacy-cutover-{uuid4().hex[:8]}"
        )
    )
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="services-publication",
        workflow_revision=3,
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )
    binding["decisions"] = [
        {
            "decision_table_id": decision.decision_table_id,
            "decision_key": decision.decision_key,
            "slot_key": "sale",
            "decision_revision": decision.version_number,
        }
    ]
    bindings, target_database = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    _attach_pool_slot_edge(
        tenant=pool.tenant,
        pool=pool,
        database=target_database,
        period_start=date(2026, 1, 1),
        slot_key="sale",
    )
    pool.metadata = {
        **(pool.metadata if isinstance(pool.metadata, dict) else {}),
        "document_policy": _build_document_policy_payload(),
    }
    pool.save(update_fields=["metadata", "updated_at"])

    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": bindings[0]["binding_id"],
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code=POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "legacy topology document_policy" in problem["detail"]


@pytest.mark.django_db
def test_preview_pool_workflow_binding_rejects_missing_binding_reference(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_REQUIRED",
    )
    assert payload["detail"] == "pool_workflow_binding_id is required."


@pytest.mark.django_db
def test_preview_pool_workflow_binding_fails_closed_for_attachment_without_profile_refs(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    legacy_binding = _create_legacy_pool_workflow_binding_without_profile_refs(
        tenant=default_tenant,
        pool=pool,
    )

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": legacy_binding.binding_id,
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "mode": PoolRunMode.SAFE,
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING",
    )
    assert payload["title"] == "Pool Workflow Binding Preview Failed"
    assert legacy_binding.binding_id in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_ambiguous_actor_mapping(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    bindings, database = _prepare_pool_runtime_bindings(
        tenant=default_tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-1",
        ib_password="pass-1",
        is_service=False,
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-2",
        ib_password="pass-2",
        is_service=False,
    )
    binding = bindings[0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_AMBIGUOUS",
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "/rbac" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_succeeds_when_actor_mapping_configured(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    bindings, database = _prepare_pool_runtime_bindings(
        tenant=default_tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
    )
    if not InfobaseUserMapping.objects.filter(database=database, user=user, is_service=False).exists():
        _create_actor_infobase_mapping(
            database=database,
            user=user,
            username="actor-ok",
        )
    binding = bindings[0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-with-mapping", status="queued"),
    ):
        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert response.status_code == 201
    assert response.json()["run"]["workflow_execution_id"] is not None


@pytest.mark.django_db
def test_create_pool_run_enqueues_to_workflow_stream_with_normal_priority(
    authenticated_client: APIClient,
    user: User,
    pool: OrganizationPool,
) -> None:
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=pool.tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.SAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]
    payload = {
        "pool_id": str(pool.id),
        "pool_workflow_binding_id": binding["binding_id"],
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "30.00"}]},
        "mode": "safe",
    }
    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.STREAM_WORKFLOWS = "commands:worker:workflows"
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123456-0"

        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert response.status_code == 201
    run_payload = response.json()["run"]
    assert run_payload["workflow_execution_id"] is not None

    mock_redis_client.enqueue_operation_stream.assert_called_once()
    call_args = mock_redis_client.enqueue_operation_stream.call_args
    message = call_args.args[0]
    assert call_args.kwargs["stream_name"] == "commands:worker:workflows"
    assert message["execution_config"]["priority"] == "normal"
    assert message["execution_config"]["idempotency_key"] == run_payload["idempotency_key"]
    assert message["payload"]["data"]["pool_run_idempotency_key"] == run_payload["idempotency_key"]
    assert message["operation_type"] == "execute_workflow"
    mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_get_pool_run_returns_details(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-details-db")
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary error",
    )
    run.add_audit_event(
        event_type="run.test_event",
        status_before=run.status,
        status_after=run.status,
        payload={"test": True},
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == str(run.id)
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["terminal_reason"] is None
    assert payload["run"]["master_data_gate"] is None
    assert payload["run"]["readiness_blockers"] == []
    assert payload["run"]["readiness_checklist"] == {
        "status": "not_ready",
        "checks": [
            {
                "code": "master_data_coverage",
                "status": "not_ready",
                "blocker_codes": [],
                "blockers": [],
            },
            {
                "code": "organization_party_bindings",
                "status": "not_ready",
                "blocker_codes": [],
                "blockers": [],
            },
            {
                "code": "policy_completeness",
                "status": "not_ready",
                "blocker_codes": [],
                "blockers": [],
            },
            {
                "code": "odata_verify_readiness",
                "status": "not_ready",
                "blocker_codes": [],
                "blockers": [],
            },
        ],
    }
    assert payload["run"]["verification_status"] == "not_verified"
    assert payload["run"]["verification_summary"] is None
    assert payload["run"]["provenance"]["workflow_run_id"] is None
    assert payload["run"]["provenance"]["workflow_status"] is None
    assert payload["run"]["provenance"]["execution_backend"] == "legacy_pool_runtime"
    assert payload["run"]["root_operation_id"] is None
    assert payload["run"]["execution_consumer"] is None
    assert payload["run"]["lane"] is None
    assert payload["run"]["provenance"]["root_operation_id"] is None
    assert payload["run"]["provenance"]["execution_consumer"] is None
    assert payload["run"]["provenance"]["lane"] is None
    assert payload["run"]["provenance"]["retry_chain"] == []
    assert len(payload["publication_attempts"]) == 1
    attempt_payload = payload["publication_attempts"][0]
    assert attempt_payload["target_database_id"] == str(database.id)
    assert attempt_payload["attempt_timestamp"] is not None
    assert attempt_payload["payload_summary"] == {
        "documents_count": 1,
        "entity_name": "Document_IntercompanyPoolDistribution",
    }
    assert attempt_payload["http_error"] is None
    assert attempt_payload["transport_error"] == {
        "code": "network",
        "message": "temporary error",
    }
    assert attempt_payload["domain_error_code"] == "network"
    assert attempt_payload["domain_error_message"] == "temporary error"
    assert attempt_payload["publication_identity_strategy"] == ""
    assert any(event["event_type"] == "run.test_event" for event in payload["audit_events"])


@pytest.mark.django_db
def test_historical_run_read_contract_returns_nullable_run_input_and_legacy_contract_version(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    historical_run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2025, 12, 1),
        run_input={},
        source_hash="legacy-source-hash",
    )

    list_response = authenticated_client.get(f"/api/v2/pools/runs/?pool_id={pool.id}&limit=10")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    historical_row = next(item for item in list_payload["runs"] if item["id"] == str(historical_run.id))
    assert historical_row["run_input"] is None
    assert historical_row["input_contract_version"] == "legacy_pre_run_input"
    assert historical_row["master_data_gate"] is None
    assert "source_hash" not in historical_row

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{historical_run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    assert details_payload["run"]["run_input"] is None
    assert details_payload["run"]["input_contract_version"] == "legacy_pre_run_input"
    assert details_payload["run"]["master_data_gate"] is None
    assert "source_hash" not in details_payload["run"]

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{historical_run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["master_data_gate"] is None


@pytest.mark.django_db
def test_get_pool_run_and_report_include_stable_master_data_gate_read_model(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    missing_org_id = str(uuid4())
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "completed",
            "pool_runtime_master_data_gate": {
                "status": "failed",
                "mode": "resolve_upsert",
                "targets_count": "3",
                "bindings_count": 1,
                "error_code": "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING",
                "detail": "Missing Organization->Party binding for publication target organizations.",
                "diagnostic": {
                    "missing_count": 1,
                    "missing_organization_bindings": [{"organization_id": missing_org_id}],
                },
            },
        },
    )

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    details_gate = details_payload["run"]["master_data_gate"]
    assert details_gate == {
        "status": "failed",
        "mode": "resolve_upsert",
        "targets_count": 3,
        "bindings_count": 1,
        "error_code": "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING",
        "detail": "Missing Organization->Party binding for publication target organizations.",
        "diagnostic": {
            "missing_count": 1,
            "missing_organization_bindings": [{"organization_id": missing_org_id}],
        },
    }
    assert set(details_gate.keys()) == {
        "status",
        "mode",
        "targets_count",
        "bindings_count",
        "error_code",
        "detail",
        "diagnostic",
    }

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["master_data_gate"] == details_gate


@pytest.mark.django_db
@override_settings(INTERNAL_API_TOKEN="test-internal-token")
def test_top_down_pool_run_read_model_projects_publication_attempts_and_verification_after_internal_completion(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding, database = _prepare_single_pool_runtime_binding(
        tenant=default_tenant,
        pool=pool,
        workflow_definition_key="top-down-publication",
        workflow_revision=3,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.UNSAFE,
        period_start=date(2026, 1, 1),
    )
    _attach_pool_slot_edge(
        tenant=default_tenant,
        pool=pool,
        database=database,
        period_start=date(2026, 1, 1),
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-top-down",
        ib_password="actor-pass",
        is_service=False,
    )
    _create_service_infobase_mapping(
        database=database,
        username="svc-top-down",
        password="svc-pass",
    )

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "Ref_Key": "sale-ref-001",
                "ВидОперации": "Услуги",
                "СуммаДокумента": "12956834.00",
                "Услуги": [
                    {
                        "Номенклатура_Key": "item-packing-service",
                        "Содержание": "Услуги упаковки",
                        "Количество": 1,
                        "Цена": "12956834.00",
                        "Сумма": "12956834.00",
                        "СтавкаНДС": "НДС20",
                        "СуммаНДС": "2159472.33",
                    }
                ],
            }

    class _FakeAdapter:
        def __init__(
            self,
            *,
            base_url: str,
            username: str,
            password: str,
            timeout: int | None = None,
            verify_tls: bool = True,
        ) -> None:
            self.base_url = base_url
            self.username = username
            self.password = password
            self.timeout = timeout
            self.verify_tls = verify_tls

        def fetch_document(self, *, entity_name: str, entity_id: str) -> _Response:
            assert entity_name == "Document_РеализацияТоваровУслуг"
            assert entity_id == "guid'sale-ref-001'"
            return _Response()

        def __enter__(self) -> "_FakeAdapter":
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-top-down", status="queued"),
    ):
        create_response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": binding["binding_id"],
                "direction": PoolRunDirection.TOP_DOWN,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"starting_amount": "12956834.00"},
                "mode": PoolRunMode.UNSAFE,
            },
            format="json",
        )

    assert create_response.status_code == 201
    create_payload = create_response.json()
    run_id = create_payload["run"]["id"]
    execution_id = create_payload["run"]["workflow_execution_id"]
    assert execution_id is not None
    assert create_payload["run"]["direction"] == PoolRunDirection.TOP_DOWN
    assert create_payload["run"]["approval_state"] == "not_required"
    assert create_payload["run"]["publication_step_state"] == "queued"

    execution = WorkflowExecution.objects.get(id=execution_id)
    internal_client = APIClient()
    internal_client.credentials(HTTP_X_INTERNAL_TOKEN="test-internal-token")

    document_plan_artifact = {
        "targets": [
            {
                "database_id": str(database.id),
                "chains": [
                    {
                        "documents": [
                            {
                                "entity_name": "Document_РеализацияТоваровУслуг",
                                "idempotency_key": "realization-uslugi-1",
                                "completeness_requirements": {
                                    "required_fields": [
                                        "ВидОперации",
                                        "СуммаДокумента",
                                    ],
                                    "required_table_parts": {
                                        "Услуги": {
                                            "min_rows": 1,
                                            "required_fields": [
                                                "Номенклатура_Key",
                                                "Содержание",
                                                "Количество",
                                                "Цена",
                                                "Сумма",
                                                "СтавкаНДС",
                                                "СуммаНДС",
                                            ],
                                        }
                                    },
                                },
                            }
                        ]
                    }
                ],
            }
        ]
    }

    patch_response = internal_client.patch(
        f"/api/v2/internal/workflow-executions/{execution.id}/",
        {
            "input_data": {
                **(execution.input_context or {}),
                "pool_runtime_document_plan_artifact": document_plan_artifact,
            }
        },
        format="json",
    )
    assert patch_response.status_code == 200

    with patch(
        "apps.intercompany_pools.publication_verification.ODataDocumentAdapter",
        _FakeAdapter,
    ):
        complete_response = internal_client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "completed",
                "result": {
                    "node_results": {
                        "publication_odata__chain_1": {
                            "step": "publication_odata",
                            "pool_run_id": str(run_id),
                            "entity_name": "Document_РеализацияТоваровУслуг",
                            "target_databases": [str(database.id)],
                            "documents_count_by_database": {str(database.id): 1},
                            "attempts": [
                                {
                                    "target_database": str(database.id),
                                    "attempt_number": 1,
                                    "status": "success",
                                    "entity_name": "Document_РеализацияТоваровУслуг",
                                    "documents_count": 1,
                                    "posted": True,
                                    "request_summary": {"documents_count": 1},
                                    "response_summary": {
                                        "posted": True,
                                        "successful_document_refs": {
                                            "realization-uslugi-1": "sale-ref-001",
                                        },
                                    },
                                }
                            ],
                        }
                    }
                },
            },
            format="json",
        )

    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == WorkflowExecution.STATUS_COMPLETED

    run = PoolRun.objects.get(id=run_id)
    assert run.direction == PoolRunDirection.TOP_DOWN

    execution = WorkflowExecution.objects.get(id=execution.id)
    assert execution.status == WorkflowExecution.STATUS_COMPLETED
    verification = execution.input_context.get("pool_runtime_verification")
    assert verification["status"] == "passed"
    assert verification["summary"]["verified_documents"] == 1
    assert verification["summary"]["mismatches_count"] == 0

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    assert details_payload["run"]["direction"] == PoolRunDirection.TOP_DOWN
    assert details_payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert details_payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED
    assert details_payload["run"]["approval_state"] == "not_required"
    assert details_payload["run"]["publication_step_state"] == "completed"
    assert details_payload["run"]["verification_status"] == "passed"
    assert details_payload["run"]["verification_summary"] == {
        "checked_targets": 1,
        "verified_documents": 1,
        "mismatches_count": 0,
        "mismatches": [],
    }
    assert len(details_payload["publication_attempts"]) == 1
    assert details_payload["publication_attempts"][0]["target_database_id"] == str(database.id)
    assert details_payload["publication_attempts"][0]["status"] == PoolPublicationAttemptStatus.SUCCESS
    assert details_payload["publication_attempts"][0]["response_summary"] == {
        "posted": True,
        "successful_document_refs": {
            "realization-uslugi-1": "sale-ref-001",
        },
    }

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert report_payload["run"]["verification_status"] == "passed"
    assert report_payload["run"]["verification_summary"] == details_payload["run"]["verification_summary"]
    assert report_payload["publication_attempts"] == details_payload["publication_attempts"]


@pytest.mark.django_db
@override_settings(INTERNAL_API_TOKEN="test-internal-token")
def test_top_down_pool_run_read_model_projects_failed_verification_after_internal_completion(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
    pool: OrganizationPool,
) -> None:
    binding, database = _prepare_single_pool_runtime_binding(
        tenant=default_tenant,
        pool=pool,
        workflow_definition_key="top-down-publication-failed-verify",
        workflow_revision=4,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.UNSAFE,
        period_start=date(2026, 1, 1),
    )
    _attach_pool_slot_edge(
        tenant=default_tenant,
        pool=pool,
        database=database,
        period_start=date(2026, 1, 1),
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-top-down",
        ib_password="actor-pass",
        is_service=False,
    )
    _create_service_infobase_mapping(
        database=database,
        username="svc-top-down",
        password="svc-pass",
    )

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "Ref_Key": "sale-ref-001",
                "ВидОперации": "Услуги",
                "СуммаДокумента": "12956834.00",
                "Услуги": [],
            }

    class _FakeAdapter:
        def __init__(
            self,
            *,
            base_url: str,
            username: str,
            password: str,
            timeout: int | None = None,
            verify_tls: bool = True,
        ) -> None:
            self.base_url = base_url
            self.username = username
            self.password = password
            self.timeout = timeout
            self.verify_tls = verify_tls

        def fetch_document(self, *, entity_name: str, entity_id: str) -> _Response:
            assert entity_name == "Document_РеализацияТоваровУслуг"
            assert entity_id == "guid'sale-ref-001'"
            return _Response()

        def __enter__(self) -> "_FakeAdapter":
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-top-down-failed-verify", status="queued"),
    ):
        create_response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": binding["binding_id"],
                "direction": PoolRunDirection.TOP_DOWN,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"starting_amount": "12956834.00"},
                "mode": PoolRunMode.UNSAFE,
            },
            format="json",
        )

    assert create_response.status_code == 201
    create_payload = create_response.json()
    run_id = create_payload["run"]["id"]
    execution_id = create_payload["run"]["workflow_execution_id"]
    assert execution_id is not None

    execution = WorkflowExecution.objects.get(id=execution_id)
    internal_client = APIClient()
    internal_client.credentials(HTTP_X_INTERNAL_TOKEN="test-internal-token")

    document_plan_artifact = {
        "targets": [
            {
                "database_id": str(database.id),
                "chains": [
                    {
                        "documents": [
                            {
                                "entity_name": "Document_РеализацияТоваровУслуг",
                                "idempotency_key": "realization-uslugi-1",
                                "completeness_requirements": {
                                    "required_fields": [
                                        "ВидОперации",
                                        "СуммаДокумента",
                                    ],
                                    "required_table_parts": {
                                        "Услуги": {
                                            "min_rows": 1,
                                            "required_fields": [
                                                "Номенклатура_Key",
                                                "Содержание",
                                                "Количество",
                                                "Цена",
                                                "Сумма",
                                                "СтавкаНДС",
                                                "СуммаНДС",
                                            ],
                                        }
                                    },
                                },
                            }
                        ]
                    }
                ],
            }
        ]
    }

    patch_response = internal_client.patch(
        f"/api/v2/internal/workflow-executions/{execution.id}/",
        {
            "input_data": {
                **(execution.input_context or {}),
                "pool_runtime_document_plan_artifact": document_plan_artifact,
            }
        },
        format="json",
    )
    assert patch_response.status_code == 200

    with patch(
        "apps.intercompany_pools.publication_verification.ODataDocumentAdapter",
        _FakeAdapter,
    ):
        complete_response = internal_client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "completed",
                "result": {
                    "node_results": {
                        "publication_odata__chain_1": {
                            "step": "publication_odata",
                            "pool_run_id": str(run_id),
                            "entity_name": "Document_РеализацияТоваровУслуг",
                            "target_databases": [str(database.id)],
                            "documents_count_by_database": {str(database.id): 1},
                            "attempts": [
                                {
                                    "target_database": str(database.id),
                                    "attempt_number": 1,
                                    "status": "success",
                                    "entity_name": "Document_РеализацияТоваровУслуг",
                                    "documents_count": 1,
                                    "posted": True,
                                    "request_summary": {"documents_count": 1},
                                    "response_summary": {
                                        "posted": True,
                                        "successful_document_refs": {
                                            "realization-uslugi-1": "sale-ref-001",
                                        },
                                    },
                                }
                            ],
                        }
                    }
                },
            },
            format="json",
        )

    assert complete_response.status_code == 200
    execution = WorkflowExecution.objects.get(id=execution.id)
    verification = execution.input_context.get("pool_runtime_verification")
    assert verification == {
        "status": "failed",
        "summary": {
            "checked_targets": 1,
            "verified_documents": 1,
            "mismatches_count": 1,
            "mismatches": [
                {
                    "database_id": str(database.id),
                    "entity_name": "Document_РеализацияТоваровУслуг",
                    "document_idempotency_key": "realization-uslugi-1",
                    "field_or_table_path": "Услуги",
                    "kind": "missing_table_part",
                }
            ],
        },
    }

    run = PoolRun.objects.get(id=run_id)
    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    assert details_payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert details_payload["run"]["verification_status"] == "failed"
    assert details_payload["run"]["verification_summary"] == verification["summary"]

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert report_payload["run"]["verification_status"] == "failed"
    assert report_payload["run"]["verification_summary"] == verification["summary"]
    assert report_payload["publication_attempts"] == details_payload["publication_attempts"]


@pytest.mark.django_db
def test_get_pool_run_and_report_include_readiness_and_verification_read_model(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "completed",
            "pool_runtime_readiness_blockers": [
                {
                    "code": "POOL_DOCUMENT_POLICY_MAPPING_INVALID",
                    "detail": "Document policy is incomplete for minimal_documents_full_payload.",
                    "entity_name": "Document_Sales",
                    "field_or_table_path": "Goods",
                }
            ],
            "pool_runtime_verification": {
                "status": "failed",
                "summary": {
                    "checked_targets": 1,
                    "verified_documents": 1,
                    "mismatches_count": 1,
                    "mismatches": [
                        {
                            "database_id": "11111111-1111-1111-1111-111111111111",
                            "entity_name": "Document_Sales",
                            "document_idempotency_key": "sales-doc-1",
                            "field_or_table_path": "Goods",
                            "kind": "missing_table_part",
                        }
                    ],
                },
            },
        },
    )

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    assert details_payload["run"]["readiness_blockers"] == [
        {
            "code": "POOL_DOCUMENT_POLICY_MAPPING_INVALID",
            "detail": "Document policy is incomplete for minimal_documents_full_payload.",
            "kind": None,
            "entity_name": "Document_Sales",
            "field_or_table_path": "Goods",
            "database_id": None,
            "organization_id": None,
            "edge_ref": None,
            "participant_side": None,
            "required_role": None,
            "diagnostic": None,
        }
    ]
    assert details_payload["run"]["readiness_checklist"] == {
        "status": "not_ready",
        "checks": [
            {
                "code": "master_data_coverage",
                "status": "ready",
                "blocker_codes": [],
                "blockers": [],
            },
            {
                "code": "organization_party_bindings",
                "status": "ready",
                "blocker_codes": [],
                "blockers": [],
            },
            {
                "code": "policy_completeness",
                "status": "not_ready",
                "blocker_codes": ["POOL_DOCUMENT_POLICY_MAPPING_INVALID"],
                "blockers": [
                    {
                        "code": "POOL_DOCUMENT_POLICY_MAPPING_INVALID",
                        "detail": "Document policy is incomplete for minimal_documents_full_payload.",
                        "kind": None,
                        "entity_name": "Document_Sales",
                        "field_or_table_path": "Goods",
                        "database_id": None,
                        "organization_id": None,
                        "edge_ref": None,
                        "participant_side": None,
                        "required_role": None,
                        "diagnostic": None,
                    }
                ],
            },
            {
                "code": "odata_verify_readiness",
                "status": "ready",
                "blocker_codes": [],
                "blockers": [],
            },
        ],
    }
    assert details_payload["run"]["verification_status"] == "failed"
    assert details_payload["run"]["verification_summary"] == {
        "checked_targets": 1,
        "verified_documents": 1,
        "mismatches_count": 1,
        "mismatches": [
            {
                "database_id": "11111111-1111-1111-1111-111111111111",
                "entity_name": "Document_Sales",
                "document_idempotency_key": "sales-doc-1",
                "field_or_table_path": "Goods",
                "kind": "missing_table_part",
            }
        ],
    }

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["readiness_blockers"] == details_payload["run"]["readiness_blockers"]
    assert report_payload["run"]["readiness_checklist"] == details_payload["run"]["readiness_checklist"]
    assert report_payload["run"]["verification_status"] == "failed"
    assert report_payload["run"]["verification_summary"] == details_payload["run"]["verification_summary"]


@pytest.mark.django_db
def test_get_pool_run_and_report_include_topology_readiness_blocker_context(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    organization_id = str(uuid4())
    database_id = str(uuid4())
    parent_node_id = str(uuid4())
    child_node_id = str(uuid4())
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "completed",
            "pool_runtime_readiness_blockers": [
                {
                    "code": MASTER_DATA_PARTY_ROLE_MISSING,
                    "detail": "Child organization is bound to a party without counterparty role.",
                    "organization_id": organization_id,
                    "database_id": database_id,
                    "edge_ref": {
                        "parent_node_id": parent_node_id,
                        "child_node_id": child_node_id,
                    },
                    "participant_side": "child",
                    "required_role": "counterparty",
                },
                {
                    "code": POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
                    "detail": "Unsupported participant side in document_policy alias.",
                    "field_or_table_path": "chains[0].documents[0].field_mapping.Контрагент",
                },
            ],
        },
    )

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    assert details_payload["run"]["readiness_blockers"] == [
        {
            "code": MASTER_DATA_PARTY_ROLE_MISSING,
            "detail": "Child organization is bound to a party without counterparty role.",
            "kind": None,
            "entity_name": None,
            "field_or_table_path": None,
            "database_id": database_id,
            "organization_id": organization_id,
            "edge_ref": {
                "parent_node_id": parent_node_id,
                "child_node_id": child_node_id,
            },
            "participant_side": "child",
            "required_role": "counterparty",
            "diagnostic": None,
        },
        {
            "code": POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
            "detail": "Unsupported participant side in document_policy alias.",
            "kind": None,
            "entity_name": None,
            "field_or_table_path": "chains[0].documents[0].field_mapping.Контрагент",
            "database_id": None,
            "organization_id": None,
            "edge_ref": None,
            "participant_side": None,
            "required_role": None,
            "diagnostic": None,
        },
    ]
    assert details_payload["run"]["readiness_checklist"] == {
        "status": "not_ready",
        "checks": [
            {
                "code": "master_data_coverage",
                "status": "ready",
                "blocker_codes": [],
                "blockers": [],
            },
            {
                "code": "organization_party_bindings",
                "status": "not_ready",
                "blocker_codes": [MASTER_DATA_PARTY_ROLE_MISSING],
                "blockers": [
                    {
                        "code": MASTER_DATA_PARTY_ROLE_MISSING,
                        "detail": "Child organization is bound to a party without counterparty role.",
                        "kind": None,
                        "entity_name": None,
                        "field_or_table_path": None,
                        "database_id": database_id,
                        "organization_id": organization_id,
                        "edge_ref": {
                            "parent_node_id": parent_node_id,
                            "child_node_id": child_node_id,
                        },
                        "participant_side": "child",
                        "required_role": "counterparty",
                        "diagnostic": None,
                    }
                ],
            },
            {
                "code": "policy_completeness",
                "status": "not_ready",
                "blocker_codes": [POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID],
                "blockers": [
                    {
                        "code": POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
                        "detail": "Unsupported participant side in document_policy alias.",
                        "kind": None,
                        "entity_name": None,
                        "field_or_table_path": "chains[0].documents[0].field_mapping.Контрагент",
                        "database_id": None,
                        "organization_id": None,
                        "edge_ref": None,
                        "participant_side": None,
                        "required_role": None,
                        "diagnostic": None,
                    }
                ],
            },
            {
                "code": "odata_verify_readiness",
                "status": "ready",
                "blocker_codes": [],
                "blockers": [],
            },
        ],
    }

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["readiness_blockers"] == details_payload["run"]["readiness_blockers"]
    assert report_payload["run"]["readiness_checklist"] == details_payload["run"]["readiness_checklist"]


@pytest.mark.django_db
def test_get_pool_run_serializes_http_error_in_canonical_diagnostics(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-http-error-db")
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=2,
        posted=False,
        http_status=503,
        error_code="ODataRequestError",
        error_message="gateway timeout",
        request_summary={"documents_count": 2},
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    attempt_payload = payload["publication_attempts"][0]
    assert attempt_payload["payload_summary"] == {
        "documents_count": 2,
        "entity_name": "Document_IntercompanyPoolDistribution",
        "requested_documents_count": 2,
    }
    assert attempt_payload["http_error"] == {
        "status": 503,
        "code": "ODataRequestError",
        "message": "gateway timeout",
    }
    assert attempt_payload["transport_error"] is None
    assert attempt_payload["domain_error_code"] == "ODataRequestError"
    assert attempt_payload["domain_error_message"] == "gateway timeout"
    assert "error_code" not in attempt_payload
    assert "error_message" not in attempt_payload
    assert "http_status" not in attempt_payload


@pytest.mark.django_db
def test_get_pool_run_redacts_traceback_and_sensitive_diagnostics(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-redaction-db")
    sensitive_error = (
        f"Traceback (most recent call last): File \"worker.py\", line 42, "
        f"password=super-secret token=abc123 tenant={default_tenant.id}"
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="ODataRequestError",
        error_message=sensitive_error,
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    attempt_payload = payload["publication_attempts"][0]
    assert attempt_payload["domain_error_message"] == "internal_error"
    assert attempt_payload["transport_error"] == {
        "code": "ODataRequestError",
        "message": "internal_error",
    }
    assert str(default_tenant.id) not in attempt_payload["domain_error_message"]
    assert "super-secret" not in attempt_payload["domain_error_message"]
    assert "abc123" not in attempt_payload["domain_error_message"]


@pytest.mark.django_db
def test_get_pool_run_resolves_transition_workflow_link_without_persisted_relation(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    run.add_audit_event(
        event_type="run.transition_only_event",
        status_before=run.status,
        status_after=run.status,
        payload={"source": "transition"},
    )
    execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "started",
        },
        link_run=False,
    )
    run_state = PoolRun.objects.get(id=run.id)
    assert run_state.workflow_execution_id is None
    assert run_state.execution_backend == "legacy_pool_runtime"

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["workflow_execution_id"] == str(execution.id)
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["execution_backend"] == "workflow_core"
    assert payload["run"]["root_operation_id"] == str(execution.id)
    assert payload["run"]["execution_consumer"] == "pools"
    assert payload["run"]["lane"] == "workflows"
    assert payload["run"]["provenance"]["workflow_run_id"] == str(execution.id)
    assert payload["run"]["provenance"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["provenance"]["root_operation_id"] == str(execution.id)
    assert payload["run"]["provenance"]["execution_consumer"] == "pools"
    assert payload["run"]["provenance"]["lane"] == "workflows"
    assert payload["run"]["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(execution.id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_RUNNING,
        }
    ]
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHING
    assert any(event["event_type"] == "run.transition_only_event" for event in payload["audit_events"])


@pytest.mark.django_db
def test_get_pool_run_builds_deterministic_lineage_for_multiple_workflow_attempts(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    initial_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "completed",
        },
        link_run=False,
    )
    initial_execution.input_context = {
        **(initial_execution.input_context or {}),
        "workflow_run_id": str(initial_execution.id),
        "root_workflow_run_id": str(initial_execution.id),
        "parent_workflow_run_id": None,
        "attempt_number": 1,
        "attempt_kind": "initial",
    }
    initial_execution.save(update_fields=["input_context"])

    retry_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "started",
        },
        link_run=False,
    )
    retry_execution.input_context = {
        **(retry_execution.input_context or {}),
        "workflow_run_id": str(retry_execution.id),
        "root_workflow_run_id": str(initial_execution.id),
        "parent_workflow_run_id": str(initial_execution.id),
        "attempt_number": 2,
        "attempt_kind": "retry",
    }
    retry_execution.save(update_fields=["input_context"])

    run_state = PoolRun.objects.get(id=run.id)
    assert run_state.workflow_execution_id is None

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["workflow_execution_id"] == str(retry_execution.id)
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["provenance"]["workflow_run_id"] == str(initial_execution.id)
    assert payload["run"]["provenance"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(initial_execution.id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_COMPLETED,
        },
        {
            "workflow_run_id": str(retry_execution.id),
            "parent_workflow_run_id": str(initial_execution.id),
            "attempt_number": 2,
            "attempt_kind": "retry",
            "status": WorkflowExecution.STATUS_RUNNING,
        },
    ]


@pytest.mark.django_db
def test_list_runs_resolves_transition_workflow_link_without_persisted_relation(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_PENDING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "publication_step_state": "not_enqueued",
        },
        link_run=False,
    )
    assert PoolRun.objects.get(id=run.id).workflow_execution_id is None

    response = authenticated_client.get(f"/api/v2/pools/runs/?pool_id={pool.id}&limit=10")
    assert response.status_code == 200
    payload = response.json()
    run_payload = next(item for item in payload["runs"] if item["id"] == str(run.id))
    assert run_payload["workflow_execution_id"] == str(execution.id)
    assert run_payload["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert run_payload["execution_backend"] == "workflow_core"
    assert run_payload["root_operation_id"] == str(execution.id)
    assert run_payload["execution_consumer"] == "pools"
    assert run_payload["lane"] == "workflows"
    assert run_payload["provenance"]["workflow_run_id"] == str(execution.id)
    assert run_payload["provenance"]["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert run_payload["provenance"]["root_operation_id"] == str(execution.id)
    assert run_payload["provenance"]["execution_consumer"] == "pools"
    assert run_payload["provenance"]["lane"] == "workflows"
    assert run_payload["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(execution.id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_PENDING,
        }
    ]


@pytest.mark.django_db
def test_get_pool_run_projects_safe_pending_workflow_to_validated_preparing(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save()
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_PENDING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "preparing",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "preparing"
    assert payload["run"]["approval_state"] == "preparing"
    assert payload["run"]["publication_step_state"] == "not_enqueued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert payload["run"]["provenance"]["workflow_run_id"] == str(run.workflow_execution_id)
    assert payload["run"]["provenance"]["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert payload["run"]["provenance"]["execution_backend"] == "workflow_core"
    assert payload["run"]["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(run.workflow_execution_id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_PENDING,
        }
    ]


@pytest.mark.django_db
def test_get_pool_run_report_exposes_binding_lineage_and_runtime_projection(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    binding = {
        "binding_id": str(uuid4()),
        "pool_id": str(pool.id),
        "binding_profile_id": str(uuid4()),
        "binding_profile_revision_id": "binding-profile-revision-7",
        "binding_profile_revision_number": 2,
        "revision": 4,
        "selector": {
            "direction": PoolRunDirection.TOP_DOWN,
            "mode": PoolRunMode.SAFE,
            "tags": ["quarter-close"],
        },
        "effective_from": "2026-01-01",
        "status": "active",
        "resolved_profile": {
            "binding_profile_id": str(uuid4()),
            "code": "services-publication",
            "name": "Services Publication",
            "status": "active",
            "binding_profile_revision_id": "binding-profile-revision-7",
            "binding_profile_revision_number": 2,
            "workflow": {
                "workflow_definition_key": "services-publication",
                "workflow_revision_id": "workflow-revision-7",
                "workflow_revision": 7,
                "workflow_name": "compiled-services-publication",
            },
            "decisions": [
                {
                    "decision_table_id": "decision-1",
                    "decision_key": "invoice_mode",
                    "decision_revision": 2,
                }
            ],
            "parameters": {"publication_variant": "full"},
            "role_mapping": {"initiator": "finance"},
        },
    }
    projection = {
        "version": "pool_runtime_projection.v1",
        "run_id": str(run.id),
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.TOP_DOWN,
        "mode": PoolRunMode.SAFE,
        "workflow_definition": {
            "plan_key": "plan-services-v7",
            "template_version": "workflow-template:7",
            "workflow_template_name": "compiled-services-publication",
            "workflow_type": WorkflowType.SEQUENTIAL,
        },
        "workflow_binding": {
            "binding_mode": "pool_workflow_binding",
            "binding_id": binding["binding_id"],
            "pool_id": str(pool.id),
            "binding_profile_id": binding["binding_profile_id"],
            "binding_profile_revision_id": binding["binding_profile_revision_id"],
            "binding_profile_revision_number": binding["binding_profile_revision_number"],
            "attachment_revision": binding["revision"],
            "workflow_definition_key": binding["resolved_profile"]["workflow"]["workflow_definition_key"],
            "workflow_revision_id": binding["resolved_profile"]["workflow"]["workflow_revision_id"],
            "workflow_revision": binding["resolved_profile"]["workflow"]["workflow_revision"],
            "workflow_name": binding["resolved_profile"]["workflow"]["workflow_name"],
            "decision_refs": [
                {
                    "decision_table_id": "decision-1",
                    "decision_key": "invoice_mode",
                    "decision_revision": 2,
                }
            ],
            "selector": {
                "direction": PoolRunDirection.TOP_DOWN,
                "mode": PoolRunMode.SAFE,
                "tags": ["quarter-close"],
            },
            "status": "active",
        },
        "document_policy_projection": {
            "source_mode": "document_plan_artifact",
            "policy_refs": [
                {
                    "slot_key": "invoice_mode",
                    "edge_ref": {"parent_node_id": "node-root", "child_node_id": "node-child"},
                    "policy_version": "document_policy.v1",
                    "source": "workflow_binding.decision_table:decision-1:v2",
                }
            ],
            "compiled_document_policy_slots": {
                "invoice_mode": {
                    "decision_table_id": "decision-1",
                    "decision_revision": 2,
                    "document_policy_source": "workflow_binding.decision_table:decision-1:v2",
                    "document_policy": _build_document_policy_payload(),
                }
            },
            "slot_coverage_summary": {
                "total_edges": 1,
                "counts": {
                    "resolved": 1,
                    "missing_selector": 0,
                    "missing_slot": 0,
                    "ambiguous_slot": 0,
                    "ambiguous_context": 0,
                    "unavailable_context": 0,
                },
                "items": [
                    {
                        "edge_id": "node-root:node-child",
                        "edge_label": "node-root -> node-child",
                        "slot_key": "invoice_mode",
                        "coverage": {
                            "code": None,
                            "status": "resolved",
                            "label": "Resolved",
                            "detail": "invoice_mode -> decision-1 r2",
                        },
                    }
                ],
            },
            "policy_refs_count": 1,
            "targets_count": 3,
        },
        "artifacts": {
            "document_plan_artifact_version": "document_plan_artifact.v1",
            "topology_version_ref": "topology:v7",
            "distribution_artifact_ref": {"id": "distribution-artifact:v7"},
        },
        "compile_summary": {
            "steps_count": 5,
            "atomic_publication_steps_count": 3,
            "compiled_targets_count": 3,
        },
    }
    run.workflow_binding_snapshot = binding
    run.runtime_projection_snapshot = projection
    run.save(update_fields=["workflow_binding_snapshot", "runtime_projection_snapshot", "updated_at"])

    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_PENDING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "awaiting_approval",
            "publication_step_state": "not_enqueued",
        },
    )

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    payload = report_response.json()
    run_payload = payload["run"]
    assert run_payload["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert run_payload["workflow_binding"]["binding_profile_revision_id"] == (
        binding["binding_profile_revision_id"]
    )
    assert run_payload["workflow_binding"]["revision"] == binding["revision"]
    assert run_payload["workflow_binding"]["resolved_profile"]["workflow"]["workflow_revision"] == 7
    assert run_payload["workflow_binding"]["resolved_profile"]["decisions"] == [
        {
            "decision_table_id": "decision-1",
            "decision_key": "invoice_mode",
            "decision_revision": 2,
        }
    ]
    assert run_payload["runtime_projection"]["workflow_definition"]["plan_key"] == "plan-services-v7"
    assert run_payload["runtime_projection"]["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert (
        run_payload["runtime_projection"]["workflow_binding"]["binding_profile_revision_id"]
        == binding["binding_profile_revision_id"]
    )
    assert (
        run_payload["runtime_projection"]["workflow_binding"]["attachment_revision"]
        == binding["revision"]
    )
    assert (
        run_payload["runtime_projection"]["document_policy_projection"]["compiled_document_policy_slots"][
            "invoice_mode"
        ]["decision_table_id"]
        == "decision-1"
    )
    assert (
        run_payload["runtime_projection"]["document_policy_projection"]["slot_coverage_summary"]["counts"]["resolved"]
        == 1
    )
    assert run_payload["runtime_projection"]["compile_summary"]["compiled_targets_count"] == 3


@pytest.mark.django_db
def test_get_pool_run_projects_completed_workflow_with_failed_targets_to_partial_success(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    run.publication_summary = {"failed_targets": 2}
    run.save(update_fields=["publication_summary", "updated_at"])
    _attach_workflow_execution_to_run(run=run, status=WorkflowExecution.STATUS_COMPLETED)

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PARTIAL_SUCCESS
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_completed_workflow_with_completed_publication_step_to_published(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "completed",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] == "completed"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_completed_workflow_with_non_completed_publication_step_to_failed(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "queued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_FAILED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] == "queued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED
    diagnostics = payload["run"]["diagnostics"]
    assert any(
        item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
        for item in diagnostics
        if isinstance(item, dict)
    )


@pytest.mark.django_db
def test_get_pool_run_returns_stable_publication_incomplete_problem_code_with_existing_diagnostics(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    run.diagnostics = [
        {
            "type": "about:blank",
            "title": "Validation Error",
            "status": 400,
            "detail": "legacy diagnostics should not replace publication code",
            "code": "VALIDATION_ERROR",
        }
    ]
    run.save(update_fields=["diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "queued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    diagnostics = [item for item in payload["run"]["diagnostics"] if isinstance(item, dict)]
    publication_diagnostics = [
        item
        for item in diagnostics
        if item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
    ]
    assert len(publication_diagnostics) == 1
    publication_problem = publication_diagnostics[0]
    assert publication_problem.get("type") == "about:blank"
    assert publication_problem.get("title") == "Publication Step Incomplete"
    assert publication_problem.get("status") == 409
    assert publication_problem.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
    assert "publication-step completion" in str(publication_problem.get("detail"))
    assert any(item.get("code") == "VALIDATION_ERROR" for item in diagnostics)


@pytest.mark.django_db
def test_get_pool_run_and_report_preserve_legacy_non_list_diagnostics_for_publication_incomplete_problem(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    legacy_diagnostic = {
        "legacy_code": "LEGACY_PUBLICATION_WARNING",
        "detail": "historical diagnostic payload should stay readable",
    }
    run.diagnostics = legacy_diagnostic
    run.save(update_fields=["diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "queued",
        },
    )

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")

    assert details_response.status_code == 200
    assert report_response.status_code == 200
    details_payload = details_response.json()
    report_payload = report_response.json()
    diagnostics = details_payload["run"]["diagnostics"]
    assert report_payload["run"]["diagnostics"] == diagnostics
    assert report_payload["diagnostics"] == diagnostics
    assert legacy_diagnostic in diagnostics
    publication_diagnostics = [
        item
        for item in diagnostics
        if isinstance(item, dict) and item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
    ]
    assert len(publication_diagnostics) == 1


@pytest.mark.django_db
def test_get_pool_run_and_report_preserve_legacy_non_list_diagnostics_for_workflow_failure_problem(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    legacy_diagnostic = "historical worker failure summary"
    run.diagnostics = legacy_diagnostic
    run.save(update_fields=["diagnostics", "updated_at"])
    execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_FAILED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
        },
    )
    WorkflowExecution.objects.filter(id=execution.id).update(
        error_code="POOL_RUNTIME_ROUTE_DISABLED",
        error_message="route disabled for publication",
        error_details={"operation_type": "pool.publication_odata"},
    )

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")

    assert details_response.status_code == 200
    assert report_response.status_code == 200
    details_payload = details_response.json()
    report_payload = report_response.json()
    diagnostics = details_payload["run"]["diagnostics"]
    assert report_payload["run"]["diagnostics"] == diagnostics
    assert report_payload["diagnostics"] == diagnostics
    assert legacy_diagnostic in diagnostics
    workflow_failure_diagnostics = [
        item
        for item in diagnostics
        if isinstance(item, dict) and item.get("code") == "POOL_RUNTIME_ROUTE_DISABLED"
    ]
    assert len(workflow_failure_diagnostics) == 1
    workflow_failure = workflow_failure_diagnostics[0]
    assert workflow_failure.get("title") == "Workflow Execution Failed"
    assert workflow_failure.get("detail") == "route disabled for publication"
    assert workflow_failure.get("error_details") == {"operation_type": "pool.publication_odata"}


@pytest.mark.django_db
def test_get_pool_run_projects_workflow_core_historical_completed_without_publication_state_uses_legacy_projection(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        },
    )

    historical_started_at = datetime(2025, 12, 31, 23, 59, tzinfo=dt_timezone.utc)
    WorkflowExecution.objects.filter(id=run.workflow_execution_id).update(started_at=historical_started_at)

    RuntimeSetting.objects.update_or_create(
        key="pools.projection.publication_hardening_cutoff_utc",
        defaults={"value": "2026-01-01T00:00:00Z"},
    )
    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED
    diagnostics = payload["run"]["diagnostics"]
    assert not any(
        item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
        for item in diagnostics
        if isinstance(item, dict)
    )


@pytest.mark.django_db
def test_get_pool_run_projects_workflow_core_new_completed_without_publication_state_is_failed_after_cutoff(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        },
    )

    started_after_cutoff = datetime(2026, 1, 1, 0, 1, tzinfo=dt_timezone.utc)
    WorkflowExecution.objects.filter(id=run.workflow_execution_id).update(started_at=started_after_cutoff)

    RuntimeSetting.objects.update_or_create(
        key="pools.projection.publication_hardening_cutoff_utc",
        defaults={"value": "2026-01-01T00:00:00Z"},
    )
    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_FAILED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_workflow_core_completed_without_publication_state_ignores_non_utc_cutoff(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        },
    )

    started_after_cutoff = datetime(2026, 1, 1, 0, 1, tzinfo=dt_timezone.utc)
    WorkflowExecution.objects.filter(id=run.workflow_execution_id).update(started_at=started_after_cutoff)

    RuntimeSetting.objects.update_or_create(
        key="pools.projection.publication_hardening_cutoff_utc",
        defaults={"value": "2026-01-01T00:00:00+03:00"},
    )
    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_safe_completed_unapproved_workflow_to_validated_awaiting_approval(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save()
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "preparing",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "awaiting_approval"
    assert payload["run"]["approval_state"] == "awaiting_approval"
    assert payload["run"]["publication_step_state"] == "not_enqueued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_running_approved_with_queued_publication_state_to_validated_queued(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.confirm_publication()
    run.save(
        update_fields=[
            "status",
            "validated_at",
            "validation_summary",
            "diagnostics",
            "publication_confirmed_at",
            "publication_confirmed_by",
            "updated_at",
        ]
    )
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat(),
            "publication_step_state": "queued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "queued"
    assert payload["run"]["approval_state"] == "approved"
    assert payload["run"]["publication_step_state"] == "queued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING


@pytest.mark.django_db
def test_get_pool_run_projects_running_approved_with_started_publication_state_to_publishing(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.confirm_publication()
    run.save(
        update_fields=[
            "status",
            "validated_at",
            "validation_summary",
            "diagnostics",
            "publication_confirmed_at",
            "publication_confirmed_by",
            "updated_at",
        ]
    )
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat(),
            "publication_step_state": "started",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHING
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["approval_state"] == "approved"
    assert payload["run"]["publication_step_state"] == "started"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING


@pytest.mark.django_db
def test_get_pool_run_returns_terminal_reason_from_workflow_input_context(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_CANCELLED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": timezone.now().isoformat(),
            "publication_step_state": "queued",
            "terminal_reason": "aborted_by_operator",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_FAILED
    assert payload["run"]["terminal_reason"] == "aborted_by_operator"


@pytest.mark.django_db
def test_confirm_publication_requires_idempotency_key_header(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.django_db
def test_abort_publication_requires_idempotency_key_header(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.django_db
def test_confirm_publication_returns_noop_200_for_already_approved_run(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="approved",
        approved_at=timezone.now().isoformat(),
        publication_step_state="queued",
        workflow_status=WorkflowExecution.STATUS_RUNNING,
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-noop-1",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == "noop"
    assert payload["replayed"] is False
    assert payload["run"]["approval_state"] == "approved"
    assert payload["run"]["status_reason"] == "queued"
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_abort_publication_returns_noop_200_for_aborted_terminal_replay(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="approved",
        approved_at=timezone.now().isoformat(),
        publication_step_state="queued",
        workflow_status=WorkflowExecution.STATUS_CANCELLED,
        terminal_reason="aborted_by_operator",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-noop-1",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == "noop"
    assert payload["replayed"] is False
    assert payload["run"]["terminal_reason"] == "aborted_by_operator"
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_confirm_publication_from_preparing_returns_retryable_conflict_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="preparing",
        publication_step_state="not_enqueued",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-preparing-1",
    )
    assert response.status_code == 409
    _assert_safe_command_conflict_payload(
        response.json(),
        run_id=run.id,
        expected_code="AWAITING_PRE_PUBLISH",
        expected_reason="awaiting_pre_publish",
        expected_retryable=True,
    )


@pytest.mark.django_db
def test_confirm_publication_with_readiness_blockers_returns_problem_details(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
        input_context_overrides={
            "pool_runtime_readiness_blockers": [
                {
                    "code": "POOL_DOCUMENT_POLICY_MAPPING_INVALID",
                    "detail": "Document policy is incomplete for minimal_documents_full_payload.",
                    "entity_name": "Document_Sales",
                    "field_or_table_path": "Goods",
                }
            ]
        },
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-readiness-problem-1",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=409,
        code="POOL_RUN_READINESS_BLOCKED",
    )
    assert payload["title"] == "Pool Run Readiness Blocked"
    assert payload["errors"] == [
        {
            "code": "POOL_DOCUMENT_POLICY_MAPPING_INVALID",
            "detail": "Document policy is incomplete for minimal_documents_full_payload.",
            "kind": None,
            "entity_name": "Document_Sales",
            "field_or_table_path": "Goods",
            "database_id": None,
            "organization_id": None,
            "edge_ref": None,
            "participant_side": None,
            "required_role": None,
            "diagnostic": None,
        }
    ]
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_confirm_publication_with_topology_readiness_blockers_returns_problem_details(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    organization_id = str(uuid4())
    database_id = str(uuid4())
    parent_node_id = str(uuid4())
    child_node_id = str(uuid4())
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
        input_context_overrides={
            "pool_runtime_readiness_blockers": [
                {
                    "code": MASTER_DATA_PARTY_ROLE_MISSING,
                    "detail": "Child organization is bound to a party without counterparty role.",
                    "organization_id": organization_id,
                    "database_id": database_id,
                    "edge_ref": {
                        "parent_node_id": parent_node_id,
                        "child_node_id": child_node_id,
                    },
                    "participant_side": "child",
                    "required_role": "counterparty",
                }
            ]
        },
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-topology-readiness-problem-1",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=409,
        code="POOL_RUN_READINESS_BLOCKED",
    )
    assert payload["errors"] == [
        {
            "code": MASTER_DATA_PARTY_ROLE_MISSING,
            "detail": "Child organization is bound to a party without counterparty role.",
            "kind": None,
            "entity_name": None,
            "field_or_table_path": None,
            "database_id": database_id,
            "organization_id": organization_id,
            "edge_ref": {
                "parent_node_id": parent_node_id,
                "child_node_id": child_node_id,
            },
            "participant_side": "child",
            "required_role": "counterparty",
            "diagnostic": None,
        }
    ]
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_confirm_publication_for_unsafe_run_returns_not_safe_conflict_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        mode=PoolRunMode.UNSAFE,
        approval_required=False,
        approval_state="not_required",
        approved_at=timezone.now().isoformat(),
        publication_step_state="queued",
        workflow_status=WorkflowExecution.STATUS_RUNNING,
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-unsafe-1",
    )
    assert response.status_code == 409
    _assert_safe_command_conflict_payload(
        response.json(),
        run_id=run.id,
        expected_code="NOT_SAFE_RUN",
        expected_reason="not_safe_run",
        expected_retryable=False,
    )


@pytest.mark.django_db
def test_abort_publication_after_started_step_returns_publication_started_conflict_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="approved",
        approved_at=timezone.now().isoformat(),
        publication_step_state="started",
        workflow_status=WorkflowExecution.STATUS_RUNNING,
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-started-1",
    )
    assert response.status_code == 409
    _assert_safe_command_conflict_payload(
        response.json(),
        run_id=run.id,
        expected_code="PUBLICATION_STARTED",
        expected_reason="publication_started",
        expected_retryable=False,
    )


@pytest.mark.django_db
def test_confirm_publication_returns_accepted_and_deterministic_replay(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    first = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-key-1",
    )
    replay = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-key-1",
    )

    assert first.status_code == 202
    first_payload = first.json()
    assert first_payload["result"] == "accepted"
    assert first_payload["replayed"] is False

    assert replay.status_code == 202
    replay_payload = replay.json()
    assert replay_payload["result"] == "accepted"
    assert replay_payload["replayed"] is True

    execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert execution.input_context.get("publication_auth") == {
        "strategy": "actor",
        "actor_username": user.username,
        "source": "confirm_publication",
    }
    assert PoolRunCommandLog.objects.filter(run=run).count() == 1
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_abort_publication_returns_accepted_and_deterministic_replay(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
    )

    first = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-key-replay-1",
    )
    replay = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-key-replay-1",
    )

    assert first.status_code == 202
    first_payload = first.json()
    assert first_payload["result"] == "accepted"
    assert first_payload["replayed"] is False

    assert replay.status_code == 202
    replay_payload = replay.json()
    assert replay_payload["result"] == "accepted"
    assert replay_payload["replayed"] is True

    assert PoolRunCommandLog.objects.filter(run=run).count() == 1
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_abort_publication_after_confirm_pending_outbox_returns_single_winner_conflict(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    confirm = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-key-2",
    )
    abort = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-key-2",
    )

    assert confirm.status_code == 202
    assert abort.status_code == 409
    _assert_safe_command_conflict_payload(
        abort.json(),
        run_id=run.id,
        expected_code="TERMINAL_STATE",
        expected_reason="terminal_state",
        expected_retryable=False,
    )

    outbox_entries = list(PoolRunCommandOutbox.objects.filter(run=run))
    assert len(outbox_entries) == 1


@pytest.mark.django_db
def test_confirm_publication_with_reused_key_from_other_command_returns_idempotency_conflict(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    abort = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="shared-key",
    )
    confirm = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="shared-key",
    )

    assert abort.status_code == 202
    assert confirm.status_code == 409
    _assert_safe_command_conflict_payload(
        confirm.json(),
        run_id=run.id,
        expected_code="IDEMPOTENCY_KEY_REUSED",
        expected_reason="idempotency_key_reused",
        expected_retryable=False,
    )


@pytest.mark.django_db
def test_get_pool_run_cross_tenant_and_unknown_run_are_indistinguishable(
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)

    another_tenant = Tenant.objects.create(slug=f"tenant-alt-{uuid4().hex[:6]}", name="Tenant Alt")
    TenantMember.objects.create(
        tenant=another_tenant,
        user=user,
        role=TenantMember.ROLE_ADMIN,
    )
    another_client = APIClient()
    another_client.force_authenticate(user=user)
    another_client.credentials(HTTP_X_CC1C_TENANT_ID=str(another_tenant.id))

    cross_tenant_response = another_client.get(f"/api/v2/pools/runs/{run.id}/")
    unknown_response = another_client.get(f"/api/v2/pools/runs/{uuid4()}/")

    assert cross_tenant_response.status_code == 404
    assert unknown_response.status_code == 404
    assert cross_tenant_response.json() == unknown_response.json()
    assert cross_tenant_response.json()["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.django_db
def test_confirm_publication_cross_tenant_and_unknown_run_are_indistinguishable(
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
    )

    another_tenant = Tenant.objects.create(slug=f"tenant-alt-safe-{uuid4().hex[:6]}", name="Tenant Alt Safe")
    TenantMember.objects.create(
        tenant=another_tenant,
        user=user,
        role=TenantMember.ROLE_ADMIN,
    )
    another_client = APIClient()
    another_client.force_authenticate(user=user)
    another_client.credentials(HTTP_X_CC1C_TENANT_ID=str(another_tenant.id))

    cross_tenant_response = another_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="tenant-cross-check",
    )
    unknown_response = another_client.post(
        f"/api/v2/pools/runs/{uuid4()}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="tenant-cross-check-unknown",
    )

    assert cross_tenant_response.status_code == 404
    assert unknown_response.status_code == 404
    assert cross_tenant_response.json() == unknown_response.json()
    assert cross_tenant_response.json()["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_returns_accepted_workflow_reference_and_avoids_direct_publication(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    binding, _ = _prepare_single_pool_runtime_binding(
        tenant=default_tenant,
        pool=pool,
        workflow_definition_key="retry-publication",
        workflow_revision=3,
        direction=run.direction,
        mode=run.mode,
        period_start=run.period_start,
        actor=user,
    )
    db_one = _create_database(tenant=default_tenant, name="pool-api-retry-db-one")
    db_two = _create_database(tenant=default_tenant, name="pool-api-retry-db-two")
    initial_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY: binding,
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_one,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=True,
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_two,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary network error",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-1", status="queued"),
    ) as enqueue:
        response = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(db_one.id): [{"Amount": "100.00"}, {"Amount": "110.00"}],
                    str(db_two.id): [{"Amount": "90.00"}],
                },
                "use_retry_subset_payload": True,
                "max_attempts": 1,
            },
            format="json",
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["operation_id"] == "retry-op-1"
    assert payload["retry_target_summary"] == {
        "requested_targets": 2,
        "requested_documents": 3,
        "failed_targets": 1,
        "enqueued_targets": 1,
        "skipped_successful_targets": 1,
    }
    assert payload["workflow_execution_id"] != str(initial_execution.id)
    enqueue.assert_called_once()

    run_reloaded = PoolRun.objects.get(id=run.id)
    assert str(run_reloaded.workflow_execution_id) == payload["workflow_execution_id"]
    assert run_reloaded.workflow_status == "queued"
    retry_execution = WorkflowExecution.objects.get(id=run_reloaded.workflow_execution_id)
    assert retry_execution.input_context.get("attempt_kind") == "retry"
    assert retry_execution.input_context.get("attempt_number") == 2
    assert retry_execution.input_context.get("parent_workflow_run_id") == str(initial_execution.id)
    retry_request = retry_execution.input_context.get("retry_request")
    assert isinstance(retry_request, dict)
    assert retry_request.get("requested_target_ids") == [str(db_two.id)]
    assert retry_request.get("requested_targets_count") == 1
    assert retry_request.get("requested_documents_count") == 1
    assert retry_request.get("use_retry_subset_payload") is True
    assert retry_execution.input_context.get("pool_runtime_retry_settings") == {
        "use_retry_subset_payload": True,
    }
    publication_payload = retry_execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    assert pool_runtime_payload.get("entity_name") == "Document_IntercompanyPoolDistribution"
    assert pool_runtime_payload.get("documents_by_database") == {
        str(db_two.id): [{"Amount": "90.00"}],
    }
    assert retry_execution.input_context.get("publication_auth") == {
        "strategy": "actor",
        "actor_username": user.username,
        "source": "retry_publication",
    }


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_builds_subset_from_persisted_document_plan_artifact(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    binding, _ = _prepare_single_pool_runtime_binding(
        tenant=default_tenant,
        pool=pool,
        workflow_definition_key="retry-publication-artifact",
        workflow_revision=3,
        direction=run.direction,
        mode=run.mode,
        period_start=run.period_start,
        actor=user,
    )
    db_success = _create_database(tenant=default_tenant, name="pool-api-retry-success-db")
    db_failed = _create_database(tenant=default_tenant, name="pool-api-retry-failed-db")
    initial_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY: binding,
            "pool_runtime_document_plan_artifact": {
                "version": "document_plan_artifact.v1",
                "run_id": str(run.id),
                "distribution_artifact_ref": {
                    "version": "distribution_artifact.v1",
                    "topology_version_ref": "topology-v1",
                },
                "topology_version_ref": "topology-v1",
                "policy_refs": [
                    {
                        "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-child"},
                        "policy_version": "document_policy.v1",
                        "source": "edge.metadata.document_policy",
                    }
                ],
                "targets": [
                    {
                        "database_id": str(db_success.id),
                        "chains": [
                            {
                                "chain_id": "chain-success",
                                "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-success"},
                                "policy_source": "edge.metadata.document_policy",
                                "policy_version": "document_policy.v1",
                                "allocation": {"amount": "80.00"},
                                "documents": [
                                    {
                                        "document_id": "doc-success",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "optional",
                                        "idempotency_key": "doc-success-key",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "database_id": str(db_failed.id),
                        "chains": [
                            {
                                "chain_id": "chain-failed",
                                "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-failed"},
                                "policy_source": "edge.metadata.document_policy",
                                "policy_version": "document_policy.v1",
                                "allocation": {"amount": "20.00"},
                                "documents": [
                                    {
                                        "document_id": "doc-sale",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "optional",
                                        "idempotency_key": "doc-sale-key",
                                    },
                                    {
                                        "document_id": "doc-invoice",
                                        "entity_name": "Document_Invoice",
                                        "document_role": "invoice",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "required",
                                        "idempotency_key": "doc-invoice-key",
                                        "link_to": "doc-sale",
                                    },
                                ],
                            }
                        ],
                    },
                ],
                "compile_summary": {
                    "compiled_edges": 1,
                    "targets_count": 2,
                    "chains_count": 2,
                    "documents_count": 3,
                    "compiled_at": "2026-01-01T00:00:00+00:00",
                },
            },
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_success,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_Sales",
        documents_count=1,
        posted=True,
        request_summary={
            "documents_count": 1,
            "document_idempotency_keys": ["doc-success-key"],
        },
        response_summary={
            "posted": True,
            "successful_document_idempotency_keys": ["doc-success-key"],
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_failed,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_Sales",
        documents_count=2,
        posted=False,
        error_code="network",
        error_message="temporary network error",
        request_summary={
            "documents_count": 2,
            "document_idempotency_keys": ["doc-sale-key", "doc-invoice-key"],
        },
        response_summary={
            "posted": False,
            "successful_document_idempotency_keys": ["doc-sale-key"],
            "successful_document_refs": {"doc-sale-key": "sale-doc-ref"},
            "failed_document_idempotency_key": "doc-invoice-key",
        },
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-artifact", status="queued"),
    ) as enqueue:
        response = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "target_database_ids": [str(db_failed.id)],
                "use_retry_subset_payload": True,
                "max_attempts": 1,
            },
            format="json",
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["operation_id"] == "retry-op-artifact"
    assert payload["retry_target_summary"] == {
        "requested_targets": 1,
        "requested_documents": 0,
        "failed_targets": 1,
        "enqueued_targets": 1,
        "skipped_successful_targets": 0,
    }
    assert payload["workflow_execution_id"] != str(initial_execution.id)
    enqueue.assert_called_once()

    run_reloaded = PoolRun.objects.get(id=run.id)
    retry_execution = WorkflowExecution.objects.get(id=run_reloaded.workflow_execution_id)
    retry_request = retry_execution.input_context.get("retry_request")
    assert isinstance(retry_request, dict)
    assert retry_request.get("requested_target_ids") == [str(db_failed.id)]
    assert retry_request.get("requested_targets_count") == 1
    assert retry_request.get("requested_documents_count") == 0
    publication_payload = retry_execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    assert pool_runtime_payload.get("documents_by_database") == {
        str(db_failed.id): [{"Amount": "20.00"}]
    }
    assert pool_runtime_payload.get("document_chains_by_database") == {
        str(db_failed.id): [
            {
                "chain_id": "chain-failed",
                "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-failed"},
                "policy_source": "edge.metadata.document_policy",
                "policy_version": "document_policy.v1",
                "allocation": {"amount": "20.00"},
                "documents": [
                    {
                        "document_id": "doc-invoice",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "idempotency_key": "doc-invoice-key",
                        "invoice_mode": "required",
                        "field_mapping": {},
                        "table_parts_mapping": {},
                        "link_rules": {},
                        "payload": {},
                        "link_to": "doc-sale",
                        "resolved_link_refs": {"doc-sale": "sale-doc-ref"},
                    }
                ],
            }
        ]
    }


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_replays_idempotency_key_without_duplicate_enqueue(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    binding, _ = _prepare_single_pool_runtime_binding(
        tenant=default_tenant,
        pool=pool,
        workflow_definition_key="retry-publication-replay",
        workflow_revision=3,
        direction=run.direction,
        mode=run.mode,
        period_start=run.period_start,
        actor=user,
    )
    failed_db = _create_database(tenant=default_tenant, name="pool-api-retry-replay-failed-db")
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY: binding,
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=failed_db,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary network error",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-replay", status="queued"),
    ) as enqueue:
        first = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-replay-key-1",
        )
        replay = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-replay-key-1",
        )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == first.json()
    enqueue.assert_called_once()
    logs = list(
        PoolRunCommandLog.objects.filter(
            run=run,
            command_type=PoolRunCommandType.RETRY_PUBLICATION,
        )
    )
    assert len(logs) == 1
    assert logs[0].replay_count == 1


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_reused_key_with_different_payload_returns_conflict(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    binding, _ = _prepare_single_pool_runtime_binding(
        tenant=default_tenant,
        pool=pool,
        workflow_definition_key="retry-publication-reuse",
        workflow_revision=3,
        direction=run.direction,
        mode=run.mode,
        period_start=run.period_start,
        actor=user,
    )
    failed_db = _create_database(tenant=default_tenant, name="pool-api-retry-reuse-failed-db")
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY: binding,
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=failed_db,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary network error",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-reuse", status="queued"),
    ) as enqueue:
        first = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-reuse-key-1",
        )
        reused = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 2,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-reuse-key-1",
        )

    assert first.status_code == 202
    assert reused.status_code == 409
    _assert_safe_command_conflict_payload(
        reused.json(),
        run_id=run.id,
        expected_code="IDEMPOTENCY_KEY_REUSED",
        expected_reason="idempotency_key_reused",
        expected_retryable=False,
    )
    enqueue.assert_called_once()


@pytest.mark.django_db
def test_list_schema_templates_returns_public_by_default(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    public_template = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-public",
        name="JSON Public",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-private",
        name="JSON Private",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=False,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    response = authenticated_client.get("/api/v2/pools/schema-templates/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["templates"][0]["id"] == str(public_template.id)


@pytest.mark.django_db
def test_list_schema_templates_supports_format_and_visibility_filters(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    json_public_active = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-public-active",
        name="JSON Public Active",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-public-inactive",
        name="JSON Public Inactive",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=False,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    xlsx_private_active = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="xlsx-private-active",
        name="XLSX Private Active",
        format=PoolSchemaTemplateFormat.XLSX,
        is_public=False,
        is_active=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    filtered = authenticated_client.get(
        "/api/v2/pools/schema-templates/?format=json&is_public=true&is_active=true"
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["count"] == 1
    assert filtered_payload["templates"][0]["id"] == str(json_public_active.id)

    private_only = authenticated_client.get("/api/v2/pools/schema-templates/?is_public=false")
    assert private_only.status_code == 200
    private_payload = private_only.json()
    assert private_payload["count"] == 1
    assert private_payload["templates"][0]["id"] == str(xlsx_private_active.id)


@pytest.mark.django_db
def test_create_schema_template_with_optional_workflow_binding(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/schema-templates/",
        {
            "code": "xlsx-import-v1",
            "name": "XLSX Import V1",
            "format": PoolSchemaTemplateFormat.XLSX,
            "schema": {"sheet_name": "Sheet1", "columns": {"inn": "inn", "amount": "amount"}},
            "workflow_template_id": "11111111-1111-1111-1111-111111111111",
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["template"]["code"] == "xlsx-import-v1"
    assert payload["template"]["workflow_template_id"] == "11111111-1111-1111-1111-111111111111"

    duplicate = authenticated_client.post(
        "/api/v2/pools/schema-templates/",
        {
            "code": "xlsx-import-v1",
            "name": "Duplicate",
            "format": PoolSchemaTemplateFormat.XLSX,
        },
        format="json",
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_TEMPLATE_CODE"


@pytest.mark.django_db
def test_update_schema_template(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    template = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-import-v1",
        name="JSON Import V1",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={"columns": {"inn": "inn"}},
        metadata={"workflow_binding": {"label": "legacy"}},
    )

    response = authenticated_client.put(
        f"/api/v2/pools/schema-templates/{template.id}/",
        {
            "code": "json-import-v2",
            "name": "JSON Import V2",
            "format": PoolSchemaTemplateFormat.JSON,
            "is_public": False,
            "is_active": True,
            "schema": {"columns": {"inn": "inn", "amount": "amount"}},
            "metadata": {"workflow_binding": {"label": "compat-v2"}},
            "workflow_template_id": "33333333-3333-3333-3333-333333333333",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["template"]["code"] == "json-import-v2"
    assert payload["template"]["name"] == "JSON Import V2"
    assert payload["template"]["is_public"] is False
    assert payload["template"]["workflow_template_id"] == "33333333-3333-3333-3333-333333333333"

    template.refresh_from_db()
    assert template.code == "json-import-v2"
    assert template.name == "JSON Import V2"
    assert template.is_public is False
    assert template.schema == {"columns": {"inn": "inn", "amount": "amount"}}
    assert template.metadata["workflow_template_id"] == "33333333-3333-3333-3333-333333333333"


@pytest.mark.django_db
def test_update_schema_template_returns_404_for_missing_template(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.put(
        f"/api/v2/pools/schema-templates/{uuid4()}/",
        {
            "code": "json-import-v2",
            "name": "JSON Import V2",
            "format": PoolSchemaTemplateFormat.JSON,
        },
        format="json",
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEMPLATE_NOT_FOUND"


@pytest.mark.django_db
def test_graph_endpoint_filters_versions_by_requested_date(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Root Date", inn="750000000001")
    jan_org = Organization.objects.create(tenant=default_tenant, name="Jan Child", inn="750000000002")
    feb_org = Organization.objects.create(tenant=default_tenant, name="Feb Child", inn="750000000003")
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    jan_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=jan_org,
        effective_from=date(2026, 1, 1),
    )
    feb_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=feb_org,
        effective_from=date(2026, 2, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=jan_node,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=feb_node,
        effective_from=date(2026, 2, 1),
    )

    january_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert january_response.status_code == 200
    january_payload = january_response.json()
    assert len(january_payload["nodes"]) == 2
    assert len(january_payload["edges"]) == 1

    february_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-02-15")
    assert february_response.status_code == 200
    february_payload = february_response.json()
    assert len(february_payload["nodes"]) == 3
    assert len(february_payload["edges"]) == 2


@pytest.mark.django_db
def test_list_pools_and_graph_endpoint(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Root", inn="700000000001")
    child_org = Organization.objects.create(tenant=default_tenant, name="Child", inn="700000000002")
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
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=child_node,
        effective_from=date(2026, 1, 1),
    )

    pools_response = authenticated_client.get("/api/v2/pools/")
    assert pools_response.status_code == 200
    pools_payload = pools_response.json()
    assert pools_payload["count"] >= 1
    assert any(item["id"] == str(pool.id) for item in pools_payload["pools"])

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["pool_id"] == str(pool.id)
    assert len(graph_payload["nodes"]) == 2
    assert len(graph_payload["edges"]) == 1
    assert any(node["is_root"] for node in graph_payload["nodes"])


@pytest.mark.django_db
def test_list_pools_endpoint_ignores_invalid_canonical_workflow_bindings(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    PoolWorkflowBinding.objects.create(
        binding_id="binding-invalid-slot",
        tenant=default_tenant,
        pool=pool,
        status="active",
        effective_from=date(2026, 1, 1),
        direction="bottom_up",
        mode="safe",
        selector_tags=[],
        workflow_definition_key="wf-invalid-slot",
        workflow_revision_id="wf-invalid-slot-r1",
        workflow_revision=1,
        workflow_name="Workflow Invalid Slot",
        decisions=[
            {
                "decision_table_id": "baseline-services-policy",
                "decision_key": "document_policy",
                "decision_revision": 1,
            }
        ],
        parameters={},
        role_mapping={},
        revision=1,
        created_by="test",
        updated_by="test",
    )

    pools_response = authenticated_client.get("/api/v2/pools/")

    assert pools_response.status_code == 200
    pools_payload = pools_response.json()
    pool_payload = next(item for item in pools_payload["pools"] if item["id"] == str(pool.id))
    assert pool_payload["workflow_bindings"] == []
    assert pool_payload["metadata"]["workflow_bindings_read_error"] == {
        "code": "POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING",
        "detail": "Workflow binding 'binding-invalid-slot' is missing binding_profile references.",
    }


@pytest.mark.django_db
def test_create_pool_run_with_schema_template_uses_workflow_runtime(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    template = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-run-template",
        name="JSON Run Template",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    bindings, _ = _prepare_pool_runtime_bindings(
        tenant=default_tenant,
        pool=pool,
        bindings=[
            _build_pool_workflow_binding_payload(
                pool=pool,
                workflow_definition_key="services-publication",
                workflow_revision=3,
                direction=PoolRunDirection.BOTTOM_UP,
                mode=PoolRunMode.UNSAFE,
            )
        ],
        period_start=date(2026, 1, 1),
        actor=user,
    )
    binding = bindings[0]

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-2", status="queued"),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "pool_workflow_binding_id": binding["binding_id"],
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_artifact_id": "artifact://pool-run-input"},
                "mode": "unsafe",
                "schema_template_id": str(template.id),
                "seed": 42,
            },
            format="json",
        )
    assert response.status_code == 201
    payload = response.json()
    assert payload["created"] is True
    assert payload["run"]["schema_template_id"] == str(template.id)
    assert payload["run"]["seed"] == 42
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["workflow_execution_id"] is not None
    assert payload["run"]["approval_state"] == "not_required"
    assert payload["run"]["publication_step_state"] == "queued"
    assert payload["run"]["execution_backend"] == "workflow_core"
    workflow_execution = WorkflowExecution.objects.get(id=payload["run"]["workflow_execution_id"])
    assert workflow_execution.execution_consumer == "pools"
    assert workflow_execution.tenant_id == default_tenant.id
    run = PoolRun.objects.get(id=payload["run"]["id"])
    assert run.publication_confirmed_at is not None
    assert workflow_execution.input_context.get("approved_at") is not None
    assert workflow_execution.input_context.get("approval_state") == "not_required"
    assert workflow_execution.input_context.get("publication_step_state") == "queued"


@pytest.mark.django_db
def test_list_runs_and_report_endpoint(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-report-db")
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=True,
    )

    runs_response = authenticated_client.get(f"/api/v2/pools/runs/?pool_id={pool.id}&limit=10")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["count"] >= 1
    assert any(item["id"] == str(run.id) for item in runs_payload["runs"])

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["id"] == str(run.id)
    assert report_payload["validation_summary"]["rows"] == 1
    assert report_payload["attempts_by_status"]["success"] == 1
    assert len(report_payload["publication_attempts"]) == 1
