from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.apps import apps as django_apps
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.databases.models import Database, DatabaseExtensionsSnapshot, InfobaseUserMapping
from apps.api_v2.tests import _execute_ibcmd_cli_support as support
from apps.intercompany_pools.business_identity_backfill import (
    backfill_database_business_identity_scope,
)
from apps.intercompany_pools.metadata_catalog import (
    ERROR_CODE_POOL_METADATA_FETCH_FAILED,
    ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE,
    ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS,
    ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
    describe_metadata_catalog_snapshot_resolution,
    MetadataCatalogError,
    _read_snapshot_from_cache,
    _fetch_live_catalog_payload,
    _resolve_metadata_mapping_credentials,
    read_metadata_catalog_snapshot,
    refresh_metadata_catalog_snapshot,
    resolve_metadata_catalog_scope,
    validate_document_policy_references,
)
from apps.intercompany_pools.business_configuration_profile import (
    load_configuration_xml_from_artifact_path,
    parse_business_configuration_profile_xml,
)
from apps.operations.models import BatchOperation
from apps.operations.services.operations_service import OperationsService
from apps.operations.services.operations_service.types import EnqueueResult
from apps.intercompany_pools.models import (
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshotSource,
)
from apps.tenancy.models import Tenant, TenantMember


def _create_database(
    *,
    tenant: Tenant,
    name: str,
    base_name: str | None = None,
    version: str = "3.0.193.19",
) -> Database:
    database = Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        base_name=base_name or name,
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
        version=version,
    )
    metadata = dict(database.metadata or {})
    metadata["business_configuration_profile"] = {
        "config_name": str(base_name or name),
        "config_root_name": str(base_name or name),
        "config_version": str(version or ""),
        "config_vendor": 'Фирма "1С"',
        "config_generation_id": "seed-generation-id",
        "config_name_source": "seed_fixture",
        "verification_status": "verified",
        "verified_at": "2026-03-12T00:00:00+00:00",
    }
    database.metadata = metadata
    database.save(update_fields=["metadata", "updated_at"])
    return database


def _catalog_payload(*, suffix: str) -> dict[str, object]:
    return {
        "documents": [
            {
                "entity_name": f"Document_Sales_{suffix}",
                "display_name": f"Document Sales {suffix}",
                "fields": [
                    {"name": "Amount", "type": "Edm.Decimal", "nullable": False},
                ],
                "table_parts": [],
            }
        ]
    }


def _create_service_infobase_mapping(*, database: Database, username: str = "svc-user", password: str = "svc-pass") -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=username,
        ib_password=password,
        is_service=True,
    )


def _seed_ibcmd_business_configuration_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "driver_schema": {},
        "commands_by_id": {
            "infobase.config.export.objects": {
                "label": "config export objects",
                "description": "Export selected config objects",
                "argv": ["infobase", "config", "export", "objects"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {
                    "arg1": {
                        "kind": "positional",
                        "position": 1,
                        "required": False,
                        "expects_value": True,
                        "label": "Object1 ... ObjectN",
                    },
                    "archive": {
                        "kind": "flag",
                        "flag": "--archive",
                        "required": False,
                        "expects_value": False,
                        "label": "--archive",
                    },
                    "out": {
                        "kind": "flag",
                        "flag": "--out",
                        "required": False,
                        "expects_value": True,
                        "label": "--out",
                    },
                },
            },
        },
    }
    support._seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"meta-user-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.mark.django_db
def test_refresh_snapshot_switches_current_version_atomically(default_tenant: Tenant, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-db-{uuid4().hex[:8]}")
    payloads = [_catalog_payload(suffix="v1"), _catalog_payload(suffix="v2")]

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        lambda **_: payloads.pop(0),
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)

    first = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )
    second = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

    assert first.id != second.id
    current_snapshots = PoolODataMetadataCatalogSnapshot.objects.filter(
        tenant=default_tenant,
        database=database,
        is_current=True,
    )
    assert current_snapshots.count() == 1
    assert current_snapshots.get().id == second.id
    assert PoolODataMetadataCatalogSnapshot.objects.filter(
        tenant=default_tenant,
        database=database,
        is_current=False,
    ).count() == 1


def test_parse_business_configuration_profile_xml_prefers_ru_synonym() -> None:
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
  <Configuration>
    <Properties>
      <Name>AccountingEnterprise</Name>
      <Synonym>
        <v8:item>
          <v8:lang>en</v8:lang>
          <v8:content>Accounting Enterprise</v8:content>
        </v8:item>
        <v8:item>
          <v8:lang>ru</v8:lang>
          <v8:content>Бухгалтерия предприятия, редакция 3.0</v8:content>
        </v8:item>
      </Synonym>
      <Vendor>Фирма "1С"</Vendor>
      <Version>3.0.193.19</Version>
    </Properties>
  </Configuration>
