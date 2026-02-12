import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.intercompany_pools.models import Organization, OrganizationStatus
from apps.intercompany_pools.sync import sync_organizations
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_sync_organizations_creates_and_updates_without_duplicates() -> None:
    tenant = Tenant.objects.create(slug="pool-sync", name="Pool Sync")

    first_pass = sync_organizations(
        tenant=tenant,
        rows=[
            {"inn": "300000000001", "name": "Org A"},
            {"inn": "300000000002", "name": "Org B", "status": OrganizationStatus.INACTIVE},
        ],
    )
    assert first_pass.created == 2
    assert first_pass.updated == 0
    assert first_pass.skipped == 0
    assert Organization.objects.filter(tenant=tenant).count() == 2

    second_pass = sync_organizations(
        tenant=tenant,
        rows=[
            {"inn": "300000000001", "name": "Org A Updated"},
            {"inn": "300000000002", "name": "Org B", "status": OrganizationStatus.INACTIVE},
        ],
    )
    assert second_pass.created == 0
    assert second_pass.updated == 1
    assert second_pass.skipped == 1
    assert Organization.objects.filter(tenant=tenant).count() == 2
    assert Organization.objects.get(tenant=tenant, inn="300000000001").name == "Org A Updated"


@pytest.mark.django_db
def test_sync_organizations_rejects_unknown_database() -> None:
    tenant = Tenant.objects.create(slug="pool-sync-unknown-db", name="Pool Sync Unknown DB")

    with pytest.raises(ValidationError, match="unknown database_id"):
        sync_organizations(
            tenant=tenant,
            rows=[{"inn": "310000000001", "name": "Org", "database_id": "missing"}],
        )


@pytest.mark.django_db
def test_sync_organizations_enforces_one_to_one_database_link() -> None:
    tenant = Tenant.objects.create(slug="pool-sync-db", name="Pool Sync DB")
    database = Database.objects.create(
        tenant=tenant,
        name="pool-sync-db-1",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )

    sync_organizations(
        tenant=tenant,
        rows=[{"inn": "320000000001", "name": "Org 1", "database_id": database.id}],
    )
    with pytest.raises(ValidationError, match="already linked to another organization"):
        sync_organizations(
            tenant=tenant,
            rows=[{"inn": "320000000002", "name": "Org 2", "database_id": database.id}],
        )
