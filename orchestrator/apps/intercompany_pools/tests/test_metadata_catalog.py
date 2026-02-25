from __future__ import annotations
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError

from apps.databases.models import Database
from apps.intercompany_pools.metadata_catalog import (
    ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS,
    ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
    MetadataCatalogError,
    _resolve_metadata_mapping_credentials,
    read_metadata_catalog_snapshot,
    refresh_metadata_catalog_snapshot,
)
from apps.intercompany_pools.models import (
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogSnapshotSource,
)
from apps.tenancy.models import Tenant, TenantMember


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )


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
def test_read_snapshot_falls_back_to_db_when_cache_miss(default_tenant: Tenant, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-read-db-{uuid4().hex[:8]}")
    snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=default_tenant,
        database=database,
        config_name=database.name,
        config_version="",
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