</MetaDataObject>
"""

    profile = parse_business_configuration_profile_xml(xml_payload)

    assert profile["config_name"] == "Бухгалтерия предприятия, редакция 3.0"
    assert profile["config_root_name"] == "AccountingEnterprise"
    assert profile["config_name_source"] == "synonym_ru"
    assert profile["config_vendor"] == 'Фирма "1С"'
    assert profile["config_version"] == "3.0.193.19"


def test_parse_business_configuration_profile_xml_falls_back_to_first_synonym() -> None:
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
  <Configuration>
    <Properties>
      <Name>AccountingEnterprise</Name>
      <Synonym>
        <v8:item>
          <v8:lang>en</v8:lang>
          <v8:content>Accounting Enterprise</v8:content>
        </v8:item>
        <v8:item>
          <v8:lang>de</v8:lang>
          <v8:content>Buchhaltung</v8:content>
        </v8:item>
      </Synonym>
      <Vendor>Vendor</Vendor>
      <Version>3.0.193.19</Version>
    </Properties>
  </Configuration>
</MetaDataObject>
"""

    profile = parse_business_configuration_profile_xml(xml_payload)

    assert profile["config_name"] == "Accounting Enterprise"
    assert profile["config_root_name"] == "AccountingEnterprise"
    assert profile["config_name_source"] == "synonym_any"
    assert profile["config_version"] == "3.0.193.19"


def test_parse_business_configuration_profile_xml_falls_back_to_root_name_when_synonym_missing() -> None:
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration>
    <Properties>
      <Name>AccountingEnterprise</Name>
      <Vendor>Vendor</Vendor>
      <Version>3.0.193.19</Version>
    </Properties>
  </Configuration>
</MetaDataObject>
"""

    profile = parse_business_configuration_profile_xml(xml_payload)

    assert profile["config_name"] == "AccountingEnterprise"
    assert profile["config_root_name"] == "AccountingEnterprise"
    assert profile["config_name_source"] == "name"
    assert profile["config_version"] == "3.0.193.19"


def test_load_configuration_xml_from_archive_artifact(tmp_path) -> None:
    import zipfile

    archive_path = tmp_path / "Configuration.zip"
    configuration_xml = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration>
    <Properties>
      <Name>AccountingEnterprise</Name>
      <Version>3.0.193.19</Version>
    </Properties>
  </Configuration>
</MetaDataObject>
"""
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("Configuration.xml", configuration_xml)

    resolved = load_configuration_xml_from_artifact_path(str(archive_path))

    assert "AccountingEnterprise" in resolved
    assert "3.0.193.19" in resolved


@pytest.mark.django_db
def test_read_snapshot_enqueues_business_profile_bootstrap_when_profile_is_missing(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_ibcmd_business_configuration_catalog(monkeypatch)
    database = Database.objects.create(
        tenant=default_tenant,
        name=f"meta-profile-missing-{uuid4().hex[:8]}",
        host="localhost",
        base_name="legacy-name",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )
    database.metadata = {
        "ibcmd_connection": {
            "remote": "ssh://agent:1545",
        }
    }
    database.save(update_fields=["metadata", "updated_at"])

    def _fake_enqueue(op_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=op_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=op_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", _fake_enqueue)

    with pytest.raises(MetadataCatalogError) as exc_info:
        read_metadata_catalog_snapshot(
            tenant_id=str(default_tenant.id),
            database=database,
            requested_by_username="meta-user",
            allow_cold_bootstrap=False,
        )

    assert exc_info.value.code == ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE
    operation = BatchOperation.objects.get()
    assert operation.status == BatchOperation.STATUS_QUEUED
    assert (operation.metadata or {}).get("command_id") == "infobase.config.export.objects"
    assert (operation.metadata or {}).get("business_configuration_job_kind") == "verification"


@pytest.mark.django_db
def test_read_snapshot_reuses_shared_snapshot_by_business_identity_without_database_confirmation(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-shared-db-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-shared-db-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        lambda **_: _catalog_payload(suffix="shared"),
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)

    refreshed = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

    resolved, source = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    assert refreshed.id is not None
    assert source == "db"
    assert resolved.id == refreshed.id
    resolution = PoolODataMetadataCatalogScopeResolution.objects.get(
        tenant=default_tenant,
        database=second_database,
    )
    assert resolution.snapshot_id == refreshed.id
    assert (
        PoolODataMetadataCatalogSnapshot.objects.filter(
            tenant=default_tenant,
            config_name="shared-profile",
            config_version="8.3.24",
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_read_snapshot_reuses_existing_shared_snapshot_without_second_live_fetch(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-shared-db-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-shared-db-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)

    fetch_calls: list[str] = []

    def _fetch_payload(*, database: Database, **_: object) -> dict[str, object]:
        fetch_calls.append(str(database.id))
        return _catalog_payload(suffix="shared")

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        _fetch_payload,
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)

    refreshed = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

    resolved, source = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=True,
    )

    assert source == "db"
    assert resolved.id == refreshed.id
    assert fetch_calls == [str(first_database.id)]
    resolution = PoolODataMetadataCatalogScopeResolution.objects.get(
        tenant=default_tenant,
        database=second_database,
    )
    assert resolution.snapshot_id == refreshed.id


@pytest.mark.django_db
def test_refresh_snapshot_updates_canonical_extensions_fingerprint_when_second_database_confirms_same_snapshot(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-shared-refresh-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-shared-refresh-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)
    DatabaseExtensionsSnapshot.objects.create(
        database=first_database,
        snapshot={"extensions": [{"name": "CoreA", "version": "1.0.0"}]},
    )
    DatabaseExtensionsSnapshot.objects.create(
        database=second_database,
        snapshot={"extensions": [{"name": "CoreB", "version": "1.0.0"}]},
    )

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        lambda **_: _catalog_payload(suffix="shared"),
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)

    first_snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )
    second_snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

    assert second_snapshot.id == first_snapshot.id
    second_snapshot.refresh_from_db()
    expected_scope = resolve_metadata_catalog_scope(
        tenant_id=str(default_tenant.id),
        database=second_database,
    )
    assert str(second_snapshot.database_id) == str(second_database.id)
    assert second_snapshot.extensions_fingerprint == expected_scope.extensions_fingerprint


