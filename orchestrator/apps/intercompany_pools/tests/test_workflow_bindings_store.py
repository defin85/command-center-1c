from __future__ import annotations

from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.workflow_bindings_store import (
    PoolWorkflowBindingNotFoundError,
    get_canonical_pool_workflow_binding,
    list_canonical_pool_workflow_bindings,
    upsert_canonical_pool_workflow_binding,
)
from apps.tenancy.models import Tenant


def _build_binding_payload(*, pool: OrganizationPool) -> dict[str, object]:
    return {
        "binding_id": str(uuid4()),
        "pool_id": str(pool.id),
        "workflow": {
            "workflow_definition_key": "services-publication",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": 3,
            "workflow_name": "services_publication",
        },
        "decisions": [
            {
                "decision_table_id": "document-policy",
                "decision_key": "document_policy",
                "decision_revision": 2,
            }
        ],
        "parameters": {
            "publication_variant": "full",
        },
        "role_mapping": {
            "initiator": "finance",
        },
        "selector": {
            "direction": "top_down",
            "mode": "safe",
            "tags": ["baseline"],
        },
        "effective_from": "2026-01-01",
        "status": "active",
    }


@pytest.mark.django_db
def test_upsert_canonical_pool_workflow_binding_persists_required_fields() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-{uuid4().hex[:8]}", name="Binding Store")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Pool",
    )

    saved_binding, created = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="architect",
    )

    assert created is True
    record = PoolWorkflowBinding.objects.get(binding_id=saved_binding["binding_id"])
    assert record.tenant_id == tenant.id
    assert record.pool_id == pool.id
    assert record.direction == "top_down"
    assert record.mode == "safe"
    assert record.selector_tags == ["baseline"]
    assert record.workflow_definition_key == "services-publication"
    assert record.workflow_revision == 3
    assert record.decisions == saved_binding["decisions"]
    assert record.parameters == {"publication_variant": "full"}
    assert record.role_mapping == {"initiator": "finance"}
    assert record.revision == 1
    assert record.created_by == "architect"
    assert record.updated_by == "architect"

    listed = list_canonical_pool_workflow_bindings(pool=pool)
    assert listed == [saved_binding]
    resolved = get_canonical_pool_workflow_binding(pool=pool, binding_id=saved_binding["binding_id"])
    assert resolved == saved_binding


@pytest.mark.django_db
def test_get_canonical_pool_workflow_binding_raises_for_missing_record() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-missing-{uuid4().hex[:8]}", name="Missing Binding")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Missing Binding Pool",
    )

    with pytest.raises(PoolWorkflowBindingNotFoundError):
        get_canonical_pool_workflow_binding(pool=pool, binding_id="missing-binding")


@pytest.mark.django_db
def test_pool_workflow_binding_model_rejects_cross_tenant_pool() -> None:
    pool_tenant = Tenant.objects.create(slug=f"binding-pool-{uuid4().hex[:8]}", name="Pool Tenant")
    foreign_tenant = Tenant.objects.create(slug=f"binding-foreign-{uuid4().hex[:8]}", name="Foreign Tenant")
    pool = OrganizationPool.objects.create(
        tenant=pool_tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Cross Tenant Pool",
    )

    record = PoolWorkflowBinding(
        binding_id=str(uuid4()),
        tenant=foreign_tenant,
        pool=pool,
        status="active",
        effective_from="2026-01-01",
        direction="top_down",
        mode="safe",
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=1,
        workflow_name="services_publication",
    )

    with pytest.raises(ValidationError, match="same tenant"):
        record.full_clean()


@pytest.mark.django_db
def test_pool_workflow_binding_model_rejects_invalid_effective_range() -> None:
    tenant = Tenant.objects.create(slug=f"binding-range-{uuid4().hex[:8]}", name="Range Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Range Pool",
    )

    record = PoolWorkflowBinding(
        binding_id=str(uuid4()),
        tenant=tenant,
        pool=pool,
        status="active",
        effective_from="2026-02-01",
        effective_to="2026-01-01",
        direction="top_down",
        mode="safe",
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=1,
        workflow_name="services_publication",
    )

    with pytest.raises(ValidationError):
        record.full_clean()
