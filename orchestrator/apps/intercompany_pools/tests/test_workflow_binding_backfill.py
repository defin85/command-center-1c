from __future__ import annotations

import io
import json
from uuid import uuid4

import pytest
from django.core.management import call_command

from apps.intercompany_pools.models import OrganizationPool
from apps.intercompany_pools.workflow_binding_backfill import (
    REMEDIATION_REASON_CANONICAL_ONLY_BINDING,
    REMEDIATION_REASON_CONFLICTING_CANONICAL_BINDING,
    REMEDIATION_REASON_INVALID_LEGACY_BINDING,
    run_pool_workflow_binding_backfill,
)
from apps.intercompany_pools.workflow_bindings_store import (
    list_canonical_pool_workflow_bindings,
    upsert_canonical_pool_workflow_binding,
)
from apps.tenancy.models import Tenant


def _create_tenant(*, slug_prefix: str) -> Tenant:
    return Tenant.objects.create(
        slug=f"{slug_prefix}-{uuid4().hex[:8]}",
        name=f"{slug_prefix} tenant",
    )


def _create_pool(*, tenant: Tenant, code_prefix: str, metadata: dict | None = None) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=tenant,
        code=f"{code_prefix}-{uuid4().hex[:6]}",
        name=f"{code_prefix} pool",
        metadata=metadata or {},
    )


def _build_binding_payload(
    *,
    pool: OrganizationPool,
    binding_id: str | None = None,
    slot_key: str | None = None,
) -> dict[str, object]:
    decision_ref: dict[str, object] = {
        "decision_table_id": "document-policy",
        "decision_key": "document_policy",
        "decision_revision": 2,
    }
    if slot_key is not None:
        decision_ref["slot_key"] = slot_key
    return {
        "binding_id": binding_id or str(uuid4()),
        "pool_id": str(pool.id),
        "workflow": {
            "workflow_definition_key": "services-publication",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": 3,
            "workflow_name": "services_publication",
        },
        "decisions": [
            decision_ref
        ],
        "parameters": {"publication_variant": "full"},
        "role_mapping": {"initiator": "finance"},
        "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
        "effective_from": "2026-01-01",
        "status": "active",
    }


@pytest.mark.django_db
def test_workflow_binding_backfill_imports_legacy_metadata_into_canonical_store() -> None:
    tenant = _create_tenant(slug_prefix="wf-binding-backfill")
    pool = _create_pool(tenant=tenant, code_prefix="wf-binding-backfill")
    legacy_binding = _build_binding_payload(pool=pool)
    pool.metadata = {"workflow_bindings": [legacy_binding]}
    pool.save(update_fields=["metadata", "updated_at"])

    stats = run_pool_workflow_binding_backfill()

    canonical_bindings = list_canonical_pool_workflow_bindings(pool=pool)
    assert stats.pools_with_legacy_bindings == 1
    assert stats.pools_backfilled == 1
    assert stats.pools_already_imported == 0
    assert stats.pools_conflicted == 0
    assert stats.pools_invalid_legacy == 0
    assert stats.legacy_bindings_seen == 1
    assert stats.canonical_created == 1
    assert stats.canonical_unchanged == 0
    assert len(canonical_bindings) == 1
    assert canonical_bindings[0]["binding_id"] == legacy_binding["binding_id"]
    assert canonical_bindings[0]["workflow"]["workflow_revision"] == 3
    assert canonical_bindings[0]["decisions"][0]["slot_key"] == "document_policy"

    pool.refresh_from_db(fields=["metadata"])
    assert pool.metadata["workflow_bindings"][0]["binding_id"] == legacy_binding["binding_id"]


@pytest.mark.django_db
def test_workflow_binding_backfill_is_idempotent_when_canonical_matches_legacy() -> None:
    tenant = _create_tenant(slug_prefix="wf-binding-idempotent")
    pool = _create_pool(tenant=tenant, code_prefix="wf-binding-idempotent")
    legacy_binding = _build_binding_payload(pool=pool)
    pool.metadata = {"workflow_bindings": [legacy_binding]}
    pool.save(update_fields=["metadata", "updated_at"])

    first_stats = run_pool_workflow_binding_backfill()
    second_stats = run_pool_workflow_binding_backfill()

    assert first_stats.canonical_created == 1
    assert second_stats.canonical_created == 0
    assert second_stats.canonical_unchanged == 1
    assert second_stats.pools_already_imported == 1
    assert len(list_canonical_pool_workflow_bindings(pool=pool)) == 1


