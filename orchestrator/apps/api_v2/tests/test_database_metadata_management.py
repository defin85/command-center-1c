from __future__ import annotations

import uuid

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.api_v2.tests import _execute_ibcmd_cli_support as support
from apps.databases.models import Database, PermissionLevel
from apps.intercompany_pools.models import (
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogSnapshotSource,
)
from apps.operations.models import BatchOperation

from ._execute_ibcmd_cli_support import client, target_dbs, user  # noqa: F401


def _grant_database_permission(client, user: User, codename: str) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))


def _set_business_configuration_profile(
    *,
    database: Database,
    config_name: str = "Бухгалтерия предприятия, редакция 3.0",
    root_name: str = "БухгалтерияПредприятия",
    config_version: str = "3.0.193.19",
    config_vendor: str = 'Фирма "1С"',
    config_generation_id: str = "1f53b85eba259b43bf2c696c614fc1d900000000",
    verification_status: str = "verified",
    verification_operation_id: str | None = None,
    observed_metadata_hash: str = "",
    canonical_metadata_hash: str = "",
    publication_drift: bool = False,
) -> None:
    metadata = dict(database.metadata or {})
    profile = {
        "config_name": config_name,
        "config_root_name": root_name,
        "config_version": config_version,
        "config_vendor": config_vendor,
        "config_generation_id": config_generation_id,
        "config_name_source": "synonym_ru",
        "verification_status": verification_status,
        "verified_at": "2026-03-12T00:00:00+00:00",
    }
    if verification_operation_id:
        profile["verification_operation_id"] = verification_operation_id
    if observed_metadata_hash:
        profile["observed_metadata_hash"] = observed_metadata_hash
    if canonical_metadata_hash:
        profile["canonical_metadata_hash"] = canonical_metadata_hash
    if publication_drift:
        profile["publication_drift"] = True
        profile["observed_metadata_fetched_at"] = "2026-03-12T01:00:00+00:00"
    metadata["business_configuration_profile"] = profile
    database.metadata = metadata
    database.save(update_fields=["metadata", "updated_at"])


def _create_current_metadata_catalog_snapshot(
    *,
    database: Database,
    metadata_hash: str = "a" * 64,
    provenance_database: Database | None = None,
) -> PoolODataMetadataCatalogSnapshot:
    profile = dict(database.metadata.get("business_configuration_profile") or {})
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant_id=database.tenant_id,
        database=provenance_database or database,
        config_name=str(profile.get("config_name") or ""),
        config_version=str(profile.get("config_version") or ""),
        extensions_fingerprint="",
        metadata_hash=metadata_hash,
        catalog_version=f"v1:{uuid.uuid4().hex[:16]}",
        payload={
            "documents": [
                {
                    "entity_name": "Document_Sales",
                    "display_name": "Sales",
                    "fields": [{"name": "Amount", "type": "Edm.Decimal", "nullable": False}],
                    "table_parts": [],
                }
            ]
        },
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        fetched_at=timezone.now(),
        is_current=True,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant_id=database.tenant_id,
        database=database,
        snapshot=snapshot,
        config_name=str(profile.get("config_name") or ""),
        config_version=str(profile.get("config_version") or ""),
        extensions_fingerprint="",
        confirmed_at=snapshot.fetched_at,
    )
    return snapshot