@pytest.mark.django_db
def test_refresh_snapshot_keeps_canonical_shared_snapshot_when_publication_drift_is_detected(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_name = "shared-profile-diverged"
    shared_version = "8.3.25"
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-diverged-db-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-diverged-db-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    third_database = _create_database(
        tenant=default_tenant,
        name=f"meta-diverged-db-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)
    _create_service_infobase_mapping(database=third_database)

    payload_by_database = {
        first_database.id: _catalog_payload(suffix="variant-a"),
        second_database.id: _catalog_payload(suffix="variant-b"),
        third_database.id: _catalog_payload(suffix="variant-a"),
    }

    def _fetch_payload(*, database: Database, **_: object) -> dict[str, object]:
        return payload_by_database[database.id]

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        _fetch_payload,
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)

    first_snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )
    second_snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )
    third_snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=third_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

    assert first_snapshot.id == second_snapshot.id
    assert third_snapshot.id == first_snapshot.id

    resolved_first, source_first = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )
    resolved_second, source_second = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    assert source_first == "db"
    assert source_second == "db"
    assert resolved_first.id == first_snapshot.id
    assert resolved_second.id == first_snapshot.id


@pytest.mark.django_db
def test_refresh_snapshot_keeps_single_current_shared_snapshot_when_provenance_database_drifts(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_name = "shared-profile-provenance-drift"
    shared_version = "8.3.27"
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-provenance-drift-a-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-provenance-drift-b-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    third_database = _create_database(
        tenant=default_tenant,
        name=f"meta-provenance-drift-c-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    for database in (first_database, second_database, third_database):
        _create_service_infobase_mapping(database=database)

    payload_by_database = {
        first_database.id: _catalog_payload(suffix="canonical-a"),
        second_database.id: _catalog_payload(suffix="canonical-a"),
        third_database.id: _catalog_payload(suffix="canonical-a"),
    }
    fetch_calls: list[str] = []

    def _fetch_payload(*, database: Database, **_: object) -> dict[str, object]:
        fetch_calls.append(str(database.id))
        return payload_by_database[database.id]

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        _fetch_payload,
    )
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)

    first_snapshot = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )
    adopted_second, source_second = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    assert source_second == "db"
    assert adopted_second.id == first_snapshot.id

    payload_by_database[first_database.id] = _catalog_payload(suffix="drifted-b")

    drifted_refresh = refresh_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
    )

    resolved_third, source_third = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=third_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    first_database.refresh_from_db()
    profile = (first_database.metadata or {}).get("business_configuration_profile") or {}
    current_snapshots = PoolODataMetadataCatalogSnapshot.objects.filter(
        tenant=default_tenant,
        config_name=shared_name,
        config_version=shared_version,
        is_current=True,
    )

    assert drifted_refresh.id == first_snapshot.id
    assert source_third == "db"
    assert resolved_third.id == first_snapshot.id
    assert current_snapshots.count() == 1
    assert current_snapshots.get().id == first_snapshot.id
    assert (
        PoolODataMetadataCatalogScopeResolution.objects.filter(
            tenant=default_tenant,
            config_name=shared_name,
            config_version=shared_version,
            snapshot_id=first_snapshot.id,
        ).count()
        == 3
    )
    assert profile["publication_drift"] is True
    assert profile["canonical_metadata_hash"] == first_snapshot.metadata_hash
    assert profile["observed_metadata_hash"] != first_snapshot.metadata_hash
    assert fetch_calls == [
        str(first_database.id),
        str(first_database.id),
    ]


