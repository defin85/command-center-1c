from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
)
from apps.intercompany_pools.validators import validate_pool_graph
from apps.tenancy.models import Tenant


def test_validate_pool_graph_accepts_valid_dag() -> None:
    snapshot = validate_pool_graph(
        node_ids=["root", "a", "b", "c"],
        edge_pairs=[("root", "a"), ("a", "b"), ("a", "c")],
    )

    assert snapshot.root_id == "root"
    assert len(snapshot.node_ids) == 4


def test_validate_pool_graph_rejects_cycle() -> None:
    with pytest.raises(ValidationError, match="acyclic"):
        validate_pool_graph(
            node_ids=["root", "a", "b"],
            edge_pairs=[("root", "a"), ("a", "b"), ("b", "a")],
        )


def test_validate_pool_graph_rejects_multiple_roots() -> None:
    with pytest.raises(ValidationError, match="exactly one root"):
        validate_pool_graph(
            node_ids=["root", "a", "orphan"],
            edge_pairs=[("root", "a")],
        )


def test_validate_pool_graph_rejects_deep_multi_parent() -> None:
    with pytest.raises(ValidationError, match="Multi-parent links"):
        validate_pool_graph(
            node_ids=["root", "a", "b", "c"],
            edge_pairs=[("root", "a"), ("root", "b"), ("a", "c"), ("b", "c")],
        )


@pytest.mark.django_db
def test_organization_pool_validate_graph_for_date() -> None:
    tenant = Tenant.objects.create(slug="pool-test", name="Pool Test")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="core",
        name="Core Pool",
    )

    root_org = Organization.objects.create(tenant=tenant, name="Root", inn="100000000001")
    child_org = Organization.objects.create(tenant=tenant, name="Child", inn="100000000002")
    orphan_org = Organization.objects.create(tenant=tenant, name="Orphan", inn="100000000003")

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

    pool.validate_graph(date(2026, 1, 1))

    PoolNodeVersion.objects.create(
        pool=pool,
        organization=orphan_org,
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(ValidationError, match="exactly one root"):
        pool.validate_graph(date(2026, 1, 1))


@pytest.mark.django_db
def test_organization_database_link_is_one_to_one() -> None:
    tenant = Tenant.objects.create(slug="pool-db-link", name="Pool DB Link")
    database = Database.objects.create(
        tenant=tenant,
        name="pool-db-link-db",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )

    Organization.objects.create(
        tenant=tenant,
        database=database,
        name="Org 1",
        inn="200000000001",
    )

    with pytest.raises(IntegrityError):
        Organization.objects.create(
            tenant=tenant,
            database=database,
            name="Org 2",
            inn="200000000002",
        )
