from __future__ import annotations

import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.models import (
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshotSource,
)
from apps.tenancy.models import Tenant


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(
        username=f"decision_staff_{uuid.uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


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


def _create_service_infobase_mapping(*, database: Database) -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="svc-user",
        ib_password="svc-pass",
        is_service=True,
    )


def _create_current_metadata_catalog_snapshot(
    *,
    tenant: Tenant,
    database: Database,
    payload: dict[str, object] | None = None,
    metadata_hash: str = "a" * 64,
) -> PoolODataMetadataCatalogSnapshot:
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=tenant,
        database=database,
        config_name=str(database.base_name or database.name or database.id),
        config_version=str(database.version or ""),
        extensions_fingerprint="",
        metadata_hash=metadata_hash,
        catalog_version=f"v1:{uuid.uuid4().hex[:16]}",
        payload=payload
        or {
            "documents": [
                {
                    "entity_name": "Document_Sales",
                    "display_name": "Sales",
                    "fields": [
                        {"name": "Amount", "type": "Edm.Decimal", "nullable": False},
                    ],
                    "table_parts": [],
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
        },
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant=tenant,
        database=database,
        snapshot=snapshot,
        config_name=str(database.base_name or database.name or database.id),
        config_version=str(database.version or ""),
        extensions_fingerprint="",
        confirmed_at=snapshot.fetched_at,
    )
    return snapshot


def _build_decision_payload(
    *,
    decision_table_id: str | None = None,
    decision_key: str = "document_policy",
) -> dict[str, object]:
    if decision_key != "document_policy":
        return {
            "decision_table_id": decision_table_id or f"decision-{uuid.uuid4().hex[:8]}",
            "decision_key": decision_key,
            "name": "Generic Decision",
            "inputs": [
                {"name": "direction", "value_type": "string", "required": True},
            ],
            "outputs": [
                {"name": decision_key, "value_type": "string", "required": True},
            ],
            "rules": [
                {
                    "rule_id": "default",
                    "priority": 0,
                    "conditions": {"direction": "bottom_up"},
                    "outputs": {decision_key: "route-a"},
                }
            ],
        }
    return {
        "decision_table_id": decision_table_id or f"decision-{uuid.uuid4().hex[:8]}",
        "decision_key": decision_key,
        "name": "Document Policy Decision",
        "inputs": [
            {"name": "direction", "value_type": "string", "required": True},
            {"name": "mode", "value_type": "string", "required": True},
        ],
        "outputs": [
            {"name": "document_policy", "value_type": "json", "required": True},
        ],
        "rules": [
            {
                "rule_id": "bottom-up-safe",
                "priority": 0,
                "conditions": {
                    "direction": "bottom_up",
                    "mode": "safe",
                },
                "outputs": {
                    "document_policy": {
                        "version": "document_policy.v1",
                        "chains": [
                            {
                                "chain_id": "sale_chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
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
                },
            }
        ],
    }


@pytest.mark.django_db
def test_decision_tables_api_create_list_and_detail_round_trip(staff_client: APIClient) -> None:
    create_response = staff_client.post(
        "/api/v2/decisions/",
        data=_build_decision_payload(decision_key="route_policy"),
        format="json",
    )

    assert create_response.status_code == 201
    created = create_response.json()["decision"]
    assert created["decision_revision"] == 1
    assert created["decision_key"] == "route_policy"
    assert created["outputs"][0]["name"] == "route_policy"
    assert created["metadata_context"] is None
    assert created["metadata_compatibility"] is None

    list_response = staff_client.get("/api/v2/decisions/")
    assert list_response.status_code == 200
    listed = list_response.json()["decisions"]
    assert any(item["id"] == created["id"] for item in listed)

    detail_response = staff_client.get(f"/api/v2/decisions/{created['id']}/")
    assert detail_response.status_code == 200
    detailed = detail_response.json()["decision"]
    assert detailed["id"] == created["id"]
    assert detailed["decision_table_id"] == created["decision_table_id"]
    assert detailed["rules"][0]["outputs"]["route_policy"] == "route-a"


@pytest.mark.django_db
def test_decision_tables_api_can_create_new_revision_from_parent(staff_client: APIClient) -> None:
    first_response = staff_client.post(
        "/api/v2/decisions/",
        data=_build_decision_payload(
            decision_table_id="services-publication-policy",
            decision_key="route_policy",
        ),
        format="json",
    )
    assert first_response.status_code == 201
    first = first_response.json()["decision"]

    second_response = staff_client.post(
        "/api/v2/decisions/",
        data={
            **_build_decision_payload(
                decision_table_id="services-publication-policy",
                decision_key="route_policy",
            ),
            "parent_version_id": first["id"],
            "name": "Document Policy Decision v2",
        },
        format="json",
    )

    assert second_response.status_code == 201
    second = second_response.json()["decision"]
    assert second["decision_table_id"] == first["decision_table_id"]
    assert second["decision_revision"] == 2
    assert second["parent_version"] == first["id"]


@pytest.mark.django_db
def test_decision_tables_api_create_uses_shared_metadata_snapshot_context(
    staff_client: APIClient,
) -> None:
    tenant = Tenant.objects.create(slug=f"decision-meta-{uuid.uuid4().hex[:8]}", name="Decision Meta")
    first_database = _create_database(
        tenant=tenant,
        name=f"decision-db-a-{uuid.uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=tenant,
        name=f"decision-db-b-{uuid.uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=second_database)
    snapshot = _create_current_metadata_catalog_snapshot(tenant=tenant, database=first_database)

    response = staff_client.post(
        "/api/v2/decisions/",
        data={
            **_build_decision_payload(),
            "database_id": str(second_database.id),
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["decision"]["decision_key"] == "document_policy"
    assert payload["decision"]["metadata_context"]["snapshot_id"] == str(snapshot.id)
    assert payload["decision"]["metadata_context"]["metadata_hash"] == snapshot.metadata_hash
    assert payload["decision"]["metadata_compatibility"]["is_compatible"] is True
    assert payload["metadata_context"]["database_id"] == str(second_database.id)
    assert payload["metadata_context"]["snapshot_id"] == str(snapshot.id)
    assert payload["metadata_context"]["resolution_mode"] == "shared_scope"
    assert payload["metadata_context"]["is_shared_snapshot"] is True
    assert payload["metadata_context"]["provenance_database_id"] == str(first_database.id)


@pytest.mark.django_db
def test_decision_tables_api_rejects_invalid_document_policy_metadata_refs(
    staff_client: APIClient,
) -> None:
    tenant = Tenant.objects.create(slug=f"decision-meta-invalid-{uuid.uuid4().hex[:8]}", name="Decision Meta Invalid")
    database = _create_database(
        tenant=tenant,
        name=f"decision-invalid-db-{uuid.uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=database)
    _create_current_metadata_catalog_snapshot(tenant=tenant, database=database)

    invalid_payload = _build_decision_payload()
    invalid_payload["rules"][0]["outputs"]["document_policy"]["chains"][0]["documents"][0]["field_mapping"] = {
        "UnknownField": "allocation.amount"
    }

    response = staff_client.post(
        "/api/v2/decisions/",
        data={
            **invalid_payload,
            "database_id": str(database.id),
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "POOL_METADATA_REFERENCE_INVALID"


@pytest.mark.django_db
def test_decision_tables_api_rejects_document_policy_create_without_database_context(
    staff_client: APIClient,
) -> None:
    response = staff_client.post(
        "/api/v2/decisions/",
        data=_build_decision_payload(),
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "POOL_METADATA_CONTEXT_REQUIRED"


@pytest.mark.django_db
def test_decision_tables_api_reports_diverged_metadata_surface_as_incompatible(
    staff_client: APIClient,
) -> None:
    tenant = Tenant.objects.create(slug=f"decision-meta-diverged-{uuid.uuid4().hex[:8]}", name="Decision Meta Diverged")
    first_database = _create_database(
        tenant=tenant,
        name=f"decision-diverged-a-{uuid.uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=tenant,
        name=f"decision-diverged-b-{uuid.uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)
    created_snapshot = _create_current_metadata_catalog_snapshot(
        tenant=tenant,
        database=first_database,
        metadata_hash="a" * 64,
    )
    _create_current_metadata_catalog_snapshot(
        tenant=tenant,
        database=second_database,
        payload={
            "documents": [
                {
                    "entity_name": "Document_Transfer",
                    "display_name": "Transfer",
                    "fields": [
                        {"name": "TransferAmount", "type": "Edm.Decimal", "nullable": False},
                    ],
                    "table_parts": [],
                }
            ]
        },
        metadata_hash="b" * 64,
    )

    create_response = staff_client.post(
        "/api/v2/decisions/",
        data={
            **_build_decision_payload(decision_table_id="shared-policy"),
            "database_id": str(first_database.id),
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert create_response.status_code == 201
    created = create_response.json()["decision"]
    assert created["metadata_context"]["snapshot_id"] == str(created_snapshot.id)

    detail_response = staff_client.get(
        f"/api/v2/decisions/{created['id']}/?database_id={second_database.id}",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    compatibility = detail_payload["decision"]["metadata_compatibility"]
    assert compatibility["is_compatible"] is False
    assert compatibility["status"] == "incompatible"
    assert compatibility["reason"] == "metadata_surface_diverged"


@pytest.mark.django_db
def test_decision_tables_api_list_returns_metadata_context_for_builder(
    staff_client: APIClient,
) -> None:
    tenant = Tenant.objects.create(slug=f"decision-meta-list-{uuid.uuid4().hex[:8]}", name="Decision Meta List")
    database = _create_database(
        tenant=tenant,
        name=f"decision-list-db-{uuid.uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=database)
    snapshot = _create_current_metadata_catalog_snapshot(tenant=tenant, database=database)

    response = staff_client.get(
        f"/api/v2/decisions/?database_id={database.id}",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata_context"]["database_id"] == str(database.id)
    assert payload["metadata_context"]["snapshot_id"] == str(snapshot.id)
    assert payload["metadata_context"]["resolution_mode"] == "database_scope"