@pytest.mark.django_db
def test_migration_backfills_legacy_database_current_snapshots_into_scope_resolution_registry(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_name = "shared-profile-backfill"
    shared_version = "8.3.26"
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-backfill-db-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-backfill-db-{uuid4().hex[:8]}",
        base_name=shared_name,
        version=shared_version,
    )
    _create_service_infobase_mapping(database=first_database)
    _create_service_infobase_mapping(database=second_database)

    first_snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=first_database,
        config_name=shared_name,
        config_version=shared_version,
        extensions_fingerprint="",
        metadata_hash="a" * 64,
        catalog_version=f"v1:{uuid4().hex[:16]}",
        payload=_catalog_payload(suffix="backfill-a"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    second_snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=second_database,
        config_name=shared_name,
        config_version=shared_version,
        extensions_fingerprint="",
        metadata_hash="b" * 64,
        catalog_version=f"v1:{uuid4().hex[:16]}",
        payload=_catalog_payload(suffix="backfill-b"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    assert PoolODataMetadataCatalogScopeResolution.objects.count() == 0

    migration = importlib.import_module(
        "apps.intercompany_pools.migrations.0024_poolodatametadatacatalogscoperesolution_and_more"
    )
    migration._backfill_scope_resolutions_and_deduplicate_snapshots(
        django_apps,
        SimpleNamespace(connection=connection),
    )

    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: None)
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache", lambda **_: None)

    resolved_first, source_first = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=first_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )
    resolved_second, source_second = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=second_database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )
    first_resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=str(default_tenant.id),
        database=first_database,
        snapshot=resolved_first,
    )
    second_resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=str(default_tenant.id),
        database=second_database,
        snapshot=resolved_second,
    )

    assert source_first == "db"
    assert source_second == "db"
    assert resolved_first.id == first_snapshot.id
    assert resolved_second.id == second_snapshot.id
    assert first_resolution.resolution_mode == "database_scope"
    assert second_resolution.resolution_mode == "database_scope"
    assert PoolODataMetadataCatalogScopeResolution.objects.filter(tenant=default_tenant).count() == 2