@pytest.mark.django_db
def test_get_database_metadata_management_returns_missing_state_without_hidden_bootstrap(client, user, target_dbs):
    db = target_dbs[0]
    _grant_database_permission(client, user, "view_database")
    support._allow_operate(user, db, level=PermissionLevel.VIEW)

    response = client.get("/api/v2/databases/get-metadata-management/", {"database_id": str(db.id)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_id"] == str(db.id)
    assert payload["configuration_profile"]["status"] == "missing"
    assert payload["metadata_snapshot"]["status"] == "missing"
    assert payload["metadata_snapshot"]["missing_reason"] == "configuration_profile_unavailable"
    assert PoolODataMetadataCatalogSnapshot.objects.count() == 0
    assert PoolODataMetadataCatalogScopeResolution.objects.count() == 0


@pytest.mark.django_db
def test_get_database_metadata_management_returns_profile_and_snapshot_state(client, user, target_dbs):
    db = target_dbs[0]
    _grant_database_permission(client, user, "view_database")
    support._allow_operate(user, db, level=PermissionLevel.VIEW)
    _set_business_configuration_profile(
        database=db,
        observed_metadata_hash="b" * 64,
        canonical_metadata_hash="a" * 64,
        publication_drift=True,
    )
    snapshot = _create_current_metadata_catalog_snapshot(database=db, metadata_hash="a" * 64)

    response = client.get("/api/v2/databases/get-metadata-management/", {"database_id": str(db.id)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["configuration_profile"]["status"] == "verified"
    assert payload["configuration_profile"]["config_name"] == "Бухгалтерия предприятия, редакция 3.0"
    assert payload["configuration_profile"]["config_version"] == "3.0.193.19"
    assert payload["configuration_profile"]["config_generation_id"] == "1f53b85eba259b43bf2c696c614fc1d900000000"
    assert payload["configuration_profile"]["publication_drift"] is True
    assert payload["configuration_profile"]["observed_metadata_hash"] == "b" * 64
    assert payload["configuration_profile"]["canonical_metadata_hash"] == "a" * 64
    assert payload["metadata_snapshot"]["status"] == "available"
    assert payload["metadata_snapshot"]["snapshot_id"] == str(snapshot.id)
    assert payload["metadata_snapshot"]["metadata_hash"] == "a" * 64
    assert payload["metadata_snapshot"]["resolution_mode"] == "database_scope"
    assert payload["metadata_snapshot"]["is_shared_snapshot"] is False
    assert payload["metadata_snapshot"]["provenance_database_id"] == str(db.id)


@pytest.mark.django_db
def test_get_database_metadata_management_marks_verification_pending_from_active_operation(client, user, target_dbs):
    db = target_dbs[0]
    _grant_database_permission(client, user, "view_database")
    support._allow_operate(user, db, level=PermissionLevel.VIEW)
    operation = BatchOperation.objects.create(
        name="business_configuration_profile verification",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_QUEUED,
        payload={},
        config={},
        total_tasks=1,
        created_by="tester",
        metadata={
            "business_configuration_job_kind": "verification",
            "snapshot_kinds": ["business_configuration_profile"],
        },
    )
    operation.target_databases.set([db])
    _set_business_configuration_profile(
        database=db,
        verification_status="reverify_required",
        verification_operation_id=str(operation.id),
    )

    response = client.get("/api/v2/databases/get-metadata-management/", {"database_id": str(db.id)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["configuration_profile"]["status"] == "verification_pending"
    assert payload["configuration_profile"]["verification_operation_id"] == str(operation.id)
    assert payload["metadata_snapshot"]["status"] == "missing"
    assert payload["metadata_snapshot"]["missing_reason"] == "current_snapshot_missing"


@pytest.mark.django_db
def test_reverify_configuration_profile_requires_operate_permission(client, user, target_dbs):
    db = target_dbs[0]
    _grant_database_permission(client, user, "operate_database")
    support._allow_operate(user, db, level=PermissionLevel.VIEW)

    response = client.post(
        "/api/v2/databases/reverify-configuration-profile/",
        {"database_id": str(db.id)},
        format="json",
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_reverify_configuration_profile_queues_operation(client, user, target_dbs, monkeypatch):
    db = target_dbs[0]
    _grant_database_permission(client, user, "operate_database")
    support._allow_operate(user, db, level=PermissionLevel.OPERATE)

    operation = BatchOperation.objects.create(
        name="business_configuration_profile verification",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_QUEUED,
        payload={},
        config={},
        total_tasks=1,
        created_by="tester",
        metadata={
            "business_configuration_job_kind": "verification",
            "snapshot_kinds": ["business_configuration_profile"],
        },
    )
    operation.target_databases.set([db])

    def _fake_enqueue(*, database: Database, reason: str, triggered_by_operation_id: str | None = None):
        assert database.id == db.id
        assert reason == "manual_database_metadata_management"
        assert triggered_by_operation_id is None
        return operation

    monkeypatch.setattr(
        "apps.api_v2.views.databases.metadata_management.enqueue_business_configuration_verification",
        _fake_enqueue,
    )

    response = client.post(
        "/api/v2/databases/reverify-configuration-profile/",
        {"database_id": str(db.id)},
        format="json",
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["database_id"] == str(db.id)
    assert payload["status"] == "queued"
    assert payload["operation_id"] == str(operation.id)


@pytest.mark.django_db
def test_refresh_metadata_snapshot_returns_updated_state(client, user, target_dbs, monkeypatch):
    db = target_dbs[0]
    _grant_database_permission(client, user, "operate_database")
    support._allow_operate(user, db, level=PermissionLevel.OPERATE)
    _set_business_configuration_profile(database=db)
    refreshed_snapshot = _create_current_metadata_catalog_snapshot(database=db, metadata_hash="c" * 64)

    def _fake_refresh(*, tenant_id: str, database: Database, requested_by_username: str, source: str = "live_refresh"):
        assert tenant_id == str(db.tenant_id)
        assert database.id == db.id
        assert requested_by_username == user.username
        assert source == "live_refresh"
        return refreshed_snapshot

    monkeypatch.setattr(
        "apps.api_v2.views.databases.metadata_management.refresh_metadata_catalog_snapshot",
        _fake_refresh,
    )

    response = client.post(
        "/api/v2/databases/refresh-metadata-snapshot/",
        {"database_id": str(db.id)},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_id"] == str(db.id)
    assert payload["metadata_snapshot"]["status"] == "available"
    assert payload["metadata_snapshot"]["snapshot_id"] == str(refreshed_snapshot.id)
    assert payload["metadata_snapshot"]["metadata_hash"] == "c" * 64