@pytest.mark.django_db
def test_workflow_binding_backfill_reports_invalid_legacy_binding_payload() -> None:
    tenant = _create_tenant(slug_prefix="wf-binding-invalid")
    pool = _create_pool(
        tenant=tenant,
        code_prefix="wf-binding-invalid",
        metadata={
            "workflow_bindings": [
                {
                    "binding_id": str(uuid4()),
                    "workflow": {
                        "workflow_definition_key": "services-publication",
                        "workflow_revision_id": str(uuid4()),
                        "workflow_revision": 3,
                        "workflow_name": "services_publication",
                    },
                    "effective_from": "2026-02-01",
                    "effective_to": "2026-01-01",
                    "status": "active",
                }
            ]
        },
    )

    stats = run_pool_workflow_binding_backfill()

    assert stats.pools_invalid_legacy == 1
    assert stats.canonical_created == 0
    assert list_canonical_pool_workflow_bindings(pool=pool) == []
    remediation = stats.remediation_list[0]
    assert remediation.reason == REMEDIATION_REASON_INVALID_LEGACY_BINDING
    assert remediation.pool_id == str(pool.id)


@pytest.mark.django_db
def test_workflow_binding_backfill_reports_conflicting_existing_canonical_binding() -> None:
    tenant = _create_tenant(slug_prefix="wf-binding-conflict")
    pool = _create_pool(tenant=tenant, code_prefix="wf-binding-conflict")
    legacy_binding = _build_binding_payload(pool=pool, binding_id=str(uuid4()))
    conflicting_binding = _build_binding_payload(
        pool=pool,
        binding_id=str(legacy_binding["binding_id"]),
        slot_key="document_policy",
    )
    conflicting_binding["workflow"] = {
        **legacy_binding["workflow"],
        "workflow_revision": 4,
        "workflow_revision_id": str(uuid4()),
    }
    pool.metadata = {"workflow_bindings": [legacy_binding]}
    pool.save(update_fields=["metadata", "updated_at"])
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=conflicting_binding,
        actor_username="seed-conflict",
    )

    stats = run_pool_workflow_binding_backfill()

    assert stats.pools_conflicted == 1
    assert stats.canonical_created == 0
    remediation = next(
        item for item in stats.remediation_list if item.reason == REMEDIATION_REASON_CONFLICTING_CANONICAL_BINDING
    )
    assert remediation.pool_id == str(pool.id)
    assert remediation.binding_id == str(legacy_binding["binding_id"])
    canonical_bindings = list_canonical_pool_workflow_bindings(pool=pool)
    assert canonical_bindings[0]["workflow"]["workflow_revision"] == 4


@pytest.mark.django_db
def test_workflow_binding_backfill_reports_canonical_only_bindings() -> None:
    tenant = _create_tenant(slug_prefix="wf-binding-canonical-only")
    pool = _create_pool(tenant=tenant, code_prefix="wf-binding-canonical-only")
    legacy_binding = _build_binding_payload(pool=pool)
    pool.metadata = {"workflow_bindings": [legacy_binding]}
    pool.save(update_fields=["metadata", "updated_at"])
    extra_canonical_binding = _build_binding_payload(pool=pool, slot_key="document_policy")
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=extra_canonical_binding,
        actor_username="seed-extra",
    )

    stats = run_pool_workflow_binding_backfill()

    assert stats.pools_conflicted == 1
    remediation = next(
        item for item in stats.remediation_list if item.reason == REMEDIATION_REASON_CANONICAL_ONLY_BINDING
    )
    assert remediation.binding_id == str(extra_canonical_binding["binding_id"])


@pytest.mark.django_db
def test_backfill_pool_workflow_bindings_command_supports_dry_run_and_json_output() -> None:
    tenant = _create_tenant(slug_prefix="wf-binding-command")
    pool = _create_pool(tenant=tenant, code_prefix="wf-binding-command")
    legacy_binding = _build_binding_payload(pool=pool)
    pool.metadata = {"workflow_bindings": [legacy_binding]}
    pool.save(update_fields=["metadata", "updated_at"])

    out_dry_run = io.StringIO()
    call_command("backfill_pool_workflow_bindings", "--dry-run", "--json", stdout=out_dry_run)
    dry_run_payload = json.loads(out_dry_run.getvalue())
    assert dry_run_payload["dry_run"] is True
    assert dry_run_payload["canonical_created"] == 1
    assert list_canonical_pool_workflow_bindings(pool=pool) == []

    out_apply = io.StringIO()
    call_command("backfill_pool_workflow_bindings", "--json", stdout=out_apply)
    apply_payload = json.loads(out_apply.getvalue())
    assert apply_payload["dry_run"] is False
    assert apply_payload["canonical_created"] == 1
    assert len(list_canonical_pool_workflow_bindings(pool=pool)) == 1