@pytest.mark.django_db
def test_business_identity_persistence_constraints_ignore_extensions_fingerprint(
    default_tenant: Tenant,
) -> None:
    database = _create_database(
        tenant=default_tenant,
        name=f"meta-constraint-db-{uuid4().hex[:8]}",
        base_name="shared-constraints-profile",
        version="8.3.26",
    )
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=database,
        config_name="shared-constraints-profile",
        config_version="8.3.26",
        extensions_fingerprint="fingerprint-a",
        metadata_hash="a" * 64,
        catalog_version=f"v1:{uuid4().hex[:16]}",
        payload=_catalog_payload(suffix="constraint"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant=default_tenant,
        database=database,
        snapshot=snapshot,
        config_name="shared-constraints-profile",
        config_version="8.3.26",
        extensions_fingerprint="fingerprint-a",
        confirmed_at=snapshot.fetched_at,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        PoolODataMetadataCatalogSnapshot.objects.create(
            tenant=default_tenant,
            database=database,
            config_name="shared-constraints-profile",
            config_version="8.3.26",
            extensions_fingerprint="fingerprint-b",
            metadata_hash="b" * 64,
            catalog_version=snapshot.catalog_version,
            payload=_catalog_payload(suffix="constraint-dup"),
            source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
            is_current=False,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        PoolODataMetadataCatalogScopeResolution.objects.create(
            tenant=default_tenant,
            database=database,
            snapshot=snapshot,
            config_name="shared-constraints-profile",
            config_version="8.3.26",
            extensions_fingerprint="fingerprint-b",
            confirmed_at=snapshot.fetched_at,
        )


@pytest.mark.django_db
def test_business_identity_backfill_reuses_canonical_snapshot_across_extensions_fingerprint_drift(
    default_tenant: Tenant,
) -> None:
    shared_name = "shared-profile-backfill"
    shared_version = "8.3.26"
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-backfill-db-{uuid4().hex[:8]}",
        base_name=f"legacy-infobase-{uuid4().hex[:4]}",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-backfill-db-{uuid4().hex[:8]}",
        base_name=f"legacy-infobase-{uuid4().hex[:4]}",
        version="8.3.24",
    )
    for database in (first_database, second_database):
        metadata = dict(database.metadata or {})
        profile = dict(metadata.get("business_configuration_profile") or {})
        profile["config_name"] = shared_name
        profile["config_version"] = shared_version
        metadata["business_configuration_profile"] = profile
        database.metadata = metadata
        database.save(update_fields=["metadata", "updated_at"])
    DatabaseExtensionsSnapshot.objects.create(
        database=first_database,
        snapshot={"extensions": [{"name": "CoreA", "version": "1.0.0"}]},
    )
    DatabaseExtensionsSnapshot.objects.create(
        database=second_database,
        snapshot={"extensions": [{"name": "CoreB", "version": "1.0.0"}]},
    )

    shared_catalog_version = f"v1:{uuid4().hex[:16]}"
    first_snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=first_database,
        config_name=first_database.base_name,
        config_version=first_database.version,
        extensions_fingerprint="legacy-ext-a",
        metadata_hash="a" * 64,
        catalog_version=shared_catalog_version,
        payload=_catalog_payload(suffix="backfill-a"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    second_snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=second_database,
        config_name=second_database.base_name,
        config_version=second_database.version,
        extensions_fingerprint="legacy-ext-b",
        metadata_hash="a" * 64,
        catalog_version=shared_catalog_version,
        payload=_catalog_payload(suffix="backfill-a"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant=default_tenant,
        database=first_database,
        snapshot=first_snapshot,
        config_name=first_database.base_name,
        config_version=first_database.version,
        extensions_fingerprint="legacy-ext-a",
        confirmed_at=first_snapshot.fetched_at,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant=default_tenant,
        database=second_database,
        snapshot=second_snapshot,
        config_name=second_database.base_name,
        config_version=second_database.version,
        extensions_fingerprint="legacy-ext-b",
        confirmed_at=second_snapshot.fetched_at,
    )

    first_result = backfill_database_business_identity_scope(database=first_database)
    second_result = backfill_database_business_identity_scope(database=second_database)

    canonical_snapshots = list(
        PoolODataMetadataCatalogSnapshot.objects.filter(
            tenant=default_tenant,
            config_name=shared_name,
            config_version=shared_version,
            catalog_version=shared_catalog_version,
        )
    )
    assert len(canonical_snapshots) == 1
    canonical_snapshot = canonical_snapshots[0]
    assert first_result["snapshot_id"] == str(canonical_snapshot.id)
    assert second_result["snapshot_id"] == str(canonical_snapshot.id)

    resolutions = list(
        PoolODataMetadataCatalogScopeResolution.objects.filter(
            tenant=default_tenant,
            config_name=shared_name,
            config_version=shared_version,
        ).order_by("database_id")
    )
    assert {str(item.database_id) for item in resolutions} == {
        str(first_database.id),
        str(second_database.id),
    }
    assert {str(item.snapshot_id) for item in resolutions} == {str(canonical_snapshot.id)}
    assert canonical_snapshot.extensions_fingerprint != ""
    assert len({item.extensions_fingerprint for item in resolutions}) == 2


@pytest.mark.django_db
def test_refresh_snapshot_returns_lock_conflict_without_fetching_metadata(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-lock-db-{uuid4().hex[:8]}")
    fetch_calls = {"count": 0}

    def _unexpected_fetch(**_: object) -> dict[str, object]:
        fetch_calls["count"] += 1
        return _catalog_payload(suffix="should-not-happen")

    class _LockedSelector:
        def only(self, *_args: object, **_kwargs: object) -> "_LockedSelector":
            return self

        def get(self, **_kwargs: object) -> Database:
            raise DatabaseError("lock not available")

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._fetch_live_catalog_payload",
        _unexpected_fetch,
    )
    monkeypatch.setattr(Database.objects, "select_for_update", lambda **_: _LockedSelector())

    with pytest.raises(MetadataCatalogError) as exc_info:
        refresh_metadata_catalog_snapshot(
            tenant_id=str(default_tenant.id),
            database=database,
            requested_by_username="meta-user",
            source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        )

    assert exc_info.value.code == ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS
    assert fetch_calls["count"] == 0


@pytest.mark.django_db
def test_fetch_live_catalog_payload_includes_upstream_odata_error_details(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-fetch-error-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)

    class _Response:
        status_code = 500
        text = (
            '{"exception":{"descr":"Ошибка при выполнении запроса GET к ресурсу /odata/standard.odata/$metadata:",'
            '"inner":{"descr":"На сервере 1С:Предприятия не найдена лицензия."}}}'
        )
        headers = {"Content-Type": "application/json; charset=utf-8"}

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata",
        lambda *_args, **_kwargs: _Response(),
    )

    with pytest.raises(MetadataCatalogError) as exc_info:
        _fetch_live_catalog_payload(
            database=database,
            requested_by_username="meta-user",
        )

    assert exc_info.value.code == ERROR_CODE_POOL_METADATA_FETCH_FAILED
    assert exc_info.value.status_code == 502
    assert "HTTP 500" in exc_info.value.detail
    assert "не найдена лицензия" in exc_info.value.detail.lower()
    assert exc_info.value.errors
    first_error = exc_info.value.errors[0]
    assert first_error["path"] == "$metadata"
    assert "не найдена лицензия" in str(first_error["detail"]).lower()


@pytest.mark.django_db
def test_fetch_live_catalog_payload_forbidden_is_reported_as_auth_configuration_error(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-fetch-forbidden-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)

    class _Response:
        status_code = 403
        text = (
            '{"exception":{"descr":"HTTP: Forbidden",'
            '"inner":{"descr":"База данных заблокирована: приложение Конфигуратор"}}}'
        )
        headers = {"Content-Type": "application/json; charset=utf-8"}

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata",
        lambda *_args, **_kwargs: _Response(),
    )

    with pytest.raises(MetadataCatalogError) as exc_info:
        _fetch_live_catalog_payload(
            database=database,
            requested_by_username="meta-user",
        )

    assert exc_info.value.code == ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED
    assert exc_info.value.status_code == 400
    assert "rejected by odata endpoint" in exc_info.value.detail.lower()
    assert "база данных заблокирована" in exc_info.value.detail.lower()
    assert exc_info.value.errors
    assert exc_info.value.errors[0]["code"] == ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED
    assert "база данных заблокирована" in str(exc_info.value.errors[0]["detail"]).lower()


