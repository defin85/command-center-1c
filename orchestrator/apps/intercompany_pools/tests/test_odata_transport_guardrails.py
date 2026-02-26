from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools import metadata_catalog
from apps.intercompany_pools.metadata_catalog import (
    ERROR_CODE_POOL_METADATA_FETCH_FAILED,
    MetadataCatalogError,
    _fetch_live_catalog_payload,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )


def _create_service_infobase_mapping(*, database: Database, username: str = "svc-user", password: str = "svc-pass") -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=username,
        ib_password=password,
        is_service=True,
    )


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.mark.django_db
def test_metadata_catalog_path_does_not_use_direct_requests_get() -> None:
    source = Path(metadata_catalog.__file__).read_text(encoding="utf-8")
    assert "ODataMetadataAdapter(" in source
    assert "requests.get(" not in source


@pytest.mark.django_db
def test_fetch_live_catalog_payload_transport_error_keeps_machine_readable_shape(
    default_tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"meta-transport-error-db-{uuid4().hex[:8]}")
    _create_service_infobase_mapping(database=database)

    def _raise_transport_error(*_args: object, **_kwargs: object) -> object:
        raise metadata_catalog.ODataMetadataTransportError("transport unavailable")

    monkeypatch.setattr(
        "apps.intercompany_pools.metadata_catalog.ODataMetadataAdapter.fetch_metadata",
        _raise_transport_error,
    )

    with pytest.raises(MetadataCatalogError) as exc_info:
        _fetch_live_catalog_payload(
            database=database,
            requested_by_username="meta-user",
        )

    assert exc_info.value.code == ERROR_CODE_POOL_METADATA_FETCH_FAILED
    assert exc_info.value.status_code == 502
    assert exc_info.value.errors
    assert exc_info.value.errors[0]["code"] == ERROR_CODE_POOL_METADATA_FETCH_FAILED
    assert exc_info.value.errors[0]["path"] == "$metadata"
