from __future__ import annotations

import json
import uuid
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.metadata_catalog import refresh_metadata_catalog_snapshot
from apps.intercompany_pools.models import (
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshotSource,
)
from apps.tenancy.models import Tenant
from apps.templates.workflow.models import DecisionTable


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


def _set_business_configuration_profile(
    *,
    database: Database,
    config_name: str = "Бухгалтерия предприятия, редакция 3.0",
    root_name: str = "БухгалтерияПредприятия",
    config_version: str = "3.0.193.19",
    config_vendor: str = 'Фирма "1С"',
    config_generation_id: str = "1f53b85eba259b43bf2c696c614fc1d900000000",
) -> None:
    metadata = dict(database.metadata or {})
    metadata["business_configuration_profile"] = {
        "config_name": config_name,
        "config_root_name": root_name,
        "config_version": config_version,
        "config_vendor": config_vendor,
        "config_generation_id": config_generation_id,
        "config_name_source": "synonym_ru",
        "verification_status": "verified",
        "verified_at": "2026-03-12T00:00:00+00:00",
    }
    database.metadata = metadata
    database.save(update_fields=["metadata", "updated_at"])


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
    catalog_version: str | None = None,
    snapshot_config_name: str | None = None,
    snapshot_config_version: str | None = None,
    resolution_config_name: str | None = None,
    resolution_config_version: str | None = None,
) -> PoolODataMetadataCatalogSnapshot:
    profile = dict(database.metadata.get("business_configuration_profile") or {})
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=tenant,
        database=database,
        config_name=str(snapshot_config_name or profile.get("config_name") or ""),
        config_version=str(snapshot_config_version or profile.get("config_version") or ""),
        extensions_fingerprint="",
        metadata_hash=metadata_hash,
        catalog_version=str(catalog_version or f"v1:{uuid.uuid4().hex[:16]}"),
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
        config_name=str(resolution_config_name or profile.get("config_name") or ""),
        config_version=str(resolution_config_version or profile.get("config_version") or ""),
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
    monkeypatch: pytest.MonkeyPatch,
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
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)
    _set_business_configuration_profile(database=first_database)
    _set_business_configuration_profile(database=second_database)
    shared_payload = {
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
    }
    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        lambda **_: shared_payload,
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)
    snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(tenant.id),
        database=first_database,
        requested_by_username=str(getattr(staff_client.handler._force_user, "username", "") or ""),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

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
    assert payload["metadata_context"]["source"] == "db"
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
    _set_business_configuration_profile(database=database)
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
def test_decision_tables_api_reports_diverged_metadata_surface_as_warning_while_remaining_compatible(
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
    _set_business_configuration_profile(database=first_database)
    _set_business_configuration_profile(database=second_database)
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
    assert compatibility["is_compatible"] is True
    assert compatibility["status"] == "compatible"
    assert compatibility["reason"] == "metadata_surface_diverged"


@pytest.mark.django_db
def test_decision_detail_backfills_legacy_metadata_context_from_business_profile(
    staff_client: APIClient,
) -> None:
    tenant = Tenant.objects.create(slug=f"decision-meta-legacy-{uuid.uuid4().hex[:8]}", name="Decision Meta Legacy")
    database = _create_database(
        tenant=tenant,
        name=f"decision-legacy-db-{uuid.uuid4().hex[:8]}",
        base_name="legacy-infobase-name",
        version="8.3.24",
    )
    _set_business_configuration_profile(
        database=database,
        config_name="Бухгалтерия предприятия, редакция 3.0",
        config_version="3.0.193.19",
    )
    legacy_snapshot = _create_current_metadata_catalog_snapshot(
        tenant=tenant,
        database=database,
        snapshot_config_name=database.base_name,
        snapshot_config_version=database.version,
        resolution_config_name=database.base_name,
        resolution_config_version=database.version,
    )
    decision = DecisionTable.objects.create(
        decision_table_id=f"legacy-policy-{uuid.uuid4().hex[:8]}",
        decision_key="document_policy",
        name="Legacy Policy",
        outputs=[{"name": "document_policy", "value_type": "json", "required": True}],
        rules=[
            {
                "rule_id": "default",
                "priority": 0,
                "conditions": {},
                "outputs": {"document_policy": {"version": "document_policy.v1", "chains": []}},
            }
        ],
        metadata_context={
            "database_id": str(database.id),
            "snapshot_id": str(legacy_snapshot.id),
            "config_name": database.base_name,
            "config_version": database.version,
            "metadata_hash": legacy_snapshot.metadata_hash,
            "extensions_fingerprint": "",
        },
        source_provenance={
            "kind": "legacy_edge_document_policy",
            "child_database_id": str(database.id),
        },
        version_number=1,
    )

    response = staff_client.get(f"/api/v2/decisions/{decision.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["metadata_context"]["snapshot_id"] == str(legacy_snapshot.id)
    assert payload["decision"]["metadata_context"]["config_name"] == "Бухгалтерия предприятия, редакция 3.0"
    assert payload["decision"]["metadata_context"]["config_version"] == "3.0.193.19"

    decision.refresh_from_db()
    assert decision.metadata_context["snapshot_id"] == str(legacy_snapshot.id)
    assert decision.metadata_context["config_name"] == "Бухгалтерия предприятия, редакция 3.0"
    assert decision.metadata_context["config_version"] == "3.0.193.19"


@pytest.mark.django_db
def test_business_identity_backfill_command_upgrades_legacy_scope_and_decision_contexts(
    staff_client: APIClient,
) -> None:
    tenant = Tenant.objects.create(slug=f"decision-backfill-{uuid.uuid4().hex[:8]}", name="Decision Backfill")
    first_database = _create_database(
        tenant=tenant,
        name=f"decision-backfill-a-{uuid.uuid4().hex[:8]}",
        base_name="legacy-infobase-a",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=tenant,
        name=f"decision-backfill-b-{uuid.uuid4().hex[:8]}",
        base_name="legacy-infobase-b",
        version="8.3.24",
    )
    for database in (first_database, second_database):
        _create_service_infobase_mapping(database=database)
        _set_business_configuration_profile(
            database=database,
            config_name="Бухгалтерия предприятия, редакция 3.0",
            config_version="3.0.193.19",
        )

    shared_catalog_version = f"legacy-catalog:{uuid.uuid4().hex[:12]}"
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
    first_snapshot = _create_current_metadata_catalog_snapshot(
        tenant=tenant,
        database=first_database,
        payload=shared_payload,
        metadata_hash="c" * 64,
        catalog_version=shared_catalog_version,
        snapshot_config_name=first_database.base_name,
        snapshot_config_version=first_database.version,
        resolution_config_name=first_database.base_name,
        resolution_config_version=first_database.version,
    )
    _create_current_metadata_catalog_snapshot(
        tenant=tenant,
        database=second_database,
        payload=shared_payload,
        metadata_hash="c" * 64,
        catalog_version=shared_catalog_version,
        snapshot_config_name=second_database.base_name,
        snapshot_config_version=second_database.version,
        resolution_config_name=second_database.base_name,
        resolution_config_version=second_database.version,
    )

    decision = DecisionTable.objects.create(
        decision_table_id=f"legacy-shared-policy-{uuid.uuid4().hex[:8]}",
        decision_key="document_policy",
        name="Legacy Shared Policy",
        outputs=[{"name": "document_policy", "value_type": "json", "required": True}],
        rules=[
            {
                "rule_id": "default",
                "priority": 0,
                "conditions": {},
                "outputs": {"document_policy": {"version": "document_policy.v1", "chains": []}},
            }
        ],
        metadata_context={
            "database_id": str(first_database.id),
            "snapshot_id": str(first_snapshot.id),
            "config_name": first_database.base_name,
            "config_version": first_database.version,
            "metadata_hash": first_snapshot.metadata_hash,
            "extensions_fingerprint": "",
        },
        source_provenance={
            "kind": "legacy_edge_document_policy",
            "child_database_id": str(first_database.id),
        },
        version_number=1,
    )

    out = StringIO()
    call_command(
        "backfill_business_identity_state",
        "--tenant-id",
        str(tenant.id),
        "--json",
        stdout=out,
    )
    command_payload = json.loads(out.getvalue())

    assert command_payload["databases_scanned"] == 2
    assert command_payload["scope_backfilled"] == 2
    assert command_payload["scope_unresolved"] == []
    assert command_payload["decisions_scanned"] == 1
    assert command_payload["decision_contexts_backfilled"] == 1
    assert command_payload["decision_context_unresolved"] == []

    canonical_snapshots = list(
        PoolODataMetadataCatalogSnapshot.objects.filter(
            tenant=tenant,
            config_name="Бухгалтерия предприятия, редакция 3.0",
            config_version="3.0.193.19",
            catalog_version=shared_catalog_version,
        )
    )
    assert len(canonical_snapshots) == 1
    canonical_snapshot = canonical_snapshots[0]

    resolutions = list(
        PoolODataMetadataCatalogScopeResolution.objects.filter(
            tenant=tenant,
            config_name="Бухгалтерия предприятия, редакция 3.0",
            config_version="3.0.193.19",
        ).order_by("database_id")
    )
    assert [str(item.database_id) for item in resolutions] == [str(first_database.id), str(second_database.id)]
    assert {str(item.snapshot_id) for item in resolutions} == {str(canonical_snapshot.id)}

    decision.refresh_from_db()
    assert decision.metadata_context["snapshot_id"] == str(canonical_snapshot.id)
    assert decision.metadata_context["config_name"] == "Бухгалтерия предприятия, редакция 3.0"
    assert decision.metadata_context["config_version"] == "3.0.193.19"

    detail_response = staff_client.get(
        f"/api/v2/decisions/{decision.id}/?database_id={second_database.id}",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["decision"]["metadata_context"]["snapshot_id"] == str(canonical_snapshot.id)
    assert detail_payload["decision"]["metadata_compatibility"]["is_compatible"] is True


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
    _set_business_configuration_profile(database=database)
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