@pytest.mark.django_db
def test_fetch_live_catalog_payload_rejects_non_local_plain_http_before_network_call(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-fetch-http-db-{uuid4().hex[:8]}")
    database.odata_url = "http://odata.example.test/odata/standard.odata"
    database.save(update_fields=["odata_url"])
    _create_service_infobase_mapping(database=database)

    fetch_calls = {"count": 0}

    def _unexpected_fetch(*_args: object, **_kwargs: object) -> object:
        fetch_calls["count"] += 1
        return SimpleNamespace(status_code=200, text="<ok/>", headers={"Content-Type": "application/xml"})

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata",
        _unexpected_fetch,
    )

    with pytest.raises(MetadataCatalogError) as exc_info:
        _fetch_live_catalog_payload(
            database=database,
            requested_by_username="meta-user",
        )

    assert exc_info.value.code == ERROR_CODE_POOL_METADATA_FETCH_FAILED
    assert exc_info.value.status_code == 400
    assert "https" in exc_info.value.detail.lower()
    assert fetch_calls["count"] == 0


@pytest.mark.django_db
def test_read_snapshot_falls_back_to_db_when_cache_miss(default_tenant: Tenant, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-read-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    profile = (database.metadata or {}).get("business_configuration_profile") or {}
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=database,
        config_name=profile["config_name"],
        config_version=profile["config_version"],
        extensions_fingerprint="",
        metadata_hash="a" * 64,
        catalog_version="v1:test",
        payload=_catalog_payload(suffix="db"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )

    write_calls = {"count": 0}
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._read_snapshot_from_cache", lambda **_: None)
    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache",
        lambda **_: write_calls.__setitem__("count", write_calls["count"] + 1),
    )

    resolved, source = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    assert source == "db"
    assert resolved.id == snapshot.id
    assert write_calls["count"] == 1
    resolution = PoolODataMetadataCatalogScopeResolution.objects.get(
        tenant=default_tenant,
        database=database,
    )
    assert resolution.snapshot_id == snapshot.id


@pytest.mark.django_db
def test_read_snapshot_returns_redis_hit_without_db_lookup(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-redis-hit-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    profile = (database.metadata or {}).get("business_configuration_profile") or {}
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=database,
        config_name=profile["config_name"],
        config_version=profile["config_version"],
        extensions_fingerprint="",
        metadata_hash="b" * 64,
        catalog_version="v1:redis-hit",
        payload=_catalog_payload(suffix="redis"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )
    PoolODataMetadataCatalogScopeResolution.objects.create(
        tenant=default_tenant,
        database=database,
        snapshot=snapshot,
        config_name=profile["config_name"],
        config_version=profile["config_version"],
        extensions_fingerprint="",
        confirmed_at=snapshot.fetched_at,
    )

    class _RedisClient:
        def __init__(self) -> None:
            self._value = json.dumps(
                {
                    "scope": {
                        "tenant_id": str(default_tenant.id),
                        "database_id": str(database.id),
                        "config_name": profile["config_name"],
                        "config_version": profile["config_version"],
                        "extensions_fingerprint": "",
                    },
                    "snapshot": {
                        "id": str(snapshot.id),
                        "tenant_id": str(default_tenant.id),
                        "database_id": str(database.id),
                        "config_name": profile["config_name"],
                        "config_version": profile["config_version"],
                        "extensions_fingerprint": "",
                        "metadata_hash": snapshot.metadata_hash,
                        "catalog_version": snapshot.catalog_version,
                        "payload": snapshot.payload,
                        "source": snapshot.source,
                        "fetched_at": snapshot.fetched_at.isoformat(),
                        "is_current": True,
                    },
                },
                ensure_ascii=False,
            )

        def get(self, _key: str) -> str:
            return self._value

        def close(self) -> None:
            return None

    db_lookup_calls = {"count": 0}

    def _unexpected_db_lookup(**_kwargs: object) -> PoolODataMetadataCatalogSnapshot | None:
        db_lookup_calls["count"] += 1
        return None

    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: _RedisClient())
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_current_snapshot", _unexpected_db_lookup)

    resolved, source = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    assert source == "redis"
    assert resolved.id == snapshot.id
    assert db_lookup_calls["count"] == 0


@pytest.mark.django_db
def test_read_snapshot_adopts_database_scope_resolution_on_redis_hit(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-redis-adopt-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    profile = (database.metadata or {}).get("business_configuration_profile") or {}
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=database,
        config_name=profile["config_name"],
        config_version=profile["config_version"],
        extensions_fingerprint="",
        metadata_hash="ba" * 32,
        catalog_version="v1:redis-adopt",
        payload=_catalog_payload(suffix="redis-adopt"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )

    class _RedisClient:
        def __init__(self) -> None:
            self._value = json.dumps(
                {
                    "scope": {
                        "tenant_id": str(default_tenant.id),
                        "database_id": str(database.id),
                        "config_name": profile["config_name"],
                        "config_version": profile["config_version"],
                        "extensions_fingerprint": "",
                    },
                    "snapshot": {
                        "id": str(snapshot.id),
                        "tenant_id": str(default_tenant.id),
                        "database_id": str(database.id),
                        "config_name": profile["config_name"],
                        "config_version": profile["config_version"],
                        "extensions_fingerprint": "",
                        "metadata_hash": snapshot.metadata_hash,
                        "catalog_version": snapshot.catalog_version,
                        "payload": snapshot.payload,
                        "source": snapshot.source,
                        "fetched_at": snapshot.fetched_at.isoformat(),
                        "is_current": True,
                    },
                },
                ensure_ascii=False,
            )

        def get(self, _key: str) -> str:
            return self._value

        def close(self) -> None:
            return None

    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: _RedisClient())

    resolved, source = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )
    resolution = PoolODataMetadataCatalogScopeResolution.objects.get(
        tenant=default_tenant,
        database=database,
    )
    described = describe_metadata_catalog_snapshot_resolution(
        tenant_id=str(default_tenant.id),
        database=database,
        snapshot=resolved,
    )

    assert source == "db"
    assert resolved.id == snapshot.id
    assert resolution.snapshot_id == snapshot.id
    assert described.resolution_mode == "database_scope"
    assert described.is_shared_snapshot is False


@pytest.mark.django_db
def test_read_shared_snapshot_from_redis_preserves_provenance_database(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_database = _create_database(
        tenant=default_tenant,
        name=f"meta-redis-shared-a-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    second_database = _create_database(
        tenant=default_tenant,
        name=f"meta-redis-shared-b-{uuid4().hex[:8]}",
        base_name="shared-profile",
        version="8.3.24",
    )
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=first_database,
        config_name="shared-profile",
        config_version="8.3.24",
        extensions_fingerprint="",
        metadata_hash="b" * 64,
        catalog_version="v1:redis-shared",
        payload=_catalog_payload(suffix="redis-shared"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )

    class _RedisClient:
        def __init__(self) -> None:
            self._value = json.dumps(
                {
                    "scope": {
                        "tenant_id": str(default_tenant.id),
                        "database_id": str(second_database.id),
                        "config_name": "shared-profile",
                        "config_version": "8.3.24",
                        "extensions_fingerprint": "",
                    },
                    "snapshot": {
                        "id": str(snapshot.id),
                        "tenant_id": str(default_tenant.id),
                        "database_id": str(first_database.id),
                        "config_name": "shared-profile",
                        "config_version": "8.3.24",
                        "extensions_fingerprint": "",
                        "metadata_hash": snapshot.metadata_hash,
                        "catalog_version": snapshot.catalog_version,
                        "payload": snapshot.payload,
                        "source": snapshot.source,
                        "fetched_at": snapshot.fetched_at.isoformat(),
                        "is_current": True,
                    },
                },
                ensure_ascii=False,
            )

        def get(self, _key: str) -> str:
            return self._value

        def close(self) -> None:
            return None

    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: _RedisClient())
    scope = resolve_metadata_catalog_scope(tenant_id=str(default_tenant.id), database=second_database)
    resolved = _read_snapshot_from_cache(scope=scope)
    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=str(default_tenant.id),
        database=second_database,
        snapshot=resolved,
    )

    assert resolved is not None
    assert resolved.id == snapshot.id
    assert resolved.database_id == first_database.id
    assert resolution.resolution_mode == "shared_scope"
    assert resolution.is_shared_snapshot is True
    assert resolution.provenance_database_id == str(first_database.id)
    assert resolution.provenance_confirmed_at == snapshot.fetched_at


@pytest.mark.django_db
def test_read_snapshot_falls_back_to_db_when_redis_read_fails(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-redis-fail-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)
    profile = (database.metadata or {}).get("business_configuration_profile") or {}
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=database,
        config_name=profile["config_name"],
        config_version=profile["config_version"],
        extensions_fingerprint="",
        metadata_hash="c" * 64,
        catalog_version="v1:redis-fallback",
        payload=_catalog_payload(suffix="db-fallback"),
        source=PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
        is_current=True,
    )

    class _BrokenRedisClient:
        def get(self, _key: str) -> str | None:
            raise RuntimeError("redis unavailable")

        def close(self) -> None:
            return None

    write_calls = {"count": 0}
    monkeypatch.setattr("apps.intercompany_pools.metadata_catalog._get_redis_client", lambda: _BrokenRedisClient())
    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog._write_snapshot_to_cache",
        lambda **_: write_calls.__setitem__("count", write_calls["count"] + 1),
    )

    resolved, source = read_metadata_catalog_snapshot(
        tenant_id=str(default_tenant.id),
        database=database,
        requested_by_username="meta-user",
        allow_cold_bootstrap=False,
    )

    assert source == "db"
    assert resolved.id == snapshot.id
    assert write_calls["count"] == 1


def test_validate_document_policy_references_accepts_row_mapping_from_companion_entity_fields() -> None:
    snapshot = SimpleNamespace(
        payload={
            "documents": [
                {
                    "entity_name": "Document_Sales",
                    "display_name": "Sales",
                    "fields": [
                        {"name": "Amount", "type": "Edm.Decimal", "nullable": False},
                    ],
                    "table_parts": [
                        {"name": "Items", "row_fields": []},
                    ],
                },
                {
                    "entity_name": "Document_Sales_Items",
                    "display_name": "Sales Items",
                    "fields": [
                        {"name": "LineNumber", "type": "Edm.Int32", "nullable": False},
                        {"name": "Qty", "type": "Edm.Decimal", "nullable": False},
                    ],
                    "table_parts": [],
                },
            ]
        }
    )
    policy = {
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
                        "table_parts_mapping": {
                            "Items": {"Qty": "allocation.lines.qty"}
                        },
                        "link_rules": {},
                    }
                ],
            }
        ],
    }

    errors = validate_document_policy_references(
        policy=policy,
        snapshot=snapshot,  # type: ignore[arg-type]
    )

    assert errors == []


@pytest.mark.django_db
def test_metadata_credentials_resolution_is_mapping_only_without_legacy_fallback(
    default_tenant: Tenant,
    user: User,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-auth-db-{uuid4().hex[:8]}")

    with pytest.raises(MetadataCatalogError) as exc_info:
        _resolve_metadata_mapping_credentials(
            database=database,
            requested_by_username=user.username,
        )

    assert exc_info.value.code == ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED
    assert "mapping" in exc_info.value.detail.lower()
    # Guardrail: legacy Database.username/password must not be used for metadata path.
    assert database.username == "legacy-user"
    assert str(database.password) != ""


@pytest.mark.django_db
def test_metadata_credentials_resolution_prefers_service_mapping_over_actor_mapping(
    default_tenant: Tenant,
    user: User,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-auth-priority-db-{uuid4().hex[:8]}")
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-user",
        ib_password="actor-pass",
    )
    _create_service_infobase_mapping(
        database=database,
        username="svc-user",
        password="svc-pass",
    )

    username, password = _resolve_metadata_mapping_credentials(
        database=database,
        requested_by_username=user.username,
    )

    assert username == "svc-user"
    assert password == "svc-pass"
